#!/bin/sh
# FlowChartCharter container entrypoint
set -eu

export FCC_HOST="${FCC_HOST:-0.0.0.0}"
export FCC_PORT="${FCC_PORT:-8090}"
export FCC_LIVE_WIRE="${FCC_LIVE_WIRE:-1}"
export FCC_LLM_PROVIDER="${FCC_LLM_PROVIDER:-mock}"

# Qdrant sidecar (docker-compose) → production Muscle-Memory
if [ -n "${FCC_QDRANT_URL:-}" ]; then
  export FCC_VECTOR_BACKEND="${FCC_VECTOR_BACKEND:-qdrant}"
  echo "[entrypoint] Muscle-Memory backend: Qdrant @ ${FCC_QDRANT_URL}"
else
  export FCC_VECTOR_BACKEND="${FCC_VECTOR_BACKEND:-memory}"
  echo "[entrypoint] Muscle-Memory backend: in-memory"
fi

echo "[entrypoint] FlowChartCharter API on ${FCC_HOST}:${FCC_PORT}"
exec "$@"
