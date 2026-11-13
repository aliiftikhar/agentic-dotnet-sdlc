"""Harness evals runner. Use it through scripts/eval-run.sh (see that file for usage).

Gives real tasks cut from this repository to Claude Code or Codex in a temporary, history-free copy
with no git remote, runs the normal flow (propose, an automatic approval, apply, verify, archive)
and scores the result. Standard library only. See docs/evals.md in agentic-dotnet-sdlc.
"""

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# --- Configure for your repository -------------------------------------------------
API_PROJECT = "<ApiProject>"              # folder of the API project (use cases, repositories, Program.cs)
TEST_PROJECT = "<UnitTestProject>"        # folder of the unit test project the answer keys run in
USECASES_DIR = f"{API_PROJECT}/UseCases"  # one folder per use case: <Name>/<Name>Handler.cs, ...
TEST_USECASES_DIR = f"{TEST_PROJECT}/UseCases"
REPOSITORY_FILE = f"{API_PROJECT}/<RepositoriesFolder>/{{name}}Repository.cs"   # or None if use cases have none
PROGRAM_FILE = f"{API_PROJECT}/Program.cs"  # holds the repository registration and the endpoint
# Defaults keep runs comparable and within plan limits; override with --model and --effort.
# Use the current model names your CLIs list (`claude --help`, `codex` model picker).
DEFAULT_MODEL = {"claude": "sonnet", "codex": "<codex-model>"}
DEFAULT_EFFORT = "medium"
TIMEOUT_MINUTES = 45
# -----------------------------------------------------------------------------------

REPO = Path(__file__).resolve().parent.parent
TASKS_DIR = REPO / "evals" / "tasks"
SETS_DIR = REPO / "evals" / "sets"  # named task sets, e.g. smoke.txt: one id per line
RESULTS_DIR = REPO / "evals" / "results"
LOGS_DIR = RESULTS_DIR / "logs"  # agent transcripts and check output; git-ignored
HIDDEN_DIR = f"{TEST_PROJECT}/EvalHidden"

APPROVAL = ("Approved. Apply it and finish the change up to the archive, committing on your branch. "
            "There is no remote: don't push or open a pull request.")

# Commands the normal flow needs. Edits are accepted; the repo's deny rules still apply.
CLAUDE_ALLOWED = [
    "Bash(dotnet *)", "Bash(git *)", "Bash(scripts/*)", "Bash(./scripts/*)", "Bash(bash scripts/*)",
    "Bash(openspec *)", "Bash(npx *)", "Bash(ls *)", "Bash(cat *)", "Bash(grep *)", "Bash(rg *)",
    "Bash(find *)", "Bash(head *)", "Bash(tail *)", "Bash(wc *)", "Bash(sed -n *)", "Bash(mkdir *)",
    "Bash(diff *)", "Bash(sort *)", "Bash(jq *)",
]


# ---------- tasks ----------

def parse_task(path):
    text = path.read_text()
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        raise ValueError(f"{path.name}: no front matter")
    meta = {}
    for line in m.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            value = [v.strip() for v in value[1:-1].split(",") if v.strip()]
        meta[key.strip()] = value
    for key in ("id", "kind", "setup", "hidden_tests"):
        if key not in meta:
            raise ValueError(f"{path.name}: missing {key}")
    if meta["kind"] not in ("remove", "replay", "bugfix"):
        raise ValueError(f"{path.name}: unknown kind {meta['kind']}")
    if meta["id"] != path.stem:
        raise ValueError(f"{path.name}: id {meta['id']} doesn't match the file name")
    meta["request"] = m.group(2).strip()
    meta["path"] = path
    return meta


