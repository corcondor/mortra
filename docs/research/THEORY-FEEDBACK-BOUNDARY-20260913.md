# Where the Current Feedback Loop Ends

The fold representation branch stopped receiving work at cycle79, not at the
12000-cycle cutoff. Its four successful acquisition slots had already been
consumed by cycle18, although those records span only two distinct invariant
spaces. This is a direct source-level explanation for the absence of further
representation acquisitions in the observed runs. It is not yet an explanation
of the entire held-out capability plateau.

This document is a developer-side, read-only diagnosis of existing Actions
artifacts. It contains no new normal run, no new learner feature and no newly
acquired MORTRA theorem. The rank calculations below must not be counted as
MORTRA's autonomous discoveries or fed back into the frozen runs.

## Authoritative Inputs

- Mathematical source: `14d18a42c3a7c640a7c54c86c36b7238c419df56`.
- Working tree inspected at `c9baa5a2bef764e1d59327d5adb07dc9feee993b`, clean.
- Existing [Actions34733054750](https://github.com/corcondor/mortra/actions/runs/34733054750).
- Existing [artifact10310675896](https://github.com/corcondor/mortra/actions/runs/34733054750/artifacts/10310675896).
- Local artifact root:
  `C:/Users/81808/.openclaw/reports/archive-term-interaction-20260913/actions-34733054750`.
- Audited final states under `capacity-study`:
  `128/theory-fold-frames-learn/K12000/state.json` and
  `256/theory-fold-frames-learn/K12000/state.json`.
- The ordinary run and ablation results remain in
  `docs/research/ARCHIVE-TERM-INTERACTION-RESULTS-20260913.md`.

Historical handoff statuses are not rewritten. The audit concerns the
`run_theory_formation.py` entry, not every subsystem in the repository.

## Three Actual Feedback Paths

`Theory.invent` (theory_formation.py:191) composes scalar or predicate terms from
stored concepts, then rewrites them with certified learned rules. It records
the actual reduced expression and checks its exact semantics. `Theory.settle`
(line282) likewise rewrites both sides before calling `Domain.settle`.
This feedback path is implemented and demonstrably active.

`Theory.acquire` (line311) gives an autonomously selected observable to the
existing common-invariant-space kernel. `Theory.derive` (line339) uses the
resulting matrices and readout to derive a recurrence for repeats of one action.
`Theory.use_procedure` (line398) executes that recurrence at later lengths.
This narrower representation-to-recurrence path is implemented and active.

Neither `invent` nor `settle` reads stored representation bases or matrices.
The equality solver's reuse comes from `rewrite_rules`, not the acquired
spaces. `Domain.compose` (theory_domain.py:133) emits only the declared scalar
and predicate constructors; it does not emit calls to the procedure archive or
new basis-coordinate sensors. `Domain.type_of` (line114) has only scalar and
predicate result types. The procedure records have two fixed kinds:
`certified_reduction` and `certified_scalar_recurrence`.

These facts do not show that finite grammars cannot learn algorithms, nor that
LLMs are required. They show that this entry has no implemented route that
turns an arbitrary acquired procedure into a new callable constructor or
learns a new search-control program. Its five selectable computation kinds
remain `invent`, `settle`, `acquire`, `derive`, and `use` (lines434-490).

## A Bounded-Branch Argument

For an unchanged normal execution let R be the successful representation-record
limit, G the number of declared actions, and U=2 the per-recurrence execution
limit. Assume no external state edits, no budget changes and normal entry only.

1. `actions` offers acquisition only while the number of acquired concept IDs
   is less than R (line458). Records are not removed. Therefore at most R
   successful acquisitions occur; this bound does not count distinct spaces.
2. For each representation, `derive` appends its label to `derived_labels` on
   both success and refusal (lines356 and361). `actions` offers only an absent
   label (line465). Hence at most R*G recurrence attempts occur.
3. Successful recurrence attempts create at most R*G executable recurrences.
   `actions` offers use only while `reuse_count < 2` (line470), and successful
   execution increments the counter. Thus at most U*R*G such executions occur.

Failed closure requests are a separate case: their concepts receive
`closure_refusal` and are not retried automatically. This argument bounds the
successful-representation branch, not every failed attempt or all mathematics.

The fixed plans have R=4 and G=4. The source therefore allows at most4 successful
acquisitions,16 recurrence attempts and32 recurrence executions. In both actual
fold runs two recurrence attempts were refused, leaving14 laws and28 executions.

| Observed event | Last cycle in both capacities |
| --- | ---: |
| Successful representation acquisition |18|
| Refused recurrence attempt |17|
| Successful recurrence derivation |55|
| Execution of a stored recurrence |79|

The decision logs contain no `acquire`, `derive`, or `use` option at any cycle
after79. These computations were not merely offered and starved by another
priority: the current eligibility rules no longer offered them. Later cycles
still perform genuine concept/conjecture/rewrite work. They cannot replenish
this representation branch under the unchanged rules, regardless of a faster
rule index or a larger term/archive limit.

## Slots Versus Mathematical Spaces

The acquired observables and cycles, read from the learner's own records, are:

| Representation | Observable | Acquired cycle | Dimension | Distinct encoded states |
| --- | --- | ---: | ---: | ---: |
| R-b8f032907b167b70 |pull_A(F11)|3|3|6|
| R-41a98d67901bbfc7 |-F11|10|3|6|
| R-e77b5ff053fb6d5a |F11+F11|14|3|6|
| R-f3e6a1a41618b3e6 |F11+F12|18|3|12|

The first three bases have the same rational row space on the declared24-state
model. The fourth is a different3-dimensional space. Together their rows span
a6-dimensional space. Thus three acquired records consume slots for one space.
The records are not necessarily redundant as observable/readout bindings:
sharing a space must preserve each distinct readout and its certificate.

A read-only rational-rank audit examined every nonseed, nonconstant scalar
concept in each final archive. A value vector v has a linear readout from basis
B exactly when rank([B;v])=rank(B). The audit used saved exact value vectors;
no new candidate was supplied to the learner.

| Archive condition | Nonconstant scalar concepts excluding seeds | Outside every individual stored space | Outside the sum of stored spaces |
| --- | ---: | ---: | ---: |
|128|72|57|38|
|256|130|110|74|

The earliest example outside the sum, found by sorting all results by acquisition
cycle and ID, is `C-a07629d7a8d86a2d`: `F11+F13`, born at cycle1. It was already
acquired by MORTRA, not proposed by this audit. The full finite function space
has dimension24, equal to the configured dimension cap. Consequently additional
common-invariant closures are mathematically available in the declared model.
This existence argument is not an executed autonomous acquisition or evidence
that its additional space would improve the held-out score.

Importantly, concatenating the two different encodings distinguishes all24
declared states. Therefore the outside-span counts are NOT a claim of missing
state information under arbitrary decoding. They identify missing *linear*
readouts. Nonlinear decoding may recover such observables from the combined
features. The combination and this decoding observation are developer-side
diagnostics, not a new jointly acquired MORTRA representation.

## Existing Machinery, Not a Blank Repository

`linear_readout` (theory_domain.py:28) already solves exact rational span
membership and verifies the reconstruction. The ordinary domain uses it after
closure acquisition. It is imported but unused in theory_formation.py.
`discover_action_observable_basis` is already the generic closure engine.
Neither needs a replacement solver for this diagnosis.

`runtime_typed_planner.synthesize_typed_plan` (line120) already enumerates typed
compositions of registered executable primitives. `library_compression` already
supports learned definitions, parameterized calls and checked complete expansion
(`expand_for_execution`, line534); `acquisition_session` uses that library in a
different entry. Therefore it would be incorrect to say MORTRA has no typed
planner or cannot extend any vocabulary. The audited `Theory` entry only imports
the library matcher/instantiator, not its abstraction-learning/call-generation
loop or the typed planner. None of those other entry points executed in the
audited long runs. Their existence is not proof of integrated capability here.

Macro expansion alone also does not supply a new mathematical representation or
an improved algorithm. A proposed integration must retain executable semantics,
scope, dependencies and measured downstream effects rather than count names.

## Minimal Next Proposal, Not Implemented

The previous ordered rule-index proposal targets measured matching overhead.
It remains a possible performance change, but cannot reopen a branch which has
no eligible work. This new audit narrows a separate, directly observed boundary.

Before a new solver, language, planner or reward system, the next bounded change
to evaluate is certified space sharing with observable-specific readouts:

- Reuse existing exact span/readout machinery before reacquiring a space.
- Retain all observable definitions and certificates; do not simply delete the
  three same-space records or assume their readouts are identical.
- Count distinct certified action spaces separately from readout bindings.
  Preserve the existing selection order and other budgets.
- Record dependency on the reused closure certificate and exact readout check.
  Match action system, coefficient field, model scope and legality requirements;
  reject mismatches rather than reuse on names or row rank alone.
- Compare actual closure calls, certificate work, whole-run cost, later uses,
  new spaces, proof dependencies and fixed held-out outcomes. Include ablation.
  More available slots or more records alone is not the success criterion.

This requires more than changing a numeric cap or silently changing its unit.
The state contract and counters must explicitly distinguish a space from a
readout binding. It also does not by itself make `Theory.settle` consume stored
spaces, solve a new domain, or synthesize a general procedure. Those remain
separate contracts. No patch or positive counterfactual result is asserted here.

No further capacity sweep was launched. The latest instruction to propose but
not yet implement a new mechanism remains in force.

## Reproduce the Read-Only Checks

From the repository root, with the artifact downloaded at the path above, the
following uses only Python's JSON reader and exact SymPy matrix operations.
It never imports, advances, rewrites or saves a learner state. `root` can point
to another copy of the same immutable artifact.

```python
import json
from pathlib import Path
import sympy as sp

root = Path("C:/Users/81808/.openclaw/reports/archive-term-interaction-20260913/actions-34733054750/capacity-study")
read = lambda p: json.loads(p.read_text(encoding="utf-8"))
verification = read(root / "verification.json")
for capacity, result in verification["domains"]["theory-fold-frames"]["normal_results"].items():
    state = read(root / capacity / result["final_state"])
    variables = sp.symbols("s0:" + str(len(state["exact_models"])))
    spaces = []
    for record in state["representations"].values():
        expressions = [sp.sympify(x) for x in record["basis"]]
        basis = sp.Matrix([[e.coeff(x) for x in variables] for e in expressions])
        assert all(sp.expand(e - sum(a*x for a, x in zip(row, variables))) == 0
                   for e, row in zip(expressions, basis.tolist()))
        spaces.append(basis)
    combined = sp.Matrix.vstack(*spaces)
    combined_rank = combined.rank()
    concepts = [c for c in state["concepts"].values()
                if not c["seed"] and c["type"] == "scalar"
                and len(set(c["values_or_normal_form"])) > 1]
    vectors = [sp.Matrix([[sp.Rational(x) for x in c["values_or_normal_form"]]])
               for c in concepts]
    last = {kind: max((e["cycle"] for e in state["events"] if e["kind"] == kind), default=None)
            for kind in ("representation_acquired", "recurrence_derived", "procedure_executed")}
    print(capacity, last, len(concepts),
          sum(all(b.col_join(v).rank() > b.rank() for b in spaces) for v in vectors),
          sum(combined.col_join(v).rank() > combined_rank for v in vectors),
          "combined rank", combined_rank,
          "distinct encoded states", len({tuple(combined[:, i]) for i in range(combined.cols)}))
    assert not any(a["kind"] in {"acquire", "derive", "use"}
                   for d in state["decisions"] if d["cycle"] > last["procedure_executed"]
                   for a in d["options"])
```

Observed output counts are72/57/38 and130/110/74, combined rank6 and24
distinguished states. Last cycles are18/55/79 in both conditions. These are
new post-run analyses of the previous Actions result, not a new Actions score.
