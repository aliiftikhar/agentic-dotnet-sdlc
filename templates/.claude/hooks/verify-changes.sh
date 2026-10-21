#!/bin/bash
# Claude Code Stop hook: before Claude finishes a turn, build the projects it changed
# and run the unit tests. On failure it blocks once (exit 2) and hands the errors back
# to Claude to fix; it never blocks twice in a row, so it can't loop.

# --- Configure for your repository -------------------------------------------------
# "<regex for changed paths>=<project folder to build>"
BUILD_RULES=(
  '^(<SharedUiProject>|<WebProject>)/=<WebProject>'
  '^<AdminProject>/=<AdminProject>'
)
# Changed paths matching this run the unit tests (building the test project builds the code it tests)
TEST_RULE='^(<ApiProject>|<UnitTestProject>)/'
UNIT_TEST_PROJECT='<UnitTestProject>'
# -----------------------------------------------------------------------------------

input=$(cat)
repo=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
cd "$repo" || exit 0

dotnet_bin=$(command -v dotnet || echo /usr/local/share/dotnet/dotnet)
[ -x "$dotnet_bin" ] || exit 0

base=$(git merge-base HEAD origin/main 2>/dev/null || git merge-base HEAD main 2>/dev/null)
if [ -z "$base" ]; then
  printf '{"systemMessage": "Verify hook: no main branch to compare against, so the build and tests were not run."}\n'
  exit 0
fi

# --no-renames lists both the old and new path of a moved file, so both projects get built
changed=$( { git diff --name-only --no-renames "$base"; git ls-files --others --exclude-standard; } \
  | grep -E '\.(cs|razor|cshtml|csproj|props|targets)$' | sort -u )
[ -z "$changed" ] && exit 0

# Skip when nothing has changed since the last successful check
state=$( { git diff --no-renames "$base"; git ls-files --others --exclude-standard -z; \
  git ls-files --others --exclude-standard -z | xargs -0 cat 2>/dev/null; } | shasum | cut -d' ' -f1 )
stamp="$(git rev-parse --git-dir)/claude-verify-ok"
[ -f "$stamp" ] && [ "$(cat "$stamp")" = "$state" ] && exit 0

builds=()
for rule in "${BUILD_RULES[@]}"; do
  grep -qE "${rule%%=*}" <<<"$changed" && builds+=("${rule#*=}")
done
run_unit_tests=false
grep -qE "$TEST_RULE" <<<"$changed" && run_unit_tests=true

failures=""
for project in "${builds[@]}"; do
  output=$("$dotnet_bin" build "$project" 2>&1) || failures+="Build failed: $project
$(grep -E ' error [A-Z]+[0-9]+' <<<"$output" | sed 's/ \[.*\]$//' | sort -u | head -15)

"
done

if [ "$run_unit_tests" = true ]; then
  output=$("$dotnet_bin" build "$UNIT_TEST_PROJECT" 2>&1)
  if [ $? -ne 0 ]; then
    failures+="Build failed: $UNIT_TEST_PROJECT
$(grep -E ' error [A-Z]+[0-9]+' <<<"$output" | sed 's/ \[.*\]$//' | sort -u | head -15)

"
  else
    output=$("$dotnet_bin" test "$UNIT_TEST_PROJECT" --no-build 2>&1) || failures+="Unit tests failed:
$(grep -E '^\s*Failed |Failed!' <<<"$output" | head -15)

"
  fi
fi

if [ -z "$failures" ]; then
  echo "$state" > "$stamp"
  exit 0
fi

if grep -qE '"stop_hook_active" *: *true' <<<"$input"; then
  # Already blocked once this turn: tell the user instead of blocking again
  printf '{"systemMessage": "Verify hook: build or unit tests still failing after one fix attempt."}\n'
  exit 0
fi

printf 'The build or unit tests fail for the changes you made. Fix these before finishing:\n\n%s' "$failures" >&2
exit 2
