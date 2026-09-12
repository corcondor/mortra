# Reproduce the q-directed handoff

This packages the existing implementation and results for branch
`codex/q-directed-closure-20260913`. No new mathematical feature is added during
packaging. The parent is `6eedcb7888c3f164933115b94392a557e4b78dca`.
The historical AGENTS.md, THEORY.md, MORTRA-20260912.md and NEXT.md are unchanged.
See [the implementation report](Q-DIRECTED-20260913.md) for the code changes,
certificate scope and measured costs.

## Environment and test command

Run from the repository root. The development runtime was Python 3.12.10,
SymPy 1.14.0 and python-flint 0.9.0 on Windows. Dependencies are listed in
`requirements.txt`. Install those dependencies in the chosen Python environment
if needed. A shared dependency installation is not a shared source checkout.

The following command selects all 17 related modules, totaling 351 tests. It
does not claim to run every test in the repository.

```powershell
python -m unittest scripts.test_abstraction_correspondence scripts.test_action_observable_basis scripts.test_holonomic_route_discovery scripts.test_holonomic_fast_coefficients scripts.test_holonomic_algebraic_discovery scripts.test_holonomic_ode_source scripts.test_library_compression scripts.test_representation_progress scripts.test_iteration_law scripts.test_acquisition_session scripts.test_expand_for_execution scripts.test_call_candidate_dedup scripts.test_fold_observable scripts.test_representation_evaluation scripts.test_representation_policy scripts.test_quotient_counting scripts.test_q_directed_representation
```

The first 16 modules are the handoff's 335-test baseline. The final module adds
16 regression tests. Test fixtures and mock assertions are development tests,
not autonomous discoveries.

## Packaged historical evidence

All paths below are relative to the repository root. The recorded absolute
paths inside historical seals and logs are provenance, not dependencies for
the commands below. Historical source seals remain unchanged even where later
diagnostic changes produced a different source hash.

- `artifacts/research/q-directed-handoff-20260913/test-logs/` contains byte-checked
  copies of all six `mortra-handoff-*` logs previously stored outside the repo.
  The failed development test log is retained as a failed run. Later passing
  runs do not overwrite or reclassify it.
- `artifacts/research/q-directed-handoff-20260913/normal-comparison-v1/plan.json`
  contains the 19 fixed commands and pre-run source hashes.
- The adjacent `results.json` contains costs, answers, stops and reuse records.
  The 19 sibling `.log` files are explicitly included despite the general Git
  ignore rule for logs. Per-run subdirectories contain ledgers, traces and seals.
- `baseline-smoke/`, `post-clarification-normal-v2/` and
  `final-reuse-display-v3/` under the same artifact root retain their separate
  source versions and results.

### Comparison configuration

All 19 runs use degree 1, at most 2 terms, certificate depth 3, probe length 3,
and independent enumeration at lengths 3 and 5. The enumeration route uses
coefficients +1 and -1 and offers 144 candidates. These grammar settings do not
execute in the q-directed route, which starts from the task evaluation.

A (existing exact), B (enumeration) and C (q-directed) each run four tasks:
`axis1`, `c1-plus-c2`, `axis1-from-AG`, `axis1-collision-free`. They use fresh
processes and stores, answer length 6 and a later reuse attempt at length 9.
D runs the same four tasks with reuse only, using C's saved store. The sum task
uses C's sum store; the other three use C's original-start `axis1` store.
Three D-long runs use the ordinary q-directed entry with those stores, answer
length 12 and later reuse at length 14. The collision task is excluded from
D-long. Thus the comparison has 12 + 4 + 3 = 19 runs, with 17 answers and two
expected stops. Exit zero alone is not evidence of an answered task.

To repeat the entire comparison, use a new output directory:

```powershell
python scripts/compare_q_directed_routes.py --output ../q-directed-comparison-fresh
```

## Post-commit clean-checkout protocol

Create a separate worktree from the full commit SHA, not by copying the dirty
development directory. Keep validation outputs outside that worktree. Check
HEAD, source import locations and `git status --porcelain --untracked-files=all`
before and after. Clear a custom PYTHONPATH, if present, for this verification.
Run the complete test command above before these normal-entry commands.

Choose a new output root. The CLI refuses to overwrite an existing run.

```powershell
$out = '../q-directed-clean-validation-fresh'

# Acquire from the supplied task evaluation, check small n, then reload and reuse.
python scripts/run_representation_tasks.py --output "$out/normal" --task axis1 --route q-directed --degree 1 --max-terms 2 --certificate-depth 3 --probe-length 3 --verify 3 5 --answer 6 --reuse-length 9

# A separate process, different start, using the just-saved representation.
python scripts/run_representation_tasks.py --output "$out/reuse-fresh" --task axis1-from-AG --route reuse --ledger "$out/normal/ledger.json" --verify 3 5 --answer 12 --reuse-length 14

# Reuse the historical representation shipped IN this clean checkout.
$stored = 'artifacts/research/q-directed-handoff-20260913/normal-comparison-v1/C-axis1/ledger.json'
python scripts/run_representation_tasks.py --output "$out/reuse-committed" --task axis1-from-AG --route q-directed --ledger $stored --verify 3 5 --answer 12 --reuse-length 14

# Reject the insufficient observation for collision legality; use exact fallback.
python scripts/run_representation_tasks.py --output "$out/refusal" --task axis1-collision-free --route q-directed --certificate-depth 3 --probe-length 3 --verify 3 5 --answer 6 --reuse-length 9

# Without acquisition/fallback, the incompatible stored certificate must stop.
python scripts/run_representation_tasks.py --output "$out/refusal-reuse" --task axis1-collision-free --route reuse --ledger "$out/normal/ledger.json" --verify 3 5 --answer 6 --reuse-length 9
```

Inspect traces, not just exit codes. Require independent maximum, maximizing-word
count and full observation-distribution agreement at lengths 3 and 5. Successful
reuse must offer zero candidates, record `acquired_again: false`, and report zero
acquisition and certification calls. Check the stored all-finite-words scope and
initial-state domain before accepting length 12 or 14 results.

The refusal run must record the legality counterexample before concrete
fallback; its concrete answer is not a collision certificate for the reduced
space. The reuse-only negative control must stop without answering or acquiring.
Every completed result seal must report unchanged sources. Raw executable-file
fingerprints are conservative version checks: a changed version or file encoding
may reject an old store and must not be silently waived to force reuse.

Post-commit verification logs must identify the exact commit tested. They are
kept outside that commit; amending a commit after testing would change the SHA
and no longer be a test of the amended commit. Do not merge main or push as
part of this verification.
