"""Non-invasive instrumentation of mem0 (OSS, v2.x) via monkeypatching.

Layers instrumented (span name prefix):
  mem0.*        public API + internal phases of Memory
  llm.*         OpenAI-compatible call; llama.cpp server-side timings attached
  embed.*       mem0 embedder wrapper   -> fastembed.* (ONNX runtime inside)
  vs.*          mem0 vector-store wrapper (qdrant) -> qdrant.* (client) -> qlocal.* (engine)
  nlp.*         spaCy lemmatisation / NER used for BM25 + entity linking
  db.*          SQLite history/messages store
"""
from __future__ import annotations

import os
from typing import Any

from .tracer import TRACER

# llama.cpp server option: reuse KV cache of the longest common prefix
LLM_CACHE_PROMPT = os.environ.get("MEMPROF_CACHE_PROMPT", "1") == "1"


def _len_attrs(name: str):
    def f(*a, **k):
        for v in list(a) + list(k.values()):
            if isinstance(v, (list, tuple)):
                return {name: len(v)}
        return {}
    return f


def instrument_llm_client(client: Any, role: str) -> None:
    """Wrap client.chat.completions.create; attach llama.cpp `timings`."""
    comp = client.chat.completions
    orig = comp.create
    if getattr(orig, "__memprof_wrapped__", False):
        return

    def create(*a, **k):
        if LLM_CACHE_PROMPT is not None:
            eb = dict(k.pop("extra_body", None) or {})
            eb.setdefault("cache_prompt", LLM_CACHE_PROMPT)
            k["extra_body"] = eb
        msgs = k.get("messages") or []
        chars = sum(len(m.get("content") or "") for m in msgs if isinstance(m, dict))
        with TRACER.span(f"llm.{role}", prompt_chars=chars,
                         json_mode=bool(k.get("response_format"))) as at:
            resp = orig(*a, **k)
            try:
                u = resp.usage
                at["prompt_tokens"] = u.prompt_tokens
                at["completion_tokens"] = u.completion_tokens
            except Exception:
                pass
            t = (getattr(resp, "model_extra", None) or {}).get("timings") or {}
            for key in ("prompt_n", "prompt_ms", "predicted_n", "predicted_ms", "cache_n"):
                if key in t:
                    at[key] = t[key]
            return resp

    create.__memprof_wrapped__ = True  # type: ignore[attr-defined]
    comp.create = create


_GLOBAL_DONE = False


def instrument_global() -> None:
    """Class/module level patches (shared by all Memory instances)."""
    global _GLOBAL_DONE
    if _GLOBAL_DONE:
        return
    _GLOBAL_DONE = True
    import mem0.memory.main as mm
    import fastembed
    from qdrant_client import QdrantClient
    from qdrant_client.local import local_collection as lc
    from qdrant_client.local.persistence import CollectionPersistence
    from mem0.memory.storage import SQLiteManager

    T = TRACER
    # --- mem0 module-level helpers as referenced from mem0.memory.main
    T.wrap(mm, "lemmatize_for_bm25", "nlp.lemmatize")
    T.wrap(mm, "extract_entities", "nlp.ner")
    T.wrap(mm, "extract_entities_batch", "nlp.ner_batch", _len_attrs("n"))
    T.wrap(mm, "generate_additive_extraction_prompt", "mem0.build_prompt")
    T.wrap(mm, "remove_code_blocks", "mem0.parse_llm_json")
    T.wrap(mm, "score_and_rank", "mem0.score_and_rank")
    T.wrap(mm, "parse_messages", "mem0.parse_messages")
    T.wrap(mm, "capture_event", "mem0.telemetry")
    # --- Memory methods
    T.wrap(mm.Memory, "add", "mem0.add")
    T.wrap(mm.Memory, "search", "mem0.search")
    T.wrap(mm.Memory, "_add_to_vector_store", "mem0.add.pipeline")
    T.wrap(mm.Memory, "_search_vector_store", "mem0.search.pipeline")
    T.wrap(mm.Memory, "_compute_entity_boosts", "mem0.entity_boost")
    T.wrap(mm.Memory, "_existing_entities_by_text", "mem0.entity_exact_scan")
    # --- SQLite (history + recent messages)
    for m in ("get_last_messages", "save_messages", "batch_add_history", "add_history"):
        T.wrap(SQLiteManager, m, f"db.{m}")
    # --- fastembed (ONNX) dense + sparse(BM25) encoders
    T.wrap(fastembed.TextEmbedding, "embed", "fastembed.dense", materialize=True)
    T.wrap(fastembed.SparseTextEmbedding, "embed", "fastembed.bm25", materialize=True)
    # --- qdrant client API (python) and local engine internals
    for m in ("query_points", "query_batch_points", "upsert", "scroll", "retrieve",
              "set_payload", "update_vectors", "delete", "count"):
        T.wrap(QdrantClient, m, f"qdrant.{m}",
               lambda *a, **k: {"collection": k.get("collection_name", "")})
    T.wrap(lc.LocalCollection, "search", "qlocal.scan")
    T.wrap(lc.LocalCollection, "upsert", "qlocal.upsert")
    T.wrap(lc, "calculate_payload_mask", "qlocal.filter_mask",
           lambda payloads, *a, **k: {"n_points": len(payloads)})
    T.wrap(lc, "calculate_distance", "qlocal.distance",
           lambda q, vecs, *a, **k: {"n_points": len(vecs)})
    T.wrap(CollectionPersistence, "persist", "qlocal.persist_sqlite")


def instrument_memory(m: Any) -> None:
    """Instance-level patches for one Memory object."""
    T = TRACER
    instrument_global()
    T.wrap(m.embedding_model, "embed", "embed.one")
    T.wrap(m.embedding_model, "embed_batch", "embed.batch", _len_attrs("n"))
    for store, tag in ((m.vector_store, "vs"), (m.entity_store, "ent")):
        for meth in ("search", "search_batch", "keyword_search", "insert", "update", "get", "list"):
            if hasattr(store, meth):
                T.wrap(store, meth, f"{tag}.{meth}")
        if hasattr(store, "_encode_bm25"):
            T.wrap(store, "_encode_bm25", f"{tag}.bm25_encode")
    instrument_llm_client(m.llm.client, "mem0_extract")
