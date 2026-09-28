# MORTRA Long-Run Task-Blind Exploration

This is a new development experiment, separate from the interrupted noisy-RGB
family comparison. It is not a fresh confirmatory claim or an externally
timestamped preregistration. Freeze this protocol and implementation before
large-run outcomes. No external LLM, NN, source predictor or oracle is used.

## Acting Learner

The primary selector is the existing `TaskBlindSelector('virtual_frontier')`.
The unchanged `structural` and `frontier_t0` selectors are controls. All three
use the canonical StructuralLearner, their original visit bookkeeping, q=0.90,
and existing tie-breaking. SingletonMemory rejects progress/acceptance queries.
Only actually executed action outcomes enter the learner.

The harness supplies random opaque labels for fully observed states. This is
an explicit idealized observation interface. It does not solve noisy-RGB state
identification, infer state identity from pixels, or grant oracle paths. Raw
state, genome and visualization remain harness-side. The learner is not passed
an environment object, game rules, goals, tasks, reward or future outcomes.

## Registered Scale

- 32 finite-program worlds: seeds 98028000..98028031.
- 8 unchanged finite 3D arenas: seeds 98028100..98028107.
- Program worlds: canonical generator, then 32 seeded uniformly sampled edits
  from its existing operator set, without outcome-based selection. Invalid
  syntax/no-op edits are logged. Existing board edits then expand to 32x32.
  This fixed scale choice is supplied by the experiment, not learned by MORTRA.
- The 3D control remains 7x7x3 with five actions. No mining, block placement,
  crafting or Minecraft engine is present. Longer exploration is not evidence
  for these missing capabilities.
- Save all 40 input specifications before calling any compared selector.
- No solvability filtering, world replacement, task generation or oracle calls.
- Continuous trajectory per world/selector, from empty model. Checkpoints:
  2048, 8192, 32768, 131072 actual environment operations.
- Maximum 15,728,640 operations across 40 worlds and three selectors; 480
  registered checkpoints. This is a ceiling, not completed work.
- No resets or rule changes during a world's exploration. Irrecoverable traps
  and exhaustion of accessible novelty remain observable outcomes, not reasons
  to substitute a world or change the selector.

These seeds were not found by a local source/report search before outcomes.
This does not prove they were unused in every external experiment. Report the
run as development work, not certified fresh holdout evidence.

## Persistence and Resource Limits

Run on Colab, serially, with BLAS/OMP/MKL threads fixed to one. Save to a new
Drive run directory. Every action records its opaque observations, private raw
state, selected action, field diagnostics, timing and sampled RSS. Journals
have per-row hashes and a consecutive-step hash chain. Full ordered learner
snapshots and observation-label RNG state are saved every 512 steps and at
registered checkpoints. Existing records are not overwritten.

A committed action journal can recover a not-yet-checkpointed model without
executing that action in the environment again. Recovery recomputes the
original selector and asserts that its action matches the record. Truncated
or corrupt journals cause a visible infrastructure stop, never silent skipping
or a policy failure. Source/numerical-library changes block silent continuation.

Six hours per notebook invocation and 1 GiB minimum available RAM are resource
guards, not policy-dependent stopping rules. Re-running the same notebook
continues committed work. No completed unit is selectively restarted. A forced
Colab disconnect may prevent the final interruption marker; retained journals
remain the recovery source. No background keep-alive or billing change is used.

CPU/RSS are diagnostics on one shared worker, not a rigorous speed benchmark.
Policy-plus-transition CPU excludes persistence and recovery; invocation wall
time and interruptions are reported separately. RSS is sampled, not a claim
of exact peak memory. GPU is not requested: the existing solver is CPU-based.

## Validation and Outputs

Before the cloud run: unchanged virtual-frontier tests plus new infrastructure
tests. On all three methods, verify prefix actions, observations, every ordered
learner dictionary and resumed results against the canonical training function.
Simulate a crash after a committed observation; recovery must use zero new
environment steps. Test corruption, source/run mismatch and resource pauses.

Store registration, exact source SHA and source hashes, versions, genomes,
generation edit logs, action journals, ordered snapshots, resource logs,
attempt records, tests/logs and per-world checkpoint tables. 3D checkpoint
images render the actual recorded state and are labelled inspection images;
they are not RGB inputs to this learner.

Report learned state counts and tried state-action counts, and paired method
differences at matching budgets. Do not call these true-state coverage or game
completion rates. Missing checkpoints keep the whole run INCOMPLETE, with
available denominators. No design ability, Minecraft-level competence, visual
invariance, source-value learning or cross-world transfer claim follows from
this experiment. No outcome-dependent tuning or automatic next experiment.
