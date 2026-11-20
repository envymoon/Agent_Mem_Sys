# 新颖性调研：从“系统 / 硬件”角度优化 Agent Memory

> 调研时间：2026-11。结论先行：**“从系统角度 profile agent memory”这件事本身已经有人做了，而且做得不浅**；
> 但 **“面向本地（单机 / 端侧）大规模记忆、把记忆数据结构和 LLM KV、存储层次（VRAM/DRAM/SSD）
> 一起协同设计”** 这个方向，目前没有找到直接对口的工作，仍有明确空白。定位要收窄，不能泛泛地说“没人从系统角度做”。

## 1. 已经存在、必须正面对比的工作

| 工作 | 做了什么 | 和本课题的关系 |
|---|---|---|
| **Agent Memory: Characterization and System Implications of Stateful Long-Horizon Workloads**（Stanford / KU Leuven，arXiv 2606.06448，2026-06/09） | 10 个系统（BM25、embedRAG、GraphRAG、HippoRAG v2、Mem0、SimpleMem、A-Mem、Letta、MIRIX…），H100 + vLLM 本地部署 + OpenAI API 两种模式；按 构建/检索/生成 三阶段拆分，接 NVML/DCGM 计数器（功耗、tensor core 活动、HBM 带宽）。结论：成本主要在**构建（写路径）**而不是查询；构建 token 里 decode 只占 ~4.6%，是 **prefill + embedding 主导**；Mem0 embedding 1:1 不批处理；多租户合并可让 Mem0 吞吐 ×9.6；建议 prefix reuse、批处理、后台化构建。 | **最直接的“撞车”对象**。它已经做了“全过程 profiling + 硬件计数器”，而且是 GPU 数据中心视角。我们的 profiling 若只是重复它的结论，新颖性不足。它**没有**：存储层次/放置、CPU/端侧、记忆存储引擎内部（序列化、过滤、冷启动）、KV 与记忆的协同。 |
| **Are We Ready For An Agent-Native Memory System?**（SJTU / 清华 / MemTensor，arXiv 2606.24775） | 数据管理视角，12 个记忆系统 × 11 个数据集；端到端时延（构建 + 查询摊薄）。结论：结构越重的系统构建/查询时延高几个数量级，但精度不成比例；局部维护优于全局重组。 | 只有端到端数字，没有分阶段/硬件分析。说明 DB 社区已关注，但还停在 benchmark 层面。 |
| **Akashic: Low-Overhead LLM Inference Service with MemAttention**（小红书 / SJTU / PKU，arXiv 2607.05708） | 指出语义相关性与**物理放置**脱节（“locality gap”）；NVMe 上按块组织记忆 chunk，按共同访问关系重定位，LSM 式 out-of-place 更新 + GC；对比 Mem0 吞吐 1.2–1.9×。 | **最接近“存储布局”思路**的一篇，但面向服务端 GPU、单层 NVMe，不涉及 DRAM/VRAM 分层、KV 复用、CPU 端侧。 |
| **MemForest**（NUS，arXiv 2605.23986） | 层次化时间索引；写路径分解：LLM 抽取 68%、摘要刷新 16%，**持久化只占 0.13%**；利用 prefix cache（命中 58%）与并行抽取提高吞吐。 | 也做了写路径拆分，但都是逻辑结构 + LLM 调用调度，不涉及硬件。 |
| **MemTier**（BGU，arXiv 2605.03675） | “分层”是 episodic/semantic/procedural 的**逻辑分层**；6GB 显卡笔记本 + Qwen2.5-7B；只测了检索时延（BM25 26ms、hybrid 97ms）。提到合并守护进程与前台推理争抢 VRAM、模型重载 10–30s。 | 本地场景，但完全没有硬件优化；名字容易混淆，需要在论文中区分“逻辑分层 vs 物理分层”。 |
| **LightMem**（ICLR'26）、Mem0 async 模式 | 把重的抽取/合并移出在线路径（“sleep-time”）。 | 写路径异步化已是共识；我们要研究的是**异步后台写和前台推理共享同一硬件时的干扰**，这点没人量化。 |
| **KV 作为记忆**：MemOS KVCacheMemory、KEEP（DAC'26）、InferScale（2607.27090）、Agent Memory Below the Prompt（2603.04428，Mac 上 Q4 KV 落 SSD） | 把记忆条目预计算成 KV 注入；KEEP 按静态/动态分组复用；2603.04428 在 M4 Pro 上把每个 agent 的 Q4 KV 持久化到 SSD，冷/温 TTFT 差 ~95×。 | 说明“记忆 ↔ KV”方向在升温。但它们要么不管文本记忆库（mem0 类）的写路径，要么只做 KV 持久化本身。 |
| **多轮/Agent KV 缓存**：CachedAttention/AttentionStore（ATC'24）、KVFlow（NeurIPS'25）、Pensieve、LMCache、“Where Should the KV Cache Live?”（2609.16215） | KV 在 HBM/DRAM/SSD 间分层、预取、按 agent 步骤图预测复用。 | 成熟的 serving 方向，可直接借鉴其机制；但它们把“记忆系统”当黑盒 prompt。 |
| **RAG serving**：RAGO、RAGCache、CacheBlend、PipeRAG、Chameleon、TeleRAG、RAGDoll、CacheSmith | RAG 管线调度、检索 KV 复用、异构加速器、单 GPU offload。 | Agent memory ≠ RAG：有**持续写**、更新/去重、实体维护，且查询集中在单用户的小而热的数据集。这是差异化论点。 |
| **向量检索的硬件**：DiskANN/SPANN、FaTRQ（far-memory ANNS）、D-NOVA（存内检索）、IKS（CXL 近存 RAG 检索） | 面向十亿级通用向量库。 | 单用户 agent 记忆规模小（10³–10⁵），瓶颈完全不同（见我们的测量），这些工作不能直接套用。 |

