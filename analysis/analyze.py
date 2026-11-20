"""Turn span traces into latency breakdowns (exclusive time per hardware/software layer).

usage: python analysis/analyze.py results/e2e_cache_np2 [more run dirs...]
Writes <run>/breakdown.json and prints markdown tables.
"""
from __future__ import annotations

import json
import os
import statistics as st
import sys
from collections import defaultdict

# Ordered categories; each maps to the resource it mostly exercises.
CATS = [
    ("LLM prefill", "GPU/CPU matmul (compute-bound)"),
    ("LLM decode", "weights+KV streaming (memory-BW-bound)"),
    ("LLM other", "HTTP/JSON/tokenize/sched"),
    ("Embedding ONNX", "CPU matmul"),
    ("Embedding wrapper", "Python"),
    ("spaCy NLP", "CPU (Python+Cython)"),
    ("BM25 encode", "CPU (Python)"),
    ("Vector distance", "DRAM BW (numpy)"),
    ("Payload filter", "Python per-point loop"),
    ("Persist pickle+SQLite", "serialize + storage I/O"),
    ("Vector store glue", "Python"),
    ("History DB SQLite", "storage I/O"),
    ("mem0/agent glue", "Python"),
]


def category(name: str) -> str:
    if name.startswith("fastembed.dense"):
        return "Embedding ONNX"
    if name.startswith("fastembed.bm25") or name.endswith("bm25_encode"):
        return "BM25 encode"
    if name.startswith("embed."):
        return "Embedding wrapper"
    if name.startswith("nlp."):
        return "spaCy NLP"
    if name == "qlocal.distance":
        return "Vector distance"
    if name == "qlocal.filter_mask":
        return "Payload filter"
    if name == "qlocal.persist_sqlite":
        return "Persist pickle+SQLite"
    if name.startswith(("qlocal.", "qdrant.", "vs.", "ent.")) or name in ("mem0.entity_exact_scan", "mem0.entity_boost"):
        return "Vector store glue"
    if name.startswith("db."):
        return "History DB SQLite"
    return "mem0/agent glue"


def load(run: str):
    S = [json.loads(l) for l in open(os.path.join(run, "spans.jsonl"))]
    by_id = {s["id"]: s for s in S}
    kids = defaultdict(list)
    for s in S:
        if s["parent"] is not None:
            kids[s["parent"]].append(s["id"])
    for s in S:
        child_wall = sum(by_id[c]["wall_ms"] for c in kids[s["id"]] if by_id[c]["thread"] == s["thread"])
        s["self_ms"] = max(s["wall_ms"] - child_wall, 0.0)
    return S, by_id, kids


def exclusive_breakdown(root, by_id, kids) -> dict[str, float]:
    out = defaultdict(float)
    stack = [root["id"]]
    while stack:
        s = by_id[stack.pop()]
        stack += kids[s["id"]]
        if s["name"].startswith("llm."):
            pre = s.get("prompt_ms", 0.0) or 0.0
            dec = s.get("predicted_ms", 0.0) or 0.0
            out["LLM prefill"] += pre
            out["LLM decode"] += dec
            out["LLM other"] += max(s["self_ms"] - pre - dec, 0.0)
        else:
            out[category(s["name"])] += s["self_ms"]
    return out


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))] if xs else float("nan")


