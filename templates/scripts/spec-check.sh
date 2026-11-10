#!/bin/bash
# Spec check for this branch (compared with origin/main). See "Specs and Workflows" in AGENTS.md.
# 1. Code changes must come with an OpenSpec change folder changed on the same branch, either active
#    (openspec/changes/<name>/) or archived (openspec/changes/archive/<date>-<name>/), holding
#    proposal.md, design.md, tasks.md and at least one specs/<capability>/spec.md, and a verification.md
#    from the verifier agent with a passing verdict.
# 2. Plan matches diff: every changed file must be named in design.md/tasks.md.
#    Files named there but not changed are listed as a warning.
# 3. Bug fixes (branches named fix/): each change folder has a failing-test.md. Its Commit: is on the
#    branch, comes before any production code change, changed only tests and the change folder, and the
#    recorded test files haven't changed since; or it says Commit: none with a Reason: line. See "Bug fixes" in AGENTS.md.
# 4. UI changes (files matching UI_FILES below): each change folder has a screenshots.md
#    from scripts/ui-screenshots.sh whose images exist, taken at a commit on the branch with no UI change
#    after it; or it says Screenshots: none with a Reason: line. See "UI changes" in AGENTS.md.
# 5. UI changes also need a mockups.md from scripts/ui-mockups.sh, first committed before the first commit
#    that changes a UI file, linking at least one mock-up, whose images exist and with a PNG pair for every mockups/*.html; or it says
#    Mock-up: none with a Reason: line. See "UI changes" in AGENTS.md.

# --- Configure for your repository -------------------------------------------------
# UI files (shell patterns) that need a mock-up and screenshots, and paths inside them to skip.
UI_FILES='<SharedUiProject>/*.razor <SharedUiProject>/*.css <WebProject>/*.razor <WebProject>/*.css'
UI_SKIP='*/wwwroot/lib/* */wwwroot/bootstrap/*'
# -----------------------------------------------------------------------------------

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
  if [ ! -f "${dir}verification.md" ]; then
    echo "Spec check failed: ${dir}verification.md is missing. Start the verifier agent with the change name (see \"Specs and Workflows\" in AGENTS.md)." >&2
    failed=1
  elif ! grep -qxE 'Verdict: (PASS|PASS WITH MANUAL CHECKS)' "${dir}verification.md"; then
    echo "Spec check failed: ${dir}verification.md has no passing verdict (Verdict: PASS or Verdict: PASS WITH MANUAL CHECKS). Fix the gaps it lists and run the verifier again." >&2
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

# UI changes need screenshots of the changed pages, taken after the last UI change on the branch.
# Split the patterns without expanding them against the files in the repo.
set -f; ui_files=($UI_FILES); ui_skip=($UI_SKIP); set +f
is_ui_file() {
  local pattern
  for pattern in "${ui_skip[@]}"; do
    case "$1" in $pattern) return 1 ;; esac
  done
  for pattern in "${ui_files[@]}"; do
    case "$1" in $pattern) return 0 ;; esac
  done
  return 1
}

ui_changes=$(while read -r file; do
  [ -n "$file" ] && is_ui_file "$file" && echo "$file"
done <<<"$code_changes")

