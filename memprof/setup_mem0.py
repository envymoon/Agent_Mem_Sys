"""Build a fully-local mem0 Memory instance (no cloud calls, telemetry off)."""
from __future__ import annotations

import os

os.environ.setdefault("MEM0_TELEMETRY", "False")  # must precede `import mem0`

LLM_URL = os.environ.get("MEMPROF_LLM_URL", "http://127.0.0.1:8080/v1")
EMBED_MODEL = os.environ.get("MEMPROF_EMBED_MODEL", "BAAI/bge-small-en-v1.5")
EMBED_DIMS = int(os.environ.get("MEMPROF_EMBED_DIMS", "384"))


def mem0_config(run_dir: str, collection: str = "mem") -> dict:
    os.makedirs(run_dir, exist_ok=True)
    return {
        "llm": {
            "provider": "openai",
            "config": {
                "model": "local",
                "openai_base_url": LLM_URL,
                "api_key": "sk-local",
                "temperature": 0.1,
                "max_tokens": 1024,
            },
        },
        "embedder": {
            "provider": "fastembed",
            "config": {"model": EMBED_MODEL, "embedding_dims": EMBED_DIMS},
        },
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "collection_name": collection,
                "path": os.path.join(run_dir, "qdrant"),
                "on_disk": True,
                "embedding_model_dims": EMBED_DIMS,
            },
        },
        "history_db_path": os.path.join(run_dir, "history.db"),
    }


def build_memory(run_dir: str, instrument: bool = True):
    from mem0 import Memory

    from .instrument import instrument_global, instrument_memory
    from .tracer import TRACER

    if instrument:
        instrument_global()
    with TRACER.span("mem0.init"):
        m = Memory.from_config(mem0_config(run_dir))
    if instrument:
        instrument_memory(m)
    return m
