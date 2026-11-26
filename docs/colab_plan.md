# Colab 实验方案：第一层（标准 benchmark），L4 24 GB

当前主线。本机 4060 方案（`docs/local_plan.md`）保留为备选，两边用同一套脚本，只是平台和模型档位不同。

## 1. 平台定位

Colab 运行时是一台云 GPU 虚拟机。进程看到的内存、磁盘和 `/proc` 计数器都是真实的，所以每个操作的读写字节、flush（fsync）次数和延迟、Postgres 落盘统计都能照常测。不同的是被测平台：

- 磁盘是云盘，第一个 preflight 会用 fio 测出它的顺序读、4k 随机读和 4k 写 + fsync 延迟；
- 结论写成“在云 GPU 虚拟机 + 云块存储上部署的记忆系统”，不写成本地 NVMe；
- 如果需要本地部署的数字，用延迟模型的换盘推算（`analysis/latency_model.py --disk`），并标为推算。

| 风险 | 对策 |
|---|---|
| 容器里 `/proc/sys/vm/drop_caches` 可能不可写 | 自动退回 `posix_fadvise(DONTNEED)`，按文件把数据库、模型、KV slot 文件的页缓存逐出（不需要特权）。在本容器里验证过：逐出后再读同一文件，块设备层实际读了 264 MB，热读是 0。preflight 会记录用了哪种方法以及冷读到底读了多少盘（`cache_check.json` 的 `method`、`cold_dev_read_mb`）。限制：被运行中进程 mmap 的页（Qdrant 段文件）逐不掉。 |
| 每次分到的虚拟机和磁盘可能不同 | preflight 按开机 ID 分目录（`preflight_<boot>`），每个 run 记录自己所在的虚拟机（`vm.txt`）。只在同一虚拟机内部做对照。 |
| 不同虚拟机、邻居负载带来的波动 | notebook 第 7 格在另一个运行时用 `REP=2` 重复关键 run，报告波动。 |
| 运行时断开、有时长上限 | 套件可续跑；每跑完一个 run 就把结果镜像到 Google Drive（`SYNC_DIR`），新运行时启动时先从 Drive 恢复，已完成的跳过。 |

## 2. 模型（L4 24 GB）

| 档位 | 模型 | 文件 | 显存 | 用途 |
|---|---|---|---|---|
| **gptoss20b（主）** | gpt-oss-20b，MXFP4（MoE，总参数 21B，每 token 激活约 3.6B） | ggml-org/gpt-oss-20b-GGUF，12.1 GB | 权重 12.1 GB + 32k 上下文 KV 约 0.8 GB（一半层是 128 token 滑动窗口）+ embedding 0.6 GB | 主流开源 agent 模型；推理 token 会拉长写入耗时，这本身就是真实现象 |
| q14b | Qwen3-14B Q4_K_M（稠密，关闭 thinking） | Qwen/Qwen3-14B-GGUF，9.0 GB | 9 GB + 32k KV 约 5 GB | 稠密对照：KV 压力和 MoE 完全不同 |
| q4b | Qwen3-4B-Instruct-2507 Q4_K_M | 2.3 GB | 2.3 GB + 16k KV 2.3 GB | 小模型、边缘部署参照（沿用本机档位） |

- gpt-oss 的推理强度设为 low（`REASONING=medium|high` 可改），由 proxy 通过 `chat_template_kwargs` 加到每个请求上。
- gpt-oss 的回复预算放宽到 1024 token、问答 512 token，因为推理 token 也算在里面。
- 推理引擎：llama.cpp `b12559`，`setup.sh` 会根据 `nvidia-smi` 自动选择 CUDA 架构（L4 是 89，和 4060 同属 Ada）。
- 本容器里（CPU，无 GPU）已经验证：
  - gpt-oss-20b 在 llama.cpp 上的 JSON 模式可用，推理内容和最终 JSON 分开返回；mem0-pg 通过整套 harness 跑完一轮 LoCoMo（检索、回复、约 7.8k token 的抽取请求），抽取结果能正常解析；
  - Graphiti 用的 `json_schema` 结构化输出返回合法 JSON；
  - `qa_score.py` 通过 proxy 调用评判：日期换种写法判对、时间题差一天判对、知识更新题只给旧值判错。
  - 第二轮时 llama-server 被本容器的 16 GB 内存上限 OOM 杀掉：CPU 模式下 12 GB 权重全在内存里，再加上内存里的 prompt cache。Colab L4 上权重在显存，主机内存约 50 GB，不受影响；如果在小内存机器上跑，用 `CACHE_RAM=0`。

## 3. 负载：标准 benchmark

| 数据集 | 用法 | 规模 |
|---|---|---|
| LoCoMo（`locomo10.json`） | 回放第 0 段对话里 speaker_a 的消息，每轮依次做检索、回复、写入记忆；最后问证据都已回放过的问题（排除第 5 类对抗题，与 mem0 论文一致） | l1：100 轮 + 50 题 |
| LongMemEval-S（`longmemeval_s_cleaned.json`，500 题） | 每题自带一段约 48 个会话、约 245 条用户消息、约 11.5 万 token 的历史。按时间回放用户消息；写入记忆时用数据集自带的助手回复（agent 仍然每轮生成回复，用于测前台路径） | 默认第 70 / 233 / 366 题：第一个跨会话、时间推理、知识更新题，完整历史 |

