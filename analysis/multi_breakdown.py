"""Cross-architecture latency attribution.

For every harness op (retrieve / generate / memorize / chat / turn) the op's wall-clock interval is
attributed *exclusively* to one category per instant, by priority (sweep line over all overlapping
intervals, so concurrent LLM / DB calls inside Graphiti or Letta are not double counted):

  LLM decode > LLM prefill+queue (TTFT) > Embedding > DB (client-side driver time) > NLP (spaCy/BM25)
  > other (framework / Python glue / HTTP / serialization)

LLM and embedding intervals come from the proxy log (same clock); agent-answer calls are tagged by
the harness and only attributed to agent.generate (matters in --async-add runs).
Also reports per-op token counts, prefix-cache hit ratio, #LLM calls, and server-side Postgres work.

usage: python analysis/multi_breakdown.py results/gpu/*/   -> <run>/breakdown_multi.json + markdown on stdout
"""
from __future__ import annotations

import json
import os
import statistics as st
import sys

CATS = ["LLM decode", "LLM prefill+queue", "LLM queue", "Embedding", "DB", "NLP", "other"]
PRIO = {c: i for i, c in enumerate(CATS)}
OPS = ["agent.retrieve", "agent.generate", "agent.memorize", "agent.memorize_async", "agent.chat", "agent.turn",
       "cold.start"]


def load(run: str):
    S = [json.loads(l) for l in open(os.path.join(run, "spans.jsonl"))]
    p = os.path.join(run, "llm_calls.jsonl")
    L = [json.loads(l) for l in open(p)] if os.path.exists(p) else []
    meta = json.load(open(os.path.join(run, "meta.json")))
    return S, L, meta


def intervals(S, L):
    """(t0, t1, cat, is_agent) for everything that can be attributed."""
    iv = []
    for c in L:
        if c.get("t1_ns") is None:
            continue
        agent = c.get("client") == "agent"
        if c["kind"] == "embed":
            iv.append((c["t0_ns"], c["t1_ns"], "Embedding", agent))
        else:
            tf = c.get("t_first_ns") or c["t1_ns"]
            q = ((c.get("vllm_metrics") or {}).get("queue_time_ms") or 0) * 1e6
            lt = c.get("llama_timings") or {}
            if not q and lt.get("prompt_ms") is not None and c.get("t_first_ns"):
                # llama.cpp: TTFT - server prefill time = waiting for a slot / batch + HTTP (upper bound of queue)
                q = max(0.0, (tf - c["t0_ns"]) - lt["prompt_ms"] * 1e6 - 2e6)
            if q > 0:  # split scheduler queueing from prefill
                tq = min(tf, c["t0_ns"] + int(q))
                iv.append((c["t0_ns"], tq, "LLM queue", agent))
                iv.append((tq, tf, "LLM prefill+queue", agent))
            else:
                iv.append((c["t0_ns"], tf, "LLM prefill+queue", agent))
            iv.append((tf, c["t1_ns"], "LLM decode", agent))
    for s in S:
        n = s["name"]
        cat = "DB" if n.startswith("db.") else "NLP" if n.startswith("nlp.") else None
        if cat:
            t0 = s["t0_ns"]
            iv.append((t0, t0 + int(s["wall_ms"] * 1e6), cat, False))
    iv.sort()
    return iv


def attribute(a: int, b: int, iv, want_agent: bool | None) -> dict:
    """Exclusive attribution of [a,b] by sweep line."""
    ev = []
    for t0, t1, cat, ag in iv:
        if t1 <= a:
            continue
        if t0 >= b:
            break
        if want_agent is not None and ag != want_agent:
            continue
        ev.append((max(t0, a), 0, cat))
        ev.append((min(t1, b), 1, cat))
    ev.sort()
    out = {c: 0.0 for c in CATS}
    active = {c: 0 for c in CATS}
    t = a
    for x, kind, cat in ev:
        if x > t:
            top = min((c for c in CATS if active[c] > 0), key=PRIO.get, default="other")
            out[top] += (x - t) / 1e6
            t = x
        active[cat] += 1 if kind == 0 else -1
    if b > t:
        out["other"] += (b - t) / 1e6
    return out


