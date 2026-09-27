# The Task Agent, second round: steering exploration, noise, sequences, and automata from traces

Branch `research/task-agent-product-field-20260926`. Five experiments, each fixed
in `experiments/task_agent/PROTOCOLS.md` and committed before it ran:
P1 in `c39dfad`; P2 and P3 in `ba0b546`; P4 and P5 in `ce16fb3`. The result
files are in `2bf7b7a` (`41552b6` holds only the summariser's P1 comparison
list, which matches the protocol). Every result file was created after its
protocol commit (P1's 1.8 s after `c39dfad`, P5's 33 s after `ce16fb3`); the
cache-key change in `ce16fb3`, made while P1 was running, provably changes no
P1 or P2 decision (one task object lives through each episode). The first round
is `TASK-AGENT-FIELDS-20260926.md`.

An independent audit recomputed all five verdicts and every number in
sections 1-5 from the raw CSVs and found no numerical mismatch; its wording
corrections are incorporated. Section 6.8 says which mathematical claims were
checked twice and which only once.

| | question | preregistered hypothesis | verdict as registered | with the world as the unit |
|---|---|---|---|---|
| P1 | can a field steer exploration? | H1: `optimistic_optimal_goal` beats `frontier_t0` in steps AND in successes within 512 | **supported** | holds in 7/7 worlds that need exploration (p = 0.016, the minimum possible) |
| P2 | the online agent in slipping worlds | H2: at e = 0.2 online is cheaper than the frozen model, both planners | **supported**, but the registered test is biased (2) | borderline: p = 0.023 linear, 0.055 shortest |
| P3 | noise that is not uniform | H3: linear_oracle's gap to the optimum grows, and its lead over shortest shrinks, under drift | **supported**; the reason differs by drift (3) | exact evaluation, no sampling |
| P4 | one model across 46 tasks | H4: the directed policy's advantage over broad exploration shrinks from the first half to the second | **supported** over 24 (world, order) units | **not supported**: 5 vs 2 worlds, p = 0.11 |
| P5 | the automaton from labelled traces | H5: random negatives ≈ no automaton; near-miss and counterexample traces beat it | **supported**; (a) only narrowly | (b) holds in 8/8 worlds at every N |

## 1. P1: a field that can steer exploration

Inside `OnlineTaskAgent` the exploration policy is consulted only when the
product graph holds no accepting path, so the delivered task-conditioned field
had nothing to be about (first round, section 4). `optimism.py` gives it
something: every untried action leads to a virtual node worth W. The field is
then never empty while an untried action is reachable (R-max, Brafman and
Tennenholtz 2002, not retrieved).

200 of 368 fresh tasks (seeds 520000+ / 620000+, never used before; the audit
confirmed the CSV uses exactly this set) have no accepting path at budget 512.
On those, with failures counted at 4096:

| policy | median steps | success ≤ 512 | ≤ 1024 | ≤ 4096 |
|---|---|---|---|---|
| **optimistic_optimal_goal** | **123** | **195** | 200 | 200 |
| optimistic_linear_goal | 180.5 | 169 | 195 | 200 |
| optimistic_linear_rmax | 199 | 165 | 190 | 200 |
| optimistic_linear_shaped | 201.5 | 165 | 190 | 200 |
| frontier_t0 | 210.5 | 158 | 189 | 200 |
| optimistic_optimal_rmax | 210.5 | 158 | 189 | 200 |
| task_conditioned_t0 | 233 | 159 | 188 | 200 |
| structural | 261 | 138 | 168 | 187 |

H1: `optimistic_optimal_goal` finished in fewer steps than `frontier_t0` on 139
tasks and in more on 23 (38 tied), sign test p = 2·10⁻²¹, and succeeded within
512 steps on 195 against 158 (37 tasks where only it succeeded, 0 the other way:
McNemar p = 1.5·10⁻¹¹). Per world its mean capped cost is lower in all 7 worlds
that have exploration tasks (2303 has none), by 20 to 444 steps.

Three identities, all now theorems (section 6.5):

