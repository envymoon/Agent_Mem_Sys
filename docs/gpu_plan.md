# GPU 复核与多架构验证方案

目标有两个：
1. 在 GPU 上复核 CPU 实验得到的结构性结论，包括：
   - 写路径主导；
   - 静态长前缀和 decode 是大头；
   - KV 放置决定写路径成本；
   - 后台写会干扰前台；
   - 存储引擎开销随规模线性增长。
2. 判断这些是不是 **agent 记忆系统的共性问题**，而不只是 mem0 的问题。

所有组件尽量按生产环境的方式部署和配置。

## 1. Colab 能不能用

**可以，作为主力 GPU 平台足够**，但有四个限制需要在方案里处理。

| 项 | 情况 | 处理 |
|---|---|---|
| 算力预算 | 第三方实测：A100-40G 约 5.4 CU/h，A100-80G 约 7.5，L4 约 1.7，T4 约 1.2–1.8（以 Colab 资源面板为准）。200 CU 约等于 35 h A100-40G 或 100+ h L4。 | 完整一轮 A100 实验约 40 CU；再加一轮 L4 复核约 15 CU。预算有富余。 |
| 不是真正的“本地” | VM 的磁盘是网络持久盘，不是本地 NVMe；CPU 是服务器 vCPU。 | GPU、LLM、KV 和进程间争用的结论可以用。SSD 层（落盘、冷启动、mmap）的结论**仍需在用户自己的机器上测**。 |
| 没有 Docker | Postgres、Qdrant、Neo4j 不能用容器启动。 | `scripts/services.sh` 以原生方式安装：PGDG apt 源、Qdrant 静态二进制、Neo4j tarball。已在本容器验证。 |
| 会话会断 | 空闲或超时会断开；Pro+ 才有后台执行。 | 每个 run 结束就拷到 Drive；套件可续跑，已完成的 run 自动跳过（已验证）。 |

### GPU 档位与“本地硬件”的对应

| Colab GPU | 显存 / 带宽 | 对应的本地硬件 | 用途 |
|---|---|---|---|
| A100-40G/80G | 40–80 GB / 1.6–2 TB/s | 高端工作站（RTX 4090/5090 的带宽量级） | 主实验 |
| L4 | 24 GB / 300 GB/s | 中端消费卡（RTX 4060 Ti 量级带宽），跑 FP8 | 复核“带宽受限时 decode 更贵” |
| T4 | 16 GB / 320 GB/s，无 BF16 | 仅用于调试 | — |

## 2. 选哪些记忆架构

按架构族各选一个有代表性、能本地自托管的开源实现：

| 系统 | 架构族 | 写路径 | 读路径 | 生产后端 |
|---|---|---|---|---|
| **RAG 基线** | 原始对话轮 + 向量 | embed + INSERT，写入时**不调 LLM** | 向量 kNN | Postgres + pgvector (HNSW) |
| **mem0 2.2.1** | LLM 抽取事实 + 向量/实体/BM25 | 1 次长 prompt（约 8k token）的 LLM 抽取 + 实体链接 | dense + BM25 + 实体加权 | pgvector（mem0 自托管 server 的默认后端），或 Qdrant server |
| **Graphiti 0.31（Zep 开源内核）** | 时序知识图谱 | 每轮多次 LLM 调用：抽实体、消歧、抽边、时序失效，结构化输出 | 向量 + 全文 BM25 + RRF | Neo4j 5.26 |
| **Letta 0.16.8（MemGPT 系）** | agent 自管理记忆 | LLM 用工具调用改写 in-context 记忆块、检索历史 | 同一次 agent 调用内完成 | Postgres + pgvector |

这四类覆盖了“写入时不调 LLM / 单次抽取 / 多步图构建 / agent 自管理”四种写路径形态。如果需要，后续可加 A-Mem（ChromaDB）或 Cognee。

### 统一的生产化配置

- **推理**：vLLM 0.34，开启以下特性：
  - prefix caching、工具调用（hermes）、`--enable-prompt-tokens-details`；
  - `--enable-per-request-metrics`：每个请求的排队时间、TTFT、生成时间。
- **模型**：
  - 主模型 Qwen3-8B（关闭 thinking），L4 上用 FP8；
  - embedding 用 Qwen3-Embedding-0.6B（1024 维），在同一张 GPU 上单独起一个 vLLM 进程，模拟单机部署。
- **模型名透传**：各系统保持默认的 OpenAI 模型名（如 gpt-4.1-mini、text-embedding-3-small），由代理改写成本地模型。系统本身的代码和默认参数**一律不改**。
- **负载**：
  - LoCoMo 对话重放，每系统 100 轮 + 50 题 QA；
  - agent 回答最多 256 token，检索 top-10，短期窗口 6 条消息。