if [ -n "$ui_changes" ]; then
  main_ref=$(git rev-parse --verify -q origin/main >/dev/null && echo origin/main || echo main)
  for dir in $change_dirs; do
    record="${dir}screenshots.md"
    if [ ! -f "$record" ]; then
      echo "Spec check failed: this branch changes UI files but $record is missing. Run scripts/ui-screenshots.sh <change-name> <routes> for the pages the change affects, or write Screenshots: none with a Reason: line (see \"UI changes\" in AGENTS.md)." >&2
      failed=1
      continue
    fi
    if grep -qE '^Screenshots: *none' "$record"; then
      if ! grep -qE '^Reason: *[^ ]' "$record"; then
        echo "Spec check failed: $record says Screenshots: none but has no Reason: line." >&2
        failed=1
      fi
      continue
    fi
    shas=$(grep -E '^Taken at:' "$record" | sed -E 's/^Taken at: *//; s/[ `].*//')
    if [ -z "$shas" ]; then
      echo "Spec check failed: $record has no Taken at: line; run scripts/ui-screenshots.sh again." >&2
      failed=1
    fi
    images=$(grep -oE '\]\(screenshots/[^)]+\)' "$record" | sed -E 's/^\]\(//; s/\)$//')
    while read -r image; do
      if [ -n "$image" ] && [ ! -f "$dir$image" ]; then
        echo "Spec check failed: $record links $image, which isn't in the change folder." >&2
        failed=1
      fi
    done <<<"$images"
    while read -r sha; do
      [ -z "$sha" ] && continue
      if ! git cat-file -e "$sha^{commit}" 2>/dev/null || ! git merge-base --is-ancestor "$sha" HEAD; then
        echo "Spec check failed: the Taken at: commit in $record ('$sha') is not on this branch. If the branch was rebased, take the screenshots again." >&2
        failed=1
        continue
      fi
      # ^main leaves out main's own commits, which a CI merge commit brings in.
      later=$(git log --no-merges --name-only --format= "$sha..HEAD" "^$main_ref" | sort -u | while read -r file; do
        [ -n "$file" ] && is_ui_file "$file" && echo "$file"
      done)
      if [ -n "$later" ]; then
        echo "Spec check failed: these UI files changed after the screenshots in $record were taken; take the screenshots again:" >&2
        sed 's/^/  /' <<<"$later" >&2
        failed=1
      fi
    done <<<"$shas"
  done
fi

