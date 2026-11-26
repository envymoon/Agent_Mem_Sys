#!/usr/bin/env bash
# Local inference stack on one consumer GPU, llama.cpp (pinned build), production-style server flags:
#   :8000 chat LLM  (llama-server, continuous batching, unified KV, prompt cache, host-RAM prompt cache, metrics)
#   :8001 embedder  (llama-server --embeddings, same GPU)
#   :8100 memprof proxy (every memory system talks to this)
#
# env knobs (defaults come from PROFILE in profiles.sh):
#   PROFILE=gptoss20b|q14b|q4b|q8b|llama8b|moe30b|cpu
#   CTX=  NP=2 (slots: foreground agent + background memory writer)  KV=f16|q8_0
#   CACHE_RAM=8192  host-RAM prompt cache MiB (llama.cpp default; 0 = off)        -> DRAM tier
#   CACHE_PROMPT=1  0 -> proxy injects cache_prompt=false (no prefix reuse at all) -> ablation
#   NO_KV_OFFLOAD=0 1 -> KV cache in host RAM, attention on CPU                    -> DRAM tier
#   LOAD_MODE=auto  mmap|none|dio  (model load path from SSD)
#   SLOT_SAVE=$SVC_DATA/kv_slots  slot save/restore dir (KV state to SSD)           -> SSD tier
#   LLAMA_BIN=$HOME/llama.cpp/build/bin   LLAMA_EXTRA / EMB_EXTRA  extra flags
# usage: scripts/local/start_llama.sh [all|llm|emb|proxy|stop]
set -euo pipefail
cd "$(dirname "$0")/../.."
source scripts/local/profiles.sh
BIN=${LLAMA_BIN:-$HOME/llama.cpp/build/bin}
CTX=${CTX:-$P_CTX}; NP=${NP:-2}; KV=${KV:-$P_KV}; NGL=${NGL:-$P_NGL}
SVC_DATA=${SVC_DATA:-/opt/svc/data}
SLOT_SAVE=${SLOT_SAVE:-$SVC_DATA/kv_slots}
LOGD=${LOGD:-results/server_logs}
THREADS=${THREADS:-$(nproc)}
mkdir -p "$LOGD" "$SLOT_SAVE"

wait_http() {  # url name tries log [pid]
  for _ in $(seq 1 "${3:-600}"); do
    curl -sf "$1" >/dev/null && { echo "$2 up"; return 0; }
    [ -n "${5:-}" ] && ! kill -0 "$5" 2>/dev/null && break
    sleep 0.2
  done; echo "$2 FAILED"; tail -30 "$4"; return 1; }

llm() {
  local FA=on; [ "$NGL" = 0 ] && FA=auto   # flash-attn (needed for quantized V cache) on GPU
  pkill -f "llama-server.*--port 8000" 2>/dev/null || true; sleep 1
  A=(-m "$LLM_GGUF" --alias local --port 8000 --host 127.0.0.1 -c "$CTX" -np "$NP" -ngl "$NGL"
     -ctk "$KV" -ctv "$KV" -fa "$FA" --fit off --kv-unified --cache-ram "${CACHE_RAM:-8192}"
     --slot-save-path "$SLOT_SAVE/" --metrics --jinja --no-webui -t "$THREADS" -lv 4
     --load-mode "${LOAD_MODE:-auto}")
  [ "${NO_KV_OFFLOAD:-0}" = 1 ] && A+=(--no-kv-offload)
  # shellcheck disable=SC2206
  A+=($P_EXTRA ${LLAMA_EXTRA:-})
  echo "$BIN/llama-server ${A[*]}" | tee "$LOGD/llm.cmd"
  local t0; t0=$(date +%s.%N)
  nohup "$BIN/llama-server" "${A[@]}" >"$LOGD/llm.log" 2>&1 </dev/null &
  wait_http http://127.0.0.1:8000/health "LLM ($LLM_FILE, PROFILE=${PROFILE:-q4b})" 3000 "$LOGD/llm.log" $!
  local t1; t1=$(date +%s.%N)
  # what actually landed on the GPU (an OOM fallback would silently change the experiment)
  python3 - "$LOGD/llm.log" "$t0" "$t1" >"$LOGD/llm.load.json" <<'PY'
import json, re, sys
log = open(sys.argv[1], errors="ignore").read()
def g(rx, cast=str):
    m = re.findall(rx, log)
    return cast(m[-1]) if m else None
bufs = {}
for dev, kind, mib in re.findall(r"(\S+) (model|KV|compute|RS) buffer size =\s+([\d.]+) MiB", log):
    k = f"{kind}:{dev}"
    bufs[k] = round(bufs.get(k, 0) + float(mib), 1)
print(json.dumps({"load_wall_s": float(sys.argv[3]) - float(sys.argv[2]),
  "offloaded": g(r"offloaded (\d+/\d+) layers to GPU"), "buffers_mib": bufs,
  "n_ctx_slot": g(r"n_ctx_slot = (\d+)", int)}))
PY
  cat "$LOGD/llm.load.json"
}
emb() {
  pkill -f "llama-server.*--port 8001" 2>/dev/null || true; sleep 1
  nohup "$BIN/llama-server" -m "$EMB_GGUF" --alias local-embed --port 8001 --host 127.0.0.1 --embeddings \
    --pooling last -c 8192 -b 8192 -ub 8192 -np 4 -ngl "$EMB_NGL" -t "$THREADS" --metrics --no-webui \
    ${EMB_EXTRA:-} >"$LOGD/emb.log" 2>&1 </dev/null &
  wait_http http://127.0.0.1:8001/health "embedder ($EMB_FILE)" 1500 "$LOGD/emb.log" $!
}
proxy() {
  pkill -f memprof.llm_proxy 2>/dev/null || true; sleep 0.5
  local inj='{}'; [ "${CACHE_PROMPT:-1}" = 0 ] && inj='{"cache_prompt": false}'
  nohup .venv/bin/python -m memprof.llm_proxy --port 8100 --chat http://127.0.0.1:8000 --embed http://127.0.0.1:8001 \
    --chat-model local --embed-model local-embed --ctx "$CTX" $([ "$P_NOTHINK" = 1 ] && echo --no-think) \
    --chat-kwargs "$P_CHAT_KWARGS" --inject "$inj" \
    --log results/_proxy_idle.jsonl >"$LOGD/proxy.log" 2>&1 </dev/null &
  wait_http http://127.0.0.1:8100/memprof/health proxy 100 "$LOGD/proxy.log" $!
}
stop() { pkill -f "llama-server.*--port 800[01]" 2>/dev/null || true; pkill -f memprof.llm_proxy 2>/dev/null || true; sleep 1; }
case ${1:-all} in
  all) emb; llm; proxy ;;   # embedder first: small fixed footprint, LLM gets the rest
  llm) llm ;; emb) emb ;; proxy) proxy ;; stop) stop ;;
  *) echo "usage: $0 [all|llm|emb|proxy|stop]"; exit 1 ;;
esac
