#!/usr/bin/env bash
# Runs the end-to-end agent profiling under different LLM KV-cache configurations.
set -uo pipefail
cd "$(dirname "$0")/.."
. .venv/bin/activate
M=models/qwen2.5-1.5b-instruct-q4_k_m.gguf
run() { # label np cache turns qa
  scripts/start_llm.sh $M $2 $(( $2 * 16384 )) >/dev/null
  MEMPROF_LABEL=$1 MEMPROF_CACHE_PROMPT=$3 python bench/agent_e2e.py --turns $4 --qa $5 --out results/e2e_$1 \
     2>&1 | grep -E "^turn|^\{" > results/e2e_$1.log
}
run cache_np2 2 1 40 20     # prefix cache on, 2 slots: extraction & chat get separate slots
run cache_np1 1 1 12 0      # prefix cache on, 1 slot: chat & extraction evict each other
run nocache   2 0 8 0       # prefix cache disabled
