# Posing its own geometry tasks, solving them, keeping what generalises, and using it again

Repository: `corcondor/mortra`. Branch: `codex/operation-contracts-20260918`.
Base: `749cc9f`.
Status: the cycle implemented and run. The numbers in section 5 are from the run
recorded in the commit that adds this document.

## 1. What is being tested

Whether MORTRA's own experience changes what it can do on tasks it has not seen:
either it solves more of them, or it solves them for less, while every answer
stays exactly checked.

The cycle is:

```
pose → screen → solve → certify → register → choose what to study next → measure
```

Every part of it is an existing component. What is added is the cycle itself and
its bookkeeping.

| step | component | file |
|---|---|---|
| pose | compose primitives, decide relations exactly, hide the construction | `geometry_self_posing.py` (new) |
| screen | the current solver at a small budget decides how hard a task is | `geometry_self_improvement.screen` (new) |
| solve | the relational solver, unchanged | `geometry_relational_search.py` |
| certify | exact certification over QQ(inputs) | `geometry_relational_edit.define`, `geometry_relational_library.certify_entry` |
| register | the same retrieval interface the enumerated programs use | `geometry_acquired_library.py` (new) |
| policy | budgets, family order, library breadth — as data | the solver's `config` |

The one change inside the solver is three lines: a `family_order` in the
configuration reorders the families that are offered. With no such key the
behaviour is what it was, and the existing suites still pass.

## 2. How a task is posed

A task is not written as a sentence and then checked. It is produced in this
order, which is what makes the answer exist by construction:

1. a configuration of four points with no repetition and no collinear triple;
2. a construction: primitive operations composed and executed exactly at rational
   coordinates, refusing any step whose applicability fails;
3. the relations that hold of the constructed point are decided exactly by
   `atom_holds`, which carries the prerequisites a predicate needs, and relations
   that hold for every configuration are discarded;
4. the construction, the intermediate points and the coordinates of the answer
   are hidden; the published task is the input configuration and the goal
   relations over the unknown `u`;
5. the solver receives the published part only.

A posed task is refused unless: no input point already satisfies the goals, some
pair of the goals leaves finitely many candidates (`rational_solutions`), and the
constructed point is among the candidates that satisfy every goal. The solver is
free to find a different construction; only the goals are checked.

Three simultaneous conditions on one unknown point are used, because with two a
single primitive usually satisfies both and nothing has to be composed.

## 3. What is acquired, and what is refused

From a solved task: the solution term becomes a program over at most three
slots; the task's goals become the operation's declared guarantees; each
guarantee is decided by `certify_entry` over the rational function field of the
inputs. A guarantee that held only at the configuration where the task was posed
is dropped and recorded as such, not kept. What survives is registered with its
certificates, and becomes retrievable for later tasks by the same path the
enumerated programs use.

An acquired operation is spliced into a plan as its own primitive steps, and
every step is charged. Reusing an operation is not free.

## 4. What crosses a task boundary

Only two things: the library of certified operations, and the policy. Every task
gets a fresh solver, so no coordinates, no solution and no executed-step cache
travels. The run records the module digests before and after, so that the code
is known to be fixed while the library and the policy change.

## 5. The run

See `reports/geometry-self-improvement/result.json` (produced by
`scripts/run_geometry_self_improvement.py`).

_This section is completed from the run: pools and their difficulty mixture,
what each stage acquired, the policy each stage chose, the three-way comparison
on the final tasks, the three memorisation probes, and the dominant bottleneck._

## 6. What this does not claim

* The primitives, the predicates, the posing rules, the screening thresholds and
  the shape of the policy candidates are supplied by a person. What the system
  does is pose tasks, solve them, decide which guarantees generalise, keep them,
  choose a policy from what was recorded, and use both on tasks it has not seen.
* The final tasks were posed and screened before any learning, and were never
  used to choose a policy — but they were screened with the starting solver, so
  the mixture of difficulties is defined relative to that state.
* A posed task is refused unless a rational non-input solution exists. Nothing
  here decides real solvability.
* The geometry fragment has seven primitives and no line or circle carrier;
  circle conditions are expressed as `cyclic` and `cong`, angle conditions as
  `eqangle`.
* No preregistered evaluation is affected.
