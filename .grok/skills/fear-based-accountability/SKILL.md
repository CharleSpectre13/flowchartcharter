---
name: fear-based-accountability
description: FlowChartCharter Fear-Based Accountability & Survival Mechanism — termination_risk_index, telemetry ledger, dynamic generation params, Monday pruning, lean re-hire. Triggers on survival, fear multiplier, fire agent, pruning, re-hire, termination risk.
---

# Fear-Based Accountability & Survival

Agent "fear" is an **algorithmic penalty amplifier**, not emotion.

## 1. Cognitive Survival Constraint
Every worker carries:
- `survival_status ∈ {ACTIVE, AT_RISK, CRITICAL, TERMINATED}`
- `termination_risk_index ∈ [0, 1]`

Spikes on: schema divergence, token over-ceiling, latency, structural drift.
High risk → lower temperature, `schema_lock=True`, shorter `max_tokens`.

## 2. Telemetry Ledger
Immutable per-cycle: schema errors, token spend vs ceiling, Δt, drift, quality.

## 3. Monday Pruning + Lean Re-hire
```
F(x) = α·(Q_success/Q_total) + β·(1/Δt) − γ·Tokens_norm + Q_ent
```
Fire if fitness < floor OR risk ≥ 0.85 OR schema_errors ≥ 5.
**Lean re-hire:** if surviving ops + Muscle-Memory VDB can carry load → **no backfill**.

## API
```python
agent.record_cycle(schema_divergence=1, token_spend=..., token_ceiling=..., ...)
agent.refresh_survival_prompt()  # injects live risk into system prompt
boss.monday_morning_sync(team, muscle_memory_records=n, lean_rehire=True)
```
