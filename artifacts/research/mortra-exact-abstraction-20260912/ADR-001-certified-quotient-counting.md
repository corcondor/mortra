# ADR-001: Certified quotient counting for task-preserving representations

**Status:** Accepted (implemented and run)
**Date:** 2026-09-12
**Deciders:** repository owner
**Supersedes:** the arrangement described in `mortra-representation-policy-20260912`

## Context

The previous round could acquire an observation representation, certify something
about it, and measure a reduction. Reading the four existing modules against the
brief turned up three defects that each produce a plausible-looking wrong answer,
and one accounting rule that compares two different things.

1. **The reduced search evaluated the wrong quantity.** It read
   `vector[0]` — the first basis coordinate — as the task's evaluation. That is
   the task's quantity only when the candidate observable happens to *be* the
   quantity. For an admitted candidate such as `F31 + c1`, whose certificate
   proves `c1 = 3/4 z0 + 1/4 z3`, the run silently maximised `F31 + c1` instead
   of `c1` and reported it as the answer.
2. **The refusal used an out-of-domain counterexample.** Legality congruence was
   searched over all words up to a depth, so the witness was the pair
   `("", "AAAA")` — words of *different lengths*. The counting DP merges states
   only inside one layer, so a cross-length pair is not a counterexample to
   anything it does. The refusal happened to be correct; the evidence for it was
   not.
3. **The collision task was posed on a state that cannot decide it.** Legality
   was a function of the word while the concrete state was twelve coordinates.
   A refusal against that state cannot distinguish "this observation fails" from
   "the task was posed on too little state".
4. **`total_break_even_reuse_count` mixed targets** — the maximum of a
   naive-baseline compute count and a description count, which are measured
   against different things.

## Decision

Rebuild the counting path around one shared, documented lemma; make the
certificate produce the read-out the reduced run must use; restate the
collision task on a history-sufficient state; and split the break-even
accounting per comparison target.

## Options considered

### Option A — patch the read-out, leave the rest

| Dimension | Assessment |
|---|---|
| Complexity | Low |
| Correctness | Fixes (1) only |
| Cost | Hours |

**Pros:** smallest change.
**Cons:** leaves the out-of-domain refusal and the ill-posed collision task, both
of which produce claims that cannot be defended.

### Option B — one shared DP, certificate-supplied read-out, history-sufficient states (chosen)

| Dimension | Assessment |
|---|---|
| Complexity | Medium |
| Correctness | Addresses all four |
| Cost | One session |

**Pros:** every rung runs the *same* `quotient_counting.layered_count` under the
same legality, so the rungs differ only in what they merge on and the comparison
is between routes rather than between questions. The lemma is written down with
its induction, so what the implementation relies on is inspectable.
**Cons:** the abstract run has to carry a representative concrete state whenever
legality is not vacuous or the read-out is not linear — which shows up as
primitive calls in the represented rung. Kept, and reported, rather than hidden.

### Option C — a separate verified counting engine

**Pros:** strongest guarantees.
**Cons:** duplicates the evaluation basis the brief explicitly says not to
duplicate, and none of the four defects needs it.

## Trade-off analysis

The decisive one is **where the congruence is checked**. Checking across all
depths is stricter and would have refused representations that are sound for the
use they are put to; checking per layer is exactly the domain the DP merges in.
Narrowing the check to the real domain is not a weakening — it is the difference
between a counterexample and an irrelevance. The cost is that the certificate
must state its domain explicitly, which it now does in `domain`.

The second is **carrying a witness state**. Carrying it always is simpler and
always correct; but it calls the original update once per class, putting the
primitive the representation replaces back into the measurement. Carrying it
only when legality is non-vacuous or the read-out is non-linear keeps the
measurement honest, at the price of two code paths.

## Consequences

Easier:
- one place to change how counting works; every rung inherits it
- a certificate now hands the reduced run everything it needs (`readout`), so
  the run cannot quietly evaluate something else
- a refusal names a layer, two words of that length, and the label

Harder:
- tasks must declare enough state to decide their own legality
- `abstract_routes` has two shapes, and callers must use `start_from`

To revisit:
- the observable congruence fallback (no linear read-out) is still a
  depth-bounded search, and is labelled as such rather than proved
- span-class grouping is exact but pairwise; it would not scale to thousands of
  candidates

## Action items

1. [x] `quotient_counting.py`: the lemma, the layered DP, the enumeration
2. [x] certificate: per-layer congruence, per-label legality, certified read-out,
       start-state check, `same_span`
3. [x] `fold_tasks.py`: history-sufficient collision state, verified against
       `build_square_fold_chain` over every word to length 6
4. [x] benchmarks: all rungs on the shared DP
5. [x] break-evens: joint per target, `None` carries its reason
6. [x] self-directed search: rejected-candidate cost, span classes, stated
       tie-break, reuse from store
7. [x] regression tests for multiplicity, legality, layers, domain, read-out,
       zero and variable-coefficient series
8. [x] normal-entry run over four tasks fixed before the run
