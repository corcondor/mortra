# Measured DSL synthesis results

The executable acquisition loop is preserved. Learned structural definitions
did **not** improve held-out program synthesis in this experiment. This is a
negative capability result, not a failed verification run.

## Exact execution and evidence

- Repository: `corcondor/mortra`.
- Branch: `codex/theory-formation-20260913`.
- Tested code and workflow SHA: `f5103c86bdc76a5694ef65569f880c19d52e4230`.
- [Actions run 34750353223](https://github.com/corcondor/mortra/actions/runs/34750353223),
  push event, attempt 1, conclusion `success`.
- Workflow: `.github/workflows/worker-ci.yml`, `Verify MORTRA Kernels`.
- [Artifact 10315389071](https://github.com/corcondor/mortra/actions/runs/34750353223/artifacts/10315389071),
  `q-directed-34750353223-1`.
- Artifact digest:
  `687bb9cf3d21dddf3fb61cbb775ab00ecb868d98be7ce101314cdc30beb2df36`.
- Environment: Linux x86_64, Python 3.12.10, SymPy 1.14.0, NumPy 1.26.4,
  python-flint 0.9.0, pytest 8.4.1. The complete versions are in `environment.json`.
- Downloaded evidence on the developer host:
  `C:/Users/81808/.openclaw/reports/dsl-search-actions-34750353223/q-directed-34750353223-1/`.

All numbers below, unless explicitly labelled local or retrospective audit,
come from this Actions run, not previous Windows logs. This report-only commit
is not the tested code commit above.

The protocol is [DSL-SYNTHESIS-COMPARISON-20260913.md](DSL-SYNTHESIS-COMPARISON-20260913.md).
The Actions commands were:

```bash
python -m pytest tests/test_theory_dsl.py scripts/test_library_compression.py \
  scripts/test_expand_for_execution.py scripts/test_call_candidate_dedup.py -q
python scripts/verify_theory_tasks.py --config configs/theory-dsl-fold.json \
  --challenge-seed 917334 --output "$VERIFY_OUTPUT/dsl-tasks-917334"
python scripts/verify_theory_tasks.py --config configs/theory-dsl-fold.json \
  --challenge-seed 917335 --output "$VERIFY_OUTPUT/dsl-tasks-917335"
```

The 351-test module list is `configs/q-directed-verification.json:test_modules`.
Its exact command is retained in `plan.json`; all spawned normal-entry argv
lists are in each `dsl-tasks-*/verification.json:commands`. Those include
initial evaluation, 150 learning cycles, resume to cycle 300, learned-archive
evaluation, and structural-only ablation. No evaluator witness was an argument
to `run_theory_formation.py`.

Both experiments kept source and harness hashes unchanged. Both used the same
config bytes, SHA256
`c07b9253ab3c986555cb670d2d50399eef2ae9cad3011257c057dbab59c13329`.
All 85 enumerated artifact hashes in each experiment were checked after download;
there were zero mismatches.

| Seed | Frozen challenge SHA256 | Verification JSON SHA256 |
| --- | --- | --- |
| 917334 | cb9c8a3b9d3d4af7e6f2db900ddbb511cb983bf74dd00a2daf063a3bae447f14 | 08ed7c5a9fee63936d1e4a00e4aba64188e5be1cdfb0505bf18b6a293f2075e6 |
| 917335 | b0ff387bb2d895751acf7b7275d9ac88fa9e1f59dcff31a771d0bcdc600a4d66 | 14f18cf063acb5600247d70ad9d9bed44d000890d687ba52092f5670ab188586 |

## Actual acquisition chain

In the following saved chain, `F11` and `F23` are declared frame-coordinate
observables. `R(A)` is the acquired readout `R-b8f032907b167b70` evaluated after
the action word `A`. The macro argument `u` is a scalar observable, not a
developer-provided answer. The generator chose the bodies and arguments below.

```text
Fixed initial DSL: frame observables, actions, scalar operations
  -> MORTRA executes expressions containing a certified R(A)
  -> cycle 14: h(u) = add(u, R(A)), definition 6e03302e5fc8a62d
  -> h enters the persistent typed DSL
  -> cycle 18: synthesize h(add(F11,F23))
  -> execute; independent primitive replay agrees on all 24 states
  -> cycle 26: acquire g(u) = h(add(F11,u)), definition e5c1105b431f8eb7
```

The exact objects, source corpus IDs, types, scope and execution records are in
`dsl-tasks-917334/acquisition-summary.json:actual_feedback_edges[0]`.
The other task seed has the same training trace because training is independent
of evaluation and has the same seed and config.

Each 300-cycle training run retained:

- 3 structural definitions, with observed call counts 46, 34 and 28;
- 108 normal executions containing structural calls, out of 2,184 DSL executions;
- maximum structural definition dependency depth 2;
- 3 exact shared spaces and 9 readouts, counted separately;
- a net training-corpus code reduction of 83,344 bits, after charging the three
  template bodies once (3,464 bits). This is compression, not a solved-task gain.

### Retrospective semantic audit, not an acquired theorem

The first recorded `h(F11+F23)` result equals the existing `F23` observation
at all 24 states. Subtracting its stored vector gives 24 zero residuals.
Since the stored body is literally `u + R(A)`, this implies `R(A)=-F11` on
the declared model. Consequently `h(u)=u-F11` and `g(u)=u` there. The second
structural definition only reverses the operands of the same addition.

This is an evaluator's post-run mathematical interpretation of the saved body
and exact replay, **not** a theorem that the learner acquired or an input to
evaluation. It is a concrete reason not to equate three stored definitions or
a depth-2 dependency with three independent mathematical capabilities.

## Search comparison

Each task asks for a program realizing a complete finite function on 24 states.
The expression is not given. All targets have initial-DSL witnesses and all
witnesses fit the common bounds. Every condition had zero size refusals.
No solved result exceeded the shared 512-state / 1,000,000-work-unit budget.

A uses the initial language. B enables all learned operations. C loads the same
archive as B and disables structural definitions only; readouts and recurrences
remain active. Archive digests and enabled-operation lists verify this ablation.
All query acquisition counts and task-theorem prover counts are zero. Each
accepted answer has a separately charged complete-model replay.

| Frozen set | A solved | B solved | C solved | B solves what C cannot |
| --- | ---: | ---: | ---: | ---: |
| 917334, 24 tasks | 12 | 9 | 9 | 0 |
| 917335, 24 tasks | 8 | 9 | 9 | 0 |
| Total, 48 tasks | 20 | 18 | 18 | 0 |

The set contains seed/regression-like tasks as well as new semantic functions.
After classifying overlap against all saved concepts, corpus entries and DSL
executions, 38 task specifications were unseen in learning. A solved 11/38;
B and C each solved 8/38. No structural-definition benefit appeared on that
subset either. This classification did not remove or alter any input task.

One task, `917335/external-17`, was unsolved by A at 512 states and solved by
B at 460 and C at 421 states. Both synthesized the same program:

```text
pull_T(represented(R-e77b5ff053fb6d5a, word(A)))
```

No structural definition occurs in that answer. Its semantic specification
had already appeared during learning. It is a measured stored-representation
reuse effect on a bounded search task, not a new unseen mathematical function
or evidence that the structural macros helped.

### Cost, including failures

The table sums both independent task sets. Attempted applications exclude the
17 common initial facts per task; recorded `states_explored` includes those
facts. Process seconds include startup, archive loading, search, checking and
output. These are observed single-run timings, not statistical speed estimates.

| Condition | Attempted applications | States incl. inputs | Process seconds | Interpreter work | Suite description bits |
| --- | ---: | ---: | ---: | ---: | ---: |
| A | 16,001 | 16,817 | 16.371 | 1,629,955 | 10,968 |
| B | 17,203 | 18,019 | 35.782 | 1,743,442 | 988,376 |
| C | 16,942 | 17,758 | 34.476 | 1,648,106 | 967,144 |

Each independent experiment charges its active library once. B's active library
cost is 489,608 bits: 10,616 for structural bodies, signatures, scope and
dependencies, plus 478,992 for certified spaces/readouts/procedures including
their records. C retains that same archive but only the latter operations are
active. These are conservative canonical-JSON stored-code costs, not minimal
encodings. They differ from the bare-template MDL cost in the training report.

Different conditions solve different subsets, so the all-condition common
solved subset is also reported: 17 tasks total. On those same tasks, A/B/C use
1,218 / 2,199 / 1,977 states, respectively. Their code lengths with the active
library charged once per experiment are 8,064 / 987,280 / 966,048 bits.

The two training processes together additionally cost 31.345 seconds including
startup and persistence (23.824 seconds inside the learning loops). Charging
that common learning history to B or C gives 67.126 or 65.821 seconds,
respectively, versus A's 16.371 seconds. Training is not treated as free.

B performs 5,016 macro expansions and 11,286 definition lookups during query
search/checking. C performs zero macro expansions, while retaining 3,416
represented-observation calls and 2,760 recurrence calls. No successful B
answer contains a structural macro. Macro execution in rejected or duplicate
search candidates is not reported as use in a successful answer.

Expansion visits, type/scope checks, primitive expansion time, interpretation
time, independent verification time, and cache counts are retained per task.
The search synthesizer does not run pattern-rewrite matching; its rewrite-match
counter is zero by design. Matching costs for the original 48-expression
compressor remain in that separate experiment.

## Regression and scope

Fresh Actions evidence:

- 351 q-directed related tests passed; 0 failed.
- 22 Theory tests passed.
- 90 DSL/library/expansion tests passed: 463 related tests in these sets.
- q-directed small normal run passed.
- stored reuse passed without reacquisition or task reproving, under its certificate.
- collision-free normal/refusal-reuse runs refused the inadmissible representation.
  `refusal-summary.json` retains the `AAG` / `AAT` legality counterexample.
- Original 48-expression evaluation/compression in both domains was retained
  and passed correctness checks. It did not show a held-out net code reduction.

Do not transfer the affine q-directed certificate's broader scope to the new
finite-frame synthesis tasks. The latter concern functions on the declared
24-state orientation model and do not preserve collision legality.

An independent clean local checkout at
`C:/Users/81808/.openclaw/workspace/mortra-dsl-search-clean-f5103c8/` reproduced
the same solved counts and structural ablation outcomes, with different timing.
Outputs are under `C:/Users/81808/.openclaw/reports/dsl-search-f5103c8-917334/`
and `.../dsl-search-f5103c8-917335/`. Its worktree remained clean.

## What changed and what did not

The earlier code commit `2b21189...` repaired typed macro arguments, composition
of acquired observations, and value-sensitive synthesis. The final code commit
`f5103c8...` added structural-only ablation and cost instrumentation, retained
certified recurrences in query search, relaxed common safety bounds, and fixed
the new task sets before running them. It did not change the learner's acquired
bodies to favor these tasks. Known unit-test fixtures never entered the normal
process. All development failures and the earlier negative comparison remain
saved; they are not relabelled as these fresh results.

Separate judgments:

- Exact space sharing: maintained, with independent readout and legality checks.
- Autonomous executable DSL growth and h-to-g feedback: maintained and used.
- Smaller training-corpus description: measured, without treating it as intelligence.
- Better held-out synthesis due to structural definitions: not observed; costs
  increased in this run and solved counts did not improve over C.

There is no basis here to claim general algorithmic self-improvement. The
experiment does establish the requested causal comparison and preserves its
negative result instead of replacing tasks or injecting a useful definition.
