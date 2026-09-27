# Noisy RGB candidate-set development gate

Acquisition run: https://github.com/corcondor/mortra/actions/runs/36300223767

Source: 40c5e23f5dbc19c55153d849627a10daa8189f1c.
Read-only independent evidence audit:
https://github.com/corcondor/mortra/actions/runs/36300730576
(e832bb64bd53b1489c0b85534d35f94adcc2ac39).

These are known development worlds, not fresh evidence of generalization.
All eight acquisition processes ended normally, but NO completed state machine
was acquired in either arm. Process completion is not model completion.

| World/camera | H access histories / suffixes | V representatives / suffixes | V unresolved queue |
| --- | ---: | ---: | ---: |
| 95027004 base | 1001 / 0 | 44 / 28 | 27 |
| 95027004 shifted | 1001 / 0 | 45 / 15 | 6 |
| 95027005 base | 1001 / 0 | 45 / 26 | 32 |
| 95027005 shifted | 1001 / 0 | 47 / 22 | 11 |

H exhausted its original 1000 closure passes. Every saved S/E entry, calibration
value, statistics-key order, query metadata and raw-image hash matched the old
run in all four conditions. V exhausted the preregistered 500000 exposure sets
per condition; it was NOT scored as a task failure. No recognition accuracy or
control success is claimed for these incomplete models.

All 21 unchanged-old plus new unit tests passed locally and on Actions.
All four independent raw-evidence audits passed. They reread 2000000 exposure
sets, exactly recomputed saved means/variances and 1231805 pair comparison
records, checked calibration, immutable file hashes, threshold decisions,
zero-candidate creation certificates and actual suffix witnesses. The audits
do not perform new environment interactions. The four audit JSON files are
included under independent_audits/.

The post-freeze evaluator found no false exclusion of a represented true class
and no spurious DIFFERENT witness in these four partial runs. This does not
establish complete state recovery: most of the 200 true predictive classes
were not represented, and provisional assignments earlier in learning could
still collide. See the full denominators in all_results.json.

The development gate passes implementation, information-boundary and evidence
checks, NOT acquisition completion. This is the user's specified gate. The
fresh comparison therefore retains the same confidence rule, source, budgets,
probe depth, camera, arena and action alphabet without tuning to these outcomes.

Before fresh launch, two non-algorithmic integration changes are recorded:

1. Fresh config metadata names the actual phase and seed manifest rather than
   inheriting the old development label from the unchanged baseline config.
2. Full raw artifacts remain immutable. Aggregation downloads separate compact
   result copies, avoiding an all-at-once download of more than 64 GB of raw
   evidence to one runner. This changes transport only, not any observation,
   stopping rule, comparison, or saved full evidence.

A stalled local full-artifact download was stopped with its empty .part file
retained. No acquisition job was cancelled or restarted. Independent raw audits
were instead run on GitHub Actions. Original evidence remains in the linked run.

Scope: finite resettable deterministic physics and stochastic RGB. The measured
limits do not establish impossibility for general 3D games. Relaxing reset,
deterministic dynamics, fixed cameras, finite states and rendering assumptions
remains separate work; none of those assumptions was changed in this comparison.
