---
name: executive-comms-protocol
description: Strict typed JSON performance-vector protocol for FlowChartCharter executive agents (CEO, CFO, Board, GM). Use when designing executive-layer oversight, minimizing token bloat, Monday Morning Sync strategic guidance, or any Board-to-operations handoff. Forbids free-form NL chat among executives. Always combine with flowchartcharter-engineering and continuous-team-audit-loop.
---

# Executive Comms Protocol

## Core Mandate
High-level agents (CEO, CFO, Board, GM) **never** open-ended chat. Every executive ↔ operational exchange is a **strict JSON performance vector** on the Blackboard. This is the primary control against token bloat.

## Roles
| Role | When active | Payload type |
|------|-------------|--------------|
| CEO | Monday Morning Sync + strategic charter forks | `StrategyVector` |
| CFO | Sync + budget/cost anomalies | `BudgetVector` |
| Board | Sync + Coach Trust Hand-Off reviews | `GovernanceVector` |
| GM (Boss) | Always operational buffer | `OpsVector` + talent outcomes |

## Required Schemas (strict)

```json
{
  "type": "StrategyVector",
  "from": "CEO",
  "charter_id": "string",
  "priority": 0-1,
  "budget_cap_tokens": "int",
  "quality_floor": 0.90,
  "playbook_patches": ["string"],
  "escalate_to_board": false
}
```

```json
{
  "type": "BudgetVector",
  "from": "CFO",
  "charter_id": "string",
  "token_spend": "int",
  "token_budget": "int",
  "cost_penalty_gamma": 0.001,
  "halt_if_over": true
}
```

```json
{
  "type": "GovernanceVector",
  "from": "Board",
  "charter_id": "string",
  "trust_signal": true,
  "approve_hand_off": true,
  "notes": "max 120 chars"
}
```

```json
{
  "type": "OpsVector",
  "from": "GM",
  "roster_outcomes": {"agent_id": "PROMOTED|RETAINED|DEMOTED|FIRED"},
  "fitness_snapshot": {"agent_id": 0.0},
  "playbook_updates": ["string"]
}
```

## Rules
1. Reject any executive message that is not one of the four vector types.
2. CEO/CFO/Board intervene **only** during Monday Morning Sync or explicit quality/cost halt.
3. GM is the sole day-to-day buffer; routine muscle-memory fixes never escalate.
4. All vectors are appended to Blackboard logs with timestamp + charter_id.
5. Free-form natural language between executives is a **forbidden pattern** (constitution Article VIII).

## Integration
- flowchartcharter-engineering owns lifecycle; this skill owns the executive wire format.
- Fitness cost term (−γ·Tokens) feeds BudgetVector.
- Coach Trust Hand-Off requires GovernanceVector with `approve_hand_off: true`.
