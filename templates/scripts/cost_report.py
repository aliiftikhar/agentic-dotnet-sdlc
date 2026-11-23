#!/usr/bin/env python3
"""Token and cost report for one OpenSpec change, from local agent session logs.

Reads Claude Code logs (~/.claude/projects/<repo>/) and Codex logs (~/.codex/sessions/), finds the
work that belongs to the change (by branch, and by the change the OpenSpec step markers name),
splits it into steps, prices it from scripts/model-prices.json and writes cost.md in the change
folder. Only model names, token counts, timestamps, branches and step markers are read: no
conversation text reaches the report. Standard library only. See "Cost report" in AGENTS.md.
"""

import argparse
import datetime
import glob
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PRICES = REPO / "scripts" / "model-prices.json"

STEP_ORDER = ["Plan", "Build", "Verify", "Policy review", "Archive", "PR and review", "Other"]
MARKER_STEPS = {
    "explore": "Plan", "propose": "Plan", "update": "Plan", "update-change": "Plan",
    "apply": "Build", "apply-change": "Build",
    "archive": "Archive", "archive-change": "Archive",
}
CI_AGENT = "Claude Code (CI)"
CI_USAGE = "ci-usage.jsonl"
TRUNK = {None, "", "HEAD", "main", "master"}
NAME_RE = re.compile(r"[a-z0-9][a-z0-9-]*")
CLAUDE_COMMAND = re.compile(r"<command-name>/?([^<]+)</command-name>")
CLAUDE_ARGS = re.compile(r"<command-args>([^<]*)</command-args>", re.S)
CODEX_MARKER = re.compile(r"\$(openspec-[a-z-]+|policy-review)\b([^\n]*)")


def zero():
    return {"input": 0, "cache_write_5m": 0, "cache_write_1h": 0, "cache_read": 0, "output": 0}


# ---------- markers ----------

def marker_step(skill):
    """Step for a skill or command name, or None if it isn't a step marker."""
    skill = skill.strip().lstrip("/$")
    if skill == "policy-review":
        return "Policy review"
    for prefix in ("opsx:", "openspec-"):
        if skill.startswith(prefix):
            return MARKER_STEPS.get(skill[len(prefix):])
    return None


KNOWN_CHANGES = set()  # names of the repo's changes, active and archived; set by build_report


def known_changes(repo):
    folder = Path(repo) / "openspec" / "changes"
    names = {p.name for p in folder.glob("*") if p.is_dir() and p.name != "archive"}
    names |= {re.sub(r"^\d{4}-\d{2}-\d{2}-", "", p.name) for p in (folder / "archive").glob("*") if p.is_dir()}
    return names


def marker_target(args, change):
    """'ours' if the marker's arguments name the change, 'other' if they name another, else None.
    Another change is a first word that is one of the repo's change names (single words included),
    or any other hyphenated name."""
    if re.search(r"(?<![a-z0-9-])" + re.escape(change) + r"(?![a-z0-9-])", args or ""):
        return "ours"
    first = (args or "").strip().split()
    word = first[0].rstrip(":,.;") if first else ""
    if NAME_RE.fullmatch(word) and (word in KNOWN_CHANGES or "-" in word):
        return "other"
    return None


# ---------- prices ----------

def load_prices(path=PRICES):
    with open(path) as f:
        return json.load(f)


def price_for(prices, model):
    if not model:
        return None
    models = prices.get("models", {})
    base = re.sub(r"\[[^\]]*\]$", "", model)
    return models.get(model) or models.get(base)


def cost_of(rates, tokens):
    if rates is None:
        return None
    prompt = tokens["input"] + tokens["cache_read"] + tokens["cache_write_5m"] + tokens["cache_write_1h"]
    if "long_context_over" in rates and prompt > rates["long_context_over"]:
        rates = rates["long_context"]
    return sum(tokens[k] * rates.get(k, 0) for k in tokens) / 1e6


# ---------- Claude Code ----------

def claude_project_dirs(claude_dir, repo):
    """The repo's own project folder, plus Claude Code worktrees inside it (<repo>/.claude/worktrees/<name>).
    Not other checkouts whose path merely starts with the same characters."""
    name = re.sub(r"[^A-Za-z0-9]", "-", str(repo))  # Claude Code's folder name: every other character becomes "-"
    dirs = [os.path.join(claude_dir, name)] + glob.glob(os.path.join(claude_dir, name + "--claude-worktrees-*"))
    return sorted(d for d in dirs if os.path.isdir(d))


