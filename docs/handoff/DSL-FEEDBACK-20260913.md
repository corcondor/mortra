# Executable acquired vocabulary and shared observable spaces

Development starts from `02474f8f428f855eef8ec38a9cdc83e0571d6586` on
`corcondor/mortra`, branch `codex/theory-formation-20260913`.
The historical THEORY.md / NEXT.md status labels are not rewritten.

## Normal entry and actual data flow

`scripts/run_theory_formation.py` still accepts a domain signature, seed and
resource budget. The new examples are `configs/theory-dsl-ring.json` and
`configs/theory-dsl-fold.json`. Neither contains a proposed acquired definition,
observable, helper basis, matrix, readout, or target identity.

The existing least-visited computation-kind scheduler also offers `abstract`
and `synthesize` when there is eligible runtime experience. Python is fixed;
the persistent `state.dsl` archive and its definition table grow during a run.

1. `Theory.invent` composes declared operations, executes the result with the
   exact domain interpreter, and records the computation before semantic
   deduplication. Proven identities still use the existing proof kernels.
2. `Vocabulary.learn` calls `library_compression.learn`, not another
   anti-unifier. Positive definition-inclusive code savings admit a definition.
   The archive is incremental: stable earlier references are never renumbered.
3. Its body, argument types, domain scope, acquisition sources, dependencies,
   definition cost and complete-expansion checks are persisted. The common
   anti-unifier now reuses a hole for repeated ordered disagreement pairs.
   Different pairs remain independent; shared-argument matching stays exact.
4. `Vocabulary.synthesize` calls the existing `call_candidates` with the
   acquired definition table and the live concept / execution pool. Definitions
   are ordered by observed downstream code saving, then acquisition utility.
   No extra mathematical axiom is added by a definitional abbreviation.
5. Calls fully expand through `expand_for_execution`. Their actual evaluation
   is checked against independent primitive execution. The program, arguments,
   result and cost return to the learning corpus and pending Theory frontier.
6. Subsequent anti-unification sees calls to older definitions. It can therefore
   acquire bodies that call earlier definitions; this is measured, not assumed.

This is a bounded, typed expression language. It has no learned arbitrary Python
code, unbounded recursion, new proof axiom, or general-purpose self-programmer.
Definitions of compositions are executable procedures, but are not by themselves
new mathematical theorems or new general algorithms.

## Mathematical representation operations

With `shared_spaces: 1`, `Theory.acquire_shared` searches existing rational spans
before invoking the existing `discover_action_observable_basis` closure kernel.
`observable_spaces` holds the canonical basis, action matrices and certificate.
`representations` holds observable bindings with readout vectors and space
references, not another copy of the basis or matrices.

`theory_spaces.canonical_space` performs exact rational row reduction in the
declared complete finite-function model. It transforms the action matrices by
the same change of basis, then checks every action identity. Identity includes
the action system, field, domain and certificate scope. Equal rank is not an
equality test. Outside-span observables request the existing closure kernel if
the distinct-space budget allows it; adding a readout uses no new-space slot.

There are two persistent typed executable operation contracts:

- a certified observation binding maps an action word to the scalar-valued
  function `q(T_word(x))` on every declared finite state;
- a certified recurrence maps a nonnegative integer to
  `q(T_label**n(initial_state))`, only at the certified initial state and label.

`runtime_typed_planner.synthesize_typed_plan` composes calls using these runtime
contracts. The observation interpreter uses the acquired matrices and readout;
the recurrence interpreter uses the acquired recurrence coefficients. The
independent replay uses direct model actions instead. The recurrence evaluator
is shared with the older `Theory.use_procedure`, not a second solver.

Frame-only origami still omits panel history, centre positions and collision
legality. An existing readout is not a certificate for collision-free planning
or an unrepresented goal. Such requests are refused. The separate q-directed
task/legality verification line remains in the same Actions run.

## Reproduction and measurements

Install `requirements-test.txt` in Python 3.12.10. Run:

```bash
python -m pytest tests/test_theory_dsl.py tests/test_theory_formation.py -q
python scripts/verify_theory_dsl.py \
  --config configs/theory-dsl-ring.json \
  --config configs/theory-dsl-fold.json \
  --output <new-directory>
```

The harness first freezes all held-out expression trees, action words and
natural-number arguments. They are never given to acquisition. It starts fresh
normal processes for initial-only, learning, and no-DSL-use conditions, splitting
each nontrivial run into first and resumed phases. Failed subprocesses retain
their logs and snapshots. Revisions are separate runs, not repaired evidence.

Held-out evaluation uses discarded copies and verifies the archive is unchanged:

- A: initial knowledge;
- B: acquired vocabulary enabled;
- C: the identical learned archive with vocabulary use disabled;
- an additional no-DSL-use normal run under the same configured budgets.

C retains resolvable definitions and uses primitive expressions for execution;
it does not create dangling references. Held-out evaluation forbids closure
acquisition, records exact agreement, matching overhead, code size, definition
cost, execution cost, and conditional reuse on new words and repeat lengths.

All fixed expression tasks are already evaluable by the primitive interpreter.
This experiment can demonstrate reuse or description reduction, but cannot
demonstrate an unsolved-to-solved proof-search gain. The output says so explicitly.
The action-word transfer evaluates learner-selected observations at held-out
arguments; it is not an independently preselected set of new mathematical q's.

The code-size model is the existing canonical JSON coding convention, including
each definition body once. Full archive cost, including proof/provenance data,
is recorded separately. Code shortening need not reduce primitive execution or
wall time. Structural definitions, readout aliases and distinct invariant spaces
are counted separately.

The live candidate bound charges a call node and every supplied argument, not
only its name. A separate expansion bound protects the interpreter. A newly
acquired abbreviation may express more primitive operations within the same
live program-size budget, but the expansion is not counted as free execution.

## Shared verification line

Use the existing `Verify MORTRA Kernels` workflow with dispatch input
`verification_suite=dsl-feedback`, `target_ref=<full SHA>` and
`expected_sha=<same full SHA>`. It runs the existing 351-test q-directed suite,
small normal/reuse/refusal checks, Theory regression checks, and the new DSL
experiments. Fresh logs, configs, snapshots, source seals and verification JSON
are uploaded under the existing run-ID-named artifact. No new repository or
duplicate workflow is introduced.

## Development failures preserved

Before the final frozen verification, development pilot v1 stopped because the
event emitter received the cycle twice. Pilot v2 stopped because the library
visitor encountered a non-program argument dictionary and its validator raised
KeyError instead of rejecting it as a non-term. Both were fixed in infrastructure;
their saved failed runs are not counted as completed autonomous runs.

Pilot v4 completed, but its held-out matching counters exposed a general tree
visitor omission: `holonomic_relation_reuse.occurrences` traversed dictionaries
but not lists. Theory stores child programs under `args` lists. The visitor now
traverses both container types, with a regression for list positions and alias
detachment. Pilot v4 remains a separate result, not the final code's evidence.

Final Actions run ID, exact SHA and numerical results belong in a separate result
record after that run finishes. Earlier Windows pilot results are not CI evidence.
