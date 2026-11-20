#!/usr/bin/env bash
# Start llama.cpp server (OpenAI-compatible) for the profiling runs.
# usage: start_llm.sh <model.gguf> <n_parallel_slots> <ctx_total> [port]
set -euo pipefail
MODEL=${1:-models/qwen2.5-1.5b-instruct-q4_k_m.gguf}
NP=${2:-2}
CTX=${3:-32768}
PORT=${4:-8080}
LLAMA=${LLAMA_SERVER:-/home/user/llama.cpp/build/bin/llama-server}
pkill -f "llama-server.*--port $PORT" 2>/dev/null || true
sleep 1
nohup "$LLAMA" -m "$MODEL" -c "$CTX" -np "$NP" -t "$(nproc)" --port "$PORT" \
  --metrics --no-webui --temp 0.1 > "results/llama_server_${PORT}.log" 2>&1 &
for i in $(seq 1 120); do
  curl -sf "http://127.0.0.1:$PORT/health" >/dev/null && { echo "llama-server up (np=$NP ctx=$CTX)"; exit 0; }
  sleep 1
done
echo "llama-server failed to start"; tail -20 "results/llama_server_${PORT}.log"; exit 1
