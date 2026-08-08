# SPEC.md — FlowChartCharter Core System

**Authority mode:** Spec-Anchored  
**Version:** 0.1.0  
**Date:** 2026-08-08  
**Owner:** Spectre Industries / CharleSpectre13 open design

## 1. Concrete Functional Outcomes
1. An engineer can define a versioned Charter (sequential flow units + rhythm markers + exit criteria) as a typed schema and execute it with multi-agent binding.
2. Agents self-select flow units via Blackboard volunteer scoring (capability · rank · load) with >95% role-match on fixture scenarios.
3. Super-step engine runs parallel flow units, merges via deterministic channel reducers, and checkpoints state with zero data races under 100 concurrent updates.
4. Audit gate blocks synthesis when quality score < 0.90 and routes to muscle-memory remediation (max 3 loops).
5. Boss Agent Monday Morning Sync promotes/fires agents by fitness equation and writes updated playbook entries.
6. Coach Trust Hand-Off emits a typed trust signal when charter stability criteria are met, allowing engineer exit from the live loop.
7. Graph/RAG discovery is invocable only as an explicit sub-flow tool from a charter branch.

## 2. Explicit Scope Boundaries

**In scope**
- Charter schema, reducers, BSP super-step runtime (in-memory + port interfaces)
- Corporate hierarchy agents (Board, Boss, Position Manager, Key Player, Audit, Coach, Publisher)
- Blackboard volunteer binding
- Muscle-memory weights + checkpoint history store (file/memory)
- Fitness / talent management
- Continuous learning loop contracts and audit report schema
- Open-source Python core + TypeScript Studio demo shell
- Public GitHub repos under open license

**Out of scope (v0.1)**
- Production multi-tenant SaaS billing
- Real LLM vendor lock-in (ports only; mock executors allowed)
- Full Neo4j GraphRAG reimplementation (invoke existing graphrag-pipeline as tool later)
- Mobile native apps
- Non-English first-class docs

## 3. Technical Constraints & Non-Functionals
- Python 3.10+ core; TypeScript/React Studio optional
- Pydantic v2 (or TypedDict) for state schemas
- Sub-10ms in-memory state R/W in microbench
- Deterministic reducers (no unordered dict merge for critical channels)
- Max muscle-memory remediation loops: 3
- Budget: token_cost tracked; hard cap configurable per charter
- License: Apache-2.0 for open design
- No secrets in repo; env-based config only

## 4. Prior Architectural Decisions
1. Charter is primary; GraphRAG is secondary tool.
2. BSP / Pregel-style super-steps over free ReAct loops for main path.
3. Fitness equation: F = 0.4Q + 0.3Rhythm − 0.001Cost + 0.2Synergy
4. External memory (checkpointer + decisions-log) over context-only memory
5. continuous-team-audit-loop + loop-engineer mandatory before each public repo cut
6. LangGraph / ControlFlow / Marvin are reference adapters, not hard deps in core v0.1 (ports)

## 5. Task Decomposition
See TASKS.md. High-level:
- T1 Constitution + SPEC gate
- T2 Core types + metrics + agents
- T3 Charter graph + reducers + super-step
- T4 Blackboard + binding
- T5 Muscle-memory + audit gate + hand-off
- T6 Boss downtime sync
- T7 Loop-engineering continuous learning system
- T8 Studio demo UI
- T9 Public repo publication with pre-push audits
- T10 Examples + verification suite

## 6. Objective Verification Criteria
| ID | Criterion | Pass condition |
|----|-----------|----------------|
| V1 | Import core and run fixture charter | exit 0, quality gate evaluated |
| V2 | Reducer race test | 100 concurrent merges, no lost updates |
| V3 | Volunteer binding | fixture match score routing correct role |
| V4 | Remediation loop cap | stops at 3, never infinite |
| V5 | Fitness promote/fire | scores map to expected status transitions |
| V6 | Coach trust signal | emitted only when score ≥ 0.90 after stable run |
| V7 | Audit report schema | Cross-Reference Report fields complete |
| V8 | Open repo | public GitHub, Apache-2.0, README present |
