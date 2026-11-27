"""Unattended Colab run driven from the Colab CLI (no notebook UI, no Drive, no GitHub token on the VM).

    colab new -s memprof --gpu L4
    colab exec -s memprof -f colab/cli_bootstrap.py --timeout 0 --env MAX_HOURS=5 --env CU_PER_HOUR=...

Runs in the kernel, so the VM counts as busy for as long as the experiments run. Steps:
  1. clone / pull the code branch (public repo), start the supervisor's watchdog (MAX_HOURS cap from now, remote stop)
  2. scripts/local/setup.sh (models for DL_PROFILES only); on failure wait up to SETUP_FIX_MIN for a pushed fix
     (new commit on the branch) and retry, at most 3 times; otherwise release the runtime
  3. colab/supervisor.py main loop over colab/queue.txt
Results leave the VM through /content/outbox (status + one tarball per finished run), fetched by colab/patrol.sh,
which acknowledges them in /content/inbox/ack.txt; the runtime is only released once everything is acknowledged
(or ACK_WAIT_MIN has passed).
"""
from __future__ import annotations

import importlib.util
import os
import glob
import shutil
import subprocess
import time

E = os.environ.get
os.makedirs("/content/outbox/status", exist_ok=True)
open("/content/outbox/status/bootstrap_started", "a").write(f"{time.time()}\n")   # colab/vm_client.sh: never twice
os.environ.setdefault("MEMPROF_T0", str(time.time()))
BRANCH = E("MEMPROF_BRANCH", "claude/gifted-maxwell-td8cnz")
REPO = E("MEMPROF_REPO_DIR", "/content/Agent_Mem_Sys")
URL = E("MEMPROF_REPO_URL", "https://github.com/envymoon/Agent_Mem_Sys.git")
try:
    gpu = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], capture_output=True,
                         text=True).stdout.strip().splitlines()
except FileNotFoundError:
    gpu = []
tag = (gpu[0].replace("NVIDIA ", "").replace(" ", "") if gpu else "cpu")
for k, v in {"HOME": "/root", "MEMPROF_MODELS": "/root/models", "OUT": f"/content/results/{tag}",
             "PROFILE": "gptoss20b", "L4_PROFILES": "q14b q4b", "SYNC_DIR": "", "STATUS_GITHUB": "0",
             "MAX_HOURS": "5", "ACK_WAIT_MIN": "75", "IDLE_MIN": "15"}.items():
    os.environ.setdefault(k, v)
os.environ.setdefault("DL_PROFILES", E("PROFILE"))
os.makedirs(E("OUT"), exist_ok=True)

sup = None
CRED_FILES = ["/root/.local/share/python_keyring/keyring_pass.cfg", "/root/.config/python_keyring/keyringrc.cfg"]


def start_vm_keepalive() -> str:
    """Ping this runtime's keep-alive endpoint from the VM itself.

    Without a browser or a connected `colab exec` client the runtime is reclaimed ~20 min later even while the kernel
    is busy, and Claude's container (where `colab exec` runs) is paused between turns. Claude uploads the CLI's
    Colab-scoped OAuth token (CRED_FILES) and passes COLAB_ENDPOINT; this installs the CLI in its own tool venv and
    runs colab/keepalive.py. The token dies with the VM; supervisor.finish() also deletes it before releasing.
    """
    import shutil
    for f in CRED_FILES:   # colab/launch.sh uploads them as /content/_ka_<name> (upload needs an existing dir)
        src = "/content/_ka_" + os.path.basename(f)
        if os.path.exists(src):
            os.makedirs(os.path.dirname(f), exist_ok=True)
            shutil.move(src, f)
            os.chmod(f, 0o600)
    ep = E("COLAB_ENDPOINT")
    if not ep or not os.path.exists(CRED_FILES[0]):
        return "off (no COLAB_ENDPOINT or no uploaded token)"
    py = "/root/.local/share/uv/tools/google-colab-cli/bin/python"
    if not os.path.exists(py):
        r = subprocess.run(["uv", "tool", "install", "-q", f"google-colab-cli=={E('COLAB_CLI_VERSION', '0.8.0')}",
                            "--with", "keyrings.alt"], capture_output=True, text=True)
        if r.returncode:
            return f"install failed: {r.stderr[-300:]}"
    os.makedirs("/content/outbox/status", exist_ok=True)
    log = open("/content/outbox/status/keepalive.log", "a")
    p = subprocess.Popen([py, os.path.join(REPO, "colab", "keepalive.py"), "--endpoint", ep,
                          E("KEEPALIVE_S", "240")], stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                         env={**os.environ, "OAUTHLIB_RELAX_TOKEN_SCOPE": "1"}, start_new_session=True)
    time.sleep(20)
    return f"pid {p.pid}" if p.poll() is None else f"exited rc={p.returncode} (see keepalive.log)"


