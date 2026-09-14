# MORTRA Geometry Semantic DSL Feedback, 2026-09-15

## Scope and status

In the initial c991e86 experiment, the geometry DSL acquired and executed new certified operations, but did not
acquire a certified second-generation operation or solve more held-out tasks.
The following chain is from the frozen normal run, not development examples.
`H0` is a readable alias for `geom.semantic.1b84f7c7e765b803d0dd`.

```text
7 primitive Point morphisms + exact predicates
  -> autonomous construction histories (6 sources across 3 input contexts)
  -> H0(f0,f1,f2,f3) = orthocenter(circle(f0,f1,f2),f0,f3)
  -> universal guarded contract certified; H0 registered in the DSL
  -> automatically generated use(H0, foot(a,b,c), a, b, c)
  -> primitive replay: 3 DAG operations, residuals [0,0]
  -> this semantic call enters the next acquisition corpus
  -> candidate 3eda78c47a89e9e7:
       H1_candidate(x,y,z) = use(H0, foot(x,y,z), x, y, z)
  STOP: candidate not selected for certification/registration;
        no certified H1 with an H0 dependency in this run.
```

The first H0 execution history is
`c1f658a8c78cd0dce5e3ee26131c6dc3e91385bc16344d0f26c8d4ce2182e5e9`.
One acquisition source is
`538c7122cdd6be17d23be020e118c69a85ebfdcbc9a116bfcbb9a88c1cea6acf`.
Both are in `events.jsonl`; the contract, all source matches and task hashes
are in `C-archive.json`. A candidate is not a certified acquisition.

Repository: `corcondor/mortra`.
Branch: `codex/geometry-semantic-feedback-20260915`.
Clean source baseline: `aaf2a8ff1855268a81008f7fddd9001aaad8c339`.
Frozen experiment source: `c991e86df081f1c5632cb0040db94d7ee90d1051`.
Local checkout:
`C:/Users/81808/.openclaw/workspace/mortra-geometry-semantic-feedback-20260915`.

The attachment authorizes implementation, superseding the preceding read-only
audit restriction for this task. Its SHA256 is
`5e9b760204d1d70cc3f599bf18df3f6ed329e2393797c758f853ca743d67b968`.
The quarantined parser/solver changes were not restored. No parser was edited,
no historical file was restored, and no main merge was performed.

## Reused mechanisms and changes

- `library_compression.py`: existing `use`, parameter sharing, anti-unification,
  candidate extraction, definition-inclusive utility, definition tables,
  syntactic round trips, and `expand_for_execution`. No second call language.
- `fold_domain.py`: read as the existing generate/learn/call/execute feedback
  precedent; neither fold operators nor recurrences replace geometry here.
- `runtime_typed_planner.py` and `theory_action_domain.py`: existing fair planner;
  the latter now accepts retained facts for continuation between windows.
- `typed_geometry_stalk.py`: existing seven families, typed candidate generation,
  generated-point ranking, and deterministic per-family scheduling.
- `geometry_contracts.py`: retains its old midpoint/foot behavior by default;
  an explicit fragment parameter supports the semantic geometry route.
- `geometry_semantic_dsl.py`: typed predicate/state/call/contract records; existing
  exact JGEX explicit and relational construction semantics; scope checks.
- `theory_geometry_feedback.py`: normal-entry semantic search, acquisition,
  registration, repeated learning, and frozen A/B/C/D/E comparisons.
- `scripts/run_theory_formation.py`: selects the new geometry mode, seals source,
  records environment, and writes completion or failure separately.
- Existing `mortra-paper-guided-geometry-ci.yml`: adds a semantic-feedback job;
  the existing exact-kernel job is retained. No parallel replacement workflow.
- `.gitignore`: excludes this checkout's isolated `.venv`.

The historical typed-stalk report was read in full. Its previous numerical
results are historical evidence, not results reproduced by this experiment.
The optional `.agents/skills/mortra-autonomous-research/SKILL.md` referenced by
AGENTS was absent at this baseline; it was not reconstructed.

