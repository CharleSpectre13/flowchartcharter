# FlowChartCharter

**Execution-and-quality-first multi-agent state-chart systems** — the process-orchestration discipline after GraphRAG.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

## Why
GraphRAG optimizes *what is related and how do I retrieve it*.  
FlowChartCharter optimizes *what is the fastest reliable path to execute* while building earned **Coach Trust Hand-Off** so the engineer can exit the live loop.

Graph / GraphRAG tools remain **callable sub-flows** when pure relational discovery is required. The Charter owns the workflow.

## Quick start
```bash
python3 examples/run_demo.py
python3 loop-engineering/Ops/run-learning-loop.py
```

## Architecture (v0.1)
- `packages/core` — agents, fitness, blackboard, charter, system facade
- `packages/runtime` — BSP super-step engine, reducers, memory checkpointer
- `packages/sdk` — public imports
- `loop-engineering/` — continuous learning contracts, verifiers, memory
- `07_CROSS_REFERENCE_REPORTS/` — continuous-team-audit-loop outputs
- `constitution/` + `spec/` — Spec-Driven Development contracts
- `.grok/skills/flowchartcharter-engineering/` — agent skill package

## Lifecycle
ST-01 Init → ST-02 Bind → ST-03 Super-step → ST-04 Audit gate → ST-05 Muscle-memory loop → ST-06 Coach Trust Hand-Off → ST-07 Monday Morning Sync

## Fitness
```
F = 0.4·Quality + 0.3·Rhythm − 0.001·Cost + 0.2·Synergy
```

## Open design
Apache-2.0. Pre-repo creation is gated by continuous-team-audit-loop + loop-engineer.

## Related skills
flowchartcharter-engineering · superpowers · spec-driven-development · advanced-agent-builder · loop-engineer · continuous-team-audit-loop · graph-engineering (tool mode only)
