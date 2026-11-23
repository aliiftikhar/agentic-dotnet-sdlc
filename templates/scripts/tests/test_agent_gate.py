import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import agent_gate as g  # noqa: E402

REPO = "owner/repo"


def pr(head, base="main", number=5, state="open", repo=REPO, **extra):
    return {"number": number, "state": state, "head": {"ref": head, "repo": {"full_name": repo}},
            "base": {"ref": base}, **extra}


class FakeApi:
    def __init__(self, perms=None, branches=(), prs=None, inline=None, comments=None):
        self.perms, self.branches = perms or {"owner": "admin"}, set(branches)
        self.prs, self.inline, self.comments = prs or {}, inline or {}, comments or []

    def __call__(self, path):
        if "/collaborators/" in path:
            login = path.split("/collaborators/")[1].split("/")[0]
            return {"permission": self.perms.get(login, "read")}
        if "/branches/" in path:
            return {} if path.split("/branches/")[1] in self.branches else None
        if "/reviews/" in path:
            return self.inline.get(int(path.split("/reviews/")[1].split("/")[0]), [])
        if "/issues/" in path and path.endswith("per_page=100"):
            return self.comments
        if "/pulls?" in path:
            return [{"number": 9}]
        if "/pulls/" in path:
            return self.prs.get(int(path.split("/pulls/")[1]))
        raise AssertionError(path)


def gate(name, event, api=None, users="", rounds=""):
    return g.Gate(name, event, REPO, "owner", users, rounds, api or FakeApi())


def label_event(sender="owner", author="owner", title="Add ValidateRequest() to the 4 handlers now", label="agent:plan"):
    return {"action": "labeled", "label": {"name": label}, "sender": {"login": sender},
            "issue": {"number": 87, "title": title, "user": {"login": author}}}


class Names(unittest.TestCase):
    def test_slug(self):
        self.assertEqual(g.slug("Add ValidateRequest() to the 4 handlers now"), "add-validaterequest-to-the-4")
        self.assertEqual(g.slug("4 handlers"), "change-4-handlers")
        self.assertEqual(g.slug("!!!"), "change")

    def test_parse_branch(self):
        self.assertEqual(g.parse_branch("agent/87-add-x", plan=False), (87, "add-x"))
        self.assertEqual(g.parse_branch("agent/87-add-x-plan", plan=True), (87, "add-x"))
        self.assertIsNone(g.parse_branch("agent/87-add-x", plan=True))
        self.assertIsNone(g.parse_branch("feat/add-x", plan=False))

    def test_change_name_ending_in_plan(self):
        # Issue "Add a revision plan": the build branch itself ends in -plan.
        self.assertEqual(g.parse_branch("agent/87-add-a-revision-plan", plan=False), (87, "add-a-revision-plan"))
        self.assertEqual(g.parse_branch("agent/87-add-a-revision-plan-plan", plan=True), (87, "add-a-revision-plan"))
        self.assertEqual(g.parse_branch("agent/87-plan-plan", plan=True), (87, "plan"))
        build, plan = "agent/87-add-a-revision-plan", "agent/87-add-a-revision-plan-plan"
        review = {"action": "submitted", "review": {"id": 1, "user": {"login": "owner"}, "body": "x"},
                  "pull_request": pr(build, "main", number=6)}
        out = gate("pull_request_review", review).decide("build")
        self.assertEqual((out["run"], out["kind"], out["change"]), ("true", "fix", "add-a-revision-plan"))
        review["pull_request"] = pr(plan, build, number=5)
        out = gate("pull_request_review", review).decide("plan")
        self.assertEqual((out["kind"], out["build_branch"]), ("revise", build))
        merge = {"action": "closed", "pull_request": pr(plan, build, number=5, merged=True, merged_by={"login": "owner"})}
        out = gate("pull_request", merge).decide("build")
        self.assertEqual((out["kind"], out["change"]), ("build", "add-a-revision-plan"))

    def test_users_default_to_owner(self):
        self.assertEqual(g.agent_users("", "Owner"), ["owner"])
        self.assertEqual(g.agent_users(" a, B ", "owner"), ["a", "b"])


class Start(unittest.TestCase):
    def test_owner_labels_own_issue(self):
        out = gate("issues", label_event()).decide("plan")
        self.assertEqual(out["run"], "true")
        self.assertEqual(out["kind"], "start")
        self.assertEqual(out["build_branch"], "agent/87-add-validaterequest-to-the-4")
        self.assertEqual(out["plan_branch"], "agent/87-add-validaterequest-to-the-4-plan")

    def test_someone_else(self):
        self.assertEqual(gate("issues", label_event(sender="eve")).decide("plan")["run"], "false")
        self.assertEqual(gate("issues", label_event(author="eve")).decide("plan")["run"], "false")
        self.assertEqual(gate("issues", label_event(label="bug")).decide("plan")["run"], "false")

    def test_agent_users_variable(self):
        e = label_event(sender="alice", author="alice")
        self.assertEqual(gate("issues", e, users="alice").decide("plan")["run"], "true")
        self.assertEqual(gate("issues", e, users="bob").decide("plan")["run"], "false")
        self.assertEqual(gate("issues", label_event(), users="alice").decide("plan")["run"], "false")

    def test_branches_exist(self):
        api = FakeApi(branches={"agent/87-add-validaterequest-to-the-4"})
        out = gate("issues", label_event(), api).decide("plan")
        self.assertEqual(out["run"], "false")
        self.assertIn("#9", out["notice"])
        self.assertEqual(out["notice_on"], "87")

    def test_build_workflow_ignores_labels(self):
        self.assertEqual(gate("issues", label_event()).decide("build")["run"], "false")


