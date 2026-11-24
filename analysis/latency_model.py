"""First-order latency model of a memory-system op, split into a model-dependent and a system-dependent part.

    T_op ~= T_llm + T_emb + T_db + T_nlp + T_other
    T_llm  = sum over the op's LLM calls of  prefill(p | c) + decode(g | c+p) + h,   divided by kappa
             p = tokens actually prefilled (prompt_n), c = tokens reused from the KV / prompt cache (cache_n),
             g = generated tokens (predicted_n): COUNTS come from the trace (llm_calls.jsonl, llama.cpp timings),
             per-token COSTS come from a micro-benchmark (llama-bench pp512/tg at several KV depths) -- not from the
             trace, so on the machine itself this is a prediction, not a fit.
             h     = per-request overhead outside the GPU (HTTP, proxy, sampling), median over the trace
             kappa = (sum of call walls) / (union of call intervals): call-level concurrency of the system
                     (Graphiti issues parallel calls); structural, measured once on the local machine.
    T_db   = client-side DB time; its storage component is approximated by  n_flush * t_commit, where n_flush is
             the block-device flush count measured for the op (/proc/diskstats) and t_commit the 4k write + fsync
             latency from fio on the same disk. Swapping in another disk's fio result gives the disk what-if.
    T_emb, T_nlp, T_other  measured (kept fixed in what-ifs; embedding runs on the same GPU and is small).

What it is for:
  1. validation on the local machine: predicted LLM part / op wall vs measured (error %), per system and op;
  2. what-if: the same op counts on another GPU (its llama-bench file) and/or another disk (its fio file) ->
     how the LLM / storage shares shift ("on a faster GPU, does storage become the bottleneck?");
  3. cross-check: if the other GPU also ran the same runs (--check), compare its measured LLM part against the
     prediction made from the local trace.
Not modelled: contention between concurrent foreground/background requests (that is measured directly in l2/l3).

usage:
  python analysis/latency_model.py --runs results/local/HOST/l1_q4b_*_sync \
      --rates results/local/HOST/rates_q4b/llama_bench.json --fio results/local/HOST/preflight/fio_fsyncwrite.json \
      [--gpu A100=results/cloud/a100/rates_q4b/llama_bench.json] [--disk native=results/local/HOST-native/preflight/fio_fsyncwrite.json] \
      [--check A100=results/cloud/a100] [--out results/local/HOST/latency_model.json]
"""
from __future__ import annotations

import argparse
import bisect
import json
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from multi_breakdown import attribute, intervals, load  # noqa: E402

LLM_CATS = ("LLM decode", "LLM prefill+queue", "LLM queue")
OPS = ("agent.memorize", "agent.generate", "agent.retrieve")


class Rates:
    """Per-token prefill / decode cost (ms) as a function of KV depth, from llama-bench JSON."""

    def __init__(self, path: str):
        R = json.load(open(path))
        pp, tg = {}, {}
        for r in R:
            d = r.get("n_depth", 0)
            if r.get("n_prompt") and not r.get("n_gen"):
                pp[d] = r["avg_ns"] / 1e6 / r["n_prompt"]
            elif r.get("n_gen") and not r.get("n_prompt"):
                tg[d] = r["avg_ns"] / 1e6 / r["n_gen"]
        if not pp or not tg:
            raise SystemExit(f"{path}: need pp and tg rows")
        self.pp, self.tg = sorted(pp.items()), sorted(tg.items())
        self.n_pp = next((r["n_prompt"] for r in R if r.get("n_prompt")), 512)
        self.info = {k: R[0].get(k) for k in ("gpu_info", "model_type", "model_filename", "type_k", "n_gpu_layers",
                                               "n_cpu_moe", "build_number") if k in R[0]}

    @staticmethod
    def _at(tab, d):
        xs = [x for x, _ in tab]
        if len(tab) == 1:
            return tab[0][1]
        i = min(max(bisect.bisect_left(xs, d), 1), len(tab) - 1)
        (x0, y0), (x1, y1) = tab[i - 1], tab[i]
        return max(1e-6, y0 + (y1 - y0) * (d - x0) / (x1 - x0))  # linear, extrapolates past the last depth

    def prefill_ms(self, p, c):
        # pp512@d covers tokens d..d+512 -> its per-token cost belongs to depth d+256
        return p * self._at(self.pp, max(0, c + p / 2 - self.n_pp / 2))

    def decode_ms(self, g, d):
        return g * self._at(self.tg, d + g / 2)


def t_commit_ms(fio_path: str) -> float:
    j = json.load(open(fio_path))["jobs"][0]
    return (j["write"]["lat_ns"]["mean"] + (j.get("sync", {}).get("lat_ns", {}).get("mean") or 0)) / 1e6


