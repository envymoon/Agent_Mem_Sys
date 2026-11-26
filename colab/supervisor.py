"""Colab supervisor: runs the experiment queue unattended and reports to GitHub so it can be monitored remotely.

Run inside the notebook kernel (`%run colab/supervisor.py`); the cell blocks until the queue is done.

  queue     colab/queue.txt on the code branch, one suite invocation per line (e.g. "pilot", "l1 lme score").
            A line's identity is its full text: append "  # retry 2" to re-run a line that already finished/gave up.
            Done / given-up lines are recorded on Drive ($SYNC_DIR/queue_state.json), so a new runtime continues.
  retries   before every attempt the code branch is pulled (fast-forward only), so a pushed fix is picked up.
            An attempt fails if the suite exits non-zero, a run logged FAILED / TIMEOUT and still has no meta.json, or
            nothing was written for STALL_MIN minutes (the suite is then killed). MAX_TRIES attempts per line.
  backup    every finished run is mirrored to Drive by the suite; the supervisor verifies the copy (meta.json present,
            spans.jsonl same size), re-syncs if needed, and also pushes runs/<name>.tar.gz (run dir without the
            database store; < 50 MB) to the status branch -> a second copy outside Google.
  status    every REPORT_MIN minutes: <tag>/status.md + status.json + suite.log tail + summaries, pushed to the
            STATUS_BRANCH (default colab-status) of the same repo. Needs GH_TOKEN (Colab secret) with
            Contents read/write on this repository.
  idle      with nothing left to run, the queue is re-checked every 5 min; after IDLE_MIN minutes the final status is
            pushed, Drive is flushed and the runtime is released (AUTO_RELEASE=1), so no compute units burn idle.
"""
from __future__ import annotations

import datetime
import glob
import json
import os
import re
import shutil
import signal
import subprocess
import tarfile
import threading
import time

E = os.environ.get
REPO = E("MEMPROF_REPO_DIR", "/content/Agent_Mem_Sys")
BRANCH = E("MEMPROF_BRANCH", "claude/gifted-maxwell-td8cnz")
GH_REPO = E("MEMPROF_GH_REPO", "envymoon/Agent_Mem_Sys")
STATUS_BRANCH = E("STATUS_BRANCH", "colab-status")
OUT = E("OUT")
SYNC = E("SYNC_DIR", "")
TAG = os.path.basename(OUT.rstrip("/"))
SDIR = E("STATUS_DIR", "/content/_status_repo")
SUITE = E("SUITE_CMD", "scripts/local/run_local_suite.sh")   # override only for testing the supervisor
REPORT_MIN = float(E("REPORT_MIN", 10))
IDLE_MIN = float(E("IDLE_MIN", 20))
STALL_MIN = float(E("STALL_MIN", 45))
MAX_TRIES = int(E("MAX_TRIES", 3))
AUTO_RELEASE = E("AUTO_RELEASE", "1") == "1"
CU_PER_HOUR = float(E("CU_PER_HOUR", 0) or 0)
STATE_F = os.path.join(SYNC or OUT, "queue_state.json")
OUTBOX = E("OUTBOX", "/content/outbox")      # status + run tarballs for `colab download` (CLI mode: no Drive/GitHub)
INBOX = E("INBOX", "/content/inbox")         # ack.txt (runs Claude has downloaded), stop (finish now)
ACK_WAIT_MIN = float(E("ACK_WAIT_MIN", 60))  # before releasing: wait this long for the last runs to be backed up
MAX_HOURS = float(E("MAX_HOURS", 0) or 0)     # hard cap from MEMPROF_T0 (bootstrap start): stop + release
T0 = float(E("MEMPROF_T0", 0) or time.time())
LOCK = threading.Lock()
REPORT_LOCK = threading.Lock()
EVENTS: list[str] = []
NOW = {"line": None, "attempt": 0, "proc": None, "phase": "starting", "stop": None}
FINISH_LOCK = threading.Lock()


def now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def event(msg: str) -> None:
    line = f"[{now()}] {msg}"
    print(line, flush=True)
    with LOCK:
        EVENTS.append(line)
        del EVENTS[:-200]


