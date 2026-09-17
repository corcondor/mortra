# Relational geometry DSL: design, soundness rules and preregistered evaluation

Repository: `corcondor/mortra`. Branch: `codex/geometry-relational-dsl-20260917`.
Base commit: `10213b0a1639352cd682e7224090a960ec8333b6`.
Status: design and preregistration. Nothing here is a result.

## 1. Direction

The geometric predicates and their polynomial meaning stay fixed:
`midp/3, coll/3, perp/4, para/4, cyclic/4, cong/4, eqangle/8` and the
nondegeneracy predicates `diff/2, ncoll/3, npara/4`, lowered by the existing
`geometry_semantic_dsl.lower` and bridge `goal()`, with prerequisites from
`geometry_semantic_dsl.conditions`. What is redesigned is the language that
combines them into relations, constructions, inferences and operations.

The goal is not more command types. It is a small set of syntax rules from which
operations are generated, transformed and abstracted, such that:

* R1. Shared variables, sorts and applicability conditions are syntax. They are
  matched when terms are composed. A condition that cannot be discharged is kept
  as an open obligation, never dropped and never counted as proved. A composition
  whose condition is refuted is excluded before any application is charged.
* R2. Operation bodies can be composed, partially substituted (an inner step
  replaced) and abstracted (common structure extracted; a specific relation or
  operation turned into a parameter). Relations and operations are arguments,
  not only points.
* R3. Acquired operations return as material to the same grammar. The grammar is
  finite, composition depth is not cut by the language, and per-run budgets are
  separate from expressiveness.

Criterion: not whether an acquired operation can be called, but whether its
internal structure can be re-edited and generalized inside the same DSL.

The mapping of the current code (commit 10213b0) against these requirements is
summarized in section 9. Parts that already satisfy them are reused.

## 2. Sorts and terms

Sorts: `Point`, `Rel[k]` (k-ary relation over points), `Op[n -> m]` (n inputs,
m point outputs; higher-order inputs are typed separately), `Rule` (an operation
with no outputs: an inference).

All terms are JSON, content-addressed with `representation_progress.digest`.

### 2.1 Relation terms (four rules)

```
R ::= {"atom": p, "args": [v, ...]}          # p a fixed predicate, v variable names
    | {"and": [R, ...]}                       # conjunction; sharing = same variable name
    | {"exists": [z, ...], "body": R}         # hiding
    | {"rvar": rho, "args": [v, ...]}         # relation variable of sort Rel[k] (higher order)
```

A named relation definition is `{"id", "params": [v...], "body": R}` stored in a
content-addressed table and referenced as `{"rdef": id, "args": [...]}`, which
unfolds definitionally. A relation definition asserts nothing: it carries no
existence claim.

A *spec* is a relation with one distinguished free point variable, written
`λv. R`, used to describe what a point must satisfy.

Atoms are compared modulo certified argument symmetries (section 4.1).

### 2.2 Operation terms (three rules)

```
step  ::= {"out": y, "prim": family, "args": [v, ...]}
        | {"out": [y, ...], "call": opref, "args": {param: arg}}
program ::= {"steps": [step, ...], "result": [y, ...]}      # a DAG; later steps may use earlier outputs
opdef ::= {"id", "params": [param...], "body": program, "contract": contract, "certificate": cert,
           "parents": [id...], "generation": g}
param ::= {"name", "sort": "Point"} | {"name", "sort": "Rel", "arity": k, "interface": cond}
        | {"name", "sort": "Op", "inputs": n, "outputs": m, "interface": contract-schema}
opref ::= opdef id | {"ovar": name}
arg   ::= point variable | relation term (closed as {"lambda": [v...], "body": R}) | opref
```

`prim` families are the existing certified fragment families
(`EuclideanFragment.arities`: midpoint, mirror, foot, circle (circumcenter),
orthocenter, reflect, intersection_ll). Other JGEX families may be added only
with a kernel certificate; none are added in this iteration.

### 2.3 Contracts are part of an operation's syntax

```
contract ::= {"pre":  R over params,              # applicability: atoms and nonzero guards
              "post": R over params and outputs,  # guaranteed relations
              "obligations": [obligation...],     # open conditions, never proofs
              "existence": "certified" | "open",
              "nonvacuity": witness-or-null}
obligation ::= {"condition": atom-or-guard, "status": "open" | "discharged",
                "justification": null | {"kind": "context" | "symmetry" | "lemma" | "instance", ...}}
```

