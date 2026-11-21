"""Tests for scripts/cost_report.py. Run: python3 -m unittest discover scripts/tests"""

import json
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import cost_report  # noqa: E402

REPO = "/fake/work/Repo"
PRICES = {
    "updated": "test",
    "models": {
        "claude-opus-5-5": {"input": 4.0, "output": 20.0, "cache_read": 0.2, "cache_write_5m": 5.0, "cache_write_1h": 8.0},
        "claude-haiku-5-5": {"input": 0.1, "output": 0.5, "cache_read": 0.01, "cache_write_5m": 0.125, "cache_write_1h": 0.2,
                             "long_context_over": 100000,
                             "long_context": {"input": 0.5, "output": 2.5, "cache_read": 0.05,
                                              "cache_write_5m": 0.625, "cache_write_1h": 1.0}},
    },
}


def response(msg_id, branch, output=1_000_000, model="claude-opus-5-5", tools=(), time="2026-11-20T10:00:00Z", **usage):
    content = [{"type": "tool_use", "id": t.get("id", "t"), "name": t["name"], "input": t["input"]} for t in tools]
    u = {"input_tokens": 0, "output_tokens": output, "cache_read_input_tokens": 0}
    u.update(usage)
    return {"type": "assistant", "gitBranch": branch, "timestamp": time,
            "message": {"id": msg_id, "model": model, "usage": u, "content": content}}


def skill(name, args):
    return {"name": "Skill", "input": {"skill": name, "args": args}}


def prompt(text="next", branch="feat/a"):
    return {"type": "user", "gitBranch": branch, "message": {"role": "user", "content": text}}


class Logs:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.claude = os.path.join(self.tmp.name, "claude")
        self.codex = os.path.join(self.tmp.name, "codex")
        self.project = os.path.join(self.claude, re.sub(r"[/.]", "-", REPO))
        os.makedirs(self.project)
        os.makedirs(self.codex)

    def session(self, name, entries):
        with open(os.path.join(self.project, name + ".jsonl"), "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

    def subagent(self, session, agent_id, agent_type, tool_use_id, entries):
        folder = os.path.join(self.project, session, "subagents")
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, f"agent-{agent_id}.jsonl"), "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")
        with open(os.path.join(folder, f"agent-{agent_id}.meta.json"), "w") as f:
            json.dump({"agentType": agent_type, "toolUseId": tool_use_id}, f)

    def codex_session(self, name, branch, entries, **meta):
        folder = os.path.join(self.codex, "2026", "11", "20")
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, name + ".jsonl"), "w") as f:
            payload = {"cwd": REPO, "git": {"branch": branch}}
            payload.update(meta)
            f.write(json.dumps({"type": "session_meta", "payload": payload}) + "\n")
            for e in entries:
                f.write(json.dumps(e) + "\n")

    def report(self, change="add-a", branch="feat/a", known=()):
        text, cost, tokens = cost_report.build_report(change, branch, self.claude, self.codex, PRICES, repo=REPO,
                                                      today="2026-11-21", known=known)
        rows = {}
        for line in text.splitlines():
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) == 8 and cells[0] not in ("Step", "---") and not cells[0].startswith("**"):
                rows[(cells[0], cells[2])] = cells
        return text, cost, tokens, rows


def codex_tokens(inp, cached, out, time=None):
    return {"type": "event_msg", "timestamp": time, "payload": {"type": "token_count", "info": {"total_token_usage": {
        "input_tokens": inp, "cached_input_tokens": cached, "output_tokens": out}}}}


def codex_user(text, time=None):
    return {"type": "response_item", "timestamp": time, "payload": {"type": "message", "role": "user",
                                                                    "content": [{"type": "input_text", "text": text}]}}


