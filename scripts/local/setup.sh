#!/usr/bin/env bash
# One-time setup of the local profiling stack on the user's own machine: native Ubuntu 22.04/24.04 or
# WSL2 Ubuntu on Windows. Run as root (services, page-cache drops and /proc/<pid>/io need it):
#   sudo -E scripts/local/setup.sh            # or, from Windows:  scripts\win\memprof.ps1 setup
# Idempotent; ~20-30 min the first time (CUDA toolkit + llama.cpp build + model downloads).
#
#   LLAMA_TAG=b12559     pinned llama.cpp release (the build the harness was developed against)
#   CUDA_ARCH=auto       from nvidia-smi compute_cap (89 = RTX 40xx / L4, 86 = RTX 30xx / A10, 80 = A100, 90 = H100)
#   DL_PROFILES="q4b q8b llama8b"   model profiles to download (Colab L4: "gptoss20b q14b q4b", ~23 GB)
#   MEMPROF_MODELS=$HOME/models     keep models on the same SSD you want to profile (NOT /mnt/c in WSL)
set -euo pipefail
cd "$(dirname "$0")/../.."
export DEBIAN_FRONTEND=noninteractive
LLAMA_TAG=${LLAMA_TAG:-b12559}
CUDA_ARCH=${CUDA_ARCH:-$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader 2>/dev/null | head -1 | tr -d '. ')}
CUDA_ARCH=${CUDA_ARCH:-89}
LLAMA_DIR=${LLAMA_DIR:-$HOME/llama.cpp}
export MEMPROF_MODELS=${MEMPROF_MODELS:-$HOME/models}
[ "$(id -u)" = 0 ] || { echo "run as root (sudo -E $0)"; exit 1; }
case $PWD in /mnt/[a-z]/*) echo "WARNING: repo is on a Windows drive ($PWD) -- I/O goes through 9P and is NOT representative. Clone it inside WSL (e.g. /root/Agent_Mem_Sys)." ;; esac
IS_WSL=0; grep -qi microsoft /proc/version && IS_WSL=1
export PATH=/usr/lib/wsl/lib:/usr/local/cuda/bin:$PATH

echo "[1/7] apt packages"
apt-get update -q >/dev/null
apt-get install -y -q build-essential cmake git curl ca-certificates gnupg lsb-release fio sysstat \
  pciutils util-linux python3-venv python3-pip jq >/dev/null
command -v uv >/dev/null || { curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null; export PATH=$HOME/.local/bin:$PATH; }

echo "[2/7] CUDA toolkit (compiler only; the driver comes from Windows / the host)"
if nvidia-smi >/dev/null 2>&1; then
  if ! command -v nvcc >/dev/null; then
    . /etc/os-release
    repo=$([ $IS_WSL = 1 ] && echo wsl-ubuntu || echo "ubuntu${VERSION_ID//./}")
    curl -fsSL -o /tmp/cuda-keyring.deb "https://developer.download.nvidia.com/compute/cuda/repos/$repo/x86_64/cuda-keyring_1.1-1_all.deb"
    dpkg -i /tmp/cuda-keyring.deb >/dev/null && apt-get update -q >/dev/null
    apt-get install -y -q "${CUDA_PKG:-cuda-toolkit-12-8}" >/dev/null   # toolkit only, never a driver inside WSL
  fi
  nvcc --version | tail -1
  GPU=1
  if [ "${NSIGHT:-1}" = 1 ]; then  # kernel-level profiling (run_local_suite.sh kprof): Nsight Systems + Compute CLIs
    for t in nsys ncu; do command -v $t >/dev/null || { f=$(ls -d /usr/local/cuda/bin/$t /opt/nvidia/nsight-*/*/bin/$t \
      /opt/nvidia/nsight-*/*/$t 2>/dev/null | sort -V | tail -1); [ -n "$f" ] && ln -sf "$f" /usr/local/bin/$t; }; done
    if ! command -v nsys >/dev/null || ! command -v ncu >/dev/null; then
      if ! apt-cache policy 2>/dev/null | grep -q developer.download.nvidia.com/compute/cuda; then
        . /etc/os-release
        curl -fsSL -o /tmp/cuda-keyring.deb \
          "https://developer.download.nvidia.com/compute/cuda/repos/ubuntu${VERSION_ID//./}/x86_64/cuda-keyring_1.1-1_all.deb" \
          && dpkg -i /tmp/cuda-keyring.deb >/dev/null && apt-get update -q >/dev/null
      fi
      pk=$(apt-cache search --names-only '^nsight-systems-[0-9]' | awk '{print $1}' | sort -V | tail -1)
      pc=$(apt-cache search --names-only '^nsight-compute-[0-9]' | awk '{print $1}' | sort -V | tail -1)
      apt-get install -y -q $pk $pc >/dev/null 2>&1 || echo "  nsight install failed ($pk $pc)"
      for t in nsys ncu; do command -v $t >/dev/null || { f=$(ls -d /opt/nvidia/nsight-*/*/bin/$t /opt/nvidia/nsight-*/*/$t \
        /usr/local/cuda*/bin/$t 2>/dev/null | sort -V | tail -1); [ -n "$f" ] && ln -sf "$f" /usr/local/bin/$t; }; done
    fi
    echo "  nsys: $(nsys --version 2>&1 | tail -1)   ncu: $(ncu --version 2>&1 | tail -1)"
  fi
