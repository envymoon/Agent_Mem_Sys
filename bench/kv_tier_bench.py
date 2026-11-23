"""KV-cache placement micro-benchmark on the real machine (llama.cpp server).

For a prompt prefix of L tokens (the static part a memory system re-sends on every write: mem0's ~8k
extraction prompt, Graphiti's extraction prompts, the agent's system prompt + memories), how long does it take
to get that prefix's KV back into the GPU, per storage tier?

  recompute   prefill from scratch (cache_prompt=false)                       -> GPU compute
  gpu_hit     the prefix is still in the slot's KV                            -> ~free
  ram_hit     the slot was overwritten; prefix comes back from llama.cpp's host-RAM prompt cache
              (--cache-ram > 0)                                               -> DRAM + PCIe
  ssd_cold    slot state saved to a file (/slots?action=save), slot overwritten, guest page cache dropped,
              file restored (/slots?action=restore)                           -> NVMe + PCIe
  ssd_warm    same, file still in the page cache                              -> DRAM (page cache) + PCIe

Each point is the latency of the request that needs the prefix (n_predict=1), i.e. "time until the model can
start working on the new suffix", plus save/restore timings and bytes reported by the server, plus block-device
I/O measured around the restore. Run once with --cache-ram on (default) and once with --cache-ram 0 to see the
RAM tier switch off.

usage: python bench/kv_tier_bench.py --out results/local/x/kv_tier --lens 1024,2048,4096,8192,12288
"""
from __future__ import annotations

import argparse
import json
import os
import statistics as st
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from memprof import iostat  # noqa: E402


def post(url: str, body: dict, timeout: float = 600) -> tuple[dict, float]:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    r = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
    return r, (time.perf_counter() - t0) * 1e3


