"""Baseline: raw-turn RAG on pgvector (no LLM on the write path).

add    = embed the turn text, INSERT into a pgvector table (HNSW, cosine)
search = embed query, ORDER BY embedding <=> q LIMIT k (per user)
This is the control that separates 'memory = LLM-curated store' costs from plain retrieval costs.
"""
from __future__ import annotations

import os
from datetime import datetime

from memprof.dbwrap import instrument_all
from memprof.tracer import TRACER

from .base import MemSystem, pg_table_sizes


class RagSystem(MemSystem):
    name = "rag-pg"
    uses_pg = True

    def __init__(self, cfg: dict, run_dir: str):
        super().__init__(cfg, run_dir)
        self.tbl = "rag_" + os.path.basename(run_dir.rstrip("/")).replace("-", "_")[:40]

    def start(self) -> None:
        import psycopg
        from openai import OpenAI
        from pgvector.psycopg import register_vector
        instrument_all()
        self.oa = OpenAI(base_url=self.cfg["proxy"], api_key="sk-local")
        TRACER.wrap_flat(self.oa.embeddings, "create", "client.embed")
        self.conn = psycopg.connect(self.cfg["pg_dsn"], autocommit=True)
        register_vector(self.conn)
        d = self.cfg["emb_dim"]
        self.conn.execute(f"CREATE TABLE IF NOT EXISTS {self.tbl} (id bigserial PRIMARY KEY, user_id text, "
                          f"ts timestamptz, text text, embedding vector({d}))")
        self.conn.execute(f"CREATE INDEX IF NOT EXISTS {self.tbl}_hnsw ON {self.tbl} "
                          f"USING hnsw (embedding vector_cosine_ops)")
        self.conn.execute(f"CREATE INDEX IF NOT EXISTS {self.tbl}_user ON {self.tbl} (user_id)")

    def _embed(self, texts: list[str]):
        import numpy as np
        r = self.oa.embeddings.create(model=self.cfg["emb_name"], input=texts)
        return [np.asarray(x.embedding, dtype=np.float32) for x in r.data]

    def add(self, messages: list[dict], user_id: str, ts: datetime) -> None:
        text = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
        (e,) = self._embed([text])
        self.conn.execute(f"INSERT INTO {self.tbl} (user_id, ts, text, embedding) VALUES (%s,%s,%s,%s)",
                          (user_id, ts, text, e))

    def search(self, query: str, user_id: str, k: int) -> list[str]:
        (q,) = self._embed([query])
        rows = self.conn.execute(f"SELECT ts, text FROM {self.tbl} WHERE user_id=%s ORDER BY embedding <=> %s LIMIT %s",
                                 (user_id, q, k)).fetchall()
        return [f"[{r[0]:%Y-%m-%d}] {r[1]}" if r[0] else r[1] for r in rows]

    def count(self, user_id: str) -> int:
        return self.conn.execute(f"SELECT count(*) FROM {self.tbl} WHERE user_id=%s", (user_id,)).fetchone()[0]

    def footprint(self) -> dict:
        return {"pg:" + k: v for k, v in pg_table_sizes(self.cfg["pg_dsn"], self.tbl + "%").items()}

    def stop(self) -> None:
        self.conn.close()
