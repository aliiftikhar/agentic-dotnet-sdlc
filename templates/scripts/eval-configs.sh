#!/bin/bash
# Run the eval set once per model-per-step configuration, in the order given, and wait out usage limits.
#   scripts/eval-configs.sh sonnet/sonnet/sonnet opus/sonnet/sonnet sonnet/haiku/opus
#   scripts/eval-configs.sh sonnet/haiku/opus:2026-11-14T0438-c3      (plan/build/verify:run-id continues an earlier run)
#   EVAL_AGENT=codex EVAL_TASKS=all scripts/eval-configs.sh <plan>/<build>/<verify> ...
# Each configuration is plan/build/verify models. EVAL_TASKS: a set name or ids (default: smoke), or "all".
# When a usage limit or API outage stops a run (exit 75), it waits 30 minutes and continues the same run.
# Only the repo owner starts this: it uses their plans. Progress goes to evals/results/logs/.
set -u
repo=$(git rev-parse --show-toplevel) || exit 1
log="$repo/evals/results/logs/configs-$(date +%Y-%m-%dT%H%M).log"
mkdir -p "$(dirname "$log")"
agent="${EVAL_AGENT:-claude}"
tasks="${EVAL_TASKS:-smoke}"
task_args=(--tasks "$tasks")
[ "$tasks" = "all" ] && task_args=()
wait_minutes=30
max_waits=48  # give up after a day of waiting (a weekly limit)
awake=()
command -v caffeinate >/dev/null && awake=(caffeinate -i)  # keep a Mac awake; elsewhere, keep the machine on yourself

say() { echo "[$(date '+%Y-%m-%d %H:%M')] $*" | tee -a "$log"; }

for arg in "$@"; do
  case "${arg%%:*}" in */*/*) ;; *) echo "Not plan/build/verify: $arg"; exit 2 ;; esac
done

n=0
for arg in "$@"; do
  n=$((n + 1))
  IFS=/ read -r plan build verify <<<"${arg%%:*}"
  run_id="$(date +%Y-%m-%dT%H%M)-c$n"
  [ "$arg" != "${arg%%:*}" ] && run_id="${arg#*:}"
  waits=0
  say "Config $n: plan $plan, build $build, verify $verify, agent $agent, tasks $tasks (run $run_id)"
  while true; do
    "${awake[@]+"${awake[@]}"}" python3 "$repo/scripts/eval_run.py" --agent "$agent" "${task_args[@]+"${task_args[@]}"}" \
      --plan-model "$plan" --build-model "$build" --verify-model "$verify" --run-id "$run_id" 2>&1 | tee -a "$log"
    code=${PIPESTATUS[0]}
    if [ "$code" -eq 75 ]; then
      waits=$((waits + 1))
      if [ "$waits" -gt "$max_waits" ]; then say "Still stopped after $max_waits waits; stopping."; exit 75; fi
      say "Usage limit or API outage: waiting $wait_minutes minutes, then continuing ($waits)"
      sleep $((wait_minutes * 60))
    elif [ "$code" -ne 0 ]; then
      say "Config $n stopped with exit $code; stopping."; exit "$code"
    else
      say "Config $n done."; break
    fi
  done
done
say "All done: $*"
