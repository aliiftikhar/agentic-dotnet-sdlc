# v2.6: harness evals

The harness is everything in this kit that steers a coding agent: `AGENTS.md`, skills, hooks, the verifier and the check scripts. When you change it, you're guessing whether the agents now do better or worse work. Harness evals replace the guess with a number: the same real tasks, run through the full loop, scored the same way, before and after the change.

- **Real tasks from your own repo,** cut from code and tests you already have:
  - **remove:** a use case is deleted and the agent rebuilds it from a ticket-style request;
  - **replay:** a past change is undone and the agent redoes it;
  - **bugfix:** a one-line bug is put in and the agent fixes it test-first.
- **Your existing tests are the answer key.** They're taken out before the agent starts and put back afterwards ("hidden tests").
- **The agent runs the normal flow unchanged:** propose, then an automatic approval, then apply, verifier, policy review and archive. There's no "eval mode", so what's measured is the harness you actually use.
- **Each task is scored on six checks:** the work is committed on a branch, unit tests pass, the spec check passes, the mutation check passes, the format check passes, and the hidden tests pass.

## Setup

1. Copy `templates/scripts/eval-run.sh`, `templates/scripts/eval_run.py`, `templates/evals/` and the "Evals" section of `templates/AGENTS.md`. Fill in the configure block at the top of `eval_run.py`: API and test project folders, where use cases and repositories live, and the default models. You need Python 3 (standard library only) and the `claude` and/or `codex` CLIs, signed in by you.
2. Add to `.gitignore`:
   ```
   evals/results/logs/
   __pycache__/
   ```
3. Write tasks in `evals/tasks/`. See `templates/evals/tasks/README.md` and the [examples](examples/evals/). Start with about 3 of each kind, from use cases with good handler tests.
4. Check them with no agent, for free:
   ```bash
   scripts/eval-run.sh --check
   ```
   Each task's answer key must pass on `main` and fail after setup. Fix or replace any task that doesn't.
5. Pick a smoke set of about 5 tasks covering each kind and size, in `evals/sets/smoke.txt`.
6. Run a first baseline on the smoke set with each agent you use, and commit the results:
   ```bash
   scripts/eval-run.sh --agent claude --tasks smoke
   scripts/eval-run.sh --agent codex --tasks smoke
   ```

## How a run works

For each task, the runner:
1. Copies `main` (or `--ref <branch>`) with `git archive` into a temporary folder.
2. Reads the hidden tests, applies the task's setup and deletes `evals/`.
3. Starts a **new git repository** with one commit and no remote, and turns on the git hooks.
4. Gives the agent the request headless, and stops it after propose. It records whether the agent stopped on its own.
5. Resumes the same session with "Approved. Apply it and finish the change up to the archive…".
6. Runs the six checks, then deletes the folder. `--keep` keeps it for a look.

Each task gets one JSON line in `evals/results/<date>-<agent>-<model>-<effort>.jsonl`. The line holds:
- the six checks and whether the task passed;
- minutes, tokens, and cost when the CLI reports it;
- the branch the agent used, whether it left anything uncommitted, and how many times the verifier said FAIL;
- whether a plan usage limit cut the run short.

The summary compares the run with the previous one at the **same agent, model and effort**.

## Why it's shaped this way

- **Tasks come from your repo, not a public benchmark.** Public benchmarks don't use your `AGENTS.md`, skills, hooks or checks, so they can't tell you whether your harness change helped. The answer keys cost nothing, because you already wrote those tests.
- **The approval is automatic, but the flow isn't changed.** The agent gets the same instructions as in normal work. Whether it stops after propose is itself measured.
- **The snapshot is a new repository, not a squashed one.** After a squash, the original commit stays in the reflog and the object store. `git show HEAD@{2}:<test file>` then recovers the answer key. `--check` fails if any extra git objects or reflog entries remain.
- **Remove tasks can fail by not compiling.** When the agent doesn't build to the stated contract, the hidden tests don't compile. That's recorded as `compile`, separate from wrong behaviour.
- **Fixed model and effort defaults.** Without them, a run picks up whatever the owner's CLI is set to, and the results can't be compared.
- **Only the owner starts a run.** It uses the owner's plans. Agents suggest a run after a harness change.

## Codex and Claude Code specifics

- **Claude Code:** `claude -p --output-format json --permission-mode acceptEdits --allowedTools <list>`, then `--resume <session_id>`. The allow-list covers `dotnet`, `git`, `scripts/*`, `openspec`, `npx` and read-only shell commands. The repo's deny and ask rules still apply. Cost and tokens come from the JSON.
- **Codex:** `codex exec --json -C <folder>`, then `codex exec resume <thread_id>`. Both run with the `workspace-write` sandbox, network on and `approval_policy="never"`. The extra writable roots are the snapshot's `.git`, the NuGet and .NET folders, and the system temp folder. Codex reports tokens but not cost.

## Lessons from using this on a real codebase

- **Writing tasks finds weak tests.** One past change couldn't be replayed because its test passed with or without the change. One realistic bug couldn't be used because no test caught it. Both are real test gaps, found before any agent ran.
- **The agents find real product bugs.** While fixing a planted bug, an agent pointed out a separate, real bug in the same area.
- **Codex's sandbox keeps `.git` read-only by default.** On the first Codex run it couldn't branch or commit. In one task it worked around this by making its own writable copy. The snapshot's `.git` is now a writable root.
- **Check your CLI's own defaults.** A Codex config set to maximum reasoning effort used up the plan's limit in three tasks, at 15 to 24 minutes each. At `medium`, Codex took about the same time per task as Claude Sonnet.
- **A run that does nothing can pass most checks.** The spec and mutation checks compare a branch with `main`. On `main` with no commits there's nothing to check, so they pass. Hence the `committed` check.
- **The AI reviewer found the answer-key leak** described above, on the PR that added the runner.
- **Agents add things nobody asked for.** One agent added an ownership check to a handler. That changed the constructor the request specified, so the hidden tests didn't compile. The contract in the request is what keeps remove tasks scorable.
- **First baseline:** 5 smoke tasks per agent, about 40 minutes per run. Claude Sonnet passed 5/5 for about $7 API-equivalent; Codex at `medium` passed 4/5. Five tasks is a small sample, so treat one smoke run as "did I break something?". Trust a trend only when it shows on the full set or on repeated runs.
