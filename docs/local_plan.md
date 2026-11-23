# 本机实验方案：RTX 4060 (8 GB) + 真实 NVMe

目标与 `docs/gpu_plan.md` 相同：
1. 判断“写路径主导、长静态前缀、KV 放置、后台写干扰、存储随规模退化”这些现象，是不是 agent 记忆系统的**共性问题**；
2. 在**真实的消费级硬件**上找到瓶颈，包括 GPU 显存、PCIe、DRAM 和 SSD 各层。

相对 Colab 方案有三处改动：
- 改在用户自己的机器上跑，SSD 读写、冷启动、页缓存都是真实的；
- 推理引擎从 vLLM 换成 llama.cpp；
- 去掉 Letta。

## 1. 平台

| 项 | 选择 | 原因 |
|---|---|---|
| 操作系统 | Windows + WSL2 Ubuntu 24.04，以 root 运行 | Postgres、Neo4j、Qdrant 和 harness 都是 Linux 栈。Windows 上用 Docker Desktop 跑这些服务，本身也是跑在 WSL2 里，所以这就是 Windows 开发机的真实形态。 |
| 磁盘 | 仓库、模型、数据库都放在 WSL 的 ext4（`/root/...`），**不要放 `/mnt/c`** | ext4.vhdx 直接落在 NVMe 上；`/mnt/c` 走 9P 协议，慢一个数量级，结果不具代表性。 |
| 推理 | llama.cpp `b12559`（本仓库开发和验证所用的同一版本），CUDA 构建，sm_89 | 8 GB 卡上本地 agent 的主流引擎（Ollama、LM Studio 的底层都是它）。它的每一种 KV 放置方式都能直接开关，正好对应我们要测的存储层级（见第 3 节）。 |
| WSL 的局限 | 页缓存分两层：WSL 虚拟机里一层，Windows 宿主对 vhdx 文件可能还有一层 | `preflight` 会实测这一点：写 2 GB 文件，丢掉虚拟机的页缓存，再读回来。如果读速远高于 fio 直读的速度，说明宿主还在缓存，那么“冷”数据只是虚拟机内的冷。要求最严格时，可以改用原生 Linux，或者用 `wsl --mount` 挂一块裸盘。 |

## 2. 记忆系统（去掉 Letta）

| 系统 | 写路径 | 存储 | 为什么要测 |
|---|---|---|---|
| rag-pg | 只做 embed + INSERT，**写入时不调 LLM** | Postgres 16 + pgvector HNSW | 对照组 |
| **mem0-local** | 一次长 prompt 抽取 + 实体链接 | **嵌入式 Qdrant（落盘）+ SQLite** | mem0 开箱即用的本地模式，也是单机 agent 最常见的部署方式；之前在 CPU 上测到的线性退化就出在这里 |
| mem0-pg | 同上 | pgvector（mem0 自托管 server 的默认后端） | 生产级向量库 |
| mem0-qdrant | 同上 | Qdrant server | 生产级向量库 |
| graphiti | 每轮多次 LLM 调用（抽实体、消歧、抽边、时序失效） | Neo4j 5.26 | 时序知识图谱 |

系统代码和默认参数都不改。它们发出的 OpenAI 模型名，由 proxy 改写成本地模型。

## 3. 模型与 KV 放置（8 GB 显存预算）

| 档位 | 模型 | 显存占用 | 用途 |
|---|---|---|---|
| **q4b（主实验）** | Qwen3-4B-Instruct-2507 Q4_K_M（2.3 GB） | + 16k 上下文 f16 KV（2.3 GB）+ embedder 0.6 GB，共约 6.2 GB | 8 GB 卡上“全部放进显存、留有余量”的典型配置 |
| q8b | Qwen3-8B Q4_K_M（4.7 GB，关闭 thinking） | KV 为 q8_0、12k 上下文，共约 7.2 GB | 能塞进 8 GB 的最大稠密模型，显存吃紧 |
| llama8b | Llama-3.1-8B-Instruct Q4_K_M | 同 q8b | 换一个模型家族（KV 形状不同），看结论是否依赖 Qwen |
| moe30b | Qwen3-30B-A3B-Instruct-2507 Q4_K_M（17.3 GB） | 专家权重全部放主机内存（`--n-cpu-moe`），注意力和 KV 放 GPU | 8 GB 卡跑大 MoE 的常见做法。解码受 DRAM 和 PCIe 限制，需要 ≥ 32 GB 内存 |

