"""End-to-end profiled run of a memory-augmented agent, for any memory architecture.

Same workload for every system (LoCoMo user turns replayed, then QA on facts already seen):
  explicit-memory systems (mem0, Graphiti, RAG):  retrieve -> build ctx -> generate -> memorize
  agentic memory (Letta):                          chat (the agent LLM itself reads/writes memory)

Measured (all on CLOCK_MONOTONIC, joined at analysis time):
  spans.jsonl      harness ops + in-process layers (NLP, DB drivers, Graphiti phases, ...)
  llm_calls.jsonl  every LLM / embedding request (via memprof.llm_proxy): TTFT, decode, tokens, cache hits
  hw.jsonl         GPU util / mem-bw / power, vLLM KV usage + prefix-cache counters, per-service CPU/RSS
  meta.json        config, footprint, pg_stat_statements totals, counts

usage: python bench/multi_e2e.py --system mem0-pg --turns 40 --qa 20 --out results/gpu/mem0-pg_sync
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bench.systems import make  # noqa: E402
from bench.systems.base import default_cfg  # noqa: E402
from memprof import iostat  # noqa: E402
from memprof.tracer import TRACER, measure_overhead  # noqa: E402

AGENT_SYS = ("You are a warm, concise personal assistant chatting with {user}. "
             "Use the long-term memories about the user when relevant. Reply in 1-3 sentences.")


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
                turns.append({"session": s, "date": c.get(f"{s}_date_time"), "dia_id": u["dia_id"], "text": u["text"]})
    return user, turns, d["qa"]


def parse_date(s: str | None) -> datetime:
    for fmt in ("%I:%M %p on %d %B, %Y", "%I:%M %p on %d %b, %Y"):
        try:
            return datetime.strptime((s or "").strip(), fmt)
        except ValueError:
            pass
    return datetime(2023, 5, 1)


def pg_stats(dsn: str) -> dict:
    """Server-side Postgres work so far (all DBs): statements, exec ms, shared-buffer hits/reads, WAL."""
    try:
        import psycopg
        with psycopg.connect(dsn, autocommit=True) as c:
            r = c.execute("SELECT coalesce(sum(calls),0), coalesce(sum(total_exec_time),0), "
                          "coalesce(sum(shared_blks_hit),0), coalesce(sum(shared_blks_read),0), "
                          "coalesce(sum(wal_bytes),0) FROM pg_stat_statements").fetchone()
            w = c.execute("SELECT wal_write, wal_sync, wal_write_time, wal_sync_time FROM pg_stat_wal").fetchone()
            io = c.execute("SELECT coalesce(sum(reads),0), coalesce(sum(writes),0), coalesce(sum(fsyncs),0), "
                           "coalesce(sum(read_time),0), coalesce(sum(write_time),0), coalesce(sum(fsync_time),0) "
                           "FROM pg_stat_io").fetchone()
        return {"calls": int(r[0]), "exec_ms": float(r[1]), "blks_hit": int(r[2]), "blks_read": int(r[3]),
                "wal_bytes": int(r[4]), "wal_write": int(w[0]), "wal_sync": int(w[1]),
                "wal_write_ms": float(w[2]), "wal_sync_ms": float(w[3]),
                "io_reads": int(io[0]), "io_writes": int(io[1]), "io_fsyncs": int(io[2] or 0),
                "io_read_ms": float(io[3] or 0), "io_write_ms": float(io[4] or 0), "io_fsync_ms": float(io[5] or 0)}
    except Exception as e:  # pragma: no cover
        return {"error": repr(e)[:100]}


def proxy_ctl(proxy: str, path: str) -> None:
    base = proxy.rsplit("/v1", 1)[0]
    req = urllib.request.Request(base + "/memprof/log", data=json.dumps({"path": path}).encode(),
                                 headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=10).read()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--system", required=True)
    ap.add_argument("--data", default=os.environ.get("LOCOMO", "/home/user/locomo/data/locomo10.json"))
    ap.add_argument("--conv", type=int, default=0)
    ap.add_argument("--turns", type=int, default=40)
    ap.add_argument("--qa", type=int, default=20)
    ap.add_argument("--topk", type=int, default=10)
    ap.add_argument("--window", type=int, default=6)
    ap.add_argument("--answer-tokens", type=int, default=256)
    ap.add_argument("--async-add", action="store_true", help="memorize in a background worker")
    ap.add_argument("--think", type=float, default=0.0, help="user think time between turns (s)")
    ap.add_argument("--no-hwmon", action="store_true")
    ap.add_argument("--vllm-metrics", default=os.environ.get("MEMPROF_VLLM_METRICS", ""),
                    help="comma list of vLLM base URLs for hwmon to scrape")
    ap.add_argument("--label", default="")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    out = os.path.abspath(args.out)
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out)
    cfg = default_cfg()
    proxy_ctl(cfg["proxy"], os.path.join(out, "llm_calls.jsonl"))
    hw = None
    if not args.no_hwmon:
        hw = subprocess.Popen([sys.executable, "-m", "memprof.hwmon", "--out", os.path.join(out, "hw.jsonl"),
                               "--vllm", args.vllm_metrics], cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    user, turns, qa = load_turns(args.data, args.conv)
    turns = turns[: args.turns]
    uid = user.lower()
    meta = {"args": vars(args), "cfg": cfg, "label": args.label or args.system,
            "tracer_overhead_us": measure_overhead(), "t_start_ns": time.perf_counter_ns()}

    from openai import OpenAI
    agent_llm = OpenAI(base_url=cfg["proxy"], api_key="sk-local", default_headers={"X-Memprof-Client": "agent"})
    sysm = make(args.system, cfg, out)
    meta["pg_before"] = pg_stats(cfg["pg_dsn"]) if sysm.uses_pg else None
    meta["io_devices"] = iostat.devices()
    io_start = iostat.snapshot()
    t_start = time.perf_counter()
    TRACER.context = {"phase": "cold"}
    with TRACER.span("cold.start"):
        sysm.start()

    def pg_attrs() -> dict:
        return pg_stats(cfg["pg_dsn"]) if sysm.uses_pg else {}

    def op(name: str, fn, **attrs):
        """Run fn inside a span; attach server-side Postgres deltas and storage-I/O deltas (sync mode only:
        with a background writer the deltas could not be attributed to one op)."""
        p0 = pg_attrs() if not args.async_add else {}
        io0 = iostat.snapshot() if not args.async_add else None
        with TRACER.span(name, **attrs):
            res = fn()
        sa_ = TRACER.spans[-1]
        if io0 is not None:
            sa_.update(iostat.flat(iostat.delta(io0, iostat.snapshot())))
        if p0 and "calls" in p0:
            p1 = pg_attrs()
            # the stats query itself is excluded by being outside the span; its own row adds 1 call
            for k, v in p1.items():
                if k in p0 and isinstance(v, (int, float)):
                    sa_["pg_" + k] = v - p0[k]
        return res

    history: list[dict] = []
    pool = cf.ThreadPoolExecutor(max_workers=1) if args.async_add else None
    pending: list = []
    commit_lag: list[float] = []

    def memorize_bg(i, msgs, ts, t_submit):
        TRACER.context = {"phase": "chat", "turn": i}
        with TRACER.span("agent.memorize_async", src_turn=i):
            sysm.add(msgs, uid, ts)
        commit_lag.append(time.perf_counter() - t_submit)

    for i, t in enumerate(turns):
        TRACER.context = {"phase": "chat", "turn": i}
        ts = parse_date(t["date"])
        with TRACER.span("agent.turn", session=t["session"]):
            if sysm.agentic:
                answer, info = op("agent.chat", lambda: sysm.chat(t["text"], uid, ts))
                TRACER.spans[-1].update(info)
            else:
                hits = op("agent.retrieve", lambda: sysm.search(t["text"], uid, args.topk))
                mem_txt = "\n".join(f"- {h}" for h in hits) or "(none)"
                msgs = [{"role": "system", "content": AGENT_SYS.format(user=user)
                         + f"\nCurrent date: {t['date']}\nLong-term memories:\n{mem_txt}"}]
                msgs += history[-args.window:]
                msgs.append({"role": "user", "content": t["text"]})
                with TRACER.span("agent.generate", n_mem=len(hits)):
                    r = agent_llm.chat.completions.create(model="agent", messages=msgs,
                                                          max_tokens=args.answer_tokens, temperature=0.7)
                    answer = r.choices[0].message.content or ""
                new = [{"role": "user", "content": t["text"]}, {"role": "assistant", "content": answer}]
                if pool is None:
                    op("agent.memorize", lambda: sysm.add(new, uid, ts))
                else:
                    pending.append(pool.submit(memorize_bg, i, new, ts, time.perf_counter()))
                    TRACER.interval("agent.backlog", time.perf_counter_ns(), time.perf_counter_ns(),
                                    backlog=sum(not f.done() for f in pending))
            history += [{"role": "user", "content": t["text"]}, {"role": "assistant", "content": answer}]
        if args.think:
            time.sleep(args.think)
        print(f"[{args.system}] turn {i:3d} t={time.perf_counter() - t_start:7.1f}s", flush=True)

    if pool is not None:
        with TRACER.span("agent.drain_backlog"):
            for f in pending:
                f.result()
        meta["commit_lag_s"] = commit_lag

    seen = {t["dia_id"] for t in turns}
    qs = [q for q in qa if q.get("evidence") and set(q["evidence"]) <= seen and "answer" in q][: args.qa]
    qa_log = []
    for j, q in enumerate(qs):
        TRACER.context = {"phase": "qa", "turn": j}
        with TRACER.span("agent.qa"):
            if sysm.agentic:
                pred, _ = op("agent.chat", lambda: sysm.chat(q["question"] + " (answer briefly)", uid, ts))
                mem = []
            else:
                mem = op("agent.retrieve", lambda: sysm.search(q["question"], uid, args.topk))
                mem_txt = "\n".join(f"- {h}" for h in mem) or "(none)"
                with TRACER.span("agent.generate"):
                    r = agent_llm.chat.completions.create(model="agent", max_tokens=64, temperature=0.0, messages=[
                        {"role": "system", "content": f"Answer briefly using the memories.\nMemories:\n{mem_txt}"},
                        {"role": "user", "content": q["question"]}])
                pred = r.choices[0].message.content
        qa_log.append({"q": q["question"], "gold": str(q["answer"]), "pred": pred, "mem": mem})
    TRACER.context = {}

    meta.update({"n_turns": len(turns), "n_qa": len(qs), "total_s": time.perf_counter() - t_start,
                 "count": sysm.count(uid), "footprint": sysm.footprint(),
                 "pg_after": pg_stats(cfg["pg_dsn"]) if sysm.uses_pg else None})
    sysm.stop()
    meta["io_total"] = iostat.delta(io_start, iostat.snapshot())  # after stop(): includes final flushes
    TRACER.dump(os.path.join(out, "spans.jsonl"))
    json.dump(meta, open(os.path.join(out, "meta.json"), "w"), indent=2, default=str)
    json.dump(qa_log, open(os.path.join(out, "qa.json"), "w"), indent=2)
    if hw is not None:
        hw.send_signal(signal.SIGTERM)
        hw.wait(10)
    proxy_ctl(cfg["proxy"], os.path.join(os.path.dirname(out), "_proxy_idle.jsonl"))
    print(json.dumps({k: meta[k] for k in ("n_turns", "n_qa", "count", "total_s")}, default=str))


if __name__ == "__main__":
    main()
