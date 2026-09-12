# Frozen Baseline: Limit Inventory Before Instrumentation

This is a source audit, not a new experimental success. Mathematical target:
`14d18a42c3a7c640a7c54c86c36b7238c419df56`; control checkout at audit:
`4c06d309105495debba6598210e6c42b8f215e69`. The mathematical files are identical.
The running archive-only study (Actions 34725274254) is a separate experiment.

`size(t)` counts every node of the expression tree, including repeated subterms.
It does not count characters, polynomial degree, stored concepts, or proof depth.
Defaults below are `theory_formation.DEFAULT_BUDGET`; effective values are the
frozen frontier experiment's config overrides.

| Limit | Default / effective | Location and stage | Overflow behavior |
| --- | --- | --- | --- |
| Expression size | 7 / 9 nodes | `Theory.invent`, immediately after `Domain.compose` | `size(t) <= budget['term_size']` fails: silently omitted from `pending_terms`, BEFORE rewrite; parent remains marked expanded, no automatic retry. |
| Concept archive | 64 / 128 concepts | `Theory.invent`, after probe and conjecture generation | No new semantic admission when full; expression remains seen and conjectures can still be queued. Seeds enter through `add_concept` without this guard. Not a theorem-library limit. |
| Active concepts | 24 / 32 nominal | `Theory.refresh_active` | Other concepts remain archived, not deleted. Seeds and one representative of each type/top-constructor are unconditional, so this is NOT a strict upper bound if those alone exceed it. |
| Pending expression queue | No hard capacity | `Theory.invent` appends one parent's complete eligible composition batch; pops at most `batch` | Deferred FIFO; duplicate terms can be appended before they are seen. |
| Open conjecture backpressure | `2*batch` / 24 | `Theory.actions`: invent offered only if open count <=24 | Invent deferred, not dropped. A batch can overshoot 24; not a queue capacity. |
| Cycles | 180 / 12000 | `Theory.run` loop and optional CLI chunk | Stop with saved state; remaining work retained. One step executes one computation kind. |
| Per invent step | 12 / 12 queued expressions | `Theory.invent` | Remaining expressions deferred. At most one new parent expanded per invent call. |
| Candidate budget | 1800 / 16000 entries in `seen` | `Theory.actions` before offering invent | Invent deferred permanently within fixed config when full. Can overshoot by a batch; `seen` is a list, not the distinct generated-candidate count. |
| Representation archive | 2 / 4 acquired concepts | `Theory.actions` acquire guard | More acquisitions not offered; concepts retained. |
| Representation dimension | 24 / 24 | `Domain.acquire` passes to `discover_action_observable_basis` (kernel default64) | Independent column beyond limit raises ValueError; closure query unknown, `closure_refusal` retained, no automatic retry. |
| Training proof calls / input size | No explicit global or per-call bound | `Theory.settle`, `Domain.settle` | Whole-run resources limit calls; algebra normalisation has no separate timeout. Unsupported universal logical queries return unknown. |
| Algebra counterexample search | 4096 assignments, each jet in {0,1,2} | `Domain.settle` after identity failure | Exhaustion gives unknown, not proof. May retry after theory growth. |
| Held-out proof input | Harness setting32 nodes per call | `measure_persistent_learning.evaluate`, BEFORE existing prover | `budget_exceeded`, no proof call. Evaluation only, not a learner budget. |
| Engine seconds | 180 / 600 seconds | `Theory.step` times action body; `Theory.run` tests between steps | Stop, state retained. Does NOT include `actions()`, startup, serialization, or evaluation; label is misleadingly `wall_time_budget`. Single call can overshoot. |
| Process watchdog | effective780 seconds per measurement subprocess | `measure_persistent_learning.main`: seconds+180 | External timeout, error recorded; no fabricated completed state. |
| CI job watchdog | 120 minutes in long modes | `.github/workflows/worker-ci.yml` | Job cancellation, uploaded partial artifacts where possible. |
| Theorems / rules / procedures | No numerical archive cap | `Theory.promote` | All retained; `rules()` reads entire rewrite-rule list. `active_rules` is bookkeeping, not retrieval filtering. |

Additional fixed selection/scope bounds on this route:

- `invent` compares at most two probe-matching peers, sorted by size and seeded
  digest. Other potential conjectures are never queued from that term.
- Predicate admission considers the first other predicate for implication.
- `actions` offers the first eligible conjecture, first acquisition, first
  representation with an untried generator, and first unused recurrence.
  Choice is least-visited kind, then estimated operations, then kind name.
- `use_procedure` is offered fewer than two times per scalar recurrence.
- `Domain._finite` accepts 1..64 complete states; actual fold scope has24.
- Probes use only two evaluations/states, but these are NOT certificates.
- Scalar recurrence order search is bounded by representation dimension;
  `discover_linear_observation_recurrence` uses 3*dimension+1 samples and
  exact residual certification. Failure remains unknown.
- Rewriting has no iteration cap: each accepted replacement strictly decreases
  `(tree size, digest)` and is scope-checked. No learned spatial legality.
- Held-out generation uses8 fixed contexts/domain,64 tasks/domain, seed739182;
  questions are never supplied to learning. Larger term bounds may make these
  expressions syntactically reachable. Exact training-query overlap MUST be
  reported, not relabelled as unseen improvement.

## Source-Level Diagnosis to Test

The reported29 algebra parents have size9. Every constructor grows their raw
tree, so every continuation fails the pre-rewrite gate. This does not establish
that every continuation is semantically new, or that simplification cannot
return it below9. Read-only traces will use ONLY rules and concepts available
at the actual expansion cycle, not knowledge acquired later.

No limit or scheduler has been changed in this audit. The planned single-factor
term sweep is9,12,14,18,36 (`ceil(9*m)` for m=1,1.25,1.5,2,4). Archive128,
active32, batch12, representation4/dimension24 and seed remain fixed.
