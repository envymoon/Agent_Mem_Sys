"""Hardware / service time-series sampler (separate process; joins with spans via perf_counter_ns).

Every --interval seconds writes one jsonl record:
  gpu[i]: util %, mem-bandwidth util %, mem used MB, power W, SM clock      (pynvml, if a GPU exists)
  vllm:   KV-cache usage, running/waiting requests, prefix-cache queries/hits, preemptions,
          prompt/generation token counters                                   (scraped from /metrics)
  procs:  CPU% and RSS per process group (llm server, embed server, postgres, qdrant, neo4j,
          letta server, harness)                                              (psutil)
  sys:    total CPU%, disk read/write bytes, used RAM

usage: python -m memprof.hwmon --out results/x/hw.jsonl --vllm http://127.0.0.1:8000 --interval 0.25
Stops on SIGTERM / SIGINT.
"""
from __future__ import annotations

import argparse
import json
import re
import signal
import time
import urllib.request

import psutil

GROUPS = {  # name -> regex on cmdline
    "llm_server": r"vllm.*serve(?!.*[Ee]mbed)|llama-server(?!.*--embeddings)|sglang",
    "embed_server": r"vllm.*serve.*[Ee]mbed|llama-server.*--embeddings|infinity_emb|text-embeddings",
    "vllm_engine": r"EngineCore|VLLM::",
    "postgres": r"^postgres|/postgres ",
    "qdrant": r"/qdrant(\s|$)",
    "neo4j": r"neo4j|org\.neo4j",
    "letta": r"letta.*server|letta_server|uvicorn.*letta",
    "proxy": r"memprof\.llm_proxy",
    "harness": r"bench/|bench\.",
}
VLLM_KEYS = {
    "vllm:kv_cache_usage_perc": "kv_usage", "vllm:gpu_cache_usage_perc": "kv_usage",
    "vllm:num_requests_running": "running", "vllm:num_requests_waiting": "waiting",
    "vllm:prefix_cache_queries_total": "pc_queries", "vllm:prefix_cache_hits_total": "pc_hits",
    "vllm:gpu_prefix_cache_queries_total": "pc_queries", "vllm:gpu_prefix_cache_hits_total": "pc_hits",
    "vllm:num_preemptions_total": "preemptions", "vllm:prompt_tokens_total": "prompt_tokens",
    "vllm:generation_tokens_total": "gen_tokens",
}
_re_line = re.compile(r"^([a-zA-Z_:][a-zA-Z0-9_:]*)(\{[^}]*\})?\s+([0-9.eE+-]+|NaN)")


def scrape_vllm(url: str) -> dict:
    out: dict = {}
    try:
        txt = urllib.request.urlopen(url.rstrip("/") + "/metrics", timeout=1).read().decode()
    except Exception:
        return out
    for line in txt.splitlines():
        m = _re_line.match(line)
        if m and m.group(1) in VLLM_KEYS:
            k = VLLM_KEYS[m.group(1)]
            out[k] = out.get(k, 0.0) + float(m.group(3))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--interval", type=float, default=0.25)
    ap.add_argument("--vllm", default="", help="comma list of vLLM base URLs to scrape")
    ap.add_argument("--vllm-every", type=int, default=4, help="scrape vLLM every N samples")
    args = ap.parse_args()

    stop = False

    def _stop(*_):
        nonlocal stop
        stop = True
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    nv = None
    try:
        import pynvml
        pynvml.nvmlInit()
        nv = [pynvml.nvmlDeviceGetHandleByIndex(i) for i in range(pynvml.nvmlDeviceGetCount())]
    except Exception:
        nv = None
    pats = {g: re.compile(p) for g, p in GROUPS.items()}
    procs: dict[int, tuple[psutil.Process, str]] = {}
    me = psutil.Process().pid

    def refresh():
        for p in psutil.process_iter(["pid", "cmdline", "name"]):
            if p.pid in procs or p.pid == me:
                continue
            cl = " ".join(p.info["cmdline"] or []) or (p.info["name"] or "")
            for g, rx in pats.items():
                if rx.search(cl):
                    try:
                        p.cpu_percent(None)
                    except psutil.Error:
                        break
                    procs[p.pid] = (p, g)
                    break

    vurls = [u for u in args.vllm.split(",") if u]
    f = open(args.out, "a", buffering=1)
    psutil.cpu_percent(None)
    d0 = psutil.disk_io_counters()
    i = 0
    while not stop:
        if i % 20 == 0:
            refresh()
        rec: dict = {"t_ns": time.perf_counter_ns(), "wall": time.time()}
        if nv:
            import pynvml
            g = []
            for h in nv:
                try:
                    u = pynvml.nvmlDeviceGetUtilizationRates(h)
                    mem = pynvml.nvmlDeviceGetMemoryInfo(h)
                    g.append({"util": u.gpu, "mem_bw_util": u.memory, "mem_mb": mem.used / 2**20,
                              "power_w": pynvml.nvmlDeviceGetPowerUsage(h) / 1e3,
                              "sm_mhz": pynvml.nvmlDeviceGetClockInfo(h, pynvml.NVML_CLOCK_SM)})
                except Exception:
                    pass
            rec["gpu"] = g
        if vurls and i % args.vllm_every == 0:
            rec["vllm"] = {u: scrape_vllm(u) for u in vurls}
        grp: dict = {}
        for pid, (p, gname) in list(procs.items()):
            try:
                c = p.cpu_percent(None)
                rss = p.memory_info().rss
            except psutil.Error:
                procs.pop(pid, None)
                continue
            s = grp.setdefault(gname, {"cpu": 0.0, "rss_mb": 0.0})
            s["cpu"] += c
            s["rss_mb"] += rss / 2**20
        rec["procs"] = grp
        d = psutil.disk_io_counters()
        vm = psutil.virtual_memory()
        rec["sys"] = {"cpu": psutil.cpu_percent(None), "ram_used_mb": vm.used / 2**20,
                      "disk_r": d.read_bytes - d0.read_bytes, "disk_w": d.write_bytes - d0.write_bytes}
        f.write(json.dumps(rec) + "\n")
        i += 1
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
