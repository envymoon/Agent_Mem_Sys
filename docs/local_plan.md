# 本机实验方案：RTX 4060 (8 GB) + 真实 NVMe

目标与 `docs/gpu_plan.md` 相同：
1. 判断“写路径主导、长静态前缀、KV 放置、后台写干扰、存储随规模退化”这些现象，是不是 agent 记忆系统的**共性问题**；
2. 在**真实的消费级硬件**上找到瓶颈，包括 GPU 显存、PCIe、DRAM 和 SSD 各层。

相对 Colab 方案有三处改动：
- 改在用户自己的机器上跑，SSD 读写、冷启动、页缓存都是真实的；
- 推理引擎从 vLLM 换成 llama.cpp；
- 去掉 Letta。

## 0. 论证结构：为什么主实验放在本机

结论的性质是“瓶颈在哪里”：fsync、KV 被挤出、冷加载读盘、后台写干扰。这些只有在能控制、能复现的真实硬件上测出来才站得住。云 GPU 的磁盘是虚拟化的网络盘，旁边还有别的租户，往往也清不掉页缓存，测到的存储行为说明不了记忆系统本身。所以整个实验分三层：

| 层 | 在哪跑 | 回答什么 | 对应 |
|---|---|---|---|
| ① 真实测量 | 本机 RTX 4060 + NVMe（WSL2），4 档模型 | 每个操作的 LLM / 嵌入 / DB / fsync / 读写字节分解，以及它们之间的相互作用（KV 池容量 → 前缀被挤出 → 重新 prefill） | l1–l5 |
| ② 平台复测 | 同一台机器，原生 Ubuntu（U 盘或双系统） | 存储相关的结论是不是 WSL2 虚拟磁盘（NTFS 上的 VHDX + Hyper-V 存储栈）带来的假象 | 第 9 节 |
| ③ 延迟模型 + 大显卡验证点 | 本机的 trace + 任意 Linux GPU（Colab/云）上的 llama-bench | 换成更快的 GPU 或更慢/更快的盘，瓶颈怎么转移。云上只测 LLM 速率，不对存储下结论 | 第 8、10 节 |

和模型有关的部分（prefill / decode）随 GPU 和模型变化；和系统有关的部分（存储、fsync、索引、KV 能否复用）基本不随模型变化。第①层把两部分在真实硬件上测准，第③层用简单模型把它们拼起来做外推，第②层排除平台本身的干扰。

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
| rates | llama-bench：pp512 和 tg64，KV 深度 0 到上下文上限，与服务端相同的模型、KV 类型和卸载参数 | 延迟模型用的每 token prefill / decode 成本（l4 对每档模型自动跑一遍） | 5 min |
| **l1** | 5 个系统同步写，100 轮 + 50 题 QA | 写路径在各架构里是否都占主导？每轮的 LLM、DB、磁盘写和 fsync 开销各是多少？ | 2–4 h |
| **l2** | 异步写（think 时间 0 s / 5 s），测 rag、mem0-local、mem0-pg、graphiti | 2 个 slot 共享一张 8 GB 卡时，后台写对前台 TTFT 和 decode 的干扰有多大？积压和提交延迟是多少？ | 2 h |
| **l3** | mem0-pg 和 graphiti 在异步写下跑 6 种 KV 配置：基线、关前缀缓存、关内存缓存、KV q8_0、KV 放主机内存、上下文 8k | 不同架构对 KV 放置的敏感度：mem0 是长静态前缀，Graphiti 是多个中等长度的 prompt | 3 h |
| l4 | q8b、llama8b、moe30b，测 mem0-pg 和 graphiti，并对每个模型跑一遍 kv 微基准 | 结论是否随模型规模、模型家族、MoE 放 CPU 而保持？ | 2–3 h |
| **l5** | 存储规模 10³–10⁵ 条，热页缓存对比冷页缓存（重启服务并丢掉页缓存），测 rag-pg、mem0-pg、mem0-qdrant、mem0-local | 生产后端会不会出现嵌入式 Qdrant 那种线性退化？冷查询要读多少字节 SSD？重新打开存储要多久？ | 1–2 h |

