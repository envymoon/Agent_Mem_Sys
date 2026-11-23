#!/usr/bin/env bash
# Hardware inventory + storage baseline of THIS machine (run before any experiment; root).
#   OUT=results/local/<host> scripts/local/preflight.sh
# Writes $OUT/preflight/{inventory.json, fio_*.json, cache_check.json} and prints a summary + suggested PROFILE.
#
# Storage baseline (fio, on the directory that holds the stores, direct I/O):
#   seqread 1M QD8, randread 4k QD1 (latency a cold HNSW/page-cache miss pays), randwrite 4k QD1 + fsync each
#   write (what a durable commit pays: Postgres WAL, Neo4j tx log, SQLite).
# Page-cache check: write 2 GB, drop the (guest) page cache, read it back buffered. On WSL2 a read speed far above
# the fio direct seqread means the Windows host is still caching the VHDX -> "cold" numbers are only guest-cold.
set -uo pipefail
cd "$(dirname "$0")/../.."
OUT=${OUT:-results/local/$(hostname)}
D=$OUT/preflight; mkdir -p "$D"
SVC_DATA=${SVC_DATA:-/opt/svc/data}; mkdir -p "$SVC_DATA"
T=$SVC_DATA/_fio; mkdir -p "$T"
export PATH=/usr/lib/wsl/lib:$PATH

{
  echo "{"
  echo "\"kernel\": \"$(uname -r)\", \"wsl\": $(grep -qi microsoft /proc/version && echo true || echo false),"
  echo "\"cpu\": \"$(lscpu | sed -n 's/^Model name:\s*//p' | head -1)\", \"cores\": $(nproc),"
  echo "\"ram_gb\": $(awk '/MemTotal/{printf "%.1f", $2/1048576}' /proc/meminfo), \"swap_gb\": $(awk '/SwapTotal/{printf "%.1f", $2/1048576}' /proc/meminfo),"
  if nvidia-smi >/dev/null 2>&1; then
    q=$(nvidia-smi --query-gpu=name,memory.total,memory.used,driver_version,pcie.link.gen.max,pcie.link.width.max,power.limit --format=csv,noheader,nounits | head -1)
    IFS=, read -r n mt mu dv pg pw pl <<<"$q"
    echo "\"gpu\": \"${n# }\", \"vram_mb\": ${mt# }, \"vram_used_mb_idle\": ${mu# }, \"driver\": \"${dv# }\", \"pcie_gen\": \"${pg# }\", \"pcie_width\": \"${pw# }\", \"power_limit_w\": \"${pl# }\","
  else echo "\"gpu\": null,"; fi
  src=$(df --output=source "$SVC_DATA" | tail -1); fs=$(df --output=fstype "$SVC_DATA" | tail -1)
  echo "\"data_dir\": \"$SVC_DATA\", \"data_fs\": \"$fs\", \"data_dev\": \"$src\","
  echo "\"block_devices\": $(lsblk -J -d -o NAME,MODEL,SIZE,ROTA,TRAN 2>/dev/null || echo null),"
  echo "\"data_free_gb\": $(df -BG --output=avail "$SVC_DATA" | tail -1 | tr -dc 0-9)"
  echo "}"
} >"$D/inventory.json"
jq . "$D/inventory.json" 2>/dev/null || cat "$D/inventory.json"

if command -v fio >/dev/null; then
  f() { fio --name="$1" --directory="$T" --size=2G --direct=1 --ioengine=libaio --runtime=20 --time_based \
        --group_reporting --output-format=json "${@:2}" >"$D/fio_$1.json" 2>/dev/null; }
  f seqread  --rw=read --bs=1M --iodepth=8
  f randread --rw=randread --bs=4k --iodepth=1
  f fsyncwrite --rw=randwrite --bs=4k --iodepth=1 --fsync=1 --size=256M
  python3 - "$D" <<'PY'
import json, sys, os
d = sys.argv[1]
for n in ("seqread", "randread", "fsyncwrite"):
    try:
        j = json.load(open(os.path.join(d, f"fio_{n}.json")))["jobs"][0]
    except Exception as e:
        print(n, "fio failed", e); continue
    io = j["read"] if n != "fsyncwrite" else j["write"]
    lat = io.get("clat_ns", {}).get("percentile", {})
    extra = ""
    if n == "fsyncwrite":
        s = j.get("sync", {}).get("lat_ns", {})
        extra = f" fsync p50={s.get('percentile', {}).get('50.000000', 0)/1e3:.0f}us p99={s.get('percentile', {}).get('99.000000', 0)/1e3:.0f}us"
    print(f"  fio {n:10s} {io['bw']/1024:8.0f} MB/s  {io['iops']:8.0f} IOPS  clat p50={lat.get('50.000000', 0)/1e3:.0f}us p99={lat.get('99.000000', 0)/1e3:.0f}us{extra}")
PY
fi

# page-cache / host-cache check
dd if=/dev/urandom of="$T/cachecheck" bs=1M count=2048 status=none conv=fsync
sync; echo 3 >/proc/sys/vm/drop_caches 2>/dev/null && dropped=true || dropped=false
t0=$(date +%s.%N); dd if="$T/cachecheck" of=/dev/null bs=1M status=none; t1=$(date +%s.%N)
t2=$(date +%s.%N); dd if="$T/cachecheck" of=/dev/null bs=1M status=none; t3=$(date +%s.%N)
python3 -c "
import json; c=2048/($t1-$t0); w=2048/($t3-$t2)
json.dump({'dropped': $dropped, 'cold_buffered_mb_s': c, 'warm_mb_s': w}, open('$D/cache_check.json','w'))
print(f'  page cache: cold read {c:.0f} MB/s (after drop_caches=$dropped), warm read {w:.0f} MB/s')"
rm -rf "$T"

python3 - "$D/inventory.json" <<'PY'
import json, sys
j = json.load(open(sys.argv[1]))
v, r = j.get("vram_mb") or 0, j["ram_gb"]
prof = "cpu" if not v else "q4b"
print(f"\nsuggested: PROFILE={prof} (main).  q8b/llama8b {'OK' if v >= 7800 else 'may not fit'};"
      f" moe30b {'OK' if r >= 30 else 'needs >= 32 GB RAM (WSL: raise memory= in .wslconfig)'}")
if j.get("wsl"):
    print(f"WSL: the VM sees {r} GB RAM (default = 50% of the host); raise memory= in %UserProfile%\\.wslconfig for moe30b / DRAM-tier runs.")
PY