def corpus_tokens(base: str, data: str, n: int, seed: int) -> list[int]:
    D = json.load(open(data))
    txt = []
    for d in D[seed % len(D):] + D[: seed % len(D)]:
        for k, v in d["conversation"].items():
            if k.startswith("session_") and isinstance(v, list):
                txt += [f"{u['speaker']}: {u['text']}" for u in v]
    toks: list[int] = []
    i = 0
    while len(toks) < n:
        chunk = "\n".join(txt[i: i + 200])
        i += 200
        toks += post(base + "/tokenize", {"content": chunk})[0]["tokens"]
    return toks[:n]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--data", default=os.environ.get("LOCOMO", os.path.expanduser("~/locomo/data/locomo10.json")))
    ap.add_argument("--lens", default="1024,2048,4096,8192,12288")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--slot", type=int, default=0)
    ap.add_argument("--label", default="")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    base = a.url.rstrip("/")
    props = json.loads(urllib.request.urlopen(base + "/props").read())
    n_ctx = props.get("default_generation_settings", {}).get("n_ctx") or 16384
    lens = [L for L in (int(x) for x in a.lens.split(",")) if L + 64 <= n_ctx]
    rows = []

    def complete(tokens, cache=True):
        r, ms = post(base + "/completion", {"prompt": tokens, "n_predict": 1, "cache_prompt": cache,
                                            "id_slot": a.slot, "temperature": 0})
        t = r.get("timings", {})
        return {"wall_ms": ms, "prompt_ms": t.get("prompt_ms"), "prompt_n": t.get("prompt_n"),
                "cache_n": t.get("cache_n")}

    def slot(action, fn):
        r, ms = post(f"{base}/slots/{a.slot}?action={action}", {"filename": fn})
        return r, ms

    complete(corpus_tokens(base, a.data, 256, 99))  # warm-up (CUDA graphs, allocator)
    for L in lens:
        P = corpus_tokens(base, a.data, L, 1)
        Q = corpus_tokens(base, a.data, L, 5)  # same length, different content: evicts P from the slot
        res: dict = {"L": L, "reps": []}
        for rep in range(a.reps):
            x: dict = {}
            x["recompute"] = complete(P, cache=False)
            complete(P)
            x["gpu_hit"] = complete(P)
            complete(Q)
            x["ram_hit"] = complete(P)  # with --cache-ram 0 this is a recompute
            fn = f"kvbench_{L}.bin"
            sr, s_ms = slot("save", fn)
            x["save"] = {"wall_ms": s_ms, "save_ms": sr.get("timings", {}).get("save_ms"), "bytes": sr.get("n_written"),
                         "n_tokens": sr.get("n_saved")}
            for mode in ("ssd_cold", "ssd_warm"):
                complete(Q)
                dropped = iostat.drop_caches() if mode == "ssd_cold" else False
                io0 = iostat.snapshot()
                rr, r_ms = slot("restore", fn)
                io = iostat.flat(iostat.delta(io0, iostat.snapshot()))
                c = complete(P)
                x[mode] = {"restore_wall_ms": r_ms, "restore_ms": rr.get("timings", {}).get("restore_ms"),
                           "bytes": rr.get("n_read"), "then_request": c, "total_ms": r_ms + c["wall_ms"],
                           "dropped_cache": dropped, "dev_rd_ios": io.get("dev_rd_ios"),
                           "llm_rd_bytes": iostat.delta(io0, iostat.snapshot())["procs"].get("llm_server", {}).get("read_bytes")}
            res["reps"].append(x)
            print(f"L={L:6d} rep{rep} recompute={x['recompute']['wall_ms']:.0f} gpu={x['gpu_hit']['wall_ms']:.0f} "
                  f"ram={x['ram_hit']['wall_ms']:.0f}(cache_n={x['ram_hit']['cache_n']}) "
                  f"ssd_cold={x['ssd_cold']['total_ms']:.0f} ssd_warm={x['ssd_warm']['total_ms']:.0f} ms "
                  f"kv={(x['save']['bytes'] or 0) / 2**20:.0f}MB", flush=True)
        med = lambda f: st.median(f(r) for r in res["reps"])  # noqa: E731
        res["median"] = {
            "recompute_ms": med(lambda r: r["recompute"]["wall_ms"]),
            "recompute_prefill_ms": med(lambda r: r["recompute"]["prompt_ms"] or 0),
            "gpu_hit_ms": med(lambda r: r["gpu_hit"]["wall_ms"]),
            "ram_hit_ms": med(lambda r: r["ram_hit"]["wall_ms"]),
            "ram_hit_cache_n": med(lambda r: r["ram_hit"]["cache_n"] or 0),
            "ssd_cold_ms": med(lambda r: r["ssd_cold"]["total_ms"]),
            "ssd_cold_restore_ms": med(lambda r: r["ssd_cold"]["restore_wall_ms"]),
            "ssd_warm_ms": med(lambda r: r["ssd_warm"]["total_ms"]),
            "save_ms": med(lambda r: r["save"]["wall_ms"]),
            "kv_bytes": med(lambda r: r["save"]["bytes"] or 0),
        }
        res["median"]["kv_bytes_per_token"] = res["median"]["kv_bytes"] / L
        rows.append(res)
        sp = os.path.join(os.environ.get("SLOT_SAVE", "/opt/svc/data/kv_slots"), fn)
        if os.path.exists(sp):
            os.remove(sp)
    meta = {"label": a.label, "props": {k: props.get(k) for k in ("model_path", "total_slots")}, "n_ctx": n_ctx,
            "cmd": open("results/server_logs/llm.cmd").read().strip() if os.path.exists("results/server_logs/llm.cmd") else None}
    json.dump({"meta": meta, "rows": rows}, open(os.path.join(a.out, "kv_tier.json"), "w"), indent=1)
    print("| L | recompute | gpu hit | RAM cache | SSD cold | SSD warm | save | KV MB |")
    print("|---|---|---|---|---|---|---|---|")
    for r in rows:
        m = r["median"]
        print(f"| {r['L']} | {m['recompute_ms']:.0f} | {m['gpu_hit_ms']:.0f} | {m['ram_hit_ms']:.0f} | {m['ssd_cold_ms']:.0f} "
              f"| {m['ssd_warm_ms']:.0f} | {m['save_ms']:.0f} | {m['kv_bytes'] / 2**20:.0f} |")


if __name__ == "__main__":
    main()
