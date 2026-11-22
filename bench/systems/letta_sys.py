"""Letta (MemGPT lineage): agent-managed memory. The LLM itself edits in-context memory blocks and
searches conversation history via tool calls; state lives in Postgres + pgvector.

Letta runs as its own server (scripts/letta.sh), so the harness sees one HTTP call per user turn;
LLM / embedding calls inside it are measured by the proxy, Postgres work by pg_stat_statements and
the server's CPU by hwmon. Default agent type of the release (letta_v1_agent) and default tools.
"""
from __future__ import annotations

from datetime import datetime

import httpx

from memprof.tracer import TRACER

from .base import MemSystem, pg_table_sizes

PERSONA = "You are a warm, concise personal assistant. Use your memory about the user when relevant. Reply in 1-3 sentences."


class LettaSystem(MemSystem):
    name = "letta"
    agentic = True
    uses_pg = True

    def start(self) -> None:
        c = self.cfg
        self.http = httpx.Client(base_url=c["letta"], timeout=3600)
        TRACER.wrap_flat(self.http, "post", "letta.http_post")
        self.agents: dict[str, str] = {}
        self.llm = {"model": c["llm_name"], "model_endpoint_type": "openai", "model_endpoint": c["proxy"],
                    "context_window": c["letta_ctx"], "handle": "openai-proxy/" + c["llm_name"]}
        self.emb = {"embedding_model": c["emb_name"], "embedding_endpoint_type": "openai",
                    "embedding_endpoint": c["proxy"], "embedding_dim": c["emb_dim"],
                    "embedding_chunk_size": 300, "handle": "openai-proxy/" + c["emb_name"]}

    def _agent(self, user_id: str) -> str:
        if user_id not in self.agents:
            r = self.http.post("/agents/", json={
                "name": f"agent-{user_id}",
                "memory_blocks": [{"label": "human", "value": f"Name: {user_id.title()}"},
                                  {"label": "persona", "value": PERSONA}],
                "llm_config": self.llm, "embedding_config": self.emb})
            r.raise_for_status()
            self.agents[user_id] = r.json()["id"]
        return self.agents[user_id]

    def chat(self, text: str, user_id: str, ts: datetime) -> tuple[str, dict]:
        aid = self._agent(user_id)
        r = self.http.post(f"/agents/{aid}/messages", json={"messages": [
            {"role": "user", "content": f"[{ts:%Y-%m-%d %H:%M}] {text}"}]})
        r.raise_for_status()
        d = r.json()
        msgs = d.get("messages", [])
        answer = " ".join(m.get("content") or "" for m in msgs if m.get("message_type") == "assistant_message")
        tools = [m["tool_call"]["name"] for m in msgs if m.get("message_type") == "tool_call_message" and m.get("tool_call")]
        u = d.get("usage") or {}
        return answer, {"n_tool_calls": len(tools), "tools": ",".join(tools), "steps": u.get("step_count"),
                        "letta_prompt_tokens": u.get("prompt_tokens"), "letta_completion_tokens": u.get("completion_tokens")}

    def count(self, user_id: str) -> int:
        aid = self.agents.get(user_id)
        if not aid:
            return 0
        r = self.http.get(f"/agents/{aid}/core-memory/blocks")
        return sum(len(b.get("value", "")) for b in r.json()) if r.status_code == 200 else -1

    def footprint(self) -> dict:
        dsn = self.cfg["pg_dsn"].rsplit("/", 1)[0] + "/letta"
        return {"pg:" + k: v for k, v in pg_table_sizes(dsn).items()}
