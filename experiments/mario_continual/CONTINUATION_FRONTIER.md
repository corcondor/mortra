# Mario continual exploration: continuation frontier

## Observed failure mode of the previous controller

The previous T4 run was not failing because exploration had stopped.  It was
continuing to add predictive structure while repeatedly failing to clear the
level.  The important mismatch was between the unit of exploration and the
unit of useful progress.

The old controller used `VirtualFrontierPolicy(task_aware=False,
task_source=False)`.  Every untried pair `(predictive_state, primitive_action)`
became an equal virtual terminal source.  A local unknown action therefore had
the maximum immediate frontier value.  When predictive refinement creates new
states faster than these local pairs are consumed, frontier work grows instead
of shrinking.

A second issue amplified that effect: predictive state identity ignored the
exact reset-relative action history even though the Mario bridge is
deterministic and replay itself relies on that history.  Replaying the same
physical trajectory could therefore generate a new predictive split again.

A third issue changed control semantics: a learned tool was allowed to execute
when only its *first* primitive matched the policy action.  The remaining tool
actions were not required to match the planner's intended route.

## Invariant 1: exact-history context identity

For this experiment the reset level, action alphabet, action duration, and game
engine are deterministic.  Let

    E(h)

be the physical engine state reached by reset followed by primitive history
`h`.  Then the same `h` is a context witness:

    h_1 = h_2  =>  E(h_1) = E(h_2).

This does **not** claim that equal RGB observations imply equal states.  Distinct
histories with the same RGB observation may still split after a behavioural
counterexample.  It only prevents the *same* already-evidenced history from
creating another state on replay.

Implementation: `PredictiveRegistry.history_index[(observation, history)]`
reuses an existing predictive state before any new split is materialized.

## Invariant 2: continue at the deepest evidenced boundary

For predictive state `q`, define its frontier depth from the earliest real
history that evidenced its visual observation:

    d(q) = min |h|

over stored representatives of the same observation class.

Using observation-first depth prevents later predictive refinements of one
visual class from manufacturing artificial depth.

A frontier state is a non-terminal reachable state with at least one untried
primitive action.  From current state `s`, the continuation policy performs a
BFS over **known modal transitions only**.  Among reachable frontier states it
selects lexicographically

    max ( d(q), -dist(s,q), -q ).

It then follows the known shortest route to `q` and appends one untried action
at `q`.

Consequently a shallow local unknown action no longer automatically beats a
known route to a deeper boundary.  Unknown successors are never inspected or
predicted.

This converts the controller from local pair coverage toward depth-first
continual extension.  Along a useful chain of depth `D`, the intended work is
closer to repeated boundary probing plus route replay instead of attempting to
flatten the entire expanding product `state x primitive_action`.

## Invariant 3: tools may compress a plan, not replace it

A reusable tool with primitive expansion

    T = (a_0, ..., a_k)

may run only if its expansion is a prefix of the controller's current planned
primitive route

    P = (p_0, ..., p_m),

that is

    k <= m  and  T = P[:k+1].

The existing predictive-state guards and stepwise evidence checks remain in
force.  If a tool ceases to match evidence, execution stops as before.

This preserves control semantics while still allowing learned programs to
compress repeated navigation to a frontier.

## No Mario oracle signal

The continuation policy does not read Mario x-position, completion percentage,
level geometry, hidden engine state, reward, or an unknown action's successor.
It uses only:

- learned predictive states,
- observed action counts and modal transitions,
- terminal markers already observed from real play,
- representative action histories already stored as evidence,
- reusable tools learned from repeated resolved transitions.

## Experimental protocol

Use a fresh output directory for the first comparison.  Resuming the old
checkpoint would retain predictive states created under the old
history-agnostic identity rule and would confound the test.

Primary checks:

1. Replaying an identical action history does not increase predictive-state
   count.
2. The controller can bypass a shallow local frontier when a deeper reachable
   frontier exists.
3. Tool execution never departs from the planned route.
4. Real Mario action sequences cease the long exact-repeat regime seen in the
   prior run.
5. Compare predictive-state growth, known-pair growth, unique episode action
   sequences, terminal outcomes, and FIRST_CLEAR.

The only success criterion remains the real engine terminal status `WIN`.


## First continuation-depth experiment: rejected

The first implementation ranked frontiers primarily by representative action
history depth.  A real 100-episode Mario benchmark rejected that hypothesis:

- continuation-depth: 99/99 completed episodes were unique, longest identical
  consecutive action sequence = 1, but max engine completion audit was only
  0.058089703;
- prior virtual frontier: max engine completion audit was 0.108492985.

Therefore the exact-repeat pathology was fixed, but action-history depth was not
a valid proxy for game progress.  This negative result is retained rather than
reinterpreted.

## RGB displacement frontier

The next controller keeps the exact-history identity and plan-safe tool
invariants, but replaces survival/history depth as the primary frontier signal.

Each blocked RGB frame supplies a compact 64-bin horizontal edge-energy profile.
For two successive advancing frames, the Python port searches a bounded set of
horizontal translations and evaluates normalized overlap correlation.  A shift
is accepted only when both absolute similarity and the margin over the next-best
shift exceed fixed thresholds.  Same-frame SNAP recaptures never create motion.

For an exact action history h, the predictive memory integrates only reliable
visual translations:

    x_rgb(h a) = x_rgb(h) + delta_rgb

and otherwise carries the previous value forward.  This is a direct statistic
of observed RGB motion, not a learned latent representation.

A reachable frontier q is now ranked by

    (has_reliable_visual_motion,
     abs(x_rgb(q)),
     first_evidence_depth(q),
     -known_route_length(q),
     -q).

The absolute displacement makes the rule direction-agnostic.  On a bounded
side-scroller, one direction exhausts quickly while expansion of the other side
continues.  No RIGHT action, Mario position, level coordinate, completion
percentage, or goal location is encoded in the policy.

The engine completion percentage is logged only *after terminal* as
`completion_audit_only` so experiments can test whether the RGB statistic
actually correlates with real progress.  It is never passed to
`choose_primitive`, predictive updates, or frontier ranking.


## Bootstrap rule

The 8-episode RGB smoke produced no reliable global displacement witness.  The
depth-only controller had already been shown to underperform the prior virtual
frontier before such a witness appeared.  Therefore the final controller does
not alter exploration before it has evidence for a progress statistic.

If no reachable frontier carries reliable RGB-motion ancestry, the selected
primitive is exactly the action returned by the previous
`VirtualFrontierPolicy(task_aware=False, task_source=False)`.

Only after a reliable RGB displacement is observed does the controller switch
to displacement-prioritized continuation.  This makes the intervention
conservative:

    no visual progress evidence  =>  old exploration policy
    visual progress evidence     =>  known-route continuation toward the
                                     farthest visually displaced frontier

Learned tools are still allowed only as exact prefixes of the selected primitive
plan.
