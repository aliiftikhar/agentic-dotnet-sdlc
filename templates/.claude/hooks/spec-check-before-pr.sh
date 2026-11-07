#!/bin/bash
# Claude Code PreToolUse hook for `gh pr create`: runs the spec check first and blocks opening the PR
# until the branch has an OpenSpec change and every changed file is named in its design or tasks.
# `if` in settings.json is best-effort and also fires on commands with $VAR, $(...) or pipes,
# so skip unless this Bash call really runs `gh pr create`.
input=$(cat)
grep -q 'gh pr create' <<<"$input" || exit 0
# The no-spec label is the owner's skip (see AGENTS.md); CI honours it too.
grep -qE '(--label|-l)[ =]+(\\?["'"'"'])?no-spec' <<<"$input" && exit 0
output=$("$CLAUDE_PROJECT_DIR/scripts/spec-check.sh" 2>&1)
if [ $? -ne 0 ]; then
  printf '%s\n\nFix the plan or the change, rerun scripts/spec-check.sh, then open the PR. If the change should skip this, ask the repo owner whether to open the PR with --label no-spec.\n' "$output" >&2
  exit 2
fi
exit 0
