# Agent runs from issues

Label an issue `agent:plan` and Claude Code, running in GitHub Actions, takes it through the same flow you'd drive on your machine: it writes the OpenSpec plan as a PR for you to review, builds once you merge that plan, verifies, opens the PR into `main`, and fixes review comments. You review and merge; you never type a prompt.

Working on your machine doesn't change. Both ways use the same `AGENTS.md`, skills, hooks and checks; see the [SDLC map](sdlc-map.md).

## How a change goes through

```
Issue ──label agent:plan──▶ plan run ──▶ plan PR (agent/<n>-<slug>-plan → agent/<n>-<slug>)
                                              │  you comment ──▶ revise run ──┐
                                              │◀──────────────────────────────┘
                                              ▼  you merge the plan PR = approval
                                         build run: apply, tests, verifier, policy review,
                                         screenshots, archive, cost report
                                              ▼
                                         PR into main ──▶ CI + Codex review (asked from your account)
                                              │  review comments or Codex findings ──▶ fix run ──┐
                                              │◀────────────────────────────────────────────────┘
                                              ▼
                                         you merge
```

1. **Label.** An agent user adds `agent:plan` to an issue an agent user opened. The workflow creates `agent/<issue>-<slug>` (the build branch) from `main`, and `agent/<issue>-<slug>-plan` from it. The slug is the first five words of the title and is also the OpenSpec change name.
2. **Plan PR.** The agent writes the proposal, design, tasks and spec deltas (and mock-ups for UI changes) and opens a PR from the plan branch into the build branch, with a summary, open questions, its confidence and the cost so far.
3. **Revise.** Each comment or review on the plan PR starts a revision run, which updates the plan, pushes and replies.
4. **Approve by merging.** Merging the plan PR starts the build run. It updates the build branch from `main`, then applies, verifies, runs the policy review, takes screenshots for UI changes, archives, records the cost and opens the PR into `main`. A workflow step then posts `@codex review` from your account.
5. **Fix.** Review comments on that PR start fix runs, and so does a Codex review with findings (capped per PR). A comment that a check failed is enough: fix runs can read CI logs. You merge.

## Files

| Path | What it is |
|------|------------|
| `templates/.github/workflows/agent-plan.yml` | Label → branches and plan PR; comments and reviews on the plan PR → revision runs |
| `templates/.github/workflows/agent-build.yml` | Plan PR merged → build run and PR into `main`; comments, reviews and Codex findings → fix runs; asks Codex to review with your token |
| `templates/.github/agent-prompts/` | What each run is told: `frame.md` (rules for every run), `plan.md`, `revise.md`, `build.md`, `fix.md` |
| `templates/scripts/agent_gate.py`, `templates/scripts/tests/test_agent_gate.py` | Decides from the GitHub event whether a run starts, and what it works on |
| `templates/scripts/cost_report.py` | `--record-ci`: a run records its own token usage in the change's `ci-usage.jsonl`; the report shows those lines as "Claude Code (CI)" rows |
| `templates/scripts/protected-paths.sh` | Also flags new or changed NuGet packages, which need `protected-ok` |
| `templates/docs/threat-model.md` | What could go wrong with agents in your repo, and what stops it; the policy review checks harness changes against it |

## Setup

1. Copy the files above and the "Agent runs from issues" section of `templates/AGENTS.md`. In `frame.md`, replace `<ApiProject>`.
2. Run `claude setup-token` in a terminal and add the token as the repo secret `CLAUDE_CODE_OAUTH_TOKEN`. Runs use your Claude subscription.
3. Install the Claude GitHub App on the repo (github.com/apps/claude, only this repository). Don't use `/install-github-app`: it adds its own workflow.
4. Create the `agent:plan` label.
5. Create a fine-grained personal access token for this repo only, with pull requests read and write and an expiry, and add it as `CODEX_REVIEW_TOKEN`. Without it, runs still work but you ask Codex for reviews yourself.
6. Optional repo variables: `AGENT_USERS` (comma-separated logins allowed to label and approve; the repo owner when unset) and `AGENT_MAX_CODEX_ROUNDS` (default 3).
7. Fill in `docs/threat-model.md` for your repo, then try a small, clearly scoped issue first.

## Why it's shaped this way

- **A plan PR, merged as the approval.** Reviewing a plan is cheaper than reviewing code built on a wrong plan, and a PR gives line comments, a history and a clear "approve" action (the merge). Plan-first gates are the common pattern for agents that work from issues.
- **Gates on GitHub logins, never email.** Labels and plan merges by `AGENT_USERS`; comments and reviews by anyone with write access; Codex only with findings and within the round cap. The agent's own comments never start a run.
- **One run per issue.** GitHub keeps only one waiting run per concurrency group and drops the others, so each run handles every comment that has no reply yet, not just the one that started it.
- **Same rules as local.** The prompts point at `AGENTS.md` rather than repeating it, so one change to the rules covers both ways of working.

## Lessons learned

- **Codex acts only for accounts connected to Codex.** It doesn't review PRs opened by the Claude app on its own, and it answers `@codex review` from `claude[bot]` with "create a Codex account". The request has to come from your account, hence `CODEX_REVIEW_TOKEN`.
- **Auto mode treats PR text as data.** A comment asking the agent to post something for another bot was denied. Instructions that must be followed belong in the prompt files, not in comments.
- **The action revokes its app token when it ends,** so pushes made after it wouldn't start CI. The agent records its cost and pushes itself; the run's last few turns aren't counted.
- **PRs opened by `claude[bot]` count as untrusted** to the action, which then blocks build and test commands. The workflows set `restrict_untrusted_prs: "false"`; the gate script decides who can start a run.
- **Fix runs must run the checks themselves.** The spec-check hook fires on `gh pr create`, which only build runs call. A fix run that skipped it pushed a red PR, and a failed check starts no run, so the fix prompt runs the format and spec checks before pushing.
- **Give each token only what its step needs.** `CODEX_REVIEW_TOKEN` has pull requests access only, so reading the branch through the API with it returned 403 and Codex wasn't asked again. The tip is read in its own step with the job token.
- **`gh` in the Claude step uses the app's token,** so `actions: read` on the job alone doesn't let the agent read CI logs. `additional_permissions: actions: read` turns on the action's CI tools, which use the job's token.
- **Any workflow on a branch can read the repo's secrets.** Check whether the Claude GitHub App has the Workflows permission; see T2 in the threat model.
- **Measured on the source project:** three small issues, from label to PR into `main`, cost $0.49, $0.66 and $1.05 in API-equivalent tokens on Sonnet. A plan run cost about $0.17 to $0.19, a revision $0.12 to $0.15, and a build run $0.30 to $0.71.
