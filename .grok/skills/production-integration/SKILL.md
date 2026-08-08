---
name: production-integration
description: FlowChartCharter Phase 1 production wiring — LLMExecutionClient (TPC inject), ProductionMuscleMemory (Qdrant/Pinecone/memory), Pydantic schema gate → entanglement_errors, async Boss super-step fan-out. Triggers on production, qdrant, pinecone, LLMExecutionClient, WorkerNode live.
---

# Production Integration

## LLMExecutionClient (inside WorkerNode)
- Appends playbook constraints
- Injects `termination_risk_index` → `generation_params_for_risk` (temp→0, schema_lock)
- `FlowUnitResultSchema` validation; failures → `entanglement_errors += 1`

```python
node = WorkerNode("W1", "Key Player")
node.execute_live("Legacy Code Refactor", path="path_A")
```

## ProductionMuscleMemory
```bash
export FCC_VECTOR_BACKEND=qdrant   # or pinecone | memory | auto
export FCC_QDRANT_URL=...
# or FCC_PINECONE_API_KEY + FCC_PINECONE_HOST
```

## Async rhythm
`run_workers_parallel(tasks)` — ThreadPoolExecutor fan-out after CFO pre-gate.
