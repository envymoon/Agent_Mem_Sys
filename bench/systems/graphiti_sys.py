"""Graphiti (open-source core of Zep): temporal knowledge graph on Neo4j.

add  = add_episode(): LLM entity extraction -> node dedup/resolution -> edge (fact) extraction ->
       edge dedup + temporal invalidation -> embeddings -> Neo4j writes (many LLM calls per episode).
search = hybrid (Neo4j vector + fulltext BM25) over facts with RRF (Graphiti default `search()`).

Graphiti is asyncio-native; a dedicated event-loop thread serves both foreground search and
(background) add, so --async-add works like in production.
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import threading
import time
from datetime import datetime, timezone

from memprof.dbwrap import instrument_all
from memprof.tracer import TRACER

from .base import MemSystem

os.environ.setdefault("GRAPHITI_TELEMETRY_ENABLED", "false")


def _make_tracer():
    from graphiti_core.tracer import Tracer, TracerSpan

    class _Span(TracerSpan):
        def __init__(self):
            self.attrs = {}

        def add_attributes(self, attributes):
            for k, v in (attributes or {}).items():
                if isinstance(v, (int, float, str, bool)):
                    self.attrs[k] = v

        def set_status(self, status, description=None):
            self.attrs["status"] = status

        def record_exception(self, exception):
            self.attrs["error"] = repr(exception)[:200]

    class _Tracer(Tracer):
        @contextlib.contextmanager
        def start_span(self, name):
            sp = _Span()
            t0 = time.perf_counter_ns()
            try:
                yield sp
            finally:
                TRACER.interval("graphiti." + name, t0, time.perf_counter_ns(), **sp.attrs)

    return _Tracer()


def _fmt_fact(e) -> str:
    """A fact with its validity interval, as Graphiti's own search_results_to_context_string presents it
    (valid_at defaults to the episode's reference time, so every fact carries a date)."""
    d = lambda t: t.strftime("%Y-%m-%d") if t else None  # noqa: E731
    if not e.valid_at:
        return e.fact
    return f"{e.fact} (valid {d(e.valid_at)} - {d(e.invalid_at) or 'present'})"


class GraphitiSystem(MemSystem):
    name = "graphiti"

    def __init__(self, cfg: dict, run_dir: str):
        super().__init__(cfg, run_dir)
        self.loop = asyncio.new_event_loop()
        self.th = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.th.start()
        self.n = 0

    def _run(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result()

    def start(self) -> None:
        from graphiti_core import Graphiti
        from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
        from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
        from graphiti_core.llm_client.config import LLMConfig
        from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient
        c = self.cfg
        llm_cfg = LLMConfig(api_key="sk-local", model=c["llm_name"], small_model=c["small_llm_name"],
                            base_url=c["proxy"])
        instrument_all()
        import graphiti_core.graphiti as gg
        if not getattr(gg, "__memprof__", False):
            gg.__memprof__ = True
            gg.create_tracer = lambda t=None, prefix="graphiti": t  # accept our tracer as-is
            # pipeline phases of add_episode / search (flat async intervals)
            for fn in ("extract_nodes", "resolve_extracted_nodes", "extract_attributes_from_nodes",
                       "extract_edges", "resolve_extracted_edges", "build_episodic_edges", "search"):
                if hasattr(gg, fn):
                    w = TRACER.wrap_async if asyncio.iscoroutinefunction(getattr(gg, fn)) else TRACER.wrap_flat
                    w(gg, fn, f"graphiti.phase.{fn}")
            for meth in ("retrieve_episodes", "_extract_and_resolve_edges", "_process_episode_data"):
                if hasattr(gg.Graphiti, meth):
                    TRACER.wrap_async(gg.Graphiti, meth, f"graphiti.phase.{meth.lstrip('_')}")

        async def init():
            self.g = Graphiti(
                c["neo4j_uri"], c["neo4j_user"], c["neo4j_password"],
                llm_client=OpenAIGenericClient(config=llm_cfg),
                embedder=OpenAIEmbedder(OpenAIEmbedderConfig(
                    api_key="sk-local", embedding_model=c["emb_name"], embedding_dim=c["emb_dim"],
                    base_url=c["proxy"])),
                cross_encoder=OpenAIRerankerClient(config=llm_cfg),
                tracer=_make_tracer())
            await self.g.build_indices_and_constraints()
        self._run(init())

    def search(self, query: str, user_id: str, k: int) -> list[str]:
        edges = self._run(self.g.search(query, group_ids=[user_id], num_results=k))
        return [_fmt_fact(e) for e in edges]

    def add(self, messages: list[dict], user_id: str, ts: datetime) -> None:
        from graphiti_core.nodes import EpisodeType
        # Graphiti's message format is "<speaker>: <text>"; extraction always makes the speaker an entity,
        # so the user's real name goes there (a bare "user" leaves facts unattached to the person asked about)
        body = "\n".join(f"{self.user_name if m['role'] == 'user' else 'assistant'}: {m['content']}" for m in messages)
        self.n += 1
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        self._run(self.g.add_episode(name=f"turn-{self.n}", episode_body=body, source=EpisodeType.message,
                                     source_description="chat with assistant", reference_time=ts,
                                     group_id=user_id))

    def _q(self, cypher: str, **params):
        recs, _, _ = self._run(self.g.driver.client.execute_query(cypher, **params))
        return recs

    def count(self, user_id: str) -> int:
        return self._q("MATCH ()-[e:RELATES_TO {group_id:$g}]->() RETURN count(e) AS n", g=user_id)[0]["n"]

    def footprint(self) -> dict:
        fp = {}
        for lbl in ("Entity", "Episodic", "Community"):
            fp[f"nodes:{lbl}"] = self._q(f"MATCH (n:{lbl}) RETURN count(n) AS n")[0]["n"]
        fp["edges:RELATES_TO"] = self._q("MATCH ()-[e:RELATES_TO]->() RETURN count(e) AS n")[0]["n"]
        fp["edges:MENTIONS"] = self._q("MATCH ()-[e:MENTIONS]->() RETURN count(e) AS n")[0]["n"]
        d = os.path.join(os.environ.get("SVC_DATA", "/opt/svc/data"), "neo4j", "data")
        fp["disk_bytes"] = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(d) for f in fs)
        return fp

    def stop(self) -> None:
        with contextlib.suppress(Exception):
            self._run(self.g.close())
        self.loop.call_soon_threadsafe(self.loop.stop)
