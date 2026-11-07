#!/bin/bash
# Spec check for this branch (compared with origin/main). See "Specs and Workflows" in AGENTS.md.
# 1. Code changes must come with an OpenSpec change folder changed on the same branch, either active
#    (openspec/changes/<name>/) or archived (openspec/changes/archive/<date>-<name>/), holding
#    proposal.md, design.md, tasks.md and at least one specs/<capability>/spec.md.
# 2. Plan matches diff: every changed file must be named in design.md/tasks.md.
#    Files named there but not changed are listed as a warning.

set -u
repo=$(git rev-parse --show-toplevel) || exit 1
cd "$repo" || exit 1

base=$(git merge-base HEAD origin/main 2>/dev/null || git merge-base HEAD main 2>/dev/null)
if [ -z "$base" ]; then
  echo "Spec check: can't find origin/main or main to compare against, so changed files are unknown." >&2
  exit 1
fi

changed=$( { git diff --name-only --no-renames "$base"; git ls-files --others --exclude-standard; } | sort -u )

# OpenSpec's own files and the change artifacts don't need to be planned.
is_openspec_file() {
  case "$1" in
    openspec/*|.claude/commands/opsx/*|.claude/skills/openspec-*|.agents/skills/openspec-*|.agents/skills/.openspec-target) return 0 ;;
    *) return 1 ;;
  esac
}

code_changes=$(while read -r file; do
  [ -n "$file" ] && ! is_openspec_file "$file" && echo "$file"
done <<<"$changed")

if [ -z "$code_changes" ]; then
  echo "Spec check: no code changes outside the spec artifacts; nothing to check."
  exit 0
fi

change_dirs=$( { grep -E '^openspec/changes/' <<<"$changed" | grep -v '^openspec/changes/archive/' | grep -oE '^openspec/changes/[^/]+/'
  grep -oE '^openspec/changes/archive/[^/]+/' <<<"$changed"; } | sort -u )

if [ -z "$change_dirs" ]; then
  echo "Spec check failed: this branch changes code but has no OpenSpec change." >&2
  echo "Run the OpenSpec propose step and commit its artifacts on this branch, or ask the repo owner to add the no-spec label." >&2
  exit 1
fi

failed=0
plan_files=""

for dir in $change_dirs; do
  for doc in proposal.md design.md tasks.md; do
    if [ ! -f "$dir$doc" ]; then
      echo "Spec check failed: $dir$doc is missing." >&2
      failed=1
    fi
  done
  if [ -z "$(find "${dir}specs" -name spec.md 2>/dev/null)" ]; then
    echo "Spec check failed: ${dir}specs/ has no spec.md." >&2
    failed=1
  fi
  plan_files="$plan_files ${dir}design.md ${dir}tasks.md"
done

# File paths named in the plan, e.g. `MyApi/UseCases/GetOrder/GetOrderHandler.cs` or `Program.cs`.
plan_text=$(cat $plan_files 2>/dev/null)
planned=$(printf '%s\n' "$plan_text" \
  | grep -oE '[A-Za-z0-9_.@/-]+\.(cs|razor|cshtml|css|js|ts|json|csproj|sh|yml|yaml|md|html|sql|xml|props|targets)' \
  | sed 's|^\./||' | sort -u)

# A full path counts whatever its extension, so `MyApi/Dockerfile` works; a bare name like `Program.cs` needs a known one.
is_planned() {
  grep -qF -- "$1" <<<"$plan_text" && return 0
  while read -r path; do
    [ -z "$path" ] && continue
    case "$1" in
      "$path"|*/"$path") return 0 ;;
    esac
  done <<<"$planned"
  return 1
}

unplanned=$(while read -r file; do
  is_planned "$file" || echo "$file"
done <<<"$code_changes")

if [ -n "$unplanned" ]; then
  echo "Spec check failed: these changed files are not named in design.md or tasks.md:" >&2
  sed 's/^/  /' <<<"$unplanned" >&2
  echo "Add them to design.md/tasks.md with the reason, or revert the change." >&2
  failed=1
fi

is_changed() {
  while read -r file; do
    case "$file" in
      "$1"|*/"$1") return 0 ;;
    esac
  done <<<"$changed"
  return 1
}

not_changed=$(grep -vE '^openspec/|\.md$' <<<"$planned" | while read -r path; do
  [ -n "$path" ] && ! is_changed "$path" && echo "$path"
done)

if [ -n "$not_changed" ]; then
  echo "Spec check warning: these files are named in the plan but not changed (fine if they were only referenced):"
  sed 's/^/  /' <<<"$not_changed"
fi

if [ $failed -ne 0 ]; then
  exit 1
fi
echo "Spec check passed: $(wc -l <<<"$code_changes" | tr -d ' ') changed file(s), all covered by $(echo $change_dirs)."
