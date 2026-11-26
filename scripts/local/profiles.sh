# Model profiles for an 8 GB consumer GPU (RTX 4060 / 4060 Laptop). Sourced by start_llama.sh / suites.
# Each profile = what a local-agent user would actually run with llama.cpp on this card.
# VRAM budget (8 GB, ~0.3-0.8 GB taken by the Windows desktop when the card drives a display):
#   q4b     Qwen3-4B-Instruct-2507 Q4_K_M  2.3 GB + KV f16 16k (2.3 GB) + embedder 0.6 GB  -> ~6.2 GB   MAIN
#   q8b     Qwen3-8B Q4_K_M (no-think)     4.7 GB + KV q8_0 12k (0.8 GB) + embedder        -> ~7.2 GB   max dense that fits
#   llama8b Llama-3.1-8B-Instruct Q4_K_M   4.6 GB + KV q8_0 12k (0.8 GB) + embedder        -> ~7.0 GB   other family / KV shape
#   moe30b  Qwen3-30B-A3B-Instruct-2507 Q4_K_M 17.3 GB, experts of all layers in host RAM (--n-cpu-moe),
#           attention + KV on GPU  -> the common "big MoE on an 8 GB card" setup; DRAM/PCIe bound. Needs >= 32 GB RAM.
#   cpu     tiny CPU-only profile (pipeline smoke test without a GPU)
# 24 GB profiles (Colab L4 / any 24 GB card; main platform after the move to Colab):
#   gptoss20b  gpt-oss-20b MXFP4 (12.1 GB; MoE 21B total / 3.6B active), 32k ctx f16 KV (~0.8 GB: half the layers
#              are 128-token sliding window), reasoning_effort=low (REASONING=medium|high to change)        MAIN
#   q14b       Qwen3-14B Q4_K_M (9.0 GB, dense, no-think), 32k ctx f16 KV (~5 GB)            dense contrast
#   q4b        (above) Qwen3-4B, small/edge reference
# Embedder (all profiles): Qwen3-Embedding-0.6B Q8_0 on GPU (last-token pooling, 1024-d).
MODELS=${MEMPROF_MODELS:-$HOME/models}
HF=https://huggingface.co
EMB_REPO=Qwen/Qwen3-Embedding-0.6B-GGUF; EMB_FILE=Qwen3-Embedding-0.6B-Q8_0.gguf
EMB_NGL=${EMB_NGL:-99}
case ${PROFILE:-q4b} in
  q4b)     LLM_REPO=unsloth/Qwen3-4B-Instruct-2507-GGUF; LLM_FILE=Qwen3-4B-Instruct-2507-Q4_K_M.gguf
           P_CTX=16384; P_KV=f16; P_NGL=99; P_EXTRA="" ;;
  q8b)     LLM_REPO=Qwen/Qwen3-8B-GGUF; LLM_FILE=Qwen3-8B-Q4_K_M.gguf
           P_CTX=12288; P_KV=q8_0; P_NGL=99; P_EXTRA="" ;;
  llama8b) LLM_REPO=bartowski/Meta-Llama-3.1-8B-Instruct-GGUF; LLM_FILE=Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf
           P_CTX=12288; P_KV=q8_0; P_NGL=99; P_EXTRA="" ;;
  moe30b)  LLM_REPO=unsloth/Qwen3-30B-A3B-Instruct-2507-GGUF; LLM_FILE=Qwen3-30B-A3B-Instruct-2507-Q4_K_M.gguf
           P_CTX=16384; P_KV=f16; P_NGL=99; P_EXTRA="--n-cpu-moe ${N_CPU_MOE:-48}"; P_BENCH="-ncmoe ${N_CPU_MOE:-48}" ;;
  gptoss20b) LLM_REPO=ggml-org/gpt-oss-20b-GGUF; LLM_FILE=gpt-oss-20b-MXFP4.gguf
           P_CTX=32768; P_KV=f16; P_NGL=99; P_EXTRA=""; P_NOTHINK=0
           P_CHAT_KWARGS="{\"reasoning_effort\": \"${REASONING:-low}\"}" ;;
  q14b)    LLM_REPO=Qwen/Qwen3-14B-GGUF; LLM_FILE=Qwen3-14B-Q4_K_M.gguf
           P_CTX=32768; P_KV=f16; P_NGL=99; P_EXTRA="" ;;
  cpu)     LLM_REPO=Qwen/Qwen2.5-1.5B-Instruct-GGUF; LLM_FILE=qwen2.5-1.5b-instruct-q4_k_m.gguf
           P_CTX=16384; P_KV=f16; P_NGL=0; P_EXTRA=""; EMB_NGL=0 ;;
  *) echo "unknown PROFILE=$PROFILE" >&2; return 1 2>/dev/null || exit 1 ;;
esac
P_BENCH=${P_BENCH:-}   # llama-bench equivalent of P_EXTRA (rates suite)
P_NOTHINK=${P_NOTHINK:-1}             # Qwen3: enable_thinking=false (ignored by other templates)
P_CHAT_KWARGS=${P_CHAT_KWARGS:-'{}'}  # extra chat_template_kwargs the proxy adds to every chat request
LLM_GGUF=$MODELS/$LLM_FILE
EMB_GGUF=$MODELS/$EMB_FILE