def restore_finished() -> None:
    """A new runtime starts with an empty OUT. Copy the runs Claude already downloaded and committed
    (results/colab/<tag>/<run>/meta.json) back into OUT, so the suite skips them instead of redoing them,
    and the queue state, so finished queue lines are not rerun."""
    src = os.path.join(REPO, "results", "colab", tag)
    n = 0
    for m in glob.glob(os.path.join(src, "*", "meta.json")):
        r = os.path.basename(os.path.dirname(m))
        if not os.path.exists(os.path.join(E("OUT"), r)):
            shutil.copytree(os.path.dirname(m), os.path.join(E("OUT"), r))
            n += 1
    q = os.path.join(src, "_status", "queue_state.json")
    if os.path.exists(q) and not os.path.exists(os.path.join(E("OUT"), "queue_state.json")):
        shutil.copy(q, E("OUT"))
    print(f"restored {n} finished runs from {src}", flush=True)


def _main() -> None:
    global sup
    if not os.path.isdir(os.path.join(REPO, ".git")):
        subprocess.run(["git", "clone", "-q", "-b", BRANCH, URL, REPO], check=True)
    else:
        subprocess.run(["git", "-C", REPO, "pull", "-q", "--ff-only", "origin", BRANCH])
    os.chdir(REPO)
    restore_finished()
    ka = start_vm_keepalive()

    spec = importlib.util.spec_from_file_location("supervisor", os.path.join(REPO, "colab", "supervisor.py"))
    sup = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sup)
    os.makedirs(sup.INBOX, exist_ok=True)
    sup.start_watchdog()
    import threading
    threading.Thread(target=sup.reporter, daemon=True).start()   # status every REPORT_MIN during setup too
    sup.event(f"bootstrap: gpu={gpu} OUT={E('OUT')} PROFILE={E('PROFILE')} DL_PROFILES={E('DL_PROFILES')} "
              f"cap={E('MAX_HOURS')} h keepalive={ka}")

    ok = E("SKIP_SETUP") == "1"   # testing the CLI path only
    for attempt in range(1, 4 if not ok else 1):
        sup.NOW["phase"] = f"setup attempt {attempt}"
        sup.report()
        log = os.path.join(sup.OUTBOX, "status", "setup.log")
        os.makedirs(os.path.dirname(log), exist_ok=True)
        t = time.time()
        with open(log, "a") as f:
            head_start = sup.pull_code()
            f.write(f"\n===== setup attempt {attempt} at {sup.now()} code {head_start}\n")
            f.flush()
            try:
                rc = subprocess.run(["bash", "scripts/local/setup.sh"], stdout=f, stderr=subprocess.STDOUT,
                                    timeout=float(E("SETUP_TIMEOUT_MIN", 120)) * 60).returncode
            except subprocess.TimeoutExpired:
                rc = 124
        sup.event(f"setup attempt {attempt}: rc={rc} in {(time.time() - t) / 60:.1f} min")
        os.environ["SESSION_SETUP_MIN"] = f"{(time.time() - t) / 60:.0f}"
        if rc == 0:
            ok = True
            break
        if sup.NOW["stop"]:
            break
        sup.NOW["phase"] = f"setup failed (attempt {attempt}): waiting for a fix"
        sup.report()
        t = time.time()   # retry as soon as the branch has moved past the code this attempt ran
        while time.time() - t < float(E("SETUP_FIX_MIN", 30)) * 60 and sup.pull_code() == head_start \
                and not sup.NOW["stop"]:
            time.sleep(120)
        if sup.pull_code() == head_start:
            break

    if ok:
        sup.entry()
    elif not sup.NOW["stop"]:
        sup.finish("setup failed")


try:
    _main()
except BaseException as e:  # never leave a paid VM idle: report the crash, then release
    import traceback
    os.makedirs("/content/outbox/status", exist_ok=True)
    open("/content/outbox/status/bootstrap_error.txt", "w").write(traceback.format_exc())
    if isinstance(e, KeyboardInterrupt):
        raise
    if sup is not None:
        sup.event(f"bootstrap crashed: {e!r}"[:300])
        sup.finish("bootstrap crashed")
    else:
        for f in CRED_FILES:
            if os.path.exists(f):
                os.remove(f)
        from google.colab import runtime  # type: ignore
        runtime.unassign()