* `optimistic_optimal_rmax` and `frontier_t0` produced **identical episodes on
  all 368 tasks**. With every untried action worth exactly the value of
  acceptance, the optimal field is q^(1+d) to the nearest state with an untried
  action, and its tie-break reproduces breadth-first search's first action.
* `optimistic_linear_rmax` is the user's `VirtualFrontierPolicy` (generic,
  `experiments/task_agent/virtual_frontier.py`, commit `24c44da`, written
  independently) multiplied by the constant 1/(1−q): they made the same choice
  on all 12 794 exploration decisions of the `linear_rmax` agent on the P1 tasks
  of worlds 2101 and 2505. So the fresh-70-world study's secondary endpoint
  (G = −20.0 steps per task, world-bootstrap CI [−32.0, −10.2], 65/70 worlds
  analysable, descriptive) measures the policy P1 calls `linear_rmax`. P1 sees
  the same direction (88 vs 32 tasks, p = 3·10⁻⁷) but, on its own 7 worlds, not
  at the world level (5 vs 2, p = 0.14, CI [−77.9, 1.9]); fresh-70 is what
  establishes it at that level, on the unselected generator.
* Weighting the virtual nodes by **automaton progress alone almost never
  changes a decision**: `linear_shaped` differed from `linear_rmax` on 4 and
  `task_virtual_frontier` from the generic field on 13 of those 12 794 decisions
  (the fresh-70 primary endpoint: D = −1.0 steps per task, 91 action changes in
  71 673 decisions). A memory-only weight is constant on the virtual nodes
  reachable without completing a subgoal, and a constant factor cannot move an
  argmax; it can matter only when virtual nodes at two memories are reachable
  (3 183 of the 12 794 decisions), and, at a state with an untried action, only
  if the weight ratio between memories reaches 1/q. `task_virtual_frontier`'s
  exp(progress) gives 1.40-1.65, `shaped` exactly 1/q = 1.11, which is why the
  former changes more decisions.

What moved behaviour is the only variant that uses what the task says about
the world: `goal` weights a virtual node by the L1 distance h, in the world's
own variables, from its state to the next target (`linear_goal` vs
`linear_rmax` 74 vs 36, p = 4·10⁻⁴; `optimal_goal` vs `linear_goal` 129 vs 31).
As written, W_goal = q^(r(m)−1+h)/(1−q) is **not** an upper bound on the value of
an untried action in any of the eight worlds: it is off by one step (h is
measured at the current state, W values the successor) and ignores that one
true step moves the variables by up to Δ = 9, 7, 1, 3, 3, 5, 3, 6 in L1 (worlds
2101 … 2808). The admissible form is proved in section 6.5. Because only ratios
of W enter a decision, the off-by-one alone changes nothing, so in world 2303
(Δ = 1) the delivered `goal` policy already acts exactly as its admissible
version; in the other seven worlds the admissible version is flatter and was not
run.

## 2. P2: the online agent in a slipping world

From the same budget-8192 slip-trained model the exact evaluation froze, the
online agent (which adds states, records transitions and replans) against the
frozen model's exact expectation, failures charged 512, three execution seeds
per task:

| e | planner | frozen success ≤ 512 | online ≤ 512 | frozen mean cost | online mean cost | tasks online cheaper / frozen cheaper |
|---|---|---|---|---|---|---|
| 0.05 | linear | 0.982 | 0.999 | 24.8 | 16.1 | 244 / 124 |
| 0.05 | shortest | 0.983 | 0.999 | 25.9 | 16.2 | 248 / 120 |
| 0.10 | linear | 0.948 | 1.000 | 49.4 | 20.4 | 263 / 105 |
| 0.10 | shortest | 0.950 | 0.999 | 50.9 | 20.3 | 242 / 126 |
| 0.20 | linear | 0.923 | 0.994 | 64.8 | 28.4 | 257 / 110 |
| 0.20 | shortest | 0.932 | 0.994 | 61.6 | 29.2 | 253 / 114 |

