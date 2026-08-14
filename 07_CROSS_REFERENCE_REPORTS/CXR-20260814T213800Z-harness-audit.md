# CXR — Adversarial product audit (post-harness)

**Mode:** continuous-team-audit-loop + loop-engineer verifier  
**Building:** none  
**Self-grade warning:** same session that shipped the harness. Discount praise.

## Blocking (honest)

1. Harness is **not on the Charter hot path**. `execute_charter` / `execute_playbook_action_unit` never call `KillSwitch` or `ToolPort`. HALT only works if you remember to use `harness.run_action`.
2. ExecutionSandbox is **policy**, not isolation. No process, container, or syscall boundary.
3. DurableNotebook is **RAM**. Git SHA is cosmetic. Restart forgets unless something else persists it.
4. Retrieval is not GraphRAG. DRIFT is a neighborhood walk over a hand-built ontology.
5. Many quality numbers are still `0.92 if ok`. Rhythm is real JSON; the score is often not earned.
6. Loop-engineering taxonomy is mostly folders. No running outer loop with worktrees, receipts, and stop-hooks in production.

## Excellent (narrow)

- Contracts are named and mostly tested: Fear, CFO, Coach, Port honesty, `claimed_graphrag`.
- Maker-checker exists as a type. That is the actual differentiator vs retrieval stacks.

## Adjustment

Do not market “world-class harness” until HALT is unavoidable on every ActionUnit the Charter can fire.

**FCC (as an accountable agent OS, today): 5.5 / 10**  
**Microsoft GraphRAG (as a retrieval/sensemaking system, today): 8 / 10**
