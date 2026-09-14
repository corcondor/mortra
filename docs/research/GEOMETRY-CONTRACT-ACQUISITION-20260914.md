# Acquired geometric morphisms with exact contracts

## Verdict

Recommendation 1 is implemented for midpoint and perpendicular foot. The final
fixed-code run acquires three morphisms from five fresh successful construction
search histories, derives their contracts, registers them in the shared typed
planner and uses an acquired morphism in two held-out construction proofs.
**The requested positive causal-ablation criterion is NOT met in the final run.**
Do not report this as a new geometry algorithm, improved geometry capability, or
completion of all scientific success conditions.

## Executable route

`scripts/run_theory_formation.py` selects the `geometry/contract_acquisition`
adapter. It uses `search_action_domain` -> `synthesize_typed_plan` and the existing
`ConstructionFamily` / `enumerate_typed_candidates` interface. Coordinates and
relational equations come from the existing JGEX exact bridge. No external
geometry prover is invoked. Newclid is imported for the bridge's schema types.

Training inputs contain polynomial conditions on an unknown output point, not
construction programs. The following is a rendering of recorded data, not an
input witness. Here `m` denotes the midpoint constructor.

```text
initial actions: midpoint, foot
  |
  v
normal search solves 5/5 training construction specifications
  |
  v
existing anti-unification of repeated, shared proof sub-DAGs
  |
  v
H0(p,a,b) = m(p,m(a,b))      geom.a0247196c81e93c6fd89
H1(p,a)   = m(p,m(p,a))      geom.0f5663e398d89048703c
H2(q,p,a,b) = m(q,foot(p,a,b))  geom.b68ba801870de5688a1b
  |
  v
derive P, rational witnesses, C, Q and exact transfer certificates
  |
  v
register all 3 in the ordinary typed candidate interface
  |
  v
unseen-01: construct v2=m(a,b), then choose H0(a,b,v2)
  |
  v
exactly prove 8*u=5*a+3*b; independent primitive replay passes
  |
  v
disable H0: another acquired construction still solves the task
positive causal improvement: NOT established
```

The final 4-task evaluation is a small, developer-authored **construction
specification** benchmark, not an olympiad theorem benchmark or autonomous
problem-generation experiment. All tasks were fixed before the first training
run; none contains a supplied H, intermediate point, answer program or lemma.
The two solved evaluation tasks are variants of one dyadic division family.
Both projection tasks remain unsolved at the candidate budget. After observing
these results, these tasks must be treated as regression data for further work.

## Contract scope

Coefficients are rational; input coordinates range over arbitrary real values
satisfying P. Inputs have no additional polynomial equality assumptions. Only
single-valued rational midpoint/foot constructions are supported. Orthogonality
means a zero vector dot product; it does not imply either vector is nonzero.

For H2 the automatically derived P is
`(f2x-f3x)^2 + (f2y-f3y)^2 != 0`. The foot's local point is on the axis and its
displacement from the projected point is orthogonal to that axis; the output is
the midpoint of this foot and the first parameter. H0 and H1 are total and have
P=true. Their local auxiliary points are existentially bound and fresh.

`geometry_contracts.certify_body` substitutes earlier witnesses into each
primitive guard and coefficient determinant. It preserves factors needed for
denominators even when a final coordinate cancels them. Each relational block is
linear in its new point, with nonzero 2x2 determinant under P. Rational witness
substitution proves existence. Triangular uniqueness extends the witness's Q to
all C-models. Geometry/polynomial transfer is checked for each declared predicate;
the midpoint sum-of-squares equivalence specifically relies on the real domain.

Q currently contains compositional primitive guarantees. It is not an additional
discovered incidence theorem or an eliminated input/output relation. P is sound
and sufficient, not claimed weakest. Unknown guards are refused conservatively.
This is exact arithmetic replay, not a proof-assistant kernel formalization.

## Final local experiment: v3

Base HEAD: `ed87f0ea67c921fbf686d47074762150507e418a`, Windows, Python 3.12.10.
This was a dirty development checkout; `input.json` seals source-file contents.
It is not evidence of an earlier Cloud run. `environment.json` records packages.
Plan digest: `199c9c28f28b874b2d342bb23877b4b29aeb982425c66366bc9ebd5d1d39279c`.
Candidate seed=17, PYTHONHASHSEED=0, 120 states (119 candidate attempts),
360 expanded primitive-equivalent operations, 12 candidates/family/state.
The 120-second time limit is checked between exact operations, not a hard
interrupt of a symbolic operation. Registration, proof checks, rejected attempts
and symbolic execution are included in wall time; independent replay is separate.