H2 holds as registered. **The registered test is biased, though.** It compares
a mean of three Monte Carlo episodes with an exact expectation, and a cost that
is usually t and occasionally 512 is right-skewed: for a two-point law with
failure probability p < 1/3, P(mean of 3 < E) = (1 − p)³, which exceeds 1/2
whenever p < 0.206. On the frozen policies' actual cost laws, a task falls on the
"online cheaper" side with probability about 0.61 even if online and frozen had
the same law, so the "244 / 124"-type counts are not evidence by themselves.

With an unbiased comparison H2's conclusion survives at e = 0.2: sign test
calibrated to the null share, two-sided p = 5·10⁻⁵ (linear) and 9·10⁻⁴
(shortest); paired mean difference −36.4
steps (task CI [−47.3, −26.4]) and −32.3 ([−42.6, −22.8]). With the world as the
unit it is borderline: 7/8 and 6/8 worlds, sign-flip p = 0.023 and 0.055. At
e = 0.05 the calibrated test is not significant (p = 0.16 and 0.051). Almost all
of the difference (> 99 %) comes from tasks on which the frozen model can fail
outright: the online agent's gain is **recovering from model errors**, not
executing faster. On tasks where the frozen policy never fails, online and
frozen costs are indistinguishable.

Online, the linear field beat the shortest-path field on 96/65, 146/82 and
187/96 tasks at the three slip rates. Both are Monte Carlo under common random
numbers, so this comparison is not affected by the bias above.

## 3. P3: noise that is not uniform

Mean expected cost above the SSP optimum, exact, 368 tasks:

| noise | planner | e = 0.05 | 0.10 | 0.20 | 0.40 |
|---|---|---|---|---|---|
| uniform | linear_oracle | 0.171 | 0.179 | **0.192** | 0.249 |
| uniform | shortest_oracle | 0.243 | 0.548 | 1.431 | 5.660 |
| drift_state | linear_oracle | 0.389 | 0.647 | **1.322** | 4.427 |
| drift_state | shortest_oracle | 0.483 | 1.058 | 2.670 | 10.842 |
| drift_global | linear_oracle | 0.351 | 0.596 | 1.326 | 6.263 |
| drift_global | shortest_oracle | 0.694 | 1.618 | 4.758 | 30.656 |

linear_oracle cheaper than shortest_oracle at e = 0.2: 336 tasks under uniform,
289 under drift_state, 281 under drift_global. Both parts of H3 hold, for both
drifts. H3 was registered as two inequalities without a test; the audit's
paired tests at e = 0.2 under drift_state: (a) the gap is larger under drift on
353 of 368 tasks, sign p = 6·10⁻⁸⁵; (b) linear beats shortest under uniform but
not under drift on 55 tasks, the reverse on 8, McNemar p = 10⁻⁹. Under uniform slip the linear
field's excess over the optimum barely moves while e grows eightfold; section
6.3 explains why exactly.

The outcome was predicted; the stated reason was right for one drift only. The
prediction said the linear field would lose its edge because under drift "U does
not appear". At e = 0.2 the committed numbers separate the two ways a gap can
grow:

| e = 0.2 | linear_oracle | SSP optimum | gap |
|---|---|---|---|
| uniform | 18.334 | 18.142 | 0.192 |
| drift_state | 18.504 (+0.17) | 17.182 (−0.96) | 1.322 |
| drift_global | 19.373 (+1.04) | 18.048 (−0.09) | 1.326 |

Under `drift_state` the linear field costs almost what it cost under uniform slip
and 85 % of the gap's growth is the optimum getting better: an agent that knows
a drift direction can use it. The reason is that a direction hashed from the
state is, in expectation over the hash, the uniform kernel to first order
(section 6.3); the numbers hold for e ≤ 0.2 and drift a little further at 0.4.
Under `drift_global` the optimum barely moves at 0.2 and the linear field itself
degrades, as predicted; at 0.4 even the optimum is worse than under uniform slip
(+3.7 steps). Same verdict, two mechanisms.

## 4. P4: one model across a sequence

