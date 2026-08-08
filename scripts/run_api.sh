#!/bin/sh
# Boot FlowChartCharter API Nervous System on 0.0.0.0:8090
set -eu
cd "$(dirname "$0")/.."
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)/packages/core"
export FCC_HOST="${FCC_HOST:-0.0.0.0}"
export FCC_PORT="${FCC_PORT:-8090}"
exec python3 -m flowchartcharter.api_server
