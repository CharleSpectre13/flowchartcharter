# Phase 4 — Open Source MVP & Enterprise Launch

Shipped with core **v1.4.0**:

1. **PyPI package** `flowchart-charter-engine` via `pyproject.toml`
2. **Multi-stage Dockerfile** + **docker-compose** (API + Qdrant)
3. **CI** `.github/workflows/audit.yml` (pycodestyle, pyflakes, black, tests, wheel)
4. **Manifesto README** contrasting GraphRAG vs FlowChartCharter pillars

```bash
pip install flowchart-charter-engine
docker compose up --build
```
