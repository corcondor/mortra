# Noisy RGB predictive/provisional V2

## Scope and freeze

This is a development protocol fixed before V2 environment outcomes, not an
external preregistration. V1/H code and artifacts remain unchanged. Canonical
V1 execution is cb61cb548f07243250b1ea07ebb0d8ff46bd9dae; report is
c8afe549a26d5499b9243003452cd833e9fa431d. The attached request and the subsequent
user clarification define the scope. No NN, embedding, hidden state, complete
graph, goal-directed source, new physics, or task-specific learner is added.

Prerequisite A passed on all 64 saved V1 conditions in Actions 36308147477:
18,962,586 exact events, zero new sensor operations. The checked report and
summary live in reports/noisy_rgb_predictive_v2_diagnosis_36308147477/.

Development uses all seeds 97027000..97027031 and both existing cameras.
Development V1 is reconstructed from saved statistics and its exact event
stream, not reacquired. Checkpoint evaluation is new and read-only with respect
to acquisition. Missing historical prefix CPU/memory remain null. V2 starts
from zero. Development outcomes are never called fresh outcomes.

After development, code/protocol/settings are frozen again. An unused range
of at least 16, preferably 32 seeds will be searched and registered separately
before new-world outcomes. Fresh compares unchanged V1 acquisition and V2.
No seed replacement or result-dependent change to the listed settings.

## Fixed sensors, evidence, resources

Use the existing 7x7x3 arena, five opaque actions, 12x12 four-view RGB, existing
noise/texture/exposure/jitter, base and shifted camera (+.32,-.24), calibration
and stages 8/16/32 unchanged. SAME/DIFFERENT/UNRESOLVED are exactly the V1
stability rule. SAME is an empirical decision, not a calibrated epsilon-delta
theorem. No threshold is tuned from outcomes.

Acquisition limits remain 500,000 exposure sets, 1,000,000 replay actions,
1,800 wall seconds. Resource exhaustion means incomplete, not policy failure.
Infrastructure job interruption has its own status. Raw exposures and executed
histories are retained, with costs for reset-and-replay sampling explicitly
counted. Reset itself is not a learned transition.

## Candidates, tree and exploration

Each history retains candidate representatives plus NEW. Only direct
DIFFERENT evidence excludes a representative. SAME and UNRESOLVED do not.
The initial reset history and an identical executed-history replay can denote
the same representative; no true-state token is involved.

Classification starts with the empty experiment and walks local discrimination
tests backed by direct representative-pair certificates. Overlapping branches
are allowed: noisy SAME is not assumed transitive. A new certificate refines
affected leaves only; it never clears all observed transitions. The local
classifier is not the old global E-by-representative scan. The exhaustive 31
tests below are a separate empirical merge certificate, not the primary lookup.

Unresolved histories are provisional nodes. A FIFO worklist executes one
untried action, in existing opaque action order, and one active probe per visit.
Depth 1 precedes depth 2; ties use the existing length/lexicographic order.
Probe scoring uses only cached RGB and observed transition differences among
existing hypotheses. NEW contributes unknown information, never a fabricated
successor/emission. Provisional nodes are reported separately from confirmed
representatives. Promotion requires observed DIFFERENT from every current
representative. Adding a representative reopens affected empirical memberships
because noisy comparisons do not support transitive exclusion.

## Reversible depth-2 empirical merge

The user explicitly authorized public goal/terminal-label equality as an
additional identity condition. V2 therefore uses RGB plus public-label equality
for identity, not strictly RGB alone. V1 remains unchanged. This is not a pure
single-factor comparison of a data structure. The environment has a public
goal boolean but no terminal API; no false terminal value is invented.
Labels are captured only when that endpoint is actually photographed, without
additional hidden replay. The learner receives an equality interface, not a
goal reward. Labels are not used for acquisition priority or probe scores.

