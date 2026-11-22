#!/usr/bin/env bash
# Production-style local inference stack on one GPU:
#   :8000 chat LLM (vLLM, prefix caching on, tool calling, per-request metrics)
#   :8001 embedding model (vLLM pooling runner, same GPU)
#   :8100 memprof proxy (all memory systems talk to this)
#
# env knobs (defaults = A100 profile):
#   LLM_MODEL=Qwen/Qwen3-8B   LLM_QUANT=(empty|fp8|awq)   LLM_CTX=32768   LLM_GPU_UTIL=0.80
#   KV_BYTES=            e.g. 4G -> fixed KV-cache budget (emulate a smaller consumer GPU)
#   KV_OFFLOAD_GB=       e.g. 16 -> vLLM native KV offloading to host RAM (DRAM tier)
#   PREFIX_CACHE=1       0 -> --no-enable-prefix-caching (ablation)
#   EMB_MODEL=Qwen/Qwen3-Embedding-0.6B  EMB_GPU_UTIL=0.08
#   VLLM_EXTRA / EMB_EXTRA  extra CLI flags
#   usage: scripts/start_vllm.sh [all|llm|emb|proxy|stop]
set -euo pipefail
cd "$(dirname "$0")/.."
VV=${VLLM_VENV:-.venv-vllm}
LLM_MODEL=${LLM_MODEL:-Qwen/Qwen3-8B}
LLM_CTX=${LLM_CTX:-32768}
LLM_GPU_UTIL=${LLM_GPU_UTIL:-0.80}
EMB_MODEL=${EMB_MODEL:-Qwen/Qwen3-Embedding-0.6B}
EMB_GPU_UTIL=${EMB_GPU_UTIL:-0.08}
LOGD=${LOGD:-results/server_logs}
mkdir -p "$LOGD"

wait_http() { for _ in $(seq 1 ${3:-900}); do curl -sf "$1" >/dev/null && { echo "$2 up"; return 0; }; sleep 1; done; echo "$2 FAILED"; tail -30 "$4"; return 1; }

llm() {
  pkill -f "vllm serve.*--port 8000" 2>/dev/null || true; sleep 2
  A=(serve "$LLM_MODEL" --served-model-name local --port 8000 --host 127.0.0.1
     --max-model-len "$LLM_CTX" --enable-auto-tool-choice --tool-call-parser hermes
     --enable-prompt-tokens-details --enable-per-request-metrics --enable-force-include-usage
     --disable-uvicorn-access-log --default-chat-template-kwargs '{"enable_thinking": false}')
  if [ -n "${KV_BYTES:-}" ]; then A+=(--kv-cache-memory-bytes "$KV_BYTES"); else A+=(--gpu-memory-utilization "$LLM_GPU_UTIL"); fi
  [ "${PREFIX_CACHE:-1}" = 0 ] && A+=(--no-enable-prefix-caching) || A+=(--enable-prefix-caching)
  [ -n "${LLM_QUANT:-}" ] && A+=(--quantization "$LLM_QUANT")
  [ -n "${KV_OFFLOAD_GB:-}" ] && A+=(--kv-offloading-size "$KV_OFFLOAD_GB" --kv-offloading-backend native)
  echo "vllm ${A[*]} ${VLLM_EXTRA:-}" | tee "$LOGD/vllm_llm.cmd"
  nohup "$VV/bin/vllm" "${A[@]}" ${VLLM_EXTRA:-} >"$LOGD/vllm_llm.log" 2>&1 </dev/null &
  wait_http http://127.0.0.1:8000/health "LLM ($LLM_MODEL)" 1200 "$LOGD/vllm_llm.log"
}
emb() {
  pkill -f "vllm serve.*--port 8001" 2>/dev/null || true; sleep 2
  nohup "$VV/bin/vllm" serve "$EMB_MODEL" --served-model-name local-embed --port 8001 --host 127.0.0.1 \
    --runner pooling --gpu-memory-utilization "$EMB_GPU_UTIL" --max-model-len 8192 --disable-uvicorn-access-log \
    ${EMB_EXTRA:-} >"$LOGD/vllm_emb.log" 2>&1 </dev/null &
  wait_http http://127.0.0.1:8001/health "embedder ($EMB_MODEL)" 900 "$LOGD/vllm_emb.log"
}
proxy() {
  pkill -f memprof.llm_proxy 2>/dev/null || true; sleep 1
  nohup .venv/bin/python -m memprof.llm_proxy --port 8100 --chat http://127.0.0.1:8000 --embed http://127.0.0.1:8001 \
    --chat-model local --embed-model local-embed --ctx "$LLM_CTX" --no-think \
    --log results/_proxy_idle.jsonl >"$LOGD/proxy.log" 2>&1 </dev/null &
  wait_http http://127.0.0.1:8100/memprof/health proxy 30 "$LOGD/proxy.log"
}
stop() { pkill -f "vllm serve" 2>/dev/null || true; pkill -f memprof.llm_proxy 2>/dev/null || true; sleep 3; }
case ${1:-all} in
  all) emb; llm; proxy ;;   # embedder first: it claims a small fixed fraction
  llm) llm ;; emb) emb ;; proxy) proxy ;; stop) stop ;;
esac
