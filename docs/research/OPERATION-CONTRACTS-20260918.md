# One operation contract for the planner, the relational DSL, the edit calculus and the algebraic layer

Repository: `corcondor/mortra`. Branch: `codex/operation-contracts-20260918`.
Base: `7312ada` (the frozen algebraic structures result).
Status: integration and its execution record. No preregistered comparison, no claim.

## 1. What this integrates, and what it does not add

The goal is not more mathematics. It is that the reasoners already in this
repository speak about the same operations, so that an operation composed while
solving one problem can be registered, edited, re-certified and used on the next.

| what happens | which existing module does it |
|---|---|
| typed search over objects | `runtime_typed_planner.synthesize_typed_plan` |
| programs, unfolding, folding, splicing, higher-order abstraction | `geometry_relational_edit` |
| exact arithmetic, kernels, images, complexes, Jacobians | `algebraic_structures` |
| the geometry language and its exact certification | `geometry_relational_dsl`, `geometry_relational_library` |

No second planner, no second certifier and no second algebra were written. Three
modules were added, and they only hold the shared record:

* `operation_contracts.py` — the contract, object identity, the proof context, the
  session that applies contracts and charges one counter;
* `algebraic_operation_domain.py` — the sorts, the exactly decidable predicates, the
  specifications, and the given contracts for maps, bases, quotients, complexes and
  tangent data, each wrapping an existing `algebraic_structures` function;
* `operation_acquisition.py` — reading a solution back as a program, deriving its
  guarantee, carrying its preconditions, registering it, and expanding it again.

`geometry_relational_edit` gained one parameter, `domain`, whose default is the
geometry language it was written for; the geometry behaviour is unchanged and its
tests pass untouched.

## 2. The contract

A contract carries exactly six things.

* **type** — each parameter and the result have a sort (`Map`, `Basis`, `Quotient`,
  `Complex`, `Degree`, `System`, `Point`). Sorts are the planner's types, so maps,
  complexes and quotients travel in the same search that points travel in.
* **object identity** — every value has a canonical identity inside its sort, so a
  condition is a statement about objects rather than about variables. Identity is
  content-addressed: two equal matrices are the same object.
* **preconditions** — conditions that must hold before the operation applies.
* **guarantees** — conditions that hold of the result.
* **proof** — for each guarantee, whether it was decided exactly or derived by a
  rule; for each precondition, whether it came from the task's hypotheses, was
  inherited from a guarantee already established, or was checked exactly here. An
  operation whose precondition cannot be discharged does not apply; nothing is
  assumed.
* **cost** — every check and every computation charges one `OperationCounter`, the
  same counter the algebraic layer already uses.

Provenance is kept apart and never collapsed:

* `given` — written by a person: the sorts, the predicates, the specifications, the
  primitive contracts and three inference rules;
* `acquired` — composed during a run and registered only after its guarantee was
  derived from the guarantees of its own steps;
* `candidate` — observed to hold on the instances tried. A candidate runs, but its
  guarantees are recorded with status `instance`, never enter the proof context, and
  may never discharge another operation's precondition.

## 3. A goal is a specification, not a route

A specification is a definition, `predicate(params) := exists witnesses. conjuncts`:

```
homology_of(A, B, v)      := ∃ K, I.  kernel_of(A, K) ∧ image_of(B, I) ∧ quotient_of(K, I, v)
homology_at(C, q, v)      := ∃ A, B, r. differential_of(C, q, A) ∧ successor(q, r)
                                        ∧ differential_of(C, r, B) ∧ homology_of(A, B, v)
tangent_quotient(S,T,p,v) := ∃ J, G, K, M. jacobian_at(S, p, J) ∧ jacobian_at(T, p, G)
                                        ∧ kernel_of(G, K) ∧ same_columns(K, M) ∧ homology_of(J, M, v)
```

The contracts for kernel, image and quotient are given; which sequence of them meets
a specification is not. A fact meets a goal when its own certified guarantees, with
the guarantees already established, entail the specification — the same derivation
that later certifies an acquired operation.

## 4. The loop

While solving ordinary goals:

1. **compose** — the planner reaches a fact meeting the specification;
2. **derive** — the specification is matched against what the run established,
   exhibiting the witnesses the body produced. Without that, nothing is acquired;
