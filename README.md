# Agent_Mem_Sys

面向本地大规模 AI Agent 记忆系统的系统/硬件层研究。

- **报告**：[`docs/report.md`](docs/report.md) —— mem0 + 本地 LLM 的全链路延迟剖析（端到端、KV cache 配置、异步写干扰、存储规模扩展）
- **新颖性调研**：[`docs/related_work.md`](docs/related_work.md)
- `memprof/`：非侵入式分层打点（span tracer + mem0 / qdrant / fastembed / spaCy / SQLite / llama.cpp timings）
- `bench/agent_e2e.py`：LoCoMo 重放的记忆增强对话 agent；`bench/scale_store.py`：记忆规模扩展（LLM 桩）
- `analysis/`：分解、对比、作图脚本；`results/`：原始 trace（`spans.jsonl`）与汇总
- `scripts/`：llama-server 启动与实验套件
