# Target-Free Theory Formation

This is a bounded experiment in persistent theory formation, not evidence of an
autonomous mathematician or a new general algorithm. The baseline is
`6eb45fd60622dcb591f66331a07759d75ca29083` in `corcondor/mortra`.
Development is on `codex/theory-formation-20260913`.
Historical built/partial/not-built statements in THEORY.md and NEXT.md are not
retroactively changed.

## Persistent Learning Hypothesis

MORTRA is intended to improve cumulatively with continued computation,
but continued runtime alone is not considered improvement.

The intended loop is:

experience -> certified mathematical knowledge -> reusable representation /
theorem / procedure -> reduced or redirected future search -> access to
previously unreachable mathematics -> new certified experience.

A new acquisition counts as capability growth only when it produces at least one
measurable downstream effect: solves a previously unsolved task, proves a
previously open conjecture, reduces cost, is reused on a distinct unseen task,
enables a new representation/theorem, or changes the future search frontier.

The archive and the active search vocabulary are distinct. Self-generated,
external, and regression tasks have separate provenance. More entries are not
evidence of increasing intelligence. The longitudinal question is whether
knowledge acquired at cycle t improves search, representation, proof, or problem
solving at t+k. Two persisted phases are an initial test, not a long-run result.

## Implemented Versus Not Built

- Built: a persistent TheoryState containing definitions, empirical conjectures,
  exact certificates, counterexamples, proof dependencies, representations,
  executable reduction rules/recurrences, decisions, costs and open questions.
- Built: typed bounded composition, two-sample conjecture grouping, exact semantic
  deduplication, exact settling, certified rewriting before further exploration.
  Samples never license a theorem.
- Built: the engine chooses a nonconstant invented observable, invokes the
  existing common-invariant-space kernel, then derives and executes recurrences.
  No target q, basis, action matrix, readout or target theorem is accepted.
- Built: archive-preserving resume, fixed-input checks, ablations, and independent
  replay of original theorems/counterexamples and stored representations.
- Partial: theorem/concept feedback into future search. Certified reductions
  prune later candidates; reused concepts affect active vocabulary selection.
  Selection of computation kinds is an auditable least-visited/cost heuristic,
  not learned rational metareasoning.
- Partial: unknown equations retry after theory growth. Unknown closure or
  recurrence kernel requests remain archived but are not automatically retried.
- Partial: diversity is maintained by constructor/type coverage in the active
  concepts. All proved rewrite rules currently stay active. This is not a
  validated long-term retention or diversity guarantee.
- Not built: arbitrary procedure synthesis, a procedure generating another
  procedure, self-modifying Python, general algorithmic self-improvement,
  induction, conditional universal ring proofs, cross-domain theorem transfer,
  autonomous domain-signature creation, or evidence of new mathematics.

Theorems, representations and procedures are stored separately. A certified
reduction is an executable procedure, but its interpreter and the rule-discovery
algorithm were supplied by the developer. Similarly, recurrence coefficients are
derived; the recurrence evaluator was not invented by MORTRA. Do not describe
either as a newly invented general algorithm.

## Existing Kernels Reused

`theory_domain.py` adapts:

- `abstraction_correspondence.prove_identity` and differential-expression
  normalization for universal identities over rational differential polynomials.
- `rigid_fold_problem_discovery.apply_fold_generator` and the existing reachable
  frame closure for the complete 24-orientation model.
- `discover_action_observable_basis` for common invariant linear closure;
  auxiliary coordinates, action matrices and readout are derived.
- `discover_linear_observation_recurrence` for exact recurrence certification.

`theory_formation.py` uses the existing `library_compression` matcher and
instantiator. Formal variables are mapped consistently to its f0/f1 hole format.
Substitution is allowed only for universal differential identities. Finite
sensor identities authorize exact subtree replacement, not universal variable
substitution. Rewrite steps strictly decrease syntax size, or a tie-breaking
order, so learned reductions terminate.

The q-directed task-solving entry and its certificates are not replaced.
This mode generates its own questions. Generic finite-table inputs provide only
states, total actions and rational sensors, not answers or named concepts.

## Exact Scope

Experiment A uses two formal generators with add/multiply/negate/differentiate.
The exact prover supplies the laws of a commutative differential ring. False
identities receive exact rational jet counterexamples realizable by polynomials.
Only scalar identities have a universal prover; other logical questions are
unknown rather than numerically promoted.

Experiment B uses the complete finite model of 24 fold orientations. It omits
centres, panels, self-intersection and legality. The theorem is about this
complete finite model, not collision-free origami or all geometry. One-hot
coordinates are initial infrastructure; a smaller invariant space is acquired.
The current recurrence scope is repeats of one action from initial model index
zero. Use at later lengths stays inside that scope.

Certificates trust Python, SymPy and the existing exact kernels. They are not
LCF proof objects and do not inherit Isabelle/HOL's trust guarantees.

## Frozen Experiments

Install only formally declared dependencies:

```bash
python -m pip install -r requirements-test.txt
python -m unittest discover -s tests -p test_theory_formation.py -v
python scripts/verify_theory_formation.py --output build/theory-verification
```

