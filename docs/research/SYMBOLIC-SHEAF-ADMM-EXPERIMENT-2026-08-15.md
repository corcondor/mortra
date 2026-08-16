# MORTRA LLM-free Symbolic Sheaf-ADMM Experiment

Date: 2026-08-15

## 1. Research question

Can exact symbolic reasoners coordinate and self-organize without an LLM while
preserving native proof correctness?  More specifically, can the local-to-global
mechanism of Sakana AI's Sheaf-ADMM be transferred from learned latent vectors to
typed proof obligations?

Primary sources:

- Paper: [Self-Organizing Multi-Agent Intelligence via Learned Sheaf-ADMM](https://arxiv.org/abs/2605.31005)
- Official code: [SakanaAI/sheaf-admm](https://github.com/SakanaAI/sheaf-admm)
- Pinned commit: `1e2b5d648361802234348b0b1a7fb3a222128e7d`

The pinned commit is still `origin/main` as of this experiment.  Its official test
suite was reproduced separately: 38 collected, 38 passed.  This verifies the
released implementation, not the paper's trained Sudoku/maze scores.

## 2. Mathematical translation

For symbolic agent `i`, let `P_i` be its finite typed predicate-channel basis.
Its private search preference is `x_i in R^|P_i|`.  An edge `e=(i,j)` exists only
when one agent exports a predicate that the other imports.  The edge stalk is the
shared predicate basis, and the restriction maps are weighted coordinate
projections:

```text
F_i,e : R^|P_i| -> R^|P_e|
F_j,e : R^|P_j| -> R^|P_e|.
```

The coboundary and sheaf energy are

```text
(delta_F z)_e = F_i,e z_i - F_j,e z_j
E_F(z) = 1/2 ||delta_F z||^2
L_F = delta_F^T delta_F.
```

The MORTRA control plane follows the official scaled update:

```text
x <- prox_f(z - y; rho)
z <- argmin_z gamma E_F(z) + rho/2 ||z - (x + y)||^2
y <- y + x - z.
```

For the quadratic local objective used here,

```text
f_i(x_i) = 1/2 ||x_i - p_i||^2,
```

the x-update is closed form.  The z-update is solved exactly, channel by channel:

```text
(rho I + gamma L_F) z = rho (x + y).
```

This matches the `prox` linear system in the official unrolled-CG z-solver.  MORTRA
uses an exact NumPy solve because this experiment is small and does not need
backpropagation through an under-solved CG trajectory.

## 3. Truth plane and control plane

Continuous consensus must not decide mathematical truth.  MORTRA therefore has
two strictly separated planes:

1. Control plane: x/z/y decide which typed proof obligations receive finite
   communication and search budget.
2. Truth plane: a fact is accepted only if the producing symbolic solver replays
   a native certificate from already accepted premises.

An invalid agent can have high priority and still cannot add a fact.  ADMM,
confidence, averaging, and majority vote never bypass certificate replay.

## 4. What is learned

The neural encoder/decoder and gradient-trained restriction maps from the paper
are not used.  They are replaced by Beta-Bernoulli updates over replayed proof
flows:

- rule structure: `(agent role, multiset of premise predicates, conclusion predicate)`;
- edge structure: `(producer role, consumer role, shared predicate)`.

The learner never receives problem text, problem ID, point/set labels, numeric
answer, or an answer oracle at inference.  Rule names are not features.  A unit
test renames both rules and entities and requires the learned structural weight
and proof to remain valid.

## 5. Protocol

| Split | Episodes | Purpose |
|---|---:|---|
| train | 90 | learn only from replayed proof flow |
| dev | 60 | choose the smallest transfer budget attaining the best dev solve count |
| final confirmation | 300 | disjoint labels/numbers, more distractors, frozen policy |

The three typed domains are Euclidean line relations, integer divisibility, and
set inclusion/disjointness.  Each episode requires certificates from at least two
agents.  Test entities and numbers do not occur in train/dev.  The selected budget
was one certificate per round.

Compared variants:

- independent agents;
- strict global exchange of every valid certificate;
- unprioritized global blackboard under the same budget;
- learned global blackboard;
- static local sheaf;
- learned local sheaf.

## 6. PDCA trace, including the failed run

The first 300-episode run produced only `200/300` for learned sheaf.  All 100
geometry episodes failed after the distractor count increased.  The proof trace
showed that the same perpendicular fact could fill both premises of
`common-perpendicular`, creating many reflexive `parallel(line,line)` facts.

This was not repaired with a text or problem-ID condition.  The theorem schema was
made mathematically explicit by adding the typed non-degeneracy premise
`distinct(line_1,line_2)`.  A new confirmation split with a new seed range was
then run.  The initial result remains in:

- `data/symbolic-sheaf-learning-experiment-initial-2026-08-15.json`

The final confirmation is not presented as a pristine one-shot benchmark because
the failure class informed the schema repair.  It is a post-repair confirmation.

## 7. Final confirmation result

Source: `data/symbolic-sheaf-learning-final-confirmation-2026-08-15.json`

| Method | Solved / 300 | Replayed | Communication |
|---|---:|---:|---:|
| independent | 1 | 1 | 0 |
| strict all-certificate exchange | 300 | 300 | 12,243 |
| budgeted blackboard | 40 | 40 | 4,702 |
| learned global blackboard | 300 | 300 | 1,484 |
| static local sheaf | 300 | 300 | 2,286 |
| learned local sheaf | **300** | **300** | **1,424** |

Learned local sheaf reduced communication by 88.37% relative to strict exchange.
Learning reduced local-sheaf communication from 2,286 to 1,424 while preserving
the same 300/300 solve count.

The sheaf-specific gain over the learned global blackboard is small:

- total messages: 1,424 vs 1,484;
- mean paired difference: -0.20 messages per episode;
- sheaf wins / ties / loses: 25 / 275 / 0;
- paired bootstrap 95% interval for the mean: `[-0.28, -0.12]`.

Thus the experiment supports local symbolic coordination and capability
preservation.  It does not support a claim that Sheaf-ADMM is dramatically better
than a learned centralized scheduler on these tasks.

## 8. Fault and generalization controls

- Invalid goal-asserting agent: learned sheaf still solved and replayed 300/300.
- False proof acceptance: 0.
- Invalid certificates rejected after scheduling: 299.  One was never scheduled
  because a valid goal certificate finished first.
- Randomized, disjoint entity labels/numbers across splits.
- Rule-name renaming test passes.
- `para/perp/cong` theorem matching now enumerates the finite symmetry orbit, so
  proof validity no longer depends on the lexical order of point names.

## 9. Scientific conclusion

The controlled result establishes the following limited claim:

> Exact symbolic agents with partial local views can exchange typed,
> certificate-checked facts over learned restriction edges, reach all held-out
> goals in this finite proof benchmark, preserve replay correctness, and use far
> less communication than exhaustive exchange without any LLM.

It does not yet establish:

- the paper's neural Sudoku/maze accuracy;
- improved IMO-AG-30 score over the current external 17/30 union;
- end-to-end learning of restriction maps by gradients;
- asynchronous or Byzantine-optimal consensus;
- superior accuracy over the learned global blackboard.

The next external experiment must connect Newclid/GCLC native proof obligations
to the same local stalks and beat 17/30 under the same timeout with independently
replayable native proofs.  Until then, the external coordination gain remains
unmeasured.

## 10. Reproduction

```powershell
python -B -m unittest discover -s worker/backend -p "test_symbolic_*.py"
python -B worker/backend/test_geometry_proof_hypergraph.py
python -B scripts/experiment_symbolic_sheaf_learning.py --test-start 50000 --phase local-view-final-confirmation --output data/symbolic-sheaf-learning-final-confirmation-2026-08-15.json
```

## 11. External follow-up (2026-08-16)

The next experiment has now been executed.  A structural JGEX-to-GCLC
translation was accepted only when a native GCLC proof and an independent exact
JGEX polynomial replay agreed on the symmetry-canonicalized typed goal.

- baseline: `17/30`;
- strict cross-engine result: `18/30`;
- replayed external exchange: `2012_p5`;
- false proof acceptance: `0`.

The complete protocol, negative results, equal-dispatch control, and claim
boundary are recorded in
`docs/research/MORTRA-REAL-SYMBOLIC-COORDINATION-EXPERIMENT-JA-2026-08-16.md`.
This is a certified cooperative cascade, not yet learned decentralized
Sheaf-ADMM over intermediate proof obligations.
