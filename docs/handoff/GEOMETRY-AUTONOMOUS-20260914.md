# Geometry autonomous adapter

Starting point: `c474b659a0cdc7c50effbaef8f5c72f763a75aa9`, clean
`codex/theory-formation-20260913`, repository `corcondor/mortra`.
This work stops basis optimization. It does not repeat continuous-feedback or
DSL-growth studies as the research objective.

## Executable asset audit

| Asset | Current status and use |
| --- | --- |
| `theory_formation.Domain` | Initially only differential ring, fold frames and finite tables. No geometry state/action connection. |
| `runtime_typed_planner` | Existing typed composition, fair application scheduling, dependency certificates. Extended with lazy alternative applications on the same input facts. |
| `worker/backend/typed_geometry_stalk.py` | Executable, general point-construction grammar with structural ranking. Reused seven default families unchanged. |
| `scripts/experiment_newclid_construction_stalk.py` | Existing separate experiment, not the current Theory entry. Its reusable grammar and Newclid construction interface are used, not its problem-specific experiments. |
| `geometry_proof_hypergraph.py` | Executable relation/rule matching code. Not a replacement for the integrated Newclid inference engine. |
| `jgex_exact_constraint_bridge.py` | Executable polynomial lowering and exact quotient replay. Reused; affine/structural local-lemma shortcuts are disabled in this adapter. |
| `newclid_sympy_ar_compat.py` | Existing fixes for constant-length enumeration and variadic inequality predicates. Reused. |
| `yuclid_native_verifier.py` | Reused by the native adapter revision, using declared `py-yuclid==3.0.0`. |
| `euclidean_geometry_runtime.py` | Has specialized orthocenter/reflection proof code. Not used as a target-specific fallback. |
| `generated_construction_action.py` | Canonicalizes construction DAGs. Its names/certificates alone are not learned geometry procedures. |
| AGENTS traceback discovery/replay scripts | Referenced historical entry points are absent in this checkout. Their described achievements are not fresh evidence. |
| Acquired geometry morphisms | No archive with executable geometry contracts, acquisition provenance and transferable proof scope was found on the audited path. A learned-morphism advantage or causal ablation cannot be claimed. |

Newclid is an integrated external symbolic geometry engine, not an LLM. The
same immutable upstream revision already used by the repository's symbolic
geometry workflows is declared in `requirements-geometry.txt`. No neural
proposer or network API participates in solving.

## Boundary and normal entry

`scripts/run_theory_formation.py` dispatches the formal geometry configuration
to `GeometryDomain`. `search_action_domain` connects that adapter to the same
`synthesize_typed_plan` already used by typed DSL synthesis. The adapter does
not own an independent search queue or prescribe a route.

Each existing construction exposes its input/output point types, requirements,
definition clauses, produced relations and certificate obligation. Line and
circle incidence views retain point arguments; they are not extra assumptions.
The generic planner receives state-to-state typed actions. Geometry-specific
parsing, numerical construction, symbolic deduction and exact certification
remain in the adapter and existing backends.

Candidate enumeration records the actual input points and closure relations.
Application records the parent and child state hashes, new assumptions, new
relations and the entire child state. Later enumeration reads that child, not
the original diagram or an identifier-only proxy.

## Verification scope

The initial symbolic closure uses all executable rules in the pinned Newclid
Python interface, up to the declared step bound. Its angle-equation and
length-equation predicate constructors are explicitly unimplemented upstream;
rules requiring them are recorded as unsupported, not silently proved. Thus
exhaustion means exhaustion of this executable rule set, not all geometry.

The pinned Python mapper also had interface failures for constants, inadmissible
predicate instances and triangle relation types. A compatibility adapter keeps
literals literal, rejects invalid instances, and preserves triangle types under
permutation. It adds no theorem and checks every instantiated premise.
Its line-merge evidence lacked the hash contract already implemented for
circle-merge evidence; the adapter supplies that same predicate-based hash.
The optional SymPy AR deductor is disabled because its generated deductions
sometimes lack recoverable premises. This is a restricted symbolic-closure
baseline, not a claim to reproduce full native Yuclid/DDAR performance.

Numerical coordinates only select valid constructions and reject degeneracy.
A solved flag is insufficient. Both the original and augmented statements must
pass the existing exact polynomial verifier. Quotients, remainders, coordinate
normalization, nonzero assumptions and construction blocks are saved. The
claim is on that declared regular locus, not degenerate or unsupported cases.
The original theorem is independently certified so adding an auxiliary cannot
silently restrict the original claim. The whole path is regenerated, including
candidate eligibility, construction, closure and exact certificates.