| Condition | Solved | Attempts | Primitive-equivalent attempts | Wall seconds | Contract check seconds |
|---|---:|---:|---:|---:|---:|
| Primitive only | 2/4 | 268 | 268 | 27.904 | 0.386 |
| Plain syntactic macro | 2/4 | 304 | 516 | 21.817 | 0.354 |
| Existing compression learner | 2/4 | 268 | 268 | 22.556 | 0.352 |
| Contract-bearing morphism | 2/4 | 304 | 516 | 28.959 | 0.594 |
| Contract-bearing, H0 disabled | 2/4 | 298 | 471 | 29.056 | 0.644 |

All submitted proofs passed independent replay (15/15 across training and all
comparison conditions); there were zero false proofs in those submissions.
Unsolved cases are not counted as verified answers. Acquisition took 1.362 seconds,
including 1.155 seconds of contract certification. The contract condition made
212 acquired-morphism calls: 125 accepted, 87 rejected, and two on final proof
dependency paths. Registration recertification took 2.319 seconds and 120 exact
identity checks over the four tasks. Goal checks numbered 1,966 versus 1,416 for
primitive-only. Independent result replay took 0.259 seconds in the contract
condition. Raw per-task records retain additional execution and enumeration costs.

Primitive-equivalent counts expand the requested body even when an attempt is
rejected early; actual primitive executions and certified witness evaluations
are separate counters. They are not hardware instruction counts. Wall-time
differences are single-run measurements with shared in-process symbolic caches,
not a statistically established speedup. Both macro conditions have identical
candidate counts and accepted/rejected calls. Plain macros check every primitive
guard and do not receive a deliberately unsafe implementation.

The existing description-length learner selects zero definitions with positive
definition-inclusive utility from this small corpus. Contract acquisitions are
selected by the predeclared training source count/compression/hash ordering, not
by evaluation results. All three are retained; no learned selector is claimed.
Removing the most-used H0 changes solved-task attempts from 28 to 28 and from 38
to 32. No solution is lost and no primitive-expanded proof becomes longer.
The other two tasks remain unsolved. Extra grammar branches can hurt search.

## Preserved earlier outcomes

`output/geometry-contract-acquisition-20260914-v1` stopped after training because
the adapter omitted the corpus ID required by the existing learner. It is a
failed run, not retrospectively repaired evidence.

`v2` completed with distinct-point input enumeration. H0 ablation increased
attempts 6->14 and 16->18. This apparent positive effect **did not survive** the
general fix permitting repeated actual arguments. V2 is not the final result.
It also used coarse certificate-step counts and an unfixed Python hash seed.
One interrupted development test and a subsequent fixed-hash rerun are not
autonomous acquisition evidence. Hash ordering changed symbolic runtime sharply;
the reproducible protocol now fixes it explicitly instead of hiding the cost.

## Reproduce

Install `requirements-geometry-contracts.txt` in a fresh Python 3.12 environment.
PowerShell:

```powershell
$env:PYTHONHASHSEED='0'
python -m pytest tests/test_geometry_contracts.py tests/test_theory_geometry.py tests/test_theory_dsl.py tests/test_theory_formation.py worker/backend/test_typed_geometry_stalk.py -q
python scripts/run_theory_formation.py --config configs/theory-geometry-contract-acquisition.json --output output/new-contract-run
python scripts/replay_geometry_contracts.py --run output/new-contract-run --output output/new-contract-replay.json --require-chain
```

The final command deliberately exits 1 when replay is valid but the positive
scientific criterion fails. Omitting `--require-chain` checks correctness alone.
Local tests: 98 passed, 1 skipped. This includes previously uncommitted geometry
regression tests; a clean committed checkout may have a different test count.

The existing **Verify MORTRA Kernels** workflow gains a `geometry-contracts`
dispatch choice. Supply `target_ref` and full `expected_sha`. It runs the existing
q-directed verification, new contract tests, the normal acquisition comparison,
and independent replay with the scientific gate. Artifacts are uploaded even on
failure. This dispatch does not start other research experiments. No main merge,
force push, external prover installation, or broad geometry replacement is needed.

## Remaining scientific limitation

The final implementation preserves and checks the contracts and demonstrates
autonomous H acquisition and later execution. It has not demonstrated a robust
causal search benefit, an advantage over safe macros, or new algorithmic novelty.
NQSynth/Twitch/AUXIL were not rerun here; no assertion of superiority is made.
Do not proceed to another research theme or tune these evaluation tasks to turn
this negative outcome into a positive novelty claim.
