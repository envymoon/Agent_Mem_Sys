"""mem0 OSS (2.x): LLM fact extraction + vector store (+ entity store, BM25 keyword search).

Production-style config: OpenAI-compatible LLM + embedder (served locally behind the proxy),
pgvector (as in mem0's self-hosted server) or Qdrant server. Everything else = mem0 defaults.
"""
from __future__ import annotations

import os
from datetime import datetime

from memprof.dbwrap import instrument_all
from memprof.tracer import TRACER

from .base import MemSystem, pg_table_sizes

os.environ.setdefault("MEM0_TELEMETRY", "False")


def _instrument(m) -> None:
    import mem0.memory.main as mm
    from mem0.memory.storage import SQLiteManager
    T = TRACER
    if not getattr(mm, "__memprof_multi__", False):
        mm.__memprof_multi__ = True
        T.wrap(mm, "lemmatize_for_bm25", "nlp.lemmatize")
        T.wrap(mm, "extract_entities", "nlp.ner")
        T.wrap(mm, "extract_entities_batch", "nlp.ner_batch")
        T.wrap(mm, "score_and_rank", "mem0.score_and_rank")
        T.wrap(mm.Memory, "add", "mem0.add")
        T.wrap(mm.Memory, "search", "mem0.search")
        T.wrap(mm.Memory, "_compute_entity_boosts", "mem0.entity_boost")
        for meth in ("get_last_messages", "save_messages", "batch_add_history", "add_history"):
            T.wrap_flat(SQLiteManager, meth, f"db.sqlite.{meth}")
    for store, tag in ((m.vector_store, "vs"), (m.entity_store, "ent")):
        if hasattr(store, "_encode_bm25"):
            T.wrap_flat(store, "_encode_bm25", "nlp.bm25_encode")
    T.wrap_flat(m.embedding_model, "embed", "client.embed")
    T.wrap_flat(m.embedding_model, "embed_batch", "client.embed_batch")
    instrument_all()


class Mem0System(MemSystem):
    def __init__(self, cfg: dict, run_dir: str, backend: str = "pg"):
        super().__init__(cfg, run_dir)
        self.backend = backend
        self.name = f"mem0-{backend}"
        self.uses_pg = backend == "pg"
        self.coll = "mem0_" + os.path.basename(run_dir.rstrip("/")).replace("-", "_")[:40]

    def start(self) -> None:
        from mem0 import Memory
        c = self.cfg
        if self.backend == "pg":
            vs = {"provider": "pgvector", "config": {
                "connection_string": c["pg_dsn"], "collection_name": self.coll,
                "embedding_model_dims": c["emb_dim"], "hnsw": True}}
        else:
            host, port = c["qdrant"].split("//")[1].split(":")
            vs = {"provider": "qdrant", "config": {
                "host": host, "port": int(port), "collection_name": self.coll,
                "embedding_model_dims": c["emb_dim"]}}
        conf = {
            "llm": {"provider": "openai", "config": {
                "model": c["llm_name"], "openai_base_url": c["proxy"], "api_key": "sk-local"}},
            "embedder": {"provider": "openai", "config": {
                "model": c["emb_name"], "openai_base_url": c["proxy"], "api_key": "sk-local",
                "embedding_dims": c["emb_dim"]}},
            "vector_store": vs,
            "history_db_path": os.path.join(self.run_dir, "store", "history.db"),
        }
        os.makedirs(os.path.join(self.run_dir, "store"), exist_ok=True)
        self.m = Memory.from_config(conf)
        _ = self.m.entity_store  # create lazily-built entity collection now (cold start)
        _instrument(self.m)

    def search(self, query: str, user_id: str, k: int) -> list[str]:
        r = self.m.search(query, filters={"user_id": user_id}, top_k=k)
        return [h["memory"] for h in r["results"]]

    def add(self, messages: list[dict], user_id: str, ts: datetime) -> None:
        self.m.add(messages, user_id=user_id)

    def count(self, user_id: str) -> int:
        return len(self.m.get_all(filters={"user_id": user_id}, top_k=100000)["results"])

    def footprint(self) -> dict:
        fp = {}
        for root, _, files in os.walk(os.path.join(self.run_dir, "store")):
            for f in files:
                p = os.path.join(root, f)
                fp["sqlite:" + f] = os.path.getsize(p)
        if self.backend == "pg":
            fp.update({"pg:" + k: v for k, v in pg_table_sizes(self.cfg["pg_dsn"], self.coll + "%").items()})
        else:
            try:
                import urllib.request, json
                for col in (self.coll, self.coll + "_entities"):
                    d = json.load(urllib.request.urlopen(f"{self.cfg['qdrant']}/collections/{col}"))
                    fp["qdrant:" + col + ":points"] = d["result"].get("points_count")
            except Exception:
                pass
        return fp