For a primitive family the contract is read from the kernel certificate
(`GeometryLibrary().schemas[family]`): `post` from `guaranteed_relation`,
`pre` from `geometry_semantic_dsl.requirements` plus the sequential nonzero
polynomials. No contract field is written by hand.

## 3. Composition calculus (R1)

For a program, steps are processed in order with a context `Γ` of atoms known
at that point: the composite's `pre` atoms, then each earlier step's `post`
instantiated at its actual arguments.

For each step `s` with contract `(Pre_s, Post_s)` instantiated by `σ`:

* each atom `a` of `Pre_s[σ]` is **discharged** if it is entailed by `Γ` modulo
  certified symmetries, or by a certified lemma whose premises are all entailed
  (depth bounded by a per-run budget, not by the language), and **open**
  otherwise. Open conditions are appended to the composite's obligations and
  also lifted to its `pre`;
* a nonzero guard is discharged only by an exact argument: identical factor in
  `Γ`'s guards, or an instance evaluation (section 5) at a concrete configuration;
* if an atom or guard is **refuted** (its polynomial is identically zero after
  substitution, e.g. `diff p p`, or `ncoll a b a`), the composition is refused
  before any application is charged;
* `Post_s[σ]` is added to `Γ`.

The composite `post` is the conjunction of all step posts projected by `exists`
over non-result locals. The composite's `existence` is `certified` only if every
obligation is discharged universally and the non-vacuity check below passes.

Non-vacuity (fixes a defect found at 10213b0, where
`certify_body(circle(midpoint(f0,f1),f0,f1))` is certified although its guard
vanishes identically): before an operation is registered, every guard and every
`pre` atom's lowered polynomial is evaluated exactly at deterministic rational
general-position inputs. If some sample makes all guards nonzero and all `pre`
equalities hold where required, the guard set is not identically zero on the
input space, so the domain is dense. Otherwise the operation is refused as
possibly vacuous. The sample points are derived from the operation digest, never
from a task.

## 4. Inference: rules generated by metarules and certified exactly

### 4.1 Symmetries

The symmetry groups used for canonical atom comparison (the ones in
`geometry_proof_hypergraph.Atom.canonical`, plus `midp` swapping its last two
arguments) are each verified once by exact polynomial comparison: the permuted
polynomial must equal the original up to a nonzero rational constant. A symmetry
that fails is not used.

### 4.2 Metarules (supplied language bias, not lemmas)

As in meta-interpretive learning, a few metarule shapes are supplied; their
instances are certified by exact algebra and only certified instances are used.

MR-transfer. For a spec atom `α(v)` and a relation `S(y, x1, x2)` that appears
among the certified primitive `post` atoms relating an output to two of its
inputs:

```
α(y)  <-  α(x1) ∧ α(x2) ∧ S(y, x1, x2) ∧ diff(x1, x2)
```

The set of `S` shapes is read from the primitive contracts, not chosen by hand.

Certification of an instance: parametrize the solutions of `S(y, x1, x2)` by the
existing rational witness of the primitive that publishes `S`
(for `coll(y,x1,x2)` the line `y = x1 + t (x2 - x1)` with a fresh symbol `t`),
and search for polynomial multipliers `λ1, λ2` of degree at most one in `t` with

```
α(y) - λ1 α(x1) - λ2 α(x2) ≡ 0
```

by exact linear algebra over QQ in the coefficients. A solution is a certificate
(sufficient, not complete); it is replayed by `geometry_contracts.exact_zero`.
Absence of a solution means "not certified", never "false".

The conclusion is the polynomial equation of `α(y)`. The nondegeneracy
prerequisites of `α(y)` (`conditions()`) are not concluded by the lemma and
remain obligations.

MR-chain (hidden variable), `P(xs) <- Q(xs1, z) ∧ S(xs2, z)`, is declared but
not enabled in this iteration; enabling it later is a separate preregistered
change.

## 5. Instance evaluation and replay

At an exact rational configuration a program is executed with the existing
`EuclideanFragment.primitive` on `_JGEXElaborator` coordinates (as
`SemanticGeometryDomain.replay` does). Every denominator and guard is checked
exactly; a zero refuses the step. Each primitive execution is one charged
application. An atom holds at an instance when its lowered polynomial is exactly
zero and its `conditions()` prerequisites hold (same as `certify_atom`).

