#!/usr/bin/env bash
# Start an unattended run on a new Colab runtime from Claude's container.
#   colab/launch.sh SESSION GPU [--env K=V ...]     GPU: L4 | T4 | A100 | none (CPU, for tests)
# 1. colab new (retries "Service Unavailable")
# 2. upload the CLI's Colab-scoped OAuth token to /content/_ka_*
# 3. short colab exec of colab/vm_start.py (with the --env args, which stay in the kernel): clones the repo and starts
#    colab/vm_client.sh detached on the VM
# 4. upload this session's CLI state; vm_client.sh then runs colab/cli_bootstrap.py in the same kernel with the CLI
#    on the VM, so the kernel keeps a connected client while Claude's container is paused (GPU runtimes were
#    reclaimed ~20 min after the client in Claude's container lost its connection)
# The token stays on Colab's VM and is deleted before the VM releases itself.
set -uo pipefail
cd "$(dirname "$0")/.."
export PATH=$HOME/.local/bin:$PATH OAUTHLIB_RELAX_TOKEN_SCOPE=1
S=$1; GPU=$2; shift 2
CLIPY=$HOME/.local/share/uv/tools/google-colab-cli/bin/python
LOGDIR=${LOGDIR:-/tmp/colab_$S}; mkdir -p "$LOGDIR"
st=$(colab status -s "$S" 2>&1)   # exits 0 even when the session does not exist
if grep -qi "not found" <<<"$st"; then
  for i in 1 2 3 4 5 6; do
    if [ "$GPU" = none ]; then colab new -s "$S" && break; else colab new -s "$S" --gpu "$GPU" && break; fi
    echo "colab new failed (try $i), retrying in 60 s"; sleep 60
  done
fi
EP=$("$CLIPY" -c "import sys; from colab_cli.state import StateStore; print(StateStore(None).get(sys.argv[1]).endpoint)" "$S") \
  || { echo "no session $S"; exit 1; }
echo "session $S endpoint $EP"
colab upload -s "$S" "$HOME/.local/share/python_keyring/keyring_pass.cfg" /content/_ka_keyring_pass.cfg >/dev/null \
  && colab upload -s "$S" "$HOME/.config/python_keyring/keyringrc.cfg" /content/_ka_keyringrc.cfg >/dev/null \
  || { echo "token upload failed"; exit 1; }
colab exec -s "$S" -f colab/vm_start.py --env COLAB_ENDPOINT="$EP" --env COLAB_SESSION="$S" "$@" \
  >"$LOGDIR/start.log" 2>&1 || { echo "start exec failed"; cat "$LOGDIR/start.log"; exit 1; }
tail -2 "$LOGDIR/start.log"
"$CLIPY" - "$S" "$LOGDIR/sessions.json" <<'PY'
import json, sys
d = json.load(open("/root/.config/colab-cli/sessions.json"))
s = dict(d[sys.argv[1]], running=None)
assert s.get("kernel_id"), "no kernel id after the start exec"
json.dump({sys.argv[1]: s}, open(sys.argv[2], "w"))
PY
colab upload -s "$S" "$LOGDIR/sessions.json" /content/_ka_sessions.json >/dev/null || { echo "state upload failed"; exit 1; }
rm -f "$LOGDIR/sessions.json"
echo "started; VM client log /content/outbox/status/vm_client.log, kernel output exec_vm.log"