else
  echo "  no NVIDIA GPU visible -> CPU-only build (PROFILE=cpu)"; GPU=0
fi

echo "[3/7] llama.cpp $LLAMA_TAG"
[ -d "$LLAMA_DIR/.git" ] || git clone -q https://github.com/ggml-org/llama.cpp "$LLAMA_DIR"
git -C "$LLAMA_DIR" fetch -q --tags origin
git -C "$LLAMA_DIR" checkout -q "$LLAMA_TAG"
if [ ! -x "$LLAMA_DIR/build/bin/llama-server" ] || [ "$(cat "$LLAMA_DIR/build/.memprof_tag" 2>/dev/null)" != "$LLAMA_TAG-$GPU-$CUDA_ARCH" ]; then
  cmake -S "$LLAMA_DIR" -B "$LLAMA_DIR/build" -DCMAKE_BUILD_TYPE=Release -DLLAMA_CURL=OFF \
    $([ $GPU = 1 ] && echo "-DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=$CUDA_ARCH") >/dev/null
  cmake --build "$LLAMA_DIR/build" -j "$(nproc)" --target llama-server llama-bench >/dev/null
  echo "$LLAMA_TAG-$GPU-$CUDA_ARCH" >"$LLAMA_DIR/build/.memprof_tag"
fi
"$LLAMA_DIR/build/bin/llama-server" --version 2>&1 | tail -2

echo "[4/7] memory backends (Postgres 16 + pgvector, Qdrant, Neo4j 5.26)"
scripts/services.sh install

echo "[5/7] harness venv"
[ -x .venv/bin/python ] || uv venv -q -p 3.12 .venv
# --python, not VIRTUAL_ENV: Colab's preinstalled uv ignores VIRTUAL_ENV and installs into the system Python
uv pip install -q --python .venv/bin/python -r requirements-gpu.txt
.venv/bin/python -c "import aiohttp, mem0" || { echo "venv is missing packages"; exit 1; }
.venv/bin/python -c "import en_core_web_sm" 2>/dev/null || uv pip install -q --python .venv/bin/python \
  https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl

echo "[6/7] models -> $MEMPROF_MODELS"
mkdir -p "$MEMPROF_MODELS"
dl() { [ -s "$MEMPROF_MODELS/$2" ] && [ ! -f "$MEMPROF_MODELS/$2.part" ] && return 0
       echo "  $1/$2"; touch "$MEMPROF_MODELS/$2.part"
       curl -fL --retry 5 -C - -o "$MEMPROF_MODELS/$2" "https://huggingface.co/$1/resolve/main/$2" && rm -f "$MEMPROF_MODELS/$2.part"; }
for p in ${DL_PROFILES:-q4b q8b llama8b}; do (PROFILE=$p; source scripts/local/profiles.sh; dl "$LLM_REPO" "$LLM_FILE"); done
(source scripts/local/profiles.sh; dl "$EMB_REPO" "$EMB_FILE")

echo "[7/7] benchmarks: LoCoMo, LongMemEval-S (cleaned)"
LOCOMO=${LOCOMO:-$HOME/locomo/data/locomo10.json}
[ -f "$LOCOMO" ] || git clone -q --depth 1 https://github.com/snap-research/locomo "$(dirname "$(dirname "$LOCOMO")")"
LONGMEMEVAL=${LONGMEMEVAL:-$HOME/longmemeval/longmemeval_s_cleaned.json}
[ -s "$LONGMEMEVAL" ] || { mkdir -p "$(dirname "$LONGMEMEVAL")"; curl -fL --retry 5 -C - -o "$LONGMEMEVAL" \
  https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/longmemeval_s_cleaned.json; }
echo "setup ok  (WSL=$IS_WSL GPU=$GPU llama.cpp=$LLAMA_TAG models=$MEMPROF_MODELS)"
