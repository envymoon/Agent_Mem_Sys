#!/usr/bin/env bash
# Extra control: single slot AND host-RAM prompt cache disabled -> chat and extraction evict each other.
set -uo pipefail
cd "$(dirname "$0")/.."
. .venv/bin/activate
until grep -q ALLDONE results/followups.log 2>/dev/null; do sleep 15; done
LLAMA_EXTRA="--cache-ram 0" scripts/start_llm.sh models/qwen2.5-1.5b-instruct-q4_k_m.gguf 1 16384 >/dev/null
MEMPROF_LABEL=cache_np1_noram python bench/agent_e2e.py --turns 8 --qa 0 --out results/e2e_cache_np1_noram \
  2>&1 | grep -E "^turn|^\{" > results/e2e_cache_np1_noram.log
cp results/llama_server_8080.log results/e2e_cache_np1_noram/llama_server.log
echo EXTRADONE
