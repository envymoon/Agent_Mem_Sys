"""Compare user-facing latency in sync vs async-add runs (write-path interference).

usage: python analysis/async_stats.py results/e2e_cache_np2 results/e2e_async_np2
"""
from __future__ import annotations

import json
import os
import statistics as st
import sys


def spans(run):
    return [json.loads(l) for l in open(os.path.join(run, "spans.jsonl"))]


def stats(run: str) -> dict:
    S = spans(run)
    meta = json.load(open(os.path.join(run, "meta.json")))
    out = {"label": meta.get("label")}
    for name in ("agent.retrieve", "agent.generate", "llm.agent_answer"):
        xs = [s for s in S if s["name"] == name and s.get("phase") == "chat" and s.get("turn", 0) >= 1]
        if not xs:
            continue
        w = sorted(s["wall_ms"] for s in xs)
        out[name] = {"n": len(w), "mean_ms": st.mean(w), "p50_ms": w[len(w) // 2], "max_ms": w[-1]}
        if name == "llm.agent_answer":
            out[name]["prefill_tok_s"] = sum(s["prompt_n"] for s in xs) / sum(s["prompt_ms"] for s in xs) * 1e3
            out[name]["decode_tok_s"] = sum(s["predicted_n"] for s in xs) / sum(s["predicted_ms"] for s in xs) * 1e3
    ex = [s for s in S if s["name"] == "llm.mem0_extract"]
    if ex:
        out["extract_decode_tok_s"] = sum(s["predicted_n"] for s in ex) / sum(s["predicted_ms"] for s in ex) * 1e3
        out["extract_prefill_tok_s"] = sum(s["prompt_n"] for s in ex) / sum(s["prompt_ms"] for s in ex) * 1e3
    bl = [s["backlog"] for s in S if s["name"] == "agent.backlog"]
    if bl:
        out["backlog_per_turn"] = bl
    if "commit_lag_s" in meta:
        lag = meta["commit_lag_s"]
        out["commit_lag_s"] = {"min": min(lag), "median": sorted(lag)[len(lag) // 2], "max": max(lag)}
    turns = [s for s in S if s["name"] == "agent.turn" and s.get("turn", 0) >= 1]
    out["user_turn_ms_mean"] = st.mean(s["wall_ms"] for s in turns)
    return out


if __name__ == "__main__":
    res = [stats(r) for r in sys.argv[1:]]
    print(json.dumps(res, indent=1))
    json.dump(res, open(os.path.join(sys.argv[-1], "async_compare.json"), "w"), indent=1)