## 3. 测量方法（与系统无关）

| 层 | 怎么测 | 得到什么 |
|---|---|---|
| LLM / embedding | `memprof/llm_proxy.py`：所有系统都经过这个 OpenAI 兼容代理。非流式请求在上游改成流式再重组。 | 每次调用的排队、prefill、decode 时间，token 数和缓存命中 token。进程内的库（mem0、Graphiti）和独立服务（Letta）用同一把尺子。 |
| 数据库客户端 | `memprof/dbwrap.py`：包装 psycopg、neo4j、qdrant 的驱动调用，记录扁平区间。 | 客户端侧的 DB 时间，可正确处理异步和并发。 |
| 数据库服务端 | 每个操作前后各取一次 `pg_stat_statements` 快照。 | 语句数、执行时间、缓冲命中、WAL 字节（Letta 的 DB 开销只能这样看到）。 |
| 系统内部阶段 | mem0：NLP、实体加权、历史库；Graphiti：extract_nodes、resolve、extract_edges 等阶段。 | 写路径的阶段分解。 |
| 硬件 | `memprof/hwmon.py`，每 250 ms 采样一次。 | GPU 利用率、显存带宽利用率、功耗；vLLM 的 KV 占用、前缀缓存命中、抢占；各服务进程的 CPU 和 RSS；磁盘写入。 |
| 归因 | `analysis/multi_breakdown.py`：对每个操作的时间窗做扫描线互斥归因，优先级为 decode > prefill > queue > embedding > DB > NLP > 其他。 | 并发调用不会重复计时，各系统的结果可以直接横向比较。 |

全部计时用 CLOCK_MONOTONIC，跨进程可以直接对齐。

## 4. 实验矩阵（`scripts/run_gpu_suite.sh`）

| 套件 | 内容 | 回答的问题 |
|---|---|---|
| smoke | 每个系统跑 3 轮 | 环境是否正常 |
| **e1** | 每个系统同步写，100 轮 + 50 题 QA | 写路径是否在各架构里都占主导？各架构的 LLM 调用数、前缀长度、缓存命中率、DB 和框架开销分别是多少？ |
| **e2** | 异步写（无思考时间 / 5 s 思考时间），测 RAG、mem0、Graphiti | 单 GPU 上后台写对前台 TTFT 和 decode 的干扰有多大？积压和提交延迟是多少？vLLM 的排队时间直接给出答案。 |
| **e3** | 关闭前缀缓存（mem0、Graphiti、Letta）；显存 KV 预算扫描 1G、2G、4G，各自对比开/不开主机内存 KV 卸载（异步写下） | KV 放置对不同架构的影响：mem0 靠长静态前缀，Graphiti 是多个中等 prompt，Letta 是不断增长的上下文。DRAM 这一层能挽回多少？ |
| e4 | Qwen3-4B / Qwen3-14B | 结论是否随模型规模保持 |
| e5（下一步） | 存储规模扫描到 10⁵ 条，用 Colab 高内存 CPU 运行时 | 生产后端（HNSW、Neo4j）是否还会出现 mem0 嵌入式 Qdrant 那种线性退化 |

## 5. 本地冒烟结果（CPU + Qwen2.5-3B，只用来验证管线）

5 个系统都已经端到端跑通。下面的数字只用于说明定性差异，绝对值没有意义。

| 系统 | 每次写入的 LLM 调用 | 抽取 prompt 的前缀缓存命中 | 其他 |
|---|---|---|---|
| mem0 | 1 次，约 8.2k token | 97% | — |
| Graphiti | 约 5.5 次 | 约 19% | 阶段分解：extract_nodes ≈ extract_edges > resolve_nodes > resolve_edges |
| Letta | 每轮约 1–3 次（含工具调用） | 98% | 每轮约 170 条 Postgres 语句；harness 能看到约 0.5 s 不属于 LLM 的服务端框架时间 |
| RAG | 0 | — | 写入 0.14 s，全是 embedding |

由此可以预期，**“写路径以 LLM 为主”在 LLM 驱动的架构里很可能是共性**，但瓶颈的形态不同：
- mem0 是长静态前缀 + 长 JSON 输出；
- Graphiti 是多次调用串行依赖、缓存命中低；
- Letta 是上下文不断增长，外加框架和 DB 开销。

这需要 e1–e3 在 GPU 上证实。

## 6. 结果如何回到这里

notebook 最后一格会把 `memprof_<GPU>.tgz` 存到 Drive。之后任选一种方式：
- 把 tgz 上传给我；
- 用 GitHub token 推到单独的 `results/<gpu>` 分支，我来拉取分析。
