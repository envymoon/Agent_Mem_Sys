"""Scaling study of mem0's non-LLM data path vs. number of stored memories N.

The LLM is stubbed (fixed extraction JSON) so we isolate what the *memory
system* itself costs as it grows: embedding, spaCy, BM25 encoding, vector
scan, payload filtering, entity boosting, SQLite/pickle persistence, cold
open (reload of the on-disk store) and resident memory.

Memories are LoCoMo utterances (all 10 conversations, recycled with a
suffix when N exceeds the corpus) so text statistics are realistic.
Two layouts:
  single : all N memories belong to the queried user
  multi  : N memories spread over 100 users, query one user (multi-tenant)
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import shutil
import sys
import time
import uuid
import hashlib
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memprof.setup_mem0 import build_memory  # noqa: E402
from memprof.tracer import TRACER  # noqa: E402

import psutil  # noqa: E402

STUB_JSON = json.dumps({"memory": [
    {"text": "User mentioned a new hobby: {x}"},
    {"text": "User plans to visit {y} next month"},
]})


def corpus(data: str) -> tuple[list[str], list[str]]:
    D = json.load(open(data))
    texts, qs = [], []
    for d in D:
        c = d["conversation"]
        for k, v in c.items():
            if k.startswith("session_") and isinstance(v, list):
                texts += [u["speaker"] + ": " + u["text"] for u in v]
        qs += [q["question"] for q in d["qa"]]
    return texts, qs


def populate(m, texts: list[str], users: list[str], batch: int = 512) -> None:
    """Bulk-load memories through mem0's own building blocks (embed, lemmatize,
    entity extraction, vector-store insert, entity-store insert)."""
    from mem0.utils.entity_extraction import extract_entities_batch
    from mem0.utils.lemmatization import lemmatize_for_bm25
    TRACER.enabled = False
    try:
        for s in range(0, len(texts), batch):
            tb, ub = texts[s:s + batch], users[s:s + batch]
            vecs = m.embedding_model.embed_batch(tb, "add")
            now = datetime.now(timezone.utc).isoformat()
            ids = [str(uuid.uuid4()) for _ in tb]
            payloads = [{"data": t, "text_lemmatized": lemmatize_for_bm25(t),
                         "hash": hashlib.md5(t.encode()).hexdigest(), "user_id": u,
                         "created_at": now, "updated_at": now} for t, u in zip(tb, ub)]
            m.vector_store.insert(vectors=vecs, ids=ids, payloads=payloads)
            ents = extract_entities_batch(tb)
            agg: dict[tuple[str, str], set[str]] = {}
            for mid, u, el in zip(ids, ub, ents):
                for _, et in el:
                    agg.setdefault((u, et), set()).add(mid)
            if agg:
                keys = list(agg)
                evecs = m.embedding_model.embed_batch([k[1] for k in keys], "add")
                m.entity_store.insert(vectors=evecs, ids=[str(uuid.uuid4()) for _ in keys],
                                      payloads=[{"data": k[1], "entity_type": "X", "user_id": k[0],
                                                 "linked_memory_ids": sorted(agg[k])} for k in keys])
    finally:
        TRACER.enabled = True


def stub_llm(m) -> None:
    i = [0]

    def gen(*a, **k):
        i[0] += 1
        return STUB_JSON.replace("{x}", f"pottery-{i[0]}").replace("{y}", f"city-{i[0]}")
    m.llm.generate_response = gen


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="/home/user/locomo/data/locomo10.json")
    ap.add_argument("--sizes", default="1000,4000,16000,48000")
    ap.add_argument("--layout", choices=["single", "multi"], default="single")
    ap.add_argument("--queries", type=int, default=30)
    ap.add_argument("--adds", type=int, default=10)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if os.path.exists(a.out):
        shutil.rmtree(a.out)
    os.makedirs(a.out)
    store = os.path.join(a.out, "store")
    texts, qs = corpus(a.data)
    qs = qs[: a.queries]
    proc = psutil.Process()
    summary = []

    m = build_memory(store)
    m.search("warmup", filters={"user_id": "u0"})  # load spaCy / BM25 encoder
    stub_llm(m)
    m.add("warm up the write path", user_id="u0")
    loaded = 0
    for N in [int(x) for x in a.sizes.split(",")]:
        need = N - loaded
        tb = [texts[(loaded + j) % len(texts)] + ("" if loaded + j < len(texts) else f" (#{(loaded + j) // len(texts)})")
              for j in range(need)]
        ub = ["u0"] * need if a.layout == "single" else [f"u{(loaded + j) % 100}" for j in range(need)]
        t0 = time.perf_counter()
        populate(m, tb, ub)
        pop_s = time.perf_counter() - t0
        loaded = N
        # ---- cold open: drop and reopen the on-disk store
        m.vector_store.client.close()
        del m
        gc.collect()
        rss0 = proc.memory_info().rss
        TRACER.context = {"N": N, "op": "open"}
        t0 = time.perf_counter()
        m = build_memory(store)
        _ = m.entity_store
        open_s = time.perf_counter() - t0
        stub_llm(m)
        m.search("warmup", filters={"user_id": "u0"})
        rss1 = proc.memory_info().rss
        # ---- read path
        TRACER.context = {"N": N, "op": "search"}
        lat = []
        for q in qs:
            t0 = time.perf_counter()
            m.search(q, filters={"user_id": "u0"}, top_k=10)
            lat.append((time.perf_counter() - t0) * 1e3)
        # ---- write path (LLM stubbed)
        TRACER.context = {"N": N, "op": "add"}
        wl = []
        for j in range(a.adds):
            t0 = time.perf_counter()
            m.add([{"role": "user", "content": f"I just started pottery class number {j}."}], user_id="u0")
            wl.append((time.perf_counter() - t0) * 1e3)
        TRACER.context = {}
        lat.sort(); wl.sort()
        row = {"N": N, "layout": a.layout, "populate_s": pop_s, "open_s": open_s,
               "rss_after_open_mb": rss1 / 2**20, "rss_delta_open_mb": (rss1 - rss0) / 2**20,
               "search_p50_ms": lat[len(lat) // 2], "search_p95_ms": lat[int(len(lat) * .95) - 1],
               "add_p50_ms": wl[len(wl) // 2], "add_max_ms": wl[-1],
               "store_mb": sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(store) for f in fs) / 2**20}
        summary.append(row)
        print(json.dumps(row), flush=True)
    TRACER.dump(os.path.join(a.out, "spans.jsonl"))
    json.dump(summary, open(os.path.join(a.out, "summary.json"), "w"), indent=2)


if __name__ == "__main__":
    main()