class CostReportTests(unittest.TestCase):
    def setUp(self):
        self.logs = Logs()

    def tearDown(self):
        self.logs.tmp.cleanup()

    def test_steps_from_markers_with_propose_on_main(self):
        self.logs.session("s1", [
            prompt("let's plan", "main"),
            response("m0", "main"),                                            # discussion before propose
            response("m1", "main", tools=[skill("opsx:propose", "add-a: thing")]),
            response("m2", "feat/a", tools=[skill("opsx:apply", "add-a")]),
            response("m3", "feat/a", tools=[skill("policy-review", "Change add-a on branch feat/a")]),
            response("m4", "feat/a", tools=[skill("opsx:archive", "add-a")]),
            prompt("open the PR"),
            response("m5", "feat/a"),
        ])
        text, cost, tokens, rows = self.logs.report()
        self.assertEqual(rows[("Plan", "claude-opus-5-5")][6], "2,000,000")
        self.assertEqual(rows[("Build", "claude-opus-5-5")][6], "1,000,000")
        self.assertEqual(rows[("Policy review", "claude-opus-5-5")][6], "1,000,000")
        self.assertEqual(rows[("Archive", "claude-opus-5-5")][6], "1,000,000")
        self.assertEqual(rows[("PR and review", "claude-opus-5-5")][6], "1,000,000")
        self.assertAlmostEqual(cost, 6 * 20.0)
        self.assertEqual(tokens, 6_000_000)
        self.assertIn("Total tokens: 6,000,000. Total estimated cost: $120.00.", text)

    def test_later_session_on_branch_takes_step_from_time(self):
        self.logs.session("s1", [
            response("m1", "main", tools=[skill("opsx:propose", "add-a")], time="2026-11-20T09:00:00Z"),
            response("m2", "feat/a", tools=[skill("opsx:apply", "add-a")], time="2026-11-20T10:00:00Z"),
        ])
        self.logs.session("s2", [
            response("n1", "feat/a", time="2026-11-20T11:00:00Z"),                  # before this session's marker
            response("n2", "feat/a", tools=[skill("opsx:archive", "add-a")], time="2026-11-20T12:00:00Z"),
        ])
        self.logs.session("s3", [response("p1", "feat/a", time="2026-11-20T13:00:00Z")])   # review fixes, no marker
        _, _, _, rows = self.logs.report()
        self.assertEqual(rows[("Build", "claude-opus-5-5")][6], "2,000,000")   # m2 and n1
        self.assertEqual(rows[("Archive", "claude-opus-5-5")][6], "1,000,000")
        self.assertEqual(rows[("PR and review", "claude-opus-5-5")][6], "1,000,000")

    def test_two_verifier_runs(self):
        self.logs.session("s1", [
            response("m1", "feat/a", tools=[skill("opsx:apply", "add-a")]),
            response("m2", "feat/a", tools=[{"id": "tu1", "name": "Agent", "input": {"subagent_type": "verifier"}}]),
            response("m3", "feat/a", tools=[{"id": "tu2", "name": "Agent", "input": {"subagent_type": "verifier"}}]),
        ])
        self.logs.subagent("s1", "v1", "verifier", "tu1", [response("v1", "feat/a", output=500_000)])
        self.logs.subagent("s1", "v2", "verifier", "tu2", [response("v2", "feat/a", output=300_000)])
        _, _, _, rows = self.logs.report()
        self.assertEqual(rows[("Verify", "claude-opus-5-5")][6], "800,000")

    def test_each_response_counted_once(self):
        self.logs.session("s1", [
            response("m1", "feat/a", tools=[skill("opsx:apply", "add-a")]),
            response("m1", "feat/a"),
            response("m1", "feat/a"),
        ])
        _, cost, _, _ = self.logs.report()
        self.assertAlmostEqual(cost, 20.0)

    def test_another_change_in_same_session_not_counted(self):
        self.logs.session("s1", [
            response("m1", "main", tools=[skill("opsx:propose", "add-a")]),
            response("m2", "main"),
            response("m3", "main", tools=[skill("opsx:propose", "add-b")]),
            response("m4", "main"),
            response("m5", "feat/b", tools=[skill("opsx:apply", "add-b")]),
        ])
        _, cost, _, rows = self.logs.report()
        self.assertAlmostEqual(cost, 40.0)
        self.assertEqual(list(rows), [("Plan", "claude-opus-5-5")])

    def test_verifier_subagent_is_verify(self):
        self.logs.session("s1", [
            response("m1", "feat/a", tools=[skill("opsx:apply", "add-a")]),
            response("m2", "feat/a", tools=[{"id": "tu1", "name": "Agent", "input": {"subagent_type": "verifier", "prompt": "add-a"}}]),
        ])
        self.logs.subagent("s1", "v1", "verifier", "tu1", [response("v1", "feat/a", output=500_000)])
        _, _, _, rows = self.logs.report()
        self.assertEqual(rows[("Verify", "claude-opus-5-5")][6], "500,000")
        self.assertEqual(rows[("Build", "claude-opus-5-5")][6], "2,000,000")

    def test_cache_rates_and_haiku_long_prompt(self):
        self.logs.session("s1", [
            response("m1", "feat/a", output=0, tools=[skill("opsx:apply", "add-a")],
                     cache_read_input_tokens=1_000_000, cache_creation={"ephemeral_5m_input_tokens": 1_000_000,
                                                                        "ephemeral_1h_input_tokens": 1_000_000}),
            response("m2", "feat/a", output=1_000_000, model="claude-haiku-5-5", input_tokens=40_000),
            response("m3", "feat/a", output=1_000_000, model="claude-haiku-5-5", input_tokens=200_000),
        ])
        _, _, _, rows = self.logs.report()
        self.assertEqual(rows[("Build", "claude-opus-5-5")][7], "$13.20")   # 0.2 + 5 + 8
        # Each response priced on its own: 40K prompt at the normal rate ($0.504), 200K at the long rate ($2.60).
        self.assertEqual(rows[("Build", "claude-haiku-5-5")][7], "$3.10")

    def test_other_row_from_session_total(self):
        self.logs.session("s1", [
            response("m1", "feat/a", tools=[skill("opsx:apply", "add-a")]),       # $20, ours
            response("m2", "main", tools=[skill("opsx:propose", "add-b")]),        # $20, not ours
            {"type": "cost-state", "modelUsage": {"claude-opus-5-5": {"costUSD": 44.0}}},
        ])
        text, cost, _, _ = self.logs.report()
        self.assertIn("| Other | Claude Code | session overhead", text)
        self.assertAlmostEqual(cost, 22.0)   # $20 + half of the $4 overhead

    def test_codex_differences_and_no_price(self):
        self.logs.codex_session("c1", "feat/a", [
            {"type": "turn_context", "payload": {"model": "gpt-test"}},
            codex_user("$openspec-apply-change add-a"),
            codex_tokens(1000, 400, 100),
            codex_tokens(3000, 1400, 300),
        ])
        text, cost, tokens, rows = self.logs.report()
        row = rows[("Build", "gpt-test")]
        self.assertEqual(row[1], "Codex")
        self.assertEqual(row[3:8], ["1,600", "0", "1,400", "300", "no price"])
        self.assertEqual(cost, 0)
        self.assertIn("leaves out models with no price", text)
        self.assertEqual(tokens, 3300)

    def test_codex_steps_change_after_a_prompt(self):
        self.logs.codex_session("c1", "feat/a", [
            {"type": "turn_context", "payload": {"model": "gpt-test"}},
            codex_user("$openspec-apply-change add-a"),
            codex_tokens(100, 0, 10),
            codex_user("$policy-review add-a"),
            codex_tokens(200, 0, 20),
            codex_user("thanks, carry on"),
            codex_tokens(300, 0, 30),
            codex_user("$openspec-archive-change add-a"),
            codex_tokens(400, 0, 40),
            codex_user("now open the PR"),
            codex_tokens(500, 0, 50),
        ])
        _, _, _, rows = self.logs.report()
        self.assertEqual(rows[("Build", "gpt-test")][6], "20")
        self.assertEqual(rows[("Policy review", "gpt-test")][6], "10")
        self.assertEqual(rows[("Archive", "gpt-test")][6], "10")
        self.assertEqual(rows[("PR and review", "gpt-test")][6], "10")

    def test_codex_session_without_markers_takes_step_from_time(self):
        self.logs.session("s1", [
            response("m1", "feat/a", tools=[skill("opsx:apply", "add-a")], time="2026-11-20T10:00:00Z"),
            response("m2", "feat/a", tools=[skill("opsx:archive", "add-a")], time="2026-11-20T11:00:00Z"),
        ])
        self.logs.codex_session("c1", "feat/a", [
            {"type": "turn_context", "payload": {"model": "gpt-test"}},
            codex_tokens(100, 0, 10, time="2026-11-20T12:00:00Z"),
        ])
        _, _, _, rows = self.logs.report()
        self.assertEqual(rows[("PR and review", "gpt-test")][6], "10")

    def test_codex_on_another_feature_branch_not_counted(self):
        self.logs.codex_session("c1", "feat/b", [
            {"type": "turn_context", "payload": {"model": "gpt-test"}},
            codex_user("$openspec-apply-change add-a"),
            codex_tokens(100, 0, 10),
        ])
        text, _, _, rows = self.logs.report()
        self.assertEqual(rows, {})
        self.assertIn("No agent work was found", text)

    def test_codex_injected_context_is_not_a_marker(self):
        self.logs.codex_session("c1", "feat/a", [
            {"type": "turn_context", "payload": {"model": "gpt-test"}},
            codex_user("# AGENTS.md instructions\n... then run $openspec-archive-change <name> ..."),
            codex_user("$openspec-apply-change add-a"),
            codex_user("<skill>\n... when done, run $openspec-archive-change add-a\n</skill>"),
            codex_tokens(100, 0, 10),
        ])
        _, _, _, rows = self.logs.report()
        self.assertEqual(list(rows), [("Build", "gpt-test")])

    def test_other_checkouts_with_a_similar_path_not_read(self):
        other = os.path.join(self.logs.claude, re.sub(r"[/.]", "-", REPO + "Other"))
        os.makedirs(other)
        with open(os.path.join(other, "s9.jsonl"), "w") as f:
            f.write(json.dumps(response("x1", "feat/a")) + "\n")
        worktree = os.path.join(self.logs.claude, re.sub(r"[/.]", "-", REPO + "/.claude/worktrees/wt1"))
        os.makedirs(worktree)
        with open(os.path.join(worktree, "s8.jsonl"), "w") as f:
            f.write(json.dumps(response("w1", "feat/a")) + "\n")
        folder = os.path.join(self.logs.codex, "2026", "11", "21")
        os.makedirs(folder)
        with open(os.path.join(folder, "c9.jsonl"), "w") as f:
            f.write(json.dumps({"type": "session_meta", "payload": {"cwd": REPO + "Other", "git": {"branch": "feat/a"}}}) + "\n")
            f.write(json.dumps(codex_tokens(100, 0, 10)) + "\n")
        _, cost, tokens, _ = self.logs.report()
        self.assertEqual(tokens, 1_000_000)   # only the worktree session
        self.assertAlmostEqual(cost, 20.0)

    def test_subagent_in_session_without_markers_takes_step_from_time(self):
        self.logs.session("s1", [
            response("m1", "feat/a", tools=[skill("opsx:apply", "add-a")], time="2026-11-20T10:00:00Z"),
            response("m2", "feat/a", tools=[skill("opsx:archive", "add-a")], time="2026-11-20T11:00:00Z"),
        ])
        self.logs.session("s2", [
            response("n1", "feat/a", time="2026-11-20T12:00:00Z",
                     tools=[{"id": "tu9", "name": "Agent", "input": {"subagent_type": "general-purpose"}}]),
        ])
        self.logs.subagent("s2", "g1", "general-purpose", "tu9", [response("g1", "feat/a", output=300_000)])
        _, _, _, rows = self.logs.report()
        self.assertEqual(rows[("PR and review", "claude-opus-5-5")][6], "1,300,000")
        self.assertNotIn(("Plan", "claude-opus-5-5"), rows)

    def test_single_word_change_name_switches_context(self):
        self.logs.session("s1", [
            response("m1", "main", tools=[skill("opsx:propose", "add-a")]),
            response("m2", "main", tools=[skill("opsx:propose", "cleanup: tidy the scripts")]),
            response("m3", "main"),
        ])
        _, cost, _, _ = self.logs.report(known={"add-a", "cleanup"})
        self.assertAlmostEqual(cost, 20.0)

    def test_free_text_first_word_is_not_another_change(self):
        self.logs.session("s1", [
            response("m1", "main", tools=[skill("opsx:propose", "add-a")]),
            response("m2", "main", tools=[skill("opsx:update", "tidy the wording of add-a")]),
        ])
        _, cost, _, _ = self.logs.report(known={"add-a", "cleanup"})
        self.assertAlmostEqual(cost, 40.0)

    def test_codex_verifier_subagent_is_verify(self):
        self.logs.session("s1", [
            response("m1", "feat/a", tools=[skill("opsx:apply", "add-a")], time="2026-11-20T10:00:00Z"),
        ])
        self.logs.codex_session("c1", "feat/a", [
            {"type": "turn_context", "payload": {"model": "gpt-test"}},
            {"ordinal": 1, **codex_user("$openspec-apply-change add-a")},      # replayed parent history
            {"ordinal": 2, **codex_tokens(1000, 0, 100)},                      # replayed: parent's tokens
            {"ordinal": 5, **codex_tokens(1500, 0, 130, time="2026-11-20T11:00:00Z")},
        ], agent_role="verifier", parent_thread_id="p1", subagent_history_start_ordinal=3)
        _, _, _, rows = self.logs.report()
        self.assertEqual(rows[("Verify", "gpt-test")][3:7], ["500", "0", "0", "30"])
        self.assertNotIn(("Build", "gpt-test"), rows)

    def test_marker_in_a_later_line_of_the_same_response(self):
        thinking = response("m2", "feat/a")
        thinking["message"]["content"] = [{"type": "thinking", "thinking": ""}]
        self.logs.session("s1", [
            response("m1", "feat/a", tools=[skill("opsx:apply", "add-a")]),
            thinking,
            response("m2", "feat/a", tools=[skill("opsx:archive", "add-a")]),
        ])
        _, _, _, rows = self.logs.report()
        self.assertEqual(rows[("Build", "claude-opus-5-5")][6], "1,000,000")
        self.assertEqual(rows[("Archive", "claude-opus-5-5")][6], "1,000,000")

    def test_trunk_branch_counts_only_marked_work(self):
        self.logs.session("s1", [response("u1", "main")])                      # unrelated work on main
        self.logs.session("s2", [response("m1", "main", tools=[skill("opsx:propose", "add-a")])])
        _, cost, _, _ = self.logs.report(branch="main")
        self.assertAlmostEqual(cost, 20.0)

    def test_command_line_refuses_trunk_without_branch(self):
        import contextlib, io
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = cost_report.main(["add-a", "--branch", "main", "--print",
                                     "--claude-dir", self.logs.claude, "--codex-dir", self.logs.codex])
        self.assertEqual(code, 2)
        self.assertIn("--branch", err.getvalue())

    def test_no_other_row_when_session_has_unpriced_work(self):
        self.logs.session("s1", [
            response("m1", "feat/a", tools=[skill("opsx:apply", "add-a")]),          # $20
            response("m2", "main", model="some-new-model", tools=[skill("opsx:propose", "add-b")]),
            {"type": "cost-state", "modelUsage": {"claude-opus-5-5": {"costUSD": 20.0}, "some-new-model": {"costUSD": 10.0}}},
        ])
        text, cost, _, _ = self.logs.report()
        self.assertNotIn("| Other |", text)
        self.assertAlmostEqual(cost, 20.0)

    def test_codex_subagent_takes_its_parents_step(self):
        self.logs.codex_session("p1", "feat/a", [
            {"type": "turn_context", "payload": {"model": "gpt-test"}},
            codex_user("$openspec-apply-change add-a", time="2026-11-20T10:00:00Z"),
            codex_user("$policy-review add-a", time="2026-11-20T11:00:00Z"),
        ], id="parent")
        self.logs.codex_session("w1", "feat/a", [
            {"type": "turn_context", "payload": {"model": "gpt-test"}},
            codex_tokens(100, 0, 10, time="2026-11-20T11:05:00Z"),
        ], id="child", parent_thread_id="parent", agent_role="worker", timestamp="2026-11-20T11:01:00Z")
        self.logs.codex_session("e1", "feat/a", [
            {"type": "turn_context", "payload": {"model": "gpt-test"}},
            codex_tokens(200, 0, 20, time="2026-11-20T12:05:00Z"),
        ], id="grandchild", parent_thread_id="verifier1", agent_role="explorer", timestamp="2026-11-20T12:01:00Z")
        self.logs.codex_session("v1", "feat/a", [], id="verifier1", parent_thread_id="parent", agent_role="verifier",
                                timestamp="2026-11-20T12:00:00Z")
        _, _, _, rows = self.logs.report()
        self.assertEqual(rows[("Policy review", "gpt-test")][6], "10")
        self.assertEqual(rows[("Verify", "gpt-test")][6], "20")       # an explorer the verifier started

    def test_nested_claude_subagent_counted_with_its_parents_step(self):
        self.logs.session("s1", [
            response("m1", "feat/a", tools=[skill("opsx:apply", "add-a")]),
            response("m2", "feat/a", tools=[{"id": "tu1", "name": "Agent", "input": {"subagent_type": "verifier"}}]),
        ])
        self.logs.subagent("s1", "v1", "verifier", "tu1", [
            response("v1", "feat/a", output=500_000,
                     tools=[{"id": "tu2", "name": "Agent", "input": {"subagent_type": "Explore"}}])])
        self.logs.subagent("s1", "x1", "Explore", "tu2", [response("x1", "feat/a", output=200_000)])
        _, _, _, rows = self.logs.report()
        self.assertEqual(rows[("Verify", "claude-opus-5-5")][6], "700,000")

    def test_injected_notices_are_not_prompts(self):
        self.logs.session("s1", [
            response("m1", "feat/a", tools=[skill("opsx:archive", "add-a")]),
            prompt("<task-notification>agent finished</task-notification>", "feat/a"),
            response("m2", "feat/a"),
            prompt("open the PR", "feat/a"),
            response("m3", "feat/a"),
        ])
        _, _, _, rows = self.logs.report()
        self.assertEqual(rows[("Archive", "claude-opus-5-5")][6], "2,000,000")
        self.assertEqual(rows[("PR and review", "claude-opus-5-5")][6], "1,000,000")

    def test_claude_folder_name_replaces_every_other_character(self):
        repo = "/fake/my work_dir/Repo.v2"
        folder = os.path.join(self.logs.claude, "-fake-my-work-dir-Repo-v2")
        os.makedirs(folder)
        self.assertEqual(cost_report.claude_project_dirs(self.logs.claude, repo), [folder])

    def test_investigation_before_the_proposal_counts_as_plan(self):
        self.logs.session("s1", [
            response("m0", "main", tools=[{"id": "tu1", "name": "Agent", "input": {"subagent_type": "Explore"}}]),
            response("m1", "main", tools=[skill("opsx:propose", "add-a")]),
        ])
        self.logs.subagent("s1", "x1", "Explore", "tu1", [response("x1", "main", output=500_000)])
        _, _, tokens, rows = self.logs.report()
        self.assertEqual(rows[("Plan", "claude-opus-5-5")][6], "2,500,000")

    def test_codex_verifier_on_main_keeps_its_parents_change(self):
        self.logs.codex_session("p1", "main", [
            {"type": "turn_context", "payload": {"model": "gpt-test"}},
            codex_user("$openspec-apply-change add-a", time="2026-11-20T10:00:00Z"),
        ], id="parent")
        self.logs.codex_session("v1", "main", [
            {"type": "turn_context", "payload": {"model": "gpt-test"}},
            codex_tokens(100, 0, 10, time="2026-11-20T11:05:00Z"),
        ], id="verifier1", parent_thread_id="parent", agent_role="verifier", timestamp="2026-11-20T11:00:00Z")
        self.logs.codex_session("e1", "main", [
            {"type": "turn_context", "payload": {"model": "gpt-test"}},
            codex_tokens(200, 0, 20, time="2026-11-20T11:10:00Z"),
        ], id="explorer1", parent_thread_id="verifier1", agent_role="explorer", timestamp="2026-11-20T11:06:00Z")
        _, _, _, rows = self.logs.report()
        self.assertEqual(rows[("Verify", "gpt-test")][6], "30")

    def test_no_conversation_text_in_report(self):
        self.logs.session("s1", [prompt("SECRET-PROMPT", "feat/a"),
                                 response("m1", "feat/a", tools=[skill("opsx:apply", "add-a SECRET-ARGS")])])
        text, _, _, _ = self.logs.report()
        self.assertNotIn("SECRET", text)

    def test_nothing_found(self):
        text, cost, _, _ = self.logs.report()
        self.assertIn("No agent work was found", text)
        self.assertEqual(cost, 0)


if __name__ == "__main__":
    unittest.main()
