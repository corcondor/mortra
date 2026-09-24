# Integrated comparison: retraction and corrected connection

## Retraction

Actions run 35971324989, commit eeecbecffe83dc65878ee469d8c708135255248d,
does not establish failure of MORTRA or of the supplied predictive perception
model. Codex's integration substituted training-prefix positions for reusable
learned world states. The external evaluator also treated identical UNKNOWN
beliefs as equal known states. Interpretations attributing these results to the
user's model are retracted. The integration and evaluation errors are Codex's.

The run is superseded, not a theoretical FAIL. Existing code, results, logs and
artifacts are retained. The source audit remains a diagnosis of that harness,
not a claim about the predictive perception reference's capabilities.

## Corrected contract, fixed before rerunning

The original reference perception, optimized perception, OLD baseline, exact
quotient and belief/reachability algorithms remain byte-identical. A separate
`SymbolWorld` adapter replaces only the prefix-position key with the learned
sensory symbol. For each training tuple `(z, a, z_next)` it records the actual
transition count. Repeated symbol visits reuse the same state. All conflicting
observed successors are retained. A missing action row remains UNKNOWN.

This constructs an empirical symbol transition relation. It does not synthesize
a minimal latent machine or assert that every sensory symbol is a sufficient
statistic. Selected perceptual history features supply the learned distinctions;
no new memory variable, history limit, confidence threshold or goal enters this
adapter. The inherited belief update conditions the observed relation on the
next symbol. This may yield singleton beliefs and must not be presented as a
demonstration of nontrivial hidden-state identification.

The inherited congruence audit is relative to these empirical action operators.
In particular, unique symbol labels can make its quotient the identity. A zero
residual then establishes consistency, not compression or true-world recovery.

## Corrected external measurements

- UNKNOWN, contradictions, and non-singleton uncertain beliefs are not assigned
  to a fictitious known state for partition-error statistics.
- False merge/split denominators and known-assignment coverage are reported.
  The primary paired partition table uses the intersection of known singleton
  histories across all three conditions. Per-condition diagnostics are retained
  separately; missing predictions do not improve the shared-carrier metric.
- Same-observation/different-future cases are still counted across all histories;
  excluded uncertain occurrences and evaluable pair counts are explicit.
- All-step recursive/reconstructed equality is only an implementation check.
  Known nonempty agreement and unknown/contradiction counts are separate.
- Successful action trajectories that equal a training prefix are counted
  separately from successful trajectories that do not. Neither alone proves
  generalization. Success at reset remains separate.

## Data and verification

The corrected run reuses the original shared input artifact 10795982721 from
run 35971324989. Every train/held-out NPZ hash is checked. Observations, actions,
episode boundaries, environments, seeds, goals and evaluation budgets do not
change. No benchmark outcome selects a representation, threshold or policy.

Development tests use synthetic data only. They require repeated states,
loops, a held-out action ordering assembled from recorded transitions,
retention of conflicting successors, explicit missing transitions, exact
operator projection and non-vacuous memory checks. Reference/optimized full
tree, BIC, means and all symbol assignments are still checked before use.

The platform's parallel job count changes from 4 to 20; per-job algorithms and
budgets do not change. Existing raw-image reference memory requirements remain
unchanged. Resource-unavailable cases must not be reported as model failures.

Results must not be retuned after the corrected source is frozen.

## Development test correction

The first end-to-end synthetic fixture repeated a six-action periodic trace.
The absolute-target reference selected `obs[t-2][0]` and `obs[0]`. A proposed
test requiring non-UNKNOWN replay of an arbitrary new action order failed.
That test incorrectly assumed perception generalization in order to test
operator wiring. No learner was changed to force it to pass. The periodic
fixture remains as a test that history-selected symbols are preserved and
evaluation does not add transitions. A separately exhaustive one-step sensor
fixture checks non-UNKNOWN multi-step composition, with no manual symbols.
Neither fixture is included in benchmark learning or in reported capability.
