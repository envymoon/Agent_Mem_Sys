"""Memory-system adapters (one per architecture family) behind a common interface."""
from __future__ import annotations


def make(name: str, cfg: dict, run_dir: str):
    if name in ("mem0-pg", "mem0-qdrant", "mem0-local"):
        from .mem0_sys import Mem0System
        return Mem0System(cfg, run_dir, backend=name.split("-")[1])
    if name == "graphiti":
        from .graphiti_sys import GraphitiSystem
        return GraphitiSystem(cfg, run_dir)
    if name == "letta":
        from .letta_sys import LettaSystem
        return LettaSystem(cfg, run_dir)
    if name == "rag-pg":
        from .rag_sys import RagSystem
        return RagSystem(cfg, run_dir)
    raise ValueError(name)


SYSTEMS = ["rag-pg", "mem0-local", "mem0-pg", "mem0-qdrant", "graphiti", "letta"]
LOCAL_SYSTEMS = ["rag-pg", "mem0-local", "mem0-pg", "mem0-qdrant", "graphiti"]  # local 4060 study: no Letta
