#!/usr/bin/env bash
# GPU experiment suite (resumable). Each run gets fresh stores; results are copied to $DEST after
# every run, and runs already present in $DEST are skipped (Colab disconnects are safe).
#
#   DEST=/content/drive/MyDrive/memprof_results/a100 scripts/run_gpu_suite.sh e1 [e2 e3 ...]
#
#   smoke  every system, 3 turns                                          (~10 min, run first)
#   e1     main profile, sync write path: all systems, TURNS turns, QA questions
#   e2     write/read interference: --async-add (back-to-back turns, and 5 s think time)
#   e3     KV placement: prefix cache off; VRAM KV budget sweep (KV_LIST) with/without host-RAM KV offload
#   e4     model size: Qwen3-4B-Instruct-2507 and Qwen3-14B (A100-80G) for mem0-pg + graphiti
set -uo pipefail
cd "$(dirname "$0")/.."
HW=${HW:-$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 | tr ' ' '_' || echo cpu)}
OUT=${OUT:-results/gpu/$HW}
DEST=${DEST:-}
TURNS=${TURNS:-100}
QA=${QA:-50}
CONV=${CONV:-0}
SYSTEMS=${SYSTEMS:-"rag-pg mem0-pg mem0-qdrant graphiti letta"}
PY=.venv/bin/python
mkdir -p "$OUT"
export MEMPROF_VLLM_METRICS=${MEMPROF_VLLM_METRICS:-http://127.0.0.1:8000}

fresh_stores() {
  scripts/services.sh reset all >/dev/null 2>&1
  scripts/services.sh start all >/dev/null 2>&1 || { echo "services failed"; return 1; }
  if [ "$1" = letta ]; then scripts/letta.sh reset >/dev/null && scripts/letta.sh start >/dev/null || return 1; fi
}

run() {  # run <name> <system> [extra args...]
  local name=$1 sys=$2; shift 2
  if [ -n "$DEST" ] && [ -f "$DEST/$name/meta.json" ]; then echo "skip $name (done)"; return 0; fi
  echo "=== $name ($sys) $(date +%T)"
  fresh_stores "$sys" || return 1
  $PY bench/multi_e2e.py --system "$sys" --conv "$CONV" --out "$OUT/$name" --label "$name" "$@" \
     >"$OUT/$name.log" 2>&1
  local rc=$?
  [ "$sys" = letta ] && { cp results/letta_server.log "$OUT/$name/letta_server.log" 2>/dev/null; scripts/letta.sh stop; }
  cp results/server_logs/vllm_llm.cmd "$OUT/$name/" 2>/dev/null
  if [ $rc -ne 0 ]; then echo "FAILED $name (rc=$rc), tail:"; tail -15 "$OUT/$name.log"; return 0; fi
  $PY analysis/multi_breakdown.py "$OUT/$name" >/dev/null 2>&1
  tail -1 "$OUT/$name.log"
  if [ -n "$DEST" ]; then mkdir -p "$DEST"; cp -r "$OUT/$name" "$OUT/$name.log" "$DEST/"; fi
}

restart_llm() { scripts/start_vllm.sh llm >/dev/null || { echo "vLLM restart failed"; tail -30 results/server_logs/vllm_llm.log; exit 1; }; }

for suite in "$@"; do case $suite in
  smoke)
    for s in $SYSTEMS; do run "smoke_$s" "$s" --turns 3 --qa 2; done ;;
  e1)
    for s in $SYSTEMS; do run "e1_${s}_sync" "$s" --turns "$TURNS" --qa "$QA"; done ;;
  e2)
    for s in rag-pg mem0-pg graphiti; do
      run "e2_${s}_async" "$s" --turns "$TURNS" --qa 0 --async-add
      run "e2_${s}_async_think5" "$s" --turns "$TURNS" --qa 0 --async-add --think 5
    done ;;
  e3)
    T3=${T3:-60}
    PREFIX_CACHE=0 restart_llm
    for s in mem0-pg graphiti letta; do run "e3_${s}_noprefix" "$s" --turns "$T3" --qa 0; done
    for kv in ${KV_LIST:-1G 2G 4G}; do
      KV_BYTES=$kv restart_llm
      for s in mem0-pg graphiti; do run "e3_${s}_kv${kv}_async" "$s" --turns "$T3" --qa 0 --async-add; done
      KV_BYTES=$kv KV_OFFLOAD_GB=${KV_OFFLOAD_GB:-16} restart_llm
      for s in mem0-pg graphiti; do run "e3_${s}_kv${kv}_off${KV_OFFLOAD_GB:-16}_async" "$s" --turns "$T3" --qa 0 --async-add; done
    done
    restart_llm ;;
  e4)
    for m in Qwen/Qwen3-4B-Instruct-2507 ${E4_BIG:-}; do
      tag=$(basename "$m"); LLM_MODEL=$m restart_llm
      for s in mem0-pg graphiti; do run "e4_${s}_${tag}" "$s" --turns "${T4:-60}" --qa 0; done
    done
    restart_llm ;;
  *) echo "unknown suite $suite" ;;
esac; done
echo "suite done -> $OUT ${DEST:+(copied to $DEST)}"
