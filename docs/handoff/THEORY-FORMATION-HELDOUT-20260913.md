# Held-Out Model Declaration

Code freeze: `0e66e613f4d6ca783e5342575a94cfc6b15c7c8d`.
The A/B Actions run completed before this configuration was added:
[34717633700](https://github.com/corcondor/mortra/actions/runs/34717633700).
The source code, tests and workflow are unchanged in this follow-up commit.

The new exact model is a five-position bounded counter, with saturating
increment/decrement and reflection. Saturation makes two actions non-invertible;
this differs from the permutation actions used in development. The generic
finite-table adapter was implemented and tested before this model was declared.
No target identity, observable to acquire, expected basis, recurrence coefficients
or next action is included. The only sensor is the counter's position.

This is a small developer-declared held-out model, not a blinded external
benchmark or a claim of broad mathematical generality. It was not executed before
this configuration-only experiment. No implementation changes may be made to
improve its result while still counting the run as this held-out experiment.
Unknown, refusal, exhaustion and failure remain valid recorded outcomes.

The workflow executes A/B/C with the same fixed code, using separate empty
archives for each model. Each archive is resumed in a second process. This tests
the generic exploration mechanism on C; it does not test transferring a theorem
from A/B to C. Cross-domain learned-knowledge transfer remains unimplemented.

## Fresh A/B Evidence

Artifact:
[10305900996](https://github.com/corcondor/mortra/actions/runs/34717633700/artifacts/10305900996).

- Existing q-directed regression: 351 passed, zero failed/skipped; normal,
  stored reuse, collision-free refusal and reuse-only refusal passed.
- Theory guard tests: 22 passed.
- A/B: new certificates and counterexamples were independently replayed;
  archive retention, source hashes and paired ablations passed.
- A: six fewer prover calls on shared completed queries. Engine time was
  5.389 seconds with learned rules versus 3.875 without. This is not a net
  runtime improvement; rule matching has a cost.
- B: eight repeated certified-closure constructions were avoided; measured
  reacquisition alone cost 5.001 seconds in the no-representation-reuse condition.
  Engine totals were 2.224 seconds with reuse versus 7.303 without it.
- Both passed the comparative minimum criteria; B did not reduce term/conjecture
  pruning. Its measured benefit was avoided closure construction/certification.

The figures describe these exact bounded runs, not scaling laws or long-term
intelligence growth. The long-term goal remains active.
