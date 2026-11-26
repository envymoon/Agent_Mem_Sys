"""How long (and how many Colab compute units) would the full suites take, extrapolated from finished runs
(normally the `pilot` suite).

Per (profile, system, dataset) the per-turn wall time is fitted as  wall(i) = a + b*i  over the pilot's turns:
memory stores grow, so later turns are slower (b > 0); the projection to N turns is N*a + b*N(N-1)/2 (not N times
the pilot mean). QA cost per question and the cold start are taken as measured. Every number printed is an
extrapolation from short runs: treat it as a planning figure, and re-run this after the first full run.

usage: python analysis/budget.py OUT_DIR      env: CU_PER_HOUR (from Colab's "Resources" panel), TURNS, QA,
       LME_ITEMS, LME_FULL_TURNS (default 245 = LongMemEval-S mean user turns), SESSION_SETUP_MIN, SESSION_HOURS
"""
from __future__ import annotations

import collections
import glob
import json
import math
import os
import re
import sys

E = os.environ.get


def fit(ys):
    """ys = per-turn walls without turn 0 (cold prefix / first-call warm-up). Slope only from >= 5 points."""
    n = len(ys)
    if n < 5:
        m = sum(ys) / n
        return m, 0.0
    xs = range(n)
    mx, my = (n - 1) / 2, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return my - b * mx, max(0.0, b)


def project(a, b, n):
    return n * a + b * n * (n - 1) / 2


def load_runs(out):
    R = {}
    for meta_p in glob.glob(os.path.join(out, "*", "meta.json")):
        run = os.path.dirname(meta_p)
        meta = json.load(open(meta_p))
        a = meta["args"]
        if a.get("async_add"):
            continue
        S = [json.loads(line) for line in open(os.path.join(run, "spans.jsonl"))]
        turns = sorted((s for s in S if s["name"] == "agent.turn" and s.get("phase") == "chat"), key=lambda s: s["turn"])
        qa = [s["wall_ms"] for s in S if s["name"] == "agent.qa"]
        cold = [s["wall_ms"] for s in S if s["name"] == "cold.start"]
        if not turns:
            continue
        m = re.match(r"(?:l1|l4|lme|smoke)_([a-z0-9]+)_", os.path.basename(run))
        prof = m.group(1) if m else "?"
        key = (prof, a["system"], a.get("dataset", "locomo"))
        r = R.setdefault(key, {"turns": [], "qa": [], "cold": [], "runs": 0})
        if len(turns) > len(r["turns"]):  # keep the longest run's turn series
            r["turns"] = [s["wall_ms"] / 1e3 for s in turns if s["turn"] >= 1] or [s["wall_ms"] / 1e3 for s in turns]
        r["qa"] += [x / 1e3 for x in qa]
        r["cold"] += [x / 1e3 for x in cold]
        r["runs"] += 1
    return R


def rate_ratio(out, p_from, p_to, depth=4096):
    """Relative LLM cost of profile p_to vs p_from from their llama-bench files (mean of pp and tg ratios)."""
    def costs(p):
        f = os.path.join(out, f"rates_{p}", "llama_bench.json")
        if not os.path.exists(f):
            return None
        R = json.load(open(f))
        pick = lambda rows: min(rows, key=lambda r: abs(r["n_depth"] - depth))["avg_ns"]  # noqa: E731
        pp = [r for r in R if r.get("n_prompt")]
        tg = [r for r in R if r.get("n_gen")]
        return (pick(pp) / pp[0]["n_prompt"], pick(tg) / tg[0]["n_gen"]) if pp and tg else None
    a, b = costs(p_from), costs(p_to)
    return (b[0] / a[0] + b[1] / a[1]) / 2 if a and b else None


