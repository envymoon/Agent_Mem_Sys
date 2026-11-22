"""Generic client-side instrumentation of the storage drivers used by the memory systems.

All recorded as flat intervals (safe under threads and asyncio): analysis attributes op wall time
by interval union, so concurrent DB calls inside one op are not double counted.

  db.pg.*      psycopg 3 (sync + async) cursor execute / executemany        (mem0-pgvector, RAG baseline)
  db.neo4j.*   neo4j async + sync driver: execute_query / session.run / tx.run (Graphiti)
  db.qdrant.*  qdrant_client QdrantClient (server mode over HTTP/gRPC)       (mem0-qdrant)
  db.sqlite.*  mem0 SQLiteManager (history + recent messages)
"""
from __future__ import annotations

from .tracer import TRACER

_DONE: set[str] = set()


def _sql_attrs(_self, query=None, *a, **k):
    q = query
    try:
        q = q.as_string(None) if hasattr(q, "as_string") else str(q)
    except Exception:
        q = str(q)
    head = " ".join(q.split()[:3]).upper() if q else ""
    return {"sql": head[:40]}


def _cypher_attrs(_self, query=None, *a, **k):
    q = query if isinstance(query, str) else getattr(query, "text", str(query))
    return {"cypher": " ".join((q or "").split())[:60]}


def instrument_psycopg() -> None:
    if "pg" in _DONE:
        return
    _DONE.add("pg")
    try:
        import psycopg
    except ImportError:
        return
    T = TRACER
    T.wrap_flat(psycopg.Cursor, "execute", "db.pg.execute", _sql_attrs)
    T.wrap_flat(psycopg.Cursor, "executemany", "db.pg.executemany", _sql_attrs)
    T.wrap_async(psycopg.AsyncCursor, "execute", "db.pg.execute", _sql_attrs)
    T.wrap_async(psycopg.AsyncCursor, "executemany", "db.pg.executemany", _sql_attrs)
    T.wrap_flat(psycopg.Connection, "commit", "db.pg.commit")


def instrument_neo4j() -> None:
    if "neo4j" in _DONE:
        return
    _DONE.add("neo4j")
    try:
        import neo4j
    except ImportError:
        return
    T = TRACER
    T.wrap_async(neo4j.AsyncDriver, "execute_query", "db.neo4j.execute_query", _cypher_attrs)
    T.wrap_async(neo4j.AsyncSession, "run", "db.neo4j.session_run", _cypher_attrs)
    T.wrap_async(neo4j.AsyncSession, "execute_write", "db.neo4j.execute_write")
    T.wrap_async(neo4j.AsyncSession, "execute_read", "db.neo4j.execute_read")
    T.wrap_flat(neo4j.Driver, "execute_query", "db.neo4j.execute_query", _cypher_attrs)
    T.wrap_flat(neo4j.Session, "run", "db.neo4j.session_run", _cypher_attrs)


def instrument_qdrant() -> None:
    if "qdrant" in _DONE:
        return
    _DONE.add("qdrant")
    try:
        from qdrant_client import QdrantClient
    except ImportError:
        return
    for m in ("query_points", "query_batch_points", "search", "upsert", "scroll", "retrieve",
              "set_payload", "update_vectors", "delete", "count", "create_collection", "create_payload_index"):
        if hasattr(QdrantClient, m):
            TRACER.wrap_flat(QdrantClient, m, f"db.qdrant.{m}",
                             lambda *a, **k: {"collection": k.get("collection_name", "")})


def instrument_all() -> None:
    instrument_psycopg()
    instrument_neo4j()
    instrument_qdrant()
