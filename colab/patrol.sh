#!/usr/bin/env bash
# Claude's side of an unattended Colab CLI run (colab/cli_bootstrap.py on the VM).
#   colab/patrol.sh [SESSION]      default SESSION=memprof
# 1. CU balance / rate and session status
# 2. download /content/outbox/status/* (status.json, status.md, suite.log, setup.log, keepalive.log, summaries)
# 3. download every run tarball not yet here, unpack to results/colab/<tag>/<run>/
# 4. upload the list of runs held here as /content/inbox/ack.txt (the VM releases only when all are acked)
# Prints a short report; exit 2 if the session is gone. Commit results/colab afterwards.
set -uo pipefail
cd "$(dirname "$0")/.."
export PATH=$HOME/.local/bin:$PATH OAUTHLIB_RELAX_TOKEN_SCOPE=1
S=${1:-memprof}
D=${DEST:-results/colab}
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

colab usage 2>&1 | grep -E "balance|rate|assignments"
if ! colab status -s "$S" >"$TMP/st" 2>&1 || grep -qi "not found" "$TMP/st"; then
  echo "session $S: GONE"; cat "$TMP/st"; exit 2
fi
mkdir -p "$TMP/s"
for f in status.json status.md suite.log setup.log keepalive.log vm_client.log exec_vm.log qa_summary.md budget.md breakdown.md \
         queue_state.json; do   # queue_state.json: a relaunched runtime restores it (cli_bootstrap.py)
  colab download -s "$S" "/content/outbox/status/$f" "$TMP/s/$f" >/dev/null 2>&1
done
[ -s "$TMP/s/status.json" ] || { echo "no status yet (bootstrap starting?)"; exit 0; }
tag=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['tag'])" "$TMP/s/status.json")
mkdir -p "$D/$tag/_status"
cp "$TMP/s/"* "$D/$tag/_status/"
for r in $(python3 -c "import json,sys; print(' '.join(json.load(open(sys.argv[1])).get('outbox_runs', [])))" "$TMP/s/status.json"); do
  if [[ $r == *+late* ]]; then   # files a packed run gained later (scores): unpack into the run dir
    grep -qx "$r" "$D/$tag/_status/late_fetched.txt" 2>/dev/null && continue
  else
    [ -d "$D/$tag/$r" ] && continue
  fi
  if colab download -s "$S" "/content/outbox/runs/$r.tar.gz" "$TMP/$r.tar.gz" >/dev/null 2>&1 \
     && tar xzf "$TMP/$r.tar.gz" -C "$D/$tag/" && [ -d "$D/$tag/${r%+late*}" ]; then
    [[ $r == *+late* ]] && echo "$r" >>"$D/$tag/_status/late_fetched.txt"
    echo "fetched $r"
  else
    echo "FETCH FAILED $r"
  fi
done
{ ls -d "$D/$tag"/*/ 2>/dev/null | xargs -rn1 basename | grep -v '^_status$'
  cat "$D/$tag/_status/late_fetched.txt" 2>/dev/null; } >"$TMP/ack.txt"
colab upload -s "$S" "$TMP/ack.txt" /content/inbox/ack.txt >/dev/null 2>&1 || echo "ACK UPLOAD FAILED"
python3 - "$TMP/s/status.json" <<'PY'
import json, sys
s = json.load(open(sys.argv[1]))
print(f"{s['time']} phase={s['phase']} line={s['current_line']} try={s['attempt']} run={s['current_run']}")
print(f"  up {s['runtime_up_h']} h, {s['hours_since_start']} h since start (cap {s['max_hours']}), "
      f"last write {s['minutes_since_last_write']} min ago, suite alive {s['suite_alive']}")
print(f"  queue {s['queue']} done {s['done']} gave_up {s['gave_up']}  finished runs {len(s['finished_runs'])}")
print(f"  backup {s['backup']}  disk {s['disk_free_gb']} GB  RAM {s['ram_avail_gb']} GB  GPU {s['gpu']}")
for x in s["failed_lines"][-8:]:
    print("  !", x[:220])
PY