3. **carry** — every precondition no step of the body established is lifted to the
   composite. A precondition about an object internal to the body cannot be stated at
   the interface, so the composite is refused rather than weakened;
4. **register** — the composite becomes a contract with a body in the edit calculus
   grammar, its provenance, its parents and its generation;
5. **edit** — a step of an acquired body can be lifted to an operation parameter with
   the interface of that step's guarantees, and instantiated by any operation that
   offers at least that interface;
6. **re-certify** — an edited body is accepted only through the same gate: execute it,
   derive the specification again, register it as a new generation;
7. **re-inject** — later goals are searched with the acquired vocabulary, and the
   acquired operation is offered before the given operations reaching the same sort.

Two pieces of scheduling are supplied and are not results: rules that return one of
their arguments (adding a guarantee, not an object) are offered before operations
that build objects, so that a precondition a rule can discharge is not recomputed;
and while an acquired operation reaches a sort, the given operations reaching that
same sort are held back for one pass.

## 5. What the run did

`scripts/run_operation_integration.py` (record in `reports/operation-integration/result.json`).

**First integration task — `ker(A)/im(B)` under `AB = 0`.** Solved by composing
`kernel_basis`, `image_basis` and `quotient_basis`, with the inclusion `im B ⊆ ker A`
discharged by the supplied rule rather than recomputed. The quotient's dimension
agreed with `algebraic_structures.homology`. Acquired as `homology_pair`
(generation 1) with the carried precondition `zero_composition(A, B)` — the
hypothesis was about two particular matrices, so it became a precondition — and the
guarantee `homology_of(A, B, v)`.

**Later goals, each solved twice: with what had been acquired, and with the given
operations only.** States explored and counted operations, this run, these inputs:

| goal | used the acquired operation | with acquired | given only |
|---|---|---|---|
| H₁ of two triangles | yes | 63 states, 650 ops | 1,184 states, 3,850 ops |
| H₁ of two circles | yes | 129 states, 1,202 ops | 2,049 states, 20,921 ops |
| H₂ of a tetrahedron boundary | yes | 63 states, 375 ops | 830 states, 2,415 ops |
| tangent directions removed by `z = 0` on the sphere | yes | 4,055 states, 24,627 ops | 4,105 states, 24,706 ops |

Every answer agreed with `algebraic_structures.homology` or with the difference of
the two `tangent_space` dimensions, computed independently.

**Second generation, on two kinds of problem.** `homology_at_degree(C, q)` and
`tangent_gap(S, T, p)` were both acquired with parent `homology_pair`, so the
operation composed for the first task is used both for the homology of a chain
complex and for tangent spaces. Each expands to given contracts only.

**Editing.** The `differential` step of `homology_at_degree` was lifted to an
operation parameter with interface `differential_of(i0, i1, o)`. Instantiating it
with `compose_maps` was refused — that operation does not offer the interface —
and instantiating it with an operation that does gave a body which, after being
executed and having its specification derived again, was registered as generation 3
with the same expansion as its parent.

**Provenance.** A candidate operation guessing that a kernel basis is an image basis
ran on a nilpotent matrix where that happens to be true: its guarantee was recorded
with status `instance`, did not enter the proof context, and the operation stayed out
of the certified vocabulary. On a matrix where the guess is false it did not apply.

**The supplied rules were audited.** With `verify_derivations` on, all 17 guarantees
that the three rules derived were also decided exactly, and agreed.

## 6. Non-claims and limits

* The sorts, the predicates, the specifications, the primitive contracts and the
  three inference rules are supplied by a person. What the system does is compose,
  derive, carry, register, edit and reuse.
* An acquired guarantee is derived from the guarantees of its steps under its carried
  preconditions. It is not a proof that the operation behaves well outside them.
* The measurements above compare two runs of this search on these inputs. They are
  not a claim about searches in general, and the tangent goal shows no gain: its cost
  is dominated by enumerating the arguments of a seven-parameter rule and by the
  symbolic differentiation that checks a Jacobian.
* Acquisition happens when a goal is met, and the vocabulary is re-read at the next
  search; the planner still fixes its operation set for the duration of one search.
* Nothing here touches a preregistered evaluation. `configs/*-20260917.json`, the two
  preregistration documents, the algebraic result and its runner are unchanged; this
  layer adds modules, a test file and a record of its own.
