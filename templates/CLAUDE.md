@AGENTS.md

## Claude Code

All project instructions live in `AGENTS.md`, which Codex and other coding agents also read. Add or change instructions there, not here. Only Claude-specific notes belong in this file.

A Stop hook (`.claude/hooks/verify-changes.sh`) builds the projects you changed and runs the unit tests when you finish a turn. If it reports failures, fix them before finishing.

A PreToolUse hook (`.claude/hooks/mutation-check-before-pr.sh`) runs `scripts/mutation-check.sh` before `gh pr create` and blocks the PR until every mutant in changed code is killed.