def call_counts(c: dict) -> tuple[float, float, float]:
    lt = c.get("llama_timings") or {}
    if lt.get("prompt_n") is not None:
        return lt.get("prompt_n") or 0, lt.get("cache_n") or 0, lt.get("predicted_n") or 0
    pt, ct = c.get("prompt_tokens") or 0, c.get("cached_tokens") or 0
    return pt - ct, ct, c.get("completion_tokens") or 0


def overhead_ms(L: list[dict]) -> float:
    xs = [c["wall_ms"] - c["llama_timings"]["prompt_ms"] - c["llama_timings"]["predicted_ms"]
          for c in L if c.get("kind") == "chat" and (c.get("llama_timings") or {}).get("predicted_ms") is not None
          and c.get("wall_ms")]
    return max(0.0, st.median(xs)) if xs else 3.0


def op_rows(run: str):
    """Per steady-state op: measured attribution + the LLM calls inside it."""
    S, L, meta = load(run)
    iv = intervals(S, L)
    out = []
    for s in S:
        if s.get("flat") or s.get("phase") != "chat" or s.get("turn", 0) < 1 or s["name"] not in OPS:
            continue
        a, b = s["t0_ns"], s["t0_ns"] + int(s["wall_ms"] * 1e6)
        want = s["name"] == "agent.generate"  # agent calls only in generate, never in memorize/retrieve
        att = attribute(a, b, iv, want)
        calls = [c for c in L if c.get("kind") == "chat" and c.get("t1_ns") and c["t0_ns"] >= a and c["t1_ns"] <= b
                 and (c.get("client") == "agent") == want]
        out.append({"op": s["name"], "wall": s["wall_ms"], "att": att, "calls": calls,
                    "flush": s.get("dev_flush_ios") or 0, "flush_ms": s.get("dev_flush_ms") or 0})
    return out, L, meta


def predict(rows, rates: Rates, h: float, kappa: dict, t_commit_local: float, t_commit_tgt: float | None = None,
            reuse: bool = True):
    """-> {op: {...means...}}.  reuse=False: every cached token is prefilled again (no prefix / prompt cache)."""
    by: dict = {}
    for r in rows:
        llm_pred = 0.0
        for c in r["calls"]:
            p, cn, g = call_counts(c)
            if not reuse:
                p, cn = p + cn, 0
            llm_pred += rates.prefill_ms(p, cn) + rates.decode_ms(g, cn + p) + h
        k = kappa.get(r["op"], 1.0)
        llm_pred /= k
        att = r["att"]
        llm_meas = sum(att[x] for x in LLM_CATS)
        fs_local = r["flush"] * t_commit_local
        db = att["DB"]
        if t_commit_tgt is not None:
            db = max(0.0, db - fs_local) + r["flush"] * t_commit_tgt
            fs = r["flush"] * t_commit_tgt
        else:
            fs = fs_local
        fixed = att["Embedding"] + att["NLP"] + att["other"]
        x = by.setdefault(r["op"], {k2: [] for k2 in ("wall", "llm_meas", "llm_pred", "db", "storage", "fixed",
                                                      "pred_total", "flush", "flush_ms", "n_llm", "p_tok", "c_tok", "g_tok")})
        x["wall"].append(r["wall"]); x["llm_meas"].append(llm_meas); x["llm_pred"].append(llm_pred)
        x["db"].append(db); x["storage"].append(min(fs, db) if db else fs); x["fixed"].append(fixed)
        x["pred_total"].append(llm_pred + db + fixed)
        x["flush"].append(r["flush"]); x["flush_ms"].append(r["flush_ms"]); x["n_llm"].append(len(r["calls"]))
        cs = [call_counts(c) for c in r["calls"]]
        x["p_tok"].append(sum(a for a, _, _ in cs)); x["c_tok"].append(sum(b for _, b, _ in cs))
        x["g_tok"].append(sum(g for _, _, g in cs))
    return {op: {k: (st.mean(v) if v else 0.0) for k, v in x.items()} | {"n": len(x["wall"])} for op, x in by.items()}


def kappas(rows) -> dict:
    k: dict = {}
    for op in {r["op"] for r in rows}:
        s = sum(c["wall_ms"] for r in rows if r["op"] == op for c in r["calls"])
        u = sum(sum(r["att"][x] for x in LLM_CATS) for r in rows if r["op"] == op)
        k[op] = s / u if s and u else 1.0
    return k


