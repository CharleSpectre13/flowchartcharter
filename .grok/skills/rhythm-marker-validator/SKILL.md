---
name: rhythm-marker-validator
description: Self-auditing Rhythm Marker validators for FlowChartCharter. Use when implementing ST-04 audit gates, exit-criteria checks, quality thresholds at designated markers, or validator agents that review state snapshots before Blackboard commit. Enables Earned Engineering Trust without continuous executive oversight. Always combine with flowchartcharter-engineering and continuous-team-audit-loop.
---

# Rhythm Marker Validator

## Core Mandate
Specialized **validator agents** review state snapshots at designated **Rhythm Markers** against strict quality thresholds. The team is self-auditing so CEO/CFO/Board and the Head Coach only intervene on strategic forks.

## Marker Contract
Every FlowUnit declares:
- `rhythm_marker` — stable id (e.g. `start`, `bind`, `superstep`, `gate`, `loop`, `handoff`, `sync`)
- `exit_threshold` — numeric gate (default quality ≥ 0.90)
- typed inputs / outputs

## Validator Agent Duties
1. Load checkpointed state at the marker.
2. Evaluate exit criteria (quality, synergy, cost caps, schema validity).
3. Emit pass → allow edge to next unit; fail → route to muscle-memory remediation (max 3 loops).
4. Never self-grade the same agent that produced the work (maker-checker).

## Pass / Fail Payload (strict JSON)
```json
{
  "type": "RhythmAudit",
  "marker": "gate",
  "charter_id": "string",
  "quality": 0.0,
  "threshold": 0.90,
  "passed": true,
  "remediation_loops": 0,
  "blocking_issues": []
}
```

## Rules
1. Synthesis / Coach Trust Hand-Off cannot fire unless the final gate marker passed.
2. Remediation loop hard-capped (default 3); escalate OpsVector to GM on cap.
3. Validators write only `RhythmAudit` vectors to the Blackboard — no free-form chat.
4. Independent Audit Manager role ≠ implementor Key Players.

## Integration
- ST-04 in the seven-phase lifecycle is the primary gate marker.
- Feeds executive-comms-protocol (BudgetVector / GovernanceVector) only on failure or hand-off.
- continuous-team-audit-loop after any threshold or marker schema change.
