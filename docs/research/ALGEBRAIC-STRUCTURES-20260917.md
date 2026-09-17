# Algebraic structures built on polynomials: modules, complexes, homology, and acquired procedures

Repository: `corcondor/mortra`. Branch: `codex/algebraic-structures-20260917`.
Base: `a62e931` (the frozen relational geometry DSL, whose own evaluation is separate).
Status: implementation, tests and preregistration. Nothing here is a result.

## 1. Direction

Polynomials are used not only as equations to evaluate but as the starting point
for structures and for maps between structures:

polynomials -> rings and presented modules -> maps with certificates ->
chain complexes -> homology, and the same kernel / image / quotient operations
serving geometry (tangent spaces, Grassmannians) and topology (homology,
persistence). The goal for MORTRA is a layer in which such structures and the
maps that preserve them are exact objects with certificates that can be composed,
searched over and reused.

## 2. What is implemented

`math_os_prototype/algebraic_structures.py` (exact over QQ; every elimination update
counted):

* sparse matrices; column reduction with the column-operation record; kernel with
  the certificate `A K = 0`, full column rank and `rank A + cols K = n`; image;
  cokernel complement;
* presentations `coker(A) -> coker(B)` given by `F`: the map descends iff `F A = B S`
  for some `S`; `solve_presentation_map` finds `S` or reports that none exists;
* chain complexes with the certificate `d d = 0`; homology `ker d_q / im d_{q+1}` with
  representative cycles; chain maps with `d F = F d`; induced maps on homology;
* chain homotopy equivalences `(F, G, h, h')` with `G F - id = d h + h d` and
  `F G - id = d h' + h' d`, checked exactly, and their composition;
* simplicial chain complexes;
* the elementary reduction along an invertible boundary coefficient (reduction
  lemma), returned with `F, G, h` and checked exactly;
* persistence of a filtered complex (standard column reduction), the rank invariant
  computed independently, and the graded `k[t]`-module presentation
  `t^b k[t] / (t^(e-b))` of the bars;
* dual numbers `k[e]/(e^2)`, the Jacobian from first-order evaluation, and the
  Zariski tangent space `ker J(p)` of the scheme cut out by the given polynomials,
  with the check that `p` lies on it;
* Plucker coordinates of 2-planes in 4-space, the Plucker relation, and the pairing
  whose vanishing detects that two planes meet.

`math_os_prototype/algebraic_reduction_search.py`: reduction moves on a mutable
complex with every update, reindexing and priority-queue operation charged, and
the lift of representatives back through the recorded moves.

`math_os_prototype/algebraic_minimal_models.py`: the certified minimal model
(zero differential; over a field every finite complex reduces to one), reached by
five supplied move orderings (`min-fill`, `top-first`, `bottom-first`,
`short-boundary`, `few-cofaces`), by exploration (successive halving over the
orderings on the task, comparing cost at equal numbers of moves, every probe
charged), or by an ordering chosen by a one-split rule learned from the system's
own reductions of training complexes.