def in_repo(path, repo):
    path, repo = str(path).rstrip("/"), str(repo).rstrip("/")
    return path == repo or path.startswith(repo + "/")


def read_jsonl(path):
    with open(path, errors="replace") as f:
        for line in f:
            try:
                yield json.loads(line)
            except ValueError:
                continue


def claude_usage(usage):
    t = zero()
    t["input"] = usage.get("input_tokens", 0) or 0
    t["output"] = usage.get("output_tokens", 0) or 0
    t["cache_read"] = usage.get("cache_read_input_tokens", 0) or 0
    created = usage.get("cache_creation") or {}
    if created:
        t["cache_write_5m"] = created.get("ephemeral_5m_input_tokens", 0) or 0
        t["cache_write_1h"] = created.get("ephemeral_1h_input_tokens", 0) or 0
    else:
        t["cache_write_5m"] = usage.get("cache_creation_input_tokens", 0) or 0
    return t


def is_human_prompt(entry):
    """A message a person typed. Tool results, and notices the app injects as tagged text
    (<task-notification>, <local-command-stdout>, <system-reminder>, ...), are not."""
    if entry.get("type") != "user" or entry.get("isMeta"):
        return False
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, list):
        if any(isinstance(c, dict) and c.get("type") == "tool_result" for c in content):
            return False
        content = " ".join(c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text")
    return isinstance(content, str) and bool(content.strip()) and not content.lstrip().startswith("<")


def claude_responses(path):
    """Each response once (last line for its message id wins), in order, plus markers, in log order."""
    events, by_id = [], {}
    for entry in read_jsonl(path):
        kind = entry.get("type")
        if kind == "assistant":
            msg = entry.get("message") or {}
            key = msg.get("id") or entry.get("uuid")
            found = []
            for block in msg.get("content") or []:
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue
                inp = block.get("input") or {}
                if block.get("name") == "Skill" and marker_step(inp.get("skill", "")):
                    found.append({"kind": "marker", "step": marker_step(inp["skill"]), "args": inp.get("args", ""),
                                  "time": entry.get("timestamp")})
                elif block.get("name") in ("Agent", "Task"):
                    found.append({"kind": "spawn", "id": block.get("id"), "type": inp.get("subagent_type"),
                                  "branch": entry.get("gitBranch"), "time": entry.get("timestamp")})
            # Markers go before their response: the response that starts a step belongs to that step. A
            # response is logged as several lines (thinking, text, tool call), so a marker can arrive after
            # its response was first seen; it then goes in front of that response.
            if key in by_id:
                existing = by_id[key]
                at = next(i for i in range(len(events) - 1, -1, -1) if events[i] is existing)
                events[at:at] = found
                existing.update(usage=msg.get("usage") or {}, model=msg.get("model"))
                continue
            events.extend(found)
            ev = {"kind": "response", "model": msg.get("model"), "usage": msg.get("usage") or {},
                  "branch": entry.get("gitBranch"), "time": entry.get("timestamp")}
            by_id[key] = ev
            events.append(ev)
        elif kind == "user":
            content = (entry.get("message") or {}).get("content")
            text = content if isinstance(content, str) else " ".join(
                c.get("text", "") for c in content or [] if isinstance(c, dict) and c.get("type") == "text")
            command = CLAUDE_COMMAND.search(text or "")
            if command and marker_step(command.group(1)):
                args = CLAUDE_ARGS.search(text)
                events.append({"kind": "marker", "step": marker_step(command.group(1)),
                               "args": args.group(1) if args else "", "time": entry.get("timestamp")})
            elif is_human_prompt(entry):
                events.append({"kind": "prompt", "time": entry.get("timestamp")})
        elif kind == "cost-state":
            events.append({"kind": "cost-state", "total": sum(
                (m.get("costUSD") or 0) for m in (entry.get("modelUsage") or {}).values())})
    return events


def walk_session(events, change, branch):
    """Yield (event, step) for the responses that belong to the change, and the spawn steps by id."""
    counted, spawns = [], {}
    context, step, seen_marker = None, "Plan", False
    pending = []  # responses before the session's first marker
    pending_spawns, spawns_branch = [], {}
    for ev in events:
        kind = ev["kind"]
        if kind == "marker":
            target = marker_target(ev["args"], change)
            if not seen_marker:
                seen_marker = True
                if target == "ours":
                    counted.extend((p, "Plan") for p in pending if p["branch"] in TRUNK or p["branch"] == branch)
                    # Subagents started in that discussion (e.g. an investigation) count as Plan too.
                    for sid in pending_spawns:
                        kind_, _, _, time_ = spawns[sid]
                        on = spawns_branch[sid] in TRUNK or spawns_branch[sid] == branch
                        spawns[sid] = (kind_, "Plan", on, time_)
                pending = []
                pending_spawns = []
            if target is not None:
                context = target
            step = ev["step"]
        elif kind == "prompt":
            if step == "Archive":
                step = "PR and review"
            elif step == "Policy review":
                step = "Build"
        elif kind == "spawn":
            if not seen_marker:
                # Like the responses around it: on the branch, its step is decided by time; off it, it waits
                # for the session's first marker.
                spawns[ev["id"]] = (ev["type"], None, ev.get("branch") == branch and branch not in TRUNK, ev.get("time"))
                spawns_branch[ev["id"]] = ev.get("branch")
                if not spawns[ev["id"]][2]:
                    pending_spawns.append(ev["id"])
            else:
                spawns[ev["id"]] = (ev["type"], step, belongs(ev.get("branch"), context, branch, seen_marker), ev.get("time"))
        elif kind == "response":
            if not seen_marker:
                if ev["branch"] == branch and branch not in TRUNK:
                    counted.append((ev, None))  # step decided by time, across sessions
                else:
                    pending.append(ev)
            elif belongs(ev["branch"], context, branch, seen_marker):
                counted.append((ev, step))
    return counted, spawns


def belongs(ev_branch, context, branch, seen_marker):
    if ev_branch == branch and branch not in TRUNK:
        return context != "other"
    if ev_branch not in TRUNK and ev_branch is not None:
        return False  # another feature branch
    return seen_marker and context == "ours"


def step_by_time(time, apply_at, archive_at):
    if archive_at and time and time >= archive_at:
        return "PR and review"
    if apply_at and time and time >= apply_at:
        return "Build"
    return "Plan"


def marker_times(event_lists, change):
    """Times of the change's first apply marker and last archive marker, across all sessions."""
    apply_at = archive_at = None
    for events in event_lists:
        context = None
        for ev in events:
            if ev["kind"] != "marker":
                continue
            context = marker_target(ev["args"], change) or context
            if context == "ours" and ev["step"] == "Build" and ev["time"] and (not apply_at or ev["time"] < apply_at):
                apply_at = ev["time"]
            if context == "ours" and ev["step"] == "Archive" and ev["time"] and (not archive_at or ev["time"] > archive_at):
                archive_at = ev["time"]
    return apply_at, archive_at


def claude_sessions(claude_dir, repo):
    paths = []
    if not claude_dir:
        return []
    for project in claude_project_dirs(claude_dir, repo):
        paths.extend(sorted(glob.glob(os.path.join(project, "*.jsonl"))))
    return [(path, claude_responses(path)) for path in paths]


def claude_rows(sessions, change, branch, prices, add, apply_at, archive_at):
    """Add Claude Code rows. Returns the Other cost."""
    other = 0.0
    for path, events in sessions:
        counted, spawns = walk_session(events, change, branch)
        session_cost = ours_cost = 0.0
        all_costs = {}
        for ev in events:
            if ev["kind"] == "response":
                c = cost_of(price_for(prices, ev["model"]), claude_usage(ev["usage"])) or 0.0
                all_costs[id(ev)] = c
                session_cost += c
        for ev, step in counted:
            step = step or step_by_time(ev["time"], apply_at, archive_at)
            tokens = claude_usage(ev["usage"])
            if not any(tokens.values()):
                continue
            add(step, "Claude Code", ev["model"], tokens, cost_of(price_for(prices, ev["model"]), tokens))
            ours_cost += all_costs.get(id(ev), 0.0)
        unpriced = any(price_for(prices, ev["model"]) is None and any(claude_usage(ev["usage"]).values())
                       for ev in events if ev["kind"] == "response")
        # Subagents, including ones a subagent started: each takes its step from the call that started it.
        subs = []
        for sub in sorted(glob.glob(os.path.join(os.path.splitext(path)[0], "subagents", "*.jsonl"))):
            meta_path = os.path.splitext(sub)[0] + ".meta.json"
            meta = {}
            if os.path.exists(meta_path):
                with open(meta_path) as f:
                    meta = json.load(f)
            subs.append((meta, claude_responses(sub)))
        resolved = {}  # toolUseId -> (step, counts)
        for tool_use, (kind, step, counts, time) in spawns.items():
            resolved[tool_use] = (step or step_by_time(time, apply_at, archive_at), counts)
        todo = list(subs)
        while todo:
            ready = [s for s in todo if s[0].get("toolUseId") in resolved]
            if not ready:
                break
            for meta, sub_events in ready:
                todo.remove((meta, sub_events))
                parent_step, counts = resolved[meta.get("toolUseId")]
                step = "Verify" if meta.get("agentType") == "verifier" else parent_step
                for e in sub_events:
                    if e["kind"] == "spawn":
                        resolved[e["id"]] = (step, counts)
                    if e["kind"] != "response":
                        continue
                    tokens = claude_usage(e["usage"])
                    rates = price_for(prices, e["model"])
                    c = cost_of(rates, tokens) or 0.0
                    session_cost += c
                    unpriced = unpriced or (rates is None and any(tokens.values()))
                    if counts and any(tokens.values()):
                        add(step, "Claude Code", e["model"], tokens, cost_of(rates, tokens))
                        ours_cost += c
        for meta, sub_events in todo:  # started by nothing we can find: still part of the session's cost
            for e in sub_events:
                if e["kind"] == "response":
                    session_cost += cost_of(price_for(prices, e["model"]), claude_usage(e["usage"])) or 0.0
        # Claude Code's own session total also covers calls not in the transcript. Skip it when some of the
        # session's work has no price: the difference would then include that work, not just overhead.
        states = [e["total"] for e in events if e["kind"] == "cost-state"]
        if states and not unpriced and session_cost > 0 and ours_cost > 0 and states[-1] > session_cost:
            other += (states[-1] - session_cost) * ours_cost / session_cost
    return other


# ---------- Codex ----------

def codex_events(path, repo):
    """A Codex session as the same events as a Claude session: markers, prompts and responses (token
    differences between token_count lines, with their tokens worked out). None if not in the repo."""
    entries = list(read_jsonl(path))
    if not entries or entries[0].get("type") != "session_meta":
        return None
    meta = entries[0].get("payload") or {}
    if not in_repo(meta.get("cwd", ""), repo):
        return None
    branch = (meta.get("git") or {}).get("branch")
    # A forked subagent first replays its parent's history: skip it, but keep its running token total.
    history_end = meta.get("subagent_history_start_ordinal") or 0
    events, model, last = [], None, zero()
    for entry in entries:
        payload = entry.get("payload") or {}
        time = entry.get("timestamp")
        replayed = (entry.get("ordinal") or 0) < history_end
        if replayed and entry.get("type") != "turn_context" and not (payload.get("type") == "token_count" and payload.get("info")):
            continue
        if entry.get("type") == "turn_context":
            model = payload.get("model") or model
        elif entry.get("type") == "response_item" and payload.get("type") == "message" and payload.get("role") == "user":
            text = " ".join(c.get("text", "") for c in payload.get("content") or [] if isinstance(c, dict))
            # Codex also logs the context it injects (AGENTS.md, environment, skill bodies) as user messages.
            # Their examples of $openspec-... are not invocations, so skip them before looking for markers.
            if text.lstrip().startswith(("<", "# AGENTS.md")):
                continue
            markers = CODEX_MARKER.findall(text)
            for name, args in markers:
                if marker_step(name):
                    events.append({"kind": "marker", "step": marker_step(name), "args": args, "time": time})
            if not markers:
                events.append({"kind": "prompt", "time": time})
        elif payload.get("type") == "token_count" and payload.get("info"):
            total = payload["info"].get("total_token_usage") or {}
            now = {"input": total.get("input_tokens", 0), "cache_read": total.get("cached_input_tokens", 0),
                   "cache_write_5m": total.get("cache_write_input_tokens", 0) or 0, "cache_write_1h": 0,
                   "output": total.get("output_tokens", 0)}
            delta = {k: max(0, now[k] - last[k]) for k in now}
            last = now
            # Codex counts cached tokens (and cache writes, in builds that report them) inside input_tokens.
            delta["input"] = max(0, delta["input"] - delta["cache_read"] - delta["cache_write_5m"])
            if any(delta.values()) and not replayed:
                events.append({"kind": "response", "model": model, "tokens": delta, "branch": branch, "time": time})
    return events


def codex_sessions(codex_dir, repo):
    sessions = []
    if not codex_dir:
        return sessions
    for path in sorted(glob.glob(os.path.join(codex_dir, "**", "*.jsonl"), recursive=True)):
        events = codex_events(path, repo)
        if events is not None:
            meta = (next(read_jsonl(path), {}) or {}).get("payload") or {}
            sessions.append((path, events, meta))
    return sessions


def state_at(events, time, change):
    """The step and change context of a session at a moment (for a subagent it started then)."""
    step = context = None
    for ev in events:
        if time and ev.get("time") and ev["time"] > time:
            break
        if ev["kind"] == "marker":
            step = ev["step"]
            context = marker_target(ev["args"], change) or context
        elif ev["kind"] == "prompt":
            step = {"Archive": "PR and review", "Policy review": "Build"}.get(step, step)
    return step, context


def codex_rows(sessions, change, branch, prices, add, apply_at, archive_at):
    threads = {meta.get("id"): (events, meta) for _, events, meta in sessions if meta.get("id")}

    def inherited(thread_id, depth=0):
        """(step, context) a subagent session takes from the session that started it, or (None, None).
        A verifier's step is Verify (and so is everything it starts); its change comes from its parent."""
        events, meta = threads[thread_id]
        own = "Verify" if meta.get("agent_role") == "verifier" else None
        parent = meta.get("parent_thread_id")
        if parent not in threads or depth > 10:
            return own, None
        step, context = state_at(threads[parent][0], meta.get("timestamp"), change)
        up_step, up_context = inherited(parent, depth + 1)
        if up_step == "Verify":
            step = "Verify"
        return own or step or up_step, context or up_context

    for _, events, meta in sessions:
        if meta.get("id") in threads:
            step_from_parent, context_from_parent = inherited(meta["id"])
        else:
            step_from_parent = "Verify" if meta.get("agent_role") == "verifier" else None
            context_from_parent = None
        if context_from_parent == "ours":
            # Started by our change's work: all of it counts, unless it ran on another feature branch.
            counted = [(ev, None) for ev in events if ev["kind"] == "response"
                       and (ev["branch"] in TRUNK or ev["branch"] == branch)]
        elif context_from_parent == "other":
            counted = []
        else:
            counted, _ = walk_session(events, change, branch)
        for ev, step in counted:
            step = step_from_parent or step or step_by_time(ev["time"], apply_at, archive_at)
            add(step, "Codex", ev["model"], ev["tokens"], cost_of(price_for(prices, ev["model"]), ev["tokens"]))


# ---------- report ----------

def change_dir(change):
    active = REPO / "openspec" / "changes" / change
    if active.is_dir():
        return active
    archived = sorted((REPO / "openspec" / "changes" / "archive").glob("*-" + change))
    return archived[-1] if archived else None


def current_branch():
    out = subprocess.run(["git", "-C", str(REPO), "branch", "--show-current"], capture_output=True, text=True)
    return out.stdout.strip()


def build_report(change, branch, claude_dir, codex_dir, prices, repo=REPO, today=None, known=None, ci_usage=()):
    global KNOWN_CHANGES
    KNOWN_CHANGES = set(known) if known is not None else known_changes(repo)
    rows = defaultdict(zero)
    costs = defaultdict(float)
    unpriced = set()

    def add(step, agent, model, tokens, cost):
        """Each response is priced on its own (Haiku's rate depends on the prompt's size)."""
        key = (step, agent, model or "unknown")
        row = rows[key]
        for k in row:
            row[k] += tokens.get(k, 0)
        if cost is None:
            unpriced.add(key[2])
        else:
            costs[key] += cost

    claude = claude_sessions(claude_dir, repo)
    codex = codex_sessions(codex_dir, repo)
    apply_at, archive_at = marker_times([e for _, e in claude] + [e for _, e, _ in codex], change)
    other = claude_rows(claude, change, branch, prices, add, apply_at, archive_at)
    codex_rows(codex, change, branch, prices, add, apply_at, archive_at)
    for line in ci_usage:
        add(line.get("step", "Other"), CI_AGENT, line.get("model"), {k: line.get(k, 0) or 0 for k in zero()},
            line.get("cost"))

    order = {s: i for i, s in enumerate(STEP_ORDER)}
    lines = [f"# Cost: {change}", "",
             f"Estimated from agent session logs (local, and CI runs recorded in `ci-usage.jsonl`) on {today or datetime.date.today().isoformat()}, "
             f"prices from `scripts/model-prices.json` ({prices.get('updated', 'undated')}). "
             "API-equivalent: what the same tokens would cost on the API, not a subscription bill.", "",
             "| Step | Agent | Model | Input | Cache write | Cache read | Output | Cost |",
             "|---|---|---|---:|---:|---:|---:|---:|"]
    total_cost = 0.0
    sums = zero()
    for (step, agent, model) in sorted(rows, key=lambda k: (order.get(k[0], 99), k[1], k[2])):
        t = rows[(step, agent, model)]
        c = None if model in unpriced else costs[(step, agent, model)]
        total_cost += c or 0.0
        for k in sums:
            sums[k] += t[k]
        write = t["cache_write_5m"] + t["cache_write_1h"]
        lines.append(f"| {step} | {agent} | {model} | {t['input']:,} | {write:,} | {t['cache_read']:,} | "
                     f"{t['output']:,} | {'no price' if c is None else f'${c:,.2f}'} |")
    if other > 0.005:
        total_cost += other
        lines.append(f"| Other | Claude Code | session overhead (auto-mode checks, summaries) | | | | | ${other:,.2f} |")
    total_tokens = sum(sums.values())
    write = sums["cache_write_5m"] + sums["cache_write_1h"]
    lines.append(f"| **Total** | | | **{sums['input']:,}** | **{write:,}** | **{sums['cache_read']:,}** | "
                 f"**{sums['output']:,}** | **${total_cost:,.2f}** |")
    lines += ["", f"Total tokens: {total_tokens:,}. Total estimated cost: ${total_cost:,.2f}."]
    notes = ["Not measured: the Codex review on GitHub, GitHub Actions minutes, and work done from a session "
             "started in another folder."]
    if ci_usage:
        notes.append("Claude Code (CI) rows are recorded by each CI run just before its last push, so the run's "
                     "final few turns (commit, push, replies) aren't counted.")
    if unpriced:
        notes.insert(0, "The total leaves out models with no price in `scripts/model-prices.json`: "
                     + ", ".join(sorted(unpriced)) + ".")
    if not rows:
        notes.insert(0, f"No agent work was found for this change on branch `{branch}`.")
    lines += [""] + notes
    return "\n".join(lines) + "\n", total_cost, total_tokens


# ---------- CI runs ----------

def record_ci(claude_dir, repo, prices, step, run_id):
    """Per (step, model) usage of every Claude Code session on this runner for this checkout: one CI run.
    Steps start at `step` and follow the OpenSpec step markers; verifier subagents count as Verify, other
    subagents take the step of the call that started them."""
    sums, costs, unpriced = defaultdict(zero), defaultdict(float), set()

    def add(at, model, tokens):
        if not any(tokens.values()):
            return
        key = (at, model or "unknown")
        for k in tokens:
            sums[key][k] += tokens[k]
        c = cost_of(price_for(prices, model), tokens)
        if c is None:
            unpriced.add(key)
        else:
            costs[key] += c

    for path, events in claude_sessions(claude_dir, repo):
        now, spawned = step, {}
        for ev in events:
            if ev["kind"] == "marker":
                now = ev["step"]
            elif ev["kind"] == "spawn":
                spawned[ev["id"]] = now
            elif ev["kind"] == "response":
                add(now, ev["model"], claude_usage(ev["usage"]))
        todo = []
        for sub in sorted(glob.glob(os.path.join(os.path.splitext(path)[0], "subagents", "*.jsonl"))):
            meta_path = os.path.splitext(sub)[0] + ".meta.json"
            meta = {}
            if os.path.exists(meta_path):
                with open(meta_path) as f:
                    meta = json.load(f)
            todo.append((meta, claude_responses(sub)))
        while todo:
            ready = [t for t in todo if t[0].get("toolUseId") in spawned] or todo[:1]
            for meta, sub_events in ready:
                todo.remove((meta, sub_events))
                at = "Verify" if meta.get("agentType") == "verifier" else spawned.get(meta.get("toolUseId"), step)
                for e in sub_events:
                    if e["kind"] == "spawn":
                        spawned[e["id"]] = at
                    elif e["kind"] == "response":
                        add(at, e["model"], claude_usage(e["usage"]))
    order = {s: i for i, s in enumerate(STEP_ORDER)}
    return [{"step": at, "agent": CI_AGENT, "model": model, **sums[(at, model)],
             "cost": None if (at, model) in unpriced else round(costs[(at, model)], 6), "run": str(run_id)}
            for at, model in sorted(sums, key=lambda k: (order.get(k[0], 99), k[1]))]


def read_ci_usage(folder):
    path = Path(folder) / CI_USAGE if folder else None
    return list(read_jsonl(path)) if path and path.exists() else []


def write_ci_usage(folder, lines, run_id):
    """Replace this run's lines (a rerun of the same step) and keep every other run's."""
    kept = [l for l in read_ci_usage(folder) if str(l.get("run")) != str(run_id)]
    with open(Path(folder) / CI_USAGE, "w") as f:
        for line in kept + lines:
            f.write(json.dumps(line) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Token and cost report for an OpenSpec change, from agent session logs.")
    parser.add_argument("change", help="OpenSpec change name (active or archived)")
    parser.add_argument("--branch", help="the change's branch (default: the current branch)")
    parser.add_argument("--print", dest="print_only", action="store_true", help="print the table without writing cost.md")
    parser.add_argument("--record-ci", action="store_true",
                        help="in a CI run: record this run's usage in the change's ci-usage.jsonl instead of reporting")
    parser.add_argument("--step", default="Build", choices=STEP_ORDER, help="with --record-ci: the run's starting step")
    parser.add_argument("--run", default=os.environ.get("GITHUB_RUN_ID", "local"), help="with --record-ci: the run id")
    # In CI the runner's own logs are this run, which --record-ci records; the report reads them from
    # ci-usage.jsonl, so it doesn't read them again as local logs.
    in_ci = os.environ.get("GITHUB_ACTIONS") == "true"
    parser.add_argument("--claude-dir", default="" if in_ci else os.path.expanduser("~/.claude/projects"))
    parser.add_argument("--codex-dir", default="" if in_ci else os.path.expanduser("~/.codex/sessions"))
    args = parser.parse_args(argv)

    if args.record_ci:
        folder = change_dir(args.change)
        if folder is None:
            print(f"No change folder for '{args.change}' in openspec/changes/ or its archive.", file=sys.stderr)
            return 1
        logs = args.claude_dir or os.path.expanduser("~/.claude/projects")
        lines = record_ci(logs, REPO, load_prices(), args.step, args.run)
        if not lines:
            print(f"No Claude Code logs for this checkout in {logs}; nothing recorded.", file=sys.stderr)
            return 0
        write_ci_usage(folder, lines, args.run)
        print(f"Recorded {len(lines)} line(s) for run {args.run} in {folder.relative_to(REPO)}/{CI_USAGE}", file=sys.stderr)
        return 0

    folder = change_dir(args.change)
    if folder is None and not args.print_only:
        print(f"No change folder for '{args.change}' in openspec/changes/ or its archive.", file=sys.stderr)
        return 1
    branch = args.branch or current_branch()
    if branch in TRUNK:
        print(f"On '{branch or 'no branch'}': run this on the change's branch, or pass --branch <the change's branch>.",
              file=sys.stderr)
        return 2
    report, _, _ = build_report(args.change, branch, args.claude_dir, args.codex_dir, load_prices(),
                                ci_usage=read_ci_usage(folder))
    if not args.print_only:
        (folder / "cost.md").write_text(report)
        print(f"Wrote {folder.relative_to(REPO)}/cost.md\n", file=sys.stderr)
    print(report, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
