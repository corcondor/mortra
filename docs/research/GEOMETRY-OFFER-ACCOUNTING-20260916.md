# Application-budget accounting: one change, one experiment

Repository: `corcondor/mortra`.
Branch: `codex/geometry-offer-accounting-20260916`.
Solver baseline: `f4334cead7ca669f044bf6d2c3143fae735cee79`.
Compared against Actions run `35060935705` (`fa6e10a4c80fb0cdd5d9dcec39597fc6f7b443ad`),
whose record is `docs/research/GEOMETRY-TIME-EXTENSION-20260916.json`.

Headline: **0 of 7 additional tasks proved.** The cumulative count remains
17/24. The change did what it was designed to do and did not solve anything.

## What the recorded run showed

Read from the artifact of run 35060935705 (`semantic-feedback-normal/run-*/events.jsonl`),
by pairing each `symbolic_dsl_apply_started` with the outcome that followed it.

Across the five tasks whose search reached the construction layer:

| | count |
| --- | ---: |
| applications offered | 1085 |
| applications that produced a state | 76 (7.0%) |
| refusals | 1009 |
| construction families offered | 38 |
| families never accepted once | 30 |
| refusals belonging to those 30 families | 845 (83.7%) |
| exact duplicates (same parent state, family and inputs) | 0 |

Every one of the thirty never-accepted families was refused with the same
reason on every offer. The reasons are properties of the JGEX definition rather
than of the points supplied: `worker/backend/jgex_exact_constraint_bridge.py`
admits a construction only when its output point is fixed by two degree-one
equations whose effects lie in `{coll, para, perp, cong, midp}`, so a
construction that leaves a degree of freedom, that alters the normalization
scope, or whose defining condition is quadratic cannot be admitted. Only
`midpoint` and `mirror` were accepted every time; `foot`, `reflect`, `circle`,
`circumcenter`, `orthocenter` and `parallelogram` were accepted occasionally.

That the duplicate count is zero is a check on the search, not a finding: the
`attempted` set in `SymbolicDSLDomain.alternatives` does prevent an identical
candidate being offered twice at the same state.

## The defect

`math_os_prototype/runtime_typed_planner.py`, in `synthesize_typed_plan`:

```python
result = invoke()
progress.applications_completed += 1
states_explored += 1          # before the refusal is tested
if result is None:
    continue
```

`states_explored` was incremented before checking whether the application
produced anything, so a refusal consumed a unit of `max_states` exactly as an
accepted application did. With `max_states` at 257, positions 3, 17 and 23
stopped on that budget after 256 offers, having executed 14, 20 and 18
constructions respectively.

This is in the planner, not in the certifier. The certifier's refusals are
correct; what was wrong was that they were charged to the state budget.

## The change

One option, `max_offers`, added to `synthesize_typed_plan` and passed through
`theory_action_domain.search_action_domain` and
`geometry_symbolic_dsl.run_symbolic_solver`.

* Left unset, the planner behaves exactly as before. Every existing caller,
  config and test is unaffected.
* Set, `max_states` counts only applications that produced a state, and
  `max_offers` caps the offers, which is then what guarantees termination. A new
  `offer_budget` status distinguishes that stop.

It changes what the budget counts. It does not change which candidates are
generated, the order they are offered in, which of them the domain accepts, the
certifier, the proof backend, or any proof.

Four tests were added to `math_os_prototype/test_runtime_typed_planner.py`,
including one asserting that a plan with nothing refused produces an identical
goal value and an identical proof program with and without the option.

## The experiment

`configs/theory-geometry-autonomous-solve-offers-20260916.json` differs from
`configs/theory-geometry-autonomous-solve-extended-20260916.json` in one entry,
`search.max_offers: 4096`. Task timeout 300 s, proof attempt 30 s, seed 917401,
depth 5, `max_states` 257, `per_family_limit` 8, `proof_dsl_budget` 256 and all
seven task objects are unchanged.

4096 was chosen to be non-binding against the 300-second task limit: the
recorded run reached 256 offers in 92 to 245 seconds. What the experiment varies
is therefore the accounting, not the amount of work permitted.

```sh
PYTHONHASHSEED=0 python scripts/verify_theory_geometry.py \
  --plan configs/theory-geometry-autonomous-solve-offers-20260916.json \
  --output reports/semantic-feedback-normal
```

Actions run: https://github.com/corcondor/mortra/actions/runs/35069966974
Tested commit: `49ab45fca84420cdf350f5bea767c3bbcdaa0f91`.
Artifact: https://github.com/corcondor/mortra/actions/runs/35069966974/artifacts/10436752536

## Results

`proved: 0`, `statuses: {"timeout": 7}`, `false_proofs_detected: 0`,
`sources_unchanged: true`. Tests: 283 passed, 1 skipped in the semantic suite;
10 passed in the bridge subset; the exact-kernel job passed.

Positions are those of the original 24-task cohort. "before" is run
35060935705; "after" is run 35069966974.

