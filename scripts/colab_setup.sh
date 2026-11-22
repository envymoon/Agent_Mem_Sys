#!/usr/bin/env bash
# One-time setup on a fresh Colab GPU runtime (Ubuntu 22.04, root, Python 3.12). Idempotent, ~15 min.
# Three isolated venvs: .venv (harness + mem0 + Graphiti), .venv-vllm (inference), .venv-letta (Letta server).
set -euo pipefail
cd "$(dirname "$0")/.."
export DEBIAN_FRONTEND=noninteractive
command -v uv >/dev/null || pip install -q uv
echo "[1/5] services (Postgres+pgvector, Qdrant, Neo4j)"; scripts/services.sh install
echo "[2/5] harness venv"
[ -x .venv/bin/python ] || uv venv -q -p 3.12 .venv
VIRTUAL_ENV=.venv uv pip install -q -r requirements-gpu.txt
.venv/bin/python -c "import en_core_web_sm" 2>/dev/null || VIRTUAL_ENV=.venv uv pip install -q \
  https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl
echo "[3/5] vLLM venv"
[ -x .venv-vllm/bin/vllm ] || { uv venv -q -p 3.12 .venv-vllm; VIRTUAL_ENV=.venv-vllm uv pip install -q "vllm==${VLLM_VERSION:-0.34.0}"; }
echo "[4/5] Letta server"; scripts/letta.sh setup
echo "[5/5] data + model weights"
LOCOMO=${LOCOMO:-/content/locomo/data/locomo10.json}
[ -f "$LOCOMO" ] || git clone -q --depth 1 https://github.com/snap-research/locomo "$(dirname "$(dirname "$LOCOMO")")"
.venv-vllm/bin/python -c "
from huggingface_hub import snapshot_download as s
s('${LLM_MODEL:-Qwen/Qwen3-8B}'); s('${EMB_MODEL:-Qwen/Qwen3-Embedding-0.6B}')"
echo "setup ok"
