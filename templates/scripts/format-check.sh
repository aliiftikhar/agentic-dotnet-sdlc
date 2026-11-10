#!/bin/bash
# C# whitespace check (see "Build, Test, Verify" in AGENTS.md). Rules are in .editorconfig.
#   scripts/format-check.sh          check the C# projects changed on this branch (compared with origin/main)
#   scripts/format-check.sh --all    check every C# project (CI)
#   scripts/format-check.sh --fix    reformat instead of checking (combine with --all for everything)
# Only the projects listed below are checked; EF migrations are excluded (generated, and protected).

set -u
repo=$(git rev-parse --show-toplevel) || exit 1
cd "$repo" || exit 1

fix=false
all=false
for arg in "$@"; do
  case "$arg" in
    --fix) fix=true ;;
    --all) all=true ;;
    *) echo "Usage: scripts/format-check.sh [--fix] [--all]" >&2; exit 2 ;;
  esac
done

# --- Configure for your repository -------------------------------------------------
# Project folders, each holding <folder>/<folder>.csproj
all_projects="<ApiProject> <UnitTestProject> <WebProject>"
EXCLUDE="<ApiProject>/Migrations"
# -----------------------------------------------------------------------------------

dotnet_bin=$(command -v dotnet || echo /usr/local/share/dotnet/dotnet)

if [ "$all" = true ]; then
  projects=" $all_projects"
else
  base=$(git merge-base HEAD origin/main 2>/dev/null || git merge-base HEAD main 2>/dev/null)
  if [ -z "$base" ]; then
    echo "Format check: can't find origin/main or main to compare against." >&2
    exit 1
  fi
  changed=$( { git diff --name-only --no-renames "$base"; git ls-files --others --exclude-standard; } \
    | grep -E '\.(cs|csproj)$' | cut -d/ -f1 | sort -u )
  projects=""
  for project in $all_projects; do
    grep -qx "$project" <<<"$changed" && projects="$projects $project"
  done
fi

if [ -z "${projects// /}" ]; then
  echo "Format check: no C# projects changed; nothing to check."
  exit 0
fi

failed=0
for project in $projects; do
  if [ "$fix" = true ]; then
    "$dotnet_bin" format whitespace "$project/$project.csproj" --exclude "$EXCLUDE" -v q || failed=1
  else
    output=$("$dotnet_bin" format whitespace "$project/$project.csproj" --exclude "$EXCLUDE" --verify-no-changes -v q 2>&1)
    if [ $? -ne 0 ]; then
      failed=1
      grep -E ' error [A-Z]+:' <<<"$output" | sed -E "s|^$repo/||; s| \[.*\]$||" | sort -u | head -20 >&2
    fi
  fi
done

if [ "$fix" = true ]; then
  [ "$failed" -eq 0 ] && echo "Format check: reformatted$projects." && exit 0
  echo "Format check: dotnet format failed." >&2
  exit 1
fi
if [ "$failed" -ne 0 ]; then
  echo "Format check failed: run scripts/format-check.sh --fix and commit the result." >&2
  exit 1
fi
echo "Format check passed:$projects."
