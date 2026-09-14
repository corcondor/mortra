# Reproduce certified geometric state contraction

## Fixed code and scope

- Repository: `corcondor/mortra`.
- Research branch: `codex/geometry-morphism-contraction-20260914`.
- Experiment code: `adf05ea8e3437d254ec89bd9805636b6e39076a1`.
- Python: 3.12.10. Set `PYTHONHASHSEED=0` before starting Python.
- Exact fragment: midpoint and perpendicular foot, rational coefficients,
  arbitrary real input coordinates satisfying the certified sufficient guards.
- No new external solver. The existing pinned Newclid package supplies schema
  compatibility to the bridge; it is not the prover for this experiment.

Use a clean checkout of the exact code commit. Do not substitute the original
four-task artifact for this new run. Those tasks are regression only and their
original negative result remains frozen at commit
`39ce48368639f3c508bdd611b06339aad893f342`, Actions `34818657880`.

The new plan is `configs/theory-geometry-morphism-contraction.json`. Its
canonical-JSON digest is
`2ccd039890159983d3a8fde478ccdf2090eb2919e9cdb060a1c427956d98010a`.
The evaluator witnesses are separate from the solver input. Their canonical
digest is `63bda7df8ca7c522e9c40d3fe619035ee3d3180f6d3d92e7fba1a3dda72f60f7`.
The generator protocol, seeds, task specification and budgets were committed
before the first mechanism evaluation. Do not regenerate or tune them to change
the scientific verdict.

The generator's frozen `rejection` prose overstates one check: initial-point
outputs are not actually rejected. This discrepancy was recorded before the
first evaluation in `reports/geometry-contraction-cohort-development.md`.
Keep the cohort unchanged. Requested witness depth is not minimal solution
depth or a measurement of problem difficulty.

## Commands

Create and activate a Python 3.12.10 environment using the platform's normal
venv commands. Install only the declared dependency closure:

```bash
python -m pip install -r requirements-geometry-contracts.txt
python -m pip check
python -m pip freeze
git rev-parse HEAD
git status --short
export PYTHONHASHSEED=0
python -m pytest tests/test_geometry_contracts.py tests/test_geometry_contraction.py tests/test_theory_geometry.py tests/test_theory_dsl.py tests/test_theory_formation.py worker/backend/test_typed_geometry_stalk.py -q --junitxml=contraction-tests.xml
python scripts/run_theory_formation.py --config configs/theory-geometry-morphism-contraction.json --output output/geometry-contraction-fresh
python scripts/replay_geometry_contraction.py --run output/geometry-contraction-fresh --output contraction-replay.json --require-scientific-pass
```

In PowerShell, use `$env:PYTHONHASHSEED='0'` instead of `export`. Both the normal
entry and replay reject an existing output destination; choose a fresh one.

The normal entry runs training, acquisition, summary compilation, five fixed
evaluation conditions, used-morphism ablation, and separate historical
regression. It does not accept mid-run candidate definitions. The evaluator
witness file is not loaded by this entry.

The five conditions are primitive-only; exposed syntactic macro; exposed
certified morphism; summarized certified morphism with guard filtering and
effect ordering; and summarized morphism without that filtering/ordering.
Refinement is a paid planner alternative in both summarized conditions.

Normal-entry exit zero means execution completed and the source seal did not
change. It does not mean the scientific hypothesis passed. Replay without
`--require-scientific-pass` checks correctness even for a negative result.
With the flag, a scientifically negative but correctly replayed result exits 1.
Preserve that failure; do not weaken the gate.

## Shared Actions

The existing `worker-ci.yml` workflow is extended, not replaced. Dispatch the
exact commit:

```bash
gh workflow run worker-ci.yml --repo corcondor/mortra --ref codex/geometry-morphism-contraction-20260914 -f verification_suite=geometry-contraction -f target_ref=adf05ea8e3437d254ec89bd9805636b6e39076a1 -f expected_sha=adf05ea8e3437d254ec89bd9805636b6e39076a1
```

This also executes the existing q-directed 351-test reproduction, acquisition,
stored reuse, and legality-refusal checks. Its top-level `verification.json`
belongs to that regression suite. The new hypothesis verdict is in
`geometry-contraction/verification.json`, and independent checks are in
`contraction-replay.json`. Do not confuse the two verdicts.

Artifacts are uploaded on success or failure. They include dependencies,
environment, commands, exact SHA, test logs, frozen plan, acquired library,
per-task results, all emitted events, comparisons, regression results and replay.

## Reading costs

- Acquisition, summary compilation, registration/replay, candidate generation,
  precondition checking, application, goal proving and independent replay have
  separate records. Some named timings are inclusive; do not sum overlapping
  timers to obtain total wall time.
- Primitive-equivalent operation charges include full macro bodies. Witness
  evaluations and actual primitive executions are also recorded separately.
- Object counts are point objects, not coordinate dimensions or memory bytes.
  The mean weights states actually checked for the goal; it is not an average
  over all mathematically possible states.
- The existing planner's `states_explored` includes attempted expansions plus
  its initial state. `states_retained` counts retained facts. On a soft-wall or
  operation-budget exception these counts may be null. Do not interpret the
  aggregate sum of available counts as a complete count in that case.
- `expanded_primitive_proof_depth` currently records the number of primitive
  DAG nodes, not longest-path depth. `macro_proof_length` counts relevant
  executed actions. Use these meanings when reporting them.
- Wall limits are checked between exact operations, not preemptively. Wall time
  and the number of attempts before timeout can differ across machines.
- A smaller archive, object count or proof expression is not alone evidence
  of reduced later search. Inspect the paired task traces and ablation.
