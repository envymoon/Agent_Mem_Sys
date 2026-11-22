# Agent_Mem_Sys

面向本地大规模 AI Agent 记忆系统的系统/硬件层研究。

- **报告**：[`docs/report.md`](docs/report.md) —— mem0 + 本地 LLM 的全链路延迟剖析（端到端、KV cache 配置、异步写干扰、存储规模扩展）
- **新颖性调研**：[`docs/related_work.md`](docs/related_work.md)
- `memprof/`：非侵入式分层打点（span tracer + mem0 / qdrant / fastembed / spaCy / SQLite / llama.cpp timings）
- `bench/agent_e2e.py`：LoCoMo 重放的记忆增强对话 agent；`bench/scale_store.py`：记忆规模扩展（LLM 桩）
- `analysis/`：分解、对比、作图脚本；`results/`：原始 trace（`spans.jsonl`）与汇总
- `scripts/`：llama-server 启动与实验套件

## GPU / multi-architecture extension (Colab)

Same workload across five memory architectures (RAG baseline, mem0 on pgvector / Qdrant server,
Graphiti on Neo4j, Letta on Postgres) on a production-style local stack (vLLM + native DB servers).
Plan and rationale: [`docs/gpu_plan.md`](docs/gpu_plan.md). Run it with [`colab/memprof_gpu.ipynb`](colab/memprof_gpu.ipynb).

| Piece | File |
|---|---|
| OpenAI-compatible logging proxy (TTFT / decode / queue / cached tokens for every system) | `memprof/llm_proxy.py` |
| GPU / vLLM-metrics / per-service CPU sampler | `memprof/hwmon.py` |
| DB driver instrumentation (psycopg, neo4j, qdrant) | `memprof/dbwrap.py` |
| Memory-system adapters | `bench/systems/` |
| Driver (sync / async write path) | `bench/multi_e2e.py` |
| Cross-system exclusive latency attribution | `analysis/multi_breakdown.py` |
| Services (no Docker), vLLM, Letta, Colab setup, resumable suite | `scripts/services.sh`, `scripts/start_vllm.sh`, `scripts/letta.sh`, `scripts/colab_setup.sh`, `scripts/run_gpu_suite.sh` |
