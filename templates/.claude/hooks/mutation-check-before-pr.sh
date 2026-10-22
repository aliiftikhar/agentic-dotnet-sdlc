#!/bin/bash
# Claude Code PreToolUse hook for `gh pr create`: runs the mutation check first and
# blocks opening the PR until every mutant in changed UseCases/Services/Models code is killed.
output=$("$CLAUDE_PROJECT_DIR/scripts/mutation-check.sh" 2>&1)
if [ $? -ne 0 ]; then
  printf '%s\n\nFix the tests, rerun scripts/mutation-check.sh, then open the PR.\n' "$output" >&2
  exit 2
fi
exit 0
