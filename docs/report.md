# mem0 本地 Agent 全链路延迟剖析（Profiling Report v1）

> 目的：在**全本地**（无云 API）环境下，跑一个带长期记忆的对话 agent（mem0 + 本地 LLM），
> 对每一层、每一步记录时延 / CPU / I/O，搞清楚时间到底花在哪、和硬件资源是什么关系，
> 为后续“硬件感知的 agent memory 系统”找切入点。新颖性调研见 [`related_work.md`](related_work.md)。

## 0. TL;DR

1. **写路径（`mem0.add`）是绝对瓶颈**：稳态每轮 44.6 s 中 `add` 占 41.4 s（93%）；读路径（检索）只要 **40 ms**，回答生成 3.2 s。
2. `add` 的时间 **>99.7% 在 LLM 抽取调用里**；embedding、spaCy、向量库、SQLite 加起来约 **100 ms**。
3. 抽取调用的根源是 **mem0 2.2.1 的抽取 system prompt 约 8k token（33.6 KB），而且每次 `add` 都要带上**：
   - 不开 prefix cache：每次 add 的 prefill 是 **59.9 s**（8356 token，140 tok/s）；
   - 开 prefix cache（命中 91.5%）：prefill 降到 **8.7 s**（6.9×），但剩下约 740 个新 token 要对 8k 的缓存做 attention，只能跑 **85 tok/s**（短上下文是 250 tok/s）；
   - decode 在 8k 上下文下只有 **11.6 tok/s**（短上下文是 22.6 tok/s），而 mem0 要求输出“15–80 词/条”的 JSON，平均 **376 个输出 token** → **decode 32.5 s 成为最大单项**。
4. **这段静态前缀的 KV 约 230 MB/份**（Qwen2.5-1.5B，F16 KV）。llama-server 默认会把空闲 slot 的 KV 存到主机内存（`--cache-ram 8192`），所以单 slot 时依然能命中——**现成推理引擎里已经有一层“KV 在 slot↔DRAM 之间分层”**，记忆系统完全没有意识到并利用它。
5. **把写路径异步化在单机上不是免费的**：后台 `add` 和前台回答抢同一份算力，前台回答 **3.2 s → 10.4 s（p50 6.0 s，最长 55 s）**，decode 22.2 → 4.2 tok/s；同时写队列线性堆积，记忆从说出到可检索的**提交延迟中位数 114 s、最长 319 s**（新鲜度问题）。
6. **存储引擎层面**（mem0 默认本地栈 = Qdrant embedded + SQLite）：Python 逐点 payload 过滤、numpy 暴力扫描、每个点 pickle 一次写入 SQLite、冷启动全量反序列化进 DRAM；每次 `add` 块设备写入约 **300 KB**，而新增记忆文本只有几百字节（**写放大约 1000×**）。规模上去之后的退化见第 5 节。
7. 结论：在本地场景里，**“记忆系统 ↔ 推理引擎（KV）↔ 存储层次”之间缺少协同**，这正是可以做系统/硬件优化的地方（第 6 节）。

## 1. 实验环境

| 项 | 配置 |
|---|---|
| 硬件 | 云容器：Intel Xeon @ 2.1GHz **4 vCPU**，15 GB DRAM，virtio 磁盘，**无 GPU** |
| LLM | Qwen2.5-1.5B-Instruct **Q4_K_M** (GGUF)，llama.cpp `llama-server`（本地源码编译，`GGML_NATIVE`），OpenAI 兼容接口 |
| LLM 基准 | `llama-bench`：pp512 252 tok/s，pp2048 221 tok/s，pp8192 136 tok/s，tg64 22.7 tok/s |
| 记忆系统 | **mem0ai 2.2.1**（OSS），telemetry 关闭 |
| Embedding | fastembed（ONNX Runtime，CPU）`BAAI/bge-small-en-v1.5`，384 维 |
| 向量库 | Qdrant **embedded/local 模式**（mem0 默认），`on_disk=True`，BM25 稀疏向量（fastembed `Qdrant/bm25`） |
| NLP | spaCy `en_core_web_sm`（BM25 词形还原 + 实体抽取） |
| 历史库 | SQLite（mem0 `history.db`） |
| 负载 | **LoCoMo** conversation 0：把 Caroline 的发言当作用户消息逐轮重放；每轮 = 检索 top-5 → 构造 prompt（记忆 + 最近 6 条消息）→ 本地 LLM 回答（≤128 token）→ `mem0.add([user, answer])`；之后 20 个 LoCoMo 问题只走读路径 |

