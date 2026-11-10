#!/bin/bash
# Protected-paths check for this branch (compared with origin/main). See "Git Workflow" in AGENTS.md.
# Agents change these paths only when the repo owner asked; the owner approves the PR with the
# `protected-ok` label, which makes CI skip this check.
# Keep this list in sync with the "ask" rules in .claude/settings.json.
# --- Configure for your repository -------------------------------------------------
protected=(
  .github/
  .githooks/
  .claude/settings.json
  .claude/hooks/
  .claude/agents/
  .codex/
  .agents/agents/
  scripts/
  '<ApiProject>/Migrations/'
)
# -----------------------------------------------------------------------------------

set -u
repo=$(git rev-parse --show-toplevel) || exit 1
cd "$repo" || exit 1

base=$(git merge-base HEAD origin/main 2>/dev/null || git merge-base HEAD main 2>/dev/null)
if [ -z "$base" ]; then
  echo "Protected-paths check: can't find origin/main or main to compare against." >&2
  exit 1
fi

changed=$( { git diff --name-only --no-renames "$base"; git ls-files --others --exclude-standard; } | sort -u )

is_protected() {
  local path
  for path in "${protected[@]}"; do
    case "$1" in
      "$path"*) return 0 ;;
    esac
  done
  return 1
}

hits=$(while read -r file; do
  [ -n "$file" ] && is_protected "$file" && echo "$file"
done <<<"$changed")

if [ -n "$hits" ]; then
  echo "Protected-paths check failed: this branch changes files that need the repo owner's approval:" >&2
  sed 's/^/  /' <<<"$hits" >&2
  echo "If the owner asked for this change, they approve it by adding the protected-ok label to the PR. Agents never add it." >&2
  exit 1
fi
echo "Protected-paths check: no protected files changed."
