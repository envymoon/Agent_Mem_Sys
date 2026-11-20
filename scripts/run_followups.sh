#!/usr/bin/env bash
# Async write-path interference run + memory-store scaling study.
set -uo pipefail
cd "$(dirname "$0")/.."
. .venv/bin/activate
while pgrep -f run_e2e_suite >/dev/null; do sleep 10; done
scripts/start_llm.sh models/qwen2.5-1.5b-instruct-q4_k_m.gguf 2 32768 >/dev/null
MEMPROF_LABEL=async_np2 python bench/agent_e2e.py --turns 15 --qa 0 --async-add --think 5 \
  --out results/e2e_async_np2 2>&1 | grep -E "^turn|^\{" > results/e2e_async_np2.log
pkill -f llama-server   # scaling study does not use the LLM; free the cores
python bench/scale_store.py --layout single --out results/scale_single 2>&1 | grep -E "^\{|Error|Traceback" > results/scale_single.log
python bench/scale_store.py --layout multi  --out results/scale_multi  2>&1 | grep -E "^\{|Error|Traceback" > results/scale_multi.log
echo ALLDONE
