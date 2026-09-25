# Frontier v1.2 Adaptive Designer: Preregistration

This protocol is fixed before any new benchmark result is observed. No prior
worlds or results are training inputs. No experiment-level pass fraction is set.

## Frozen experiment

The 18 files from c0f9f7b2c55d01bdb300b1ebb060f55b6c4d0902 remain
unchanged. The MORTRA baseline originates at
483d1592e5cd0d2b23d474cc79e217b121fd1fbe. The generic language, 14 existing
mutation primitives, semantics, Player, StructuralLearner, q=.90, cutoff=1e-7,
selection rule, task sampler, full-information diagnostic and holdout method
are reused directly. Uniform must reproduce frozen v1.1 on correctness fixtures.

Stage 1 uses independent seeds 3101,3202,3303, five generations and eight slots,
Adaptive/Uniform only. Stage 2 uses 2101,2202,2303,2404,2505,2606,2707,2808,
ten generations and eight slots, Adaptive/Uniform/Random/Size-only. All four
conditions use the same newly generated G0 for each seed. Initial pool remains
32, tasks 100, checkpoints 1,2,4,...,8192, horizon 2048, max board 32, oracle
cap 250000, dense-K guard 512 MiB. Stage 1 uses these same measurement settings.
No extra candidate is generated to replace an invalid/no-op proposal.

## One fixed learner: context-binned UCB1

The context key is (floor(log2(reachable-state count)), B80 reached/unreached).
These are generic structural/performance summaries, not mechanic labels.
Rules, state-variable count, action count, area and selection D are also
recorded, but are not extra UCB keys. Each context starts with empty statistics;
there is no learned-state transfer from Stage 1 or other seeds/conditions.

For every proposed primitive, record the candidate outcome and update:

```text
r = D_candidate - D_parent
    if candidate_valid AND full_info_success>=.8 AND final_selection_success>=.8
r = 0 otherwise
```

Invalid/no-op/unresolved candidates have zero proposal utility and consume a
slot. An unresolved resource outcome is not a Player task failure. B80/B90
deltas are reported only when both crossings are finite; censored cases retain
both original values and a censor flag. They do not enter the UCB reward.

D ranges from 0 to 13 under the frozen checkpoints. For the UCB confidence
formula only, normalize reward as x=(r/13+1)/2 in [0,1]. For context count n
and arm count n_a, use mean(x_a)+sqrt(2 log(max(1,n))/n_a). Untried arms
take precedence. Probability is uniform among UCB maximizers, zero elsewhere.
Throughout generation 1 all 14 primitive probabilities are 1/14 even though
statistics update after each slot. There is no softmax, probability floor,
learned weight, reward clipping, or result-dependent constant.

Mutation RNG remains derive(seed,generation,slot,'mutation'). Always consume
the frozen uniform-family draw before calling frozen mutate. In generation 1
Adaptive uses that draw as well, giving A/B identical paired proposals. Later
Adaptive replaces only the family choice using a separate UCB tie RNG
derive(seed,generation,slot,'proposal'). Mutation internals consume the same
remaining RNG stream. Selection still runs the frozen choose function after
eight slots, with its unchanged RNG and parent inclusion.

## Information boundary

The learner receives only frozen numeric Context and Outcome dataclasses.
They cannot contain tasks, goal paths, game semantics or holdout fields. Full
information contributes only the permitted success scalar. Evaluation objects
are converted to this whitelist before reward updates. Tests reject extra
fields and wrong input types. World rules remain visible to the mutation
implementation, not to the UCB learner. All proposals, rewards, context tables
and chosen families must be exactly replayable from saved histories.

Stage 1 advances on correctness, not efficacy: changing finite probabilities,
equal slot counts, identical G0, unchanged selection, replayable updates and
exact Player selection-checkpoint reproduction. No holdout is generated in
Stage 1. Poor rewards or performance must not block Stage 2 or trigger tuning.

## Post-evolution holdout

Only after all 32 Stage 2 evolutions complete, freeze up to 500 unused
distance>=4 start-target pairs per (seed,genome), using the previous distance
bins, reservoir/redistribution and seed root 2026092502 with
derive(root,seed,hash,'generation-holdout'). Exclude the union of same-genome
selection pairs from all new initial candidates and all four conditions.
Short populations are enumerated without replacement; no regeneration.
The same world receives the same holdout across generations and conditions.
Holdout evaluation never updates the learned graph, selection, or UCB tables.

Reproduce archived selection checkpoints exactly, then measure holdout on the
same frozen graph. Use the unchanged full-information core separately. Report
all 352 frontier records and unique-world counts separately.

## Endpoints and reporting

Primary comparison is Adaptive vs Uniform, paired by new seed:
first eligible generation; D_holdout change from first eligibility to G10;
final D, success, B80; frozen failure categories; frontier per equal proposal
budget. Report no eligibility and censored B80 separately, not as failure
substitutions. D may increase because of permanent failure, so report success,
full-information success and core-solvable D beside it.

Save probabilities for every slot/generation, counts, valid/eligible/selection
rates, raw mean reward, all UCB states, CPU and memory. Report invalid slots and
actual evaluated candidates separately from the equal 80-slot budget. Compare
overall usage concentration with context-specific policies. A deterministic
UCB choice on one step is not by itself evidence of premature collapse.

The requested post-hoc proposal audit reports whether high-probability arms
had higher observed reward within the same context/run. UCB may deliberately
choose low-evidence arms. These are selection-biased observations, not causal
counterfactual outcomes of untried edits. Do not evaluate new edits or retune.

Report all eight seeds, negative cases, selection versus holdout differences,
compute and candidate efficiency. Make all twelve requested plots. A positive
result would support learning which existing generic mutation operators to
propose, not inventing new operators. No performance-based algorithm change
after the run. Stop after Stage 2 and reporting. External interruption is
RUN_NOT_COMPLETED, not a theoretical failure.
