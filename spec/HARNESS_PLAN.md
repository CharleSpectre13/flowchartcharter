# PLAN — CharterHarness

**From:** HARNESS_SPEC.md  
**Phase:** Superpowers 3 — Plan. Not implement.

## Shape

One new kernel module, two small adapters, one test file.  
Existing Charter / Rhythm / Port / ActionUnits stay. The car wraps them.

```
Charter.step
    → HarnessKernel.arm_check()        # KillSwitch
    → ToolPort.execute(unit)           # schema + sandbox
    → RhythmValidator.audit()          # teacher
    → DurableNotebook.commit()         # notebook
    → CFO.charge(billed_tokens)        # brakes
```

## Components

| Module | Responsibility | Hoare |
|---|---|---|
| `KillSwitch` | ARMED / HALTED. Global. | `{armed} halt() {halted ∧ no new HTTP}` |
| `ToolPort` | Attest + dispatch ActionUnits | `{schema_ok} exec() {effect xor blocked}` |
| `ExecutionSandbox` | Isolate side-effects (in-process v1: no network unless allowlisted + dry-run default) | `{policy} run() {policy'}` |
| `DurableNotebook` | Checkpoint + muscle id + optional git sha | `{unit_done} commit() {recoverable}` |
| `HarnessKernel` | Glue. Does not own the map. | Charter calls kernel, never the reverse |

## Risks

| Risk | Mitigation |
|---|---|
| Name collision “sandbox” | ScenarioSandbox vs ExecutionSandbox |
| Over-clone Claude Code | No free bash. Hands = ToolPort only |
| Context-rot project-creep | Out of v1. Muscle-Memory is enough |
| Implementor self-grade | Rhythm stays independent |

## Next

Approve SPEC → T1 KillSwitch + failing tests first (TDD).
