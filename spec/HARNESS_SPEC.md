# SPEC — CharterHarness (exact-fit car under the Charter)

**Authority:** Spec-Anchored  
**Version:** 2.4.0-proposed  
**Constitution:** Articles I, IV, VI, VIII, IX bind this spec  
**Status:** Implemented in v2.4. Hot-path gap closed in v2.5 Halt Law (`HALT_LAW_SPEC.md`).

## 1. Concrete Functional Outcomes

1. A Charter run can execute only while `KillSwitch` is `ARMED`. One `HALT` freezes new side-effects; in-flight ActionUnits finish or abort dry. The run cannot claim `done` after HALT.
2. Every ToolPort call is schema-validated, attested, and executed inside `ExecutionSandbox`. Hallucinated payloads never leave the process (Fear path unchanged).
3. Every super-step writes a DurableNotebook record: checkpoint blob + optional git commit hash + muscle-memory id. Restart from that record does not ask the model what happened.
4. Every Flow Unit still emits a `RhythmAudit` JSON. Implementor ≠ Audit Manager. Fail → muscle-memory remediation, cap 3, then OpsVector to GM.
5. Retrieval stays honest: `claimed_graphrag=true` only after successful GraphRAG HTTP. DRIFT/KG remain `fcc_kg_subflow`.
6. An agent that says “done” while any required Rhythm marker is unpassed is rejected. The harness, not the model, decides finished.

## 2. Explicit Scope Boundaries

**In**
- `packages/core/flowchartcharter/harness.py` (kernel: loop hooks, KillSwitch, ToolPort adapter)
- `execution_sandbox.py` (isolation wrapper around ActionUnits)
- `durable_notebook.py` (checkpoint + optional git hash; in-process first)
- One example: `examples/test_v24_harness.py`
- Rename-in-docs: today’s `SimulationSandbox` → **ScenarioSandbox** (behavior unchanged)

**Out**
- Replacing Hybrid Router, Charter, or Coach Trust
- Vendor SDKs, E2B/Daytona cloud, real gVisor
- Reimplementing Leiden / Microsoft GraphRAG
- Slot-math, Pixi, Storybook (wrong simulation skill surface)
- Multi-tenant OS containers
- Silent live LLM spend
- Studio UI rewrite beyond a one-line “Harness: ARMED/HALT” badge later

## 3. Technical Constraints & Non-Functionals

- Python 3.10+, stdlib + existing Pydantic. No new runtime deps.
- Tool calls: schema before HTTP. Dry-run default without credentials.
- CFO ceiling remains the spend brake. KillSwitch is the authority brake.
- Super-step extra overhead target: < 5 ms local (no network).
- Rhythm payload remains the locked JSON in rhythm-marker-validator.
- Port honesty from v2.2.1 / v2.3 holds.
- Maker-checker never collapsed into one agent.

## 4. Prior Architectural Decisions (do not reopen)

- Charter is primary. GraphRAG is a sub-flow.
- Executive wire is typed vectors only.
- Muscle-Memory is the 0-token win on repeats.
- Coach Trust: PENDING until 1-click approve.
- Fear path: schema → optional dry-run → HTTP.
- LLM via one OpenAI-compatible Port. Mock is not live.
- Constitution Article IX forbidden patterns stay forbidden.

## 5. Task Decomposition

See `HARNESS_TASKS.md`. Order: types → KillSwitch → ToolPort wrap → Notebook → ScenarioSandbox rename-in-docs → tests → CXR. No UI until tests green.

## 6. Objective Verification Criteria

A Verifier who did not write the code must be able to run:

```
PYTHONPATH=packages/core python3 examples/test_v24_harness.py
```

and see:

| ID | Assertion |
|---|---|
| V1 | `KillSwitch.halt()` prevents a subsequent ActionUnit HTTP (status blocked or dry abort) |
| V2 | Claiming `done=True` with a failed RhythmAudit raises / returns not-done |
| V3 | ToolPort on invalid GitHub payload → `BLOCKED_SCHEMA_FAILURE`, unauthorized SE = 0 |
| V4 | Notebook record after one unit includes `checkpoint_id` and `rhythm_audit` |
| V5 | Retrieval through harness still has `claimed_graphrag is False` without endpoint |
| V6 | ScenarioSandbox (old SimulationSandbox) still passes `test_phase2_sandbox.py` |
| V7 | No new vendor SDK names in `pyproject.toml` |
| V8 | pycodestyle max-line-length 88 on new modules |

SQI of this SPEC: 6/6 elements present.
