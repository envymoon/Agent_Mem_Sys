#!/usr/bin/env bash
# Local-machine experiment suite (RTX 4060 8 GB, llama.cpp, real NVMe). Resumable: a run whose
# $OUT/<name>/meta.json (or result file) exists is skipped. Run as root inside WSL2/Ubuntu:
#   scripts/local/run_local_suite.sh preflight smoke kv load l1 l2 l3 l4 l5
#
#   preflight  hardware inventory, fio baseline (seq/rand/fsync), page-cache check            ~3 min
#   smoke      every system, 3 turns                                                          ~10 min
#   kv         KV-tier micro-benchmark: recompute vs GPU vs host-RAM prompt cache vs SSD slot file
#              (with --cache-ram 8192 and 0)                                                   ~10 min
#   load       model cold (page cache dropped) vs warm load, mmap vs read                      ~5 min
#   l1         main profile, sync write path, every system, TURNS turns + QA questions        ~2-4 h
#   l2         foreground/background interference: async memorize, think time 0 / 5 s         ~2 h
#   l3         KV placement on real workloads (mem0-pg, graphiti; async; T3 turns):
#              base | no prefix cache | no host-RAM cache | KV q8_0 | KV in host RAM | 8k ctx   ~3 h
#   l4         model choice: q8b, llama8b, moe30b (if downloaded) on mem0-pg + graphiti      ~2-3 h
#   l5         store scale 1e3..1e5 with hot/cold page cache: rag-pg, mem0-pg, mem0-qdrant, mem0-local ~1-2 h
#
# env: PROFILE=q4b  TURNS=100  QA=50  T3=60  T4=60  SIZES=1000,10000,50000,100000  OUT=results/local/<host>
set -uo pipefail
cd "$(dirname "$0")/../.."
export PROFILE=${PROFILE:-q4b}
export MEMPROF_MODELS=${MEMPROF_MODELS:-$HOME/models}
export LOCOMO=${LOCOMO:-$HOME/locomo/data/locomo10.json}
export SVC_DATA=${SVC_DATA:-/opt/svc/data}
export SLOT_SAVE=${SLOT_SAVE:-$SVC_DATA/kv_slots}
export MEMPROF_VLLM_METRICS=${MEMPROF_VLLM_METRICS:-http://127.0.0.1:8000}   # hwmon scrapes llama.cpp /metrics
OUT=${OUT:-results/local/$(hostname)}
TURNS=${TURNS:-100}; QA=${QA:-50}; CONV=${CONV:-0}
SYSTEMS=${SYSTEMS:-"rag-pg mem0-local mem0-pg mem0-qdrant graphiti"}
PY=.venv/bin/python
L=scripts/local/start_llama.sh
mkdir -p "$OUT"
export PATH=/usr/lib/wsl/lib:$PATH
log() { echo "[$(date +%T)] $*" | tee -a "$OUT/suite.log"; }

stack() {  # (re)start llama-server + proxy with the current env; embedder only if not up
  curl -sf http://127.0.0.1:8001/health >/dev/null || $L emb >>"$OUT/suite.log" 2>&1 || { log "embedder failed"; exit 1; }
  $L llm >>"$OUT/suite.log" 2>&1 || { log "LLM failed: $(tail -3 results/server_logs/llm.log)"; exit 1; }
  $L proxy >>"$OUT/suite.log" 2>&1 || { log "proxy failed"; exit 1; }
}
fresh_stores() { scripts/services.sh reset all >/dev/null 2>&1; scripts/services.sh start all >/dev/null 2>&1 || { log "services failed"; return 1; }; }

run() {  # run <name> <system> [args...]
  local name=$1 sys=$2; shift 2
  [ -f "$OUT/$name/meta.json" ] && { log "skip $name"; return 0; }
  log "=== $name ($sys) PROFILE=$PROFILE"
  fresh_stores || return 1
  sync; echo 3 >/proc/sys/vm/drop_caches 2>/dev/null   # every run starts from the same (cold store) state
  $PY bench/multi_e2e.py --system "$sys" --conv "$CONV" --out "$OUT/$name" --label "$name" "$@" >"$OUT/$name.log" 2>&1
  local rc=$?
  cp results/server_logs/llm.cmd results/server_logs/llm.load.json "$OUT/$name/" 2>/dev/null
  if [ $rc -ne 0 ]; then log "FAILED $name rc=$rc: $(tail -3 "$OUT/$name.log" | tr '\n' ' ')"; return 0; fi
  $PY analysis/multi_breakdown.py "$OUT/$name" >/dev/null 2>&1
  log "done $name: $(tail -1 "$OUT/$name.log")"
}

for suite in "$@"; do case $suite in
  preflight) [ -f "$OUT/preflight/inventory.json" ] || OUT=$OUT scripts/local/preflight.sh | tee -a "$OUT/suite.log" ;;
  smoke) stack; for s in $SYSTEMS; do run "smoke_$s" "$s" --turns 3 --qa 2; done ;;
  kv)
    for cr in 8192 0; do
      n=kv_${PROFILE}_ram$cr; [ -f "$OUT/$n/kv_tier.json" ] && { log "skip $n"; continue; }
      CACHE_RAM=$cr NP=1 stack; log "=== $n"
      $PY bench/kv_tier_bench.py --out "$OUT/$n" --label "$n" --lens "${KV_LENS:-1024,2048,4096,8192,12288}" 2>&1 | tee -a "$OUT/suite.log"
    done; stack ;;
  load)
    n=load_$PROFILE; [ -f "$OUT/$n/load.jsonl" ] && { log "skip $n"; continue; }
    mkdir -p "$OUT/$n"; curl -sf http://127.0.0.1:8001/health >/dev/null || $L emb >/dev/null
    for mode in mmap none; do for temp in cold warm; do
      $L stop >/dev/null; $L emb >/dev/null
      [ $temp = cold ] && { sync; echo 3 >/proc/sys/vm/drop_caches; }
      $PY -c "from memprof import iostat; import json; json.dump(iostat.snapshot(), open('/tmp/_io0.json','w'))"
      LOAD_MODE=$mode $L llm >/dev/null
      $PY - "$mode" "$temp" >>"$OUT/$n/load.jsonl" <<'PYX'
