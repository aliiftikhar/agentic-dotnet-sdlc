#!/usr/bin/env python3
"""Decides whether a GitHub event starts an agent run, and what it works on.

Used by .github/workflows/agent-plan.yml and agent-build.yml (see "Agent runs from issues" in
AGENTS.md). Reads the event from GITHUB_EVENT_PATH, asks the GitHub API through `gh api` when it
needs more, and writes key=value lines to GITHUB_OUTPUT:

  run          true or false
  kind         start | revise | build | fix
  issue        the issue number
  change       the OpenSpec change name
  build_branch agent/<issue>-<change>
  plan_branch  agent/<issue>-<change>-plan
  pr           the PR the run works on (revise, fix), or the merged plan PR (build)
  trigger      what started it, e.g. "review 123 by alice"
  codex        true when a Codex review started it
  notice       a comment to post when the event is refused for a reason the user should see
  notice_on    the issue or PR number for the notice
  reason       why there's no run (for the log)

Checks are on GitHub logins, never email. Standard library only.
"""

import json
import os
import re
import subprocess
import sys

CODEX = "chatgpt-codex-connector[bot]"
AGENT = "claude[bot]"
LABEL = "agent:plan"
ROUND_MARK = "<!-- agent-codex-round -->"
WRITE = {"admin", "maintain", "write"}


def slug(title, words=5):
    parts = re.findall(r"[a-z0-9]+", (title or "").lower())[:words]
    name = "-".join(parts) or "change"
    return name if name[0].isalpha() else "change-" + name


def agent_users(variable, owner):
    users = [u.strip().lower() for u in (variable or "").split(",") if u.strip()]
    return users or [owner.lower()]


def parse_branch(ref, plan):
    """(issue, change) for an agent/ build branch (plan=False) or plan branch (plan=True), else None.

    The caller says which it expects (from the PR's base), because a change name can itself end in
    "-plan": issue "Add a revision plan" has build branch agent/87-add-a-revision-plan.
    """
    m = re.fullmatch(r"agent/(\d+)-([a-z0-9][a-z0-9-]*)", ref or "")
    if not m:
        return None
    issue, change = int(m.group(1)), m.group(2)
    if plan:
        if not change.endswith("-plan"):
            return None
        change = change[:-len("-plan")]
    return issue, change


def gh_api(path):
    out = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if out.returncode != 0:
        return None
    return json.loads(out.stdout)


