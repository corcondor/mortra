# Archive and Term Interaction: Stage2 Result

The joint relaxation produced no additional held-out solutions, representation
spaces, or maximum dependency depth within the fixed budgets. It did produce
a small, attributable expression-reduction benefit on two unseen algebra
queries. This is autonomous reuse of an elementary learned identity, not a new
mathematical algorithm, a new theory, or an overall speedup.

## Fresh Evidence

- Repository: `corcondor/mortra`
- Branch: `codex/theory-formation-20260913`
- Mathematical SHA: `14d18a42c3a7c640a7c54c86c36b7238c419df56`
- Control SHA: `631d5058975943368b5bc2440384970cc0d27c59`
- [Actions run34733054750](https://github.com/corcondor/mortra/actions/runs/34733054750)
- Job103659332723: success,33m25s
- [Artifact10310675896](https://github.com/corcondor/mortra/actions/runs/34733054750/artifacts/10310675896)
- Artifact archive:46,991,595bytes; GitHub digest
  `74c441c0b3a0d96bbe50165166d7d3cb382e668f771504809f6ee556640a3a8c`
- Downloaded evidence:
  `C:/Users/81808/.openclaw/reports/archive-term-interaction-20260913/actions-34733054750`
- Preregistered protocol: `docs/handoff/ARCHIVE-TERM-INTERACTION-20260913.md`

No Python or workflow implementation changed for stage2. Only two experiment
plans and documentation changed before dispatch. During normal execution there
were no supplied candidates, helper quantities, target answers or repairs.
All four final states record `human_inputs_after_start=0`. The fixed source and
input seals passed. These records establish this execution protocol, not an
unrestricted security proof against every possible intervention.

Linux x86_64, Python3.12.10, SymPy1.14.0, NumPy1.26.4, pytest8.4.1 and
python-flint0.9.0 are recorded in `environment.json`, along with all installed
dependency versions. Fresh checks passed:351 related tests,22 theory tests,
9 measurement tests and2 capacity-plan tests. Independent replay of the four
learning states performed39,624 checks with zero failures. Replay checks are
not counts of distinct discoveries.

The same Actions run freshly reproduced the separate q-directed baseline:
acquisition from a supplied observable, stored reuse with0 reacquisitions and
0 Task-certifier calls, and collision-free refusal including reuse-only mode.
The refusal records words `AAG` and `AAT` with equal stored observation but
different legality for the next label `T`. This baseline is not counted as
autonomous selection of a research question.

## Frozen Conditions and Comparison

Both capacities used term_size12, seed20260913, held-out seed739182,
12000 cycles,600s cumulative action-body time,16000 candidates, an active
concept target of32, and at most4 representations. The unchanged learner and
measurement commands are specified below. Evaluation copies never returned
held-out questions, oracle answers or ablation results to the learner.

Each domain has64 frozen held-out questions. A question is solved when proved
or refuted correctly. The budget is32 abstract-syntax-tree nodes per exact
prover input, not a total runtime budget or a bound on proof-tree search.
K0, the state before learning, solves40 algebra and48 fold questions.
Unbounded evaluations solve all64 using the already existing exact kernels.
Consequently the measured gains concern reuse under this explicit bound, not
mathematics that the underlying kernels could never solve.

The table reports final states at their actual stopping cycles. Representation
spaces are distinct measured row spaces, not the number of stored records.
Concept depth counts recorded expanded-parent edges; it is not a full operand
dependency graph. Proof depth counts recorded theorem-proof dependencies.

| Quantity | Algebra128 | Algebra256 | Fold128 | Fold256 |
| --- | ---: | ---: | ---: | ---: |
| Final cycle |6505|11832|12000|12000|
| Concepts including seeds |128|256|128|256|
| Acquired semantic concepts |124|252|117|245|
| Expanded acquired concepts |124|219|110|107|
| Theorems |117|126|508|523|
| Representation records / spaces |0/0|0/0|4/2|4/2|
| Maximum concept depth |2|2|1|1|
| Maximum proof depth |3|3|2|2|
| Held-out solved, of64 |51|51|54|54|
| Held-out solved with all learned rules disabled |40|40|48|48|
| Existing exact-prover calls during learning |5934|10877|11349|11383|
| Rule candidates inspected during learning |10752468|24079083|40866793|36786921|
| Exact certification seconds |19.219|30.701|4.130|4.796|
| Action-body seconds |307.494|600.603|61.386|95.408|
| Normal processes and snapshots, seconds |333.800|655.751|103.915|139.324|
| Independent replay checks |5955|10901|11367|11401|

Algebra128 exhausted its bounded frontier. Algebra256 hit the action-body
timeout before12000 cycles, so its final observation is censored: it does not
prove the enlarged frontier is exhausted. Both fold conditions hit the cycle
cap. Equal budget ceilings must not be described as equal completed work.

Algebra256 admitted128 extra semantic concepts;95 were expanded and16 theorems
referenced an extra concept. Fold256 admitted128 extras; none were expanded
before cutoff, but140 theorems used extra concepts as comparison peers.
Neither domain recorded a child concept whose expanded parent was an extra
concept. There were no extra representation IDs. More concepts and theorems
therefore did not produce a larger measured solution set or deeper maximum
dependency chain in this experiment.

## A Concrete Autonomous Reuse Effect

The larger algebra archive stored concept `C-07fdb84f5eff22e0`, representing
`-u-v`, at cycle497. The128 condition did not store it. At cycle8606 the learner
generated conjecture `Q-633428f140f59c2f`; at cycle8633 it certified

```text
u - (v + u) = -v
```

The resulting theorem `T-633428f140f59c2f` cites the acquired concept and the
previously stored `-v` concept. The existing exact ring prover certified a zero
residual for independent inputs. The system stored the identity as a universal
rewrite pattern and an executable `certified_reduction` procedure. Its own
record explicitly says this is a specialized reduction, not a newly invented
general algorithm. Neither this identity nor these concept IDs were added to
the experiment code or initial inputs.

Two later held-out proofs list this new theorem among their dependencies:

| Held-out task | Prover input,128 | Prover input,256 |256 with extra acquisitions disabled |
| --- | ---: | ---: | ---: |
| H-06-associativity |30 nodes|26 nodes|30 nodes|
| H-06-derivation-add |29 nodes|25 nodes|29 nodes|

Each still uses one exact-prover call and was already solved in128. Both are
new expressions, not exact training-query repetitions. The preregistered
ablation removes all17 high-only algebra theorems and their proof descendants,
not only this one theorem. The changed proof dependencies identify the
cancellation rule; the group ablation confirms the additional-acquisition
contribution, without claiming a separately performed single-rule ablation.

The stored theorem's training `reuse_count` is0. This is consistent with its
later uses being on discarded evaluation copies; those uses are explicitly
recorded in the held-out proof dependencies, not fed into resumed learning.

Across all64 algebra queries, total exact-prover input decreases480 to472
nodes, while rule inspections increase239394 to257979. Median answer time
increases20.281ms to22.853ms; median matching time increases19.997ms to22.719ms.
Thus a narrow symbolic-cost improvement is real, but an overall speedup is not.

Disabling the140 high-only fold theorems and descendants also leaves54/64
solved. Fold matching inspections decrease825537 to726201 in the full256
condition; its rule set is not a superset of128's. This must not be presented
as a general benefit of retaining more rules.

## What Was Reproduced, and What Was New?

The fresh all-rules ablations reproduce the previously observed bounded reuse
benefit: algebra40 to51 and fold48 to54. There is no exact held-out/training
query overlap in any of the four final evaluations. The fold learner again
acquires4 representation records spanning2 measured spaces. Its16 recorded
representation uses include recurrence attempts; those attempts are not all
successful. Held-out solving has no stored-space route in this baseline, so
these held-out gains must not be attributed to representation routing.

New in stage2 is the joint archive256/term12 condition and its fresh counterpart
archive128/term12. Comparison with historical stage1 Actions34725274254 verifies
identical mathematical source seals and challenge hashes. Plans differ only
in term_size9 versus12 and the descriptive scope note. Both archive contrasts
have zero additional solved tasks; the primary interaction criterion is
negative within the budgets. The two smaller algebra prover inputs above are
a secondary effect, not evidence that the primary criterion succeeded.

Challenge hashes:

```text
theory-ring        322892f7cb83dfb6ba8e1617b13ddf6dbf32ca01dcdaff6c0937980599ac84d8
theory-fold-frames 96508334b8082635d05e0a2833a545fd0472c60d477f97645c78954492c0b6ab
```

Stage1 and stage2 ran in different jobs. Their timings are not a controlled
cross-job speed comparison. Here the two complete measurement commands took
691s and1108s (1s resolution), including evaluation and diagnostic ablations.
Their sum1799s exceeds the1232.790s normal-process/snapshot sum by566.210s.
That difference contains evaluation and harness overhead, not learner search.
The full2005s job additionally includes setup, tests, analysis and upload.
Certification times in the table are included in action-body time, not extra
time to add to it. Closure and recurrence costs are separately in the artifact.
Peak memory and detailed matching profiles were not newly measured in this
configuration-only follow-up; their previous measurements remain historical.

## Reproduction and Record Locations

The dispatched command was:

```bash
gh workflow run worker-ci.yml --repo corcondor/mortra --ref codex/theory-formation-20260913 -f verification_suite=capacity-study -f target_ref=14d18a42c3a7c640a7c54c86c36b7238c419df56 -f expected_sha=14d18a42c3a7c640a7c54c86c36b7238c419df56
```

Use the control SHA above for exact reproduction, not a later branch tip.
The following are the equivalent invocations from the Actions workspace root.
The actual prepare step runs inside `ci-control`, the two measurement commands
run in a `for capacity in 128 256` loop, and outputs are also sent to log files.
The literal shell blocks are in the pinned workflow, lines260-286.

```bash
export MORTRA_BASELINE_ROOT="$GITHUB_WORKSPACE/target"
python ci-control/scripts/analyze_capacity_study.py --output "$VERIFY_OUTPUT/capacity-study" --prepare
python ci-control/scripts/measure_persistent_learning.py --plan ci-control/configs/persistent-learning-capacity-128.json --output "$VERIFY_OUTPUT/capacity-study/128"
python ci-control/scripts/measure_persistent_learning.py --plan ci-control/configs/persistent-learning-capacity-256.json --output "$VERIFY_OUTPUT/capacity-study/256"
python ci-control/scripts/analyze_capacity_study.py --output "$VERIFY_OUTPUT/capacity-study"
```

All commands, exact plans, seeds, sealed sources, oracle, K0, trajectories,
candidate decisions, normal-entry outputs, certificates and ablations are in
the artifact. `capacity-study/verification.json` gives the comparison and paths.
The algebra final states are `128/theory-ring-learn/K08000/state.json` (actual
cycle6505) and `256/theory-ring-learn/K12000/state.json` (actual cycle11832).
Directory names are requested checkpoints, not necessarily completed cycles.
The two fold final states are at actual cycle12000.

## Decision

Stop this configuration experiment as preregistered. Do not launch still larger
capacities or new seeds to seek a positive score. No new index, scheduler,
solver, prover, representation language or self-programmer was implemented.

The evidence supports bounded autonomous acquisition and subsequent reuse, but
not sustained capability expansion from prolonged operation. It does not show
that the small cancellation identity is novel mathematics, or that the finite
fold representation preserves collision-free physical legality.

For the already requested ten-part bottleneck diagnosis and the unimplemented
minimal ordered rule-index proposal, see
`docs/research/THEORY-BOTTLENECK-RESULTS-20260913.md`. That proposal targets measured
lookup overhead, not a promise of new mathematics. The current evidence still
does not isolate a single proven cause of the capability plateau. A larger
corpus or a faster lookup alone must not be presented as solving that problem.
