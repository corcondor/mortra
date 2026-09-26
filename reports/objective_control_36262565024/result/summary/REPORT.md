# Objective-derived exploration readout pilot

8 previously observed fixed worlds; retrospective descriptive pilot, not fresh confirmation
Status: COMPLETE; complete worlds: 8/8

Only exploration readout changes. World, task compiler, learner, terminal sources, and execution planner are frozen.
Deadline optimizes a frontier proxy, not unknown task completion. It introduces no successor prediction.
Doob sampling is a policy change; Doob argmax alone is algebraically unchanged.
Algebraic scaling is a certificate, not a performance treatment.

| Policy | Episodes | Success | Mean capped steps | CPU seconds |
|---|---:|---:|---:|---:|
| fixed_generic | 96 | 1.0 | 22.78125 | 6.021 |
| fixed_task | 96 | 1.0 | 22.833333333333332 | 6.103 |
| doob_generic | 960 | 1.0 | 41.775 | 119.963 |
| doob_task | 960 | 1.0 | 43.215625 | 121.381 |
| deadline_generic | 96 | 1.0 | 25.479166666666668 | 7.335 |
| deadline_task | 96 | 1.0 | 25.78125 | 6.321 |

Process peak RSS is cumulative per world job. Timing includes common reference-field computation even for deadline readout.
Success on the last allowed action retains the original executor's existing boundary semantics.
Confidence intervals resample worlds after averaging repeats within task. No outcome-defined pass threshold is used.
Full numerical certificates, baseline replay checks, action traces and per-decision probabilities are retained.
