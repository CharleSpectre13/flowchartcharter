# TASKS — CharterHarness

Stop if consecutive_failures=3 or SPEC V-criteria already fail by design.

- [x] T1 KillSwitch type + `HALT` blocks next ActionUnit (failing test first)
- [x] T2 ToolPort wraps ActionUnit_GitHubPR / Slack; schema still Fear-gated
- [x] T3 ExecutionSandbox policy: dry-run default, allowlist, no raw shell
- [x] T4 DurableNotebook record after one super-step
- [x] T5 HarnessKernel: done := all required RhythmAudits passed (model cannot lie)
- [x] T6 Alias/docs: SimulationSandbox described as ScenarioSandbox
- [x] T7 `examples/test_v24_harness.py` V1–V8 green
- [x] T8 CXR + loop-engineering memory; desk badge + stop button

Do not start T2 until T1 test exists.