Twenty-four sequences (8 worlds × 3 orders) of the 46 registered tasks, one
learner from the budget-512 snapshot carried through each:

| policy | mean total steps | first half | second half | tasks needing exploration (sum, halves) | failures |
|---|---|---|---|---|---|
| optimistic_optimal_goal (directed) | **1187** | **784** | 404 | 117 + 17 | 0 |
| optimistic_linear_rmax (broad) | 1249 | 882 | 367 | 75 + 11 | 0 |
| frontier_t0 | 1279 | 929 | 350 | 81 + 8 | 0 |
| structural | 5056 | 3493 | 1564 | 80 + 14 | 12 |

H4: d = steps(directed) − steps(broad); d2 > d1 on 16 units, d2 < d1 on 5
(3 tied, all world 2303), p = 0.027. Supported as registered -- with two
qualifications the audit made precise.

* **The registered statistic cannot tell a shrinking advantage from shrinking
  totals.** If both policies' second-half costs were just their first-half costs
  scaled by λ < 1, then d2 − d1 = (λ − 1)·d1 > 0 whenever d1 < 0, which holds in
  17 of 24 units. The informative test is d2 alone: in the second half the broad
  policy used fewer steps on the same tasks in 16 units and more in 5 (p = 0.027),
  and the observed mean d2 is +37 steps where proportional shrinkage predicts −46.
  Directed exploration maps less (it left 134 task starts without a path against
  86) and pays for it later.
* **The three orders of a world are not independent.** The intraclass
  correlation of d2 − d1 across orders within a world is 0.48 (about 12
  effective units, not 24). With the world as the unit, 5 worlds go one way, 2
  the other and 1 is tied: sign p = 0.45, sign-flip p = 0.11. d2 alone clusters
  much less (ICC 0.05), but no statement about P4 holds at the world level.

Over a whole sequence the directed policy is ahead on average, not significantly
(13 vs 8 units); after Holm correction the three exploring policies are pairwise
indistinguishable and each beats `structural`.

## 5. P5: the automaton from labelled traces

`synthesis.py`: RPNI (Oncina and García 1992, not retrieved) on traces labelled
at every step by the true automaton, alphabet = world states, planning on the
true world graph so only the automaton is being learned. Held-out success from
16 starts per task, on the 272 sequence / all_of / branch tasks:

| N demonstrations | goal_set (no automaton) | rpni_random | rpni_near_miss | rpni_counterexample |
|---|---|---|---|---|
| 2 | 0.019 | 0.039 | 0.119 | **0.344** |
| 4 | 0.017 | 0.043 | 0.123 | 0.253 |
| 8 | 0.016 | 0.052 | 0.117 | 0.208 |
| 16 | 0.016 | 0.048 | 0.112 | 0.189 |

H5 holds. (a) Random negatives stay within 0.032 of the goal-set baseline (CI
[0.015, 0.051], one-sided upper bound 0.048): inside the registered margin, but
narrowly, and `rpni_random` is strictly better than no automaton (21 tasks
better, 0 worse). (b) Near-miss and counterexample traces beat the baseline
(53 and 99 tasks better, none worse, p < 10⁻¹⁵), in all 8 worlds at every N.
The P5 run reproduces row for row, and every inferred automaton is consistent
with its own sample.

The prediction's stated reason was wrong, though its outcome held. The protocol
said nothing in `rpni_random`'s sample contradicts "reach where the
demonstrations ended". In fact a rejected prefix -- often an earlier prefix of a
demonstration that passes the final landmark before the first -- visits a
demonstration's end state in 107, 160, 197 and 234 of the 272 (task, N) cells
at N = 2, 4, 8, 16. RPNI still returns something close to the goal set, because
its merges are driven by what it never sees contradicted along each branch, not
by the whole sample (section 6.7).

The absolute numbers are low -- sequence tasks reach 0.10 even with
counterexamples -- and equivalence on the world is reached on at most one task
per condition. And `rpni_counterexample` gets **worse** as demonstrations are
added: better at N = 16 than at N = 2 on 22 tasks, worse on 89 (p = 10⁻¹⁰), in
all 8 worlds. (The near-miss rates, 0.119 / 0.123 / 0.117 / 0.112, show no
established trend.)

