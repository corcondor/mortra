# Abstraction source eligibility under a fixed pair budget

Fresh Linux CI results and the next unresolved selection question are recorded
in [the results report](DSL-ELIGIBLE-SOURCES-RESULTS-20260914.md).

## Starting evidence, not a new runtime acquisition

Base: `c1978ca3f029e18c5444b0d4f503b49b12195c30`, whose code is the
tested `7b37ea25ac174c5f860e33e73d9f0519bf5b3da2`.
Actions 34760174353 showed 59 post-capacity abstraction attempts, 1,602
offered templates, zero detailed evaluations, and no additional solved tasks.
The FIFO feedback repair remains; this change investigates the next obstacle.

A post-hoc development audit of the preserved V2 final sample found 512 rows:
488 single-operation roots and 24 composite roots. There were 1,100 subterm
positions, 556 distinct source trees, and 26 distinct trees with at least two
context operations. The unmodified 3,000-pair schedule produced 36 templates,
none satisfying Theory's existing composition contract.

Comparing the 26 eligible distinct trees took 325 pairs and produced four
contract-admissible templates. The first three checked saved 2,040, 2,040 and
2,592 bits, respectively, on that same corpus, including definition cost and
unchanged round-trip checks. This is a developer diagnosis, NOT a MORTRA
acquisition, NOT held-out evidence, and NOT an input to the next learner.

## General repair and its boundary

The existing anti-unifier, `_spread` pair schedule, utility function, type
checker, proof checker and semantic editor are unchanged. The opt-in
`--eligible-sources` flag constructs their source pool differently:

1. Walk all existing subterm positions, including nested acquired calls.
2. Reject sources with fewer context operations than the existing admissible
   template contract requires (two). Literals and holes contribute zero.
3. Deduplicate exact source syntax, preserving first occurrence order.
4. Run the existing deterministic pair schedule with the same pair budget.
5. Test the existing template contract again; score and certify on the full,
   unchanged corpus, with all occurrences and their evidence retained.

Why the early filter is sound for this contract: successful structural
anti-unification only retains operation nodes shared by both operands or
replaces subtrees with holes. For each retained node and recursively for its
children, the context count is bounded by that in each source. Thus
`count(generalise(a,b)) <= min(count(a),count(b))`. No successful template with
count >= 2 can use a source with count < 2. Deduplicating identical source trees
also cannot remove a distinct template; generalising identical trees already
produces no abstraction. These statements concern exhaustive structural
candidates, NOT a guarantee about a bounded search's ordering or best result.

The generic library accepts an optional source predicate. Callers must provide
a necessary condition preserved under generalisation, not a held-out utility
preference. Theory is the only new caller, with the count condition above.
Its result still requires the original type, scope, utility and proof checks.
No definition, equation, task ID, action label or desired result is embedded.

Source positions scanned, excluded sources, duplicate sources, retained
sources, possible pairs and budget/exhaustion reasons are saved per attempt.
Preprocessing wall time is included in library acquisition; these scan counts
are not hidden behind the smaller pair count. No occurrences are removed from
the learning sample or from the cost/proof calculation.

## Fixed comparison

`configs/theory-eligible-sources-evaluation.json` fixes conditions and cohorts.
The prior 48 tasks (917334/917335) remain regressions. Fresh seeds
919071/919072 are reserved before development evaluation, and all 96 target
specifications are generated before either normal learner starts. No witness
or successful program is supplied to normal learning or query synthesis.

Both learners use `theory-dsl-fold.json`, seed 20260913, FIFO capacity 512,
semantic editing, interval 32, 3,000 candidate pairs, eight definition slots,
300 cycles and 300 internal seconds. Both run 150 cycles then resume.
The only mechanism difference is eligible-source preprocessing. Initial,
same-archive editing-disabled, and same-archive definition-disabled query
conditions are also retained. No capacity or definition-budget sweep is used.

```
python scripts/verify_theory_semantic_edit.py \
  --plan configs/theory-eligible-sources-evaluation.json \
  --output <fresh-output-directory>
```

Development uses a separately labelled `--development-seed 917332` run. Its
outcomes are not held-out results. Changing code requires a separate run.
The old fixed-capacity plan and results are preserved, not overwritten.

## Tests and claims

