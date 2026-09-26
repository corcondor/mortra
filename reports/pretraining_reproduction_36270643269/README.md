# Task-blind pretraining reproduction: behavioral match, numerical gate stopped

Run: https://github.com/corcondor/mortra/actions/runs/36270643269

Executed commit: `dd845c64b3ecfd82a17012b7ca4dabe315597e23`.
Parent report commit: `154f7a62988a52265b17c4dd0ad02839c9e32cc3`.
Original ZIP SHA256: `b483aeb976826ac993a17dde0e43b45e4fbf7b2c86776e22f24566f6f97ccf64`.

## Result

**All 864 outcomes, 72 ordered model snapshots, and every executed action were
reproduced through both the standalone ZIP and canonical MORTRA checkout.**
However, the stricter exact numerical trace gate did not pass. Fresh64 was not
started. This is not a policy failure and not evidence of worse task performance.
No algorithm, tolerance, tie-break, or parameter was changed after this result.

| Check | Standalone | Canonical |
| --- | ---: | ---: |
| Unchanged bundled tests | 35/35 | 35/35 |
| Structural512 reference model attributes and insertion order | 8/8 | 8/8 |
| Historical generic outcomes/steps/exploration | 96/96 | 96/96 |
| Unique episode keys and non-timing episode columns | 864/864 | 864/864 |
| Complete ordered model snapshots | 72/72 | 72/72 |
| Training actions, observations, recorder data | 49,152/49,152 | 49,152/49,152 |
| Evaluation action trace rows | 65,489/65,489 | 65,489/65,489 |
| Training rows with internal numerical differences | 1,420 | 1,420 |

Separately, 99 unchanged canonical tests and 5 new comparison-harness tests
passed (104 total). Both supplied replay audits passed. There were no
accepted-memory/reported-success discrepancies in the 864 episodes per route.

The reproduced development results at training budget512 are:

| Initial training selector | Successes | Mean task steps | Initially has accepting path |
| --- | ---: | ---: | ---: |
| structural | 96/96 | 22.78125 | 77/96 |
| frontier_t0 | 96/96 | 21.270833333333332 | 83/96 |
| virtual_frontier | 96/96 | 17.0625 | 90/96 |

These match the supplied historical development experiment. They are not fresh64
results, and do not establish out-of-development generalization.

All 1,420 differing rows belong to virtual_frontier training. On each route,
1,078 rows differ in generic_scores and 534 in field_residual (these sets
overlap). The maximum absolute difference for each field is
`3.3306690738754696e-16`. Every other trace field agrees. For example, seed73000000,
training step15, action0's score is `0.8426966292134832` in the supplied record
and `0.8426966292134831` on Actions; the selected action remains2.

Standalone and canonical executions agree with one another **exactly**, including
these internal scores/residuals. Their discrepancies against the supplied record
are identical. Thus no discrepancy was observed from canonical integration.

## Runtime and stopping

Python3.13.5, NumPy2.3.5, SciPy1.17.0, pytest9.0.2 match the requested versions.
The original Python reports GCC14.2.0 and glibc2.41; Actions reports GCC13.3.0
and glibc2.39. Compiler/platform/build differences are recorded, but the precise
cause of the few-ulp numerical differences has **not** been isolated. Do not
attribute them definitively to one library or CPU without further evidence.

Standalone wall time:183.869s. Canonical wall time:174.747s. Combined child
CPU:358.702s. Peak child RSS:93,339,648bytes (cumulative process accounting,
not isolated per-policy memory). Full job elapsed:6m44s. The original algorithms
and pretraining module remain unchanged.

The preregistered gate requires exact numerical trace agreement and instructs
stopping on a discrepancy. Accordingly, `fresh_allowed=false` and all64 fresh
worlds remain unevaluated. No fresh success/generalization/adoption claim follows.

## Evidence

- `original_actions_artifact.zip`: unchanged downloaded Actions artifact,
  ID10914934920, 5,147,517bytes,
  SHA256`c75f5e2fef4fe35380682289a9e817db70731c6c00cafb1007d2379d82603613`.
  It retains original bundle files/results, both full reruns, testsXML/logs,
  every snapshot/action trace, and all mismatch rows.
- `verification.json`: saved-artifact-only analysis, including exact runtime.
- `canonical_vs_standalone/comparison.json`: exact cross-route comparison.
- `gate.json`, `source_snapshot.json`, `attempts.json`, `original_integrity.json`.
- `verify_saved_evidence.py`: read-only evidence analysis; invokes no policy.

The Actions failure conclusion denotes the reproduction gate, not a failed
task-solving experiment. The original 864-trial smoke remains development data.