**What causes the decline is not more data but more distinct starting points.**
Interventions on all 272 core tasks, held-out success at N = 2 → N = 16:

| variant | N = 2 | N = 16 |
|---|---|---|
| P5 as run (N demonstrations from N starts, N walks) | 0.344 | 0.189 |
| N demonstrations drawn from only the first 2 starts, N walks | 0.344 | 0.349 |
| 2 demonstrations, N walks | 0.344 | 0.366 |
| N demonstrations, no walks | 0.327 | 0.152 |
| counterexamples from 5 starts each round | 0.488 | 0.353 |
| the loop run to 80 rounds instead of 16 | 0.538 | 0.260 |

Holding the number of demonstration starts at two removes the decline in every
task type; more walks do not cause it; more rounds and counterexamples from more
starts help at both N and leave it in place. Every held-out failure is an early
acceptance -- the hypothesis accepts, on a landmark, before the truth does --
never a missing plan, and the number of spurious exits from the initial state
grows with N (1.88 → 3.81) and predicts failure. The proposed mechanism, not
isolated merge by merge: RPNI's first wrong merge absorbs a progressed node into
the root, after which every demonstration from a new start contributes an
acceptance route that skips the earlier landmarks, and the loop removes about
one such route per round. An independent re-implementation on a different random
sample of 64 core tasks reproduced the registered values exactly and gave
0.317 → 0.134 as run and 0.281 with demonstrations from two starts, all failures
early.

Exploratory and post hoc (the class was chosen after seeing the results): a
learner restricted to landmark automata -- only goal states move the memory,
every other symbol loops, fewest predicates first -- reached 0.756 at N = 2 and
0.958 at N = 16 in the counterexample loop on a 30-task sample, against RPNI's
0.290 and 0.190, and improves with N. The failure is RPNI's hypothesis class on
a world-state alphabet, not the traces. Claiming this needs its own protocol.

## 6. Mathematics of the code

### 6.1 The field is a Laplace transform of a hitting time

Let G be the accepting product states and K the delivered kernel (uniform over
tried actions, modal successor). Memory is monotone and acceptance absorbing in
every automaton here (`core.py` 70-153), so G is closed under K and

    ψ = Σ_t q^t K^t 1_G = Σ_t q^t P_z(τ ≤ t) = E_z[q^τ] / (1 − q),

τ the hitting time of G. So (1−q)ψ is the probability generating function of τ
at q, equivalently P_z(τ < T) for an independent geometric killing time T, and ψ
is the q-potential (discounted occupation measure) of the chain integrated
against 1_G. Its support is exactly the set of product states from which
acceptance is reachable, since every tried edge has weight ≥ 1/A. Checked
against an independently propagated law of τ on every product state at budget
8192 (335 611 states, max error 2.3·10⁻¹⁵) and, at the smaller budgets, on
every task whose start reaches acceptance; 0 support mismatches. At budget 512,
100 tasks have no accepting product state at all (ψ is undefined there, and the
package returns None) and 2 681 dead states in the other 22 tasks with dead
states have ψ = 0 exactly.

### 6.2 What greedy ascent on it optimises

Expanding the generating function over action words,

    (1 − q) ψ(z) = Σ_w Π_i q / |A(z_i)|,    log (1−q)ψ = −E + H,

w ranging over words from z that first hit G at their end, |A(z)| the number of
tried actions, E the minimum word cost with per-step cost log(|A(z)|/q), and
H = log Σ_w exp(−(C(w) − E)) ≥ 0 the log effective number of words. Greedy
ascent therefore trades length against multiplicity; it is also the mode (not
the law) of the optimal controlled kernel of the KL-control problem whose
desirability is ψ (first round). At budget 8192 all 33 non-shortest first
detours are **entropy-driven**: the detour has more words (H larger in 33/33)
and never lower energy E (0/33), and the two successors had equally many tried
actions in 33/33. The zero-temperature rule, greedy on −E alone, is shortest on
366/368 tasks; the delivered temperature is what produces the 33 detours.