Tests compare exhaustive admissible template sets before/after the filter,
check the structural count bound on small terms and acquired-call syntax,
verify that occurrences/utility remain unchanged, expose pair-budget
starvation with artificial data, and retain the flag and provenance on resume.
Artificial fixtures are never autonomous discovery evidence.

The main scientific questions remain separate:

- Did new experience after capacity yield an automatically acquired definition?
- Was its relation certified, and was it actually used by later code generation?
- Did another acquisition depend on it?
- Did held-out correctness or total cost improve, with acquisition, matching,
  expansion, verification and persistence included?

Reaching the eight-definition limit must be reported as that limit, not as
exhausting mathematics. Positive compression alone is not capability growth.
Existing finite-frame scope and unused panel-structure definitions remain
unchanged. This repair is developer-written infrastructure, not an algorithm
invented by MORTRA. The cumulative-intelligence goal remains open.

## Completed development run, not fresh generalization evidence

The command above with `--development-seed 917332` completed with unchanged
source seals, no intervention, and no infrastructure errors in 715.728 seconds.
Its parent HEAD is c1978ca; the uncommitted implementation is identified by the
full source seal in `verification.json`, not misreported as that parent's code.
Output: `C:/Users/81808/.openclaw/reports/dsl-eligible-sources-development-v1`.

The old / eligible-source learners acquired 3 / 8 definitions. In the latter,
three acquisitions occurred after capacity, at cycles 44, 50 and 56. Their
three attempts evaluated 120 candidates. At cycle 56 the unchanged budget of
eight archived definitions was reached, so later abstraction was not enabled.
There is no claim that eight concepts exhaust mathematics.

One actual post-capacity chain is:

```
44: D5 [95f4c39b7bc58240](f0)
    = add(represented(R-b8f032907b167b70, word(A,C)), f0)
  -> exact symbolic finite-model proof: D5(f0) = add(f0, neg(F31))
48: automatically generated D5(F22)
  -> rewritten to add(F22, neg(F31))
  -> independently replayed; no represented call in normal execution
  -> no later acquisition sourced from this particular execution
```

This is an executable alias and a certified simplification in the declared
24-frame model, not a new mathematical function or an origami legality result.
The attempt ledger preserves source provenance. Calls rewritten before normal
execution are recorded under semantic uses, not falsely counted as raw macro
calls. Eight source-to-definition records have later edit links, but they are
not eight distinct acquisitions. Definitions acquired before capacity still
produce later acquisitions; however the maximum syntactic definition-call
depth is 2 in the old condition and only 1 in the new condition.

| Development condition | Correct / 24 | Expanded candidates | Query seconds | Complete query process seconds |
| --- | ---: | ---: | ---: | ---: |
| Initial knowledge | 10 | 8637 | 2.749 | 4.145 |
| FIFO, unfiltered source pool | 8 | 9026 | 60.563 | 80.845 |
| FIFO, eligible sources | 7 | 9215 | 86.579 | 120.689 |
| Same new archive, editing off | 7 | 9243 | 86.451 | 124.716 |
| Same new archive, definition calls off | 8 | 9009 | 81.822 | 126.304 |

Eligible sources solve no task the unfiltered condition misses and lose one.
The definition-only ablation restores that task under the same archive and
resource bounds. This is evidence of search competition, not broken references:
the evaluator checks that only definition operations were removed, the archive
is identical, and the initial-language size bound is nonbinding. No evaluation
outcome was used to alter the frozen source policy or to choose another cohort.

Training internal seconds are 71.816 / 119.207; complete training-process
seconds 93.166 / 158.670. Acquisition-only seconds are 11.238 / 9.950, but the
new learner stops acquiring at its definition budget. This is not a comparable
full-run speedup. Independent replay, preprocessing, matching and persistence
remain charged. More definitions and local simplification do not establish an
overall capability improvement here. The feature remains opt-in.

Local regression invocations: 125 DSL/library/semantic/corpus tests passed
(including four new source-budget tests), and 22 Theory guards passed. The
first development fixture used a nonexistent call helper; correcting the
fixture to the existing `use_node` helper preceded the frozen run. That failed
test is not a failed autonomous experiment or part of the reported acquisition.

The existing `worker-ci.yml` verification job will run the reserved 96-task
comparison on the committed code. Its infrastructure timeout is 60 minutes,
increased from 45 based on the measured paired-process cost; the mathematical
budgets inside both conditions are unchanged. Worker/release limits remain
unchanged. The old corpus comparison plan and results remain in the repository.
