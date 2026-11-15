# v2.7: a model per step

Each change goes through three steps that can run on different models:

| Step | What runs it | How to set its model |
|---|---|---|
| **Plan** | the first turn: the agent proposes the change | the model you start the session with (Claude `--model`, Codex `-m`) |
| **Build** | the turn after approval: apply, policy review, archive | the model of the turn that applies (switch models before approving) |
| **Verify** | the verifier subagent, with a fresh context | `model:` in `.claude/agents/verifier.md` (`inherit` uses the session's model); `model = "..."` in the Codex verifier agent file |

A cheaper model for some steps could cut cost; a stronger one for others could catch more. The harness evals ([docs/evals.md](evals.md)) let you measure that on your own tasks instead of guessing.

## Default: one model for every step

The kit's default is **Sonnet for every step, at effort `medium`** (`DEFAULT_MODEL` in `eval_run.py`, and `model: inherit` in the verifier). For Codex, use the model you normally work with for all three steps. The measurements below found no mix that beat it.

## Measuring your own

```bash
# One configuration: Opus plans, Haiku builds, Sonnet verifies
scripts/eval-run.sh --agent claude --plan-model opus --build-model haiku --verify-model sonnet --tasks smoke

# Several configurations in a row, waiting out usage limits (plan/build/verify each)
scripts/eval-configs.sh sonnet/sonnet/sonnet opus/sonnet/sonnet sonnet/haiku/opus
EVAL_TASKS=all scripts/eval-configs.sh sonnet/sonnet/sonnet opus/opus/opus
```

- `--plan-model`, `--build-model` and `--verify-model` each default to `--model`. The runner writes the verify model into the snapshot's verifier agent file before the agent starts; your repo's own file doesn't change.
- Each result line records all three models, and the results file is named after them (`<date>-<agent>-<plan>-<build>-<verify>-<effort>.jsonl`). The summary compares a run only with earlier runs of the same three models and effort.
- **Usage limits:** comparing several configurations on all tasks takes hours and will hit your plan's limits. When a limit or an API outage stops a task, the runner doesn't record it and exits with 75; `--run-id <id>` continues the same run. `eval-configs.sh` does this for you: it waits 30 minutes and tries again, up to a day. Don't delete result lines by hand: if a check misses a new kind of limit message, fix the check and rerun.
- **Run the full set before deciding.** A 5-task smoke set is enough to catch a broken harness, not to choose models.

## What we measured

On a production .NET API (20 tasks: 12 rebuild a removed use case, 4 replay a past change, 4 fix a planted bug), Claude Code at effort `medium`, Nov 2026:

| Plan / Build / Verify | Passed (all six checks) | Hidden tests passed | Minutes | Cost (API-equivalent) |
|---|---|---|---|---|
| **Sonnet / Sonnet / Sonnet** | **20/20** | 20/20 | 140 | **$30** |
| Opus / Sonnet / Sonnet | 19/20 | 19/20 | 149 | $56 |
| Opus / Opus / Opus | 18/20 | 19/20 | 177 | $67 |
| Opus / Haiku / Sonnet | 16/20 | 19/20 | 152 | $42 |
| Sonnet / Haiku / Sonnet | 11/20 | 19/20 | 155 | $23 |

Nine configurations ran on the 5-task smoke set first; these five were then run on all 20.

- **The code was right almost everywhere.** Every configuration passed the hidden tests on 19 or 20 tasks. The models differed in how well they followed the flow, not in the code they wrote.
- **An Opus planner doubled the cost and added no passes.** These tasks are ordinary feature work and bug fixes; Sonnet already plans them well.
- **Opus is more cautious.** In one task the verifier failed the change twice because it couldn't tell whether it was a feature or a bug fix, and Opus stopped to ask. That's reasonable with a person watching, and a failure in an unattended run.
- **A Haiku builder skips the flow.** Most Haiku failures were "verification.md is missing": it wrote working code but never started the verifier, and sometimes didn't commit. An Opus planner helped, but not enough.
- **The smoke set hid this.** On 5 tasks, Sonnet/Haiku/Opus and Opus/Haiku/Sonnet both passed 5/5, and Sonnet/Haiku/Sonnet 4/5.
- **One task was unfair.** Its request said "an empty value", but its hidden test sent a whitespace-only one, and four of five configurations failed on that test alone. A task's request has to state every case its hidden tests check.

These are one run per configuration on one codebase. Treat them as a starting point, and measure on your own tasks before changing your defaults, especially if your work is larger or more design-heavy than ours. Codex models weren't compared per step.