The fixed experiments are epsilon, a, and a1 a2: 1+5+25=31. For every sequence,
the fixed RGB rule must return SAME and all available public labels must agree.
Observed outgoing actions must exist at both histories and have no known
contradiction. One DIFFERENT forbids the corresponding merge. One UNRESOLVED
keeps NEW. All still-possible candidates must meet the certificate; an
unresolved candidate is not silently removed to enable merging.

If several representatives satisfy the rule, all remain in the candidate set
with NEW=false. No arbitrary representative is chosen; such a set is not
exported as a deterministic edge. The status is PROVISIONALLY_MERGED and the
identity scope is EMPIRICALLY_EQUIVALENT_DEPTH_2, never TRUE_EQUIVALENT.
Records retain the history, representatives, all 31 SAME certificate IDs,
public-label evidence, evidence version, reversibility and later revocations.
Original histories, RGB and edges are never deleted.

Later directly observed future DIFFERENT evidence revokes the affected merge,
restores NEW and reschedules exploration. A longer distinguishing future may
be observed through normal exploration; it does not increase the fixed active
probe depth. No depth-3 active search is introduced. Empirical depth-2 identity
does not imply equality of infinite futures.

## Checkpoints and external evaluation

Exposure checkpoints: 50,000 / 100,000 / 250,000 / 500,000. Freeze immediately
before the next indivisible RGB batch would cross the target, giving at most
31 exposure-set slack, plus a separately labelled final checkpoint when needed.
Never use later statistics to fill an earlier model. Save input hashes and
verify them before and after evaluation. Evaluation happens after acquisition,
on serialized read-only snapshots; no evaluation experience returns to training.

Per checkpoint report representative/provisional counts, confirmed and
provisional true-class coverage separately, union coverage, candidate coverage,
coverage including a genuinely unrepresented NEW class, wrong unique rate,
unresolved rate, known-transition error, mean candidate-set size, actions,
exposures, CPU, memory. Truth is evaluator-side only. Unique means one candidate
and NEW=false; an existing singleton plus NEW is unresolved.

Held-out input is the existing 200 episodes x 25 actions (5,000 cases), RNG
seed world+1,000,000. The fixed separate evaluation limit is 2,000,000 exposure
sets / 10,000,000 replay actions / 1,800 wall seconds. If interrupted, full
5,000-case rates are null; partial rates include the observed denominator.
Missing frozen prototypes remain UNRESOLVED and are not acquired from the
training environment after freeze.

Partial control uses only confirmed deterministic edges and the existing
solve_fixed_field(q=.90). Missing edges stay missing; the known-edge operator
is substochastic with weight 1/5 per known action, not a completed self-loop
model. No unknown source estimate is introduced. Public goal checks and their
replay costs are recorded separately. A candidate consensus action is usable
only with NEW=false and the same known best action for every candidate. On
disagreement use active visual probes, then stop UNRESOLVED if still ambiguous.
No oracle state fallback. Fixed control horizon 60, independent probe budget
500,000 exposures / 1,000,000 actions / 1,800 seconds. Check final-step success.

Primary plots: represented classes / acquisition exposures and partial-control
success / acquisition exposures. Non-reached checkpoints are missing, not
silently carried forward or assigned failures. These are discrete-budget,
descriptive curves, not universal predictive equivalence claims. CPU includes
instrumentation; development baseline prefix timings are unavailable.

## Execution and retention

GitHub Actions: test and frozen-source gate, fixed first-condition integration
run, then remaining seed-camera-arm matrix, max parallel 8. The first condition
is development seed 97027000/base/V2 and is not rerun in the matrix. V1 baseline
artifacts are read once per condition. Fail-fast is disabled. Full raw artifacts
are separate from compact aggregate artifacts. No local large acquisition.
Retain source/command/runtime, configs, all seeds, raw evidence, events,
certificates, snapshots, evaluation traces, figures, tests and failure logs.
Correcting an implementation error must be recorded; do not tune the algorithm
to improve an observed score. Fresh launch requires a separate fixed manifest.
