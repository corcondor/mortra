# Development Game Construction, 2026-09-25

The user explicitly redirected work away from the disputed Stage-1 experiment
to game construction. This run does not assert a Stage-1 pass. It is the small
development duel, not a generalization or theoretical-identification claim.

## Frozen Components

- OLD: `evaluate_adaptive_refinement.HistoryModel`, supplied historical SHA
  `b7810586055e74af7e7f07e89d911ce27ece84b9ed9dfc1845e565e795a9db9f`.
- NEW: supplied `FutureRefinementCore`, verified against vendor SHA256.json.
- Environment, generation, critique, mutation and acceptance function bodies:
  `evaluate_autonomous_game_design_loop.py`, loaded as definitions only.
- Common observation preprocessing: existing full-game visual renderer from
  `evaluate_visual_state_construction.py` and existing `make_classifier` from
  the Congruence experiment. Both state learners receive only integer symbols.
  There is no new perception training or raw-visual performance claim.
- Shared collector: historical adaptive-refinement OLD HistoryModel and
  IdentificationPolicy. NEW replays exactly its saved observations/actions.
- Reasoning: historical `solve_fixed_field(q=.90)` and expected-successor-value
  action selection from OLD `run_game`. Goal labels are attached after collection.

The historical design script's privileged hidden-state learner is NOT used as
the OLD baseline. The user selected HistoryModel, which has a different input
contract. This is therefore not a numerical replication of the earliest
privileged self-game-design experiment. Likewise, the full design environment
contains blocks and teleporters, unlike the smaller Congruence environment.

## Fixed Run

Seeds 201, 302, 403; three edit proposals per designer per seed. Budgets retain
the adaptive-refinement defaults: 800 shared exploration interactions, 20 play
trials, 100 actions per trial. Both players get identical input per game.
Noise is paired by trial so early stopping cannot shift the other trial's RNG.
Each designer only reads its own play metrics plus the same random baseline.
Opposing-player results and oracle paths are not supplied to mutation/scoring.

All unique candidate games are saved and evaluated, including rejected games.
An independent finite-state BFS checks solvability. Oracle-unsolvable proposals
are rejected, and cannot count as attack wins. This extra validity gate is
identical for both designers. Random play uses an independent process and
exactly one Boolean outcome per trial. The defective legacy evaluator is not
executed or modified. Raw trials are retained.

The original critique and acceptance thresholds are unchanged. Its phrase
"unsolvable" actually refers to failure of the self-player, not a proof of
impossibility. Oracle results are recorded separately. The metric adapter uses
the state counts/edges of each selected state core, and counts unknown-state
readout stops as dead ends. No auxiliary key/switch task is introduced.

## Adapters And Limits

NEW's learned classification rules are applied to a private history-node view
at test time. The training evidence, rules and quotient do not change. This
adapter invokes the supplied classifier; it does not add a history cap or a
belief/planning algorithm. Unseen classifier leaves yield UNKNOWN/None.

The common reasoner needs action probabilities. NEW's observed successor counts
are normalized in the adapter, without modal-successor replacement. Missing
action rows remain absent. OLD's aggregate K convention for a state with no
observed actions is applied only at the downstream reasoner interface, never
inserted as an observed action transition in NEW.

OLD collection CPU includes encoding/exploration, whereas NEW replay CPU does
not. These are explicitly different cost scopes, not a speedup comparison.
Memory is a retained-object estimate, not process peak RSS.

An attack win requires at least one successful trial for the designer and zero
for its opponent, on an oracle-solvable final game. All counts and denominators
are reported; no significance or adversarial-optimality claim is made.

The game editor still uses a developer-written set of legal mutations and
numeric critique rules. Automation of that loop is not invention of arbitrary
game rules, understanding of fun, or human-level game design.

## Evidence

Each run records source hashes, branch/HEAD/status, RNG seeds, shared dataset
hash, every candidate definition, independent random trials, oracle result,
both players' complete recorded action/state trajectories, and edit decisions.
The first trial is plotted for both conditions even if neither succeeds. Every
plotted action is replay-checked against the saved states and final goal flag.
Images are labelled as redrawn recorded actions, not stored camera frames.
