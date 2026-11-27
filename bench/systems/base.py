from __future__ import annotations

import os
from datetime import datetime


def default_cfg() -> dict:
    """Endpoints of the shared stack (override with env vars)."""
    e = os.environ.get
    return {
        "proxy": e("MEMPROF_PROXY", "http://127.0.0.1:8100/v1"),
        "emb_dim": int(e("MEMPROF_EMB_DIM", "1024")),
        "pg_dsn": e("MEMPROF_PG_DSN", "postgresql://postgres@127.0.0.1:5432/memprof"),
        "qdrant": e("MEMPROF_QDRANT", "http://127.0.0.1:6333"),
        "neo4j_uri": e("MEMPROF_NEO4J_URI", "bolt://127.0.0.1:7687"),
        "neo4j_user": e("MEMPROF_NEO4J_USER", "neo4j"),
        "neo4j_password": e("NEO4J_PASSWORD", "memprof-neo4j"),
        "letta": e("MEMPROF_LETTA", "http://127.0.0.1:8283/v1"),
        "letta_ctx": int(e("MEMPROF_LETTA_CTX", "32768")),
        # model names the systems *send*; the proxy rewrites them to the served model
        "llm_name": e("MEMPROF_LLM_NAME", "gpt-4.1-mini"),
        "small_llm_name": e("MEMPROF_SMALL_LLM_NAME", "gpt-4.1-nano"),
        "emb_name": e("MEMPROF_EMB_NAME", "text-embedding-3-small"),
    }


class MemSystem:
    """Common interface. Explicit-memory systems implement search/add; agentic ones (Letta) chat."""
    name = "base"
    agentic = False
    uses_pg = False
    user_name = "user"  # how the replayed user is named in the conversation (LoCoMo: the speaker's name)

    def __init__(self, cfg: dict, run_dir: str):
        self.cfg = cfg
        self.run_dir = run_dir

    def start(self) -> None: ...
    def search(self, query: str, user_id: str, k: int) -> list[str]: raise NotImplementedError
    def add(self, messages: list[dict], user_id: str, ts: datetime) -> None: raise NotImplementedError
    def chat(self, text: str, user_id: str, ts: datetime) -> tuple[str, dict]: raise NotImplementedError
    def footprint(self) -> dict: return {}
    def count(self, user_id: str) -> int: return -1
    def stop(self) -> None: ...


def pg_table_sizes(dsn: str, like: str = "%") -> dict:
    import psycopg
    with psycopg.connect(dsn, autocommit=True) as c:
        rows = c.execute(
            "SELECT relname, pg_total_relation_size(c.oid) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND c.relkind='r' AND relname LIKE %s", (like,)).fetchall()
    return {r[0]: r[1] for r in rows if r[1]}
