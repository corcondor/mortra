# Autonomous Game Frontier v1.1: Preregistered Protocol

This protocol supersedes the abandoned essential-gate draft, which was never run.
Source parent: `137d784f32884600a27da4e146db3a77103d665f`.
Frozen research core: `483d1592e5cd0d2b23d474cc79e217b121fd1fbe`.
No files under `experiments/game_frontier_v1/` or its reports are changed.
The old GitHub v1 run deletion was requested before the final preservation instruction;
the local v1 results were not deleted. No further v1 deletion is performed.

## Language and Sampling Distribution

Finite integer-domain variables, opaque integer actions, conjunction guards and
simultaneous finite assignments form a generic executable program. Variables 0/1
are spatial coordinates; additional variables have no semantic names. First matching
rule wins. Out-of-domain or blocked destination rejects the entire assignment.
Unmatched actions are identity transitions. The language can express interactions
without named key/door/portal templates. This is not uniform sampling of all programs.

The initial sampling prior is explicit: 12x12 boards, random interior obstacle density
in [0.05,0.20], 3..8 actions, permuted unit-displacement rules for up to four actions,
random finite extra variable and assignments, and 0..3 additional random rules.
Each seed generates exactly 32 candidates, without outcome-driven regeneration.
Generic mutations edit variables, domains, actions, rules, guards, assignments,
dependencies, priority, topology and reset position. Size-only leaves the rule AST
and nonspatial variables unchanged. Wall and board changes affect only spatial topology.

## Roles and Frozen Core

Designer has world program and registered scalar feedback. Player receives only
opaque observations/actions and task start/target IDs. Evaluator alone holds hidden
states, exact graphs, distances and rule-removal diagnostics. The Python interface
is a data-flow boundary, not a security sandbox against malicious introspection.

The original StructuralLearner and original run_fixed_field_policy are SHA-verified
and executed unchanged. q=.90, tolerance=1e-8, 300-iteration limit and cutoff=1e-7
are historical conditions, not new tunable constants. At each checkpoint K is built
once. Identical target solves may be memoized inside an unchanged readout function
code object. Tests compare memoized vs uncached and direct original execution.

## Tasks and Measurements

Oracle completion precedes task selection. All reachable ordered start-target pairs
with distance>=4 are considered using per-bin reservoir sampling, then stratified
across 4-7/8-15/16-31/32+. Missing quotas redistribute randomly. No task duplicates.
The task set is fixed before learning and reused at every checkpoint. Targets are
public objectives, but an unobserved target is not inserted into the learned model.
One continuous training stream per candidate uses the frozen exploration policy.
No evaluation transition enters that stream. Fingerprints are checked around every task.

Checkpoints are powers of two from 1 through 2048 (Stage 1) or 8192 (Stage 2).
B50/B80/B90 are first measured crossings, not exact acquisition times; missing
crossings are reported as right-censored. D is the trapezoidal integral of 1-S over
log2 budget. Complete ties use seeded random, never a hash. Censored thresholds rank
above finite thresholds but are not reported as the artificial ranking sentinel.

Full-information uses the same task set, learner class, K builder, solver and readout
in a separate evaluation-only model. It is not passed to the training player.
Full-info>=.8 with learned>=.8 is LEARNED_SUCCESS; learned<.8 is EXPLORATION_LIMITED.
Full-info<.8 is REASONER_LIMITED. These are protocol categories, not universal causal
proofs: a partial graph can have different averaging weights and outperform the full graph.

Every rule is separately removed. Task starts remain evaluation reset states even if
not reachable from the world's original reset after removal. Exact reachability and
shortest distances are compared with the original fixed task set. Relevance is the
changed-task fraction. It is reporting-only except the registered nonzero-relevance gate.

## Stages and Gates

Stage 0 runs old correctness tests plus new tests. Stage 1: seeds201/302/403,
three conditions, five generations, six proposals, forty tasks, board<=16.
Stage 2: eight seeds201/302/403/504/605/706/807/908, ten generations, eight proposals,
one hundred tasks, board<=32. No Stage 3.

G0 is a seeded random choice from the 32-candidate pool satisfying >=64 reachable
states, at least two branching states, enough tasks, median task distance>=8,
nonzero relevance and full-info success>=.8. All conditions share exactly that G0.
An empty pool stops the seed; it is not repaired using benchmark outcomes.

Common validity requires complete graph, enough tasks and a relevant rule.
Random selection uses common validity only. Performance and size-only additionally
require full-info>=.8 and final learned>=.8, then maximize D/B80/B90/median successful
steps lexicographically. The parent is an eligible competitor when it passes the gate.
This difference from random selection is deliberate and reported.

Oracle cap250000 and a dense K allocation guard512MiB are resource limits only.
Guarded/incomplete runs are not player task failures. All rejected/limited candidates
are saved. External interruption produces RUN_NOT_COMPLETED. No parameter adjustment
is allowed after outcomes, except documented generator/evaluator correctness bugs.

## Claim Boundary

Human-defined: language, generic mutation operators, sampling prior and protocol.
Automatic: concrete worlds, edits, exploration, graph acquisition, evaluation and
performance-guided selection. No claim of learned mutation language, semantic mechanic
discovery, cross-world transfer, persistent memory or visual perception is made.
Different-world comparisons change task distributions; correlated complexity plots
do not establish which mutation caused a capability change.
