# Writing Contracts

"Done" is a locked box. Every box starts as **NO**.

## Shape

`contracts/feature_list.json`:

```json
{
  "version": 1,
  "autonomy": "off",
  "features": [
    {
      "id": "kebab-id",
      "title": "One human sentence of the outcome",
      "passes": false,
      "evidence": [],
      "notes": "optional"
    }
  ]
}
```

JSON, not markdown, for the scoreboard. Models edit markdown too freely.

If the file is missing: `node scripts/harness/init.mjs`.

## How to write a row

- One outcome you can check without being the author.
- `id` is stable. Do not rename mid-flight.
- `passes` is always `false` at birth.
- Prefer 3–12 rows over 80. Split later if a row is a project.

## How a row becomes YES

Not by editing JSON. Not by saying it works.

```sh
node scripts/harness/verify-gate.mjs pass --id kebab-id --evidence screenshots/foo.png
```

Evidence must exist on disk and live under `screenshots/`, `gates/`, or `artifacts/`.

To record a reject:

```sh
node scripts/harness/verify-gate.mjs fail --id kebab-id --reason "why"
```

```sh
node scripts/harness/verify-gate.mjs audit
```

must stay clean. A hand-toggled `true` is a failed audit.

## When not to

A one-file typo does not need a contract. Use `complexity-router`. A contract with one row that is the entire product is a novel — split it.
