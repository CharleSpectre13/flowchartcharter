---
name: muscle-memory-vectordb
description: FlowChartCharter Muscle-Memory Vector DB — stores verified execution trajectories (state embedding, flow path, Q_entanglement, prompt tweak) instead of unstructured GraphRAG chunks. Triggers on muscle memory, execution memory, cheat code retrieval, QueryMuscleMemory, trajectory store, or charter acceleration.
---

# Muscle-Memory Vector DB

## Why it beats GraphRAG under pressure
| GraphRAG | Muscle-Memory |
|----------|---------------|
| Unstructured graph → chunks | Structured execution vectors |
| LLM re-reasons every time | Replays verified Flow Unit sequence |
| High latency / tokens / hallucination | Sub-second, zero hallucination, coach trust |

## Four quadrants per record
1. **State Embedding** `state_vector` — entropy, size_kb, complexity, error_weight
2. **Contextual Action** `successful_flow_path` — ordered Flow Units
3. **Synergy Fingerprint** `entanglement_score` — Q_entanglement
4. **Cheat Code** `prompt_tweak` — historical prompt/format insight

## API
```python
from flowchartcharter import MuscleMemoryVectorDB, ExecutionMemoryRecord

db = MuscleMemoryVectorDB()
db.commit_memory(record)
hit = db.query_muscle_memory(payload, similarity_threshold=0.85)
```

## Skill wiring
- `QueryMuscleMemory` → `db.query_top_k`
- Successful charters → `commit_memory` (quality ≥ 0.90)
- Monday Morning Sync re-ingests successful_runs into the VDB

## Rules
- Only commit trustworthy trajectories (quality ≥ 0.90 or Q_ent ≥ 0.85)
- On MISS → fall back to Charter quantum collapse (never invent paths)
- On HIT → reuse flow path + apply prompt_tweak; confidence 1.0
- Blackboard JSON only — no free-form NL between agents
