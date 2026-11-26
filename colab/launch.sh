#!/usr/bin/env bash
# Start an unattended run on a new Colab runtime from Claude's container.
#   colab/launch.sh SESSION GPU [--env K=V ...]     GPU: L4 | T4 | A100 | none (CPU, for tests)
# 1. colab new (retries "Service Unavailable")
# 2. upload the CLI's Colab-scoped OAuth token to /content/_ka_* so the VM can ping its own keep-alive endpoint
#    (Claude's container is paused between turns; a runtime nobody pings is reclaimed after ~20 min)
# 3. colab exec colab/cli_bootstrap.py in the background with COLAB_ENDPOINT, log in $LOGDIR/exec.log
# The token never leaves Colab's own VM and is deleted before the VM releases itself.
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
nohup colab exec -s "$S" -f colab/cli_bootstrap.py --timeout 0 --env COLAB_ENDPOINT="$EP" "$@" \
  >"$LOGDIR/exec.log" 2>&1 &
echo "exec pid $! log $LOGDIR/exec.log"
