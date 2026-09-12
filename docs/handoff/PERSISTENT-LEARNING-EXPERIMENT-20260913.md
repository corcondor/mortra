# Fixed-Baseline Longitudinal Experiment

## Freeze and hypothesis

Baseline repository: `corcondor/mortra`, branch
`codex/theory-formation-20260913`, exact mathematical baseline
`f9f80e39ca92035bfc37490ad5a072289c9cd80f`.
Verified Actions run: [34718259018](https://github.com/corcondor/mortra/actions/runs/34718259018).
That run passed the 351 related tests, 22 theory tests, acquisition, reuse,
refusals and the bounded theory experiments. These are previous results, not
this experiment's fresh evidence. The current documentation-only descendant is
`aad9d2e0dd0ae262ab135fd4d4627f867dfa9ba5`.

This experiment tests whether earlier acquired knowledge changes later
capability, without adding mathematical capabilities. All mathematical imports
and normal-entry subprocesses use a separate checkout at the baseline SHA.
The control checkout contains measurement, fixed input, guard tests, and CI
changes only. No changes to `math_os_prototype` or the existing normal entry.
The code, all questions, budgets and seeds freeze before learning starts.

## Existing mechanisms and limits

The baseline's `Theory` generates typed terms, proposes relations, calls exact
provers, compiles acquired equalities into decreasing rewrite rules, acquires
finite observable closures, derives recurrences, and executes those recurrences.
It retains concepts, certificates, counterexamples, dependencies and history.
The learner's `actions` method selects its own next calculation. The evaluator
does not supply the next concept, equation, basis, procedure or theorem.

Executable reductions and derived recurrence parameters count as specialized
procedures. The recurrence interpreter and reduction strategy are initial
developer-supplied machinery. No newly invented general algorithm is assumed.

Archive concepts and active concepts are separate. All acquired rewrite rules
remain available to matching, so rule growth may increase search time.
Finite closures omit position, collision and legality. They cannot answer
collision-free folding tasks. The q-directed baseline regression still checks
the separate existing legality refusal machinery.

## Predeclared workload

Plan: `configs/persistent-learning.json`. One training seed, 20260913.
Independent external-question seed: 739182. No seed robustness claim.

Three existing signatures: differential polynomial ring; all 24 reachable fold
frames; the existing five-state finite model. There is no library transfer
between these separate domains. The five-state model was held out from the
earlier development, but is a training domain in this experiment, not a new
unseen-domain claim.

Learning conditions: normal, theorem reuse disabled, representation reuse
disabled. Normal-entry resumes retain all prior state. Resource bounds alone
are enlarged: maximum 12,000 cycles, 600 engine seconds per condition/domain,
16,000 considered terms, 128 concepts, 32 active concepts, size-nine terms,
four representations. Remaining budget parameters retain baseline values.
Snapshots: 0, 10, 25, 50, 100, 250, 500, 1000, 2000, 4000, 8000, 12000.
Stopping early is recorded at the actual cycle. A resource stop or exhausted
bounded frontier is not repaired mid-run. Runtime excludes subprocess startup,
serialization and evaluator time; all are recorded separately where measured.

Each domain has 64 fixed questions (eight random contexts, eight predeclared
families). Contexts exceed the learner's syntax bound. Families include algebraic
equalities, differential identities or action identities, perturbed and
independent pairs. The harness is not selecting questions for success. These
are human-designed evaluation families, not MORTRA-generated achievements.
The same mathematical structure may already be known: syntactic novelty is
not a claim of world novelty, unseen theorem families or difficult mathematics.
Exact repeated training-query overlap is recorded explicitly.

Every normal-learning checkpoint evaluates the same 64 questions. For the two
full-run ablations, evaluate initial and final states; intermediate snapshots
retain all knowledge and training metrics. Three answer timing repetitions per
task, identical order, fresh disposable state for every task/repetition. A
fresh invocation uses its own caches, but no process is spawned per individual
task. Thus the timings are not controlled cold-cache benchmarks.

`Theory.settle` is called unmodified. Evaluating a task may transiently prove it,
but that acquisition is discarded before the next task and never returned to
training. No additional representation selection or recurrence route is added
to this interface. Its held-out representation reuse is zero if the baseline
does not route to its spaces, even when a human could construct such a route.
The holonomic acquisition library is a separate state format; do not pretend
that this Theory snapshot is consumed there. Existing series tests run as
regression, not evidence of longitudinal transfer into that domain.

## Measures and causal controls

Record per snapshot: archive sizes by kind, semantic concept count, exact
row-space-distinct closure count, active vocabulary, theorem dependency depths,
reuse events and costs, frontier/constructor distributions and provenance.
Different row bases in the same scope are identified by exact row reduction
in the evaluator only. No resulting knowledge is returned to MORTRA.

For every held-out task record solved/proved/refuted/unknown, exact outcome,
certificate, dependency IDs, rule candidates inspected, prover calls, prover
input AST nodes, and answer/copy time. Report median over the fixed tasks.
`median_search_nodes` means inspected rewrite-rule candidates. It is not a
proof-search tree count. `median_proof_cost` means prover input AST nodes, not
machine instructions. Neither substitutes for wall time. Newly solved tasks
and regressions compare the same task IDs with K0.

At the final normal state:

- Disable all active rules and repeat the fixed suite.
- Select the earliest actually used held-out dependency, by acquisition cycle
  then ID; disable that rule alone and then its recorded dependency descendants.
  The selection policy is fixed now, not manually chosen after results.
- Replay up to four earliest logged closure-to-recurrence requests, with the
  stored closure enabled versus the baseline's existing reacquisition switch.
  These are explicitly replay/regression requests, not held-out successes.
- Independently reprove stored relations/counterexamples, check closure
  matrices/readouts and execute recurrence regression checks.

No approximate semantic equivalence metric exists here; near-duplicate rate
is null. The reported non-new-semantic fraction also includes rejected terms
at the concept cap, and must not be called a pure duplicate rate.
The dependency DAG is the actual recorded proof graph, not a human route or a
claim that every dependency was logically indispensable.

## Running and evidence

Use the existing `worker-ci.yml`, dispatch suite `persistent-learning`,
target_ref and expected_sha both equal to the full baseline SHA. The control
branch contains this document and the evaluator. The job reruns the related
tests, q-directed normal/reuse/refusal, theory guards, evaluator guards, then
the experiment. It uploads evidence even when a step fails. No release CI
or scheduled release branch is changed.

Local reproduction with a baseline checkout and a distinct control checkout:

```bash
MORTRA_BASELINE_ROOT=/absolute/baseline python /absolute/control/scripts/measure_persistent_learning.py --plan /absolute/control/configs/persistent-learning.json --output /absolute/new-output
```

Development smoke runs are explicitly marked, are not scientific results, and
may only diagnose the measurement harness. Failure during a frozen Actions run
remains in that run's artifact. A harness correction needs a new control SHA
and a new run. No mathematical source changes are authorized in this experiment.

Artifacts include commands, fixed configs/questions/oracles, source seals,
environment versions, snapshots, trajectories (JSON/CSV), exact outcomes,
events, dependencies, ablations, regression checks, report and verification.json.
Infrastructure success and capability improvement are separate. More archive
entries or passing tests alone never establish the latter.

## Interpretation and references

If K0 already solves every question, success-count growth is impossible on
this suite. Report the ceiling and cost effects, including matching overhead.
If no downstream measure improves, report exactly:
"continued computation did not produce measurable capability growth".
List limitations and the smallest next mechanism proposal, but do not implement
that proposal during this experiment.

The following are design references, not guarantees about MORTRA. For this
protocol their abstracts were reread; no claim of a fresh full-paper review:
[PowerPlay](https://arxiv.org/abs/1112.5309) motivates previous-skill preservation
and incremental validation;
[DreamCoder](https://arxiv.org/abs/2006.08381) motivates evaluating transferable
compositional abstractions;
[Stitch](https://arxiv.org/abs/2211.16605) motivates separating library compression
from measured downstream capability. None licenses a claim that this baseline
implements those full systems.
