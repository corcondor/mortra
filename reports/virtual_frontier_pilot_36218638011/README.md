# Virtual-frontier development pilot: completed, implementation frozen

Run: https://github.com/corcondor/mortra/actions/runs/36218638011

Executed commit: `24c44da50aac2c084a91fdd9f6754f0429da9350`.
Base commit: `6f9fc5018dd067fa693afb3b4d3ad1cfa04485e6`.
Branch: `research/task-agent-product-field-20260926`.
Protocol: `docs/research/TASK-VIRTUAL-FRONTIER-PILOT-20260926.md` at the executed commit.

No algorithm, weight, threshold, task or success criterion was changed after
observing the pilot. This report/data-only commit does not change the executed
source. No 70-world run was started.

## Scope and verification

Smoke world 2101 completed first, followed by 2202, 2303, 2505 sequentially.
12 fresh task specifications per world, 48 tasks total, four policies each:
192 episodes. Basic task RNG seeds are 720000+world, branch RNG seeds are
820000+world. Every episode starts from a private copy of the same canonical
512-step snapshot; generators use the 8192-step snapshot. Episode cap is 4096.

41 tests passed, including unchanged historical tests, one-world registered
checkpoint reproduction, the same-learned-graph/two-task action-change test,
unknown-successor access guards and exact task-off/generic equivalence tests.
All baseline paths and previous registered outputs remained unchanged.

Independent readback checked all 192 episode rows against 39,411 exploration
telemetry rows: no discrepancies in exploration/signal/change counts.
No final-memory/success disagreement was present. All six changed choices had
strict, non-roundoff score reversals. The maximum saved field residual was
1.5543122344752192e-15. Constant-source roundoff corrections: zero.

## Mechanism endpoint (task_virtual_frontier only)

| Quantity | Result |
|---|---:|
| Exploration decisions | 5,761 |
| Decisions with frontier source variation | 1,626 (28.2243%) |
| Selected action differs from same-state generic counterfactual | 6 (0.1041%) |
| Tasks with at least one changed decision | 4 / 48 |
| Worlds with a changed decision | 2 / 4 |
| Runtime relative to frontier_t0 | 1.68350x |
| Whole-process high-water memory, maximum across stages | 69,021,696 bytes (65.8242 MiB) |

The generic counterfactual is computed at the SAME current learned model and
task memory, not from an independent trajectory. Generic and task fields use
the same K_plus and a single LU factorization with two right-hand sides.

Changed decisions: world 2101 task 1 once; world 2202 task 1 twice, task 7 once,
task 8 twice. These are ALL and condition-then tasks. World 2303 needed no
exploration on its 12 tasks. World 2505 had 1,139 signal-bearing decisions but
zero changed actions; source variation alone is not counted as conditioning.

## Descriptive performance only

Capped-step means include every episode; failures cost the full 4096-step cap.
No statistical performance success criterion was imposed on this pilot.

| Policy | Success | Mean capped steps | Episode wall seconds, total |
|---|---:|---:|---:|
| structural | 45/48 | 449.3750 | 28.4792 |
| frontier_t0 | 48/48 | 153.0833 | 16.9440 |
| virtual_frontier | 48/48 | 130.1875 | 28.7145 |
| task_virtual_frontier | 48/48 | 130.5417 | 28.5252 |

Primary contrast: task weighting cost 17 additional steps across the same 48
tasks, or +0.35417 steps/task. One task improved, one worsened, 46 tied in capped
steps. Paired world mean differences (task minus generic): 2101=0,
2202=+1.41667, 2303=0, 2505=0. This pilot does not establish a performance benefit
from task source weighting. It establishes a genuine, but infrequent, change in
exploration action caused by that weighting.

The pre-pilot mechanism/engineering gate passed. No large experiment has been
launched. Implementation and protocol are frozen at the executed commit. Any
later 70-world study needs a separately frozen registration with WORLD-level
paired inference and virtual_frontier as the primary causal control.

## Preserved artifacts

`artifact.zip` is the ORIGINAL downloaded Actions artifact, not a regenerated
experiment. It contains all per-decision JSONL, episode JSON/CSV, test XML/log,
task specs/hashes, source snapshots/hashes, configurations, seeds and run logs.
Selected small files are also exposed next to this report for direct inspection.

GitHub artifact ID: `10898232199`.
ZIP SHA-256: `de3c44d969c1062d454a21462db86d7d0286048fdf43e9f9dd2b4227c65596a9`.
The downloaded bytes matched GitHub's artifact digest before inspection.
Original compressed size: 1,116,743 bytes. Tests and experiments ran on GitHub
Actions; no local experiment or historical-result deletion was performed.