def load_tasks(ids):
    tasks = [parse_task(p) for p in sorted(TASKS_DIR.glob("*.md"))]
    if ids:
        wanted = []
        for i in (i.strip() for i in ids.split(",")):
            set_file = SETS_DIR / f"{i}.txt"
            if i and set_file.is_file():
                lines = (l.strip() for l in set_file.read_text().splitlines())
                wanted += [l for l in lines if l and not l.startswith("#")]
            elif i:
                wanted.append(i)
        by_id = {t["id"]: t for t in tasks}
        missing = [i for i in wanted if i not in by_id]
        if missing:
            sys.exit(f"Unknown task ids: {', '.join(missing)}")
        tasks = [by_id[i] for i in wanted]
    return tasks


# ---------- shell helpers ----------

def run(cmd, cwd, timeout=None, env=None):
    """Run a command, return (exit code, combined output). A timeout returns code 124."""
    try:
        p = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                           timeout=timeout, env=env, shell=isinstance(cmd, str))
        return p.returncode, p.stdout
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        return 124, out + "\n[timed out]"


def git(cwd, *args):
    code, out = run(["git", *args], cwd)
    if code != 0:
        raise RuntimeError(f"git {' '.join(args)} failed:\n{out}")
    return out.strip()


def dotnet_bin():
    return shutil.which("dotnet") or "/usr/local/share/dotnet/dotnet"


# ---------- snapshot and setup ----------

def make_snapshot(ref):
    """History-free copy of <ref>, committed as main. Returns (folder, harness sha)."""
    sha = git(REPO, "rev-parse", ref)
    folder = Path(tempfile.mkdtemp(prefix="harness-eval-"))
    archive = subprocess.run(["git", "archive", sha], cwd=REPO, stdout=subprocess.PIPE, check=True).stdout
    subprocess.run(["tar", "-x", "-C", str(folder)], input=archive, check=True)
    init_repo(folder, "Snapshot")
    return folder, sha


def init_repo(folder, message):
    """A new repository holding the folder as one commit on main."""
    git(folder, "init", "-q", "-b", "main")
    for key in ("user.name", "user.email"):
        value = run(["git", "config", key], REPO)[1].strip()
        if value:
            git(folder, "config", key, value)
    git(folder, "add", "-A")
    git(folder, "commit", "-q", "-m", message)


def remove_usecase(folder, name):
    """Delete a use case, its tests, its repository, and its using, registration and endpoint in Program.cs.
    Each piece must be found exactly once, so --check fails loudly when the code moves on."""
    shutil.rmtree(folder / USECASES_DIR / name)
    shutil.rmtree(folder / TEST_USECASES_DIR / name)
    if REPOSITORY_FILE:
        (folder / REPOSITORY_FILE.format(name=name)).unlink()

    program = folder / PROGRAM_FILE
    lines = program.read_text().split("\n")

    def drop(pattern, what):
        hits = [i for i, l in enumerate(lines) if re.search(pattern, l)]
        if len(hits) != 1:
            raise RuntimeError(f"remove-usecase {name}: expected one {what} line in Program.cs, found {len(hits)}")
        return hits[0]

    using = drop(rf"^using [\w.]+\.UseCases\.{name};", "using")
    di = drop(rf"Add\w+<I{name}Repository, {name}Repository>", "registration") if REPOSITORY_FILE else None
    ref = drop(rf"\b{name}Request\b", "endpoint")
    start = next(i for i in range(ref, -1, -1) if lines[i].startswith("app.Map"))
    end = next(i for i in range(ref, len(lines)) if lines[i].startswith("})"))
    if end + 1 < len(lines) and not lines[end + 1].strip():
        end += 1
    remove = {using, *range(start, end + 1)} | ({di} if di is not None else set())
    program.write_text("\n".join(l for i, l in enumerate(lines) if i not in remove))


def apply_setup(folder, task):
    action, _, arg = task["setup"].partition(" ")
    if action == "remove-usecase":
        remove_usecase(folder, arg.strip())
    elif action == "patch":
        patch = task["path"].with_suffix(".patch")
        code, out = run(["git", "apply", str(patch)], folder)
        if code != 0:
            raise RuntimeError(f"{patch.name} doesn't apply:\n{out}")
    else:
        raise RuntimeError(f"unknown setup {task['setup']}")


