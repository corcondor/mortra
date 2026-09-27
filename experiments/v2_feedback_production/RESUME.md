# Comparison-only correction, before production outcomes

Original run 36284251256, commit 8aefadc21004cee6842ffb9aac6c09e5e6b62a8b:
53 tests passed. All four actual 5-iteration loops and both extra C-equivalence
evaluations completed. The final trace comparison stopped on seed 79020004.
Production and common evaluation were never started.

Read-only comparison of all 5000 additional rows found differences only at
telemetry.field_solve_seconds (395 rows) and telemetry.policy_seconds (396 rows).
The former was already excluded as runtime; the latter was mistakenly left in
the exact comparator. All action/state/value fields, ordered initial/final
models, evaluation metrics and frozen trials were equal before this correction.

Correct only the comparator to exclude BOTH explicitly named elapsed-time
fields. No numerical tolerance, action, model, policy, game or selection rule
changes. Add a regression test that still rejects any action-value difference.

Resume verification from the completed original artifact, pinned to its source
commit. Retain that run and original artifact unchanged. Do not rerun any of
the 26 completed evaluations. The new gate checks their saved execution audits
and exact equivalence, then permits the original fixed production protocol.
This is a harness error, not a policy failure. Original and resumed attempts
must remain separately identifiable. No production outcomes existed at repair.
