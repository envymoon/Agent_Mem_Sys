"""Figures for the report (static PNG, light theme, validated categorical palette)."""
from __future__ import annotations

import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
GROUPS = {  # chart group -> analysis categories
    "LLM prefill": ["LLM prefill"],
    "LLM decode": ["LLM decode"],
    "LLM other (HTTP/sched/tokenize)": ["LLM other"],
    "Embedding (ONNX + wrapper)": ["Embedding ONNX", "Embedding wrapper"],
    "spaCy NLP + BM25 encode": ["spaCy NLP", "BM25 encode"],
    "Vector store + SQLite + Python glue": ["Vector distance", "Payload filter", "Persist pickle+SQLite",
                                            "Vector store glue", "History DB SQLite", "mem0/agent glue"],
}


def style(ax):
    ax.set_facecolor(SURF)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9, length=0)
    ax.xaxis.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)


def stacked(ax, rows, labels, title, xlabel="seconds"):
    left = [0.0] * len(rows)
    for gi, (g, cats) in enumerate(GROUPS.items()):
        vals = [sum(r.get(c, 0.0) for c in cats) / 1e3 for r in rows]
        ax.barh(range(len(rows)), vals, left=left, color=SERIES[gi], height=0.6,
                edgecolor=SURF, linewidth=1.5, label=g)
        left = [a + b for a, b in zip(left, vals)]
    for i, tot in enumerate(left):
        ax.text(tot, i, f"  {tot:.2f}s", va="center", color=INK, fontsize=9)
    ax.set_yticks(range(len(rows)), labels, color=INK)
    ax.invert_yaxis()
    ax.set_xlabel(xlabel, color=INK2)
    ax.set_title(title, color=INK, loc="left", fontsize=11)
    ax.set_xlim(0, max(left) * 1.18 if max(left) > 0 else 1)
    style(ax)


def fig_e2e(runs: list[str], out: str) -> None:
    R = [json.load(open(os.path.join(r, "breakdown.json"))) for r in runs]
    main = R[0]
    fig, axes = plt.subplots(2, 1, figsize=(10, 6.4), facecolor=SURF,
                             gridspec_kw={"height_ratios": [4, len(R)]})
    ops = [o for o in ("agent.retrieve(chat)", "agent.generate(chat)", "agent.memorize",
                       "agent.retrieve(qa)", "agent.generate(qa)") if o in main["ops"]]
    stacked(axes[0], [main["ops"][o]["breakdown_mean_ms"] for o in ops],
            [o.replace("agent.", "") for o in ops],
            f"Per-operation latency, steady state ({main['label']}: mean of turns 1..N)")
    stacked(axes[1], [r["ops"]["agent.memorize"]["breakdown_mean_ms"] for r in R],
            [r["label"] for r in R], "mem0.add() (memorize) under different LLM KV-cache configurations")
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=3, frameon=False, fontsize=9, labelcolor=INK)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(out, dpi=200, facecolor=SURF)


def fig_scale(summ_paths: list[str], out: str) -> None:
    S = [json.load(open(p)) for p in summ_paths]
    metrics = [("search_p50_ms", "search() p50 (ms)"), ("add_p50_ms", "add() p50, LLM stubbed (ms)"),
               ("open_s", "cold open of store (s)"), ("rss_after_open_mb", "process RSS after open (MB)")]
    fig, axes = plt.subplots(1, 4, figsize=(13, 3.2), facecolor=SURF)
    for ax, (k, t) in zip(axes, metrics):
        for si, s in enumerate(S):
            xs = [r["N"] for r in s]
            ax.plot(xs, [r[k] for r in s], color=SERIES[si], lw=2, marker="o", ms=5,
                    label=f"{s[0]['layout']}-tenant")
        ax.set_title(t, color=INK, loc="left", fontsize=10)
        ax.set_xlabel("memories in store (N)", color=INK2, fontsize=9)
        ax.set_xscale("log")
        ax.yaxis.grid(True, color=GRID, lw=0.8)
        style(ax)
        ax.xaxis.grid(False)
    axes[0].legend(frameon=False, fontsize=9, labelcolor=INK)
    fig.tight_layout()
    fig.savefig(out, dpi=200, facecolor=SURF)


if __name__ == "__main__":
    kind = sys.argv[1]
    if kind == "e2e":
        fig_e2e(sys.argv[3:], sys.argv[2])
    else:
        fig_scale(sys.argv[3:], sys.argv[2])