# UI changes need a mock-up, committed on the branch before the first commit that changes a UI file.
if [ -n "$ui_changes" ]; then
  # First commit on the branch (oldest first) that changes a UI file; empty if they're all uncommitted.
  first_ui=$(git log --reverse --no-merges --name-only --format='@%H' "$main_ref..HEAD" | while read -r line; do
    case "$line" in
      (@*) sha=${line#@} ;;
      (*) [ -n "$line" ] && is_ui_file "$line" && { echo "$sha"; break; } ;;
    esac
  done)
  for dir in $change_dirs; do
    record="${dir}mockups.md"
    if [ ! -f "$record" ]; then
      echo "Spec check failed: this branch changes UI files but $record is missing. Draw the page with scripts/ui-mockups.sh and commit it with the proposal, before the code, or write Mock-up: none with a Reason: line (see \"UI changes\" in AGENTS.md)." >&2
      failed=1
      continue
    fi
    if grep -qE '^Mock-up: *none' "$record"; then
      if ! grep -qE '^Reason: *[^ ]' "$record"; then
        echo "Spec check failed: $record says Mock-up: none but has no Reason: line." >&2
        failed=1
      fi
      continue
    fi
    images=$(grep -oE '\]\(mockups/[^)]+\)' "$record" | sed -E 's/^\]\(//; s/\)$//')
    while read -r image; do
      if [ -n "$image" ] && [ ! -f "$dir$image" ]; then
        echo "Spec check failed: $record links $image, which isn't in the change folder." >&2
        failed=1
      fi
    done <<<"$images"
    if [ -z "$images" ] || ! ls "$dir"mockups/*.html >/dev/null 2>&1; then
      echo "Spec check failed: $record lists no rendered mock-ups. Draw the page with scripts/ui-mockups.sh --new, render it with scripts/ui-mockups.sh <change-name>, or write Mock-up: none with a Reason: line." >&2
      failed=1
    fi
    for page in "$dir"mockups/*.html; do
      [ -f "$page" ] || continue
      name=${page%.html}
      if [ ! -f "$name-desktop.png" ] || [ ! -f "$name-phone.png" ]; then
        echo "Spec check failed: $page has no rendered images; run scripts/ui-mockups.sh <change-name>." >&2
        failed=1
      fi
    done
    # Look under the active path too: after archiving, the file was first added at openspec/changes/<name>/.
    name=$(basename "$dir" | sed -E 's/^[0-9]{4}-[0-9]{2}-[0-9]{2}-//')
    first_mock=$(git log --reverse --format=%H "$main_ref..HEAD" -- "$record" "openspec/changes/$name/mockups.md" | head -1)
    if [ -z "$first_mock" ]; then
      echo "Spec check failed: $record isn't committed. Commit the mock-up before the code that changes UI files." >&2
      failed=1
    elif [ -n "$first_ui" ] && { [ "$first_mock" = "$first_ui" ] || ! git merge-base --is-ancestor "$first_mock" "$first_ui"; }; then
      echo "Spec check failed: $record was first committed in or after ${first_ui:0:7}, the first commit that changes a UI file. The mock-up comes with the proposal, in an earlier commit than the code." >&2
      failed=1
    fi
  done
fi

branch=${GITHUB_HEAD_REF:-$(git rev-parse --abbrev-ref HEAD)}
if [[ "$branch" == fix/* ]]; then
  for dir in $change_dirs; do
    record="${dir}failing-test.md"
    if [ ! -f "$record" ]; then
      echo "Spec check failed: $branch is a bug fix branch but $record is missing. Write the test that reproduces the bug, commit it on its own, and record it there (see \"Bug fixes\" in AGENTS.md)." >&2
      failed=1
      continue
    fi
    commit=$(grep -m1 -E '^Commit:' "$record" | sed -E 's/^Commit: *//; s/[ `].*//')
    if [ "$commit" = "none" ]; then
      if ! grep -qE '^Reason: *[^ ]' "$record"; then
        echo "Spec check failed: $record says Commit: none but has no Reason: line." >&2
        failed=1
      fi
      continue
    fi
    if [ -z "$commit" ] || ! git cat-file -e "$commit^{commit}" 2>/dev/null || ! git merge-base --is-ancestor "$commit" HEAD; then
      echo "Spec check failed: the Commit: in $record ('$commit') is not a commit on this branch. If the branch was rebased, update it to the new sha of the failing-test commit." >&2
      failed=1
      continue
    fi
    in_commit=$(git diff-tree --no-commit-id --name-only -r "$commit")
    outside=$(grep -vE '^[^/]+Tests/|^openspec/changes/' <<<"$in_commit")
    if [ -n "$outside" ]; then
      echo "Spec check failed: the failing-test commit $commit also changes files outside the test projects; commit the test on its own, before the fix:" >&2
      sed 's/^/  /' <<<"$outside" >&2
      failed=1
    fi
    # Compare from where the failing-test commit left main, not from $base: in CI, HEAD is a merge with
    # the latest main, and main's own newer changes aren't part of this branch.
    commit_base=$(git merge-base "$commit" origin/main 2>/dev/null || git merge-base "$commit" main 2>/dev/null)
    before=$(git diff --name-only --no-renames "$commit_base" "$commit^" 2>/dev/null | grep -vE '^[^/]+Tests/|^openspec/changes/')
    if [ -n "$before" ]; then
      echo "Spec check failed: production code changed before the failing-test commit $commit; the test must come first:" >&2
      sed 's/^/  /' <<<"$before" >&2
      failed=1
    fi
    tests=$(awk '/^Test files:/{on=1; next} on && /^- `/{print; next} on && NF{on=0}' "$record" | sed -E 's/^- `([^`]*)`.*/\1/')
    if [ -z "$tests" ]; then
      echo "Spec check failed: $record lists no Test files." >&2
      failed=1
      continue
    fi
    while read -r test; do
      if ! grep -qxF -- "$test" <<<"$in_commit"; then
        echo "Spec check failed: $test is listed in $record but isn't in the failing-test commit $commit." >&2
        failed=1
      elif [ -n "$(git diff --name-only "$commit" -- "$test")" ]; then
        echo "Spec check failed: $test changed after the failing-test commit $commit. The test proves the bug and must stay as it was; if it is wrong, ask the repo owner." >&2
        failed=1
      fi
    done <<<"$tests"
  done
fi

if [ $failed -ne 0 ]; then
  exit 1
fi
echo "Spec check passed: $(wc -l <<<"$code_changes" | tr -d ' ') changed file(s), all covered by $(echo $change_dirs)."
