# Frozen virtual-frontier comparison: 70 fresh registered worlds

## Status and scope

Execution and artifact verification finished. The preregistered **70-world
confirmatory analysis is INCOMPLETE**, not a policy failure: five fixed worlds
could not produce the complete frozen task set. No world was replaced.

**65 / 70 fixed worlds** completed all four policies: 780 registered tasks,
3,120 episodes. All numerical comparisons below are **PARTIAL / DESCRIPTIVE**,
conditional on these task-generatable worlds. They are not a redefinition of
the 70-world confirmatory sample.

- Run: https://github.com/corcondor/mortra/actions/runs/36220511321
- Executed harness SHA: `d278e48425ff7a1de382e6b671767a88d3ea9494`
- Frozen algorithm SHA: `24c44da50aac2c084a91fdd9f6754f0429da9350`
- Earlier report-only SHA: `3b69e943531e7d3b182442e43a245f0cdbdcc65a`
- World seeds: every integer from 73000000 through 73000069, inclusive.
- Basic task seeds: world seed + 720000; branch task seeds: world seed + 820000.
- Source byte-identity checks passed; **53 / 53 tests passed**, none skipped.
- All genomes, task specs and starting snapshots were registered before any
  policy outcome. The same 512-step model was privately copied per policy/task.
- No algorithm changes, outcome tuning, selected reruns or outlier removal.
- Platform run status was success. This does not override confirmatory INCOMPLETE.

## Task construction availability

The unavailable seeds were 73000012, 73000022, 73000025, 73000028 and 73000069.
Seed 73000028 had only two states in the task-generation learned graph.
The other four lacked an eligible branch construction in that graph.
Seeds 73000022, 73000025 and 73000069 also exhausted the frozen basic-task
attempt limit without producing sequence/all_of quotas.
The complete exceptions, learned graph sizes, categorical diagnostics and
returned partial task specs remain in the registration artifact.
No reduced task sets were evaluated. These are construction/structural outcomes,
not evidence that a policy failed, nor impossibility proofs about the full world.

The new cohort samples the unchanged generator directly, without evolutionary
selection. It is not the same population as the archived selected worlds.

## Performance on the 65 completed worlds

Each world has 12 tasks. Failed episodes cost the frozen 4096-step cap.
Mean capped steps therefore weights worlds equally as well as tasks equally.

| Policy | Successes / 780 | Mean capped steps | Summed CPU seconds |
| --- | ---: | ---: | ---: |
| structural | 745 | 502.401282 | 355.069339 |
| frontier_t0 | 779 | 123.230769 | 173.539816 |
| virtual_frontier | 779 | 103.251282 | 295.138133 |
| task_virtual_frontier | 779 | 102.232051 | 278.827737 |

World-level bootstrap: 20,000 resamples, seed 74000000; percentile 95% intervals.
No task rows are treated as independent inference units.

| World-paired endpoint | Mean | Median | Descriptive 95% CI | Lower / higher / tied worlds |
| --- | ---: | ---: | --- | --- |
| D: task-aware minus generic, steps | -1.019231 | 0 | [-1.966699, -0.241026] | 18 / 6 / 41 |
| G: generic minus frontier_t0, steps | -19.979487 | 0 | [-31.993622, -10.243397] | 32 / 7 / 26 |
| R: task-aware relative to generic, world mean | -0.564497% | 0% | [-1.045931%, -0.147974%] | 18 / 6 / 41 |

Negative differences favor the first policy. Both paired success-rate
differences are zero in every completed world. Task-level D wins/losses/ties
are 36 / 15 / 729, descriptive only.

The relative-effect interval is inside the preregistered +/-5% band on this
conditional subset. A small directional difference and operational closeness
can coexist. **No confirmatory equivalence or improvement declaration is made
for all 70 worlds**, because the registered cohort is incomplete.

## Mechanism

For task_virtual_frontier across 65 completed worlds:

- Exploration decisions: 71,673.
- Genuine task-source variation: 15,966 / 71,673 = 22.2762%.
- Same-state generic-counterfactual action changes: 91 / 71,673 = 0.1270%.
- Changes conditional on signal: 91 / 15,966 = 0.5700%.
- Tasks with a change: 64 / 780; worlds with a change: 27 / 65.
- Total field solve time: 35.101741 seconds.
- Maximum field residual: 1.7763568394002505e-15.
- Constant-source roundoff corrections: 0.

Task information was present, not absent. Its effect on selected actions was
sparse. Behavior did change, and the conditional performance comparison showed
a small step reduction, while its relative CI remained within the practical
band. This separates information, behavior and performance; it does not turn
the incomplete 70-world experiment into a confirmed positive finding.

## Integrity and resources

The aggregate audit read **616,008 per-decision rows** across all four policies.
All 65 world's telemetry counts matched their episode summaries, and every
reported task-caused action change differed from its same-state generic
counterfactual. No terminal-memory/success mismatch and no cap violation were
found in the 3,120 saved episode rows.

Maximum recorded process peak RSS: 74,600,448 bytes. This is a cumulative
high-water mark within a shard, not isolated per-policy memory allocation.
Fourteen five-world shards ran at most four at a time. Policy order was fixed;
timing comparisons are engineering diagnostics. No resource interruption occurred.

## Preserved evidence

- `registration/`: preregistration, immutable configuration/seeds, source hashes,
  all-world manifest and availability summary. The registration ZIP additionally
  contains every genome, task list and exact starting snapshot.
- `summary/`: original aggregate report/JSON, paired world/task CSVs, all completed
  episode rows, mechanism/compute tables, status and telemetry audit.
- `tests.xml`, `tests.log`, `preflight.json`: pre-outcome tests and frozen checks.
- `artifacts/`: all 16 original GitHub artifact ZIPs, unmodified.
- `artifacts.json`: artifact IDs, original digests and verified SHA-256 values.
- `workflow_logs.zip` and `workflow_run.json`: original workflow logs/metadata.

Large traces are in the original world-shard ZIPs. Historical experiments and
the pilot have not been overwritten. This report adds data only; the algorithms
remain at the frozen development implementation. The study stops here.