Independent algebraic verification can be stronger than the selected symbolic
closure. An auxiliary-only success means the selected symbolic closure needed
it, not that every possible prover requires that auxiliary.

## Frozen evaluation

`configs/theory-geometry-cohort.json` contains eight source-formalized tasks.
It was selected before execution by a fixed hash ordering, limited only by
initial size and supported construction syntax. Supplied auxiliaries were
removed. No witness, preferred constructor, expected route or answer is input.
The cohort is unseen to this adapter's development before its first execution.
Global historical non-exposure in the large MORTRA repository is not established.
After failures are inspected it is a regression cohort, not a new held-out set.

```bash
python -m pip install -r requirements-geometry.txt
python -m pytest tests/test_theory_geometry.py tests/test_theory_dsl.py tests/test_theory_formation.py -q
python scripts/verify_theory_geometry.py --plan configs/theory-geometry-cohort.json --output build/geometry-verification
```

Each task invokes the normal Theory entry in a bounded subprocess. Fixed
settings: seed 917401, depth 2, 64 charged applications, 8 candidates per
construction family/state, 1000 closure steps/state, 180 seconds/task including
imports and replay. Timeouts retain partial event streams. Dependency versions,
source hashes, exact commands and outputs are stored. Failure is not success.

The existing `Verify MORTRA Kernels` workflow accepts `geometry` dispatch and
runs geometry on research-branch pushes. Basis measurement remains explicit
dispatch only. Original q-directed CI remains intact.

## Preserved development failures

Local `geometry-dev-v1`: initial orthocenter closure proved and exact replay
passed without auxiliaries. This is development, not the requested auxiliary
search success.

Local `geometry-cohort-v1`: all eight aborted; initial failures were incorrectly
classified as formalization failures because initialization also performed
deduction. Tracebacks identify runtime matcher failures. Classification was
corrected separately; these old outputs were not overwritten.

Local `geometry-cohort-v2`: all eight aborted on the pinned upstream's missing
length-equation predicate constructor. These remain failed solver runs. No
manual auxiliary or mathematical answer was added to either run.

Local `geometry-cohort-v3`: first task failed when the optional SymPy AR could
not recover premises. The outer Windows harness also used the locale encoding
to read UTF-8 and aborted; the encoding boundary was corrected.

Local `geometry-cohort-v4`: repeated unhashable line-merge evidence failures.
The run was stopped before further development. Its partial results and stop
record are retained. Local regression after correction: 50 tests passed
(`test_theory_geometry`, `test_theory_dsl`, `test_theory_formation`).

Result tables and shared Actions evidence are recorded separately after the
fixed implementation has been tested. No geometry learned-morphism transfer,
natural-language lowering or second-domain capability is established by this
document alone.

## Native deduction revision

The fixed Python-DD local run `geometry-cohort-v5` completed with 0/8 proved,
8 timeouts at 180 seconds each, and unchanged source hashes. Its completed
construction events remain available; no timeout is treated as a proof.
Shared baseline run: Actions `34809523377`, source
`5ba39168722e6b9babbfbaf548a160dba32b4cda`.

The next revision connects the **existing** `yuclid_native_verifier.verify_problem`
to the same adapter/planner. It changes neither the eight statements nor the
seven construction families. The `standard` existing AR profile disables sine
reasoning and gives each native closure a 10-second timeout. The original
180-second whole-task bound remains. The Python-DD backend remains an explicit
option and its regression tests remain intact. No new deduction theorem is added.

Native proofs and closure assertions are saved in the state, together with the
native executable hash and input hash. Native `solved` is only a candidate proof:
the unchanged independent polynomial certificates and full route replay still
gate acceptance. Native saturation, not a manually shortened rule list, defines
initial closure exhaustion in this revision.

The PyPI Windows wheel for `py-yuclid==3.0.0` starts with missing Boost DLLs on
the development host (exit `3221225781`). Its dependency installation is not
reported as a successful native run. The native regression test intentionally
fails on that host rather than hiding the missing dependency. The authoritative
native reproduction uses the declared Linux wheel in GitHub Actions. A separate
attempt to duplicate the complete Windows environment was stopped during
dependency installation; it contributed no research result.

Timeout summaries now include completed/rejected construction counts, newly
derived relations (with multiplicity), path depth and the number of actual child
states read by later enumeration. An incomplete final event is excluded, not
reconstructed as a completed application.