> 局限：CPU-only + 1.5B 小模型，绝对数字不能外推到 GPU；但**结构性结论**（哪些阶段占比、哪些行为随上下文长度/并发/规模变化）是可迁移的，第 7 节列出了在 GPU 上复现的计划。

## 2. 方法：怎么打点

全部是**非侵入式 monkeypatch**（不改 mem0 源码），见 `memprof/instrument.py`。每个 span 记录：wall time、进程 CPU time（含 ONNX/numpy 线程）、syscall 级 I/O（rchar/wchar）、块设备 I/O（read/write_bytes）、缺页次数，以及自定义属性。分析时用“自身时间 = 总时间 − 同线程子 span”得到**互斥的分层时间**（`analysis/analyze.py`）。

| 层 | span | 说明 |
|---|---|---|
| Agent | `agent.turn / retrieve / build_ctx / generate / memorize` | 用户视角 |
| mem0 API | `mem0.add / search`、`mem0.add.pipeline`、`mem0.entity_boost` 等 | 包括 prompt 构造、JSON 解析、打分 |
| LLM | `llm.mem0_extract / llm.agent_answer` | 附带 llama.cpp 服务端 `timings`：prompt_n、**cache_n**（KV 复用的 token）、prefill ms、decode n/ms；“LLM other” = wall − prefill − decode（HTTP/排队/tokenize/采样） |
| Embedding | `embed.*` → `fastembed.dense` | mem0 包装层 vs ONNX 推理 |
| NLP | `nlp.lemmatize / ner / ner_batch`、`fastembed.bm25` | |
| 向量库 | `vs.* / ent.*`（mem0 封装）→ `qdrant.*`（client）→ `qlocal.scan / distance / filter_mask / upsert / persist_sqlite`（引擎内部） | 区分距离计算、payload 过滤、持久化 |
| 历史库 | `db.get_last_messages / save_messages / batch_add_history` | |

打点开销：**约 23 µs/span**，主实验平均每轮约 100 个 span（约 2.3 ms），相对 44 s 的单轮可以忽略。

## 3. mem0 2.2.1 的调用路径（每一步碰什么硬件）

**写路径 `add()`（V3 phased batch pipeline）**

| 阶段 | 做什么 | 主要资源 |
|---|---|---|
| P0 | SQLite 取本 session 最近 10 条消息 | 存储 I/O（小） |
| P1 | 对新消息做 embedding → 向量检索 top-10 已有记忆 | CPU matmul + 向量扫描 |
| P2 | **1 次 LLM 调用**：约 8k token 的 system prompt + 已有记忆 + 最近消息 + 新消息 → JSON 记忆列表 | **prefill（算力）+ decode（带宽）**，绝对大头 |
| P3 | 对抽取出的每条记忆做 embedding（名义上 batch，**fastembed 实现里实际逐条**） | CPU |
| P4/5 | MD5 去重、spaCy 词形还原（BM25 用） | CPU（Python） |
| P6 | 写向量库（含 BM25 稀疏向量编码）→ 每个点 pickle → SQLite `INSERT OR REPLACE`；写 history | 序列化 + 存储 I/O |
| P7 | spaCy NER → 实体 embedding → 实体库按文本全扫 + 向量 top-1 → 插入/更新实体（`linked_memory_ids`） | CPU + 存储 |
| P8 | 保存原始消息到 SQLite | 存储 I/O |

