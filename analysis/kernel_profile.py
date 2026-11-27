"""GPU kernel-level breakdown of an Nsight Systems capture (bench/multi_e2e.py --kprof, start_llama.sh NSYS=1).

Every CUDA kernel of the LLM server inside the capture window is
  * classified by what it computes (llama.cpp kernel names: MoE/dense matmul, flash attention, quantize, norm, ...),
  * attributed to the request stage(s) the server was running when it executed, from the proxy log:
      <who>:queue / prefill / reasoning / answer   who = agent (the reply) or memory (the memory system's own calls)
    llama.cpp batches all active sequences into one forward pass, so a kernel that ran while two requests were in
    flight gets the combined label (e.g. "agent:answer+memory:reasoning").
The nsys timeline is aligned to the proxy clock by cross-correlating kernel activity with LLM-call activity
(1 ms bins), so nothing depends on nsys's timestamp base; the share of kernel time that lands inside LLM calls
after alignment is reported as a sanity check (~1.0 expected). The embedder is a separate server and is not traced.

usage: python analysis/kernel_profile.py <run_dir> [...]   -> <run>/kernel_profile.json + markdown on stdout
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys

import numpy as np

# first match wins; names are llama.cpp CUDA kernels (demangled, with template args)
CATS = [
    ("matmul MoE experts (MXFP4)", r"mul_mat.*(MXFP4|\(ggml_type\)39\b)"),
    ("matmul (quantized, other)", r"mul_mat_(vec_)?q|mul_mat_q|mmq"),
    ("matmul (f16/f32 / cuBLAS)", r"mul_mat|gemm|gemv|cutlass|xmma|cublas|ampere_|sm\d+_"),
    ("flash attention", r"flash_attn|fattn"),
    ("activation quantize", r"quantize"),
    ("router / softmax / top-k", r"soft_max|argsort|top_?k|argmax"),
    ("norm", r"norm"),
    ("rope", r"rope"),
    ("KV cache write / copy", r"set_rows|cpy|copy|concat"),
    ("gather / get_rows", r"get_rows"),
    ("elementwise (add/mul/glu/...)", r"bin_bcast|k_bin|add|mul|scale|glu|silu|gelu|unary|clamp|sum"),
]
CRX = [(c, re.compile(r, re.I)) for c, r in CATS]


def cat_of(name: str) -> str:
    for c, rx in CRX:
        if rx.search(name):
            return c
    return "other"


def export_sqlite(run: str) -> str | None:
    st = os.path.join(run, "store")
    db = os.path.join(st, "kprof.sqlite")
    rep = os.path.join(st, "kprof.nsys-rep")
    if not os.path.exists(db) and os.path.exists(rep):
        subprocess.run(["nsys", "export", "--type=sqlite", "--force-overwrite=true", f"--output={db}", rep],
                       capture_output=True, timeout=3600)
    return db if os.path.exists(db) else None


def load_kernels(db: str):
    c = sqlite3.connect(db)
    tabs = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    col = "demangledName"
    cols = {r[1] for r in c.execute("PRAGMA table_info(CUPTI_ACTIVITY_KIND_KERNEL)")}
    if col not in cols:
        col = "shortName"
    k = c.execute(f"SELECT k.start, k.end, s.value FROM CUPTI_ACTIVITY_KIND_KERNEL k "
                  f"JOIN StringIds s ON k.{col} = s.id ORDER BY k.start").fetchall()
    mc = []
    if "CUPTI_ACTIVITY_KIND_MEMCPY" in tabs:
        mc = c.execute("SELECT start, end, bytes, copyKind FROM CUPTI_ACTIVITY_KIND_MEMCPY").fetchall()
    return k, mc


def phases(calls: list[dict]) -> list[tuple[int, int, str]]:
    """(t0, t1, label) per stage of every chat call (proxy clock)."""
    out = []
    for c in calls:
        if c.get("kind") != "chat" or not c.get("t1_ns"):
            continue
        who = "agent" if c.get("client") == "agent" else "memory"
        t0, t1, tf = c["t0_ns"], c["t1_ns"], c.get("t_first_ns") or c["t1_ns"]
        pm = (c.get("llama_timings") or {}).get("prompt_ms")
        tp = max(t0, tf - int(pm * 1e6)) if pm is not None else t0
        if tp > t0:
            out.append((t0, tp, f"{who}:queue"))
        out.append((tp, tf, f"{who}:prefill"))
        ta = c.get("t_answer_ns")
        if c.get("reasoning_chunks"):
            ta = min(ta or t1, t1)
            out.append((tf, ta, f"{who}:reasoning"))
            if ta < t1:
                out.append((ta, t1, f"{who}:answer"))
        elif t1 > tf:
            out.append((tf, t1, f"{who}:answer"))
    return out


def align(ks: np.ndarray, ke: np.ndarray, ph, bin_ns=1_000_000) -> tuple[int, float]:
    """offset to add to nsys times to land on the proxy clock: max overlap of kernel activity and LLM activity."""
    k0, k1 = int(ks.min()), int(ke.max())
    a0 = min(p[0] for p in ph)
    a1 = max(p[1] for p in ph)
    K = np.zeros((k1 - k0) // bin_ns + 2)
    np.add.at(K, ((ks - k0) // bin_ns).astype(int), ((ke - ks) / bin_ns))
    A = np.zeros((a1 - a0) // bin_ns + 2)
    for t0, t1, lab in ph:
        if lab.endswith(":queue"):
            continue
        A[(t0 - a0) // bin_ns:(t1 - a0) // bin_ns + 1] = 1
    n = len(A) + len(K)
    f = np.fft.irfft(np.fft.rfft(A, n) * np.conj(np.fft.rfft(K, n)), n)
    s = int(np.argmax(f))
    if s > len(A):  # negative shift
        s -= n
    off = a0 + s * bin_ns - k0
    return off, float(f.max() / max(K.sum(), 1e-9))


def analyze(run: str) -> dict | None:
    db = export_sqlite(run)
    if not db:
        return None
    kern, mc = load_kernels(db)
    if not kern:
        return {"error": "no kernels in capture"}
    calls = [json.loads(l) for l in open(os.path.join(run, "llm_calls.jsonl"))]
    meta = json.load(open(os.path.join(run, "meta.json")))
    ks = np.array([k[0] for k in kern], dtype=np.int64)
    ke = np.array([k[1] for k in kern], dtype=np.int64)
    names = [k[2] for k in kern]
    kp = meta.get("kprof", {})
    w0 = kp.get("start", {}).get("t1_ns", 0) - 5_000_000_000
    w1 = kp.get("stop", {}).get("t0_ns", 1 << 62) + 5_000_000_000
    ph = [p for p in phases(calls) if p[1] > w0 and p[0] < w1]
    if not ph:
        return {"error": "no LLM calls in capture window"}
    off, _ = align(ks, ke, ph)
    ks, ke = ks + off, ke + off
    # timeline segments with a combined label (sweep over stage boundaries)
    ev = sorted([(p[0], 1, p[2]) for p in ph] + [(p[1], -1, p[2]) for p in ph])
    seg_t, seg_lab, active = [], [], {}
    for t, d, lab in ev:
        active[lab] = active.get(lab, 0) + d
        seg_t.append(t)
        seg_lab.append("+".join(sorted(x for x, v in active.items() if v > 0)) or "none")
    seg_t = np.array(seg_t, dtype=np.int64)
    mid = (ks + ke) // 2
    idx = np.searchsorted(seg_t, mid, side="right") - 1
    lab_of = [seg_lab[i] if i >= 0 else "none" for i in idx]
    dur = (ke - ks) / 1e6
    seg_len: dict[str, float] = {}
    for i in range(len(seg_t) - 1):
        seg_len[seg_lab[i]] = seg_len.get(seg_lab[i], 0) + (seg_t[i + 1] - seg_t[i]) / 1e6
    cats = [cat_of(n) for n in names]
    by: dict = {}
    for lab, c, d in zip(lab_of, cats, dur):
        b = by.setdefault(lab, {"kernel_ms": 0.0, "n_kernels": 0, "cats": {}})
        b["kernel_ms"] += d
        b["n_kernels"] += 1
        cc = b["cats"].setdefault(c, [0.0, 0])
        cc[0] += d
        cc[1] += 1
    for lab, b in by.items():
        b["wall_ms"] = seg_len.get(lab)
        b["gpu_busy"] = b["kernel_ms"] / b["wall_ms"] if b.get("wall_ms") else None
        b["cats"] = {c: {"ms": v[0], "n": v[1], "share": v[0] / b["kernel_ms"]} for c, v in
                     sorted(b["cats"].items(), key=lambda x: -x[1][0])}
    tot: dict = {}
    for n, d in zip(names, dur):
        short = re.sub(r"\(.*$", "", n)[:120] if "<" not in n else n[:160]
        t = tot.setdefault(short, [0.0, 0, cat_of(n)])
        t[0] += d
        t[1] += 1
    top = [{"kernel": k, "ms": v[0], "n": v[1], "mean_us": v[0] / v[1] * 1e3, "cat": v[2]}
           for k, v in sorted(tot.items(), key=lambda x: -x[1][0])[:25]]
    allcat: dict = {}
    for c, d in zip(cats, dur):
        allcat[c] = allcat.get(c, 0) + d
    kms = float(dur.sum())
    memcpy = {}
    for s0, s1, nb, kind in mc:
        m = memcpy.setdefault(str(kind), {"ms": 0.0, "bytes": 0, "n": 0})
        m["ms"] += (s1 - s0) / 1e6
        m["bytes"] += nb or 0
        m["n"] += 1
    res = {"label": meta.get("label"), "turns": kp.get("turns"), "n_kernels": len(names), "kernel_ms": kms,
           "capture_ms": (int(ke.max()) - int(ks.min())) / 1e6,
           "align": {"offset_ns": int(off), "kernel_share_in_llm_calls": 1 - by.get("none", {}).get("kernel_ms", 0) / kms},
           "by_category": {c: {"ms": v, "share": v / kms} for c, v in sorted(allcat.items(), key=lambda x: -x[1])},
           "by_stage": dict(sorted(by.items(), key=lambda x: -x[1]["kernel_ms"])), "top_kernels": top,
           "memcpy_by_kind": memcpy}
    json.dump(res, open(os.path.join(run, "kernel_profile.json"), "w"), indent=1)
    return res


def md(r: dict) -> str:
    if not r or "error" in r:
        return f"(no kernel profile: {r and r.get('error')})"
    L = [f"### {r['label']}  turns {r['turns']}: {r['n_kernels']} kernels, {r['kernel_ms']:.0f} ms kernel time "
         f"in {r['capture_ms']:.0f} ms (alignment: {r['align']['kernel_share_in_llm_calls']:.1%} inside LLM calls)",
         "", "| stage | wall ms | kernel ms | GPU busy | top categories |", "|---|---|---|---|---|"]
    for lab, b in r["by_stage"].items():
        tc = ", ".join(f"{c} {v['share']:.0%}" for c, v in list(b["cats"].items())[:4])
        busy = f"{b['gpu_busy']:.0%}" if b.get("gpu_busy") is not None else "-"
        L.append(f"| {lab} | {b['wall_ms'] or 0:.0f} | {b['kernel_ms']:.0f} | {busy} | {tc} |")
    L += ["", "| category | ms | share |", "|---|---|---|"]
    L += [f"| {c} | {v['ms']:.0f} | {v['share']:.1%} |" for c, v in r["by_category"].items()]
    return "\n".join(L)


if __name__ == "__main__":
    for run in sys.argv[1:]:
        print(md(analyze(run)))