Output directories must not already exist. The verification harness executes
the normal entry in separate processes for each domain and condition:

```bash
python scripts/run_theory_formation.py --config configs/theory-ring.json --output build/theory-first --cycles 240
python scripts/run_theory_formation.py --config configs/theory-ring.json --output build/theory-continued --resume build/theory-first/state.json
```

Conditions are `learn`, `no-theorems` and `no-representations`. In the latter,
later recurrence requests reacquire their representation. The no-theorems
condition also refuses use of learned rewrite rules and recurrence procedures.
Each output contains the actual command, SHA, code hashes, configuration,
full state, event log, conjectures, certificates, dependencies and decisions.
There is no interactive input channel during execution. Hashes check source and
input consistency; they are not cryptographic proof that no external interference
occurred. Development runs are never counted as frozen Actions evidence.

After A/B code freeze, add only a held-out domain configuration at
`configs/theory-heldout.json`. Do not tune the implementation on its results.
The existing workflow runs that file when present. Its results must be reported
even if the scientific criteria fail. The held-out model is developer-declared;
it is not an independent external benchmark.

## Measurement And Interpretation

Archive growth is not a reward. Downstream records identify the earlier theorem,
later expression/conjecture, actual rewritten term, eliminated call and scope.
The paired comparison covers shared completed conjecture IDs; whole-run totals
may cover different frontiers and must not be compared as equal workloads.

Costs include closure acquisition/reacquisition, recurrence proving, ordinary
proving, rewrite match attempts, pruning and wall time. `semantic_nodes` counts
expression-tree nodes, not CPU instructions, arithmetic bit complexity or
actual execution time. Canonicalization, matching and audits may outweigh fewer
prover calls. No end-to-end speedup follows just from a smaller expression.
Independent replay is charged to evaluation, not presented as zero-cost reuse.

Proof depth is the saved dependency depth of the proof that ran. It is not a
lower bound on necessary proof length or evidence of human problem difficulty.
Minimum scientific criteria are explicit in verification.json. Infrastructure
success and scientific success are separate; CI stays informative on negative
scientific results.

The standalone criterion `future_search_reduced` records only term/conjecture
pruning. The harness additionally credits avoided closure reproving after
matching recurrence requests, matrices, readouts, scope and outcomes against the
no-representation-reuse run. It preserves the standalone result and records
`comparative_criteria` separately. Neither measurement claims lower wall time.

The underlying hypotheses of unlimited growth, preserved long-run diversity,
external transfer, and reaching previously inaccessible mathematics remain open.

## Shared CI

The existing `Verify MORTRA Kernels` workflow is extended, not duplicated.
Push this research branch, or dispatch `worker-ci.yml` with
`verification_suite=theory-formation`, `target_ref=<commit>`,
`expected_sha=<full commit>`.

It first reproduces the existing 351-test q-directed suite, normal acquisition,
stored reuse and legality refusal. It then runs theory guard tests and fresh
A/B experiments plus both ablations, including process restart and replay.
Python is 3.12.10; versions are installed from requirements-test.txt and recorded
by the existing environment recorder. The existing q-directed artifact contains
the new `theory/` subtree and theory test/run logs. No release schedule is changed.

## Literature And Reading Scope

These are design references, not claims of identical algorithms or guarantees:

- Colton, [Automated Theory Formation in Pure Mathematics](https://link.springer.com/book/10.1007/978-1-4471-0147-5):
  publisher contents/metadata checked, including Inventing/Making/Settling and
  Assessing chapters. Full book not retrieved; do not report it as fully read.
  The concept/conjecture/proof/assessment separation is the design correspondence.
- Johansson et al., [Hipster](https://smallbone.se/papers/hipster.pdf), sections
  2.1 and 3: typed conjecture generation, empirical grouping versus proof,
  certified lemmas feeding later proof, and retry after theory growth were read.
  MORTRA does not implement their induction tactics or LCF reconstruction.
- [QuickSpec 2](https://smallbone.se/papers/quickspec2.pdf): retrieval was
  intermittent. The directly readable account used here is Hipster section 2.1;
  do not claim the entire QuickSpec paper was read. The design uses certified
  reductions to prune future terms, not sample equality as proof.
- [DreamCoder](https://arxiv.org/abs/2006.08381): abstract/overview checked, not
  a full-text reading. No neural recognition or wake-sleep learner is implemented.
- [Stitch](https://arxiv.org/html/2211.16605v1): sections 2--4 and discussion of
  utility/compression read. Description reduction and downstream search benefit
  are different measurements. This change uses existing matching infrastructure,
  not a new Stitch implementation or its optimization guarantees.
- Russell, [Metareasoning](https://people.eecs.berkeley.edu/~russell/papers/mitecs-metareasoning.pdf):
  cost and value of computation discussion read. The present selector records
  a heuristic decision; expected utility/compression is not learned.

The original developer-known test identities are fixtures, never normal-run
inputs. Post-run mathematical novelty assessment is a separate evaluation
record and must not feed a frozen run.
