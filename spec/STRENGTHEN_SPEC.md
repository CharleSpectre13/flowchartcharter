# SPEC — Strengthen weak spots (v3.3.0)

Research-backed, no fake key, no Leiden.

1. Extractor: more relation patterns + stopword reject. Still heuristic.
2. KG delta persist when harness persist is on.
3. Sandbox: deny shell/eval/file_write names; `policy_not_kernel=true`.
4. Stranger receipt: hash-chained, independently verifiable.
5. QFS stamps `reduce_mode=extractive` unless a live key is actually used.

## Out

Live LLM extract without a key. Leiden-as-GraphRAG. Claiming kernel isolation.