def pct(a, b):
    return f"{100 * (a - b) / b:+.0f}%" if b else "-"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--rates", required=True, help="llama-bench JSON of the local GPU (same model/flags as the runs)")
    ap.add_argument("--fio", required=True, help="fio_fsyncwrite.json of the disk the runs used")
    ap.add_argument("--gpu", action="append", default=[], help="NAME=llama_bench.json of another GPU (same model)")
    ap.add_argument("--disk", action="append", default=[], help="NAME=fio_fsyncwrite.json of another disk")
    ap.add_argument("--check", action="append", default=[], help="NAME=dir with the same run names measured on GPU NAME")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    local = Rates(a.rates)
    tc = t_commit_ms(a.fio)
    gpus = {n: Rates(p) for n, p in (x.split("=", 1) for x in a.gpu)}
    disks = {n: t_commit_ms(p) for n, p in (x.split("=", 1) for x in a.disk)}
    checks = dict(x.split("=", 1) for x in a.check)
    res: dict = {"local_rates": local.info, "t_commit_ms": tc, "disks": disks,
                 "gpus": {n: r.info for n, r in gpus.items()}, "runs": {}}
    print(f"local disk: 4k write+fsync = {tc * 1e3:.0f} us" + "".join(f";  {n}: {v * 1e3:.0f} us" for n, v in disks.items()))
    print("\n| run | op | n | LLM calls | prefill / cached / gen tok | measured wall | LLM meas | LLM pred (err) "
          "| pred wall (err) | flushes | n*t_commit vs dev flush ms | LLM / storage share |")
    print("|" + "---|" * 12)
    for run in a.runs:
        run = run.rstrip("/")
        if not os.path.exists(os.path.join(run, "spans.jsonl")):
            continue
        rows, L, meta = op_rows(run)
        if not rows:
            continue
        h = overhead_ms(L)
        k = kappas(rows)
        name = os.path.basename(run)
        if name in res["runs"]:
            name = os.path.join(os.path.basename(os.path.dirname(run)), name)
        R = {"system": meta["args"]["system"], "overhead_ms": h, "kappa": k,
             "local": predict(rows, local, h, k, tc), "whatif": {}}
        for op, m in R["local"].items():
            print(f"| {name} | {op.split('.')[1]} | {m['n']} | {m['n_llm']:.1f} | {m['p_tok']:.0f} / {m['c_tok']:.0f} / {m['g_tok']:.0f} "
                  f"| {m['wall']:.0f} | {m['llm_meas']:.0f} | {m['llm_pred']:.0f} ({pct(m['llm_pred'], m['llm_meas'])}) "
                  f"| {m['pred_total']:.0f} ({pct(m['pred_total'], m['wall'])}) | {m['flush']:.1f} "
                  f"| {m['storage']:.1f} vs {m['flush_ms']:.1f} | {m['llm_pred'] / m['pred_total']:.0%} / {m['storage'] / m['pred_total']:.1%} |")
        for gn, gr in list(gpus.items()) + [(None, local)]:
            for dn, dt in list(disks.items()) + [(None, None)]:
                if gn is None and dn is None:
                    continue
                key = f"{gn or 'local GPU'} + {dn or 'local disk'}"
                R["whatif"][key] = predict(rows, gr, h, k, tc, dt)
        R["whatif"]["local GPU, no KV reuse"] = predict(rows, local, h, k, tc, reuse=False)  # cf. l3 'noprefix' (measured)
        if checks:
            R["check"] = {}
            for cn, cdir in checks.items():
                cr = os.path.join(cdir, name)
                if cn not in gpus or not os.path.exists(os.path.join(cr, "spans.jsonl")):
                    continue
                crow, _, _ = op_rows(cr)
                meas = {op: st.mean(sum(r["att"][x] for x in LLM_CATS) for r in crow if r["op"] == op)
                        for op in {r["op"] for r in crow}}
                pred = R["whatif"][f"{cn} + local disk"]
                R["check"][cn] = {op: {"pred_llm": pred[op]["llm_pred"], "meas_llm": meas.get(op)} for op in pred}
        res["runs"][name] = R
    if any(r["whatif"] for r in res["runs"].values()):
        print("\nwhat-if (same op counts; LLM part re-costed with the other GPU's rates, storage with the other disk's fsync):")
        print("| run | op | scenario | pred wall | speedup vs local | LLM share | storage share | DB share |")
        print("|---|---|---|---|---|---|---|---|")
        for name, R in res["runs"].items():
            for key, W in R["whatif"].items():
                for op, m in W.items():
                    loc = R["local"][op]["pred_total"]
                    t = m["pred_total"] or 1
                    print(f"| {name} | {op.split('.')[1]} | {key} | {m['pred_total']:.0f} | x{loc / t:.2f} "
                          f"| {m['llm_pred'] / t:.0%} | {m['storage'] / t:.1%} | {m['db'] / t:.0%} |")
    for name, R in res["runs"].items():
        for cn, C in (R.get("check") or {}).items():
            for op, c in C.items():
                if c["meas_llm"]:
                    print(f"check {cn} {name} {op}: LLM part predicted {c['pred_llm']:.0f} ms vs measured {c['meas_llm']:.0f} ms "
                          f"({pct(c['pred_llm'], c['meas_llm'])})")
    if a.out:
        json.dump(res, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
