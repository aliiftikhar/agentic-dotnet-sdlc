# v2.8: what each change cost

Every change goes through the same steps: plan, build, verify, policy review, archive, then PR and review. `scripts/cost-report.sh <change-name>` tells you what each step cost, on which model, and the total, from the logs Claude Code and Codex already write on your machine. Nothing is sent anywhere, and no conversation text reaches the report.

```bash
scripts/cost-report.sh add-order-note          # on the change's branch, after archive
scripts/cost-report.sh add-order-note --print  # print only, don't write cost.md
scripts/cost-report.sh add-order-note --branch feat/order-note   # from another branch
```

It writes `cost.md` in the change folder and prints the table for the PR's **Cost** section:

| Step | Agent | Model | Input | Cache write | Cache read | Output | Cost |
|---|---|---|---:|---:|---:|---:|---:|
| Plan | Claude Code | claude-opus-5-5 | 92 | 261,088 | 5,644,359 | 48,200 | $4.18 |
| Build | Claude Code | claude-opus-5-5 | 164 | 130,733 | 20,699,130 | 71,618 | $6.62 |
| Verify | Claude Code | claude-opus-5-5 | 56 | 187,541 | 1,378,218 | 20,296 | $1.62 |
| Policy review | Claude Code | claude-opus-5-5 | 16 | 7,758 | 1,943,431 | 5,814 | $0.57 |
| Archive | Claude Code | claude-opus-5-5 | 32 | 20,017 | 4,556,606 | 8,166 | $1.23 |
| PR and review | Claude Code | claude-opus-5-5 | 58 | 16,000 | 7,349,788 | 10,605 | $1.81 |
| Other | Claude Code | session overhead (auto-mode checks, summaries) | | | | | $1.38 |
| **Total** | | | **418** | **623,137** | **41,571,532** | **164,699** | **$17.41** |

That's a real medium-sized feature from a production .NET codebase (about 1,800 lines with tests, one plan revision, two verifier runs). The report's total matches the $17.41 Claude Code itself recorded for the session.

## How it works

- **Where the data comes from.** Claude Code writes every response's model, token usage and git branch to `~/.claude/projects/<repo>/<session>.jsonl`, and each subagent to its own file. Codex writes running token totals and the branch to `~/.codex/sessions/`. The report reads only those fields, plus the step markers below.
- **Steps.** The flow already leaves markers in the logs: the `/opsx:` and `$openspec-` steps (explore, propose and update are Plan, apply is Build, then archive), the `policy-review` skill, and the verifier subagent (Verify). Work after archive is PR and review. Other subagents count toward the step that started them. Work on the branch with no marker, such as a later session fixing review comments, gets its step from when it ran.
- **Which work belongs to the change.** Work on the change's branch, plus OpenSpec steps that name the change on `main` (the propose step usually runs before the branch exists). Another change in the same session isn't counted.
- **Prices.** `scripts/model-prices.json`, per million tokens per model, with cache write and read rates and a date. A model with no price shows its tokens and "no price". Add Codex, Copilot or other models with their published rates.
- **Other.** Claude Code's own session total includes calls that aren't in the transcript (auto-mode checks, summaries), about 8% in the example. The report adds the difference as one row, shared out by the change's part of the session.

## What it doesn't measure

- **It's an estimate at API prices, not your bill.** On a subscription, it's what the same tokens would cost on the API.
- **It can't see some work.** Sessions started in another folder (if you drive the repo from elsewhere), the AI reviewer on GitHub (Codex's review exposes no usage) and GitHub Actions minutes don't show up. The report says so at the bottom.
- **Agents running in CI** need their usage added to the same file. The format is agent-neutral for that reason.

## Setup

1. Copy `templates/scripts/cost-report.sh`, `cost_report.py`, `model-prices.json` and `tests/test_cost_report.py` into `scripts/`.
2. Check the prices in `model-prices.json` against your provider's current rates and update the date.
3. Add the workflow step and the "Cost report" section from `templates/AGENTS.md`, and the Cost section from the PR template.
4. Run `python3 -m unittest discover scripts/tests`, then try it on a change you've already archived (`--branch` with its branch name).

## Lessons from building it

- **Check your numbers against the tool's own.** Pricing every response from the logs and comparing with the session total Claude Code records caught a missing 8% (the overhead row) and confirmed the cache rates: 5-minute writes at 1.25× input, 1-hour writes at 2×, reads at 0.1×. Output tokens already include thinking.
- **Most tokens are cache reads, but cost follows output and cache writes.** In the example, 98% of the tokens were cache reads, at about 48% of the cost.
- **Build is the biggest step, but not most of it.** Planning (with one revision round) was a quarter of the cost, and everything after build (verify, policy review, archive, PR) nearly another third.
- **Logs have traps.** One response is written as several lines; Codex logs the `AGENTS.md` it injects as a user message, examples of `$openspec-...` included; tool notices look like user prompts. The AI reviewer found 11 issues like these over five rounds and a final read-through found four more; about half would have given wrong numbers in normal use.