## 2. 空白在哪里（可主张的新颖点）

1. **端侧/单机场景**：已有表征工作全部是 H100/H800 数据中心 + vLLM，或云 API。
   本地场景的约束完全不同：**同一颗 CPU/GPU/统一内存** 同时承担 LLM、embedding、NLP、向量检索、存储，
   资源争用、冷启动、内存占用都是一等问题。没有人系统量化过。
2. **记忆存储引擎内部**：已有工作把向量库/历史库当作黑盒、或认为持久化“可以忽略”（MemForest 0.13%）。
   我们在 mem0 默认本地栈里看到的是：Python 逐点过滤、pickle+SQLite 逐点持久化、冷启动全量反序列化、
   全部常驻 DRAM —— 规模一大，这些都会变成主瓶颈（见规模实验）。
3. **记忆 × KV × 存储层次的协同设计**：
   - 记忆操作的 LLM 调用（抽取）有一个**巨大的静态前缀**（mem0 2.2.1 约 8k token），
     它和对话 agent 的 KV 在同一个 KV 池里互相驱逐 —— 这是“记忆系统决定 KV 放置策略”的新问题；
   - 用户记忆的**热子集**（高频实体/事实）可以以 KV 形式驻留 VRAM/DRAM，冷记忆以文本+向量落 SSD，
     这把 Akashic（存储布局）、KEEP/InferScale（KV 记忆）、CachedAttention（KV 分层）三条线连起来，目前没有人做。
4. **写路径与前台推理的干扰**：异步化已是共识，但在单机上异步写会和前台生成抢算力/带宽，
   需要优先级、批处理和“空闲时构建”的调度器 —— 2606.06448 给的是数据中心多租户合并的建议，不是单机干扰。

## 3. 建议的定位（一句话）

> *面向本地大规模 agent 记忆的硬件感知记忆系统：把记忆的“文本/向量/KV”三种表示在 VRAM–DRAM–SSD 层次上
> 统一放置与迁移，并与本地推理引擎协同调度记忆的读写路径。*

避免的说法：“首个从系统角度 profile agent memory”——这不成立（2606.06448 已做）。

## 参考链接

- [Agent Memory: Characterization and System Implications (arXiv 2606.06448)](https://arxiv.org/html/2606.06448v2)
- [Are We Ready For An Agent-Native Memory System? (arXiv 2606.24775)](https://arxiv.org/html/2606.24775v1)
- [Akashic: MemAttention (arXiv 2607.05708)](https://arxiv.org/abs/2607.05708)
- [MemForest (arXiv 2605.23986)](https://www.alphaxiv.org/abs/2605.23986)
- [MemTier (arXiv 2605.03675)](https://arxiv.org/pdf/2605.03675)
- [Agent Memory Below the Prompt: Persistent Q4 KV Cache on Edge (arXiv 2603.04428)](https://arxiv.org/pdf/2603.04428)
- [KEEP: KV-Cache-Centric Memory Management (arXiv 2602.23592)](https://arxiv.org/abs/2602.23592)
- [InferScale: GPU-Native KV Injection](https://www.alphaxiv.org/abs/2607.27090)
- [MemOS (arXiv 2505.22101)](https://arxiv.org/pdf/2505.22101) / [KVCacheMemory 文档](https://memos-docs.openmem.net/open_source/modules/memories/kv_cache_memory/)
- [Mem0 paper (arXiv 2504.19413)](https://alphaxiv.org/resources/2504.19413v1)
- [From LLM Inference to Agentic Workloads (arXiv 2608.15127)](https://arxiv.org/abs/2608.15127)
- [CachedAttention (arXiv 2403.19708)](https://arxiv.org/html/2403.19708v3)
- [KVFlow (NeurIPS'25)](https://papers.neurips.cc/paper_files/paper/2025/hash/b7971d31a7d5eb0f1eed2f8f6f368195-Abstract-Conference.html)
- [Where Should the KV Cache Live? (arXiv 2609.16215)](https://arxiv.org/html/2609.16215)
- [Tessera (arXiv 2609.32999)](https://arxiv.org/pdf/2609.32999)
- [RAGO (arXiv 2503.14649)](https://arxiv.org/pdf/2503.14649)
- [CacheSmith (arXiv 2610.18925)](https://arxiv.org/pdf/2610.18925)
- [RAGDoll (arXiv 2504.15302)](https://arxiv.org/pdf/2504.15302)
- [FaTRQ (arXiv 2601.09985)](https://arxiv.org/pdf/2601.09985)
- [D-NOVA (arXiv 2607.17538)](https://arxiv.org/pdf/2607.17538)
- [Accelerating RAG / IKS (arXiv 2412.15246)](https://arxiv.org/pdf/2412.15246)
- [LightMem (ICLR'26 notes)](https://en.papernotes.org/ICLR2026/model_compression/lightmem_lightweight_and_efficient_memory-augmented_generation/)
- [Agent memory write path (blog)](https://avchauzov.github.io/blog/2026/agent-memory-write-path/)
- [A Flat KV Cache Storage Architecture (arXiv 2610.38355)](https://arxiv.org/html/2610.38355)
