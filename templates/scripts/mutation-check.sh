#!/bin/bash
# Mutation check for code changed on this branch (compared with origin/main or main).
# Runs Stryker.NET only on changed files in the configured folders and passes when every
# mutant in that changed code is killed: 0 survived and 0 uncovered.
# Required before opening a PR that touches those folders (see AGENTS.md).

# --- Configure for your repository -------------------------------------------------
SOURCE_PROJECT='<ApiProject>'           # folder of the project Stryker mutates
UNIT_TEST_PROJECT='<UnitTestProject>'   # folder containing stryker-config.json
MUTATED_FOLDERS='UseCases|Services|Models'
# -----------------------------------------------------------------------------------

set -u
repo=$(git rev-parse --show-toplevel) || exit 1
cd "$repo" || exit 1
dotnet_bin=$(command -v dotnet || echo /usr/local/share/dotnet/dotnet)

base=$(git merge-base HEAD origin/main 2>/dev/null || git merge-base HEAD main 2>/dev/null)
if [ -z "$base" ]; then
  echo "Mutation check: can't find origin/main or main to compare against, so changed files are unknown." >&2
  exit 1
fi

source_regex=$(sed 's/\./\\./g' <<<"$SOURCE_PROJECT")
changed=$( { git diff --name-only --no-renames "$base"; git ls-files --others --exclude-standard; } \
  | grep -E "^${source_regex}/(${MUTATED_FOLDERS})/.*\.cs$" | sort -u )
if [ -z "$changed" ]; then
  echo "Mutation check: no changes in $SOURCE_PROJECT ($MUTATED_FOLDERS); nothing to check."
  exit 0
fi

echo "Mutation check: running Stryker on changed code in:"
sed 's/^/  /' <<<"$changed"

mutate_args=()
while read -r file; do mutate_args+=(--mutate "${file#"$SOURCE_PROJECT"/}"); done <<<"$changed"

cd "$UNIT_TEST_PROJECT" || exit 1
"$dotnet_bin" tool restore >/dev/null || exit 1
rm -rf StrykerOutput
"$dotnet_bin" stryker "${mutate_args[@]}" --reporter json --reporter cleartext > StrykerOutput.log 2>&1
status=$?
report=$(ls -t StrykerOutput/*/reports/mutation-report.json 2>/dev/null | head -1)
if [ $status -ne 0 ] || [ -z "$report" ]; then
  echo "Mutation check: Stryker failed. See $UNIT_TEST_PROJECT/StrykerOutput.log" >&2
  exit 1
fi

python3 -I - "$report" "$SOURCE_PROJECT" <<'EOF'
import json, sys
report = json.load(open(sys.argv[1]))
project = sys.argv[2]
tested = 0
problems = []
for path, data in report["files"].items():
    lines = data["source"].splitlines()
    for m in data["mutants"]:
        if m["status"] in ("Killed", "Timeout", "Survived", "NoCoverage"):
            tested += 1
        if m["status"] in ("Survived", "NoCoverage"):
            line = m["location"]["start"]["line"]
            original = lines[line - 1].strip() if line <= len(lines) else ""
            problems.append(f'  {path.split(project + "/")[-1]}:{line} [{m["status"]}] {m["mutatorName"]}: '
                            f'"{original}"  ->  {m.get("replacement", "").strip()}')
if problems:
    print(f"Mutation check FAILED: {len(problems)} of {tested} mutants in changed code were not caught by any test.")
    print("Add or strengthen tests (existing ones too) so each change below makes a test fail:")
    print("\n".join(problems))
    sys.exit(1)
print(f"Mutation check passed: {tested} mutants in changed code, 0 survived, 0 uncovered.")
EOF