A small discount makes greedy ascent shortest, provably: if at every decision
some successor z1 at minimal distance δ has P_{z1}(τ = δ) > q, then greedy picks
a minimal-distance successor, because E_{z1}[q^τ] ≥ q^δ P(τ = δ) > q^(δ+1) ≥
E_{z2}[q^τ] for every farther z2. No counterexample on a q-grid from 10⁻⁸ to
0.999, but the condition is extremely loose -- it certifies no task at q ≥ 0.1,
while greedy is in fact shortest on all 368 tasks up to q = 0.1, on 335 at 0.9
and 265 at 0.999 -- and the set of q where a task's route is shortest is not
always an interval (5 tasks).

### 6.3 Slip as a perturbation of the policy kernel

For a deterministic stationary policy π that reaches acceptance from every
transient product state, uniform slip makes the closed-loop kernel
(1 − e)P_π + eU, and on transient states

    V_e^π = J_π + e·G_π (U − P_π) J_π + O(e²),    G_π = (I − P_π)⁻¹,

(a Neumann series, finite for every e < 1). The mean first-order slopes over the
368 tasks are 17.02 for linear_oracle, 21.14 for shortest_oracle and 16.78 for
the optimum. The linear field starts 0.160 above the optimum at e = 0 (its 31
non-shortest tasks) but its sensitivity to slip is within 1.5 % of optimal;
shortest paths start optimal and have a slope 26 % too steep. So gap_lin(e) ≈
0.160 + 0.235e and gap_sh(e) ≈ 4.36e, crossing at e ≈ 0.039. The linear line
tracks the exact gaps up to e = 0.4 (0.254 predicted, 0.249 exact); for
shortest paths it holds only to about e = 0.05. For small e the SSP optimum
takes only shortest-path actions and has slope 16.78; it breaks the remaining
ties at second order, so it is optimal lexicographically in all Taylor
coefficients, not only the first.

The first-order term is linear in the noise kernel. If the drift action b*(s) is
uniform on the actions for each state (the sha256 hash of `noisy.py`), then
E_hash[D] = U, so every noise-agnostic policy has, in expectation over the hash,
the same first-order excess cost under drift as under uniform slip, while
E_hash[min_π slope_D] ≤ min_π slope_U: knowing a hashed drift can only help.
Measured: noise-agnostic excess under drift_state is 0.99-1.05 of the uniform
excess for e ≤ 0.2 (1.15 at 0.4), and the drift-aware optimum's slope is 12.27
against 16.78. Nothing averages under drift_global (b* = 0 everywhere).

### 6.4 The learner is a random kernel, sampled with optional stopping

For a pair sampled n times, the probability that its modal successor is wrong
has a closed form for both tie-breaks the code uses (first-seen maximum in
`checkpoint.modal_actions` and `StructuralLearner`; (count, −id) in
`core.modal_successors`, `exact_slip.learned_model` and the online agent), exact
against brute force to 10⁻¹⁶. Plugged in at the learner's realised n, it predicts
the number of wrong modal edges within 1.1-1.5 sd for the first-seen rule
(drift_state e = 0.2: 479 ± 20 predicted, 501 measured) and about 2 sd low for
the (count, −id) rule (474.5 ± 19.6 vs 515). The gap has a cause: the explorer's
choice of what to try next depends on outcomes, so n is a stopping time, not a
constant. Pairs left at one sample slipped more often than 1 − p (z ≈ +3 to +4),
pairs at two samples less often (z ≈ −3.7, −4.5), and unconditionally the rate
is exactly 1 − p (z ≈ 0); the effect vanishes for a learner that picks actions in
index order. Fixed-n multinomial formulas are therefore right only
unconditionally. These wrong edges are what the frozen model fails on in P2 and
what the online agent repairs.

### 6.5 Optimism

