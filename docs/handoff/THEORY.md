# THEORY — what the representation layer rests on

The nine points below are the frame. Under each: the statement made precise,
where it lives in the code, and what is actually established today as opposed to
intended. Read with `MORTRA-20260912.md` (what runs) and `NEXT.md` (what does
not yet).

Implementation status is marked throughout:

- **built** — implemented and exercised by the 2026-09-12 run
- **partial** — implemented narrower than the statement here
- **not built** — stated here, not in the code

---

## 1. Concrete system

A task fixes a set of concrete states `X`, a start `x0 ∈ X`, a finite label set
`G`, and a transition `T_g : X → X` for each `g ∈ G`. It also fixes
`legal(x, g)`, the evaluated quantity `q : X → K`, what a length counts, and
what object is being counted.

The state is whatever the task's own predicates need. If legality depends on the
path, the state carries the path; a task may not be posed on less state than its
own legality consults. The collision-free fold task therefore carries the placed
panels, not only the centre and frame.

**built** — `representation_certificate.TaskSpec`; `fold_tasks.displacement_task`,
`sum_of_centre_task`, `panel_step`, `panel_legal_step`. The history-sufficient
legality was checked against `build_square_fold_chain` on every word to length 6.

---

## 2. Observable action

For an observable `f : X → K`, the pullback along a generator is

```
(K_g f)(x) = f(T_g x)
```

`K_g` is linear in `f`, and `K_g K_h = K_{h∘g}` in the order the words compose.
Nothing here is approximate: `K_g` is composition, and the identities below are
polynomial identities in the state variables, not fits.

**built** — the fold action is recovered as exact integer matrices by
`fold_observable_system.measured_step` / `generator_rows`, and the one-step
correspondence between the kinematics and those matrices is checked by
`verify_step` over every reachable frame with a **symbolic** centre.

---

## 3. Task-directed representation

Given the task's `q`, put

```
V0     = span{q}
V_{k+1} = V_k + Σ_g K_g V_k
```

and let `V*` be the fixed point. `V*` is the smallest `K`-invariant linear space
containing `q`, and if `W` is any `K`-invariant space with `q ∈ W`, then
`V* ⊆ W`. So a representation from which `q` is linearly recoverable cannot be
smaller than `V*` **within this class**; see nonclaim 9.1.

**partial.** `finite_generator_problem_dna.discover_action_observable_basis`
already performs exactly this closure — it is handed observables and returns the
smallest generator-invariant linear space containing them. What is missing is
the direct call: the current normal entry enumerates a candidate grammar
(`fold_observable_system.candidate_observables`, 144 candidates in the reported
run) and certifies each, rather than starting from `q`. In that run 125 of 144
were refused on the observable check alone, and the acquisition cost 377 s.
Closing this gap is the whole of `NEXT.md`.

---

## 4. Exact representation

Let `Φ = (f_1, …, f_d)` be a basis of an invariant `V`. Invariance gives
`K_g f_i = Σ_j (B_g)_{ij} f_j` for each `g`, hence

```
Φ(T_g x) = B_g Φ(x)      for every x and every g
```

Point 4 is a consequence of point 3: it is invariance written in a basis. The
matrices are the coordinates of the pullback, so they exist as soon as the space
closes.

**built** — checked as a polynomial identity by the closure prover, recorded as
`identity_residuals_all_zero` and read by
`representation_certificate.transition_check`. Scope: all finite words, linear
closure of the supplied observations. This is a different claim from point 2's
kinematics-to-matrix correspondence, and the two are kept separate in the
record.

---

## 5. Task-sufficient quotient

Invariance alone does not license merging states. Before two states may be
identified, everything the task reads must factor through `Φ`:

```
readout    q(x)          = q̄(Φ(x))
legality   legal(x, g)   = legal‾(Φ(x), g)        for every label g
goal       goal(x)       = goal‾(Φ(x))            where a task has one
start      Φ(x0)         is the state the reduced run begins at
transition Φ(T_g x)      = B_g Φ(x)               (point 4)
```