class Gate:
    def __init__(self, event_name, event, repo, owner, users_var="", max_rounds="", api=gh_api):
        self.name, self.event, self.repo, self.api = event_name, event, repo, api
        self.users = agent_users(users_var, owner)
        self.max_rounds = int(max_rounds) if str(max_rounds or "").strip().isdigit() else 3

    # ---------- helpers ----------

    def is_user(self, login):
        return (login or "").lower() in self.users

    def can_write(self, login):
        if not login or login.endswith("[bot]"):
            return False
        data = self.api(f"repos/{self.repo}/collaborators/{login}/permission")
        return bool(data) and data.get("permission") in WRITE

    def no(self, reason, **extra):
        return {"run": "false", "reason": reason, **extra}

    def target(self, pr, workflow):
        """The run kind for an open PR in this repo, for the plan or build workflow, or None."""
        if not pr or pr.get("state") != "open":
            return None
        head, base = pr["head"], pr["base"]
        if (head.get("repo") or {}).get("full_name", "").lower() != self.repo.lower():
            return None
        if workflow == "plan":
            parsed = parse_branch(head["ref"], plan=True)
            if parsed and base["ref"] == f"agent/{parsed[0]}-{parsed[1]}":
                return ("revise", *parsed)
        if workflow == "build" and base["ref"] == "main":
            parsed = parse_branch(head["ref"], plan=False)
            if parsed:
                return ("fix", *parsed)
        return None

    def result(self, kind, issue, change, pr, trigger, codex=False):
        return {"run": "true", "kind": kind, "issue": str(issue), "change": change,
                "build_branch": f"agent/{issue}-{change}", "plan_branch": f"agent/{issue}-{change}-plan",
                "pr": str(pr), "trigger": trigger, "codex": "true" if codex else "false"}

    # ---------- events ----------

    def decide(self, workflow):
        e = self.event
        if self.name == "issues" and workflow == "plan":
            return self.labeled(e)
        if self.name == "pull_request" and workflow == "build":
            return self.merged(e)
        if self.name == "issue_comment":
            return self.comment(e, workflow)
        if self.name == "pull_request_review":
            return self.review(e, workflow)
        return self.no(f"{self.name} isn't handled by the {workflow} workflow")

    def labeled(self, e):
        issue = e.get("issue") or {}
        if e.get("action") != "labeled" or (e.get("label") or {}).get("name") != LABEL:
            return self.no("not the agent:plan label")
        if "pull_request" in issue:
            return self.no("label is on a pull request")
        if not self.is_user((e.get("sender") or {}).get("login")):
            return self.no("label added by someone who isn't an agent user")
        if not self.is_user((issue.get("user") or {}).get("login")):
            return self.no("issue opened by someone who isn't an agent user")
        number, change = issue["number"], slug(issue.get("title"))
        branch = f"agent/{number}-{change}"
        if self.api(f"repos/{self.repo}/branches/{branch}") is not None:
            prs = self.api(f"repos/{self.repo}/pulls?state=all&head={self.repo.split('/')[0]}:{branch}-plan") or []
            link = f" See #{prs[0]['number']}." if prs else ""
            return self.no("branches exist", notice_on=str(number),
                           notice=f"An agent plan for this issue already exists on `{branch}-plan`.{link} "
                                  "To start again, delete both `agent/` branches, then add the label again.")
        return self.result("start", number, change, "", f"label by {e['sender']['login']}")

    def merged(self, e):
        pr = e.get("pull_request") or {}
        if e.get("action") != "closed" or not pr.get("merged"):
            return self.no("not a merge")
        parsed = parse_branch(pr["head"]["ref"], plan=True)
        if not parsed or pr["base"]["ref"] != f"agent/{parsed[0]}-{parsed[1]}":
            return self.no("not a plan PR")
        if (pr["head"].get("repo") or {}).get("full_name", "").lower() != self.repo.lower():
            return self.no("plan PR from another repository")
        login = (pr.get("merged_by") or {}).get("login")
        if not self.is_user(login):
            return self.no("plan merged by someone who isn't an agent user", notice_on=str(pr["number"]),
                           notice="This plan was merged by someone who isn't an agent user, so no build starts.")
        issue, change = parsed
        return self.result("build", issue, change, pr["number"], f"plan PR #{pr['number']} merged by {login}")

    def comment(self, e, workflow):
        if e.get("action") != "created" or "pull_request" not in (e.get("issue") or {}):
            return self.no("not a new PR comment")
        c = e["comment"]
        login = (c.get("user") or {}).get("login", "")
        if login.lower() == AGENT or login.endswith("[bot]"):
            return self.no(f"comment by {login}")
        if (c.get("body") or "").strip().lower().startswith("@codex"):
            return self.no("a request to Codex, not to the agent")
        number = e["issue"]["number"]
        found = self.target(self.api(f"repos/{self.repo}/pulls/{number}"), workflow)
        if not found:
            return self.no("not an open agent PR for this workflow")
        if not self.can_write(login):
            return self.no(f"{login} has no write access")
        kind, issue, change = found
        return self.result(kind, issue, change, number, f"comment {c['id']} by {login}")

    def review(self, e, workflow):
        r, pr = e.get("review") or {}, e.get("pull_request") or {}
        login = (r.get("user") or {}).get("login", "")
        if e.get("action") != "submitted" or login.lower() == AGENT:
            return self.no(f"review by {login or 'nobody'}")
        found = self.target(pr, workflow)
        if not found:
            return self.no("not an open agent PR for this workflow")
        kind, issue, change = found
        number = pr["number"]
        inline = self.api(f"repos/{self.repo}/pulls/{number}/reviews/{r['id']}/comments") or []
        if login == CODEX:
            if kind != "fix":
                return self.no("Codex reviews start fix runs only")
            if not inline:
                return self.no("Codex review has no findings")
            comments = self.api(f"repos/{self.repo}/issues/{number}/comments?per_page=100") or []
            rounds = sum(ROUND_MARK in (c.get("body") or "") for c in comments)
            if rounds >= self.max_rounds:
                return self.no("Codex round cap reached", notice_on=str(number),
                               notice=f"{ROUND_MARK.replace('round', 'cap')}Codex has reviewed this PR again after "
                                      f"{rounds} agent fix rounds, the most allowed (`AGENT_MAX_CODEX_ROUNDS`). "
                                      "A person needs to look at the remaining findings; a reviewer's comment "
                                      "starts another fix run.")
            return self.result(kind, issue, change, number, f"review {r['id']} by {login}", codex=True)
        if login.endswith("[bot]"):
            return self.no(f"review by {login}")
        if not (r.get("body") or "").strip() and not inline:
            return self.no("review with no comments (e.g. an approval)")
        if not self.can_write(login):
            return self.no(f"{login} has no write access")
        return self.result(kind, issue, change, number, f"review {r['id']} by {login}")


def main(argv=None):
    argv = argv or sys.argv[1:]
    if len(argv) != 1 or argv[0] not in ("plan", "build"):
        print("usage: agent_gate.py plan|build", file=sys.stderr)
        return 2
    with open(os.environ["GITHUB_EVENT_PATH"]) as f:
        event = json.load(f)
    repo = os.environ["GITHUB_REPOSITORY"]
    gate = Gate(os.environ["GITHUB_EVENT_NAME"], event, repo, os.environ.get("REPO_OWNER") or repo.split("/")[0],
                os.environ.get("AGENT_USERS", ""), os.environ.get("AGENT_MAX_CODEX_ROUNDS", ""))
    out = gate.decide(argv[0])
    print(json.dumps(out, indent=1))
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a") as f:
            for key, value in out.items():
                f.write(f"{key}={str(value).replace(chr(10), ' ')}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
