# Noisy RGB candidate-set experiment, protocol VS1

## Provenance and scope

Base commit: e178b2faefb05e6c579e475df935836aa0a01d5e.
Old experiment: Actions 36293621710, executed 7ad519c5dbc3b7443b8f0549262246c1eb2296c5.
The old module, renderer, calibration, statistical score, and reference table
are not edited. This document specifies a new development experiment before
its first outcome. A separate fresh authorization record is committed only
after the development gate. It is not an external preregistration.

This is an operational version space of candidate representative states, NOT
an enumeration of all possible finite machines. Similarity is not transitively
closed. No equivalence theorem follows from the statistical certificates.

## Fixed statistical stability rule

Reuse Statistics.z, noise_floor=0.01 and the original 100 same-history
calibration comparisons, margin 1.18, batch 8, image size 12. T is unchanged.
Each exposure contains all four existing views. Two independent batches per
history at each stage n in (8,16,32) are acquired in separate noise namespaces.
The 8-stage namespace is training-v1; the later namespaces are
vs-training-16-v1 and vs-training-32-v1. Replicate IDs are 0 and 1.

For pair (h,r), suffix e, define six original-score measurements

    z[n,j] = z(summary_n(h+e,j), summary_n(r+e,j)), j in {0,1}.
    lo = min(z); hi = max(z); spread = hi-lo.
    envelope = [max(0,lo-spread), hi+spread].

At stages 8 and 16 the result is UNRESOLVED. At stage 32 only:

    SAME if hi+spread < T;
    DIFFERENT if max(0,lo-spread) > T;
    UNRESOLVED otherwise (including equality).

This is a preregistered empirical stability envelope, not a probabilistic
confidence interval or controlled false-discovery guarantee. It requires all
six measurements on the same side, separated from T by more than their full
observed range. This choice is an experimental rule, not mathematically unique.
No threshold is fitted to downstream outcomes. Equal replay histories are
reflexively identical experiments under deterministic reset physics; this
tautology is recorded separately and does not infer equality of distinct words.

Each terminal pair certificate is immutable and reused only in its run and
camera. SAME means SAME-under-current-tests. No union-find or transitive merge.
All raw RGB, histories, stage/replicate scores and certificate IDs are saved.

## Membership and active experiments

Begin with representative empty history and E=[empty]. A candidate is removed
only by a DIFFERENT certificate for an actually executed test. The 8-stage
candidate set is saved, followed by the 16- and 32-stage sets. Zero candidates
can create a representative only with a stage-32 witness against every current
representative. Multiple candidates never create a representative.

For a remaining multiple set Q and a candidate probe e, use only already
cached certificates or already observed deterministic transition predictions.
For each q in Q let C_e(q) contain representatives not known DIFFERENT from q
after e. Missing evidence retains the candidate. Score:

    score(e,Q) = sum_q |C_e(q)| / |Q|.

This is a uniform-hypothesis expected remaining count, not a learned posterior.
It does not require RGB similarity to form a partition. Evaluate all actions
at depth 1 first; among untried probes choose minimum score, then lexicographic
action ID. After all depth-1 probes, use depth 2 with the same rule. No probe
longer than 2. Actual sampling, not predicted evidence, removes candidates.
Save every candidate probe score and selection, and execute target and
representative histories plus the chosen probe. At most A+A^2=30 probes per
membership, including consistency probes. Stop early when unique or empty.

A new global suffix requires an actual DIFFERENT certificate between histories
compatible under previous E. Add the witnessed suffix only. For uniquely
assigned extension histories, test depth-1 then depth-2 futures against the
assigned representative to discover hidden future differences. This is
bounded consistency testing, not a complete equivalence oracle. Recompute
memberships when representatives/suffixes/observed transitions change.
The unresolved queue stores remaining candidates, probes, scores, certificate
IDs, last_evidence_version and retry_count. No retry without changed evidence.

Closure requires unique successor membership for every representative/action.
Then test all representative histories followed by all words of length <=2
against the machine prediction under E. Counterexamples are retained; a
backward witness a+e may extend E only if length<=2 and actually confirmed.
A required longer witness, unresolved fixed point or budget exhaustion is
INCOMPLETE, not a policy failure. No hard equality proof is claimed at completion.