Two asymmetries matter.

**The read-out is computed, not assumed.** `q ∈ V` is decided exactly by rank on
shared monomial coordinates, and the decision returns the coefficients, so
`q̄(z) = Σ_i c_i z_i` is what the reduced run evaluates. Reading the first basis
coordinate instead is only correct when the candidate happens to *be* `q`; that
was a real defect and is recorded in `MORTRA-20260912.md` §9.

**The domain of the check is the domain of the use.** The counting DP merges
states only inside one layer, so the congruence is searched over words of equal
length only. A pair of words of different lengths is not a counterexample to
anything the DP does. Conversely a counterexample inside a layer is a proof of
failure and the representation is then not used for that task at all — not
ranked low, not used.

A refusal is a statement about that representation on that task. Because the
task carries enough state to decide its own legality (point 1), it is not a
statement that no representation could serve it.

**built** — `representation_certificate.certify`, `span_membership`,
`congruence_check` (per layer, per label), `abstract_routes`. Admissions are
labelled by kind: symbolic decisions hold at every state; congruence searches
hold only to the depth searched, and carry that depth.

---

## 6. Exact counting

Let `~` be the equivalence `Φ(x) = Φ(y)` and suppose point 5 holds. Put

```
c_0([x0])     = 1
c_{k+1}([z']) = Σ_[z] c_k([z]) · #{ g : legal‾([z], g), [T_g z] = [z'] }
```

Then `c_k([z])` is the number of legal words of length `k` reaching `[z]`, by
induction: every legal word of length `k+1` is uniquely a legal word of length
`k` followed by a label legal there, and by point 5 both that legality and the
class of the successor depend only on the class and the label. Hence

```
v_max     = max{ q̄(z) : c_n(z) > 0 }
count_max = Σ_{q̄(z) = v_max} c_n(z)
```

are the maximum of `q` over legal words of length `n` and the number attaining
it. With no legal word of that length, `v_max` is undefined and is reported as
undefined rather than as a number.

The multiplicity rule is the whole content. Two labels reaching the same
successor contribute **twice**. Collecting successors into a set and counting
them once turns a count of words into a count of reachable classes. Macros or
compound labels must not be mixed in as extra branches, or one word is counted
more than once.

**built** — `quotient_counting.layered_count` (the lemma is written out in its
docstring with base case and induction step), `enumerate_count` for the
unmerged statement it must reproduce. The concrete and abstract routes call the
same function under the same legality, so their answers are the same kind of
object. Regression tests for the multiplicity rule, the layer rule and the
undefined maximum are in `scripts/test_quotient_counting.py`.

**This lemma is implementer-supplied general knowledge.** It is not a discovery
of any run and must never be reported as one (nonclaim 9.5).

---

## 7. Reuse

A stored representation may be reused when the new problem stays inside its
certificate: same action system, same coefficient field, same domain, and the
required observables still inside the space the certificate covers. Changing
only the initial state or the word length stays inside — update the initial
vector and whatever follows from it, and do not re-acquire.

Two candidates whose bases span the same linear space are one representation. A
reordering or rescaling of a basis is not a new space, and is decided exactly by
rank (`same_span`). In the reported run 19 admitted candidates collapsed to 3
distinct spaces.

To keep several quantities at once, build the closure from the span of all of
them rather than storing one representation per quantity.

**partial.** `Ledger.admissible_for` matches on the **task name** only —
`certificate["task"] == task_name`. Reuse across a genuinely different task with
the same action, field, scope and observables is therefore not yet keyed the way
this point states; `solve_from_store` takes the first entry admitted for the
named task. Reuse across lengths and across a changed initial state does work
and was exercised (n=14 from the store, 0 prover calls, `acquired_again: False`).
Keying on the full tuple is part of `NEXT.md`.

