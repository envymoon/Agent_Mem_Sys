"""End-to-end profiled run of a memory-augmented chat agent (mem0 + local LLM).

Each agent turn (the user's utterances replayed from LoCoMo conversation 0):
    1. retrieve   : mem0.search(user_msg)                      (read path)
    2. build ctx  : system prompt + retrieved memories + short-term window
    3. generate   : local LLM answer                            (agent LLM)
    4. memorize   : mem0.add([user_msg, answer])                (write path)
After the turns a QA phase issues LoCoMo questions (read path only).

Every layer is traced (see memprof/instrument.py); spans -> <out>/spans.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memprof.setup_mem0 import LLM_URL, build_memory  # noqa: E402  (sets MEM0_TELEMETRY)
from memprof.instrument import instrument_llm_client  # noqa: E402
from memprof.tracer import TRACER, measure_overhead  # noqa: E402

AGENT_SYS = (
    "You are a warm, concise personal assistant chatting with {user}. "
    "Use the long-term memories about the user when relevant. Reply in 1-3 sentences."
)


def load_turns(path: str, conv: int):
    d = json.load(open(path))[conv]
    c = d["conversation"]
    user = c["speaker_a"]
    sess = sorted((k for k in c if k.startswith("session_") and not k.endswith("date_time")),
                  key=lambda k: int(k.split("_")[1]))
    turns = []
    for s in sess:
        for u in c[s]:
            if u["speaker"] == user:
                turns.append({"session": s, "date": c.get(f"{s}_date_time"),
                              "dia_id": u["dia_id"], "text": u["text"]})
    return user, turns, d["qa"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="/home/user/locomo/data/locomo10.json")
    ap.add_argument("--conv", type=int, default=0)
    ap.add_argument("--turns", type=int, default=40)
    ap.add_argument("--qa", type=int, default=20)
    ap.add_argument("--topk", type=int, default=5)
    ap.add_argument("--window", type=int, default=6, help="short-term messages kept in prompt")
    ap.add_argument("--async-add", action="store_true",
                    help="run mem0.add in a background worker (mem0 async-mode style)")
    ap.add_argument("--think", type=float, default=0.0, help="user think time between turns (s)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    if os.path.exists(args.out):
        shutil.rmtree(args.out)
    os.makedirs(args.out)
    user, turns, qa = load_turns(args.data, args.conv)
    turns = turns[: args.turns]
    uid = user.lower()

    meta = {"args": vars(args), "llm_url": LLM_URL,
            "cache_prompt": os.environ.get("MEMPROF_CACHE_PROMPT", "1"),
            "tracer_overhead_us": measure_overhead(),
            "label": os.environ.get("MEMPROF_LABEL", "")}

    t_start = time.perf_counter()
    with TRACER.span("cold.build_memory"):
        m = build_memory(os.path.join(args.out, "store"))
    from openai import OpenAI
    agent_llm = OpenAI(base_url=LLM_URL, api_key="sk-local")
    instrument_llm_client(agent_llm, "agent_answer")

    history: list[dict] = []
    import concurrent.futures as cf
    pool = cf.ThreadPoolExecutor(max_workers=1) if args.async_add else None
    pending: list = []
    commit_lag: list[float] = []

    def memorize(i, msgs, t_submit):
        with TRACER.span("agent.memorize_async", src_turn=i):
            m.add(msgs, user_id=uid)
        commit_lag.append(time.perf_counter() - t_submit)
    for i, t in enumerate(turns):
        TRACER.context = {"phase": "chat", "turn": i}
        with TRACER.span("agent.turn", session=t["session"]):
            with TRACER.span("agent.retrieve"):
                hits = m.search(t["text"], filters={"user_id": uid}, top_k=args.topk)["results"]
            with TRACER.span("agent.build_ctx", n_mem=len(hits)):
                mem_txt = "\n".join(f"- {h['memory']}" for h in hits) or "(none)"
                msgs = [{"role": "system", "content": AGENT_SYS.format(user=user)
                         + f"\nCurrent date: {t['date']}\nLong-term memories:\n{mem_txt}"}]
                msgs += history[-args.window:]
                msgs.append({"role": "user", "content": t["text"]})
            with TRACER.span("agent.generate"):
                r = agent_llm.chat.completions.create(model="local", messages=msgs,
                                                      max_tokens=128, temperature=0.1)
                answer = r.choices[0].message.content or ""
            new = [{"role": "user", "content": t["text"]}, {"role": "assistant", "content": answer}]
            if pool is None:
                with TRACER.span("agent.memorize"):
                    m.add(new, user_id=uid)
            else:
                pending.append(pool.submit(memorize, i, new, time.perf_counter()))
                at_backlog = sum(not f.done() for f in pending)
                TRACER.spans.append({"id": -1, "parent": None, "name": "agent.backlog", "thread": 0,
                                     "wall_ms": 0, "cpu_ms": 0, "rchar": 0, "wchar": 0, "read_bytes": 0,
                                     "write_bytes": 0, "minflt": 0, "majflt": 0, "turn": i, "phase": "chat",
                                     "backlog": at_backlog, "t0_ns": time.perf_counter_ns()})
            history += [{"role": "user", "content": t["text"]},
                        {"role": "assistant", "content": answer}]
        if args.think:
            time.sleep(args.think)
        print(f"turn {i:3d} done  t={time.perf_counter() - t_start:7.1f}s", flush=True)

    if pool is not None:
        with TRACER.span("agent.drain_backlog"):
            for f in pending:
                f.result()
        meta["commit_lag_s"] = commit_lag

    # ---------------- QA (read path only) on facts already seen
    seen = {t["dia_id"] for t in turns}
    qs = [q for q in qa if q.get("evidence") and set(q["evidence"]) <= seen and "answer" in q]
    qs = qs[: args.qa]
    qa_log = []
    for j, q in enumerate(qs):
        TRACER.context = {"phase": "qa", "turn": j}
        with TRACER.span("agent.qa"):
            with TRACER.span("agent.retrieve"):
                hits = m.search(q["question"], filters={"user_id": uid}, top_k=args.topk)["results"]
            mem_txt = "\n".join(f"- {h['memory']}" for h in hits) or "(none)"
            with TRACER.span("agent.generate"):
                r = agent_llm.chat.completions.create(model="local", max_tokens=48, temperature=0.0,
                    messages=[{"role": "system", "content": "Answer briefly using the memories.\n"
                               f"Memories:\n{mem_txt}"}, {"role": "user", "content": q["question"]}])
        qa_log.append({"q": q["question"], "gold": str(q["answer"]),
                       "pred": r.choices[0].message.content, "mem": [h["memory"] for h in hits]})
    TRACER.context = {}

    # footprint of the persistent stores
    fp = {}
    for root, _, files in os.walk(os.path.join(args.out, "store")):
        for f in files:
            p = os.path.join(root, f)
            fp[os.path.relpath(p, args.out)] = os.path.getsize(p)
    meta.update({"n_turns": len(turns), "n_qa": len(qs), "store_bytes": fp,
                 "n_memories": len(m.get_all(filters={"user_id": uid}, top_k=100000)["results"]),
                 "total_s": time.perf_counter() - t_start})
    TRACER.dump(os.path.join(args.out, "spans.jsonl"))
    json.dump(meta, open(os.path.join(args.out, "meta.json"), "w"), indent=2)
    json.dump(qa_log, open(os.path.join(args.out, "qa.json"), "w"), indent=2)
    print(json.dumps({k: meta[k] for k in ("n_turns", "n_qa", "n_memories", "total_s")}))


if __name__ == "__main__":
    main()