## Fixed resources and stopping

V acquisition, including calibration: at most 1,000,000 replay actions,
500,000 four-view exposure sets, 1,800 wall seconds; 30 probes per membership;
depth<=2. Checks occur before sensor queries and in learner loops. Save partial
data on limits. These are resource bounds, not theoretical impossibility.
H retains exactly 1,000 closure passes, 20 rounds and depth-2 conformance, with
no new internal acquisition cap. Report unequal resource limits and actual cost.
External Actions termination is infrastructure interruption, never policy error.

## Development and fresh gates

Known development seeds 95027004,95027005, each base and shifted=(.32,-.24).
H must match saved threshold, full S/E, query order, query hashes and raw counts.
V must pass mechanism tests and audits, including actual resampling, unresolved
events, active probes and certificates. Completion is not a development gate.
Unexpected exceptions stop progression; results are not tuned to fix outcomes.

Fresh candidates 97027000..97027031 must have no prior use in tracked source,
reports or protocols. Search evidence is retained. No replacement. After the
development gate commit a seed manifest and gate hashes before fresh execution.
32 worlds x 2 cameras x H/V = 128 acquisition runs, independent from zero.
Windows Python 3.12.10, NumPy 1.26.4, Pillow 11.3.0, psutil 7.0.0,
pytest 8.4.1. Actions matrix fail-fast=false, max-parallel=8; BLAS/OMP/MKL=1.

## Frozen evaluation and diagnostics

Only completed acquisition models receive the old 200 episodes x 25 steps
heldout input corpus, rng seed=world seed+1000000. All 5000 prefixes are retained.
Independent heldout-v1 sensor namespace (additional V stages similarly isolated).
V prototypes and learned suffixes/certificates are frozen. Heldout readout uses
the same six-score rule against frozen per-stage prototype summaries; it may
acquire test RGB but cannot add suffixes/certificates/model states. H keeps its
original hard threshold readout. There is no nearest-state fallback.
Evaluation resource limit: 1,800 seconds and 2,000,000 exposure sets, reported
separately; incomplete evaluation has null primary accuracy and partial counts.

Post-freeze hidden audit uses the original observation-preserving quotient.
Report correct-unique/5000, wrong-unique/5000, unresolved (zero or multiple)/5000,
candidate coverage, candidate mean/p95, transition errors and represented
classes. Over-split = excess representatives mapping to a true class;
under-merge is reported literally as duplicate same-class representatives too,
with under-splitting/false-merge reported separately from observed assignments
to multiple true classes. Do not hide this terminology ambiguity.
Log intermediate candidate false exclusions only when the true class was
represented before and absent after; also report true-class-unrepresented.
Audit every DIFFERENT witness and added suffix for spurious true-class splits.
Truth is calculated after freeze and never supplied to acquisition.

Compare 64 paired world-camera rows: completion, wrong-unique, unresolved,
transition error, acquisition actions; state/suffix count, exposures, CPU,
wall and peak memory. Improve/tie/worsen use lower error/cost as better,
higher completion as better. Accuracy comparisons use only paired fully
evaluated conditions with their denominator; incomplete is null, not zero.
Two cameras share a world: no claim of 64 statistically independent worlds.

## Separate post-freeze control

For completed V models only, replay saved representative histories and observe
the public goal flag at their endpoints to label goal nodes. Save every labeling
action; do not use an oracle route. Use the exact existing solve_fixed_field,
q=.90, uniform-action K, argmax with original ID tie breaking, 60-step horizon.
Track model state through its frozen transitions; do not relabel or relearn
using evaluation truth. Record actual public success and complete action trace.
This tests the frozen learned controller, not visual closed-loop relocalization.

## Claim boundary

The tested class is finite, resettable, finite-action, deterministic physics with
stochastic RGB and replayable histories. Reset/replay makes repeated sensor
measurements possible. This does not prove applicability to arbitrary 3D games,
and does not establish impossibility there. Subsequent tests would separately
relax reset, deterministic dynamics, fixed cameras, finite states and the simple
renderer. Do not write that the method cannot be used for Minecraft/FPS games.

No outcome-driven threshold, probe, seed, arena, learner or camera adjustment.
Preserve bugs, stacks and affected conditions separately from research outcomes.
