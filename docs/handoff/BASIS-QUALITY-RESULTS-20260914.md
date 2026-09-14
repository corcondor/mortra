# Primitive basis quality: fresh shared-CI results

The finite-frame action alphabet has certified redundancy. Neither autonomous
reacquisition of removed operators nor a search benefit from the three tested
acquired macros was demonstrated. This is a bounded basis-quality result, not
an upper bound on MORTRA's expressivity and not a recommendation to minimize
primitive count.

## Reproduction and provenance

- Repository: `corcondor/mortra`.
- Branch: `codex/theory-formation-20260913`.
- Tested source: `44d2ff88a36c1483d2258e30a862a82a50611367`.
- Workflow: `Verify MORTRA Kernels`, existing `worker-ci.yml`.
- Fresh [run 34801823741](https://github.com/corcondor/mortra/actions/runs/34801823741): success.
- [Artifact 10331504062](https://github.com/corcondor/mortra/actions/runs/34801823741/artifacts/10331504062):
  `q-directed-34801823741-1`, 7,220,408 bytes.
- Artifact digest: `6e8ffe4f591a2109fbc0fa20b36fde8e48fead547ecc1b570e948751baea1b01`.
- Linux x86_64, Python 3.12.10, SymPy 1.14.0, python-flint 0.9.0,
  NumPy 1.26.4, pytest 8.4.1. Complete versions: `environment.json`.
- Fresh q-directed suite: 351 passed, zero failed/skipped. Normal acquisition,
  saved reuse, collision refusal and reuse-only refusal passed.
- Separate Theory tests: 22 passed; DSL/library/semantic/corpus/temporal/basis
  tests: 145 passed. These sets overlap the 351 set; do not sum them as a
  unique repository-wide test count.
- Basis experiment: 182.144 seconds; source seal unchanged; no runtime errors.

The artifact contains every command, configuration, target, evaluator-only
witness, normal-run state, cost counter, failure and operator certificate.
The commands are also in `BASIS-QUALITY-20260914.md`. The main invocation was:

```text
python scripts/verify_basis_quality.py --plan configs/theory-basis-quality.json --output <new-directory>
```

SHA256 of fresh files inside the artifact's `basis-quality/` directory:

| File | SHA256 |
| --- | --- |
| config.json | 93a80caf966d5fcf1c0910ecdb5a68140cc65b27f21b6109c1ac3d644a765e60 |
| plan.json | 86f852372685e7aa1116cabaa2da6c3c41fbb57d8f790320009791008ca49e49 |
| tasks.json | 44243bc7bd3880541efc389fab4dd825720110b79b46217e65ff497aceb18c70 |
| verification.json | 5656bf5244ddd7ab60ac397ff08c34a7323bef0452ae40772311101351bf2579 |

The evaluation set was fixed before acquisition: seed 923114, 24 scalar-value
goals and 12 Boolean-value goals. Each query had the same 256 planner budget
and 100,000 interpreter-work budget. No witness was given to the query solver.
Training had 80 cycles and a 180-second ceiling, not a requirement to spend
180 seconds. The learner received no removed-operation target.

## Actual executable inventory

Here `S` means an exact rational-valued function on the declared 24 frames;
`P` means a Boolean-valued function on those frames. The following is the
initial basis of the tested **Theory fold-frame domain**, not a count of all
MORTRA adapters. `var` and `const` are terminals, not geometric actions.

All rows are checked by `Domain.type_of` and executed by `Domain.evaluate.ev`.
Terminal generation uses `Domain.seeds`; composition uses `Domain.compose`.
`Theory` and `Vocabulary.solve_observation` both use those actual paths.
`Domain.settle` checks finite model equalities. Universal scalar-argument
checks use `SymbolicScope`; this is a stronger, separately recorded check.

| Name | Input -> output | Parameters and preconditions | Executed meaning | Normal generation / verifier |
| --- | --- | --- | --- | --- |
| var | () -> S | Declared sensor name, F11 through F33 | Read a frame entry | Seed; exact model |
| const | () -> S | Exact rational literal; normal seeds are only 0 and 1 | Constant function | Seed; exact rational/model |
| pull | S -> S | Declared A, C, G or T action; scalar argument | f composed with T_g | Composition; exact action map/model |
| add | S x S -> S | Two scalar arguments | Pointwise addition | Composition; polynomial/model |
| mul | S x S -> S | Two scalar arguments | Pointwise multiplication | Composition; polynomial/model |
| neg | S -> S | Scalar argument | Pointwise additive inverse | Composition; polynomial/model |
| eq | S x S -> P | Two scalar arguments | Pointwise exact equality | Composition; exact model |
| not | P -> P | Predicate argument | Boolean complement | Composition; exact model |
| and | P x P -> P | Two predicate arguments | Boolean conjunction | Composition; exact model |

Thus there are **9 syntax families**, **7 composition families**, **10
parameter-instantiated composition operators**, and **11 initial scalar seeds**.
The input language accepts more rational literals than the normal seed
generator supplies. Expressibility and normal parameter search are different.

Dynamic operations are separate: `use` executes a saved typed definition;
`represented(action_word)` executes a certified matrix readout;
`recurrence(natural)` executes a certified recurrence. Their bodies, signatures,
dependencies and scope come from the archive. `word` and `natural` are their
auxiliary inputs. The executable differential-ring adapter has `diff` in place
of `pull`; its operator redundancy was not tested here. Neither were panel
geometry, displacement, collision avoidance or general iteration/branching.

## Deletion comparison

All deletion conditions, including baseline B, disabled acquisition of matrix
representations and recurrences. This prevents those wrappers from silently
reintroducing a removed action. Ordinary composition, theorem checking,
library acquisition and semantic editing remained enabled in every condition.
No replacement operation was injected.

Lengths count syntax-tree nodes of the returned program, not serialized bits.
They are **first-found witnesses**, not globally shortest programs. Their mean
is conditional on success. Search counts include common seeds and attempted
applications; candidates count actual candidate evaluations. Work is the
instrumented normal interpreter count, excluding independent replay.

| Removed from B | Correct / 36 | Mean found length | Mean depth | Search count | Candidates | Normal work | Total query seconds | Correct after learning |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| None | 21 | 2.476 | 0.762 | 5663 | 5447 | 455007 | 2.022 | 21 |
| var | 3 | 2.000 | 0.667 | 8494 | 8278 | 2306001 | 8.019 | 3 |
| const | 18 | 2.556 | 0.778 | 5883 | 5667 | 501792 | 2.067 | 18 |
| pull, all parameters | 21 | 2.476 | 0.762 | 4983 | 4911 | 441087 | 1.980 | 21 |
| add | 21 | 2.476 | 0.762 | 5405 | 5189 | 442296 | 1.958 | 21 |
| mul | 18 | 2.389 | 0.722 | 5959 | 5743 | 502521 | 2.152 | 18 |
| neg | 20 | 2.500 | 0.750 | 5689 | 5473 | 467825 | 2.060 | 20 |
| eq | 9 | 1.778 | 0.444 | 4477 | 4261 | 357706 | 1.615 | 9 |
| not | 21 | 2.476 | 0.762 | 5663 | 5447 | 455007 | 2.001 | 21 |
| and | 21 | 2.476 | 0.762 | 5663 | 5447 | 455007 | 2.036 | 21 |
| A only | 21 | 2.476 | 0.762 | 5493 | 5313 | 451527 | 2.002 | 21 |
| C only | 21 | 2.476 | 0.762 | 5493 | 5313 | 451527 | 1.977 | 21 |
| G only | 21 | 2.476 | 0.762 | 5493 | 5313 | 451527 | 2.003 | 21 |
| T only | 21 | 2.476 | 0.762 | 5493 | 5313 | 451527 | 2.005 | 21 |

The original domain has 10 operator branches. Removing all pull parameters
leaves 6; removing a single parameter leaves 9. Removing `eq` leaves 7 because
`not` and `and` then have no generated predicate argument. Other operator
deletions leave 9. Removing a terminal does not change the operator count.

Median found depth is in each condition record. Same-input comparisons exclude
failed tasks from length deltas: removing `const` added two syntax nodes in
total over the 18 common successes. Other deletion conditions changed found
length by zero on common successes. This does NOT assign a cheap length to a
lost task. The lost/gained IDs are preserved in `paired`.

Query-time prover calls are zero because correctness is checked by exact
finite replay, not a new theorem-prover invocation. The baseline performed
504 replay comparisons (21 solutions x 24 states); every condition records its
checks, replay work and verification seconds separately. Training proof calls
are in `acquisition_costs`, not included in query-time zero.

## Semantic reconstruction and classification

The existing typed planner found these action-map witnesses without a supplied
word. `K_g(f) = f composed with T_g`. All four certificates compare the complete
24-state maps, so they cover **every rational-valued input function**, not just
the nine sensors:

```text
K_A = K_C K_C K_C       14 search steps; depth 3
K_C = K_A K_A K_A       14 search steps; depth 3
K_G = K_T K_T K_T       31 search steps; depth 3
K_T = K_G K_G K_G       31 search steps; depth 3
```

One primitive call is replaced by three calls. These certificates do **not**
preserve centre displacement, panel history or legality. They must not be used
as rigid-fold equivalences on the full geometric state.

| Primitive | Classification supported by this run | Necessity / redundancy / usefulness |
| --- | --- | --- |
| eq | Essential in declared initial typed fragment | Only constructor producing predicates from scalar inputs; deleting it loses all 12 predicate tasks |
| not | Essential for arbitrary predicate arguments in declared typed fragment | Complete Boolean closure without not cannot produce complement; no loss on this particular solved cohort |
| and | Essential for arbitrary predicate arguments in declared typed fragment | Complete Boolean closure without and cannot combine independent predicates by conjunction; no loss on this solved cohort |
| pull:A, pull:C, pull:G, pull:T individually | Redundant and removable **in this tested scope/budget** | Certified three-call replacement; same 21 successes and lengths, 170 fewer search counts for each deletion |
| var, const, pull as a whole, add, mul, neg | Unresolved semantic classification | No matching universal reconstruction/necessity certificate from this audit; task losses or bounded search failures are not impossibility proofs |

No primitive was classified as absent from the runtime. No autonomous acquired
macro was certified as a replacement for a deleted operator. The requested
five-way classification is therefore incomplete: six syntax families remain
unresolved rather than being assigned an unsupported category.

Symbolic reconstruction searches for add, mul and neg each exhausted the
512-step budget. Independent function arguments were retained. This does not
show that these operations are impossible to express. In particular, normal
search seeds 0 and 1, although the literal constructor supports any rational;
failure is not a theorem about all allowed parameter values.

Action pairs A/C and G/T commute on all declared frames. Cross-pair actions do
not. No two one-step action maps are equal. Every pair has 24 destination
states in common because these maps are permutations; destination overlap
alone therefore says nothing about operator equivalence. Bounded role analysis
checked 1,494 composed programs: for example pull/add shared 28 observed
behaviors and pull/neg shared 12. These are not universal operator identities.
That bounded pool did not cover every pair involving terminals or `and`; a
complete nine-family pair classification remains unmeasured.

## Autonomous reacquisition: negative and limited

In all 14 deletion/baseline normal runs, the post-learning solved count equaled
the corresponding initial count. Only the no-var run acquired definitions
(8); it remained at 3/36 and did not reconstruct a state-dependent sensor.
No-var builds constant expressions and does not acquire external sensor input.

The other 13 runs acquired no definitions. This is not evidence that their
mathematical languages cannot express useful replacements. In B, 68 natural
experiences arrived; all 297 abstraction source positions were rejected by the
existing admissibility condition `context_operations >= 2`. There were zero
anti-unification pairs. The other 12 zero-definition conditions also had every
source position excluded. The ordinary exploration had not produced eligible
multi-operation material within 80 cycles. This is a measured limitation of
this wrapper-disabled run, not a recurrence of the repaired 512-item feedback
bug and not a reason to revoke earlier self-expansion results.

The target-directed evaluator's action-map witnesses above were **not** inserted
into these normal runs and do not count as autonomous reacquisition. Enlarging
the run or changing eligibility after seeing results would be a separate study;
this run's negative evidence is retained unchanged.

## Adding actual acquired macros

A separate fixed full normal producer acquired the candidates before evaluation.
It took 18.936 seconds inside the learner, admitted 1,763 experiences, and kept
the 512-item FIFO sample. Candidate order was acquisition order, not task score.
`R` below denotes its actual certified readout `R-b8f032907b167b70`.

| Archive ID | Actual acquired body | Added-library bits, including dependencies | Correct / 36 | Search count | Normal work | Total query seconds |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| none | Initial B | 0 | 21 | 5663 | 455007 | 2.022 |
| 6e03302e5fc8a62d | h(u) = u + R(A) | 30568 | 21 | 5812 | 496464 | 9.365 |
| 85edc08a9734f568 | h(u) = u - F11 | 30224 | 21 | 5812 | 497720 | 9.396 |
| 535c04daffac4743 | h(w,u) = R(w) + u | 13336 | 21 | 5921 | 547911 | 10.006 |

All three conditions retained the baseline found lengths and solved task IDs.
None of the final solution bodies retained a macro call. This does not mean
the candidates were never used during search: the first condition recorded
314 certified rewrites and zero represented executions; the third recorded
918 represented calls. Expansion/validation/rewrite costs are retained.
The third definition had 26 uses in the producer's training history; training
reuse is not evidence of evaluation improvement.

The library column charges the selected operation and its transitive archived
dependencies once, not once per task. Individual query results also retain
program bits and program-plus-library bits. No shorter-description benefit
appeared here. Query total time includes preparation, archive hashing,
definition matching and accounting. The 4.6-4.9x total-time ratio is therefore
not a claim that the mathematical operator alone became that much slower.
Pure evaluation subtimes were 0.669 seconds for B and 0.815, 0.829 and 1.317
seconds for the additions. These measurements do not establish a steady-state
throughput ratio.

## Empirical Pareto result and ten answers

The predeclared axes were syntax-family count, solved coverage, conditional
mean found length, search count and normal execution work; no weighted sum.
The nondominated conditions were **B without pull**, **B without mul**, and
**B without eq**. Original B was not on this empirical frontier. The latter
two trade away solved tasks and are not globally better. Using family count
does not distinguish removal of one pull parameter; parameterized branch counts
are retained separately. Conditional lengths and bounded coverage make this a
descriptive frontier, not a proof of basis optimality.

1. **How many?** The tested runtime has 9 syntax families, 7 composition families,
   10 instantiated composition operators and 11 scalar seeds. This is not a
   repository-wide or theoretical limit.
2. **Which necessary?** eq, not and and have scoped typed/Boolean certificates.
   Those certificates do not show necessity for every closed scalar task.
   Six families lack a decisive operator-level certificate in this audit.
3. **Which reconstructable?** Each individual fold parameter has a certified
   three-call replacement. No further universal witness was obtained.
4. **How much longer after removal?** Operator witnesses replace one call by
   three. On common successful value tasks, const removal added two syntax
   nodes in total; other removals added zero. Global shortest lengths are unknown.
5. **How much more search?** All-task search changed from 5663 to 8494 without
   var, 5883 without const, 5959 without mul and 5689 without neg. Their task
   coverage also fell. Individual action deletion reduced the count to 5493;
   whole-pull deletion reduced it to 4983 without changing the 21 successes.
6. **Autonomous reacquisition?** Not demonstrated. Most normal conditions had
   no eligible multi-operation abstraction sources, as detailed above.
7. **Clear redundancy?** Yes, individual action maps in the 24-frame scope.
   Similar observed sensor values do not establish more.
8. **Smaller with equal performance?** On this cohort, removing pull or add
   retained the same solved tasks and reduced search/work. This is not a
   certificate that the full operation family is dispensable on unseen functions.
9. **Do acquired macros help?** Not these three on this fixed evaluation.
   Correct count and lengths were unchanged; search, work and total time rose.
10. **Is B Pareto-optimal?** Not among these tested conditions on the declared
    axes. No global optimum or smallest sufficient basis was established.

## Change boundary and retained results

`theory_domain.py` filters real terminal/operator/action availability and records
the filter in scope. `Theory` and its CLI persist that setting; zero representation
slots are now an explicit supported disable setting. `theory_vocabulary.py`
supports Boolean result specifications through the existing planner and exact
replay, records found lengths/depths, and charges selected-library dependencies.
The new harness, plan and eight regression tests evaluate deletion/reconstruction;
the existing workflow executes them. No replacement math operator, LLM,
universal machine or new frontier generator was added. Normal full-signature
behavior and earlier DSL feedback remain covered by regression tests.

The preceding temporal-utility study remains separately frozen on
`d545d2915ae434194e213bf110c69f0ece6e37a4`,
[run 34800481257](https://github.com/corcondor/mortra/actions/runs/34800481257).
Its results are in `TEMPORAL-UTILITY-RESULTS-20260914.md`. This basis evaluation
did not feed either study's external answers back into the active selector.
The reports preserve both useful local effects and the absence of demonstrated
external generalization improvement.
