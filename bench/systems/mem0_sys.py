"""mem0 OSS (2.x): LLM fact extraction + vector store (+ entity store, BM25 keyword search).

Production-style config: OpenAI-compatible LLM + embedder (served locally behind the proxy),
pgvector (as in mem0's self-hosted server), Qdrant server, or embedded on-disk Qdrant ("local", mem0's
out-of-the-box mode for a single-machine agent). Everything else = mem0 defaults.
"""
from __future__ import annotations

import os
import threading
import time
from datetime import datetime

from memprof.dbwrap import instrument_all
from memprof.tracer import TRACER

from .base import MemSystem, pg_table_sizes

os.environ.setdefault("MEM0_TELEMETRY", "False")


class _Clock(threading.local):
    today = None


_CLOCK = _Clock()


def _replay_clock() -> None:
    """mem0 OSS dates facts with the wall clock (its `timestamp=` is platform-only). In a replay that would
    date a 2023 conversation 'today', so the extraction prompt gets the turn's own date instead -- what the
    wall clock would have said had the conversation happened live."""
    import mem0.memory.main as mm
    if getattr(mm, "__memprof_clock__", False):
        return
    mm.__memprof_clock__ = True
    orig = mm.generate_additive_extraction_prompt

    def gen(*a, **kw):
        if _CLOCK.today and kw.get("current_date") is None:
            kw["current_date"] = _CLOCK.today
        return orig(*a, **kw)
    mm.generate_additive_extraction_prompt = gen


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


# mem0 2.x Memory._add_to_vector_store is one sequential function ("V3 phased batch pipeline"). Its phases are
# marked by the first instrumented call each one makes; a phase lasts until the next marker (so the Python glue
# between calls is included). Analysis: analysis/multi_breakdown.py (mem0_add_phases).
ADD_PHASES = ["context", "retrieve_existing", "llm_extract", "embed_new", "lemmatize_dedup", "persist",
              "entity_ner", "entity_embed", "entity_lookup", "entity_write"]
_PH = threading.local()


def _mark(k: int) -> None:
    if getattr(_PH, "cur", None) is not None and k > _PH.cur:
        _PH.cur = k
        t = time.perf_counter_ns()
        TRACER.interval("mem0.add.phase", t, t, step=k, step_name=ADD_PHASES[k])


def _phase_wrap(obj, attr: str, k) -> None:
    """k: phase index, or a function of the call args returning one (None = not an add phase)."""
    orig = getattr(obj, attr, None)
    if orig is None or getattr(orig, "__memprof_phase__", False):
        return

    def w(*a, **kw):
        kk = k(*a, **kw) if callable(k) else k
        if kk is not None:
            _mark(kk)
        return orig(*a, **kw)
    w.__memprof_phase__ = True
    setattr(obj, attr, w)


def _instrument_add_phases(m) -> None:
    import mem0.memory.main as mm
    if not getattr(mm.Memory._add_to_vector_store, "__memprof_phase__", False):
        orig = mm.Memory._add_to_vector_store

        def add_vs(self, *a, **kw):
            _PH.cur = -1
            try:
                return orig(self, *a, **kw)
            finally:
                t = time.perf_counter_ns()
                TRACER.interval("mem0.add.phase", t, t, step=len(ADD_PHASES), step_name="end")
                _PH.cur = None
        add_vs.__memprof_phase__ = True
        mm.Memory._add_to_vector_store = add_vs
        _phase_wrap(mm, "lemmatize_for_bm25", 4)
        _phase_wrap(mm, "extract_entities_batch", 6)
    _phase_wrap(m.db, "get_last_messages", 0)
    _phase_wrap(m.embedding_model, "embed",
                lambda *a, **kw: 1 if (a[1:2] or [kw.get("memory_action")])[0] == "search" else None)
    _phase_wrap(m.vector_store, "search", 1)
    _phase_wrap(m.llm, "generate_response", 2)
    _phase_wrap(m.embedding_model, "embed_batch", lambda *a, **kw: 7 if (_PH.__dict__.get("cur") or 0) >= 6 else 3)
    _phase_wrap(m.vector_store, "insert", 5)
    _phase_wrap(m.db, "batch_add_history", 5)
    _phase_wrap(m, "_existing_entities_by_text", 8)
    es = m.entity_store
    _phase_wrap(es, "search_batch", 8)
    _phase_wrap(es, "search", 8)
    _phase_wrap(es, "update", 9)
    _phase_wrap(es, "insert", 9)


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
        elif self.backend == "local":  # mem0's out-of-the-box local mode: embedded Qdrant on disk
            vs = {"provider": "qdrant", "config": {
                "path": os.path.join(self.run_dir, "store", "qdrant"), "on_disk": True,
                "collection_name": self.coll, "embedding_model_dims": c["emb_dim"]}}
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
        _instrument_add_phases(self.m)
        _replay_clock()

    def search(self, query: str, user_id: str, k: int) -> list[str]:
        r = self.m.search(query, filters={"user_id": user_id}, top_k=k)
        return [h["memory"] for h in r["results"]]

    def add(self, messages: list[dict], user_id: str, ts: datetime) -> None:
        _CLOCK.today = ts.date().isoformat()  # replay clock: "Today's date" in mem0's extraction prompt
        self.m.add(messages, user_id=user_id)

    def count(self, user_id: str) -> int:
        return len(self.m.get_all(filters={"user_id": user_id}, top_k=100000)["results"])

    def footprint(self) -> dict:
        fp = {}
        for root, _, files in os.walk(os.path.join(self.run_dir, "store")):
            for f in files:
                p = os.path.join(root, f)
                fp[("qdrant_local:" if "qdrant" in root else "sqlite:") + f] = os.path.getsize(p)
        if self.backend == "pg":
            fp.update({"pg:" + k: v for k, v in pg_table_sizes(self.cfg["pg_dsn"], self.coll + "%").items()})
        elif self.backend == "qdrant":
            try:
                import urllib.request, json
                for col in (self.coll, self.coll + "_entities"):
                    d = json.load(urllib.request.urlopen(f"{self.cfg['qdrant']}/collections/{col}"))
                    fp["qdrant:" + col + ":points"] = d["result"].get("points_count")
            except Exception:
                pass
        return fp

    def stop(self) -> None:  # flush/close embedded stores (local mode persists on close)
        import contextlib
        for st in (getattr(self.m, "vector_store", None), getattr(self.m, "_entity_store", None)):
            with contextlib.suppress(Exception):
                st.client.close()
