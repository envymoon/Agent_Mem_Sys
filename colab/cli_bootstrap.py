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
import subprocess
import time

E = os.environ.get
os.environ.setdefault("MEMPROF_T0", str(time.time()))
BRANCH = E("MEMPROF_BRANCH", "claude/gifted-maxwell-td8cnz")
REPO = E("MEMPROF_REPO_DIR", "/content/Agent_Mem_Sys")
URL = E("MEMPROF_REPO_URL", "https://github.com/envymoon/Agent_Mem_Sys.git")
gpu = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], capture_output=True,
                     text=True).stdout.strip().splitlines()
tag = (gpu[0].replace("NVIDIA ", "").replace(" ", "") if gpu else "cpu")
for k, v in {"HOME": "/root", "MEMPROF_MODELS": "/root/models", "OUT": f"/content/results/{tag}",
             "PROFILE": "gptoss20b", "L4_PROFILES": "q14b q4b", "SYNC_DIR": "", "STATUS_GITHUB": "0",
             "MAX_HOURS": "5", "ACK_WAIT_MIN": "60", "IDLE_MIN": "15"}.items():
    os.environ.setdefault(k, v)
os.environ.setdefault("DL_PROFILES", E("PROFILE"))
os.makedirs(E("OUT"), exist_ok=True)

if not os.path.isdir(os.path.join(REPO, ".git")):
    subprocess.run(["git", "clone", "-q", "-b", BRANCH, URL, REPO], check=True)
else:
    subprocess.run(["git", "-C", REPO, "pull", "-q", "--ff-only", "origin", BRANCH])
os.chdir(REPO)

spec = importlib.util.spec_from_file_location("supervisor", os.path.join(REPO, "colab", "supervisor.py"))
sup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sup)
os.makedirs(sup.INBOX, exist_ok=True)
sup.start_watchdog()
sup.event(f"bootstrap: gpu={gpu} OUT={E('OUT')} PROFILE={E('PROFILE')} DL_PROFILES={E('DL_PROFILES')} "
          f"cap={E('MAX_HOURS')} h")

ok = E("SKIP_SETUP") == "1"   # testing the CLI path only
for attempt in range(1, 4 if not ok else 1):
    sup.NOW["phase"] = f"setup attempt {attempt}"
    sup.report()
    log = os.path.join(sup.OUTBOX, "status", "setup.log")
    os.makedirs(os.path.dirname(log), exist_ok=True)
    t = time.time()
    with open(log, "a") as f:
        f.write(f"\n===== setup attempt {attempt} at {sup.now()} code {sup.pull_code()}\n")
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
    head0 = sup.pull_code()
    sup.NOW["phase"] = f"setup failed (attempt {attempt}): waiting for a fix"
    sup.report()
    t = time.time()
    while time.time() - t < float(E("SETUP_FIX_MIN", 30)) * 60 and sup.pull_code() == head0 and not sup.NOW["stop"]:
        time.sleep(120)
    if sup.pull_code() == head0:
        break

if ok:
    sup.entry()
elif not sup.NOW["stop"]:
    sup.finish("setup failed")