| model | 对 l1 / l4 的每个 run 跑 `analysis/latency_model.py`，输出 `latency_model_<档位>.md` | 模型在本机上的预测误差；换 GPU / 换盘 / 不复用 KV 的推算 | 1 min |

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
pwsh -File scripts\win\memprof.ps1 suite preflight smoke kv load rates
pwsh -File scripts\win\memprof.ps1 suite l1 l2 l3 l4 l5 model
pwsh -File scripts\win\memprof.ps1 status
```

- `clone`：把仓库克隆进 WSL 的 `/root/Agent_Mem_Sys`。
- `setup`：安装 CUDA toolkit、编译 llama.cpp、安装服务、下载模型，约 30 分钟。
- 第一次 `suite`：先确认环境和硬件基线。
- 第二次 `suite`：长时间实验，在后台运行。
- `status`：随时查看进度。

结果写在 WSL 的 `results/local/<主机名>-wsl/` 下（原生 Linux 上是 `-native`），跑完由我提交到分支并分析。

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

- **延迟模型在 CPU 上的自检**（`results/local/cpu_smoke/latency_model_cpu.md`）：用 llama-bench 测出的速率乘以 trace 里的 token 数，预测每个操作的耗时，没有用 trace 的耗时做拟合。

  | run | 操作 | 实测 | 预测 | 误差 |
  |---|---|---|---|---|
  | mem0-pg（8k 池） | memorize | 59.8 s | 58.6 s | −2% |
  | mem0-local（8k 池） | memorize | 61.4 s | 60.1 s | −2% |
  | mem0-pg（16k 池） | memorize | 12.5 s | 14.6 s | +17% |
  | Graphiti | memorize（9 次 LLM 调用） | 80.6 s | 66.3 s | −18% |
  | 各系统 | generate | — | — | −6% ~ +15% |

  另外，16k 池那组 run 用“不复用 KV”推算得到 65 s，和 8k 池实测的 60 s（命中率 0%）一致，说明模型抓住了 KV 复用这个主因。flush 次数 × fio 测得的单次 4k 写+fsync 延迟，与 diskstats 记录的 flush 耗时在同一量级（1.8–2.7 ms 对 2.5–3.5 ms）。

## 8. 延迟模型（`analysis/latency_model.py`）

把一次操作的耗时拆成和模型有关、和系统有关的两部分：

```
T_op ≈ T_LLM + T_emb + T_DB + T_NLP + T_other
T_LLM = Σ_调用 [ prefill(p | 已缓存 c) + decode(g | 深度 c+p) + h ] / κ
T_DB 中的存储部分 ≈ n_flush × t_commit
```

| 量 | 从哪来 |
|---|---|
| p、c、g：每次调用实际 prefill、复用和生成的 token 数 | trace（llama.cpp 每次请求返回的 timings） |
| 每 token 的 prefill / decode 成本，随 KV 深度变化 | `rates` 套件的 llama-bench，**不是**从 trace 拟合，所以在本机上是预测而不是拟合 |
| h：每次请求在 GPU 之外的开销（HTTP、proxy、采样） | trace 的中位数 |
| κ：调用并发度（Graphiti 会并行发请求）= 调用耗时之和 ÷ 调用区间的并集 | 本机 trace，视为系统结构性质 |
| n_flush：每次操作的块设备 flush 次数 | `/proc/diskstats` |
| t_commit：4k 写 + fsync 延迟 | 同一块盘的 fio |
| T_emb、T_NLP、T_other | 实测，推算时保持不变 |

用法有三种：
1. **本机验证**：预测值对比实测值，按系统、按操作给出误差。
2. **推算**：同样的 token 数和 flush 数，换上别的 GPU 的 llama-bench 结果（`--gpu`）或别的盘的 fio 结果（`--disk`），看 LLM 和存储的占比怎么变；另外自动给出“完全不复用 KV”的推算，可以和 l3 的 noprefix 实测对照。
3. **交叉验证**：如果那块 GPU 也跑了同名的 run（`--check`），直接比较它实测的 LLM 部分和从本机 trace 推出来的预测。

不建模的部分：前台和后台请求的争用。这部分由 l2/l3 直接测量，不靠模型。

## 9. 原生 Linux 复测（排除 WSL2 的影响）

WSL2 是一台 Hyper-V 虚拟机，Linux 的 ext4 放在 Windows NTFS 上的 VHDX 文件里。fsync 会传到物理盘，但中间多了一层虚拟化，Windows 那边可能还有缓存。preflight 的页缓存检查可以量化这一点，但最有说服力的办法是在同一台机器上用原生 Ubuntu 再跑一遍关键实验：

```bash
# 从 U 盘启动 Ubuntu 24.04（或双系统），装好 NVIDIA 驱动后：
git clone -b claude/gifted-maxwell-td8cnz https://github.com/envymoon/Agent_Mem_Sys.git && cd Agent_Mem_Sys
sudo -E DL_PROFILES=q4b scripts/local/setup.sh
sudo -E SYSTEMS="mem0-local mem0-pg graphiti" scripts/local/run_local_suite.sh preflight kv load rates l1 l5 model
python analysis/platform_compare.py results/local/<主机名>-wsl results/local/<主机名>-native
```

- 选择 U 盘 live 系统时，数据要放在内部 NVMe 上的分区，不能放 U 盘，否则测到的是 U 盘。
- 约 5–6 小时（l1 只跑 3 个系统，l5 全跑）。
- `platform_compare.py` 对每个指标给出 native / WSL 的比值。预期：LLM 相关的行接近 1；如果存储相关的行（fsync 延迟、冷查询、冷加载）明显偏离 1，就说明这部分要以原生结果为准，并在论文里报告这个差异。

## 10. 大显卡验证点（可选，只验证 LLM 部分）

在 Colab（A100 / L4）或任意云 GPU 上，同一个 llama.cpp 版本、同一个 GGUF：

```bash
sudo -E DL_PROFILES=q4b scripts/local/setup.sh          # CUDA 架构会自动识别
OUT=results/cloud/a100 scripts/local/run_local_suite.sh rates
OUT=results/cloud/a100 SYSTEMS="mem0-pg graphiti" TURNS=30 QA=0 scripts/local/run_local_suite.sh l1   # 交叉验证用，可选
```

回到本机的结果上：

```bash
python analysis/latency_model.py --runs results/local/<主机名>-wsl/l1_q4b_*_sync \
  --rates results/local/<主机名>-wsl/rates_q4b/llama_bench.json --fio results/local/<主机名>-wsl/preflight/fio_fsyncwrite.json \
  --gpu A100=results/cloud/a100/rates_q4b/llama_bench.json --check A100=results/cloud/a100
```

- 云上的 run 只用它的 LLM 部分（prefill、decode、调用次数）。存储数字一律不用，论文里也要这样写明。
- 想推算更大的模型（例如 Qwen3-32B）在大显卡上的情况：在云上用那个模型跑 `rates`，token 数沿用本机同一 tokenizer 家族（Qwen3）的 trace。抽取输出的长度会随模型变化，所以这一项只能标为推算。