A solution is accepted only if (1) the program replays by primitive re-execution
from the task's input points, (2) every goal atom, with `u` bound to the result,
passes `certify_atom` including prerequisites, and (3) the result is not one of
the task's input points. Numeric evaluation is never used.

## 6. Edits (R2) and acquisition (R3), as implemented

`math_os_prototype/geometry_relational_edit.py`. A definition is data in the
program grammar: params, a body of `prim` / `call` / `ovar` steps, declared post
atoms over params and the result `v`, exact certificates, parents, generation.

* `define(body, post, table)`: unfolds calls, certifies every declared post atom
  by exact substitution of kernel witnesses into the lowered predicate
  (`geometry_relational_library.certify_entry`), refuses atoms that mention a
  hidden local, and refuses the definition unless non-vacuity is shown by exact
  execution at digest-derived rational inputs. Generation is one more than the
  largest parent generation; the language has no generation cap.
* `unfold(body, table)` / `fold(body, definition, table)`: definitional expansion
  and its inverse; a fold is accepted only if both sides unfold to the same
  primitive program up to local names.
* `substitute(definition, step, replacement, table)`: replaces one inner step by a
  program over that step's inputs, then re-certifies every declared post atom on
  the edited body. The parent is recorded; the result is a new generation. A
  replacement that breaks a post atom is refused.
* `abstract_operation(first, second)`: anti-unifies two definitions with one
  skeleton. Each position whose primitive differs becomes an `Op` parameter whose
  interface is the canonical intersection of the two primitives' certified post
  atoms over that step's inputs and output; the abstraction keeps only post atoms
  certified in both. A bare hole and an abstraction with nothing differing are
  refused. `instantiate_operation` accepts an argument only if its certified post
  includes the interface, and then re-certifies every post atom on the
  instantiated body.
* `abstract_relation(programs)`: lifts the hole specs of solved transfer steps to
  `Rel` parameters. `instantiate_relation_schema` decides applicability for a
  concrete relation by replaying the MR-transfer certificate for it (accepted for
  `para`, refused for `cyclic`).
* `convert_archive_definition(h)`: converts a stored `MorphismContract` and
  re-certifies its effects that are expressible over its interface.

Acquisition of producers (`math_os_prototype/geometry_relational_library.py`) is
task-independent. Programs of certified primitives over generic inputs
`p0, p1, p2` are enumerated bottom-up to depth 2 (a depth-2 step takes exactly one
depth-1 point, the other arguments are inputs), with observational equivalence at
eight digest-seeded floating-point instances. Each distinct program is indexed by
every atom pattern over `v, p0, p1, p2` (`coll, perp, para, cong, cyclic, midp,
eqangle`) that vanishes at all instances. The index is a proposal structure: a
program is used for a pattern only after `certify_entry` decides that pattern
exactly, and the decision is cached. No task, goal, witness or solver output is
read. Acquisition time and counts are reported separately.

## 7. Search that uses the DSL, as implemented

`math_os_prototype/geometry_relational_search.py`, class `RelationalSynthesis`.
A plan is a partial program: nodes are named points, primitive steps, or holes
carrying a spec (a conjunction of canonical atoms over `v` and point names);
distinctness constraints come from transfer premises; a penalty counts root goal
atoms left unguaranteed.

Expansion of the first hole with spec `S`:

1. Reuse a point: for the root, any constructed (not input) point that satisfies
   the goal atoms exactly with prerequisites; for an inner hole, any point whose
   lowered spec polynomials vanish; for a hole with empty spec (a free argument),
   only the task's input points.
2. A primitive whose kernel post produces each atom of `S` directly (unification
   modulo certified symmetries), or transfers it through a certified MR-transfer
   shape; transfer premises become specs of new input holes plus a distinctness
   constraint. Requirements whose polynomial vanishes at bound points, and
   bindings whose exact witness returns an input for all coordinates
   (`binding_returns_input`), are excluded before any application is charged.
3. An acquired program from the index whose exactly certified patterns cover `S`
   under an injective renaming of `S`'s point names to `p0, p1, p2` (at most two
   programs per renaming), expanded into primitive step nodes; its free inputs
   become empty-spec holes.
4. Only for the root, and only in the partial phase: the same as 2 and 3 for the
   goal atoms minus one, the omitted atom adding one to the penalty. Omitted atoms
   are decided only by the exact goal check.

