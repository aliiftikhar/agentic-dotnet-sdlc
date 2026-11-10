#!/bin/bash
# Claude Code PreToolUse hook for file edits: blocks changes to the test files a bug fix recorded in
# an active openspec/changes/<name>/failing-test.md (see "Bug fixes" in AGENTS.md). The test proves
# the bug, so the fix goes in production code. Bash edits aren't seen here; scripts/spec-check.sh catches those.
input=$(cat)
file=$(grep -oE '"file_path" *: *"[^"]*"' <<<"$input" | head -1 | sed -E 's/.*: *"([^"]*)"/\1/')
[ -z "$file" ] && exit 0
file=${file#"$CLAUDE_PROJECT_DIR"/}

for record in "$CLAUDE_PROJECT_DIR"/openspec/changes/*/failing-test.md; do
  [ -f "$record" ] || continue
  locked=$(awk '/^Test files:/{on=1; next} on && /^- `/{print; next} on && NF{on=0}' "$record" \
    | sed -E 's/^- `([^`]*)`.*/\1/')
  while read -r path; do
    if [ -n "$path" ] && [ "$file" = "$path" ]; then
      echo "Blocked: $path is the failing test recorded in ${record#"$CLAUDE_PROJECT_DIR"/}. It proves the bug, so make the fix in production code without changing it. If the test itself is wrong, stop and ask the repo owner." >&2
      exit 2
    fi
  done <<<"$locked"
done
exit 0