* **Identity with nearest-frontier search.** Inside `OnlineTaskAgent`
  (exploration only when no accepting state is known), the optimal R-max field
  is q^(1+dist(z, F))·W with F the states that have an untried action; at a
  frontier state both policies take the lowest-index untried action, elsewhere
  both take the lowest-index first action of a shortest known route to F, which
  is exactly what breadth-first search in increasing action order returns. It
  fails only if acceptance is reachable (never, inside the agent) or if the
  field is reused after the modal graph changes without the cache noticing
  (below).
* **Scaling.** With g = 0 the linear field is linear in the virtual-node values
  and the optimal field is positively homogeneous in them; multiplying every W
  by c > 0 changes no decision. This gives the identity with
  `VirtualFrontierPolicy` and the result on memory-only weights in section 1.
* **Completeness.** In a finite deterministic world, greedy optimistic
  exploration with any positive W stops only when no untried pair is reachable
  in the model; the model-reachable set is then closed under the true edges, so
  every pair reachable from the current state has been tried. Each excursion
  terminates: the optimal field strictly shortens the distance to F, and the
  linear field satisfies ψ ≤ qW < W (so an untried action at the current state
  is taken at once) and max_a ψ(succ) ≥ ψ(z)/q elsewhere, so values rise and
  cannot cycle. All eight archived worlds are one strongly connected component,
  so exploration tries every pair; a three-state irreversible world shows
  strong connectivity is needed.