def sh(cmd, cwd=None, timeout=300) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                           shell=isinstance(cmd, str))
        return p.returncode, (p.stdout + p.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def token() -> str | None:
    t = E("GH_TOKEN")
    if t:
        return t
    try:
        from google.colab import userdata  # type: ignore
        return userdata.get("GH_TOKEN")
    except Exception:
        return None


def redact(s: str) -> str:
    return re.sub(r"https://[^@\s]+@", "https://***@", s)


# ---------------------------------------------------------------- queue ----
def load_state() -> dict:
    try:
        return json.load(open(STATE_F))
    except Exception:
        return {"done": [], "gave_up": [], "tries": {}}


def save_state(st: dict) -> None:
    os.makedirs(os.path.dirname(STATE_F), exist_ok=True)
    json.dump(st, open(STATE_F + ".tmp", "w"), indent=1)
    os.replace(STATE_F + ".tmp", STATE_F)


def queue_lines() -> list[str]:
    try:
        L = [x.rstrip() for x in open(E("QUEUE_FILE") or os.path.join(REPO, "colab", "queue.txt"))]
    except FileNotFoundError:
        return []
    return [x for x in L if x.strip() and not x.lstrip().startswith("#")]


def pending(st: dict) -> list[str]:
    return [x for x in queue_lines() if x not in st["done"] and x not in st["gave_up"]]


def pull_code() -> str:
    rc, out = sh(["git", "pull", "-q", "--ff-only", "origin", BRANCH], cwd=REPO, timeout=120)
    head = sh(["git", "log", "--oneline", "-1"], cwd=REPO)[1]
    if rc:
        event(f"git pull failed (continuing with {head}): {redact(out)[-200:]}")
    return head


# ---------------------------------------------------------------- runs -----
DONE_MARKERS = ("meta.json",            # an experiment run (multi_e2e)
                "kv_tier.json",         # KV-tier micro-benchmark
                "gpu.csv",              # llama-bench rates (written after llama_bench.json)
                "cache_check.json",     # preflight (written last)
                "load.jsonl")           # model-load benchmark


def finished_runs() -> list[str]:
    """Result directories that are complete (each kind has a file written last), i.e. ready to back up."""
    return sorted({os.path.basename(os.path.dirname(p)) for m in DONE_MARKERS
                   for p in glob.glob(os.path.join(OUT, "*", m))})


def suite_log() -> list[str]:
    try:
        return open(os.path.join(OUT, "suite.log"), errors="ignore").read().splitlines()
    except FileNotFoundError:
        return []


def failed_since(n0: int) -> list[str]:
    """Runs that logged FAILED / TIMEOUT after line n0 of suite.log and still have no meta.json."""
    bad = []
    for line in suite_log()[n0:]:
        if re.search(r"\] (LLM failed|embedder failed|services failed|proxy failed|pilot: a step failed)", line):
            bad.append("(stack) " + line.split("] ", 1)[-1][:80])
            continue
        m = re.search(r"\] (?:FAILED|TIMEOUT) (\S+)", line)
        if m and not os.path.exists(os.path.join(OUT, m.group(1), "meta.json")):
            bad.append(m.group(1))
    return sorted(set(bad))


def last_write() -> float:
    """Newest mtime of the files that move while work progresses (not hw.jsonl: the sampler writes even when hung)."""
    pats = ["suite.log", "*.log", "*/spans.jsonl", "*/llm_calls.jsonl", "*/kv_tier.json", "*/llama_bench.json",
            "*/qa_score.json", "preflight_*/*"]
    ts = [os.path.getmtime(p) for pat in pats for p in glob.glob(os.path.join(OUT, pat))]
    return max(ts) if ts else time.time()


def suite_pids() -> list[str]:
    return sh(["pgrep", "-f", "^bash .*" + re.escape(os.path.basename(SUITE))])[1].split()


def kill(proc) -> None:
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        time.sleep(10)
        os.killpg(proc.pid, signal.SIGKILL)
    except Exception:
        pass
    sh(["bash", "scripts/local/start_llama.sh", "stop"], cwd=REPO, timeout=60)


def run_line(line: str) -> bool:
    suites = line.split("#")[0].split()
    n0 = len(suite_log())
    con = open(os.path.join(os.path.dirname(OUT.rstrip("/")), f"suite_console_{TAG}.log"), "a")
    p = subprocess.Popen(["bash", SUITE, *suites], cwd=REPO, stdout=con,
                         stderr=subprocess.STDOUT, start_new_session=True)
    NOW["proc"] = p
    while p.poll() is None:
        time.sleep(min(30, STALL_MIN * 20))
        idle = (time.time() - last_write()) / 60
        if idle > STALL_MIN:
            event(f"STALL: nothing written for {idle:.0f} min in '{line}' -> killing the suite")
            kill(p)
            NOW["proc"] = None
            return False
    NOW["proc"] = None
    bad = failed_since(n0)
    if p.returncode != 0 or bad:
        event(f"'{line}' attempt ended rc={p.returncode}; failed runs: {bad or '-'}")
        return False
    return True


# ---------------------------------------------------------------- backup ---
def drive_ok() -> tuple[bool, str]:
    if not SYNC:
        return False, "SYNC_DIR not set"
    if SYNC.startswith("/content/drive") and not os.path.ismount("/content/drive"):
        return False, "Drive not mounted"
    try:
        os.makedirs(SYNC, exist_ok=True)
        open(os.path.join(SYNC, ".heartbeat"), "w").write(now())
        return True, "ok"
    except Exception as e:
        return False, f"Drive not writable: {e!r}"[:200]


def drive_missing() -> list[str]:
    miss = []
    for r in finished_runs():
        a, b = os.path.join(OUT, r), os.path.join(SYNC, r)
        if not os.path.isdir(b) or not set(os.listdir(a)) <= set(os.listdir(b)):
            miss.append(r)
        elif os.path.exists(os.path.join(a, "spans.jsonl")) and (not os.path.exists(os.path.join(b, "spans.jsonl")) or
                                                                 os.path.getsize(os.path.join(a, "spans.jsonl")) !=
                                                                 os.path.getsize(os.path.join(b, "spans.jsonl"))):
            miss.append(r)
    return miss


def check_drive() -> dict:
    ok, why = drive_ok()
    miss = drive_missing() if ok else finished_runs()
    if ok and miss:
        rc, out = sh(f'cp -ru "{OUT}/." "{SYNC}/"', timeout=1800)
        miss2 = drive_missing()
        event(f"Drive was missing {len(miss)} run(s); re-synced (rc={rc}); still missing: {miss2 or '-'}")
        miss = miss2
    return {"ok": ok, "why": why, "missing_runs": miss}


def github_on() -> bool:
    return E("STATUS_GITHUB", "0") == "1" and os.path.isdir(os.path.join(SDIR, ".git"))


def acked() -> set[str]:
    try:
        return {x.strip() for x in open(os.path.join(INBOX, "ack.txt")) if x.strip()}
    except FileNotFoundError:
        return set()


def backup_state() -> dict:
    """Where every finished run has a copy outside this VM: Drive (verified), GitHub, or downloaded by Claude (ack)."""
    fin = finished_runs()
    if SYNC:
        drv = check_drive()
        return {"mode": "drive", "ok": drv["ok"], "why": drv["why"], "missing": drv["missing_runs"]}
    if github_on():
        return {"mode": "github", "ok": True, "why": "pushed with each report", "missing": []}
    a = acked()
    late = sorted(os.path.basename(f)[:-7] for f in glob.glob(os.path.join(OUTBOX, "runs", "*+late*.tar.gz")))
    return {"mode": "download+ack", "ok": True, "why": f"{len(a)} acked",
            "missing": [r for r in fin + late if r not in a]}


def late_bundle(r: str, d: str) -> str | None:
    """Files of an already packed run written after its tarball (the score step adds qa_score.json at the end of the
    suite): pack them as <run>+late<k>.tar.gz, which must be acknowledged like a run."""
    packed = glob.glob(os.path.join(d, r + ".tar.gz")) + glob.glob(os.path.join(d, r + "+late*.tar.gz"))
    base = max(os.path.getmtime(f) for f in packed)
    newer = [p for p in glob.glob(os.path.join(OUT, r, "**"), recursive=True)
             if os.path.isfile(p) and "/store/" not in p and os.path.getmtime(p) > base + 1]
    if not newer:
        return None
    name = f"{r}+late{len(packed)}"
    with tarfile.open(os.path.join(d, name + ".tar.gz"), "w:gz") as t:
        for p in newer:
            t.add(p, arcname=os.path.relpath(p, OUT))
    return name


def gh_backup(d: str | None = None) -> list[str]:
    """<name>.tar.gz for every finished run not yet packed (written once): GitHub status branch or the outbox."""
    d = d or os.path.join(SDIR, TAG, "runs")
    os.makedirs(d, exist_ok=True)
    new = []
    for r in finished_runs():
        f = os.path.join(d, r + ".tar.gz")
        if os.path.exists(f + ".toolarge"):
            continue
        if os.path.exists(f):
            if d.startswith(OUTBOX) and (n := late_bundle(r, d)):
                new.append(n)
            continue
        with tarfile.open(f, "w:gz") as t:
            t.add(os.path.join(OUT, r), arcname=r, filter=lambda ti: None if "/store" in ti.name else ti)
            for extra in (r + ".log", r + ".try1.log"):
                if os.path.exists(os.path.join(OUT, extra)):
                    t.add(os.path.join(OUT, extra), arcname=os.path.join(r, "_" + extra))
        sz = os.path.getsize(f)
        if sz > 50 * 2**20:
            os.remove(f)
            open(f + ".toolarge", "w").write(f"{sz} bytes compressed: only on Drive\n")
        new.append(r)
    return new


# ---------------------------------------------------------------- status ---
def gpu() -> str:
    return sh("nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total,power.draw "
              "--format=csv,noheader", timeout=20)[1]


def status_init() -> bool:
    if E("STATUS_GITHUB", "0") != "1":   # opt-in: the notebook (GH_TOKEN secret) sets it; CLI mode does not push
        return False
    t = token()
    if not t:
        event("no GH_TOKEN: status/backup to GitHub disabled (runs still go to Drive)")
        return False
    url = E("STATUS_REMOTE") or f"https://x-access-token:{t}@github.com/{GH_REPO}.git"
    if not os.path.isdir(os.path.join(SDIR, ".git")):
        rc, out = sh(["git", "clone", "-q", "--depth", "1", "-b", STATUS_BRANCH, url, SDIR], timeout=300)
        if rc:  # branch does not exist yet
            shutil.rmtree(SDIR, ignore_errors=True)
            os.makedirs(SDIR)
            sh(["git", "init", "-q", "-b", STATUS_BRANCH], cwd=SDIR)
            sh(["git", "remote", "add", "origin", url], cwd=SDIR)
            open(os.path.join(SDIR, "README.md"), "w").write(
                "Status and run backups pushed by colab/supervisor.py from the Colab runtime. Not code.\n")
    sh(["git", "config", "user.name", "memprof-colab"], cwd=SDIR)
    sh(["git", "config", "user.email", "memprof-colab@users.noreply.github.com"], cwd=SDIR)
    return True


def report(final: bool = False) -> None:
    with REPORT_LOCK:
        _report(final)


def _report(final: bool) -> None:
    with LOCK:
        ev = list(EVENTS)
    st = load_state()
    log = suite_log()
    cur = None
    for line in log:
        m = re.search(r"\] === (\S+)", line)
        if m:
            cur = m.group(1)
        if re.search(r"\] (done|FAILED|skip) ", line) and cur and cur in line:
            cur = None
    drv = backup_state()
    up_h = float(open("/proc/uptime").read().split()[0]) / 3600
    df = shutil.disk_usage(OUT)
    mem = dict(re.findall(r"(\w+):\s+(\d+)", open("/proc/meminfo").read()))
    S = {
        "time": now(), "final": final, "tag": TAG, "phase": NOW["phase"], "code": sh(["git", "log", "--oneline", "-1"], cwd=REPO)[1],
        "boot": open("/proc/sys/kernel/random/boot_id").read()[:8], "runtime_up_h": round(up_h, 2),
        "cu_used_this_runtime": round(up_h * CU_PER_HOUR, 1) if CU_PER_HOUR else None,
        "queue": queue_lines(), "done": st["done"], "gave_up": st["gave_up"], "tries": st["tries"],
        "current_line": NOW["line"], "attempt": NOW["attempt"], "current_run": cur,
        "suite_alive": bool(suite_pids()),
        "minutes_since_last_write": round((time.time() - last_write()) / 60, 1),
        "finished_runs": finished_runs(),
        "failed_lines": [x for x in log if re.search(r"\] (FAILED|TIMEOUT|SYNC FAILED|stack down|LLM failed|"
                                                      r"embedder failed|services failed|proxy failed)", x)][-30:],
        "backup": drv, "disk_free_gb": round(df.free / 2**30, 1), "stop": NOW["stop"],
        "hours_since_start": round((time.time() - T0) / 3600, 2), "max_hours": MAX_HOURS or None,
        "ram_avail_gb": round(int(mem.get("MemAvailable", 0)) / 2**20, 1), "gpu": gpu(),
    }
    print(f"[{S['time']}] {S['phase']} | line={S['current_line']} try={S['attempt']} run={cur} | "
          f"{len(S['finished_runs'])} runs done | backup={drv['mode']} missing={len(drv['missing'])} | "
          f"idle {S['minutes_since_last_write']} min", flush=True)
    S["outbox_runs"] = sorted(os.path.basename(f)[:-7] for f in glob.glob(os.path.join(OUTBOX, "runs", "*.tar.gz")))
    dirs = [os.path.join(OUTBOX, "status")] + ([os.path.join(SDIR, TAG)] if github_on() else [])
    for d in dirs:
        write_status(d, S, ev, log, cur, drv, final)
    if not SYNC and not github_on():
        S["outbox_runs"] = sorted(r for r in gh_backup(os.path.join(OUTBOX, "runs")) + S["outbox_runs"])
        json.dump(S, open(os.path.join(dirs[0], "status.json"), "w"), indent=1)
    if not github_on():
        return
    push_github(S)


def write_status(d, S, ev, log, cur, drv, final) -> None:
    os.makedirs(d, exist_ok=True)
    json.dump(S, open(os.path.join(d, "status.json"), "w"), indent=1)
    md = [f"# {TAG}  {S['time']}  ({S['phase']}{', FINAL' if final else ''})", "",
          f"- code `{S['code']}`, runtime up {S['runtime_up_h']} h" +
          (f" (~{S['cu_used_this_runtime']} CU)" if CU_PER_HOUR else ""),
          f"- queue: {S['queue']}  done: {S['done']}  gave up: {S['gave_up']}",
          f"- now: line `{S['current_line']}` attempt {S['attempt']}, run `{cur}`, suite alive {S['suite_alive']}, "
          f"last write {S['minutes_since_last_write']} min ago",
          f"- finished runs ({len(S['finished_runs'])}): {', '.join(S['finished_runs'])}",
          f"- backup: {drv}", f"- stop: {S['stop']}; {S['hours_since_start']} h since start, cap {S['max_hours']} h",
          f"- disk free {S['disk_free_gb']} GB, RAM avail {S['ram_avail_gb']} GB, GPU {S['gpu']}",
          "", "## problems", "", *([f"    {x}" for x in S["failed_lines"]] or ["none"]),
          "", "## supervisor events", "", *[f"    {x}" for x in ev[-40:]], "",
          "## suite.log (tail)", "", *[f"    {x}" for x in log[-60:]]]
    open(os.path.join(d, "status.md"), "w").write("\n".join(md) + "\n")
    open(os.path.join(d, "suite.log"), "w").write("\n".join(log[-3000:]) + "\n")
    for pat in ("qa_summary.md", "budget.md", "breakdown.md", "latency_model_*.md", "queue_state.json",
                "preflight/*.json", "preflight_*/*.json", "rates_*/llama_bench.json", "kv_*/kv_tier.json",
                "load_*/load.jsonl"):
        for f in glob.glob(os.path.join(OUT, pat)):
            dst = os.path.join(d, os.path.relpath(f, OUT))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy(f, dst)


def push_github(S) -> None:
    new = gh_backup()
    sh(["git", "add", "-A"], cwd=SDIR)
    if sh(["git", "diff", "--cached", "--quiet"], cwd=SDIR)[0] == 0:
        return
    sh(["git", "commit", "-q", "-m", f"{TAG} {S['time']} {S['phase']}" + (f" +{len(new)} runs" if new else "")], cwd=SDIR)
    for i in range(4):
        rc, out = sh(["git", "push", "-q", "origin", f"HEAD:{STATUS_BRANCH}"], cwd=SDIR, timeout=300)
        if rc == 0:
            return
        sh(["git", "pull", "-q", "--rebase", "origin", STATUS_BRANCH], cwd=SDIR, timeout=300)  # another runtime pushed
        time.sleep(5 * 2 ** i)
    event(f"status push failed: {redact(out)[-200:]}")


def reporter() -> None:
    while True:
        time.sleep(REPORT_MIN * 60)
        try:
            report()
        except Exception as e:  # never let the reporter kill the run
            event(f"report error: {e!r}"[:300])


# ---------------------------------------------------------------- main -----
def finish(reason: str) -> None:
    """Stop paying: wait (bounded) until every finished run has a copy off this VM, then release the runtime."""
    if not FINISH_LOCK.acquire(blocking=False):
        return  # another thread is already finishing
    NOW["phase"] = f"finishing: {reason}"
    event(f"finishing ({reason}); waiting up to {ACK_WAIT_MIN:.0f} min for the backup of the last runs")
    t = time.time()
    while True:
        report()
        b = backup_state()
        if b["ok"] and not b["missing"]:
            break
        if time.time() - t > ACK_WAIT_MIN * 60:
            event(f"backup still incomplete after {ACK_WAIT_MIN:.0f} min ({b}); releasing anyway to stop the cost")
            break
        time.sleep(60)
    NOW["phase"] = f"released: {reason}"
    report(final=True)
    if not AUTO_RELEASE:
        event("AUTO_RELEASE=0: runtime left running")
        return
    for f in ("/root/.local/share/python_keyring/keyring_pass.cfg", "/root/.config/python_keyring/keyringrc.cfg"):
        try:  # Colab token uploaded for the VM-side keep-alive (cli_bootstrap.py): gone before the VM is
            os.remove(f)
        except FileNotFoundError:
            pass
    try:
        from google.colab import drive, runtime  # type: ignore
        if os.path.ismount("/content/drive"):
            drive.flush_and_unmount()
        event("releasing the runtime")
        runtime.unassign()
    except Exception as e:
        event(f"release failed: {e!r}")


def stop_suite() -> None:
    for pid in suite_pids():
        try:
            os.killpg(int(pid), signal.SIGTERM)
        except Exception:
            sh(["kill", pid])
    time.sleep(15)
    sh("pkill -9 -f run_local_suite.sh; pkill -9 -f multi_e2e.py", timeout=30)
    sh(["bash", "scripts/local/start_llama.sh", "stop"], cwd=REPO, timeout=60)


def watchdog() -> None:
    """Hard cap and remote stop, independent of the main loop (and of Claude being reachable)."""
    while True:
        time.sleep(30)
        if MAX_HOURS and time.time() - T0 > MAX_HOURS * 3600:
            reason = f"time cap {MAX_HOURS:g} h reached"
        elif os.path.exists(os.path.join(INBOX, "stop")):
            reason = "stop requested"
        else:
            continue
        NOW["stop"] = reason
        event(f"STOP: {reason}")
        stop_suite()
        finish(reason)
        return


def start_watchdog() -> None:
    if not NOW.get("watchdog"):
        NOW["watchdog"] = True
        threading.Thread(target=watchdog, daemon=True).start()


def main() -> None:
    os.chdir(REPO)
    os.makedirs(INBOX, exist_ok=True)
    start_watchdog()
    status_init()
    event(f"supervisor up: OUT={OUT} SYNC={SYNC} queue={queue_lines()}")
    threading.Thread(target=reporter, daemon=True).start()
    if suite_pids():  # the cell was interrupted and re-run: never start a second suite next to a running one
        NOW["phase"] = "waiting for the suite started before this cell was re-run"
        event(NOW["phase"])
        while suite_pids():
            time.sleep(60)
    idle_since = None
    while True:
        if NOW["stop"]:
            time.sleep(3600)  # the watchdog is finishing / has released the runtime
            continue
        head = pull_code()
        st = load_state()
        todo = pending(st)
        if not todo:
            NOW["phase"] = "idle (queue empty)"
            if idle_since is None:
                idle_since = time.time()
                event(f"queue empty at {head}; waiting up to {IDLE_MIN:.0f} min for new lines in colab/queue.txt")
                report()
            if time.time() - idle_since > IDLE_MIN * 60:
                finish("queue done")
                return
            time.sleep(min(300, IDLE_MIN * 30))
            continue
        idle_since = None
        line = todo[0]
        n = st["tries"].get(line, 0) + 1   # counts failed attempts only (a lost runtime does not use one up)
        NOW.update(line=line, attempt=n, phase="running")
        event(f"start '{line}' attempt {n}/{MAX_TRIES} at {head}")
        report()
        ok = run_line(line)
        if NOW["stop"]:
            continue
        st = load_state()
        if ok:
            st["done"].append(line)
            event(f"finished '{line}'")
        else:
            st["tries"][line] = n
        if not ok and n >= MAX_TRIES:
            st["gave_up"].append(line)
            event(f"GAVE UP '{line}' after {n} attempts (fix + append a '# retry' line to colab/queue.txt)")
        save_state(st)
        sh(f'[ -n "{SYNC}" ] && cp -ru "{OUT}/." "{SYNC}/"', timeout=1800)
        NOW.update(line=None, attempt=0)
        report()


def entry() -> None:
    try:
        main()
    except KeyboardInterrupt:
        if NOW["proc"] is not None:
            print("interrupted: the suite keeps running in the background; re-run this cell to supervise it again")
        NOW["phase"] = "supervisor stopped by user"
        report()


if __name__ == "__main__":
    entry()
