# Primitive basis quality: fixed protocol

This experiment follows, rather than modifies, temporal run 34800481257 on
`d545d2915ae434194e213bf110c69f0ece6e37a4`. It evaluates expressivity, redundancy,
search cost and autonomous reacquisition separately. Smallest is not best.

## Executable layers

The tested normal domain is `theory-dsl-fold.json`: `Theory -> Vocabulary`,
`Domain.seeds/compose -> type_of/evaluate`, typed goal synthesis, exact model
verification and normal library acquisition. It exposes nine syntax families:
var, const, pull, add, mul, neg, eq, not, and. Var has nine frame sensors; const
accepts exact rationals but normal seed generation supplies only 0 and 1.
Pull has the four actual fold labels; hence seven compositional families,
ten parameter-instantiated compositional operators, and eleven scalar seeds.
The runtime inventory table is emitted from this domain, not copied from a
general design document. `word` and `natural` are auxiliary inputs for archived
readout/recurrence operations. Acquired macros/readouts/recurrences are a
separate dynamic vocabulary, not additional initial geometric primitives.

The differential-ring adapter has diff instead of pull. It is executable, but
its expressivity is NOT measured by this finite-frame experiment. Neither is
the full panel/centre/legality model. Nine syntax forms is not a general count
of everything MORTRA can execute or a theoretical capability ceiling.

## Removal, learning, addition

`--exclude-primitive` changes the actual domain type checker, seed producer and
composition/action alphabet. The exclusion list is in the domain identity and
saved/resumed flags. Removed operators cannot appear in accepted computations.
Each of the nine families, and each of four pull parameters, is removed alone.

All deletion conditions, including B, have zero representation slots and no
shared-space acquisition. This deliberately isolates composition and learned
macros: otherwise a certified matrix/recurrence wrapper could reintroduce an
excluded pull action. Allowing a zero acquisition budget is a general disable
switch, not a fallback solver. Existing positive-budget runs remain unchanged.
No per-operator replacement code is installed into the learner.

Each condition first solves frozen value goals with the initial DSL, then runs
the same existing normal learner with only its allowed basis. Normal learning
receives no task answers, removed-operation target or desired macro. Its actual
acquisitions are evaluated later against the same target set and, where the
existing symbolic certificate applies, against the removed operation with
independent arguments at all 24 states. A failed bounded reconstruction is
unresolved, not evidence that the primitive is semantically essential.

A separate, fixed full normal producer supplies the first three actual acquired
macros for B+{macro} comparisons. Selection is acquisition order, never evaluation
performance. All referenced definitions, representations and proofs remain
available as dependencies and count in description cost. They are not silently
free primitive calls. Scalar recurrence/readout use is not panel-structure use.

## Fixed inputs and proofs

`configs/theory-basis-quality.json` fixes seed 923114, 24 scalar goals from the
existing challenge generator and 12 predicate goals from existing composition.
The complete 36-target set is fixed before any learner runs. Predicate goals
use the existing typed planner and exact independent model verifier; this is
a generic result-type extension, not a new solver. All conditions get 256
search applications, 100,000 interpreter work, and nonbinding size ceilings.
Learning uses 80 cycles, 180 seconds and the existing 512 FIFO sample.
Development uses a different seed and four goals; its outcomes are not held-out.

Fold-action reconstruction uses the existing typed planner on total action
maps. Equality of maps certifies all arbitrary QQ-valued input functions on
every declared frame, not a few observed sensor values. Scalar reconstruction
uses the existing SymbolicScope and polynomial identity checks with independent
arguments. Predicate necessity uses exact typed-constructor reachability and
complete Boolean function closure (constants overapproximate state-dependent
scalar comparisons). These are evaluator proof procedures, not autonomous
new-theorem acquisitions. Failed/unsupported operator certificates stay
unresolved; do not force them into an unjustified 'essential' category.

Primitive-pair role overlap measures bounded composed behaviors on all states;
it does not prove operator equality. Action-map equality and commutation are
separately certified. All witness programs, residuals, costs and scope are saved.

## Metrics and interpretation

Vocabulary size, observed coverage, first-found program length/depth, candidate
count, execution, verification and wall time remain separate. 'Representable'
is a lower bound from certified witnesses, unless an independent certificate
establishes more. The existing planner is not a shortest-program oracle.
First-found length must not be presented as a proved global minimum.

Comparisons include common-success per-task deltas and lost/gained task IDs.
The empirical Pareto frontier uses size, solved coverage, found description,
search and execution, without weighted scalar reward. Conditional mean length
on solved tasks is explicitly marked; the frontier is not a global theorem.
Removing a pull parameter reduces instantiated branches, not the number of
syntax families. Learning costs and acquired macro reuse are separate.

```text
python -m pytest -q tests/test_basis_quality.py tests/test_temporal_utility.py tests/test_theory_formation.py tests/test_theory_dsl.py tests/test_theory_semantic_edit.py tests/test_theory_corpus.py scripts/test_library_compression.py scripts/test_expand_for_execution.py scripts/test_call_candidate_dedup.py
python scripts/verify_basis_quality.py --plan configs/theory-basis-quality.json --output <new-directory>
```

Existing `worker-ci.yml` retains q-directed tests/acquisition/reuse/refusal and
the DSL regressions. Research pushes now select this next experiment; explicit
`temporal-utility` dispatch reproduces the preceding study. No new workflow,
main merge, force push, LLM, universal-machine construction or new frontier
generator is introduced.
