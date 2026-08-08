# PLAN.md — FlowChartCharter

## Architecture
```
packages/core     → pure domain: Agent, BossAgent, Charter, Metrics, Fitness, Blackboard
packages/runtime  → SuperStepEngine, CheckpointerPort, ChannelReducers
packages/sdk      → public FlowChartCharterSystem facade
examples/         → enterprise migration charter demo
loop-engineering/ → continuous learning contracts + ops
Studio (web)      → glanceable charter map + live roster + sync console
```

## Data contracts
- ExecutionMetrics: token_cost, execution_time, quality_score, synergy_score
- FlowUnit: id, name, inputs, outputs, exit_criteria, rhythm_marker
- CharterState: version, units[], snapshot, blackboard, trust_signal
- AuditReport: completed, excellent, weak, dos_donts, adjustments

## Risks
- Over-coupling to LangGraph → mitigated by ports in v0.1
- Simulated quality scores in demo → labeled as sim; real adapters later
- Repo sprawl → monorepo primary + thin satellite repos for loop/studio if needed

## Tech decisions
- Python stdlib-first core (uuid, dataclasses, typing)
- Optional pydantic if available
- Studio: existing TanStack/Vite workspace stack for live preview
