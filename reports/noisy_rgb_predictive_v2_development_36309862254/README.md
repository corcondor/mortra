# V2 development execution record

Run: https://github.com/corcondor/mortra/actions/runs/36309862254

Execution commit: `3e777cd5274a30e3119c125a932a6bbca98e1830`.
Branch: `research/noisy-rgb-predictive-v2-20260927`.

This file records launch and verified preflight, not performance results.
The run was in progress when this record was written. The first actual V2
condition is seed 97027000/base. The remaining registered matrix starts only
if that condition ends without an implementation error. Resource-limit status
does not fail the implementation gate and is retained as incomplete.

## Verified preflight

- All 64 saved V1 conditions passed prerequisite read-only replay in run
  36308147477. New sensor operations: zero.
- GitHub Actions preflight: 46 tests, zero failures/errors/skips. XML copied
  unchanged from the run artifact.
- Frozen V1/H and original fixed-field source passed the Git-blob identity gate.
- Saved V1 seed 97027028/base checkpoint reconstruction exactly reproduced
  the original 1,632 events, query order, model and costs. The 50k and final
  snapshots were reconstructed without new sensor operations.
- Local and GitHub tests cover all 31 merge experiments, public-label
  agreement, multiple-candidate retention, non-transitive evidence, observed
  future counterexample revocation, no deletion of histories/edges, fixed
  depth 2, no invented unknown transition, and checkpoint input preservation.
- Public-label capture preserves exact original RGB and sensor action counts
  on the fixed transport test. Only photographed endpoints acquire labels.

## Pending analysis

Development: all 32 existing seeds x 2 cameras x V1/V2 = 128 conditions.
V1 acquisition is reconstructed from original saved evidence; V2 acquisition
is new. Partial-model evaluations are independent and never returned to
training. Do not call this a fresh comparison or a completed 128-condition run.

Fresh stage is not launched or registered yet. After development, freeze the
code and protocol, check repository history for unused seeds, then register
at least 16 new worlds x 2 cameras and compare V1/V2. No result-dependent
threshold, depth, budget, physics, camera, seed replacement or goal change.

Full raw artifacts use the `pv2-full-*` prefix. Compact readback artifacts use
`pv2-compact-*`. The final aggregate uses `pv2-summary-36309862254`. Preserve
missing/interrupted conditions and implementation errors; never infer success
from a green workflow alone. Read the saved results before reporting outcomes.
