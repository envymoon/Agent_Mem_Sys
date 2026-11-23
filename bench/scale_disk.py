"""Store-size scaling with production backends, hot vs. cold page cache (the SSD tier of the memory store).

For each backend and each store size N:
  populate  bulk-insert N memories (LoCoMo utterances, real embeddings from the local embedder; beyond the
            unique corpus, recycled vectors get a small perturbation so the HNSW graph stays realistic).
            mem0 backends go through mem0's own vector-store / entity-store objects (BM25 lemmas, entities).
  hot       Q searches through the system's normal search path (query embedding included), then K adds
            (mem0: extraction LLM stubbed, so this is the store's write cost only)
  cold      stop the backend server (or close the embedded store), sync + drop the page cache, restart,
            reopen, then the same Q searches: the first ones pay real SSD reads (index + heap / payload pages)
Per query: wall, DB-driver time, embedding time, block-layer bytes read by the backend process.

backends: rag-pg (pgvector HNSW), mem0-pg, mem0-qdrant (Qdrant server), mem0-local (embedded Qdrant, mem0 default)
Needs root (drop_caches, services restart) and the stack from scripts/local/start_llama.sh (embedder via proxy).

usage: python bench/scale_disk.py --backend mem0-pg --sizes 1000,10000,50000,100000 --out results/local/x/scale_mem0-pg
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import statistics as st
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np  # noqa: E402

from bench.systems import make  # noqa: E402
from bench.systems.base import default_cfg  # noqa: E402
from memprof import iostat  # noqa: E402
from memprof.tracer import TRACER  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STUB = json.dumps({"memory": [{"text": "User mentioned a new hobby: {x}"}, {"text": "User plans to visit {y}"}]})


def corpus(data: str):
    D = json.load(open(data))
    texts, qs = [], []
    for d in D:
        for k, v in d["conversation"].items():
            if k.startswith("session_") and isinstance(v, list):
                texts += [u["speaker"] + ": " + u["text"] for u in v]
        qs += [q["question"] for q in d["qa"]]
    return list(dict.fromkeys(texts)), qs


def embed_all(sysm, texts: list[str], cache: str) -> np.ndarray:
    if os.path.exists(cache):
        E = np.load(cache)
        if len(E) == len(texts):
            return E
    from openai import OpenAI
    oa = OpenAI(base_url=sysm.cfg["proxy"], api_key="sk-local")
    out = []
    for i in range(0, len(texts), 64):
        r = oa.embeddings.create(model=sysm.cfg["emb_name"], input=texts[i:i + 64])
        out += [x.embedding for x in r.data]
    E = np.asarray(out, dtype=np.float32)
    np.save(cache, E)
    return E


def sample(texts, E, start: int, n: int, rng) -> tuple[list[str], np.ndarray]:
    idx = [(start + j) % len(texts) for j in range(n)]
    tb = [texts[i] + ("" if start + j < len(texts) else f" (#{(start + j) // len(texts)})") for j, i in enumerate(idx)]
    V = E[idx].copy()
    rec = np.array([(start + j) >= len(texts) for j in range(n)])
    if rec.any():
        V[rec] += rng.normal(0, 0.02, size=(rec.sum(), V.shape[1])).astype(np.float32)
        V[rec] /= np.linalg.norm(V[rec], axis=1, keepdims=True)
    return tb, V


def populate(sysm, backend: str, tb: list[str], V: np.ndarray, uid: str) -> None:
    TRACER.enabled = False
    try:
        if backend == "rag-pg":
            now = datetime.now(timezone.utc)
            with sysm.conn.cursor() as cur:
                cur.executemany(f"INSERT INTO {sysm.tbl} (user_id, ts, text, embedding) VALUES (%s,%s,%s,%s)",
                                [(uid, now, t, v) for t, v in zip(tb, V)])
            return
        from mem0.utils.entity_extraction import extract_entities_batch
        from mem0.utils.lemmatization import lemmatize_for_bm25
        m = sysm.m
        for s in range(0, len(tb), 512):
            t, v = tb[s:s + 512], V[s:s + 512]
            now = datetime.now(timezone.utc).isoformat()
            ids = [str(uuid.uuid4()) for _ in t]
            m.vector_store.insert(vectors=[x.tolist() for x in v], ids=ids, payloads=[
                {"data": x, "text_lemmatized": lemmatize_for_bm25(x), "hash": hashlib.md5(x.encode()).hexdigest(),
                 "user_id": uid, "created_at": now, "updated_at": now} for x in t])
            agg: dict[str, set[str]] = {}
            for mid, el in zip(ids, extract_entities_batch(t)):
                for _, et in el:
                    agg.setdefault(et, set()).add(mid)
            if agg:
                keys = list(agg)
                ev = m.embedding_model.embed_batch(keys, "add")
                m.entity_store.insert(vectors=ev, ids=[str(uuid.uuid4()) for _ in keys], payloads=[
                    {"data": k, "entity_type": "X", "user_id": uid, "linked_memory_ids": sorted(agg[k])} for k in keys])
    finally:
        TRACER.enabled = True


def timed_queries(sysm, qs, uid, k) -> list[dict]:
    rows = []
    for q in qs:
        n0 = len(TRACER.spans)
        io0 = iostat.snapshot()
        t0 = time.perf_counter()
        sysm.search(q, uid, k)
        wall = (time.perf_counter() - t0) * 1e3
        io = iostat.flat(iostat.delta(io0, iostat.snapshot()))
        sp = TRACER.spans[n0:]
        rows.append({"wall_ms": wall, "db_ms": sum(s["wall_ms"] for s in sp if s["name"].startswith("db.")),
                     "embed_ms": sum(s["wall_ms"] for s in sp if s["name"].startswith("client.embed")),
                     "rd_bytes": io["io_rd_bytes"], "dev_rd_ios": io.get("dev_rd_ios", 0)})
    return rows


def summ(rows: list[dict], key: str) -> dict:
    xs = sorted(r[key] for r in rows)
    return {"first": rows[0][key], "p50": xs[len(xs) // 2], "p95": xs[min(len(xs) - 1, int(len(xs) * .95))],
            "mean": st.mean(xs)}


def svc(cmd: str, what: str) -> float:
    t0 = time.perf_counter()
    subprocess.run([os.path.join(ROOT, "scripts/services.sh"), cmd, what], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return time.perf_counter() - t0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", required=True, choices=["rag-pg", "mem0-pg", "mem0-qdrant", "mem0-local"])
    ap.add_argument("--data", default=os.environ.get("LOCOMO", os.path.expanduser("~/locomo/data/locomo10.json")))
    ap.add_argument("--sizes", default="1000,10000,50000,100000")
    ap.add_argument("--queries", type=int, default=30)
    ap.add_argument("--adds", type=int, default=10)
    ap.add_argument("--topk", type=int, default=10)
    ap.add_argument("--no-cold", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    cfg = default_cfg()
    uid = "u0"
    server = {"rag-pg": "pg", "mem0-pg": "pg", "mem0-qdrant": "qdrant"}.get(a.backend)
    texts, qs = corpus(a.data)
    qs = qs[: a.queries]
    rng = np.random.default_rng(0)

    sysm = make(a.backend, cfg, out)
    sysm.start()
    if a.backend.startswith("mem0"):
        i = [0]

        def gen(*_a, **_k):
            i[0] += 1
            return STUB.replace("{x}", f"pottery-{i[0]}").replace("{y}", f"city-{i[0]}")
        sysm.m.llm.generate_response = gen
    E = embed_all(sysm, texts, os.path.join(os.path.dirname(out), "_corpus_emb.npy"))
    sysm.search("warm up", uid, a.topk)
    loaded, results = 0, []
    for N in [int(x) for x in a.sizes.split(",")]:
        tb, V = sample(texts, E, loaded, N - loaded, rng)
        io0 = iostat.snapshot()
        t0 = time.perf_counter()
        populate(sysm, a.backend, tb, V, uid)
        pop_s = time.perf_counter() - t0
        pop_io = iostat.flat(iostat.delta(io0, iostat.snapshot()))
        loaded = N
        row: dict = {"N": N, "backend": a.backend, "populate_s": pop_s, "populate_wr_mb": pop_io["io_wr_bytes"] / 2**20}
        row["hot"] = timed_queries(sysm, qs, uid, a.topk)
        if a.backend != "rag-pg":
            wl = []
            for j in range(a.adds):
                n0 = len(TRACER.spans)
                io0 = iostat.snapshot()
                t0 = time.perf_counter()
                sysm.add([{"role": "user", "content": f"I just started pottery class number {j}."}], uid, datetime.now())
                io = iostat.flat(iostat.delta(io0, iostat.snapshot()))
                wl.append({"wall_ms": (time.perf_counter() - t0) * 1e3,
                           "db_ms": sum(s["wall_ms"] for s in TRACER.spans[n0:] if s["name"].startswith("db.")),
                           "wr_bytes": io["io_wr_bytes"], "flushes": io.get("dev_flush_ios", 0)})
            row["add"] = wl
        if not a.no_cold:
            sysm.stop()
            restart_s = 0.0
            if server:
                svc("stop", server)
            dropped = iostat.drop_caches()
            if server:
                restart_s = svc("start", server)
            t0 = time.perf_counter()
            sysm = make(a.backend, cfg, out)
            sysm.start()
            if a.backend.startswith("mem0"):
                sysm.m.llm.generate_response = gen
            row.update(cold_dropped=dropped, cold_restart_s=restart_s, cold_open_s=time.perf_counter() - t0)
            row["cold"] = timed_queries(sysm, qs, uid, a.topk)
        row["footprint"] = sysm.footprint()
        row["summary"] = {ph: {k: summ(row[ph], k) for k in ("wall_ms", "db_ms", "rd_bytes")}
                          for ph in ("hot", "cold") if ph in row}
        results.append(row)
        s = row["summary"]
        print(f"[{a.backend}] N={N:7d} populate={pop_s:6.1f}s hot p50={s['hot']['wall_ms']['p50']:.1f}ms "
              f"(db {s['hot']['db_ms']['p50']:.1f})"
              + (f" | cold first={s['cold']['wall_ms']['first']:.0f}ms p50={s['cold']['wall_ms']['p50']:.1f}ms "
                 f"rd={sum(r['rd_bytes'] for r in row['cold']) / 2**20:.1f}MB open={row['cold_open_s']:.2f}s"
                 if "cold" in s else ""), flush=True)
        json.dump(results, open(os.path.join(out, "scale.json"), "w"), indent=1, default=str)
    sysm.stop()


if __name__ == "__main__":
    main()
