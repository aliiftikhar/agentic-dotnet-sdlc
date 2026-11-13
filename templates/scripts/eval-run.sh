#!/bin/bash
# Harness evals: give real tasks to an agent in a history-free snapshot and score the result.
# See "Evals" in AGENTS.md. Configure the project names at the top of scripts/eval_run.py.
#   scripts/eval-run.sh --check [--tasks <ids>]          check the tasks still fit the code (no agent, free)
#   scripts/eval-run.sh --agent claude|codex [--model <name>] [--effort <level>] [--tasks <ids>] [--ref <ref>] [--keep]
# <ids> is a comma-separated list of task ids or set names from evals/sets/ (e.g. --tasks smoke).
# Runs locally only, with the owner's own Claude Code and Codex sign-ins. Each task runs in a temporary
# folder with no git remote, deleted afterwards (unless --keep). --ref evaluates a harness branch before merge.
set -u
repo=$(git rev-parse --show-toplevel) || exit 1
exec python3 "$repo/scripts/eval_run.py" "$@"
