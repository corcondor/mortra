# Fixed geometry library x selection: preregistered comparison

## Status before implementation

Baseline: `616bff0d0d11a1a073e7a02099d40cb99b40a4d9`, branch
`codex/geometry-semantic-feedback-20260915`, repository `corcondor/mortra`.
Tracked baseline is clean; historical untracked run files are retained.
The AGENTS-referenced `.agents/skills/mortra-autonomous-research/SKILL.md`
is absent from this checkout. No historical files are restored.

The previous recursive acquisition result is retained. This experiment does
not acquire more definitions, extend the grammar, or teach a search policy.
It reads all 16 certified definitions from run `34889840285`; the old run is
input provenance, NOT evidence that this experiment succeeded.

## Frozen factors and inputs

The executable specification is `configs/theory-geometry-selection-factorial.json`.

| Arm | Library | Order |
|---|---|---|
| A | initial primitives | existing fair search |
| B | initial primitives | contract-guided, fair |
| C | initial primitives + all 16 stored definitions | existing fair search |
| D | initial primitives + all 16 stored definitions | contract-guided, fair |

The primary contrast for solved counts is `(D-C)-(B-A)`, with per-task paired
outcomes retained. Costs are separate measurements, not converted into a scalar
reward. Report each arm and the D-vs-B comparison as well as the interaction.
One fixed run cannot establish a population-level statistical effect.

Candidate membership must be identical for A/B and C/D at the SAME state.
The primitive/library contrast necessarily changes the grammar. Different
search orders also reach different states; full-run candidate sets are not
required to coincide. Reordering occurs AFTER the existing per-family candidate
generation and truncation. No relevance filter, new binding generator, or
solution-derived intermediate goal is permitted.

Use the existing symmetry-aware `align_candidate_atoms` and the existing
general predicate-transition information for ranking only. Conditional
postconditions may propose relevance, never establish a fact. The existing
exact applicability, effect and goal checks remain authoritative. Keep one
offer from each live family per fair round, and the original family order every
fourth round. Include selection, lookahead, matching and replay costs.

Keep the 16 old tasks as development/regression instances. Before any evaluated
search, generate all 16 new instances by the config's fixed seed and coordinate
rule; preserve the goal templates. Save the literal tasks and hashes. Do not
retain only instances a chosen library can solve. This is new-instance transfer
within known goal templates, NOT unseen mathematical-family generalization.
Development tests use artificial small configurations, not this cohort.

## Evidence and diagnosis

For each candidate retain proposed family/binding, source contract, direct
postcondition alignment, original/new position, selection, execution/refusal,
and source state. A conditional match is not proof of applicability. For solved
tasks retain the planner's construction dependency DAG, the final answer term,
primitive replay and exact instance goal certificates. Count ancestor acquired
calls separately from acquired calls remaining in the final answer term.
Neither syntactic appearance nor ancestor membership alone proves necessity.

After evaluation only, run the frozen wider budget on the old tasks unsolved
by A, under A and D. A found replayed path is an existence witness within that
budget. Failure remains unresolved; do not call it an oracle upper bound or a
proof that the fixed library has no useful construction. No diagnostic result
may modify the already frozen selector or evaluation inputs.

Use the normal `run_theory_formation.py` entry and the existing geometry Actions
workflow. Keep archive loading/revalidation, search, ranking, execution,
independent replay and serialization costs distinct. Record code/input hashes,
environment, exact commands, negative results and the workflow run ID. Failed
versions are separate runs, never repaired while running.

## Interpretation rules

- Recursive DSL acquisition is an existing result, not re-proved by this test.
- Improvement in B as well as D may be ordinary primitive selection improvement.
- A positive interaction is evidence for this library/selector/cohort/budget,
  not proof that every acquired definition is useful.
- D-only success plus a replayed acquired-call dependency is stronger evidence;
  no task-specific definition is inserted to obtain it.
- No improvement remains a valid negative result. Do not respond by extending
  the training horizon or tuning on the new evaluation cohort.