所有档位的 embedding 都用 Qwen3-Embedding-0.6B Q8_0（1024 维），和 LLM 共用同一张 GPU。

LLM 服务的公共参数：
- `-np 2 --kv-unified`：前台 agent 和后台记忆写入并发，共享一个 KV 池；
- `--cache-ram 8192`：llama.cpp 默认开启的主机内存 prompt 缓存；
- `--slot-save-path`：把 KV 状态存到 SSD 和从 SSD 恢复；
- `--metrics -fa on --fit off`：关掉自动适配，避免显存不够时悄悄把层挪到 CPU。实际有多少层、多少 KV 放进了显存，每次都记录在 `llm.load.json` 里。

KV 存储层级与开关：

| 层 | 开关 |
|---|---|
| GPU 显存 | 默认 |
| 量化 KV | `KV=q8_0` |
| 主机内存 prompt 缓存 | `CACHE_RAM`，设为 0 即关闭 |
| KV 整体放主机内存，注意力在 CPU 上算 | `NO_KV_OFFLOAD=1` |
| SSD | slot 文件的 save/restore |
| 完全不复用（重算） | `CACHE_PROMPT=0` |

## 4. 测量（在原有基础上新增）

| 层 | 新增内容 |
|---|---|
| 存储 I/O（`memprof/iostat.py`） | 每个操作前后，记录各后端进程实际落到块设备的读写字节（`/proc/<pid>/io`）。另外记录数据盘 `/proc/diskstats` 的读写次数、耗时，以及 flush 次数和耗时（即 fsync 落盘）；IO 压力用 PSI。 |
| Postgres | `pg_stat_io` 的 reads、writes、fsyncs 及各自耗时；`pg_stat_wal` 的 wal_sync 次数和耗时（已开启 `track_wal_io_timing`）。 |
| llama.cpp | `/metrics` 提供 prompt 缓存命中的 token 数、prefill 和 decode 吞吐、排队请求数；每次请求的 timings（prompt_ms、cache_n）。排队时间按 TTFT − prompt_ms 估计。 |
| GPU | 在原有指标外加 PCIe TX/RX 吞吐（KV 卸载和 MoE 放 CPU 时的流量）。 |
| 启动 | 模型加载耗时、各设备上的 buffer 大小、加载期间读盘的字节数。 |

## 5. 实验（`scripts/local/run_local_suite.sh`，可续跑）

| 套件 | 内容 | 回答的问题 | 估时 |
|---|---|---|---|
| preflight | 硬件清单；fio 基线：顺序读、4k 随机读 QD1、4k 写且每次 fsync；页缓存检查 | 这块盘的读延迟和 fsync 延迟分别是多少？“冷”数据是否可信？ | 3 min |
| smoke | 每个系统跑 3 轮 | 环境是否正常 | 10 min |
| **kv** | 前缀长度 1k–12k，比较重算、GPU 命中、内存缓存、SSD 冷读、SSD 热读（开 / 关 `--cache-ram` 各一次） | 在这台机器上，从各层取回 KV 比重算快多少？SSD 在哪个长度开始划算？ | 10 min |
| load | 模型冷加载（丢掉页缓存）对比热加载，mmap 对比 read | 冷启动有多少是 SSD 的代价？ | 5 min |
| **l1** | 5 个系统同步写，100 轮 + 50 题 QA | 写路径在各架构里是否都占主导？每轮的 LLM、DB、磁盘写和 fsync 开销各是多少？ | 2–4 h |
| **l2** | 异步写（think 时间 0 s / 5 s），测 rag、mem0-local、mem0-pg、graphiti | 2 个 slot 共享一张 8 GB 卡时，后台写对前台 TTFT 和 decode 的干扰有多大？积压和提交延迟是多少？ | 2 h |
| **l3** | mem0-pg 和 graphiti 在异步写下跑 6 种 KV 配置：基线、关前缀缓存、关内存缓存、KV q8_0、KV 放主机内存、上下文 8k | 不同架构对 KV 放置的敏感度：mem0 是长静态前缀，Graphiti 是多个中等长度的 prompt | 3 h |
| l4 | q8b、llama8b、moe30b，测 mem0-pg 和 graphiti，并对每个模型跑一遍 kv 微基准 | 结论是否随模型规模、模型家族、MoE 放 CPU 而保持？ | 2–3 h |
| **l5** | 存储规模 10³–10⁵ 条，热页缓存对比冷页缓存（重启服务并丢掉页缓存），测 rag-pg、mem0-pg、mem0-qdrant、mem0-local | 生产后端会不会出现嵌入式 Qdrant 那种线性退化？冷查询要读多少字节 SSD？重新打开存储要多久？ | 1–2 h |

