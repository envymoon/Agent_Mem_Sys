"""Same machine, two platforms: WSL2 (main runs) vs native Linux (replication). Is anything we report an artifact
of the WSL2 virtual disk (ext4 in a VHDX on NTFS, Hyper-V storage stack, possible host-side caching)?

Compares, for every run / file present in both result dirs:
  preflight  fio seq read MB/s, 4k rand read p50, 4k write+fsync commit latency; page-cache check
  kv         SSD-cold / SSD-warm restore and recompute per prefix length
  load       model cold / warm load time and bytes read
  l1 / l4    per op (memorize / generate / retrieve): wall, DB, flushes, dev flush ms, bytes written
  l5         per store size: hot p50, cold first query, cold bytes read, reopen time
Prints a markdown table with the native/WSL ratio; |log ratio| large on storage rows and ~1 on LLM rows means
the virtualization layer matters for storage, not for the model side.

usage: python analysis/platform_compare.py results/local/HOST-wsl results/local/HOST-native [--out cmp.json]
"""
from __future__ import annotations

import glob
import json
import os
import sys


def jl(p):
    try:
        return json.load(open(p))
    except (OSError, ValueError):
        return None


def fio(d):
    out = {}
    for n in ("seqread", "randread", "fsyncwrite"):
        j = jl(os.path.join(d, "preflight", f"fio_{n}.json"))
        if not j:
            continue
        j = j["jobs"][0]
        io = j["read"] if n != "fsyncwrite" else j["write"]
        out[f"fio {n} MB/s"] = io["bw"] / 1024
        out[f"fio {n} p50 us"] = io["clat_ns"]["percentile"].get("50.000000", 0) / 1e3
        if n == "fsyncwrite":
            out["fio 4k write+fsync us"] = (io["lat_ns"]["mean"] + (j.get("sync", {}).get("lat_ns", {}).get("mean") or 0)) / 1e3
    c = jl(os.path.join(d, "preflight", "cache_check.json")) or {}
    for k in ("cold_buffered_mb_s", "warm_mb_s"):
        if k in c:
            out[f"page cache {k}"] = c[k]
    return out


def kv(d):
    out = {}
    for f in glob.glob(os.path.join(d, "kv_*", "kv_tier.json")):
        tag = os.path.basename(os.path.dirname(f))
        for r in (jl(f) or {}).get("rows", []):
            m = r["median"]
            for k in ("recompute_ms", "ssd_cold_ms", "ssd_cold_restore_ms", "ssd_warm_ms", "save_ms"):
                out[f"{tag} L={r['L']} {k}"] = m[k]
    return out


def load(d):
    out = {}
    for f in glob.glob(os.path.join(d, "load_*", "load.jsonl")):
        tag = os.path.basename(os.path.dirname(f))
        for line in open(f):
            r = json.loads(line)
            out[f"{tag} {r['mode']}/{r['page_cache']} load s"] = r["load_wall_s"]
            out[f"{tag} {r['mode']}/{r['page_cache']} read MB"] = r["dev_read_mb"]
    return out


def ops(d):
    out = {}
    for f in glob.glob(os.path.join(d, "l[14]_*", "breakdown_multi.json")):
        tag = os.path.basename(os.path.dirname(f))
        for op, a in (jl(f) or {}).get("ops", {}).items():
            if not op.endswith("(chat)") or not op.startswith(("agent.memorize", "agent.generate", "agent.retrieve")):
                continue
            o = op.split(".")[1].split("(")[0]
            for k, lab in (("wall", "wall ms"), ("DB", "DB ms"), ("dev_flush_ios", "flushes"), ("dev_flush_ms", "dev flush ms"),
                           ("io_wr_bytes", "wr bytes"), ("LLM prefill+queue", "LLM prefill ms"), ("LLM decode", "LLM decode ms")):
                if k in a:
                    out[f"{tag} {o} {lab}"] = a[k]
    return out


def scale(d):
    out = {}
    for f in glob.glob(os.path.join(d, "l5_scale_*", "scale.json")):
        for r in jl(f) or []:
            s, t = r.get("summary", {}), f"{r['backend']} N={r['N']}"
            if "hot" in s:
                out[f"{t} hot p50 ms"] = s["hot"]["wall_ms"]["p50"]
            if "cold" in s:
                out[f"{t} cold first ms"] = s["cold"]["wall_ms"]["first"]
                out[f"{t} cold p50 ms"] = s["cold"]["wall_ms"]["p50"]
                out[f"{t} cold read MB"] = sum(x["rd_bytes"] for x in r["cold"]) / 2**20
                out[f"{t} reopen s"] = r.get("cold_open_s", 0) + r.get("cold_restart_s", 0)
    return out


def collect(d):
    x = {}
    for f in (fio, kv, load, ops, scale):
        x.update(f(d))
    return x


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else ""
    if out in args:
        args.remove(out)
    wsl, nat = args[:2]
    A, B = collect(wsl), collect(nat)
    keys = [k for k in A if k in B]
    print(f"| metric | {os.path.basename(wsl.rstrip('/'))} | {os.path.basename(nat.rstrip('/'))} | ratio |")
    print("|---|---|---|---|")
    res = {}
    for k in keys:
        a, b = A[k], B[k]
        r = b / a if a else None
        res[k] = {"wsl": a, "native": b, "ratio": r}
        print(f"| {k} | {a:.4g} | {b:.4g} | {f'{r:.2f}' if r is not None else '-'} |")
    print(f"\n{len(keys)} metrics in both; only in {wsl}: {len(set(A) - set(B))}; only in {nat}: {len(set(B) - set(A))}")
    if out:
        json.dump(res, open(out, "w"), indent=1)


if __name__ == "__main__":
    main()
