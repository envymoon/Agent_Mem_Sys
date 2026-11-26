"""Standard memory benchmarks as an agent workload (layer 1: LoCoMo, LongMemEval-S).

Both are normalised to the same shape so every memory system sees the same replay:
  user   display name of the user
  turns  [{session, date, id, text, ref_reply}]   user messages in chronological order;
         ref_reply = the dataset's own assistant reply (LongMemEval) or None (LoCoMo: human-human dialogue)
  qa     [{question, answer, evidence (set of turn/session ids), qtype, date}]

LoCoMo (snap-research/locomo, locomo10.json): 10 conversations, ~300 turns each, ~200 QA each. The replayed user is
speaker_a; questions whose evidence lies in speaker_a's replayed turns are asked (category 5 adversarial has no
'answer' and is excluded, as in the mem0 paper).

LongMemEval-S (xiaowu0162/longmemeval-cleaned, longmemeval_s_cleaned.json): 500 items, each one question over its own
haystack of ~48 sessions / ~245 user turns / ~115k tokens. --item picks the haystack. With --turns smaller than the
haystack, whole sessions are kept: all evidence sessions + randomly chosen (seeded) distractor sessions, in
chronological order ("truncated haystack" -- fewer distractors, same evidence).
"""
from __future__ import annotations

import json
import random
from datetime import datetime


def parse_date(s: str | None) -> datetime:
    for fmt in ("%I:%M %p on %d %B, %Y", "%I:%M %p on %d %b, %Y", "%Y/%m/%d (%a) %H:%M"):
        try:
            return datetime.strptime((s or "").strip(), fmt)
        except ValueError:
            pass
    return datetime(2023, 5, 1)


def locomo(path: str, conv: int, max_turns: int):
    d = json.load(open(path))[conv]
    c = d["conversation"]
    user = c["speaker_a"]
    sess = sorted((k for k in c if k.startswith("session_") and not k.endswith("date_time")),
                  key=lambda k: int(k.split("_")[1]))
    turns = [{"session": s, "date": c.get(f"{s}_date_time"), "id": u["dia_id"], "text": u["text"], "ref_reply": None}
             for s in sess for u in c[s] if u["speaker"] == user][:max_turns]
    seen = {t["id"] for t in turns}
    qa = [{"question": q["question"], "answer": str(q["answer"]), "evidence": set(q["evidence"]),
           "qtype": f"locomo-cat{q.get('category')}", "date": turns[-1]["date"] if turns else None}
          for q in d["qa"] if q.get("evidence") and "answer" in q and set(q["evidence"]) <= seen]
    return user, turns, qa


def longmemeval(path: str, item: int, max_turns: int, seed: int = 0):
    d = json.load(open(path))[item]
    S = list(zip(d["haystack_session_ids"], d["haystack_dates"], d["haystack_sessions"]))
    S.sort(key=lambda x: parse_date(x[1]))
    n_user = lambda s: sum(1 for m in s[2] if m["role"] == "user")  # noqa: E731
    if max_turns and sum(map(n_user, S)) > max_turns:
        ev = set(d["answer_session_ids"])
        keep = [s for s in S if s[0] in ev]
        rest = [s for s in S if s[0] not in ev]
        random.Random(seed + item).shuffle(rest)
        for s in rest:
            if sum(map(n_user, keep)) >= max_turns:
                break
            keep.append(s)
        S = sorted(keep, key=lambda x: parse_date(x[1]))
    turns = []
    for sid, date, msgs in S:
        for k, m in enumerate(msgs):
            if m["role"] != "user":
                continue
            nxt = msgs[k + 1] if k + 1 < len(msgs) and msgs[k + 1]["role"] == "assistant" else None
            turns.append({"session": sid, "date": date, "id": f"{sid}#{k}", "text": m["content"],
                          "ref_reply": nxt["content"] if nxt else ""})
    qa = [{"question": d["question"], "answer": str(d["answer"]), "evidence": set(d["answer_session_ids"]),
           "qtype": d["question_type"], "date": d["question_date"], "question_id": d["question_id"]}]
    return "the user", turns, qa


def load(dataset: str, path: str, item: int, max_turns: int):
    if dataset == "locomo":
        return locomo(path, item, max_turns)
    if dataset == "longmemeval":
        return longmemeval(path, item, max_turns)
    raise ValueError(dataset)


def seen_ids(dataset: str, turns) -> set:
    return {t["session"] for t in turns} if dataset == "longmemeval" else {t["id"] for t in turns}