`math_os_prototype/algebraic_cohort.py`: task-only generators of Vietoris-Rips
2-skeleta of noisy integer point clouds, and the reference Betti numbers from
python-flint ranks (independent of the solver's elimination).

## 3. Connections, checked by `tests/test_algebraic_structures.py`

1. Homology is kernel modulo image: circle, disk, sphere and torus give the expected
   Betti numbers, and the representatives are cycles.
2. The kernel certificate holds, and a presentation map descends exactly when a
   certificate `S` exists (a non-descending map is refused).
3. Three reduction moves compose, by the composition formula, into one certified
   homotopy equivalence that preserves the torus homology.
4. Homology is functorial: `H(F2 F1) = H(F2) H(F1)`, and `H(G1 G2) H(F2 F1) = id`.
5. Every reduction strategy agrees with the independent flint reference and lifts
   valid, independent representatives.
6. The Jacobian from dual numbers equals the symbolic Jacobian.
7. Geometry DSL loci (a rank-nullity consistency check): the evaluator's solution of a
   generated relational task lies on every goal locus, a nonzero gradient gives a
   1-dimensional Zariski tangent space and a rank-2 pair gives 0.
8. Persistence: the barcode equals the independently computed rank invariant on a
   grid of intervals, and the graded dimensions of the `k[t]`-module equal the Betti
   numbers of each stage.
9. Plucker coordinates satisfy the relation, scale by `det g` under a basis change,
   and their pairing vanishes exactly when the four spanning vectors have a
   nontrivial kernel.
10. Every ordering and exploration reach a minimal model of the same size with correct
    Betti numbers; an operation cap is enforced; every executed move has the minimum
    live key of its ordering; the homotopy certifier refuses mismatched or invalid
    complexes; duplicate simplices are collapsed.

## 4. Measured development facts (development seeds only; not claims)

Measured after the pre-freeze review corrected the priority-queue refresh (every pair
whose key changes is re-queued; a test asserts that each executed move has the
minimum live key) and after every structural update, move record, lift, complex copy
and feature computation was charged.

* Betti numbers with representatives: collapsing free faces before computing
  homology used fewer counted operations than direct computation on 24 of 24
  development complexes (seed 20260917301; 183,097 against 196,220, ratio 0.93,
  queue operations included). An earlier statement in this document that direct
  computation was cheaper was an artifact of the incomplete queue refresh and is
  withdrawn.
* Minimal models: all orderings reach the same model; their algebraic work is nearly
  equal (on seed 20260917301, min-fill 143,545, bottom-first 143,505, top-first
  149,808). The per-task oracle would save 3.9% on average (median 3%, maximum 12%);
  rules learned on half the tasks cost 0.991 and 1.014 of min-fill on the other half.
  Including queue bookkeeping, bottom-first costs 0.81 of min-fill; that difference is
  queue work, not algebra. Exploration pays for its race (1.3 to 2.7 times min-fill).

## 5. Preregistered evaluation

Seeds: the fresh-cohort seed and the training seed are derived inside the run from
drand round `R` (default chain, fixed in the freezing commit before publication) with
salts `mortra-algebraic-structures-fresh-1` and `mortra-algebraic-structures-training-1`.
The run refuses: a run outside GitHub Actions, a non-integer round, a round not
published after the commit that fixed it, any loaded project module that is untracked
or differs from HEAD, a seed equal to a development seed or to the other seed, and a
fresh task identical (points and radius) to a training or development task. The first
workflow_dispatch of this configuration at the freezing SHA is binding.

Cohort: 48 complexes from `generate_model_tasks` (shape uniform over five shapes,
40-110 integer samples, radius at a quantile uniform in [0.03, 0.12], at most 6,000
cells). Every answer is audited with python-flint: Betti numbers equal flint ranks;
number of representatives equals each Betti number; every representative uses cells of
its degree, is a cycle, and the representatives are independent modulo boundaries
(flint rank); minimal models additionally have zero remaining differential. An
exception during a condition is recorded as a failed claim.

Primary question (structure-preserving reduction as a computational operation): for
Betti numbers b_0, b_1 with representatives, is computing after certified collapses
cheaper than computing directly, at the declared count of operations (every entry
update, reindexing, move record, lift, queue push and pop)? Improvement is claimed
only if all hold: binding; loaded modules unchanged; no overlap; zero incorrect answers
in every condition of the run; both conditions solve every task; the collapse total is
lower; and the upper end of the 95% bootstrap interval (10,000 task resamples, seeded
by the fresh seed) of the ratio of totals is below 1.

Secondary questions, reported without a claim:

* minimal models by min-fill (default), by the acquired ordering rule (training runs
  every supplied ordering on the training complexes and fits a one-split rule to their
  algebraic work; nothing is explored during training), by exploration (successive
  halving on the task, all probes charged) and by every fixed ordering: ratios to
  min-fill in algebraic work and in total work including the queue, the bootstrap
  interval for the acquired rule, wins and losses, the oracle ratio, the rule's
  choices;
* the per-kind cost breakdown for every condition.

Operation cap: 5,000,000 per condition per task; an unsolved task counts at the cap.

Development disclosure: the hypothesis, the generator ranges, the orderings, the rule
form and features (cell counts only), the charging scheme and the cap were chosen after
the development runs with seeds 20260917101, 20260917102, 20260917301, 20260917311 and
20260917401, all of which are refused as fresh or training seeds.

## 6. Non-claims and limits

* The minimal model and its homotopy data are classical linear algebra over QQ;
  collapses are a classical preprocessing step. The claim under test is that the
  certified operations in this layer compose into a cheaper computation on fresh
  complexes, not that the mathematics is new.
* The orderings are supplied; only the selection among them is acquired, and on the
  development cohorts that selection had almost no room to help.
* Operation counts are a declared deterministic cost, not wall time.
* `tangent_space` computes the Zariski tangent space of the scheme cut out by the given
  polynomials; it equals the tangent space of the reduced variety only when they
  generate its ideal near the point.
* Presentation maps are solved over QQ. Syzygies over multivariate polynomial rings,
  semi-algebraic homology (Basu-Karisani) and the gluing of local charts are not
  implemented in this iteration.
* Connection 7 is a rank-nullity consistency check that the solution lies on each
  locus; it is not a new construction method and does not measure transversality rates.
