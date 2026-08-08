---
name: playbook-compiler
description: FlowChartCharter Phase 3 Head Coach Playbook Compiler — Charterfile YAML DSL, dynamic Pydantic create_model schemas, engine hydration, POST /system/load-playbook, Live-Wire unit execution. Triggers on charterfile, playbook compiler, load-playbook, YAML DSL.
---

# Playbook Compiler

```yaml
playbook_name: "Legacy Auth Refactor"
global_cfo_ceiling: 3500
roster_requisition: [...]
flow_units:
  - id: U1_Ingest_Clean
    schema: { clean_code: string, variables_found: list[string] }
```

```python
system.load_playbook("examples/charterfiles/legacy_auth_refactor.yaml")
system.execute_compiled("Refactor legacy auth")
```

API: `POST /system/load-playbook` (multipart YAML) · `POST /system/execute-compiled`
