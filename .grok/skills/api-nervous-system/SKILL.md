---
name: api-nervous-system
description: FlowChartCharter Phase 2 FastAPI microservice — workload submit, roster TPC status, Monday Sync, Analytics advance, global EngineState singleton, Live-Wire LLM bridge. Triggers on api server, fastapi, microservice, /workload/submit, nervous system.
---

# API Nervous System

```bash
export PYTHONPATH=packages/core
python3 -m flowchartcharter   # 0.0.0.0:8080
```

## Endpoints
- POST `/workload/submit`
- GET `/roster/status`
- POST `/system/trigger-monday-sync`
- POST `/system/advance-analytics`
- POST `/system/end-of-week`

## State
`EngineState` singleton (lifespan) holds `FlowChartCharterSystem` — GM, Muscle-Memory, Living Playbook, Analytics Chief.

## Live LLM
`FCC_LLM_PROVIDER` + `FCC_LLM_API_KEY` → `llm_bridge.LLMBridge` with Pydantic `LLMNodeOutput` validation.
