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
#   rates      llama-bench pp512 / tg64 at KV depth 0..ctx for PROFILE: the per-token costs the latency model
#              (analysis/latency_model.py) uses. GPU-only, no storage claims -> also the suite to run on a
#              bigger cloud GPU for the what-if / cross-check                                   ~5 min
#   l1         main profile, sync write path, every system, TURNS turns + QA questions        ~2-4 h
#   l2         foreground/background interference: async memorize, think time 0 / 5 s         ~2 h
#   l3         KV placement on real workloads (mem0-pg, graphiti; async; T3 turns):
#              base | no prefix cache | no host-RAM cache | KV q8_0 | KV in host RAM | 8k ctx   ~3 h
#   l4         model choice: q8b, llama8b, moe30b (if downloaded) on mem0-pg + graphiti      ~2-3 h
#   model      latency model per profile (l1 / l4 runs + rates + fio): validation error and GPU / disk what-ifs.
#              Extra comparisons: MODEL_GPU="A100=dir/llama_bench.json"  MODEL_DISK="native=dir/fio_fsyncwrite.json"
#   lme        LongMemEval-S (standard long-history benchmark): LME_ITEMS haystacks x LME_SYSTEMS, sync, 1 QA each;
#              default items 70 / 233 / 366 = first multi-session / temporal-reasoning / knowledge-update question;
#              LME_TURNS=0 -> full haystack (~245 user turns), N -> evidence + distractor sessions up to N turns
#   score      QA accuracy of every run with a qa.json (token F1 + LLM judge with the local model)
#   pilot      cheap first pass to see quality and cost before committing CU: preflight smoke rates kv,
#              l1 with PILOT_TURNS turns, one truncated LongMemEval item, score, budget
#   budget     per-turn cost of every finished run -> hours / compute units for the full suites (analysis/budget.py)
#   l5         store scale 1e3..1e5 with hot/cold page cache: rag-pg, mem0-pg, mem0-qdrant, mem0-local ~1-2 h
#
# Colab / cloud: SYNC_DIR=<Drive dir> mirrors OUT there after every run (and OUT is restored from it on start, so
# a new runtime resumes); REP=2 suffixes run names (_r2) to repeat key runs on another VM for variance.
# env: PROFILE=q4b  TURNS=100  QA=50  T3=60  T4=60  SIZES=1000,10000,50000,100000  OUT=results/local/<host>-<wsl|native>
set -uo pipefail
SELF="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
cd "$(dirname "$0")/../.."
export PROFILE=${PROFILE:-q4b}
source scripts/local/profiles.sh
[ "$PROFILE" = gptoss20b ] && { export ANSWER_TOKENS=${ANSWER_TOKENS:-1024} QA_TOKENS=${QA_TOKENS:-512}; }  # reasoning tokens count
export MEMPROF_MODELS=${MEMPROF_MODELS:-$HOME/models}
export LOCOMO=${LOCOMO:-$HOME/locomo/data/locomo10.json}
export LONGMEMEVAL=${LONGMEMEVAL:-$HOME/longmemeval/longmemeval_s_cleaned.json}
export SVC_DATA=${SVC_DATA:-/opt/svc/data}
export SLOT_SAVE=${SLOT_SAVE:-$SVC_DATA/kv_slots}
export MEMPROF_VLLM_METRICS=${MEMPROF_VLLM_METRICS:-http://127.0.0.1:8000}   # hwmon scrapes llama.cpp /metrics
OUT=${OUT:-results/local/$(hostname)-$(grep -qi microsoft /proc/version && echo wsl || echo native)}
TURNS=${TURNS:-100}; QA=${QA:-50}; CONV=${CONV:-0}
SYSTEMS=${SYSTEMS:-"rag-pg mem0-local mem0-pg mem0-qdrant graphiti"}
PY=.venv/bin/python
L=scripts/local/start_llama.sh
mkdir -p "$OUT"
SYNC_DIR=${SYNC_DIR:-}
BOOT=$(cut -c1-8 /proc/sys/kernel/random/boot_id)
if [ -n "$SYNC_DIR" ] && [ -d "$SYNC_DIR" ]; then cp -rn "$SYNC_DIR/." "$OUT/" 2>/dev/null; fi   # resume on a new runtime
sync_out() { [ -n "$SYNC_DIR" ] && { mkdir -p "$SYNC_DIR"; cp -ru "$OUT/." "$SYNC_DIR/" 2>/dev/null; }; return 0; }
drop() { $PY -m memprof.iostat drop >/dev/null 2>&1; }   # drop_caches, or fadvise eviction where /proc/sys is read-only
export PATH=/usr/lib/wsl/lib:$PATH
log() { echo "[$(date +%T)] $*" | tee -a "$OUT/suite.log"; }

stack() {  # (re)start llama-server + proxy with the current env; embedder only if not up
  curl -sf http://127.0.0.1:8001/health >/dev/null || $L emb >>"$OUT/suite.log" 2>&1 || { log "embedder failed"; exit 1; }
  $L llm >>"$OUT/suite.log" 2>&1 || { log "LLM failed: $(tail -3 results/server_logs/llm.log)"; exit 1; }
  $L proxy >>"$OUT/suite.log" 2>&1 || { log "proxy failed"; exit 1; }
}
rates() {  # rates <profile>: llama-bench with the same model / KV type / offload flags as the server
  local p=$1 n=rates_$1
  [ -s "$OUT/$n/llama_bench.json" ] && { log "skip $n"; return 0; }
  ( export PROFILE=$p; source scripts/local/profiles.sh
    [ -s "$LLM_GGUF" ] || { log "skip $n (model not downloaded)"; exit 0; }
    mkdir -p "$OUT/$n"; $L stop >/dev/null   # the bench needs the whole card
    local d=0 x; for x in 2048 4096 8192 12288 16384; do [ $x -lt "$P_CTX" ] && d="$d,$x"; done; d=${RATE_DEPTHS:-$d}
    log "=== $n depths $d"
    "${LLAMA_BIN:-$HOME/llama.cpp/build/bin}/llama-bench" -m "$LLM_GGUF" -ngl "$P_NGL" -fa 1 -ctk "$P_KV" -ctv "$P_KV" \
      $P_BENCH -p 512 -n 64 -d "$d" -r "${RATE_REPS:-3}" -o json >"$OUT/$n/llama_bench.json" 2>"$OUT/$n/llama_bench.err" \
      || log "rates $p failed: $(tail -2 "$OUT/$n/llama_bench.err")"
    nvidia-smi --query-gpu=name,memory.total,clocks.max.sm,power.limit --format=csv >"$OUT/$n/gpu.csv" 2>/dev/null
    $PY -c "import json,sys; [print(f\"  d={r['n_depth']:6d} {'pp' if r['n_prompt'] else 'tg'} {r['avg_ts']:8.1f} tok/s\") for r in json.load(open(sys.argv[1]))]" \
      "$OUT/$n/llama_bench.json" 2>/dev/null | tee -a "$OUT/suite.log" )
}
fresh_stores() { scripts/services.sh reset all >/dev/null 2>&1; scripts/services.sh start all >/dev/null 2>&1 || { log "services failed"; return 1; }; }

run() {  # run <name> <system> [args...]
  local name=$1${REP:+_r$REP} sys=$2; shift 2
  [ -f "$OUT/$name/meta.json" ] && { log "skip $name"; return 0; }
  log "=== $name ($sys) PROFILE=$PROFILE"
  fresh_stores || return 1
  drop   # every run starts from the same (cold store) state
  $PY bench/multi_e2e.py --system "$sys" --conv "$CONV" --out "$OUT/$name" --label "$name" "$@" >"$OUT/$name.log" 2>&1
  local rc=$?
  cp results/server_logs/llm.cmd results/server_logs/llm.load.json "$OUT/$name/" 2>/dev/null
  echo "boot=$BOOT gpu=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1) profile=$PROFILE" >"$OUT/$name/vm.txt" 2>/dev/null
  if [ $rc -ne 0 ]; then log "FAILED $name rc=$rc: $(tail -3 "$OUT/$name.log" | tr '\n' ' ')"; return 0; fi
  $PY analysis/multi_breakdown.py "$OUT/$name" >/dev/null 2>&1
  log "done $name: $(tail -1 "$OUT/$name.log")"
  sync_out
}

for suite in "$@"; do case $suite in
  preflight)  # once per VM (a new Colab runtime may be a different machine / disk): preflight_<boot id>
    P=$OUT/preflight_$BOOT
    [ -f "$P/inventory.json" ] || PREFLIGHT_DIR=$P OUT=$OUT PY=$PY scripts/local/preflight.sh | tee -a "$OUT/suite.log"
    rm -rf "$OUT/preflight"; cp -r "$P" "$OUT/preflight"; sync_out ;;
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
      [ $temp = cold ] && drop
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
  rates) rates "$PROFILE"; stack ;;
  model)
    for p in $PROFILE ${L4_PROFILES:-q8b llama8b moe30b}; do
      runs=$(ls -d "$OUT"/l1_${p}_*_sync* "$OUT"/l4_${p}_*_sync* 2>/dev/null)
      [ -n "$runs" ] && [ -s "$OUT/rates_$p/llama_bench.json" ] || continue
      extra=(); for g in ${MODEL_GPU:-}; do extra+=(--gpu "$g"); done; for d in ${MODEL_DISK:-}; do extra+=(--disk "$d"); done
      $PY analysis/latency_model.py --runs $runs --rates "$OUT/rates_$p/llama_bench.json" --fio "$OUT/preflight/fio_fsyncwrite.json" \
        "${extra[@]}" --out "$OUT/latency_model_$p.json" >"$OUT/latency_model_$p.md" 2>&1 && log "model $p -> latency_model_$p.md"
    done ;;
  lme) stack
      for it in ${LME_ITEMS:-70 233 366}; do for s in ${LME_SYSTEMS:-$SYSTEMS}; do
        run "lme_${PROFILE}_${s}_i${it}_t${LME_TURNS:-0}" "$s" --dataset longmemeval --item "$it" --turns "${LME_TURNS:-0}" --qa 1
      done; done ;;
  score) stack
      for d in "$OUT"/*/; do [ -f "$d/qa.json" ] && [ ! -f "$d/qa_score.json" ] && $PY analysis/qa_score.py "$d" >>"$OUT/suite.log" 2>&1; done
      $PY analysis/qa_score.py --summary "$OUT" | tee "$OUT/qa_summary.md"; sync_out ;;
  budget) $PY analysis/budget.py "$OUT" | tee "$OUT/budget.md"; sync_out ;;
  pilot)
    OUT=$OUT "$SELF" preflight rates kv
    TURNS=${PILOT_TURNS:-20} QA=${PILOT_QA:-10} OUT=$OUT "$SELF" l1
    LME_ITEMS=${PILOT_LME_ITEMS:-0} LME_TURNS=${PILOT_LME_TURNS:-60} OUT=$OUT "$SELF" lme
    OUT=$OUT "$SELF" score budget ;;
  l1) stack; for s in $SYSTEMS; do run "l1_${PROFILE}_${s}_sync_t$TURNS" "$s" --turns "$TURNS" --qa "$QA"; done ;;
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
        rates "$p"
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
sync_out
log "suite done -> $OUT"
