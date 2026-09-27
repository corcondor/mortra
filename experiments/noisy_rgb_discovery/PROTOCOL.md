# Noisy-RGB distinguishing-action acquisition: fixed development protocol

This specification is committed before the new arena-learning outcomes. It is
not an external preregistration. Existing seeds 95027004 and 95027005 are known
development seeds, not fresh worlds. No seed replacement or outcome-driven tuning.

## Question and inputs

Can the supplied statistical observation table discover distinguishing action
suffixes from E=[empty] using noisy RGB only? The algorithm is supplied by the
developer; the run, not Codex, selects the suffix witnesses.

Use the attached full 7x7x3 PhysicsArena3D without geometry or dynamics changes,
the supplied DelayedJumpArena definition, and its supplied noisy_batch renderer.
Record hashes. Never shrink the arena after observing cost or failure.
Two camera conditions: (0,0) and (.32,-.24) sensor-plane pixels. These are not
arbitrary 3D camera extrinsics. Four views, 12x12 RGB each, 8 exposures per batch,
same as the previous noisy holdout. Physics is deterministic; sensor is noisy.
Reset and public action-history replay are allowed and every replay action is
counted. Learner inputs contain no clean pixels, state IDs, access states,
previous suffixes, success flags, goal predicates, or pretrained graph.

The environment still renders its existing visible scene, including its goal
marking. That is RGB, not an extra success label. raw_goal and state token calls
raise during this experiment. The unchanged table's goal field is always False.
Neither fixed-field reasoning nor q is needed for this acquisition experiment.
The missing historical v2_source_excerpt is not substituted or imported.

## Algorithm and fixed numerical choices

Extract StatisticalObservationTable verbatim using AST; do not import the old
experiment at module level. Initial S=[empty], E=[empty]. Suffix ae is added only
when currently equivalent histories disagree after a followed by an existing e.
Record both witness histories, all prior suffix scores, the new score, threshold,
and query count. Preserve reference closure, consistency, and tie ordering.
Cache symmetric comparisons of immutable cached summaries; unit-check against
the unmodified table and the non-memoized adapter.

Use the reference score

    z(x,y) = sqrt(mean_j((mean_x-mean_y)^2 /
                        (var_x/n_x + var_y/n_y + .01^2))).

Calibrate from two independent batches for each of the first 100 public action
histories in the reference length/lexicographic order. For each world/camera,
threshold = max(same-history z) * 1.18. The .01 noise floor, 1.18 multiplier,
batch count, and calibration sample size are inherited numerical choices, not
discovered mathematics and not a certified error probability. Do not adjust them.
Calibration/training/heldout sensor streams use separate fixed string namespaces.

Preserve reference limits: 1000 closure passes per call, 20 rounds, depth-2
conformance perturbations. Suffix length itself is not prefilled or capped at two.
Stopping with no observed counterexample is bounded empirical conformance, not
proof for every future action sequence. Hitting a limit or an exception is
INCOMPLETE/RUN_NOT_COMPLETED, not an environment or policy failure. GitHub runner
interruption has the same incomplete interpretation. No selective retry or
environment substitution after outcomes.

## Evaluation after learning is frozen

After constructing readout prototypes from learned representatives and suffixes,
freeze the model. Only then enumerate the hidden finite arena for an evaluator-side
observation-preserving congruence quotient, preserving clean visible outputs and
every action. Do not use goal labels for this quotient. Record learned count,
true quotient count, represented classes, over-splits, and all transition errors.

Generate exactly 200 independent random-action episodes of length 25 per condition,
for 5000 evaluated prefixes, RNG seed=world seed+1000000. The finite evaluation
episode length is not a learned-state history window. Same action corpus across
camera conditions. Use independent heldout sensor noise. Label checks happen after
predictions and never update the model.

Compare full learned-E readout to empty-suffix-only readout on the same learned
representatives and observations. This is a readout ablation, NOT an equal-cost
comparison of two independent acquisition algorithms. A unique prototype within
the same calibrated threshold is a prediction. No candidate/multiple candidates
is unresolved, reported explicitly; a nearest-prototype score is diagnostic only.
Record all cases, unique-candidate accuracy, unresolved count, nearest diagnostic,
same-current-observation/different-future cases, and coverage of evaluator classes.

All results are reported, not filtered by learning or recognition performance.
4000 previous transition tests and these 5000-prefix tests have different denominators.
No planning-performance or universal sufficiency claim from this experiment.

## Execution, evidence, and scope

Run unit tests before real learning. Run four conditions on GitHub Actions with
max-parallel=2 and BLAS/OMP/MKL one thread. Python 3.12.10, NumPy 1.26.4,
Pillow 11.3.0, pytest 8.4.1, psutil 7.0.0. Preserve sources, hashes, config,
calibration, every queried action word, raw RGB exposures (streaming gzip),
summary statistics, suffix witnesses, models, external audits, and resources.
Each query's shape and index define its byte offset in its raw.rgb.gz stream.
Display images are labelled batch means, not individual exposure screenshots.

No new game, no handcrafted distinguishing word, no solution oracle in learning,
no old exact-RGB discovery. No changes to previous production-loop records/code.
Stop after these four fixed development conditions and report the actual results.
