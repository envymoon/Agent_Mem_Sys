"""QA accuracy of a run (layer-1 benchmarks): token F1 + LLM-as-judge.

  F1     SQuAD-style token F1 between prediction and gold (the LoCoMo paper's metric).
  judge  binary CORRECT / WRONG from an LLM judge, prompt adapted per question type in the spirit of the
         LongMemEval evaluation script and the mem0 LoCoMo "J" metric (generous on wording, strict on facts;
         temporal answers allow off-by-one day counts; knowledge-update needs the latest value; preference questions
         are checked against the rubric). The judge is the locally served model (via the proxy), NOT GPT-4o as in
         the papers -> absolute numbers are comparable across our systems, not with published tables.

usage: python analysis/qa_score.py RUN_DIR            -> RUN_DIR/qa_score.json
       python analysis/qa_score.py --summary OUT_DIR  -> markdown table of all scored runs
"""
from __future__ import annotations

import collections
import glob
import json
import os
import re
import string
import sys
import urllib.request

PROXY = os.environ.get("MEMPROF_PROXY", "http://127.0.0.1:8100/v1")

BASE = ("You are grading an assistant's answer against the gold answer.\n"
        "Question: {q}\nGold answer: {gold}\nAssistant's answer: {pred}\n\n")
RULES = {
    "default": "Reply CORRECT if the assistant's answer contains the gold answer or is equivalent to it (wording, "
               "format and extra detail do not matter), otherwise WRONG. A missing answer or 'I don't know' is WRONG.",
    "temporal-reasoning": "Reply CORRECT if the answer matches the gold answer; for counts of days, weeks or months an "
                          "off-by-one difference is still CORRECT. Otherwise WRONG.",
    "knowledge-update": "The gold answer is the user's latest information. Reply CORRECT if the answer gives the latest "
                        "value (mentioning older values as well is fine), WRONG if it only gives an outdated value.",
    "single-session-preference": "The gold answer is a rubric describing what a personalised response should do. Reply "
                                 "CORRECT if the response follows the user's stated preferences per the rubric (it need "
                                 "not cover every point), otherwise WRONG.",
}
TAIL = "\nAnswer with exactly one word: CORRECT or WRONG."


def norm(s: str) -> list[str]:
    s = (s or "").lower()
    s = "".join(ch for ch in s if ch not in set(string.punctuation))
    s = re.sub(r"\b(a|an|the|and)\b", " ", s)
    return s.split()


def f1(pred: str, gold: str) -> float:
    p, g = norm(pred), norm(gold)
    common = collections.Counter(p) & collections.Counter(g)
    n = sum(common.values())
    if not p or not g or n == 0:
        return 0.0
    pr, rc = n / len(p), n / len(g)
    return 2 * pr * rc / (pr + rc)


def judge(item: dict) -> tuple[int | None, str]:
    rule = RULES.get(item.get("qtype") or "", RULES["default"])
    prompt = BASE.format(q=item["q"], gold=item["gold"], pred=item.get("pred") or "(no answer)") + rule + TAIL
    body = {"model": "judge", "temperature": 0, "max_tokens": int(os.environ.get("JUDGE_TOKENS", 512)),
            "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request(PROXY + "/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer sk-local",
                                          "X-Memprof-Client": "judge"})
    try:
        out = json.loads(urllib.request.urlopen(req, timeout=600).read())["choices"][0]["message"]["content"] or ""
    except Exception as e:  # pragma: no cover
        return None, f"error: {e!r}"[:200]
    m = re.findall(r"\b(CORRECT|WRONG)\b", out.upper())
    return (1 if m[-1] == "CORRECT" else 0) if m else None, out.strip()[-200:]


def score_run(run: str) -> dict:
    qa = json.load(open(os.path.join(run, "qa.json")))
    items = []
    for x in qa:
        j, raw = judge(x)
        items.append({"q": x["q"], "gold": x["gold"], "pred": x.get("pred"), "qtype": x.get("qtype"),
                      "f1": f1(x.get("pred") or "", x["gold"]), "judge": j, "judge_raw": raw})
    js = [i["judge"] for i in items if i["judge"] is not None]
    res = {"n": len(items), "f1": sum(i["f1"] for i in items) / len(items) if items else None,
           "judge_acc": sum(js) / len(js) if js else None, "judge_failed": len(items) - len(js), "items": items}
    json.dump(res, open(os.path.join(run, "qa_score.json"), "w"), indent=1)
    print(f"{os.path.basename(run.rstrip('/'))}: n={res['n']} F1={res['f1'] or 0:.3f} J={res['judge_acc'] or 0:.3f}")
    return res


def summary(out: str) -> None:
    rows = []
    for f in sorted(glob.glob(os.path.join(out, "*", "qa_score.json"))):
        run = os.path.dirname(f)
        s = json.load(open(f))
        meta = json.load(open(os.path.join(run, "meta.json")))
        a = meta["args"]
        rows.append((os.path.basename(run), a["system"], a.get("dataset", "locomo"), s["n"], s["f1"], s["judge_acc"]))
    print("| run | system | dataset | n QA | F1 | judge acc |")
    print("|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4] or 0:.3f} | {'-' if r[5] is None else f'{r[5]:.3f}'} |")
    agg = collections.defaultdict(list)
    for r in rows:
        agg[(r[1], r[2])].append(r)
    print("\n| system | dataset | runs | n QA | F1 (QA-weighted) | judge acc (QA-weighted) |")
    print("|---|---|---|---|---|---|")
    for (sy, ds), rs in sorted(agg.items()):
        n = sum(r[3] for r in rs)
        fw = sum((r[4] or 0) * r[3] for r in rs) / n if n else 0
        jr = [r for r in rs if r[5] is not None]
        jn = sum(r[3] for r in jr)
        jw = sum(r[5] * r[3] for r in jr) / jn if jn else None
        print(f"| {sy} | {ds} | {len(rs)} | {n} | {fw:.3f} | {'-' if jw is None else f'{jw:.3f}'} |")


if __name__ == "__main__":
    if sys.argv[1] == "--summary":
        summary(sys.argv[2])
    else:
        for r in sys.argv[1:]:
            score_run(r)