* **Admissible goal weights.** With Δ the largest L1 change of the world state
  over true transitions and L(m) the fewest states that take memory m to
  acceptance, every true successor (t, m') of a non-accepting (u, m) satisfies
  D*(t, m') ≥ L(m) − 2 + ⌈h(u)/Δ⌉: the first memory change needs ⌈h/Δ⌉ steps,
  and the rest need at least L(m) − 1 letters. So
  W_adm = q^(L(m) − 2 + ⌈h/Δ⌉)/(1 − q) bounds the value of an untried action,
  and the bound is attained. Checked on all 2.85 million true (state, memory,
  action) triples of the P1 and registered tasks: 0 violations, tight in every
  world; the code's W_goal is violated on 270 826 P1 triples, in all eight
  worlds. L = r on every state here.
* **The cache.** `OptimisticFieldPolicy` reuses its field while the number of
  tried pairs is unchanged. That is sound in a deterministic world or with the
  `VersionedLearner` of `online_slip.py`, and unsound in a slipping world with a
  plain learner, where a modal successor can change without a new pair: there
  4 of 4 test episodes diverged from a fresh computation. No reported run is
  affected; the docstring now says so.

### 6.6 Sequences, and what a unit is

The model after k tasks is a random kernel that depends on the order, and the
three orders of one world share its geometry; section 4 gives the consequence.
The same holds for tasks within a world in P1, P2 and P5, which is why the
verdict table reports world-level results beside the registered ones. With 7-8
worlds no Holm-corrected secondary comparison can reach 0.05 at the world level
(the smallest sign-flip p is 2⁻⁶ or 2⁻⁷); at the task level, 12 of 13
secondaries survive Holm in P1, 2/2 in P3, 3/6 in P4, 38/38 in P5, and in P2 7/7
with the registered sign test but 3/7 with the calibrated one.

### 6.7 What traces of one world can identify

Let W be the set of paths of the true world graph and L the task language.
Every object P5 computes -- traces, labels, samples, hypotheses, held-out
outcomes, the `equivalent` verdict -- depends on the task only through L ∩ W:
any automaton T' with L(T') ∩ W = L ∩ W yields the same run with the same seeds.
So no learner fed labelled traces of this world can identify more than L ∩ W,
whose canonical form is its Myhill-Nerode partition. `synthesis.disagreement`
decides exactly L(H) ∩ W_S = L ∩ W_S for the paths W_S from the evaluation
starts: equivalence on this world from those starts, weaker in general than
L(H) ∩ W = L ∩ W.

That partition is large: it has one class per live product node, n·M classes
(376-2 376), in 271 of 272 core tasks. The four-state SEQ automaton is only the
smallest member of its class, and RPNI's size bias is the only thing that could
favour it. And no P5 sample is an RPNI characteristic sample for either target,
under any scheme and at any N: for T = SEQ(a, b, c) over all world states the
characteristic sample needs strings "a x" for every symbol x, which are not
world paths (b is a world successor of a in 0 of 96 sequence tasks); for the
minimal DFA of L ∩ W it needs a positive trace starting at every solvable state,
while P5's traces start at no more than 17 states. RPNI's identification in the
limit is therefore never in force in P5, and its decline with N contradicts no
guarantee.

### 6.8 How the claims in this section were checked

Two agents, one re-deriving proofs against the code and one recomputing with its
own scripts, confirmed 6.1, 6.3, 6.4, the completeness theorem of 6.5 and the P4
analysis, with corrections incorporated. The main session reproduced
independently: the audit's world-level results (P1 7/7 worlds, p = 0.016;
`linear_rmax` 5/2, p = 0.14; P4 5/2, sign-flip p = 0.11; P2 mean differences
−36.4 and −32.35 with 7/8 and 6/8 worlds; P5's decline 89 vs 22 in 8/8 worlds),
the admissible bound of 6.5 (0 violations, tight, in worlds 2303, 2101 and 2505;
the code's exponent violated 15 871 times in 2303), the identity of
`linear_rmax` and `VirtualFrontierPolicy` (747/747 sampled decisions), and the
decline intervention of section 5. The q-sweep of 6.2 was computed by two agents
independently with identical counts. Computed by one agent only and not
reproduced: the 33/33 entropy classification and the zero-temperature count in
6.2, the null share 0.61 of the P2 test (its two-point theorem is elementary),
and the Holm counts.

## 7. What is not claimed

* P1's worlds are the eight evolution-selected archive worlds; the replication of
  `linear_rmax` on unselected worlds is the user's fresh-70 study, whose
  confirmatory analysis is INCOMPLETE (65/70) and is cited as descriptive.
* The `goal` weights as run are not admissible in any world. P1 does not show
  that the admissible version (section 6.5) would do as well; with a single
  global Δ it keeps a gradient on only 17 % of states in world 2101 (Δ = 9).
* P2's per-task counts are not evidence on their own (section 2); P4 holds only
  with orders as units.
* P5 learns the automaton on the true world graph. Learning both at once was not
  attempted.
* Literature marked "not retrieved" was not opened in this work.

## 8. Next

1. Preregister P1 again with the admissible goal weights W_adm, with a
   per-variable Δ as a second arm, and with worlds as the unit (the fresh-70
   design).
2. P4 with more worlds and the world as the unit; test d2 directly, not d2 − d1.
3. P5: preregister the landmark-class learner against RPNI, and vary the number
   of distinct demonstration starts separately from N.
4. The optimistic policies in slipping worlds, with the `VersionedLearner`.

## 9. Running it

```
python -m experiments.task_agent.run_online --output reports/task-agent-p1-optimism --task-seed-offset 400000 \
    --seeds <half of the worlds> --shard a|b --policies structural frontier_t0 task_conditioned_t0 optimistic_...
python -m experiments.task_agent.summarize_online reports/task-agent-p1-optimism
python -m experiments.task_agent.run_online_slip [--seeds ...]; --summarise reports/task-agent-p2-online-slip
python -m experiments.task_agent.run_exact_slip --noise drift_state --slips 0.05 0.1 0.2 0.4
python -m experiments.task_agent.run_sequential --seeds ... --shard a; --summarise reports/task-agent-p4-sequential
python -m experiments.task_agent.run_synthesis; --summarise reports/task-agent-p5-synthesis
python -m pytest tests/test_task_agent.py tests/test_task_agent_fields.py tests/test_task_agent_synthesis.py -q
```

This worktree is a sparse checkout; `reports/task-agent-*` must be in the
sparse set (`git sparse-checkout add reports/task-agent-exact-slip ...`) for the
P2 summariser, which reads the frozen P3 CSV.
