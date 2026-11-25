# Threat model: agents in the SDLC

What could go wrong now that AI agents plan, build, review and fix code in this repo, and what stops it. Scope: the agent harness (local agents, CI agent runs, review loop, tokens). The app's own security is covered per change by the `policy-review` skill.

Last reviewed: <date>. Review it whenever `.github/`, `.claude/`, `.agents/`, `.codex/`, `scripts/` or the agent sections of `AGENTS.md` change; the `policy-review` skill checks harness changes against it.

How to use this template: go through each row in your repo, set the status, and write your real gaps. Mark a control ✅ only where a real run or PR showed it working, and link that PR.

Status: ✅ control seen working · ⚠️ control exists but untested or partial · ❌ open gap.

## What's worth protecting

- **`main` and the deployed apps** (<list them>). Deploys should run only when the owner starts them.
- **Secrets:** deploy credentials, `CLAUDE_CODE_OAUTH_TOKEN`, `CODEX_REVIEW_TOKEN` (acts as the owner on this repo's PRs), and any keys in committed settings files.
- **Personal data** in production. Agents should have no direct access; CI uses test data.
- **The guard rails themselves:** `AGENTS.md`, hooks, deny rules, check scripts, workflows.
- **Plan usage:** CI runs use the owner's Claude subscription; Codex uses the owner's ChatGPT plan.

## Who and what can reach an agent

- The owner (labels, comments, merges), anyone with write access (comments and reviews start fix runs), Codex (reviews with findings start fix runs).
- Text the agent reads: issues, PR comments and reviews, CI logs, code and dependencies.
- Tools and packages: NuGet, npm (OpenSpec CLI, Playwright), GitHub Actions from the marketplace.

## Threats

| # | Threat | How it would happen | Controls in this kit | Status | Check in your repo |
|---|---|---|---|---|---|
| T1 | Prompt injection | An issue, comment, review or CI log tells the agent to do something else ("push to main", "print the secrets") | `scripts/agent_gate.py`: only `AGENT_USERS` start plans and builds, only write access starts fix runs, the agent's own comments never do; the prompts treat issue, comment and log text as data; auto mode in CI | | Who has write access: they are trusted fully |
| T2 | Agent weakens its own guard rails, or runs its own workflow | Edits workflows, hooks, deny rules, check scripts or agent definitions; or adds or changes a workflow file on its branch | `protected-paths` check needs `protected-ok`; `ask` rules in `.claude/settings.json` (denied in CI); a workflow's own `GITHUB_TOKEN` can never push workflow changes | | **Any workflow on a branch can read the repo's secrets**, and pushes, reviews and plan merges run the branch's copy of a workflow. If the Claude GitHub App has the **Workflows** permission, an agent push that adds or edits `.github/workflows/` is accepted and runs before anyone reviews it. The protected-paths check only flags it on PRs into `main`; plan PRs get no checks |
| T3 | Supply chain | Agent adds a made-up or typosquatted package; a GitHub Action or npm tool is compromised | New or changed `PackageReference` needs `protected-ok`; OpenSpec CLI and Playwright pinned to exact versions | | Actions pinned by tag (`@v1`, `@v4`) rather than commit SHA; no vulnerable-package check (`dotnet list package --vulnerable`) |
| T4 | Token misuse | A step or agent leaks or misuses a CI token | `CODEX_REVIEW_TOKEN` is fine-grained and only one step gets it, posting fixed text; that step holds no other token (the branch tip is read in the step before, with the job token); the action's app token is revoked when it ends; comment-triggered runs use workflows from `main`; agent jobs don't reference deploy secrets | | Review-triggered and plan-merge runs use the branch's workflow (T2); deploy secrets in the same repo can be read by any workflow |
| T5 | Agent pushes to `main`, merges or deploys | A wrong or injected instruction | `AGENTS.md` forbids it; deny rules for `gh pr merge`, `gh workflow run`, `gh run rerun`; git hooks block pushes to `main` locally | | **Is `main` protected?** Branch protection and rulesets need GitHub Pro (or a public repo, or an organisation plan) for private repos. Without them, nothing technical stops an agent token with `contents: write` pushing to `main` in CI |
| T6 | Secrets or personal data reach an AI provider | Agents read files, logs and issues and send them to the model provider as context | Issues must not contain personal data; CI uses test settings; Actions masks secrets in logs; `policy-review` per change | | **Do committed settings files (`appsettings*.json`) hold real keys?** Every agent session can read them. Move them to a secret store and rotate them |
| T7 | Runaway runs and cost | A loop of runs, or a run that never ends | Gate; one run per issue; `--max-turns`; job timeouts; Codex rounds capped (`AGENT_MAX_CODEX_ROUNDS`); every run records its cost | | Spending caps beyond your plans' own limits |
| T8 | Plausible but wrong code | The agent misreads the issue or misses a case | Tests, mutation check, verifier, policy review, Codex review, the owner reviews every plan and PR and merges | | Everything ends at the owner's review; don't turn on auto-merge without written risk rules |
| T9 | Untrusted MCP servers or tools | A malicious MCP server gets the agent's context or tools | CI passes no MCP config, so only the action's own GitHub and CI tools run | | MCP servers in local sessions |

## Open actions, most important first

1. <Your gaps from the table, in order.>
