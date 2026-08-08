# Contributing to CharterHub

1. Fork [flowchartcharter](https://github.com/CharleSpectre13/flowchartcharter)
2. Add `charterhub/playbooks/community/<your_playbook>.yaml`
3. Validate:

```bash
pip install -e ".[dev]"
export PYTHONPATH=packages/core
fcc --local run charterhub/playbooks/community/your_playbook.yaml
```

4. Open a PR with:
   - Playbook purpose (1 paragraph)
   - Expected token budget
   - Example workload string

## Charterfile minimum schema

```yaml
playbook_name: "My Workflow"
version: "1.0.0"
global_cfo_ceiling: 5000
roster_requisition:
  - role: "Worker"
    capabilities: ["general"]
flow_units:
  - id: "U1_Step"
    description: "What this unit does"
    assigned_role: "Worker"
    expected_tokens: 500
    expected_latency_ms: 200.0
    schema:
      result: "string"
```

Rejected: missing schemas, unbounded ceilings without rationale, non-YAML formats.
