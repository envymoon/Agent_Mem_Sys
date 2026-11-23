"""Storage-I/O accounting that works on native Linux and WSL2 (needs root to read other users' /proc/<pid>/io).

snapshot() -> {"procs": {group: {read_bytes, write_bytes, rchar, wchar, syscr, syscw}},
               "dev": {name: {rd_ios, rd_ms, wr_ios, wr_ms, rd_sec, wr_sec, io_ms, flush_ios, flush_ms}},
               "psi_io": {some_total_us, full_total_us}}
delta(a, b) -> same shape, b - a.

read_bytes / write_bytes = bytes that actually hit the block layer (page-cache misses, writeback);
rchar / wchar = bytes passed through read()/write() syscalls (including page-cache hits);
syscr / syscw = syscall counts. Device stats come from /proc/diskstats for the device(s) that hold
the data directories (SVC_DATA, models, run dir), so fsync/flush latency of the real SSD is visible.
"""
from __future__ import annotations

import os
import re
import time

GROUPS = {  # same grouping as hwmon
    "llm_server": r"vllm.*serve(?!.*[Ee]mbed)|llama-server(?!.*--embeddings)|sglang",
    "embed_server": r"vllm.*serve.*[Ee]mbed|llama-server.*--embeddings|infinity_emb|text-embeddings",
    "postgres": r"^postgres|/postgres ",
    "qdrant": r"/qdrant(\s|$)",
    "neo4j": r"neo4j|org\.neo4j",
    "proxy": r"memprof\.llm_proxy",
    "harness": r"bench/|bench\.",
}
_PATS = {g: re.compile(p) for g, p in GROUPS.items()}
_IO_KEYS = ("rchar", "wchar", "syscr", "syscw", "read_bytes", "write_bytes")
_cache: dict = {"t": 0.0, "pids": {}}


def refresh() -> None:
    """Forget the cached pid->group map (call after restarting a backend)."""
    _cache["t"] = 0.0


def _pids(max_age: float = 1.0) -> dict[int, str]:
    now = time.monotonic()
    if now - _cache["t"] < max_age:
        return _cache["pids"]
    out = {}
    me = os.getpid()
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        pid = int(d)
        try:
            cl = open(f"/proc/{d}/cmdline", "rb").read().replace(b"\0", b" ").decode(errors="ignore").strip()
        except OSError:
            continue
        if not cl:
            continue
        for g, rx in _PATS.items():
            if rx.search(cl):
                out[pid] = "harness" if pid == me else g
                break
        else:
            if pid == me:
                out[pid] = "harness"
    _cache.update(t=now, pids=out)
    return out


def _proc_io(pid: int) -> dict | None:
    try:
        r = {}
        for line in open(f"/proc/{pid}/io"):
            k, v = line.split(":")
            if k in _IO_KEYS:
                r[k] = int(v)
        return r
    except (OSError, ValueError):
        return None


def data_devices(paths: list[str]) -> list[str]:
    """Block devices (as named in /proc/diskstats) backing the given paths; partitions -> whole disk too."""
    names = set()
    for p in paths:
        try:
            st = os.stat(p)
        except OSError:
            continue
        maj, mnr = os.major(st.st_dev), os.minor(st.st_dev)
        for line in open("/proc/diskstats"):
            f = line.split()
            if int(f[0]) == maj and int(f[1]) == mnr:
                names.add(f[2])
                base = re.sub(r"p?\d+$", "", f[2]) if not f[2].startswith("dm-") else None
                if base and base != f[2]:
                    names.add(base)
    return sorted(names)


def _diskstats(devs: list[str]) -> dict:
    out = {}
    if not devs:
        return out
    for line in open("/proc/diskstats"):
        f = line.split()
        if f[2] in devs:
            v = [int(x) for x in f[3:]]
            d = {"rd_ios": v[0], "rd_sec": v[2], "rd_ms": v[3], "wr_ios": v[4], "wr_sec": v[6], "wr_ms": v[7],
                 "io_ms": v[9]}
            if len(v) >= 17:
                d.update(flush_ios=v[15], flush_ms=v[16])
            out[f[2]] = d
    return out


def _psi() -> dict:
    try:
        r = {}
        for line in open("/proc/pressure/io"):
            kind, *kv = line.split()
            r[kind + "_total_us"] = int(dict(x.split("=") for x in kv)["total"])
        return r
    except (OSError, KeyError, ValueError):
        return {}


_DEVS: list[str] | None = None


def devices() -> list[str]:
    global _DEVS
    if _DEVS is None:
        paths = [os.environ.get("SVC_DATA", "/opt/svc/data"), os.environ.get("MEMPROF_MODELS", "models"), os.getcwd()]
        _DEVS = data_devices(paths)
    return _DEVS


def snapshot() -> dict:
    procs: dict = {}
    for pid, g in list(_pids().items()):
        r = _proc_io(pid)
        if r is None:
            continue
        s = procs.setdefault(g, dict.fromkeys(_IO_KEYS, 0))
        for k in _IO_KEYS:
            s[k] += r.get(k, 0)
    return {"procs": procs, "dev": _diskstats(devices()), "psi_io": _psi()}


def _sub(a, b):
    if isinstance(b, dict):
        return {k: _sub((a or {}).get(k) if isinstance(a, dict) else None, v) for k, v in b.items()}
    return b - (a or 0) if isinstance(b, (int, float)) else b


def delta(a: dict, b: dict) -> dict:
    """b - a. Groups whose processes restarted in between can go negative; those are clamped to 0."""
    d = _sub(a, b)
    for g in d.get("procs", {}).values():
        for k, v in g.items():
            if isinstance(v, (int, float)) and v < 0:
                g[k] = 0
    return d


def flat(d: dict) -> dict:
    """Compact per-op attributes: total block-layer bytes of the memory backends + device flushes."""
    p = d.get("procs", {})
    back = [g for g in ("postgres", "qdrant", "neo4j", "harness") if g in p]
    out = {"io_rd_bytes": sum(p[g]["read_bytes"] for g in back),
           "io_wr_bytes": sum(p[g]["write_bytes"] for g in back),
           "io_rchar": sum(p[g]["rchar"] for g in back), "io_wchar": sum(p[g]["wchar"] for g in back)}
    for g in back:
        out[f"io_{g}_rd"] = p[g]["read_bytes"]
        out[f"io_{g}_wr"] = p[g]["write_bytes"]
    dev = d.get("dev", {})
    if dev:
        out["dev_wr_ios"] = sum(x["wr_ios"] for x in dev.values())
        out["dev_rd_ios"] = sum(x["rd_ios"] for x in dev.values())
        out["dev_flush_ios"] = sum(x.get("flush_ios", 0) for x in dev.values())
        out["dev_wr_ms"] = sum(x["wr_ms"] for x in dev.values())
        out["dev_flush_ms"] = sum(x.get("flush_ms", 0) for x in dev.values())
    return out


def drop_caches() -> bool:
    """sync + drop the (guest) page cache. Root only. Returns False if not permitted."""
    try:
        os.sync()
        with open("/proc/sys/vm/drop_caches", "w") as f:
            f.write("3\n")
        return True
    except OSError:
        return False
