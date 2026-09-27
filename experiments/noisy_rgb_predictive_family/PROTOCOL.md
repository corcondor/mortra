# Provisional family scheduling: development comparison

This is a local specification committed before any B outcome, not an external
preregistration. Only already-used development worlds 97027000..97027031 and
base/shifted cameras are included. No replacement, fresh selection, or tuning.

## Frozen comparator and execution

A is saved V2 from run 36309862254, commit
3e777cd5274a30e3119c125a932a6bbca98e1830. It is never rerun or edited. The entire
source run must finish before the new comparison starts. B subclasses its
ProvisionalLearner and uses its acquisition runner, sensor, evidence, labels,
statistics, snapshotting, frozen readout and control evaluator unchanged.
Only the runner's constructor binding is replaced, in a new process. B keeps
every history-specific node, edge, candidate set and direct certificate.
Inherited empirical_match/maybe_merge/revalidate_merge remain the authority.

The 31 depth-at-most-two experiments, calibration, stage sizes, fixed statistical
rule, camera/physics/noise, action IDs, and all existing acquisition/evaluation
limits are unchanged. This includes the existing 1,000,000 action / 500,000
exposure / 1,800 second acquisition limits. Resource exhaustion is incompleteness,
not a policy failure. Checkpoints use the original pre-atomic-batch boundary at
50k/100k/250k/500k. Actual exposures/actions and incomplete conditions are shown.

## Signature and identity

The exact family signature is: sorted candidate IDs; NEW flag; already observed
public labels at each of the 31 endpoints (missing is explicit); outgoing action
mask; direct local outcome matrix for candidate-by-suffix (SAME, DIFFERENT,
UNRESOLVED, NOT_COMPARED); and tested suffix set. No history, raw image distance,
truth, certificate ID, or successor-state guess appears in the key. Equal keys
permit scheduling reuse only. History membership is stored separately.

Membership is refreshed on relevant evidence/identity changes, before scheduling,
and exactly at every snapshot. State/certificate/transition records are never
shared or deleted. Candidate IDs remain opaque. Local pair certificates between
representatives can guide scheduling but cannot identify a target history.

## Fixed scheduling policy

- The agenda uses one scheduling unit per current family, and one per
  non-provisional node. Choose an unsaturated unit before a saturated unit;
  within that category choose the least recently served unit, breaking ties by
  the original agenda position. No unit is merged or discarded. This is a
  priority policy, not a guarantee of finite-budget starvation freedom.
- Preserve shortest available probe length, then lexicographically minimize:
  negative number of directly separated candidate-representative pairs;
  whether this family last obtained no progress from this probe; original V2
  probe score; completed family trial count for this probe; opaque action tuple.
  There are no weighted mixtures or new RGB thresholds.
- Progress means candidate exclusion, new representative, or new tree witness.
  After **31** consecutive completed no-progress trials for the exact family,
  mark FAMILY_SATURATED. This scheduling count equals the fixed experiment-set
  cardinality; it is not a new depth or statistical parameter.
- A later new stage-32 direct certificate, representative, witness, or merge
  reopening reactivates saturated families. New certificates do not reset the
  streak of families that are not saturated; otherwise saturation would be
  impossible by construction. No tested suffix is permanently suppressed.
- A family's statistics persist if it temporarily has no members. Changed
  signatures do not inherit statistics from vaguely similar families.

Sharing disabled is a unit-test-only mode: its acquisition actions, evidence,
and original node records must agree exactly with frozen V2 on abstract fixtures.

## Metrics and definitions

All 64 paired conditions are retained, including resource-limited ones. A uses
saved acquisition CPU/actions/exposures, not zero cost. Its original workers ran
up to 8 jobs concurrently; B runs up to 4 on windows-latest, with identical pinned
Python/numerical packages and one BLAS/OMP/MKL thread. CPU comparisons are
descriptive and are not hardware-controlled speed benchmarks.

Probe count is emitted active_probe attempts. Repeated probe count means the
same history and suffix were attempted earlier, even if V2 later cleared the
tested set. Completed B trials are also reported separately. Shared decisions
read at least one available probe's family record from a different history.
An avoided redundant opportunity means B selected a different probe than the
same-node frozen scoring rule and that baseline choice had a recorded family
no-progress result. It is **not** a measured counterfactual exposure saving.

A has no operational families: report that as null, not a fabricated count.
For A and B, also compute exact-signature families post-freeze with the same
definition. B's saved memberships must agree with this reconstruction. Save
node counts, family-size mean/p50/p95/max, pure/mixed families, represented
confirmed/provisional/union classes, exposures and actions per represented
class, heldout and control metrics, active and historical erroneous merge
events, transition errors, CPU, memory, source hashes, and all schedules.

Original model-quality metrics retain the original RGB predictive quotient.
The independent structural audit additionally computes P0/P1/P2/P-infinity using
clean deterministic output plus public goal labels, their exact partition
equalities (including P1==P-infinity), and the RGB-only comparison. These are
evaluator-side finite-table calculations, never learner inputs. Pure families
are not evidence that a learner was entitled to merge them.

Compare registered checkpoint targets and show each arm's actual resources.
Do not equate different early resource stops. For matched reached checkpoints,
report every requested benefit and safety difference. A claim of improvement
requires at least one specified benefit and no worse wrong-unique, erroneous
merge, or transition-error result. Incomplete heldout evaluation cannot certify
non-degradation; report it as undetermined. No task/world exclusion or favorable
checkpoint selection. Per-world paired summaries keep the two cameras paired;
no treating histories or cases as independent worlds. No post-hoc success quota.

Stop after this comparison. Do not implement sensor programs or change B from
its outcomes. Old development, depth-2 audit, and their artifacts stay intact.
