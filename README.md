# Agent_Mem_Sys

面向本地大规模 AI Agent 记忆系统的系统/硬件层研究。

- **报告**：[`docs/report.md`](docs/report.md) —— mem0 + 本地 LLM 的全链路延迟剖析（端到端、KV cache 配置、异步写干扰、存储规模扩展）
- **新颖性调研**：[`docs/related_work.md`](docs/related_work.md)
- `memprof/`：非侵入式分层打点（span tracer + mem0 / qdrant / fastembed / spaCy / SQLite / llama.cpp timings）
- `bench/agent_e2e.py`：LoCoMo 重放的记忆增强对话 agent；`bench/scale_store.py`：记忆规模扩展（LLM 桩）
- `analysis/`：分解、对比、作图脚本；`results/`：原始 trace（`spans.jsonl`）与汇总
- `scripts/`：llama-server 启动与实验套件

## Colab 实验：第一层标准 benchmark，L4 24 GB（当前主线）

LoCoMo + LongMemEval-S 回放到 5 种记忆架构上，主模型 gpt-oss-20b（对照 Qwen3-14B、Qwen3-4B），llama.cpp 推理，
逐操作记录 LLM / 嵌入 / 数据库 / 块设备读写与 fsync。先跑 pilot 看效果和花销，再决定全套。
方案：[`docs/colab_plan.md`](docs/colab_plan.md)。入口：[`colab/memprof_colab_l1.ipynb`](colab/memprof_colab_l1.ipynb)。

## 本机实验：RTX 4060 + 真实 NVMe（备选，脚本与 Colab 共用）

在用户自己的 Windows 机器上（WSL2 Ubuntu，llama.cpp `b12559`）对比 rag-pg / mem0（嵌入式 Qdrant、pgvector、Qdrant server）/
Graphiti(Neo4j)，并逐层测 KV 放置（GPU / 主机内存 / SSD）与存储 I/O（块设备读写、fsync、冷热页缓存）。
方案：[`docs/local_plan.md`](docs/local_plan.md)。入口：`scripts/win/memprof.ps1`（Windows）→ `scripts/local/run_local_suite.sh`（WSL）。

| 组件 | 文件 |
|---|---|
| 8 GB 显存模型档位 / llama.cpp 启动（记录实际显存分配） | `scripts/local/profiles.sh`, `scripts/local/start_llama.sh` |
| 安装（CUDA toolkit、llama.cpp、服务、模型）/ 硬件与磁盘基线 | `scripts/local/setup.sh`, `scripts/local/preflight.sh` |
| 每操作的存储 I/O（/proc/pid/io、diskstats、flush、PSI） | `memprof/iostat.py` |
| KV 分层微基准（重算 / GPU / 内存缓存 / SSD slot） | `bench/kv_tier_bench.py` |
| 存储规模 × 冷热页缓存 | `bench/scale_disk.py` |
| 延迟模型：微基准速率 × trace 计数 → 本机验证误差、换 GPU / 换盘推算 | `analysis/latency_model.py` |
| WSL2 对原生 Linux 复测对照 | `analysis/platform_compare.py` |

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