import json, sys
from memprof import iostat
d = iostat.flat(iostat.delta(json.load(open("/tmp/_io0.json")), iostat.snapshot()))
j = json.load(open("results/server_logs/llm.load.json"))
dev_rd = sum(v["rd_sec"] for v in iostat.delta(json.load(open("/tmp/_io0.json")), iostat.snapshot())["dev"].values()) * 512
print(json.dumps({"mode": sys.argv[1], "page_cache": sys.argv[2], "load_wall_s": j["load_wall_s"],
                  "dev_read_mb": dev_rd / 2**20, "buffers_mib": j["buffers_mib"], "offloaded": j["offloaded"]}))
PYX
      log "load $mode/$temp: $(tail -1 "$OUT/$n/load.jsonl")"
    done; done; stack ;;
  l1) stack; for s in $SYSTEMS; do run "l1_${PROFILE}_${s}_sync" "$s" --turns "$TURNS" --qa "$QA"; done ;;
  l2) stack
      for s in rag-pg mem0-local mem0-pg graphiti; do
        run "l2_${PROFILE}_${s}_async" "$s" --turns "$TURNS" --qa 0 --async-add
        run "l2_${PROFILE}_${s}_async_think5" "$s" --turns "$TURNS" --qa 0 --async-add --think 5
      done ;;
  l3) T3=${T3:-60}
      for v in base noprefix noram kvq8 kvhost ctx8k; do
        case $v in
          base) stack ;; noprefix) CACHE_PROMPT=0 stack ;; noram) CACHE_RAM=0 stack ;;
          kvq8) KV=q8_0 stack ;; kvhost) NO_KV_OFFLOAD=1 stack ;; ctx8k) CTX=8192 stack ;;
        esac
        for s in ${L3_SYSTEMS:-mem0-pg graphiti}; do run "l3_${PROFILE}_${s}_${v}" "$s" --turns "$T3" --qa 0 --async-add; done
      done; stack ;;
  l4) for p in ${L4_PROFILES:-q8b llama8b moe30b}; do
        ( export PROFILE=$p; source scripts/local/profiles.sh
          [ -s "$LLM_GGUF" ] || { log "skip profile $p (model not downloaded)"; exit 0; }
          stack
          for s in ${L4_SYSTEMS:-mem0-pg graphiti}; do run "l4_${p}_${s}_sync" "$s" --turns "${T4:-60}" --qa 20; done
          n=kv_${p}_ram8192; [ -f "$OUT/$n/kv_tier.json" ] || { NP=1 stack; $PY bench/kv_tier_bench.py --out "$OUT/$n" --label "$n" --reps 2 2>&1 | tail -8 | tee -a "$OUT/suite.log"; } )
      done; stack ;;
  l5) stack
      for b in ${L5_BACKENDS:-rag-pg mem0-pg mem0-qdrant mem0-local}; do
        n=l5_scale_$b; [ -f "$OUT/$n/scale.json" ] && [ "$(jq length "$OUT/$n/scale.json")" -ge "$(echo "${SIZES:-1000,10000,50000,100000}" | tr , '\n' | wc -l)" ] && { log "skip $n"; continue; }
        fresh_stores; log "=== $n"
        $PY bench/scale_disk.py --backend "$b" --sizes "${SIZES:-1000,10000,50000,100000}" --out "$OUT/$n" 2>&1 | grep -v -i warn | tee -a "$OUT/suite.log"
      done ;;
  *) log "unknown suite $suite" ;;
esac; done
log "suite done -> $OUT"