def calls_in(a, b, L, want_agent):
    xs = [c for c in L if c.get("t1_ns") and c["t0_ns"] >= a and c["t1_ns"] <= b
          and (want_agent is None or (c.get("client") == "agent") == want_agent)]
    ch = [c for c in xs if c["kind"] == "chat"]
    return {"n_llm": len(ch), "n_embed": len(xs) - len(ch),
            "prompt_tok": sum(c.get("prompt_tokens") or 0 for c in ch),
            "cached_tok": sum(c.get("cached_tokens") or 0 for c in ch),
            "completion_tok": sum(c.get("completion_tokens") or 0 for c in ch),
            "llm_busy_ms": sum(c["wall_ms"] for c in ch)}


def analyze(run: str) -> dict:
    S, L, meta = load(run)
    iv = intervals(S, L)
    res = {"label": meta.get("label"), "system": meta["args"]["system"], "async": meta["args"].get("async_add"),
           "n_turns": meta.get("n_turns"), "count": meta.get("count"), "footprint": meta.get("footprint"),
           "ops": {}}
    for name in OPS:
        for phase in ("chat", "qa", "cold"):
            xs = [s for s in S if s["name"] == name and s.get("phase") == phase and not s.get("flat")]
            if phase == "chat":
                xs = [s for s in xs if s.get("turn", 0) >= 1]  # steady state
            if not xs:
                continue
            rows = []
            for s in xs:
                a = s["t0_ns"]
                b = a + int(s["wall_ms"] * 1e6)
                want = True if name == "agent.generate" else (None if name in ("agent.turn", "cold.start", "agent.chat") else False)
                r = attribute(a, b, iv, want)
                r.update(calls_in(a, b, L, want))
                r["wall"] = s["wall_ms"]
                for k, v in s.items():
                    if (k.startswith(("pg_", "io_", "dev_")) or k == "n_tool_calls") and isinstance(v, (int, float)):
                        r[k] = v
                rows.append(r)
            walls = sorted(r["wall"] for r in rows)
            keys = sorted({k for r in rows for k in r})
            agg = {k: st.mean(r.get(k, 0) or 0 for r in rows) for k in keys}
            agg.update({"n": len(rows), "p50": walls[len(walls) // 2], "p95": walls[min(len(walls) - 1, int(len(walls) * .95))],
                        "max": walls[-1]})
            agg["cache_hit"] = agg["cached_tok"] / agg["prompt_tok"] if agg.get("prompt_tok") else None
            res["ops"][f"{name}({phase})"] = agg
    # graphiti / mem0 internal phases (mean ms per memorize op, union not needed: informational)
    ph = {}
    for s in S:
        if s["name"].startswith(("graphiti.phase.", "mem0.")) and s.get("phase") == "chat" and s.get("turn", 0) >= 1:
            ph.setdefault(s["name"], []).append(s["wall_ms"])
    res["phases"] = {k: {"n": len(v), "mean_ms": st.mean(v)} for k, v in ph.items()}
    lag = meta.get("commit_lag_s")
    if lag:
        res["commit_lag_s"] = {"median": sorted(lag)[len(lag) // 2], "max": max(lag)}
    hwp = os.path.join(run, "hw.jsonl")
    if os.path.exists(hwp):
        res["hw"] = hw_summary([json.loads(l) for l in open(hwp)])
    json.dump(res, open(os.path.join(run, "breakdown_multi.json"), "w"), indent=1)
    return res


def hw_summary(H: list[dict]) -> dict:
    out: dict = {}
    g = [h["gpu"][0] for h in H if h.get("gpu")]
    if g:
        out["gpu_util_mean"] = st.mean(x["util"] for x in g)
        out["gpu_membw_util_mean"] = st.mean(x["mem_bw_util"] for x in g)
        out["gpu_mem_mb_max"] = max(x["mem_mb"] for x in g)
        out["gpu_power_mean"] = st.mean(x["power_w"] for x in g)
    v = [list(h["vllm"].values())[0] for h in H if h.get("vllm") and list(h["vllm"].values())[0]]
    if len(v) >= 2 and "pc_hits_tok" in v[-1]:  # llama.cpp: tokens served from cache / all prompt tokens
        dh = v[-1]["pc_hits_tok"] - v[0].get("pc_hits_tok", 0)
        dp = v[-1].get("prompt_tokens", 0) - v[0].get("prompt_tokens", 0)
        out["prefix_cache_hit"] = dh / (dh + dp) if dh + dp else None
        out["max_waiting"] = max(x.get("waiting", 0) for x in v)
        gt = (v[-1].get("gen_tokens", 0) - v[0].get("gen_tokens", 0))
        gs = (v[-1].get("gen_s", 0) - v[0].get("gen_s", 0))
        ps = (v[-1].get("prompt_s", 0) - v[0].get("prompt_s", 0))
        out["llm_decode_tok_s"] = gt / gs if gs else None
        out["llm_prefill_tok_s"] = dp / ps if ps else None
    elif len(v) >= 2:
        out["kv_usage_max"] = max(x.get("kv_usage", 0) for x in v)
        dq = v[-1].get("pc_queries", 0) - v[0].get("pc_queries", 0)
        dh = v[-1].get("pc_hits", 0) - v[0].get("pc_hits", 0)
        out["prefix_cache_hit"] = dh / dq if dq else None
        out["preemptions"] = v[-1].get("preemptions", 0) - v[0].get("preemptions", 0)
    procs: dict = {}
    for h in H:
        for k, x in (h.get("procs") or {}).items():
            procs.setdefault(k, []).append(x)
    out["proc_cpu_mean"] = {k: st.mean(x["cpu"] for x in xs) for k, xs in procs.items()}
    out["proc_rss_max_mb"] = {k: max(x["rss_mb"] for x in xs) for k, xs in procs.items()}
    if H:
        out["disk_w_mb"] = H[-1]["sys"]["disk_w"] / 2**20
        out["disk_r_mb"] = H[-1]["sys"]["disk_r"] / 2**20
        out["swap_mb_max"] = max(h["sys"].get("swap_mb", 0) for h in H)
    if g and "pcie_tx_kbs" in g[0]:
        out["pcie_rx_mb_s_mean"] = st.mean(x.get("pcie_rx_kbs", 0) for x in g) / 1024
        out["pcie_tx_mb_s_mean"] = st.mean(x.get("pcie_tx_kbs", 0) for x in g) / 1024
    io = [h["io"] for h in H if h.get("io")]
    if len(io) >= 2:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from memprof.iostat import delta
        d = delta(io[0], io[-1])
        out["io_by_group_mb"] = {k: {"rd": x["read_bytes"] / 2**20, "wr": x["write_bytes"] / 2**20,
                                     "rchar": x["rchar"] / 2**20, "wchar": x["wchar"] / 2**20}
                                 for k, x in d["procs"].items()}
        out["dev"] = d["dev"]
        out["psi_io"] = d.get("psi_io")
    return out


def md(results: list[dict]) -> str:
    lines = ["| run | op | n | mean ms | p95 ms | " + " | ".join(CATS)
             + " | #LLM | prompt tok | cache hit | out tok | pg stmts | disk rd KB | disk wr KB | flushes |",
             "|" + "---|" * (14 + len(CATS))]
    for r in results:
        for op, a in r["ops"].items():
            if op.startswith(("agent.turn", "cold")):
                continue
            ch = f"{a['cache_hit']:.0%}" if a.get("cache_hit") is not None else "-"
            lines.append(f"| {r['label']} | {op} | {a['n']} | {a['wall']:.0f} | {a['p95']:.0f} | "
                         + " | ".join(f"{a[c]:.0f}" for c in CATS)
                         + f" | {a['n_llm']:.1f} | {a['prompt_tok']:.0f} | {ch} | {a['completion_tok']:.0f} | {a.get('pg_calls', 0):.0f}"
                         + f" | {a.get('io_rd_bytes', 0) / 1024:.0f} | {a.get('io_wr_bytes', 0) / 1024:.0f} | {a.get('dev_flush_ios', 0):.1f} |")
    return "\n".join(lines)


if __name__ == "__main__":
    res = [analyze(r) for r in sys.argv[1:]]
    print(md(res))