def analyze(run: str) -> dict:
    S, by_id, kids = load(run)
    meta = json.load(open(os.path.join(run, "meta.json")))
    res: dict = {"run": run, "label": meta.get("label"), "meta": {k: meta[k] for k in
                 ("n_turns", "n_qa", "n_memories", "total_s", "tracer_overhead_us", "cache_prompt") if k in meta}}
    # ---------------- per agent-operation breakdown (steady state: chat turns >= 1)
    ops = {}
    for op in ("agent.turn", "agent.retrieve", "agent.generate", "agent.memorize", "agent.qa"):
        phase = "qa" if op == "agent.qa" else None
        roots = [s for s in S if s["name"] == op and (s.get("turn", 0) >= 1 or s.get("phase") == "qa")]
        if op == "agent.retrieve":
            roots_chat = [s for s in roots if s.get("phase") == "chat"]
            roots_qa = [s for s in roots if s.get("phase") == "qa"]
            groups = {"agent.retrieve(chat)": roots_chat, "agent.retrieve(qa)": roots_qa}
        elif op == "agent.generate":
            groups = {"agent.generate(chat)": [s for s in roots if s.get("phase") == "chat"],
                      "agent.generate(qa)": [s for s in roots if s.get("phase") == "qa"]}
        else:
            groups = {op: roots}
        for g, rs in groups.items():
            if not rs:
                continue
            bds = [exclusive_breakdown(r, by_id, kids) for r in rs]
            walls = [r["wall_ms"] for r in rs]
            ops[g] = {"n": len(rs), "mean_ms": st.mean(walls), "p50_ms": pct(walls, 50),
                      "p95_ms": pct(walls, 95), "max_ms": max(walls),
                      "cpu_ms_mean": st.mean(r["cpu_ms"] for r in rs),
                      "wchar_mean": st.mean(r["wchar"] for r in rs),
                      "write_bytes_mean": st.mean(r["write_bytes"] for r in rs),
                      "rchar_mean": st.mean(r["rchar"] for r in rs),
                      "breakdown_mean_ms": {c: st.mean(b.get(c, 0.0) for b in bds) for c, _ in CATS}}
    res["ops"] = ops
    # ---------------- LLM call statistics
    llm = {}
    for role in sorted({s["name"] for s in S if s["name"].startswith("llm.")}):
        L = [s for s in S if s["name"] == role and s.get("prompt_ms") is not None]
        L_ss = [s for s in L if s.get("turn", 0) >= 1 or s.get("phase") == "qa"] or L
        if not L:
            continue
        def m(k, LL=L_ss):
            return st.mean((s.get(k) or 0) for s in LL)
        llm[role] = {"n": len(L_ss), "prompt_tokens": m("prompt_tokens"), "cache_n": m("cache_n"),
                     "prompt_n_computed": m("prompt_n"), "prefill_ms": m("prompt_ms"),
                     "prefill_tok_s": sum(s["prompt_n"] for s in L_ss) / max(sum(s["prompt_ms"] for s in L_ss), 1e-9) * 1e3,
                     "decode_n": m("predicted_n"), "decode_ms": m("predicted_ms"),
                     "decode_tok_s": sum(s["predicted_n"] for s in L_ss) / max(sum(s["predicted_ms"] for s in L_ss), 1e-9) * 1e3,
                     "wall_ms": m("wall_ms"),
                     "cache_hit_ratio": sum(s.get("cache_n", 0) for s in L_ss) / max(sum(s.get("prompt_tokens", 0) for s in L_ss), 1),
                     "first_call": {k: L[0].get(k) for k in ("prompt_tokens", "cache_n", "prompt_ms", "predicted_n", "predicted_ms", "wall_ms")}}
    res["llm"] = llm
    # ---------------- cold start
    cold = {}
    for s in S:
        if s["name"] in ("cold.build_memory", "mem0.init"):
            cold.setdefault(s["name"], s["wall_ms"])
    t0 = [s for s in S if s["name"] == "agent.turn" and s.get("turn") == 0]
    t_ss = ops.get("agent.turn", {}).get("mean_ms")
    if t0:
        cold["turn0_ms"] = t0[0]["wall_ms"]
        cold["turn0_breakdown"] = exclusive_breakdown(t0[0], by_id, kids)
        cold["steady_turn_mean_ms"] = t_ss
    res["cold"] = cold
    # ---------------- top self-time spans (non-LLM) in steady state
    agg = defaultdict(lambda: [0, 0.0])
    for s in S:
        if s.get("turn", 0) >= 1 and not s["name"].startswith(("llm.", "agent.")):
            agg[s["name"]][0] += 1
            agg[s["name"]][1] += s["self_ms"]
    res["top_self"] = sorted(([k, n, w] for k, (n, w) in agg.items()), key=lambda x: -x[2])[:25]
    json.dump(res, open(os.path.join(run, "breakdown.json"), "w"), indent=2)
    return res


def md(res: dict) -> str:
    L = [f"### {res['label'] or res['run']}", "", "meta: " + json.dumps(res["meta"]), ""]
    L += ["| op | n | mean ms | p50 | p95 | " + " | ".join(c for c, _ in CATS) + " |",
          "|---|---|---|---|---|" + "---|" * len(CATS)]
    for op, o in res["ops"].items():
        L.append(f"| {op} | {o['n']} | {o['mean_ms']:.0f} | {o['p50_ms']:.0f} | {o['p95_ms']:.0f} | "
                 + " | ".join(f"{o['breakdown_mean_ms'][c]:.1f}" for c, _ in CATS) + " |")
    L += ["", "| LLM role | n | prompt tok | cached tok | computed tok | prefill ms | prefill tok/s | decode tok | decode ms | decode tok/s | wall ms |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r, x in res["llm"].items():
        L.append(f"| {r} | {x['n']} | {x['prompt_tokens']:.0f} | {x['cache_n']:.0f} | {x['prompt_n_computed']:.0f} | "
                 f"{x['prefill_ms']:.0f} | {x['prefill_tok_s']:.0f} | {x['decode_n']:.0f} | {x['decode_ms']:.0f} | "
                 f"{x['decode_tok_s']:.1f} | {x['wall_ms']:.0f} |")
    return "\n".join(L)


if __name__ == "__main__":
    for run in sys.argv[1:]:
        print(md(analyze(run)))
        print()