def main() -> None:
    out = sys.argv[1]
    R = load_runs(out)
    if not R:
        sys.exit("no finished sync runs under " + out)
    turns, qa = int(E("TURNS", 100)), int(E("QA", 50))
    lme_items = len(E("LME_ITEMS", "70 233 366").split())
    lme_turns = int(E("LME_FULL_TURNS", 245))
    systems = E("SYSTEMS", "rag-pg mem0-local mem0-pg mem0-qdrant graphiti").split()
    main_p = collections.Counter(k[0] for k in R).most_common(1)[0][0]

    print(f"## measured (pilot) per-turn cost, profile {main_p}\n")
    print("| profile | system | dataset | runs | turns | s/turn first | s/turn growth per turn | s/QA | cold start s |")
    print("|---|---|---|---|---|---|---|---|---|")
    fits = {}
    for k, r in sorted(R.items()):
        a, b = fit(r["turns"])
        q = sum(r["qa"]) / len(r["qa"]) if r["qa"] else 0.0
        c = sum(r["cold"]) / len(r["cold"]) if r["cold"] else 0.0
        fits[k] = (a, b, q, c)
        print(f"| {k[0]} | {k[1]} | {k[2]} | {r['runs']} | {len(r['turns'])} | {a:.1f} | {b:.3f} | {q:.1f} | {c:.1f} |")

    def est(prof, sysname, ds, n_turns, n_qa, scale=1.0):
        f = fits.get((prof, sysname, ds)) or fits.get((main_p, sysname, ds))
        if not f:
            return None
        a, b, q, c = f
        return (project(a, b, n_turns) + n_qa * q + c) * scale / 3600

    plan = []  # (suite, description, hours or None, note)

    def add(suite, desc, hs, note=""):
        miss = sum(h is None for h in hs)
        ok = [h for h in hs if h is not None]
        if miss:
            note = (note + "; " if note else "") + f"{miss}/{len(hs)} runs have no pilot data and are NOT included"
        plan.append((suite, desc, sum(ok) if ok else None, note))

    add("l1", f"{len(systems)} systems x LoCoMo {turns} turns + {qa} QA",
        [est(main_p, s, "locomo", turns, qa) for s in systems])
    add("lme", f"{lme_items} LongMemEval-S haystacks x {len(systems)} systems x ~{lme_turns} turns",
        [est(main_p, s, "longmemeval", lme_turns, 1) for s in systems for _ in range(lme_items)],
        "full haystack; growth extrapolated far beyond the pilot -> least certain row")
    l2s = ["rag-pg", "mem0-local", "mem0-pg", "graphiti"]
    add("l2", "4 systems x async (think 0 s and 5 s) x 100 turns",
        [est(main_p, s, "locomo", 100, 0) for s in l2s] * 2 + [len(l2s) * 100 * 5 / 3600],
        "async total ~ sync total (backlog drains at the end) + think time")
    add("l3", "2 systems (mem0-pg, graphiti) x 6 KV variants x 60 turns",
        [est(main_p, s, "locomo", 60, 0) for s in ("mem0-pg", "graphiti")] * 6,
        "costed as the base variant; 'noprefix' and 'ctx8k' are slower (mem0 can be several x)")
    for p in E("L4_PROFILES", "q14b q4b").split():
        rr = rate_ratio(out, main_p, p)
        add(f"l4 {p}", f"{p}: mem0-pg + graphiti x 60 turns + 20 QA",
            [est(main_p, s, "locomo", 60, 20, rr or 1.0) for s in ("mem0-pg", "graphiti")],
            f"scaled by llama-bench cost ratio {rr:.2f}" if rr else "no rates file for this profile yet: costed as the main profile")
    plan.append(("l5", "store scale 1e3..1e5, 4 backends", 1.5, "LLM-free; embedding + DB only; planning guess"))

    setup_h = float(E("SESSION_SETUP_MIN", 30)) / 60
    sess_h = float(E("SESSION_HOURS", 10))
    cu = float(E("CU_PER_HOUR", 0) or 0)
    print("\n## projection for the full suites\n")
    print("| suite | what | hours | " + ("compute units | " if cu else "") + "note |")
    print("|---|---|---|" + ("---|" if cu else "") + "---|")
    tot = 0.0
    for s, d, h, note in plan:
        if h is not None:
            tot += h
        hs = "?" if h is None else f"{h:.1f}"
        print(f"| {s} | {d} | {hs} | " + (f"{h * cu:.0f} | " if cu and h is not None else ("? | " if cu else "")) + f"{note} |")
    n_sess = max(1, math.ceil(tot / sess_h))
    tot_all = tot + n_sess * setup_h
    print(f"\nexperiments {tot:.1f} h + setup {n_sess} runtime(s) x {setup_h * 60:.0f} min = **{tot_all:.1f} h**"
          + (f" = **{tot_all * cu:.0f} compute units** at {cu} CU/h" if cu else
             "  (set CU_PER_HOUR from Colab's Resources panel to convert to compute units)"))


if __name__ == "__main__":
    main()
