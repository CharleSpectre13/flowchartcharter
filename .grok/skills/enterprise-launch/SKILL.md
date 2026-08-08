---
name: enterprise-launch
description: FlowChartCharter Phase 4 public launch — pyproject/pip package flowchart-charter-engine, multi-stage Dockerfile, docker-compose with Qdrant, GitHub Actions continuous audit, manifesto README. Triggers on docker, pypi, packaging, whitepaper, compose, CI.
---

# Enterprise Launch

```bash
pip install flowchart-charter-engine
docker compose up --build
```

- Package: `flowchart-charter-engine` (setuptools, packages/core)
- Image: multi-stage Python 3.12 slim, port 8090
- Compose: engine + qdrant (Muscle-Memory)
- CI: `.github/workflows/audit.yml` — pycodestyle, pyflakes, black, tests, build
