---
name: agent-skills-toolkit
description: Five essential FlowChartCharter agent function-calling skills — QueryMuscleMemory, EvaluateRhythmMarker, ExecuteQuantumCollapse, TriggerMondayMorningSync, AdjustCorporateRoster. Use when wiring Boss/GM tools, LLM tool schemas, or self-auditing agent runtimes.
---

# Agent Skills Toolkit

## Skills

| Skill | Replaces | Purpose |
|-------|----------|---------|
| `QueryMuscleMemory(state_vector, threshold)` | Open RAG | Precedent cheat-codes from successful charters only |
| `EvaluateRhythmMarker(output, schema)` | Manual QA | Q_s = exp(−k·D) schema gate; route-back on fail |
| `ExecuteQuantumCollapse(options, H_ctx)` | Guessing | Tensor routing: muscle × H_ctx × CFO matrix → M|ψ⟩ |
| `TriggerMondayMorningSync(telemetry)` | Ad-hoc review | Downtime RLAIF re-weights + talent actions |
| `AdjustCorporateRoster(id, action)` | Static roster | PROMOTE / DEMOTE / FIRE |

## Implementation
- Python: `flowchartcharter.skills.AgentSkillRuntime`
- Schemas: `flowchartcharter.prompts.AGENT_SKILL_SCHEMAS`
- Boss prompt: `flowchartcharter.prompts.BOSS_AGENT_SYSTEM_PROMPT`

## Rules
- Blackboard JSON only — no conversational filler between agents
- Never pass hand-off unless Q_s schema-compliant (D = 0 ideal)
- CFO matrix runs **before** collapse; may force `path_lite`
- High H_ctx biases toward `path_B` (data-cleansing Flow Unit)