def prepare_start(folder, task):
    """Read the answer key, apply the task, remove evals/, commit the agent's starting point."""
    hidden = {p: (folder / p).read_text() for p in task["hidden_tests"]}
    apply_setup(folder, task)
    shutil.rmtree(folder / "evals", ignore_errors=True)
    # A fresh repository, not a squash: the old commit would stay in the reflog and object store,
    # and the agent could recover the answer key from it.
    shutil.rmtree(folder / ".git")
    init_repo(folder, "Starting point")
    git(folder, "config", "core.hooksPath", ".githooks")
    return hidden


def place_hidden(folder, hidden):
    """Put the answer key in its own folder and namespace, so it can't clash with the agent's tests."""
    target = folder / HIDDEN_DIR
    target.mkdir(parents=True, exist_ok=True)
    for n, (path, text) in enumerate(hidden.items()):
        text, count = re.subn(r"^namespace ([\w.]+);", r"namespace \1.EvalHidden;", text, count=1, flags=re.M)
        if count != 1:
            raise RuntimeError(f"{path}: no file-scoped namespace to rename")
        (target / f"{n}_{Path(path).name}").write_text(text)


# ---------- checks ----------

def test_counts(output):
    m = re.search(r"Failed:\s*(\d+),\s*Passed:\s*(\d+)", output)
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def run_tests(folder, filt=None):
    """Returns ('pass' | 'fail' | 'compile' | 'none', output)."""
    code, out = run([dotnet_bin(), "build", TEST_PROJECT, "-v", "q", "-nologo"], folder, timeout=900)
    if code != 0:
        return "compile", out
    cmd = [dotnet_bin(), "test", TEST_PROJECT, "--no-build", "-nologo"]
    if filt:
        cmd += ["--filter", filt]
    code, out = run(cmd, folder, timeout=900)
    failed, passed = test_counts(out)
    if passed is None and failed is None:
        return ("none" if "No test matches" in out else "fail"), out
    if code == 0 and not failed and passed:
        return "pass", out
    return "fail", out


def script_check(folder, script):
    code, out = run(["bash", f"scripts/{script}"], folder, timeout=3600)
    return ("pass" if code == 0 else "fail"), out


# ---------- agents ----------

def cli_version(agent):
    return run([agent, "--version"], REPO)[1].strip()