**读路径 `search()`**：spaCy 词形还原 + NER → query embedding → 稠密检索（over-fetch `max(4k, 60)`）→ BM25 稀疏检索 → 实体加权（每个实体 embedding + 实体库 top-500，4 线程线程池）→ 融合打分排序。

## 4. 端到端结果

![breakdown](fig/e2e_breakdown.png)

### 4.1 主实验：prefix cache 开，2 个 slot（`results/e2e_cache_np2`，40 轮 + 20 QA，最终 72 条记忆）

| 操作（稳态，turn ≥ 1） | n | mean | p50 | p95 | LLM prefill | LLM decode | LLM other | 非 LLM 合计 |
|---|---|---|---|---|---|---|---|---|
| 整轮 `agent.turn` | 39 | **44.6 s** | 44.1 s | 71.9 s | 10.2 s | 34.1 s | 0.22 s | 0.14 s |
| 检索 `retrieve`（对话中） | 39 | **40 ms** | 36 ms | 65 ms | – | – | – | 40 ms |
| 检索 `retrieve`（QA） | 20 | 29 ms | 28 ms | 38 ms | – | – | – | 29 ms |
| 回答 `generate`（对话中） | 39 | 3.22 s | 3.12 s | 4.70 s | 1.47 s | 1.57 s | 0.18 s | – |
| 写记忆 `memorize = mem0.add` | 39 | **41.4 s** | 41.5 s | 67.3 s | 8.74 s | **32.5 s** | 0.04 s | **0.10 s** |

非 LLM 部分的细分（ms，均值）：

| 操作 | Embedding ONNX | spaCy | BM25 编码 | 向量距离 | payload 过滤 | pickle+SQLite 持久化 | 向量库胶水 | history SQLite | mem0 胶水 |
|---|---|---|---|---|---|---|---|---|---|
| retrieve(chat) | 15.2 | 13.0 | 0.2 | 0.1 | 1.1 | 0 | 8.7 | 0 | 1.0 |
| memorize（非 LLM） | 71.7 | 11.8 | 0.2 | 0.3 | 0.9 | 6.2 | 4.3 | 2.2 | 1.7 |

LLM 调用统计：

| 调用 | n | prompt tok | 命中缓存 tok | 实算 tok | prefill | prefill 速率 | 输出 tok | decode | decode 速率 |
|---|---|---|---|---|---|---|---|---|---|
| agent 回答 | 59 | 336 | 52 | 284 | 1.15 s | 247 tok/s | 33 | 1.45 s | 22.6 tok/s |
| **mem0 抽取** | 39 | **8691** | **7952** | 740 | 8.74 s | **85 tok/s** | **376** | 32.5 s | **11.6 tok/s** |

观察：

- **长静态前缀 = “隐性税”**：即使 KV 全命中，新 token 仍要和 8k 个缓存 token 做 attention，prefill 每 token 成本是短上下文的约 3 倍，decode 每 token 慢约 2 倍。CPU 上 attention 的 KV 读取是带宽受限的；GPU 上也是同样的趋势（decode 读 KV 是带宽受限）。
- **输出长度决定 decode 时间**：mem0 的输出 schema（每条记忆 15–80 词 + id/attributed_to/linked_memory_ids）让每次抽取输出约 376 token。在单机上 decode 是带宽受限的，这是最贵的部分。
- **冷启动**：第一轮 70 s，其中 prefill 59.8 s（8k 前缀没有缓存），spaCy 首次加载约 0.9 s，BM25 编码器首次加载约 0.1 s；`Memory` 初始化 1.5 s。
- **embedding 没有批处理**：mem0 的 fastembed embedder 没有覆写 `embed_batch`，基类实现是逐条循环，所以每轮约 13 次单条 ONNX 推理（与 2606.06448 观察到的“Mem0 embedding 1:1”一致）。
- **I/O 写放大**：每次 `add` 的 syscall 写约 221 KB、块设备写约 300 KB（SQLite journal + 每点 pickle 整体重写），而每次 add 只新增约 1.8 条、每条 100–300 B 的文本。对 SSD 寿命和能耗不友好，规模上去后会更明显。

