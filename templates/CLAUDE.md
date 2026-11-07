@AGENTS.md

## Claude Code

All project instructions live in `AGENTS.md`, which Codex and other coding agents also read. Add or change instructions there, not here. Only Claude-specific notes belong in this file.

A Stop hook (`.claude/hooks/verify-changes.sh`) builds the projects you changed and runs the unit tests when you finish a turn. If it reports failures, fix them before finishing.

Two PreToolUse hooks run before `gh pr create` and block the PR until they pass:
- `.claude/hooks/spec-check-before-pr.sh` runs `scripts/spec-check.sh`: the branch needs an OpenSpec change, and every changed file must be named in its `design.md` or `tasks.md`. It is skipped when the command has `--label no-spec`, which you add only when the repo owner says the change is no-spec.
- `.claude/hooks/mutation-check-before-pr.sh` runs `scripts/mutation-check.sh` and blocks until every mutant in changed code is killed.