def run_claude(folder, prompt, model, effort, session, timeout):
    cmd = ["claude", "-p", prompt, "--output-format", "json", "--permission-mode", "acceptEdits",
           "--allowedTools", *CLAUDE_ALLOWED]
    if model:
        cmd += ["--model", model]
    if effort:
        cmd += ["--effort", effort]
    if session:
        cmd += ["--resume", session]
    code, out = run(cmd, folder, timeout=timeout)
    info = {"raw": out, "code": code}
    try:
        data = json.loads(out[out.index("{"):])
    except ValueError:
        return info
    usage = data.get("usage") or {}
    info.update(session=data.get("session_id"), message=data.get("result") or "",
                cost=data.get("total_cost_usd"),
                input_tokens=sum(usage.get(k) or 0 for k in
                                 ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")),
                output_tokens=usage.get("output_tokens"),
                models=list((data.get("modelUsage") or {}).keys()))
    return info


def codex_config(folder):
    home = Path.home()
    # The workspace-write sandbox keeps .git read-only by default; the agent must branch and commit.
    roots = [str(Path(folder).resolve() / ".git"), str(home / ".nuget"), str(home / ".dotnet"), str(home / ".local" / "share" / "NuGet"),
             tempfile.gettempdir()]
    return ["-c", 'sandbox_mode="workspace-write"',
            "-c", "sandbox_workspace_write.network_access=true",
            "-c", "sandbox_workspace_write.writable_roots=" + json.dumps(roots),
            "-c", 'approval_policy="never"']


def run_codex(folder, prompt, model, effort, session, timeout):
    if session:
        cmd = ["codex", "exec", "resume", session, prompt, "--json", *codex_config(folder)]
    else:
        cmd = ["codex", "exec", prompt, "--json", "-C", str(folder), *codex_config(folder)]
    if model:
        cmd += ["-m", model]
    if effort:
        cmd += ["-c", f'model_reasoning_effort="{effort}"']
    code, out = run(cmd, folder, timeout=timeout)
    info = {"raw": out, "code": code, "session": session, "message": "", "input_tokens": 0, "output_tokens": 0}
    for line in out.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        kind = event.get("type")
        if kind == "thread.started":
            info["session"] = event.get("thread_id")
        elif kind == "turn.completed":
            usage = event.get("usage") or {}
            info["input_tokens"] += usage.get("input_tokens") or 0
            info["output_tokens"] += usage.get("output_tokens") or 0
        elif kind == "item.completed" and (event.get("item") or {}).get("type") == "agent_message":
            info["message"] = event["item"].get("text") or ""
    return info


def changed_paths(folder):
    committed = run(["git", "diff", "--name-only", "main...HEAD"], folder)[1].split()
    pending = [l[3:] for l in run(["git", "status", "--porcelain"], folder)[1].splitlines()]
    return sorted(set(committed + pending))


def verifier_fails(folder):
    log = run(["git", "log", "-p", "main..HEAD", "--", "*verification.md"], folder)[1]
    return len(re.findall(r"^\+Verdict:\s*FAIL", log, re.M))


# ---------- commands ----------

def check_task(task, ref):
    folder, _ = make_snapshot(ref)
    problems = []
    try:
        hidden = {p: (folder / p).read_text() for p in task["hidden_tests"]}
        # 1. The answer key passes on today's code.
        work = Path(tempfile.mkdtemp(prefix="harness-evalcheck-"))
        shutil.copytree(folder, work, dirs_exist_ok=True)
        place_hidden(work, hidden)
        status, out = run_tests(work, "FullyQualifiedName~EvalHidden")
        shutil.rmtree(work, ignore_errors=True)
        if status != "pass":
            problems.append(f"answer key doesn't pass on {ref} ({status})")
        # 2. The starting point builds and its tests pass.
        prepare_start(folder, task)
        reachable = len(git(folder, "rev-list", "--all", "--objects").splitlines())
        stored = len(git(folder, "cat-file", "--batch-all-objects", "--batch-check").splitlines())
        snapshot_ok = (len(git(folder, "rev-list", "--all").split()) == 1 and reachable == stored
                       and len(git(folder, "reflog").splitlines()) == 1 and not (folder / "evals").exists())
        if not snapshot_ok:
            problems.append("snapshot has history, unreachable objects or evals/")
        status, out = run_tests(folder)
        if status != "pass":
            problems.append(f"starting point tests: {status}")
        # 3. The answer key fails on the starting point.
        place_hidden(folder, hidden)
        status, out = run_tests(folder, "FullyQualifiedName~EvalHidden")
        failed, _ = test_counts(out)
        # Remove and replay tasks may change the contract, so the answer key may not compile;
        # a bug fix keeps the contract, so its answer key must build and fail.
        if task["kind"] != "bugfix":
            if status not in ("compile", "fail"):
                problems.append(f"answer key doesn't fail after setup ({status})")
        elif status != "fail" or not failed:
            problems.append(f"answer key should build and fail after setup, got {status}")
        detail = f"{failed} hidden test(s) fail" if status == "fail" else status
    except Exception as e:  # noqa: BLE001 - report and carry on with the next task
        problems.append(str(e).strip().splitlines()[0])
        detail = "error"
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    print(f"{'ok  ' if not problems else 'FAIL'} {task['id']}: " + ("; ".join(problems) or f"after setup: {detail}"),
          flush=True)
    return not problems


def run_task(task, args, run_id, sha, version, log_dir):
    folder, _ = make_snapshot(args.ref)
    started = time.time()
    record = {"run_id": run_id, "task": task["id"], "kind": task["kind"], "agent": args.agent,
              "model": args.model, "effort": args.effort, "cli_version": version, "harness_sha": sha}
    log = []
    try:
        hidden = prepare_start(folder, task)
        run_tests(folder)  # restore and build once, so the agent starts warm
        agent = run_claude if args.agent == "claude" else run_codex
        deadline = started + TIMEOUT_MINUTES * 60

        first = agent(folder, task["request"], args.model, args.effort, None, max(60, deadline - time.time()))
        log.append(first["raw"])
        record["stopped_after_propose"] = all(p.startswith("openspec/") for p in changed_paths(folder))
        turns = [first]
        if first.get("session") and first["code"] != 124:
            second = agent(folder, APPROVAL, args.model, args.effort, first["session"], max(60, deadline - time.time()))
            log.append(second["raw"])
            turns.append(second)
        timed_out = any(t["code"] == 124 for t in turns)
        # A plan's usage limit ends the run early; mark it so it isn't read as the harness failing.
        limit_hit = any("usage limit" in (t.get("raw") or "").lower() for t in turns)

        record.update(
            minutes=round((time.time() - started) / 60, 1),
            timed_out=timed_out,
            limit_hit=limit_hit,
            input_tokens=sum(t.get("input_tokens") or 0 for t in turns),
            output_tokens=sum(t.get("output_tokens") or 0 for t in turns),
            cost_usd=round(sum(t.get("cost") or 0 for t in turns), 4) if args.agent == "claude" else None,
            models=sorted({m for t in turns for m in t.get("models", [])}) or None,
            branch=git(folder, "branch", "--show-current"),
            uncommitted=bool(run(["git", "status", "--porcelain"], folder)[1].strip()),
            verifier_fails=verifier_fails(folder),
            last_message=(turns[-1].get("message") or "")[:500],
        )

        checks = {}
        # The work must be committed on a branch other than main, as AGENTS.md asks.
        ahead = run(["git", "rev-list", "--count", "main..HEAD"], folder)[1].strip()
        checks["committed"] = ("pass" if record["branch"] not in ("", "main") and not record["uncommitted"]
                               and ahead not in ("", "0") else "fail")
        checks["unit"], out = run_tests(folder); log.append(out)
        checks["spec"], out = script_check(folder, "spec-check.sh"); log.append(out)
        checks["mutation"], out = script_check(folder, "mutation-check.sh"); log.append(out)
        checks["format"], out = script_check(folder, "format-check.sh"); log.append(out)
        place_hidden(folder, hidden)
        checks["hidden"], out = run_tests(folder, "FullyQualifiedName~EvalHidden"); log.append(out)
        record["checks"] = checks
        record["passed"] = not timed_out and all(v == "pass" for v in checks.values())
    except Exception as e:  # noqa: BLE001 - one broken task shouldn't stop the run
        record.update(passed=False, error=str(e)[:500], minutes=round((time.time() - started) / 60, 1))
    finally:
        (log_dir / f"{task['id']}.log").write_text("\n\n=====\n\n".join(log))
        if args.keep:
            print(f"  kept {folder}")
        else:
            shutil.rmtree(folder, ignore_errors=True)
    return record


def summarise(agent, run_id, records):
    passed = sum(r["passed"] for r in records)
    minutes = sum(r.get("minutes") or 0 for r in records)
    cost = sum(r.get("cost_usd") or 0 for r in records)
    print(f"\nRun {run_id} ({agent}): {passed}/{len(records)} passed, {minutes:.0f} min"
          + (f", ${cost:.2f} reported" if cost else ""))
    for r in records:
        checks = " ".join(f"{k}={v}" for k, v in (r.get("checks") or {}).items()) or r.get("error", "")
        note = "  (usage limit hit: rerun this task)" if r.get("limit_hit") else ""
        print(f"  {'PASS' if r['passed'] else 'fail'} {r['task']}  {checks}{note}")

    model, effort = records[0].get("model"), records[0].get("effort")
    earlier = []
    for f in RESULTS_DIR.glob("*.jsonl"):
        for line in f.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                # Only runs at the same model and effort compare fairly; older lines with no effort never match.
                if (r["agent"] == agent and r["run_id"] < run_id and r.get("model") == model
                        and r.get("effort") is not None and r.get("effort") == effort):
                    earlier.append(r)
    if not earlier:
        print(f"No earlier run for {agent} at {model}, effort {effort}, to compare with.")
        return
    previous_id = max(r["run_id"] for r in earlier)
    previous = {r["task"]: r for r in earlier if r["run_id"] == previous_id}
    common = [r for r in records if r["task"] in previous]
    print(f"Compared with {previous_id}: {sum(previous[r['task']]['passed'] for r in common)}/{len(common)} "
          f"of the same tasks passed then, {sum(r['passed'] for r in common)}/{len(common)} now.")
    then_min = sum(previous[r["task"]].get("minutes") or 0 for r in common)
    now_min = sum(r.get("minutes") or 0 for r in common)
    then_cost = sum(previous[r["task"]].get("cost_usd") or 0 for r in common)
    now_cost = sum(r.get("cost_usd") or 0 for r in common)
    print(f"  Same tasks: {then_min:.0f} min then, {now_min:.0f} min now"
          + (f"; ${then_cost:.2f} then, ${now_cost:.2f} now" if then_cost or now_cost else ""))
    for r in common:
        if r["passed"] != previous[r["task"]]["passed"]:
            print(f"  {r['task']}: {'fail -> PASS' if r['passed'] else 'PASS -> fail'}")


def main():
    parser = argparse.ArgumentParser(prog="scripts/eval-run.sh")
    parser.add_argument("--check", action="store_true", help="check the tasks are valid, without an agent")
    parser.add_argument("--agent", choices=["claude", "codex"])
    parser.add_argument("--model", help=f"default: {DEFAULT_MODEL['claude']} for claude, {DEFAULT_MODEL['codex']} for codex")
    parser.add_argument("--effort", default=DEFAULT_EFFORT,
                        help=f"reasoning effort passed to the agent (default: {DEFAULT_EFFORT})")
    parser.add_argument("--tasks", help="comma-separated task ids or set names from evals/sets/ (e.g. smoke); default: all")
    parser.add_argument("--ref", default="main", help="the harness version to snapshot (default: main)")
    parser.add_argument("--keep", action="store_true", help="keep the snapshot folders for a look afterwards")
    args = parser.parse_args()
    tasks = load_tasks(args.tasks)

    if args.check:
        ok = [check_task(t, args.ref) for t in tasks]
        print(f"\n{sum(ok)}/{len(ok)} tasks valid.")
        sys.exit(0 if all(ok) else 1)
    if not args.agent:
        parser.error("--agent or --check is required")
    args.model = args.model or DEFAULT_MODEL[args.agent]

    run_id = dt.datetime.now().strftime("%Y-%m-%dT%H%M")
    sha = git(REPO, "rev-parse", args.ref)
    version = cli_version(args.agent)
    results = RESULTS_DIR / f"{run_id[:10]}-{args.agent}-{args.model}-{args.effort}.jsonl"
    log_dir = LOGS_DIR / f"{run_id}-{args.agent}"
    log_dir.mkdir(parents=True, exist_ok=True)
    print(f"Running {len(tasks)} task(s) with {version} ({args.model}, effort {args.effort}) on {args.ref} ({sha[:7]}); logs in {log_dir}")

    records = []
    for task in tasks:
        print(f"- {task['id']} ...", flush=True)
        record = run_task(task, args, run_id, sha, version, log_dir)
        records.append(record)
        with results.open("a") as f:
            f.write(json.dumps(record) + "\n")
        print(f"  {'PASS' if record['passed'] else 'fail'} in {record.get('minutes')} min", flush=True)
    summarise(args.agent, run_id, records)


if __name__ == "__main__":
    main()