### 4.2 KV cache 配置对照（`mem0.add` 的抽取调用）

| 配置 | 轮数 | add mean | prompt tok | 命中 tok | prefill | prefill 速率 | 输出 tok | decode 速率 |
|---|---|---|---|---|---|---|---|---|
| `cache_np2`：prefix cache 开，2 slot | 39 | 41.4 s | 8691 | 7952 (91%) | **8.7 s** | 85 tok/s | 376 | 11.6 tok/s |
| `cache_np1`：prefix cache 开，1 slot（默认 `--cache-ram 8192`） | 11 | 34.9 s | 8526 | 7981 (94%) | **6.8 s** | 80 tok/s | 321 | 11.5 tok/s |
| `nocache`：prefix cache 关 | 7 | 71.6 s | 8356 | 0 | **59.9 s** | 140 tok/s | 149 | 12.8 tok/s |
| `cache_np1_noram`：1 slot 且关闭 host-RAM prompt cache | – | 见 4.4 | | | | | | |

- prefix cache 把每次 add 的 prefill **从 59.9 s 降到 6.8–8.7 s**。各配置的输出长度差异来自对话内容不同（LLM 每次抽几条记忆不确定），所以比较 decode 时要看速率，不看总时间。
- 单 slot 时，agent 回答会占用唯一的 slot、把抽取前缀挤掉；但 llama-server 默认把空闲 slot 的 KV 存进 **host RAM 的 prompt cache**，下次再恢复，所以依然命中。单 slot 下抽取调用的“LLM other”多了约 50 ms（36.7 vs 85.8 ms），量级上与恢复一份约 230 MB 的 KV 相符（**这是推断，没有单独打点**）。

### 4.3 异步写路径的干扰（`results/e2e_async_np2`，15 轮，用户思考时间 5 s）

| 指标 | 同步 add（cache_np2） | 异步 add（后台单 worker） |
|---|---|---|
| 用户可见单轮（检索 + 回答） | 3.26 s（但每轮还要等 add 41 s） | **10.5 s** |
| 回答 `generate` mean / p50 / max | 3.2 / 3.1 / 5.5 s | **10.4 / 6.0 / 55.2 s** |
| agent 回答 decode 速率 | 22.2 tok/s | **4.2 tok/s** |
| agent 回答 prefill 速率 | 250 tok/s | 126 tok/s |
| 检索 mean | 40 ms | 78 ms |
| 写队列积压（每轮） | – | 1,2,2,2,3,3,3,3,3,4,5,6,7,7,8（线性增长） |
| 记忆提交延迟（说出 → 可检索） | 0（阻塞） | 中位数 **114 s**，最长 **319 s** |

- 前台与后台的 LLM 请求在同一个 llama-server 里连续批处理，共享 4 个核和内存带宽；后台 8k 上下文的抽取 decode 把前台 decode 拖慢 5 倍以上，某些轮次前台被后台的 prefill 块阻塞到 55 s。
- 写吞吐（约 1 次 add / 41 s）远低于对话速率（约 1 轮 / 10 s），积压无上界增长——**记忆新鲜度**无法保证。
- 意味着：在本地单机上需要**有优先级、能感知硬件（算力/带宽/KV 容量）的记忆写调度**，而不是简单地“扔到后台”。

### 4.4 单 slot + 关闭 host-RAM prompt cache

（实验结果见 4.4 补充，运行中）

## 5. 规模扩展：记忆存储本身随 N 的变化

（运行中，见 `results/scale_*`）

## 6. 从系统 / 硬件角度看到的优化机会

（待规模实验完成后定稿）

## 7. 局限与下一步

（待补充）
