#!/bin/bash
# Token and cost report for an OpenSpec change, from the local Claude Code and Codex session logs.
#
#   scripts/cost-report.sh <change-name> [--branch <branch>] [--print]
#       Writes cost.md in the change folder (active or archived) and prints the table for the PR.
#       --branch  the change's branch (default: the current branch)
#       --print   print only; don't write cost.md
#
# See "Cost report" in AGENTS.md. Prices: scripts/model-prices.json.
set -u
repo=$(git rev-parse --show-toplevel) || exit 1
exec python3 "$repo/scripts/cost_report.py" "$@"
