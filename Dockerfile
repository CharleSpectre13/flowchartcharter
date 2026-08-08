# FlowChartCharter Engine — multi-stage production image
# Boots FastAPI Nervous System on 0.0.0.0:8090
#
#   docker build -t flowchart-charter-engine .
#   docker run -p 8090:8090 flowchart-charter-engine

# ---------------------------------------------------------------------------
# Stage 1: build wheel
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build
ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE requirements.txt ./
COPY packages/core ./packages/core

RUN pip install --upgrade pip setuptools wheel build \
    && pip wheel --no-deps -w /wheels . \
    && pip wheel -w /wheels -r requirements.txt

# ---------------------------------------------------------------------------
# Stage 2: runtime
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="FlowChartCharter Engine" \
      org.opencontainers.image.description="Execution-first multi-agent API Nervous System" \
      org.opencontainers.image.source="https://github.com/CharleSpectre13/flowchartcharter" \
      org.opencontainers.image.licenses="Apache-2.0"

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FCC_HOST=0.0.0.0 \
    FCC_PORT=8090 \
    FCC_LIVE_WIRE=1 \
    FCC_LLM_PROVIDER=mock \
    FCC_VECTOR_BACKEND=auto \
    PATH="/app/.local/bin:$PATH"

# non-root user
RUN useradd --create-home --uid 10001 fcc \
    && mkdir -p /app/data /app/charterfiles \
    && chown -R fcc:fcc /app

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* \
    && rm -rf /wheels

COPY examples/charterfiles /app/charterfiles
COPY scripts/docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh && chown fcc:fcc /app/docker-entrypoint.sh

USER fcc
EXPOSE 8090

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/health', timeout=3)"

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["python", "-m", "flowchartcharter"]