## Exact meaning of the state and contracts

`GeometrySemanticState` stores exact rational Point coordinates, certified
predicate atoms, semantic terms, call history, active morphisms, and work cost.
Predicates affect candidate incidence ranking, applicability, effects, and
goal checks. Later acquisition reads the retained semantic terms and their
certified histories. It is not a natural-language parser.

Enabled constructions are midpoint, mirror, foot, circle, orthocenter, reflect,
and intersection_ll. Here `circle : Point^3 -> Point` returns a circumcenter.
Point/Line/Circle are declared carrier names, but this route has no Line- or
Circle-valued constructor. Claiming a general carrier-complete geometry DSL
would be incorrect.

Relations coll/perp/para/cyclic/cong/eqangle and requirements diff/ncoll/npara
use exact polynomial/rational evaluation. Proper nonzero lines are required
for perpendicular/parallel/angle predicates. Angles are directed modulo pi.
Cyclicity requires a noncollinear first triple and distinct points. Unsupported
operations/types or missing conditions are refused, never numerically accepted.

A learned morphism retains both its semantic body with `use(H,...)` and its
fully primitive-expanded DAG. The contract is universally certified over real
input coordinates with QQ coefficients, on the explicitly defined admissible
input domain. Each local output is the unique solution of a two-equation linear
block when its determinant and denominators are nonzero. Local rational
witnesses satisfy that block and the declared effect equations identically.
Induction in DAG order gives the composed contract. Nonzero guards involving
earlier outputs are evaluated after those outputs, before the next output.
This domain is NOT falsely represented as a list of polynomials in original
inputs when it is stored as sequential guards.

Runtime uses those local witnesses and checks their guards. Independent replay
separately executes the fully expanded primitive program from original input
coordinates and compares the result exactly. Proper geometric conditions are
also checked before publishing effect atoms. Instance goal checks are NOT
universal proofs of arbitrary geometry conjectures.

Calls preserve argument sharing and references to archived definitions. The
archive is not destructively rewritten. A later contract may contain earlier
calls; certification expands them using the existing library mechanism.
Registration replays the complete contract, not merely an ID or a rank.

## Frozen protocol

Configuration: `configs/theory-geometry-semantic-feedback.json`.
Local byte SHA256:
`24e2afde63c8b129a64fa00c7b69e56ff9635917e8d6c46493d36f09e1e6d70f`.
Input metadata also records a canonical configuration and per-source seals;
platform line-ending changes need not preserve this local byte hash.

Three training configurations, 16 solving tasks, and two reachability
configurations were fixed before the first normal run. The 16 tasks comprise
eight predicate profiles on two fresh coordinate configurations, including
conjunctions not merely a single primitive's named effect. They contain no
answer program, intermediate construction, or learned definition. The final
two configuration commits preceded all normal acquisitions. No task was
changed after inspecting normal results.

Four training windows use 112 attempted applications per domain per window.
Evaluation and fresh reachability runs each use 112 attempted applications.
All conditions use seed 17, PYTHONHASHSEED 0, the same primitive-equivalent
operation limit 6000, and 600 seconds of active search per domain. Depth 6000
is deliberately nonrestrictive relative to the work budget, not a gate excluding
primitive programs while allowing macros. Library learning uses at most 512
interleaved history samples, 3000 source pairs, four Point parameters, two
contexts, four primitive DAG steps, and two certification attempts per cycle.
Candidate ordering uses distinct-history support, net description bits, then
content hash. It does not use evaluation outcomes.

| Condition | Training and evaluation language |
|---|---|
| A | Primitives only |
| B | Acquire in first window only; no later acquisition from calls |
| C | Repeated acquisition with first-class calls retained |
| D | C's same saved archive, but no learned active operations in evaluation |
| E | Repeated acquisition after flattening learned calls into primitives |

