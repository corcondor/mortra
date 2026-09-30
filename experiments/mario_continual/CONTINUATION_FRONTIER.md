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
