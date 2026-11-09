# Runbook: Demo-/Testdaten (Seeder)

Deterministic, clearly separable demo data in the part class `TEST`.
The workflow has no "test" status (only draft/review/released/obsolete), so the
separator is the class + the `TEST ` name prefix — find records via
`GET /api/v1/parts?class_code=TEST` or the search `?query=TEST`, and in the UI
via the class filter / search. SKU = part number (assigned by the number range,
never manually).

## Local (backend venv)

```bash
cd backend
python -m app.services.testdata --count 200                     # default demo set
python -m app.services.testdata --count 2000 --levels 3 --reset # big multi-level demo
```

## Docker Compose (running stack)

```bash
docker compose exec api python -m app.services.testdata --count 2000 --levels 3 --reset
```

## Options

| Option | Default | Meaning |
|--------|---------|---------|
| `--count N` | 200 | total records (parts + assemblies) |
| `--levels N` | 1 | BOM depth; N>1 lets assemblies contain lower-level assemblies (where-used depth > 1) |
| `--seed N` | 42 | RNG seed — same seed = same data (names/attributes), reproducible demos |
| `--reset` | off | delete existing TEST-class data first (BOM lines, ECO links, revisions, parts; audit log stays append-only) |

## What gets created

- Part class `TEST` with typed attributes `saison` (enum), `farbe`, `preis`
  (EUR), `groesse` (enum XS–XL on parts)
- ~80% single parts (`P-...`), ~20% assemblies (`ASM-...`), each with 2–5 BOM
  lines (unit `Stk`, qty 1–4)
- Every write lands in the audit log (reason `Testdatensatz`)

## Scaling

`--count 1000 --levels 3` ≈ 800 parts + 200 assemblies + ~700 BOM lines, seeds
in seconds. Large counts take a little longer (one commit per record).

## Cleanup

```bash
python -m app.services.testdata --reset        # removes only class TEST
# or in compose:
docker compose exec api python -m app.services.testdata --reset
```
