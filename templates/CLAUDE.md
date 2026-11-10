@AGENTS.md

## Claude Code

All project instructions live in `AGENTS.md`, which Codex and other coding agents also read. Add or change instructions there, not here. Only Claude-specific notes belong in this file.

A Stop hook (`.claude/hooks/verify-changes.sh`) builds the projects you changed, runs the unit tests and checks C# formatting when you finish a turn. If it reports failures, fix them before finishing.

The `verifier` subagent (`.claude/agents/verifier.md`) is the Verify step in `AGENTS.md`: start it with the Agent tool and only the change name.

Two PreToolUse hooks run before `gh pr create` and block the PR until they pass:
- `.claude/hooks/spec-check-before-pr.sh` runs `scripts/spec-check.sh`: the branch needs an OpenSpec change, and every changed file must be named in its `design.md` or `tasks.md`. It is skipped when the command has `--label no-spec`, which you add only when the repo owner says the change is no-spec.
- `.claude/hooks/mutation-check-before-pr.sh` runs `scripts/mutation-check.sh` and blocks until every mutant in changed code is killed.

A PreToolUse hook (`.claude/hooks/protect-failing-test.sh`) blocks edits to the test files recorded in an active change's `failing-test.md` (see "Bug fixes" in `AGENTS.md`). Make the fix in production code; if the test is wrong, ask the repo owner.

Permission rules in `.claude/settings.json` deny merging PRs, starting workflows (deploys) and skipping git hooks, and ask the owner before you edit a protected path (see "Git Workflow" in `AGENTS.md`). The `ask` list must match `scripts/protected-paths.sh`.
