#!/usr/bin/env bash
# Runs detached on the Colab VM (started by colab/vm_start.py): the colab CLI client for this runtime's kernel.
# 1. wait for the token + session state uploaded by colab/launch.sh, put them where the CLI looks, install the CLI
# 2. colab exec colab/cli_bootstrap.py in the kernel (output -> /content/outbox/status/exec_vm.log)
# 3. if that client returns (connection lost, or the bootstrap cell ended), re-attach with a trivial exec, which
#    queues behind the running cell and keeps a client connected, until the runtime is gone
set -u
S=${1:-memprof}
export HOME=/root OAUTHLIB_RELAX_TOKEN_SCOPE=1 PATH=/root/.local/bin:$PATH
R=$(cd "$(dirname "$0")/.." && pwd)
OUTLOG=/content/outbox/status/exec_vm.log
log() { echo "[$(date -u '+%F %T')Z] $*"; }
for i in $(seq 120); do [ -f /content/_ka_sessions.json ] && break; sleep 5; done
mkdir -p /root/.local/share/python_keyring /root/.config/python_keyring /root/.config/colab-cli
for f in keyring_pass.cfg:/root/.local/share/python_keyring keyringrc.cfg:/root/.config/python_keyring \
         sessions.json:/root/.config/colab-cli; do
  src=/content/_ka_${f%%:*}; dst=${f#*:}/${f%%:*}
  [ -f "$src" ] && mv "$src" "$dst" && chmod 600 "$dst"
done
[ -f /root/.config/colab-cli/sessions.json ] || { log "no session state uploaded; giving up"; exit 1; }
echo '{"enable_update_check": false}' >/root/.config/colab-cli/settings.json
command -v colab >/dev/null || uv tool install -q "google-colab-cli==${COLAB_CLI_VERSION:-0.8.0}" --with keyrings.alt \
  || { log "CLI install failed"; exit 1; }
log "client up; running the bootstrap"
colab exec -s "$S" -f "$R/colab/cli_bootstrap.py" --timeout 0 >>"$OUTLOG" 2>&1
log "bootstrap client returned rc=$?"
while true; do
  if [ -f /content/outbox/status/bootstrap_started ]; then
    echo 'print("client re-attached")' | colab exec -s "$S" --timeout 0 >>"$OUTLOG" 2>&1
  else   # the first client failed before the bootstrap began
    colab exec -s "$S" -f "$R/colab/cli_bootstrap.py" --timeout 0 >>"$OUTLOG" 2>&1
  fi
  rc=$?
  log "re-attach client returned rc=$rc"
  colab status -s "$S" 2>&1 | grep -qi "not found" && { log "session gone"; exit 0; }
  sleep 30
done