class Build(unittest.TestCase):
    def merged(self, by="owner", head="agent/87-add-x-plan", base="agent/87-add-x", merged=True):
        return {"action": "closed", "pull_request": pr(head, base, number=12, merged=merged, merged_by={"login": by})}

    def test_owner_merges_plan(self):
        out = gate("pull_request", self.merged()).decide("build")
        self.assertEqual((out["run"], out["kind"], out["pr"], out["change"]), ("true", "build", "12", "add-x"))

    def test_not_merged_or_not_owner(self):
        self.assertEqual(gate("pull_request", self.merged(merged=False)).decide("build")["run"], "false")
        out = gate("pull_request", self.merged(by="eve")).decide("build")
        self.assertEqual(out["run"], "false")
        self.assertIn("notice", out)

    def test_not_a_plan_pr(self):
        self.assertEqual(gate("pull_request", self.merged(head="agent/87-add-x", base="main")).decide("build")["run"], "false")
        self.assertEqual(gate("pull_request", self.merged(base="agent/88-other")).decide("build")["run"], "false")


class Comments(unittest.TestCase):
    def event(self, login="owner", body="please change X", number=5):
        return {"action": "created", "issue": {"number": number, "pull_request": {}},
                "comment": {"id": 44, "user": {"login": login}, "body": body}}

    def api(self, **kw):
        return FakeApi(prs={5: pr("agent/87-add-x-plan", "agent/87-add-x"), 6: pr("agent/87-add-x")},
                       perms={"owner": "admin", "rev": "write", "reader": "read"}, **kw)

    def test_reviewer_on_plan_pr_revises(self):
        out = gate("issue_comment", self.event("rev"), self.api()).decide("plan")
        self.assertEqual((out["run"], out["kind"], out["trigger"]), ("true", "revise", "comment 44 by rev"))
        self.assertEqual(gate("issue_comment", self.event("rev"), self.api()).decide("build")["run"], "false")

    def test_reviewer_on_agent_pr_fixes(self):
        out = gate("issue_comment", self.event(number=6), self.api()).decide("build")
        self.assertEqual((out["run"], out["kind"]), ("true", "fix"))

    def test_refused(self):
        for login in ("reader", "claude[bot]", g.CODEX, "stranger"):
            self.assertEqual(gate("issue_comment", self.event(login), self.api()).decide("plan")["run"], "false", login)
        self.assertEqual(gate("issue_comment", self.event(body="@codex review", number=6), self.api()).decide("build")["run"], "false")

    def test_closed_or_other_pr(self):
        api = FakeApi(prs={5: pr("agent/87-add-x-plan", "agent/87-add-x", state="closed"), 7: pr("feat/x")})
        self.assertEqual(gate("issue_comment", self.event(), api).decide("plan")["run"], "false")
        self.assertEqual(gate("issue_comment", self.event(number=7), api).decide("build")["run"], "false")


class Reviews(unittest.TestCase):
    def event(self, login, body="", head="agent/87-add-x", base="main", review_id=1):
        return {"action": "submitted", "review": {"id": review_id, "user": {"login": login}, "body": body},
                "pull_request": pr(head, base, number=6)}

    def test_codex_with_findings(self):
        api = FakeApi(inline={1: [{"id": 1}]})
        out = gate("pull_request_review", self.event(g.CODEX), api).decide("build")
        self.assertEqual((out["run"], out["kind"], out["codex"]), ("true", "fix", "true"))

    def test_codex_without_findings(self):
        self.assertEqual(gate("pull_request_review", self.event(g.CODEX), FakeApi()).decide("build")["run"], "false")

    def test_codex_round_cap(self):
        marks = [{"body": g.ROUND_MARK + " round"}] * 3
        api = FakeApi(inline={1: [{"id": 1}]}, comments=marks)
        out = gate("pull_request_review", self.event(g.CODEX), api).decide("build")
        self.assertEqual(out["run"], "false")
        self.assertNotIn(g.ROUND_MARK, out["notice"])
        api.comments = marks[:2]
        self.assertEqual(gate("pull_request_review", self.event(g.CODEX), api).decide("build")["run"], "true")
        self.assertEqual(gate("pull_request_review", self.event(g.CODEX), api, rounds="2").decide("build")["run"], "false")

    def test_codex_on_plan_pr(self):
        api = FakeApi(inline={1: [{"id": 1}]})
        e = self.event(g.CODEX, head="agent/87-add-x-plan", base="agent/87-add-x")
        self.assertEqual(gate("pull_request_review", e, api).decide("plan")["run"], "false")

    def test_empty_approval_skipped(self):
        self.assertEqual(gate("pull_request_review", self.event("owner")).decide("build")["run"], "false")

    def test_reviewer_inline_comment(self):
        api = FakeApi(inline={1: [{"id": 1}]})
        self.assertEqual(gate("pull_request_review", self.event("owner"), api).decide("build")["run"], "true")
        e = self.event("owner", body="Looks wrong", head="agent/87-add-x-plan", base="agent/87-add-x")
        self.assertEqual(gate("pull_request_review", e).decide("plan")["kind"], "revise")

    def test_agent_and_other_bots(self):
        api = FakeApi(inline={1: [{"id": 1}]})
        for login in ("claude[bot]", "dependabot[bot]"):
            self.assertEqual(gate("pull_request_review", self.event(login, "x"), api).decide("build")["run"], "false")

    def test_fork(self):
        e = self.event("owner", "x")
        e["pull_request"]["head"]["repo"]["full_name"] = "eve/repo"
        self.assertEqual(gate("pull_request_review", e).decide("build")["run"], "false")


if __name__ == "__main__":
    unittest.main()
