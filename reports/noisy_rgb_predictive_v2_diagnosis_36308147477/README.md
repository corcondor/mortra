# Read-only prerequisite diagnosis

Source: dfabf874a33a6cea324665dee03ae6324203f205.
Actions run: https://github.com/corcondor/mortra/actions/runs/36308147477
Original V1 run: 36301127275. Original acquisition and H/V1 files are unchanged.

All 64 seed-camera records passed. The diagnostic re-executed the unchanged V1
learner against saved statistics only, asserting the complete event stream,
query order, final model, resource counts, and status against original records.
No new sensor operation was performed.

- 18,962,586 exact events replayed.
- 238,000 candidate snapshots, including 27,403 with a true class not yet represented.
- Across existing-representative comparisons at these 27,403 snapshots:
  447,439 DIFFERENT; 234,002 UNRESOLVED; 6 SAME. These are repeated comparison
  instances, not independent state pairs or six demonstrated merge errors.
- Consistency-call-site costs: 738,096 uncached RGB queries, 13,800,784 exposure
  sets, 4,649,196 replay actions. Other acquisition call sites: 922,920 queries,
  17,048,496 exposure sets, 6,999,269 replay actions. Calibration is separate.
- Consistency accounts for 44.736% of the attributed non-calibration exposure
  sets. Repeated cached comparisons add no new sensor cost.
- At recorded unique stage-32 memberships, the exact minimum subset of already
  available suffix certificates ranged from 0 to 14. This is a diagnostic
  minimum set cover, not a prediction of achievable online query savings.

`diagnosis_summary.json` preserves all 64 records. The run's per-condition
artifacts also preserve compressed event-level diagnostics: comparison counts,
last recorded unresolved blocker, first-exclusion suffix usage and exact
minimum suffix subsets. A blocker is not a causal proof that removing that
one pair would suffice to create a new state.

The earlier run 36307998165 failed on Windows path-separator handling before
acquisition. Its logs and diagnostic history are retained. The corrected run
does not modify V1 or its saved results.
