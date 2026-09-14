# Existing native geometry machinery connected to Theory

## Scope

This change connects existing MORTRA components to the normal geometry entry.
It does not invent a new geometry solver, reduce the primitive vocabulary,
or turn the frozen contraction negative result into a success.

The connection uses the existing seven point-construction families. The rule
bank has 83 theorem conclusions, including Newclid's declarative rules and
MORTRA's existing Euclidean relation rules. This is a fixed supplied vocabulary,
not 83 theorems acquired during the run and not a claim of a minimal basis.

## Call path

`scripts/run_theory_formation.py` calls `run_geometry_theory`, which calls the
existing `search_action_domain` / typed planner. `GeometryDomain` now joins:

1. Newclid formulation parsing, construction definitions and numerical drawing.
2. MORTRA `RuleClosureAdapter.propose/verify` for ground rule instances.
3. MORTRA `lower_jgex_to_exact_obligation` for exact certification of proposed
   ground consequences. Rule matching alone does not certify Euclidean truth.
4. MORTRA `synthesize_backward_obligations` and
   `stratify_backward_obligations`, retaining the existing experiment's
   ground/witness selection policy (192 states per rule, 4x result pool,
   witness fraction 0.25).
5. MORTRA `synthesize_contract_candidates`, matching open premises against
   typed construction contracts. Only candidates with discharged construction
   requirements receive contract-based priority. Existing structural candidate
   enumeration remains available; a numerical construction is not a proof.
6. Existing construction execution, exact closure of the resulting diagram,
   and later candidate enumeration using the new state.

The schema adapters were moved out of
`scripts/experiment_newclid_construction_stalk.py` into
`worker/backend/jgex_native_interfaces.py`; both entries import the same
functions. The experimental external-prover path is not imported by Theory.

## Proof boundary

The old acceptance path required an independent proof of the original problem
even when auxiliary construction was needed. A cached original failure could
therefore prevent every augmented proof from being accepted.

Original and augmented proofs are still tried. If only the augmented proof
passes, an explicit conservative-extension check is required. It reuses the
existing coordinate elaborator and exact polynomial identity replay, and
requires unchanged source clauses, goal, old coordinates, free variables,
normalization scope, and constraints. Added witnesses must be rational over
the original variables and must not require new nonzero factors. Unsupported
extensions are refused. This is a sufficient restricted test, not a general
geometric existence theorem. It does not prove that auxiliary search improves
this backend on any particular cohort.

## Evidence

Unit fixtures cover shared helper use, certified-fact consumption, preservation
of open witness branches, actual contract-candidate execution, cache behavior,
and refusal of changed goals, free variables, nonrational witnesses and extra
regularity requirements. Artificial fixtures are not autonomous-run evidence.

Normal runs use the existing eight-task cohort with unchanged statements,
selection keys, seed and budgets. This cohort has already been inspected and
is regression/connection evidence, not a newly unseen benchmark. No missing
held-out configuration is fabricated. The pre-existing workflow reference to
the nonexistent `theory-geometry-heldout.json` is replaced by the existing
development normal run and explicitly carries no generalization claim.

Events distinguish rule proposals, exact relation certificates, backward
obligations, which certified facts matched those obligations, candidate plan
certificates, selected actions and resulting child states. A fact appearing
in an obligation is evidence of consumption, not proof that it caused a
solution improvement. The verifier reports those connection edges separately
from its unchanged stricter auxiliary-solution criterion.

## Reproduction

Use Python 3.12.10 and a fresh environment without Yuclid:

```sh
python -m pip install -r requirements-geometry.txt
python -m pip check
python -m pytest tests/test_theory_geometry.py tests/test_theory_dsl.py \
  worker/backend/test_geometry_proof_hypergraph.py \
  worker/backend/test_geometry_proof_hypergraph_index.py \
  worker/backend/test_symbolic_sheaf_coordination.py \
  worker/backend/test_typed_construction_contracts.py \
  worker/backend/test_typed_geometry_stalk.py \
  worker/backend/test_typed_candidate_alignment.py -q
python scripts/verify_theory_geometry.py \
  --plan configs/theory-geometry-cohort.json --require-no-yuclid \
  --output output/native-geometry-cohort
python scripts/run_theory_formation.py \
  --config configs/theory-geometry-dev.json --output output/native-geometry-dev
```

Set `PYTHONHASHSEED=0`. Each output directory must be new. No input is modified
during a run. The existing `Verify MORTRA Kernels` workflow, dispatched with
`verification_suite=geometry`, verifies the exact target SHA, installs formal
dependencies, performs these checks, and also reproduces q-directed tests,
normal acquisition, stored reuse and refusal. Artifacts retain failures.

`requirements-geometry-external.txt` keeps the optional comparison dependency
separate. Its presence in the repository does not enable it in the native job.

The first local attempt (`geometry-native-connected-20260914-v1`) stopped at
the environment guard because the old development environment contained
`py_yuclid`. It is retained as a refusal, not a completed geometry run.

The first Actions run, `34836669023`, tested code
`7ee2326070f099a86873cff3326cb93eb8126fa2`. All 103 focused tests passed (one
external-comparison skip). The normal cohort proved 4/8 tasks at the root and
exercised five contract-selected constructions across two parent states.
One task stopped on SymPy `CoercionFailed` when a QQ polynomial operation
encountered `I`. That failed run is retained. The adapter now records
`CoercionFailed` and `PolynomialError` as unsupported certificate obligations,
never as proofs, so other candidates can still be checked. This is a domain
boundary refusal, not support for complex-coefficient geometry.