Plans are ordered by (steps + specified holes + penalty, empty holes, creation
order); a plan with more than `max_plan_steps` steps is not pursued. A plan
without holes is executed bottom-up; identical steps (canonical under certified
input symmetries of the primitive) are executed once; each new primitive
execution is one charged application; a refused step is charged and remembered;
a transfer distinctness violation stops the plan before its parent step is
charged. Every new point is checked against the goal.

Phases, each with its own declared allowance: guaranteed plans only
(`guaranteed_applications`, `guaranteed_expansions`), then partial root coverage
(`partial_applications`, `partial_expansions`), then the fallback: the existing
contract-guided search B with the remaining applications. The fallback is not new
search machinery and its solutions are marked `via: fallback`.

Accepted solutions pass primitive re-execution from the input points and exact
goal atoms with prerequisites, and are not input points.

## 8. Preregistered evaluation

Code and configuration are frozen at a commit before any run on the fresh cohort.
No edit happens during a run. A defect found during evaluation sends the work back
to development; the failed run is kept and reported.

Development disclosure. Sections 6 and 7 were developed on the exposed 16-task
regression cohort and on a development cohort generated by the rule below with
seed 20260917001 (48 tasks, 26 of them run with every condition before the design
was frozen); seed 20260917002 (2 tasks) was used to smoke-test the runner. Every
numeric and structural choice below was made after looking at those runs and is
development-tuned: the phase structure and order; `guaranteed_applications` 40,
`guaranteed_expansions` 2000, `partial_applications` 16, `partial_expansions` 1000,
`max_plan_steps` 8, `library_programs_per_binding` 2; the plan priority; input-only
binding of free arguments; partial root coverage with a penalty of one per omitted
atom; the pre-charge exclusions (vanishing requirement polynomials,
`binding_returns_input`, transfer distinctness); the producer enumeration (inputs
`p0, p1, p2`, depth 2 with exactly one depth-1 argument at depth 2, eight
floating-point instances, tolerance 1e-7 relative to the fourth power of the
coordinate scale, predicates including eqangle); the certification size bound
(20000 terms, an undecided atom is refused); and B as the fallback. None of the
development cohorts supports a claim.

Fresh cohort seed. The seed is derived inside the run from the drand default
chain (chain hash `8990e7a9...51b2ce`, period 30 s): the round number is written in
the freezing commit before that round is published, the run fetches it from two
endpoints, requires agreement, checks that the randomness equals the SHA-256 of
the signature, and uses `int(sha256(salt + ":" + randomness)[:8], 16)` with salt
`mortra-relational-dsl-fresh-1`. The BLS signature itself is not verified. The
first `workflow_dispatch` of this configuration at the freezing SHA is the binding
run, whatever its outcome; any run that writes `fresh-cohort.json` uses up the
round, including a crash, a timeout or a defect. The run refuses a dirty tree, a
development seed, and a fresh task that coincides with a regression or development
task.

Conditions, same tasks, same exact kernel, same replay and audit:

* A: existing `SelectionDomain`, primitive families, existing order.
* B: existing `SelectionDomain`, primitive families, contract-guided order. The
  baseline.
* N0: relational synthesis, direct contract production only.
* N: plus certified MR-transfer.
* NL: plus the task-independent producer index.
* NLF: plus the fallback B with the remaining applications and remaining wall time.
  The primary condition.

Budget: 112 charged applications per task, wall time 600 seconds per task including
the fallback, the allowances in `configs/theory-geometry-relational-dsl-20260917.json`.
N0, N and NL have no fallback, so they never use more than 56 applications (the two
phase allowances); comparisons of these ablations with A and B are at that effective
budget.

Unit of the budget. A charged application is not the same unit in every condition.
In A and B it is one attempted construction per search state, so the same
construction on the same points is charged again in every state where it is tried,
and a duplicate output is charged and refused. In N0, N, NL and the directed phases
of NLF, each distinct construction on the same input points is executed and charged
once per task, and bindings whose requirement polynomial vanishes at the bound
points are refused before charging. At 112 applications N can therefore execute more
distinct constructions than B. To bound this effect, every fresh task solved by NLF
and not by B at 112 is re-run with B at 448 applications (`robustness.json`); this is
reported, not part of the criterion.

Cohorts:

* regression: the 16 exposed tasks of the frozen plan in
  `reports/geometry-complete-revalidation-evidence.zip`. Development data.
