# Reproducing the MORTRA reversible-synthesis geometry result

This document reproduces the no-LLM exact-geometry portfolio reported in
`data/jgex-exact-portfolio-expanded19-2026-08-16.json`.

## Pinned inputs

- MORTRA repository branch: `research/reversible-synthesis`
- Newclid: `ac6550732a950564cf7614d605b5bf1eadd29701`
- GCLC: `8f73a5d7e6c373f6210c4b293231dcc0dcc07a28`
- Python: 3.12.10
- SymPy: 1.14.0
- Dataset: Newclid `newclid/problems_datasets/imo.txt`
- Yuclid baseline: `data/yuclid-imo-ag-30-all-ar-2026-08-15.json`

The dataset auxiliary clauses are removed before exact lowering. The exact
backend contains no problem-name solver branches and calls no external LLM.

## Environment

PowerShell example:

```powershell
git clone https://github.com/Newclid/Newclid.git ../Newclid
git -C ../Newclid checkout ac6550732a950564cf7614d605b5bf1eadd29701
uv sync --project ../Newclid --group dev

$python = Resolve-Path ../Newclid/.venv/Scripts/python.exe
$dataset = Resolve-Path ../Newclid/newclid/problems_datasets/imo.txt
$env:PYTHONPATH = (Get-Location).Path
```

On Linux or macOS, use `../Newclid/.venv/bin/python` instead.

## Tests

```powershell
& $python -m pytest `
  worker/backend/test_jgex_legacy_normalizer.py `
  worker/backend/test_jgex_exact_constraint_bridge.py -q
```

Expected: `20 passed`.

## Frozen 60-second run

```powershell
& $python scripts/experiment_jgex_exact_unsolved_set.py `
  --dataset $dataset `
  --baseline data/yuclid-imo-ag-30-all-ar-2026-08-15.json `
  --output reproduced-60s.json `
  --timeout-seconds 60
```

Runtime varies by machine. A timeout means that the process budget was
exhausted, not that the theorem is false.

## Boundary rerun

`2008_p1a` required 65.90 seconds on the reference machine, so rerun it with a
120-second budget:

```powershell
& $python scripts/experiment_jgex_exact_unsolved_set.py `
  --dataset $dataset `
  --baseline data/yuclid-imo-ag-30-all-ar-2026-08-15.json `
  --output reproduced-2008-p1a.json `
  --timeout-seconds 120 `
  --problems 2008_p1a
```

Use `--timeout-seconds 0` for an unbounded deep-research process.

## Merge and verify

```powershell
& $python scripts/merge_jgex_exact_portfolio.py `
  --baseline data/yuclid-imo-ag-30-all-ar-2026-08-15.json `
  --reports reproduced-60s.json reproduced-2008-p1a.json `
  --output reproduced-portfolio.json

& $python scripts/verify_jgex_exact_reproduction.py `
  --expected data/jgex-exact-portfolio-expanded19-2026-08-16.json `
  --actual reproduced-portfolio.json
```

Semantic acceptance requires all four checks to pass:

- portfolio: `20/30`
- proved names: `2008_p1a`, `2009_p2`, `2012_p5`
- exact certificate SHA-256 values match
- acceptance rule remains `exact_replay=true and remainder=0`

Generated timestamps, elapsed seconds, and absolute paths are intentionally
excluded from semantic equality.