SOLVE uses goal ranking and exact goals. DISCOVER has no goal reachability
hard gate. Both retain type, applicability, certification and work limits.
The seven primitive families and registered learned families receive the
existing round-robin search opportunity. No successful sequence is scripted.

`Reach(L,B)` is the set of canonical exact point-coordinate sets generated
from the same initial configuration under the same budget. Names, macro IDs,
history paths and redundant predicate caches do not create new states. The
complete supported predicate interpretation is determined by these coordinates.
The planner separately keeps path-sensitive facts because terms are learning
evidence. Report new AND lost states; macro acquisition can redirect a bounded
search rather than monotonically enlarge every reached set.

This tests bounded reachability, not increased unbounded expressivity and not
the full space of all programs within B. The deterministic policy chooses a
budget-limited subset. A positive set difference alone is not more solved
mathematics or global superiority.

## Development interruptions

1. `af42419699de8995f786579392a490944694d989`: A completed; B stalled during
   acquired-contract effect verification. External read-only stack inspection
   showed symbolic expansion after substituting the whole rational chain.
   Terminated by the developer, not classified as certified exhaustion.
   GitHub run 34883401028 was cancelled; exact-kernel passed, semantic-feedback
   had not reached its normal experiment. See its local `interrupted.json`.
2. `7e5fdfc66258d4cec0a30617d95e7a7540e0029c`: local identities removed that
   particular expansion, but explicit composed-coordinate construction still
   factored the full symbolic chain inside the existing orthocenter elaborator.
   A completed; B's first acquisition was interrupted. Read-only stack inspection
   identified SymPy factorization in `_directed_intersection`. GitHub run
   34884674289 was cancelled. Its `interrupted.json` preserves the distinction.

The final generic fix keeps a triangular local witness DAG, reusing the same
primitive semantics and proof obligations. It does not add a candidate, lemma,
answer or special case for an operation sequence. Search time now excludes
waiting for other domains and acquisition. Rejected work remains charged.
Failed development tests are preserved: one new test initially read the wrong
nesting level of the certificate record and was corrected without weakening its
assertions. These records are not autonomous acquisition successes.

## Reproduction