pilot 用截短的历史（`LME_TURNS=60`）：保留全部证据会话，再随机加入干扰会话，直到约 60 条用户消息。

**打分**（`analysis/qa_score.py`）：
- token F1（LoCoMo 论文的指标）；
- LLM 评判，按题型调整规则，参考 LongMemEval 的评测脚本和 mem0 的 J 指标：时间题允许差一天，知识更新题要求给出最新值，偏好题按评分标准判。
- 评判模型是本地的 gpt-oss-20b，不是论文里的 GPT-4o，所以只能用于我们这几个系统之间的比较，不能和论文里的绝对数值直接比。

## 4. 流程：先 pilot，看效果和花销再决定

`colab/memprof_colab_l1.ipynb`，运行时选 L4：

1. 第 1–3 格：参数、Drive、克隆仓库、安装（约 25–35 分钟）。
2. 第 4 格：`pilot` 在后台运行，约 2–3 小时（还没实测）：
   - preflight：硬件清单、fio、页缓存检查；
   - rates：llama-bench 测各 KV 深度下的 prefill / decode 速率；
   - kv：KV 分层微基准；
   - 5 个系统各跑 20 轮 LoCoMo + 10 题；
   - 1 个截短的 LongMemEval（60 条消息）× 5 个系统；
   - score：打分；
   - budget：花销估算。
3. 第 5 格：看三张表。
   - `qa_summary.md`：效果；
   - `budget.md`：根据 pilot 外推全套实验的小时数和 CU。按每轮耗时随轮数增长拟合，不是简单乘法；在 notebook 里填上 `CU_PER_HOUR` 就会换算成 CU；
   - `breakdown.md`：每个操作的耗时分解。
4. 第 6 格：选要跑的套件，默认 `l1 lme score`。

## 5. 托管运行（Claude 远程监控）

Claude 不登录你的 Google 账号，也碰不到 Colab 界面。远程管理靠仓库：

| 环节 | 做法 |
|---|---|
| 跑什么 | `colab/queue.txt`，每行一次套件调用。Claude 按你的决定改这个文件并推送；运行中的 `colab/supervisor.py` 每次开始新一行前会拉取代码 |
| 状态 | 每 10 分钟把 `status.md` / `status.json`（队列进度、当前 run、失败、Drive 校验、磁盘、内存、GPU、已用 CU）、`suite.log`、汇总表推送到 `colab-status` 分支。Claude 定时 fetch 这个分支检查 |
| 失败 | run 中途推理服务挂掉：重启服务，这个 run 重跑一次（套件内）。整行失败（有 run 失败、套件退出码非 0、超过 45 分钟没有任何输出则终止）：拉取最新代码后重试，最多 3 次。Claude 看到失败后修代码、推送，再在队列里加一行 `xxx  # retry 2` 重跑；已完成的 run 自动跳过 |
| 数据 | 两份副本：每个 run 结束即镜像到 Drive，托管程序再校验 Drive 上的副本（`meta.json` 存在、`spans.jsonl` 大小一致），不一致就重新同步；另外每个完成的 run 打包（不含数据库文件，小于 50 MB）推送到 `colab-status` 分支的 `runs/` |
| 花销 | 队列跑完后等 `IDLE_MIN`（默认 20 分钟）；没有新行就推送最终状态、刷新 Drive、释放运行时，不再计费。Drive 副本不完整时不释放 |
| 仍需要你 | 一次性：在 Colab Secrets 设 `GH_TOKEN`（细粒度 token，只授权这个仓库的 Contents 读写）。每次新运行时：打开 notebook，选 L4，“全部运行”。没有后台执行权限时，浏览器标签页需要一直开着 |

## 6. 新增的脚本

| 文件 | 作用 |
|---|---|
| `bench/workloads.py` | LoCoMo、LongMemEval-S 统一成同一种回放格式 |
| `bench/multi_e2e.py` | `--dataset`、`--item`、`--memorize-source`，问答带当前日期 |
| `analysis/qa_score.py` | F1 + LLM 评判，`--summary` 汇总 |
| `analysis/budget.py` | 由 pilot 外推全套实验的耗时和 CU |
| `memprof/iostat.py` | `evict()`：不需要特权的页缓存逐出；`python -m memprof.iostat drop` |
| `scripts/local/run_local_suite.sh` | `lme`、`score`、`budget`、`pilot` 套件；`SYNC_DIR`、`REP`、每个虚拟机单独的 preflight |
| `scripts/local/profiles.sh` | `gptoss20b`、`q14b` 档位 |
| `memprof/llm_proxy.py` | `--chat-kwargs`（gpt-oss 的推理强度） |
| `colab/memprof_colab_l1.ipynb` | Colab notebook |
| `colab/supervisor.py`、`colab/queue.txt` | 托管运行：队列、重试、卡住检测、Drive 校验、GitHub 状态和备份、空闲释放 |