* fresh: 48 tasks generated inside the evaluation run from `fresh_seed` by the rule
  in `math_os_prototype/geometry_relational_cohort.py`:
  1. points `a, b, c, d` with integer coordinates in [-9, 9], pairwise distinct,
     no three collinear;
  2. goal: two atoms, each with a predicate chosen uniformly from
     `coll, perp, para, cong, cyclic, midp, eqangle` and an argument tuple chosen
     uniformly over `{u, a, b, c, d}` containing `u`; identical atoms rejected;
  3. keep the task only if the two lowered equations in `(ux, uy)` have no common
     factor and a nonzero resultant, some rational solution is not an input point
     and satisfies both atoms with prerequisites under `certify_atom`, and no input
     point satisfies the goal;
  4. repeat until 48 tasks; rejection counts are recorded.
  The filter reads only the task, never a solver.

Primary metric: tasks solved at 112 applications on the fresh cohort, NLF versus B.
Improvement is claimed only if all of the following hold:

0. the run is binding (first dispatch at the freezing SHA, clean tree), complete
   (every task of both cohorts run) and its loaded modules are unchanged;
1. NLF solves strictly more fresh tasks than B, counting only solutions that pass
   the independent audit within the wall budget;
2. the exact one-sided binomial test on discordant tasks (NLF-only vs B-only
   solves) gives p < 0.05;
3. zero false solutions in every condition (independent replay and exact goal
   check);
4. on the regression cohort NLF loses no task that B solves, reported per task.

Secondary, reported without a claim: A versus NLF; N0, N and NL as ablations (the
contribution of transfer, of the producer index and of the fallback); solutions via
fallback; the B-at-448 robustness re-runs; applications, exact checks, library
certifications, planning expansions and warm-cache wall time; the producer index
acquisition cost.

Scope of the solve comparison. It tests contract-directed planning with certified
symmetries, the MR-transfer metarule, the enumerated producer index and the B
fallback. It does not exercise the edit and abstraction operations of section 6
(R2, R3); those are covered only by the structural gates below. A gain in the solve
comparison is not evidence for R2 or R3.

Structural gates for the DSL criterion (tests, all must pass before freezing):

* E1: every operation in the existing 16-definition archive converts; each of its
  effects expressible over its interface is either certified exactly or recorded as
  undecided at the certification size bound (never kept as a post atom). Observed
  locally: 16/16 converted, 7 effects certified, 1 undecided, 60 s.
* E2: at least one certified operation is produced by `substitute` inside an
  existing body (not argument binding).
* E3: at least one operation with a `Rel` or `Op` parameter is produced by
  `abstract` and instantiated with two different arguments, each applicability
  decided by certificate replay.
* E4: an operation built from an acquired operation is itself edited and
  re-registered (generation >= 2) without a language cap.
* E6: vacuous operations (e.g. `circle(midpoint(f0,f1), f0, f1)`) are refused;
  open obligations never yield `proved`; refuted compositions are excluded
  before charging.

Continuation rule: if the primary criterion is not met, the fresh cohort becomes
regression data, the negative result is recorded, and the next frozen change is
evaluated on a newly generated fresh cohort with a new preregistered seed. At most
three fresh cohorts are used before the approach is reassessed in writing.

## 9. What is kept from 10213b0

* Predicate lowering and prerequisites; the exact kernel `certify_body`; FLINT
  identity replay; `exact_zero`; primitive replay; `certify_atom`.
* `library_compression` term machinery (content-sealed definition tables,
  `expand_for_execution`, `generalise`) where the new program format maps onto it.
* Interference controls: frozen inputs, source hashes (here: every loaded project
  module, before and after), `PYTHONHASHSEED=0`, preregistration. Unlike the older
  runners this comparison runs in one process: the producer index certification
  cache and SymPy caches are shared across tasks and conditions, condition order
  follows a Williams Latin square, and timings are reported as warm-cache.

What is new: relation terms with hiding and relation variables; contracts with
obligations as syntax; the composition calculus; certified metarule instances;
higher-order parameters with applicability by certificate replay; substitution
inside bodies; the synthesis search. The JGEX exact-proof route is unchanged in
this iteration.

## 10. Non-claims

Instance-level solutions at exact rational configurations are not universal
theorems. Charged applications are not the same unit in A/B and in N (section 8).
The producer index is an enumeration of primitive programs, not a library learned
from solved tasks. A certified relation definition is not an existence proof. Metarules
are supplied language bias. No task statement, goal template, witness, auxiliary
point or lemma instance derived from these tasks is written into code.
