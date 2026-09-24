# Autonomous Game Frontier v1: pre-registered execution contract

Base: `483d1592e5cd0d2b23d474cc79e217b121fd1fbe`.
Branch: `research/autonomous-game-frontier-v1-20260925`.
The base and its original research branch are not edited. No post-9/23 stack is used.

## Frozen player

`evaluate_cross_domain_generalization.py` supplies `StructuralLearner`, its
selection/count/support methods, and `solve_fixed_field` unchanged. Its LF-normalized
SHA-256 is `4075ef5c0f5f6f93bf3ae4049ff9a21dd471d0ccf5a04af6ffda21b40fc5a410`.
Only its original AST definitions are compiled, avoiding the import-time log
overwrite. q=0.90, tolerance=1e-8, maximum iterations=300 and the existing
1e-7 readout cutoff remain unchanged. Dense K construction is unchanged.

The API adapter preserves the modal observed successor score, argmax tie order,
and original missing-action fallback. It checks public is_goal instead of equality
to one caller-supplied state. Multiple training-observed goal nodes are indexed
by the original solver (g is one on these nodes, zero elsewhere). No unseen goal
state is supplied. A single-goal regression compares the original readout directly.
The field is computed once per frozen checkpoint and reused in 30 actual rollouts.

Every candidate receives a fresh player. Training continues uninterrupted through
the registered checkpoints. Evaluation uses separate environment sessions and
does not update the learner or move the training session. Goal cells are
nonterminal. Hazard contact returns position to start while retaining other state.

Player input is an opaque ID for the complete Markov state, an opaque action ID,
and public goal membership. Random labels are sampled without replacement from
a 128-bit namespace, independently per candidate. Evaluation shares the same
mapping within that candidate. No visual perception or latent-state discovery is
being tested. The five-method port is a tested data-flow boundary, not a sandbox
against malicious Python reflection.

## Finite game language

Board sizes are 12,16,24,32. Eight action IDs correspond inside the environment to
four moves, interact, pick, drop and push. The player never receives those names.
The full state contains position, facing, Boolean flags and bounded object states.
Counters are clamped to each object's declared maximum (0..3); modes are 0..3.
Objects can be on-board, carried or consumed. PICK/DROP choose lowest eligible
object ID; INTERACT chooses lowest active ID within Manhattan distance one;
PUSH affects the portable solid object directly ahead. Unavailable interactions
are self-loops. A blocked move still updates facing; this supports PUSH semantics.

Rules are visited exactly once in ascending numeric ID. Conditions see preceding
effects. Movement/PUSH emits ENTER using the entry cell; effects do not emit further
events. Closing an occupied cell does not eject the occupant; subsequent movement
checks destination passability. Teleport/move to blocked destinations has no effect.
Consumed objects cannot be restored by give/move. No stochastic dynamics are used.

Mutations use the 15 registered families in `designer.py`. They are bounded editing
templates, not invented operators. A remote toggle is named temporary_retreat;
the name alone does not prove that a solution needs retreat. Dependency depth is
syntactic write/read graph depth after collapsing cycles, not a proof of effective
solution difficulty. An initial 3x3 open area inside a 12x12 board and an adjacent
goal provide an easy starting game; no solution trace is supplied to the player.

Exact reachable BFS is evaluator-only and capped at 250,000 discovered states.
Exceeding this cap is UNRESOLVED_TOO_LARGE, not UNSOLVABLE, and excludes the candidate
even if a solution was already found. Only completed SOLVABLE status enters
designer feedback; counts, coverage and shortest distances are report-only.

## Fixed design and measurement

Stage 1: seeds 201,302,403; 5 generations; 4 candidates per generation; board <=16;
checkpoints 250,500,1000,2000. Stage 1 uses the analogous final gate at 2000.
Stage 2: seeds 201,302,403,504,605,706,807,908; 10 generations; 8 candidates;
boards <=32; checkpoints 250,500,1000,2000,4000,8000. Stop after Stage 2.

All conditions evaluate each valid, oracle-solvable candidate with 30 rollouts per
checkpoint and a common horizon of 2048 actions. The initial state is identical
across trials. Deterministic repetitions are not independent tasks. Random-policy
control uses 30 independently drawn action sequences per candidate with the same
horizon. Success is counted exactly once, including arrival on the final action.

B80 is the first registered checkpoint with success>=0.8; absent crossing is right
censored, never replaced by a made-up numeric value. Difficulty area is the
unweighted sum of 1-S(B). MORTRA maximizes (B80,difficulty_area), subject to final
success>=0.8; tie is ascending genome hash, and the parent remains eligible.
Random selects uniformly among valid, oracle-solvable candidate occurrences,
without a performance gate. Size-only uses MORTRA's objective but permits only
board expansion, wall changes and goal relocation, preserving objects/rules/flags.
It is a layout-only control, not a reward for larger boards.

Candidate seeds are paired by (seed,generation,slot), with a separate selection RNG.
Parents can diverge after selection. Invalid attempts consume a candidate slot;
they are not silently replaced. Oracle exclusions can give conditions different
numbers of completed player evaluations; report them rather than equate compute.
Duplicate genomes are re-learned from scratch; all occurrences are retained.

Stage 0 is a unit-test gate. Stage 1 is a harness gate: all nine condition/seed runs
must finish, generate solvable candidates, produce valid metrics and exhibit at
least one changing learning curve among their candidates. A flat/failed stage is
reported, not repaired by altering the player. Implementation bugs may be fixed
with an explicit revision and a fresh stage run; outcomes never tune parameters.

Record all candidate outcomes, retained parents, resources, source/config hashes,
actual first-trial trajectories, and per-trial outcome/length/hash. Coverage counts
include self-loop state-action transitions. RSS is a process high-water mark,
not an isolated per-game allocation. Serialized learner bytes are reported
separately and are not called RAM. Censored B80 is separated in all aggregations.

Analysis is descriptive: learning curves, controls, board area, reachable states,
syntactic dependencies, mutation survival, and observed associations. No causal
attribution to a mechanic or semantic/transfer claim is made. No Stage 3, website
deployment, perception research or learned reasoner is part of this experiment.
