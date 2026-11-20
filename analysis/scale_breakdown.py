"""Per-component breakdown of search()/add() vs N from scale_store traces.
usage: python analysis/scale_breakdown.py results/scale_single [results/scale_multi]"""
import json, os, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze import load, category

for run in sys.argv[1:]:
    S, by_id, kids = load(run)
    out = {}
    for op, root in (("search", "mem0.search"), ("add", "mem0.add"), ("open", "mem0.init")):
        for N in sorted({s["N"] for s in S if "N" in s}):
            roots = [s for s in S if s["name"] == root and s.get("N") == N and s.get("op") == op]
            if not roots:
                continue
            agg = defaultdict(float); names = defaultdict(float)
            for r in roots:
                st = [r["id"]]
                while st:
                    s = by_id[st.pop()]; st += kids[s["id"]]
                    agg[category(s["name"])] += s["self_ms"] / len(roots)
                    names[s["name"]] += s["self_ms"] / len(roots)
            # thread-pool spans (entity boost) are parentless: attribute by op/N
            tp = [s for s in S if s.get("N") == N and s.get("op") == op and s["parent"] is None and s["name"] != root]
            for s in tp:
                names["[threadpool] " + s["name"]] += s["wall_ms"] / len(roots)
            out[f"{op}@{N}"] = {"n": len(roots), "mean_ms": sum(r["wall_ms"] for r in roots) / len(roots),
                                "by_category": dict(sorted(agg.items(), key=lambda x: -x[1])),
                                "top_spans": sorted(names.items(), key=lambda x: -x[1])[:8]}
    json.dump(out, open(os.path.join(run, "scale_breakdown.json"), "w"), indent=1)
    for k, v in out.items():
        print(run, k, round(v["mean_ms"], 1), {a: round(b, 1) for a, b in list(v["by_category"].items())[:6]})
        print("    top:", [(a, round(b, 1)) for a, b in v["top_spans"][:6]])