---

## 8. Utility

Measured separately, never combined into one number:

| measure | where |
|---|---|
| description reduction | `description_compression` — raw, representation, conditional, net, and the task count at which bits repay |
| state dimension reduction | `state_reduction` — raw against representation dimension |
| primitive elimination | `primitive_reduction` — counted at chokepoints; derivative entries and top-level derivative requests kept apart |
| search-node reduction | `search_reduction` — with the unit of each row stated, because the rungs expand different objects |
| sequential-depth reduction | `execution_depth` — recorded, **not** a success condition |
| runtime | `real_cost`, and `measure_routes.py` for repeated uninstrumented timing in fresh processes |
| acquisition cost | `acquisition_cost` — including the candidates that were rejected |
| reuse count | `reuse` — successes, held-out successes, failures |

The ledger keeps a ninth field beside these eight, `certificate_scope`, because
an admission resting on a depth-bounded search is not the same asset as one
resting on a proof, and flattening them loses the distinction the certificate
exists to make.

Selection over these is a **Pareto frontier**: nothing is weighted against
anything else, and there is no total. A representation that loses on description
bits and removes ninety-nine hundredths of a search stays on the first front.
Ties inside a front are broken by one stated rule in one unit — acquisition plus
the cost of the task's own declared workload — and where two units would order
the candidates differently, that disagreement is recorded rather than settled
silently.

Savings are attributed along a stated ladder of measured rungs — naive,
memoised, an existing mathematical route, a generic search improvement, the
learned representation — so the four causes are measured rather than
apportioned. The ladder is the marginal effect of each rung **in that order**,
not a unique causal decomposition.

Costs are separated by condition and never merged: **A** an existing route named
from the start, **B** the whole automatic answer including candidate generation
and certification, **C** reuse of a stored representation.

**built** — `representation_evaluation.{measure, attribute, break_evens,
eliminated_nodes, evaluate}`, `representation_ledger`, `representation_policy`.

---

## 9. Nonclaims

**9.1 Minimal only in the declared representation class.** `V*` is smallest
among *linear* `K`-invariant spaces containing `q`. A nonlinear or otherwise
differently-typed representation is outside the comparison. Nothing here says
`V*` is the smallest sufficient statistic in any wider sense.

**9.2 Finite tests are not universal proofs.** A congruence searched to depth 4
licenses nothing beyond depth 4, and the record carries the depth and the number
of words compared. A counterexample found inside the domain *is* a proof of
failure; the asymmetry is deliberate. Answers computed at lengths that were not
enumerated rest on the certificate, and are labelled that way.

**9.3 Compression is not semantic sufficiency.** A shorter description does not
mean the task's predicates factor through the representation. Point 5 is a
separate obligation and is separately gated; description bits never substitute
for it. Bits can be negative on a single task and the representation still be
sound.

**9.4 Semantic sufficiency is not automatically speedup.** A correct, admitted
representation can be slower than an existing exact route once acquisition is
counted. In the 2026-09-12 run this happened for all three solvable tasks: the
learned representation used 42× fewer nodes and the run still selected the
existing route, because 377 s of acquisition stood against a 9.92 s workload.
That is a correct outcome, and "solved without learning anything" would be the
wrong description of it, since the acquisition was paid in full to reach the
conclusion.

**9.5 Implementing a theorem is not MORTRA discovering it.** The counting lemma,
the closure construction, the certificate conditions and the measurement
machinery are developer work. What a run does on its own is generate candidates,
acquire closures, certify, group spaces, select and reuse. Observed regularities
— maximum `= n` with count `2^n`, and the others in `MORTRA-20260912.md` §7 —
are **conjectures** agreeing at the lengths computed, with no proof for general
`n` and no novelty check performed.

**9.6** A commit, a passing test suite, or a green certificate field is none of
the above. `MORTRA-20260912.md` §8 lists the known defects and §9 the claims
already withdrawn.
