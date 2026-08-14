# SPEC — Structured QFS Reduce (v3.1.0)

## Outcomes

1. Bags are `fcc_component` / `source_id` groups — not Leiden.
2. Map emits per-bag partials + helpfulness 0–100. Score 0 drops.
3. Reduce concatenates selected map sentences only.
4. Rhythm fails `reduce_invented` if synthesis adds a clause.
5. `claimed_graphrag` still requires HTTP.

## Out

Leiden-as-GraphRAG. Live LLM reduce without a key.
