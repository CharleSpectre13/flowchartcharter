# SPEC — Earned Rhythm (v2.6.0)

**Authority:** Spec-Anchored  
**Skills:** rhythm-marker-validator · loop-engineer · flowchartcharter-engineering

## 1. Outcomes

1. Quality is computed from an evidence bundle. Maker `quality` / `ok` claims are recorded and ignored.
2. Audit Manager is a separate function. It cannot see the maker’s grade.
3. `Q = 0.40·schema + 0.20·not_blocked + 0.15·secrets + 0.15·budget + 0.10·maker_checker`. HALT → 0. Dry-run caps at 0.90.
4. Implementor role containing `audit` matching the auditor → `maker_checker_violation`, cannot pass.
5. `force_quality` raises unless `FCC_ALLOW_FORCE_QUALITY=1`. Learning loop must not use it.
6. Harness `done` requires `earned=true` audits. Ungraded “I passed” is rejected.

## 2. Scope

**In:** `rhythm_gate.py`, `RhythmValidatorAgent`, `system.execute_charter`, `harness` done predicate, retrieval stamp, learning loop, tests, version badge.  
**Out:** Leiden, gVisor, vendor judge SDK, Studio rewrite, LLM-as-judge (no live key).

## 3. Constraints

No new deps. RhythmAudit JSON stays valid. Prior suites stay green.

## 4. Prior decisions

Charter owns the path. HALT is on execute. GraphRAG is sub-flow. Maker ≠ checker.

## 5. Tasks

Implement evidence + formula → wire charter/harness/retrieval → ban force_quality → tests V1–V8.

## 6. Verification

`python3 examples/test_v26_earned_rhythm.py` all pass.
