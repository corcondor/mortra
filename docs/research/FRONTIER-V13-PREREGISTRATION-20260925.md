# Frontier v1.3: Offline Structural Edit Reward Prediction

Registered before training. User specification is the authority; no new evolution.

## Immutable Inputs

- v1.2 run 36107649938, source c060d5c9549eaae913bd7b9555ad2289ff96ff8c.
- Landscape run 36120576842, source 3ccea4503a29a7e0f759694c26f1c5deae7c0155.
- Baseline 483d1592e5cd0d2b23d474cc79e217b121fd1fbe, q=.90, cutoff=1e-7 unchanged.
- Exactly 50 parents and 7,000 saved candidate attempts, including invalid attempts.
- Source hashes, archive hashes, every returned genome hash and archived exact reward checked.
- No engine, oracle, mutation, learner or fixed-field calls in this experiment.
- No game holdout artifacts downloaded. Selection-only source archives are whitelisted.

## Information Timing

Each parent has one feature snapshot at its earliest frontier occurrence, before
the next slot 0. Repeated occurrences are not additional independent rows.
Previously observed parent D/B50/B80/B90/success/full-info/coverage are allowed.
For G10-only parents, terminal history is past information, but a hypothetical
next UCB proposal is NOT called a recorded proposal.

Candidate outputs are isolated as labels. Static extractor accepts only parent
and returned candidate genomes, primitive, explicitly whitelisted parent metrics,
pre-proposal UCB decision and earlier proposal events. It never receives an
evaluation record. Mutation failing to return a genome is a pre-evaluation fact;
this has an explicit availability indicator. Invalid candidates remain in all
7,000-row comparisons; they are not silently removed.

## Features

M0 primitive; M1 actual coarse UCB context plus arm count/mean/bonus;
M2 parent static structure and past metrics plus primitive;
M3 M2 plus concrete static edit; M4 M3 plus UCB and past proposal statistics.
The M3-M2 contrast isolates concrete edits. M3-M1 is primary, M4-M3 secondary.

Static spatial edges are undirected four-neighbor free-cell adjacency, not actual
transition reachability. Read/write dependencies are syntax-derived rule edges;
cycles are cyclic SCCs and depth is the longest path in the condensed DAG.
AST edits count ordered scalar syntax leaves. Rules have no stable unique IDs;
sequence diffs and positional edge changes are syntactic approximations, not a
claim of semantic program equivalence. No named game-mechanic features are added.

## Models And Splits

Eight leave-one-seed-out folds, seeds 2101 through 2808 as in the protocol.
All rows for a parent stay in one fold. Parent hashes must be disjoint across
train/test. IDs remain only in a separate grouping file.
Ridge alpha=1, SVD; HistGradientBoostingRegressor depth=4, learning_rate=.05,
iterations=200, L2=1, random_state=130025, no early stopping, leaf limit=31,
min leaf samples=20, bins=255. No search. Both use train-only standardization.
Missing parent metrics use zero plus explicit availability flags.
The same two regression algorithms predict secondary eligibility/positive
indicators and observed delta_D. The indicator readout .5 is fixed in advance.
Dependencies: numpy1.26.4 scipy1.16.1 scikit-learn1.7.2 pandas2.2.3 matplotlib3.10.5.

## Ranking, Replay And Statistics

Spearman uses average ranks; constant truth/prediction is undefined, not zero.
Pairwise accuracy excludes equal true rewards and gives predicted ties .5.
Top-1 regret, top-5 overlap and precision integrate exact boundary ties.
Replay uses one seeded random priority vector shared across models to choose
exactly eight candidates, never a hash-derived fitness ranking.

Uniform-8: 10,000 seeded samples without replacement per parent, subset-distribution
quantiles and Monte Carlo standard errors. UCB uses the first recorded pre-slot
probabilities frozen over eight distinct candidate draws; this is an offline
snapshot comparator, not simulated sequential online UCB learning. Terminal-only
parents are separate. Paired M3-UCB differences use only recorded common parents.

Cheap pools: sizes8/16/32/64/140, 1,000 paired random subsets at sizes below140;
full140 pool once. Same pool and tie priorities for every model. Eight evaluated
candidates in every case. Oracle sorts archived reward, not eligibility or
delta_D. Oracle mean/best reward is an upper bound on those reward metrics, not
on every secondary metric. Headroom ratio omitted if denominator<=1e-12 (a
numerical reporting guard, not a success threshold). All absolute differences kept.

Aggregate parents within seed, then eight seeds equally. Publish all seeds,
median/range, M3-M1 paired differences, train/test contrast, and reward classes.
No p-value-centered claim, no after-the-fact 7/8 pass threshold. Dependence among
nearby parent worlds and common CV training sets remains a limitation.

## Gates And Stop

Stage0 unit tests, source/dataset/label separation and hash gates. Stage1 only
2101 held out, all frozen settings; performance cannot affect progression.
Stage2 repeats all eight folds. Repeated2101 predictions must match bit for bit.
Finish offline replay, ten figures and Japanese report; then stop. No online
integration, result-driven feature/model/reward changes, or candidate evaluation.