全套约 12–15 小时，可以分几个晚上跑。

磁盘空间：
- 模型约 30 GB（含 moe30b）；
- CUDA toolkit 约 5 GB；
- 数据和结果约 10 GB。

## 6. 怎么跑（等你说“跑”的时候我来执行）

你需要先准备好：
1. Windows NVIDIA 驱动，以及 WSL2（`memprof.ps1 check` 和 `install-wsl` 可以检查并安装）。如果想跑 moe30b，在 `.wslconfig` 里把 `memory=` 调到内存的 75% 左右。
2. 在 Claude 桌面端的 Settings → Claude Code → Remote Control 里，共享本仓库在 Windows 上的目录。这样我就能在会话里连接你的电脑，连接时你需要确认一次。

之后我会按下面的顺序执行，全部通过 PowerShell 7（`C:\Users\ianha\Documents\Codex\Tools\PowerShell\7.6.5\pwsh.exe`）：

```
pwsh -File scripts\win\memprof.ps1 check
pwsh -File scripts\win\memprof.ps1 clone
pwsh -File scripts\win\memprof.ps1 setup
pwsh -File scripts\win\memprof.ps1 suite preflight smoke kv load
pwsh -File scripts\win\memprof.ps1 suite l1 l2 l3 l4 l5
pwsh -File scripts\win\memprof.ps1 status
```

- `clone`：把仓库克隆进 WSL 的 `/root/Agent_Mem_Sys`。
- `setup`：安装 CUDA toolkit、编译 llama.cpp、安装服务、下载模型，约 30 分钟。
- 第一次 `suite`：先确认环境和硬件基线。
- 第二次 `suite`：长时间实验，在后台运行。
- `status`：随时查看进度。

结果写在 WSL 的 `results/local/<主机名>/` 下，跑完由我提交到分支并分析。

## 7. 本容器 CPU 冒烟结果（只验证管线；原始数据在 `results/local/cpu_smoke/`）

测试环境为 CPU 加 Qwen2.5-1.5B Q4，数字只能说明定性趋势。

- **全部套件跑通**：preflight、load、kv、smoke（4 个系统）、l5（rag-pg 和 mem0-local，每个 2 个规模点），均可续跑。
- **kv 微基准**，前缀 1k token：

  | 方式 | 耗时 |
  |---|---|
  | 重算 | 3.8 s |
  | KV 仍在 | 52 ms |
  | 主机内存缓存 | 79 ms |
  | SSD 冷恢复（28 MB 文件） | 72 ms |

  关掉 `--cache-ram` 后，“内存缓存”这一项退化成重算（3.6 s），但 SSD 恢复仍然有效。三个层级都能被准确开关和测到。
- **KV 池容量决定 mem0 的写路径成本，这是已经看到的第一个硬件现象**：

  | 统一 KV 池 | mem0 抽取 prompt 的缓存命中 | 每次 memorize |
  |---|---|---|
  | 8k（mem0 约 8.1k 前缀 + agent 对话放不下） | 0% | 60 s |
  | 16k | 98% | 12.5 s |

  前台 agent 的请求会把 mem0 的长前缀挤出显存。llama.cpp 的主机内存 prompt 缓存也没能把它救回来。l3 的 ctx8k / noram 两组实验会在 4060 上把这一点量化。
- **磁盘写入**：每次 memorize 的块设备写入量和 flush 次数（即 fsync）都能按操作拆分出来：

  | 系统 | flush 次数 / 每次 memorize |
  |---|---|
  | RAG | 1 |
  | mem0-local | 约 13 |
  | mem0-pg | 约 15 |
  | Graphiti | 约 10 |

  其中 Graphiti 的写主要由 Neo4j 产生。