Windows, Python 3.12.10, isolated environment from formal dependencies:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-geometry-contracts.txt
$env:PYTHONHASHSEED='0'
.venv/Scripts/python.exe -m pytest -q tests/test_geometry_semantic_feedback.py tests/test_geometry_contracts.py tests/test_geometry_contraction.py tests/test_theory_geometry.py scripts/test_library_compression.py --junitxml=reports/semantic-feedback-c991e86-tests.xml
.venv/Scripts/python.exe scripts/run_theory_formation.py --config configs/theory-geometry-semantic-feedback.json --output reports/semantic-feedback-normal-c991e86
```

Use a new output directory; the normal entry refuses an existing directory.
The exact dependency versions are in `environment.json`. Newclid supplies
imported schemas/dependencies, not the primary online solver. No online
Newclid/Yuclid proof search or external LLM is invoked by this mode.

## Fresh results

The c991e86 local normal run completed in 705.472 seconds. Source seals and
configuration remained fixed; evaluation did not modify any archive. It used
no external online prover or LLM. Its seven common primitive schema proofs
cost 4.898 seconds and 46 identity checks, separate from acquired contracts.

### Tests and independent Actions reproduction

- Fresh clean-baseline related suite at aaf2a8: 122 passed, 1 skipped, 97.62 s.
- Frozen c991e86 local suite: 151 passed, 1 skipped, 72.25 s.
- GitHub run [34885354682](https://github.com/corcondor/mortra/actions/runs/34885354682):
  both exact-kernel and semantic-feedback jobs succeeded at c991e86.
- Its XML contains 152 collected tests: 151 passed, 1 skipped, 0 failures,
  0 errors, 385.112 s. The skip is the external Yuclid comparison job only.
- Linux Python 3.12.14, SymPy 1.14.0; full package versions in its environment
  artifact. Its fresh normal run took 294.229 s.
- Comparing downloaded artifacts with local results found identical source
  seals, configuration, acquired C morphism IDs, all non-timing summary fields,
  and complete reachability sets, not only their sizes.

### Acquisition and the missing recursive edge

| C cycle | Active definitions after learning | Corpus entries | Entries containing calls | Candidate definitions containing calls | Maximum acquired generation |
|---|---:|---:|---:|---:|---:|
| 0 | 2 | 182 | 0 | 0 | 1 |
| 1 | 4 | 297 | 6 | 2 | 1 |
| 2 | 6 | 468 | 63 | 20 | 1 |
| 3 | 8 | 512 | 105 | 34 | 1 |

At the final training window, C had successfully executed acquired calls 35
times per context, 105 total. In held-out solving it executed acquired calls
120 times, but none of the final successful solution terms needed an acquired
call. There were zero registered parent dependencies between acquired
definitions. Thus executable DSL growth and subsequent calls passed; recursive
acquisition under this frozen policy did not. Artificial nested definitions in
tests only establish that the machinery can handle such dependencies.

All eight C definitions had negative net description utility on their own
acquisition corpora, ranging from -872 to -5848 bits. The first two were -1728
and -1928 bits. Do not sum these across changing corpora into a cumulative
compression estimate. Current selection orders first by history support and
then by net bits, and does not require positive utility. All registered
definitions remain active. This is a substantial limitation, not evidence of
good representation selection.

### Held-out and bounded reachability

Reach columns count normalized states on the two fixed reachability inputs,
each with 112 attempted applications. Evaluation candidate counts are sums
across the 16 tasks. Seconds are the local evaluation wall times.

| Condition | Archive / active | Solved | Evaluation candidates | Evaluation seconds | Reach input 1 | Reach input 2 |
|---|---:|---:|---:|---:|---:|---:|
| A | 0 / 0 | 8/16 | 922 | 46.024 | 76 | 72 |
| B | 2 / 2 | 8/16 | 922 | 49.037 | 61 | 57 |
| C | 8 / 8 | 8/16 | 922 | 35.163 | 43 | 39 |
| D | 8 / 0 | 8/16 | 922 | 52.907 | 76 | 72 |
| E | 8 / 8 | 8/16 | 922 | 40.269 | 41 | 37 |

The same tasks were solved in all conditions. No previously unsolved task
became solved. Each final solution had an exact successful primitive replay.
The active language changes work allocation, but this is not a demonstrated
held-out capability gain.

| C language transition | New states per input | Lost states per input |
|---|---:|---:|
| L0 to L1 (2 definitions) | 2 | 17 |
| L1 to L2 (4 definitions) | 7 | 11 |
| L2 to L3 (6 definitions) | 0 | 9 |
| L3 to L4 (8 definitions) | 0 | 5 |

Final C has 5 states per input absent from A and D, but loses 38 states per
input relative to A/D. Disabling learned operations removes those 5 states and
restores A's complete reached set. Thus learned operations causally redirect
this budgeted search, but do not produce a monotone or net enlargement.

C has 2 additional states per input relative to E, and E has no states absent
from C. C and E acquired four common definitions and four different ones.
Retaining calls therefore affected subsequent selection under this finite
budget. This does NOT establish recursive H1 acquisition, a new theorem, or
improved solving: both maximum generations are 1 and both solve 8/16.

### Costs and fairness limitations

Acquisition seconds below include candidate extraction, matching, round trips,
certification and registration. Certificate and registration columns are
subsets, not additional costs to sum with acquisition time.

| Condition | Acquisition seconds | Accepted-contract certificate seconds / checks | Registration seconds / checks | Final accumulated training-search seconds |
|---|---:|---:|---:|---:|
| A | 0 | 0 / 0 | 0 / 0 | 75.47 |
| B | 5.27 | 2.20 / 24 | 1.54 / 24 | 70.83 |
| C | 39.46 | 9.83 / 112 | 6.03 / 112 | 59.62 |
| E | 45.49 | 8.42 / 102 | 9.27 / 102 | 80.50 |

Evaluation work counters are separately recorded; instance predicate checks
are not universal theorem prover calls.

| Condition | Executed local witnesses | Independent primitive replay operations | Instance predicate checks | Applicability polynomial checks |
|---|---:|---:|---:|---:|
| A | 882 | 998 | 18382 | 612 |
| B | 786 | 838 | 15444 | 708 |
| C | 806 | 726 | 12304 | 664 |
| D | 882 | 998 | 18382 | 612 |
| E | 650 | 502 | 9616 | 788 |

Fewer checks here do not prove a better implementation of the same work:
different candidates are attempted, and fewer useful states may survive. On
the two reach inputs, C rejects 65/67 applications while A rejects 28/30.
Learned families currently allow repeated parameter bindings and check guarded
applicability only during application. This can spend scarce slots on
degeneracy/duplicate outputs. No experiment isolates this as the sole cause.

Timing is not counterbalanced: conditions execute sequentially within a
process, with shared symbolic-library caches. A and D have the same search
results/counters but different timings. Do not treat C's lower measured wall
time as an isolated causal speedup. Per-stage counters, inclusive application
time, independent replay time, expansion visits and total run time are all
retained. File serialization and logging are included in total elapsed time
but not independently timed. Certification has a candidate-count budget, not
a hard per-candidate interrupt deadline. These remain measurement/engineering
limitations, explicitly not hidden as zero cost.

### Review finding after completion

The user's subsequent review question exposed a real correctness-gate defect:
`SemanticGeometryDomain.is_goal` recorded a solution even if its independent
replay returned `passed: false`. A separate review-only fault injection
reproduced `goal_accepted: true, solution_replay_passed: false`. This did not
modify either normal experiment.

All saved successful solutions were then checked: local 40/40 and GitHub
40/40 had successful independent replay. Thus no falsely counted solution was
found in these reported experiments. Nevertheless the gate was wrong.

Commit `ce274f49b6fc769d85704129119d98b931c227be` corrects the gate, records
`goal_refusal` on failure, and adds
`test_failed_independent_goal_replay_is_not_a_solution`. After this correction,
local tests passed 152 with 1 external-comparison skip in 54.04 s. See
`reports/semantic-feedback-goal-gate-review.json`. Its fresh normal Actions
comparison is recorded separately below, not substituted for c991e86 evidence.

### Evidence locations

- Local full evidence archive: `reports/semantic-feedback-c991e86-evidence.zip`,
  15,986,665 bytes, SHA256
  `6244848389db7b35737713ed1cac7336b144dff25f08cd371d5bcdb0c6124d9e`.
  It includes the complete normal run, both interrupted runs, fresh tests and
  the failed development assertion. A copied archive is not a fresh run.
- [GitHub c991e86 artifact](https://github.com/corcondor/mortra/actions/runs/34885354682/artifacts/10364912625),
  SHA256 `f0d4f99947681327d64d470fd36d60c00e81cde04ec7eac88076eb12687be7c6`.
  This contains fresh Linux logs, XML, source seals, config, environment,
  contracts, histories, states, comparisons and verification.
- The corrected-gate run is
  [34887223359](https://github.com/corcondor/mortra/actions/runs/34887223359)
  at ce274f4. Both jobs succeeded. Its XML has 152 passed, 1 skipped, zero
  failures/errors, 33.331 seconds. Its normal run took 291.935 seconds and
  reproduced the initial acquisition/solve/reach counts with unchanged sources.

A second review finding concerned CI, not geometry semantics: the logged
pytest pipeline used an unspecified shell, so `tee` could mask pytest failure.
An isolated failing-pipeline probe returned 0 under `bash -e`, and 1 under
`bash -eo pipefail`. Explicit `shell: bash` was added in ff34b11. See
`reports/semantic-feedback-ci-gate-review.json` and
[GitHub's shell contract](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idstepsshell).
The previously reported test XMLs themselves contained no failures.

### Separate verdicts

| Claim | Verdict |
|---|---|
| Typed autonomous geometry composition and exact replay | Observed in normal runs |
| Acquired operations registered and later executed | Observed |
| Calls retained and used to generate later definition candidates | Observed |
| Later certified definition contains an earlier acquired call | Not observed: zero generation-2 acquisitions |
| New bounded states caused by learned operations | Yes, but more old states lost than gained |
| Monotone/net reachability expansion | No |
| Better held-out solved count or fewer candidates | No |
| Improved definition-inclusive compression | No for the eight acquired C definitions |
| Arbitrary symbolic geometry/NL solving or new primitive axioms | Not claimed |

The negative results do not establish anything against MORTRA's underlying
finite-morphism principle. They identify a working acquisition-to-call path
with insufficient selection quality and incomplete recursive acquisition under
the frozen policy. No new theory, heuristic, or task was inserted to reverse
that result.

## Follow-up development requested after review

The user requested completion of the recursive geometry DSL path rather than
stopping at the preceding negative result. The following is a new code version
and experiment, not a correction of the earlier outcomes. Training data, seed,
budgets, evaluation goals and initial coordinates remain unchanged. The 16
evaluation tasks are now a previously inspected regression set; no new broad
generalization claim is justified by improvement on them alone.

### Primary literature actually inspected

[DreamCoder, PLDI 2021](https://people.csail.mit.edu/asolar/papers/EllisWNSMHCST21.pdf),
sections 2 and 3, identifies the mismatch between old solution programs and a
new library, then optimizes over equivalent refactorings with library cost.
Its learned search policy is distinct from its learned library. This revision
does not implement its neural policy or claim its full algorithm.

[babble](https://arxiv.org/pdf/2212.04596), sections 4.1, 4.2 and 5, separates
candidate generation from library extraction. Extraction accounts for library
definition cost once, shared use, and redundant overlap. We reuse MORTRA's
existing pattern matching, non-overlapping replacement, use nodes and full
expansion checks. This is a bounded refactoring view, NOT a complete e-graph
implementation or general equational-theory learner. The original view is
retained for candidate generation as well as the refactored view.

### Fixed changes before the follow-up run

- Re-express learning histories with already certified definitions before
  subsequent abstraction. Preserve original execution histories and separate
  refactoring proofs. A proof is equality of fully expanded primitive programs
  under the sealed certified library, not equality at a sampled point.
- Use name-independent AST node counts for selection; count an operation,
  call or variable occurrence as one node and count the binder, parameters and
  body once for a new definition. Require positive marginal saving. Keep the
  original JSON-byte utility separately; node savings are neither bits nor
  measured execution speed. Recompute utility after every accepted definition
  against the refactored corpus, avoiding overlapping credit.
- Preserve both raw and refactored proposal views without duplicating their
  history weight in utility. E still flattens before each acquisition stage;
  within a stage its marginal selection also accounts for prior winners.
- Supply the existing typed generator's `binding_precondition` callback with
  exactly certified guards whose free variables are original inputs only.
  Unresolved intermediate-output guards are NOT guessed or discarded; they
  remain mandatory during execution. No witness is evaluated for this filter.
  Candidate guard checks/time and registry compilation time are recorded.
- No operation ID, desired parent/child definition, generation bonus, answer,
  evaluation-specific branch or new mathematical primitive was inserted.

Development regressions: 156 passed, 1 external-comparison skip, 44.94 seconds.
The supplied examples in these tests are not autonomous acquisition evidence.
The follow-up normal run and Actions evidence will be recorded below after
completion; implementation and development tests alone do not prove growth.

### Predeclared eight-cycle extension

Before starting this extension, the four-cycle training record at source commit
`d1e622820dd086373b1723a43c0ae0e5d5d2d711` showed an admissible candidate containing
a prior acquired call, supported by six histories, with seven net AST nodes
saved including its definition. The two selected candidates in that cycle
saved twelve each. This observation concerns training only; it is not a
generation-2 acquisition or an evaluation success.

The separate extension uses
`configs/theory-geometry-semantic-feedback-eight-cycles.json`, SHA256
`f44ce834ccc8914b2ad35d68e8a0990c35c8e406387541119f36103dd36807b5`.
Only the horizon changes from four to eight cycles in every training condition.
Domain, tasks, seed, all per-cycle and evaluation budgets, and acquisition
limits are identical by parsed-JSON comparison. The Python source and selection
rule are unchanged. The run will stop at eight cycles regardless of whether a
recursive definition is acquired. No candidate ID is privileged and no answer
or definition is supplied. B still learns in its first cycle only, and D is
C's final archive with no active roots, as in the original comparison.

The new config also corrects descriptive selection metadata to the rule
actually recorded by the d1e6228 Python implementation. The old four-cycle
config's historical `protocol.selection` text is not executable selection code;
the per-acquisition `selection_rule` and ranked `selection_rounds` are the
authoritative records for that run. The 16 goals remain regression tasks whose
outcomes have previously been inspected, not a new blinded evaluation.

The existing paper-guided geometry workflow gains a choice between these two
configs. Its push default is the eight-cycle extension. This does not create a
second competing CI pipeline or change the existing exact-kernel job.

### Completed four-cycle refactoring experiment

Source: `d1e622820dd086373b1723a43c0ae0e5d5d2d711`.
Local command (PowerShell, `PYTHONHASHSEED=0`):

```text
.venv/Scripts/python.exe scripts/run_theory_formation.py --config configs/theory-geometry-semantic-feedback.json --output reports/semantic-feedback-normal-d1e6228
```

Local duration was 674.223 seconds. Fresh
[Actions run 34888598466](https://github.com/corcondor/mortra/actions/runs/34888598466)
passed both jobs; its test XML records 156 passed, 1 external-comparison skip,
0 failures/errors, 50.906 seconds. Its normal experiment took 563.630 seconds.
Both runs have unchanged source seals and archives during evaluation. Parsed
non-timing summaries and complete adjacent-language reach differences agree.
The preceding shell-gate-only run 34887869294 also completed successfully.

| Condition | Registered / active definitions | Highest generation | Solved / tasks | Evaluation candidates | Reach states, inputs 1 / 2 |
|---|---:|---:|---:|---:|---:|
| A primitive | 0 / 0 | 0 | 8 / 16 | 922 | 80 / 74 |
| B first generation only | 2 / 2 | 1 | 8 / 16 | 922 | 68 / 62 |
| C recursive permitted | 8 / 8 | 1 | 8 / 16 | 922 | 54 / 47 |
| D C archive inactive | 8 / 0 | 1 | 8 / 16 | 922 | 80 / 74 |
| E flatten before acquisition | 8 / 8 | 1 | 8 / 16 | 922 | 51 / 44 |

All eight C acquisitions have positive marginal AST savings, but this is
training-description compression, not proved future utility. C has 8 / 7 new
states versus A on the two reach inputs, and loses 34 / 34 old states.
No solved goal uses an acquired call. Thus neither more solved goals nor net
bounded reach growth has been established. The extension is a separate test
of the remaining recursive-acquisition path, not a replacement for this result.

[Fresh Linux evidence artifact](https://github.com/corcondor/mortra/actions/runs/34888598466/artifacts/10366212596):
13,628,331 bytes, SHA256
`7768cf929622a67cef8cf809045a736112dda99176573909571d370f55805c10`.
It contains the exact config, source seal, environment, test log/XML, original
histories, refactoring proofs, candidate rankings, certificates and comparisons.