| Position | Stop before | Stop after | Offers before / after | Executed before / after | Proof attempts before / after |
| --- | --- | --- | ---: | ---: | ---: |
| 3 | application budget, 91.8 s | task time, 300 s | 256 / 1179 | 14 / **66** | 520 / 1602 |
| 9 | task time, 300 s | task time, 300 s | 240 / 230 | 18 / 17 | 440 / 437 |
| 15 | task time, 300 s | task time, 300 s | 6 / 6 | 3 / 3 | 171 / 171 |
| 17 | application budget, 127.0 s | task time, 300 s | 256 / 985 | 20 / **64** | 560 / 1520 |
| 22 | task time, 300 s | task time, 300 s | 0 / 0 | 0 / 0 | 9 / 9 |
| 23 | application budget, 244.8 s | task time, 300 s | 256 / 305 | 18 / **20** | 680 / 799 |
| 24 | task time, 300 s | task time, 300 s | 78 / 78 | 5 / 5 | 230 / 232 |

The mechanism behaved as designed:

* The three tasks that had stopped on the budget now use the full 300 seconds.
  Positions 3 and 17 execute 4.7 and 3.2 times as many constructions in the same
  wall time. Position 23 gains little because it was already using 245 of its
  300 seconds.
* The four tasks that were already time-limited are unchanged within run-to-run
  variation on hosted machines. That is the control: a task that never hit the
  budget should not move, and none did.

And it solved nothing. No task reached an accepted proof, and no false proof was
detected.

## What this does and does not establish

* It establishes that the budget was being spent on refusals, and that removing
  that no longer limits these tasks. The binding constraint for all seven is now
  wall time.
* It does not establish that any of the seven is provable by this solver, nor
  that it is not. Reaching a time limit is neither a completed search nor a
  proof of unprovability.
* Executing 66 constructions instead of 14 is more search, not better search.
  Nothing here changed which candidates are proposed or how they are ordered,
  and 93% of offers are still refused.
* The two runs ran on different hosted machines. Timing differences are not a
  controlled benchmark.
* No answer, auxiliary point, target lemma or desired procedure was supplied to
  the normal entry, and no code was edited while a run was in flight.

## The second experiment, which failed

`codex/geometry-gaussian-ground-20260916` (`d59b5d66642ef8ed59699778f47c67f740933a01`)
addressed position 15 separately: its 171 completed proof attempts all raised
before any reduction (102 rational-function `ValueError` in the principal-ideal
scan, 69 `CoercionFailed` in the Groebner stage) on expressions of the form
`_apex_x_1 + I*_apex_y_2 - _base_0`. `_similar_triangles_polynomial` combines
the real and imaginary residuals of a directed similarity into one
Gaussian-rational polynomial by design, while the ideal machinery built its
ground domain as `sp.QQ.frac_field(...)`, which cannot hold that coefficient.
Choosing the ground domain from the expressions was verified in isolation to
turn both failing operations into successes.

Actions run: https://github.com/corcondor/mortra/actions/runs/35070346016 —
**failed**, on an existing test:

```
tests/test_theory_geometry.py::test_actions_complex_similarity_obligation_is_refused
assert not certificate["accepted"]
```

That guard is right to reject the change as written. Its origin, commit
`aaf2a8ff1855268a81008f7fddd9001aaad8c339`, records the reason in
`docs/research/GEOMETRY-NATIVE-CONNECTION-20260914.md`: `CoercionFailed` and
`PolynomialError` are recorded as unsupported certificate obligations so that
other candidates can still be checked, and that is "a domain boundary refusal,
not support for complex-coefficient geometry". Widening the ground domain
changes a declared capability boundary, which is a decision that needs its own
verification rather than a three-line substitution.

The test was not modified and the branch was not merged. What a correct version
of this change would have to establish first:

* whether `_replay_polynomial_identity_with_flint` is reached with Gaussian
  input and what it does there — the SymPy fallback in
  `_replay_groebner_certificate` uses `domain=sp.EX` and tolerates `I`, but the
  flint fast path is rational-only and is tried first;
* whether the nonzero-condition and normalization-scope handling remains valid
  over the Gaussian rationals;
* whether the alternative — splitting the obligation into its real and
  imaginary parts as two real obligations — is preferable to widening the
  domain, since it would keep the declared boundary intact.

## Not addressed

Position 22 was deliberately left alone so that these results stay attributable.
Its ten proof attempts all reach `groebner_started` with seven equations, ten
variables and coefficient domain `QQ(_segment_length_0)` under method `f5b`, and
none completes; the search never reaches the construction layer at all. Raising
the per-attempt limit from 5 to 30 seconds reduced its completed attempts from
17 to 9 without completing a single basis. The next step there is a measurement
— one attempt with a much larger single-attempt budget, to learn whether that
basis terminates at all — not a change of method.

The thirty structurally inadmissible construction families were also left alone.
A list of them derived from these traces must not be written into the search: if
that pruning is worth doing, the criterion has to be computed by the system at
run time from the certifier, not supplied from an analysis of the answers.
