# Posing its own geometry tasks, solving them, keeping what generalises, and using it again

Repository: `corcondor/mortra`. Branch: `codex/operation-contracts-20260918`.
Status: the cycle implemented and run three times, each run answering a question
the previous one raised.

## 1. What is being tested

Whether MORTRA's own experience changes what it can do on tasks it has not seen:
either it solves more of them, or it solves them for less, while every answer
stays exactly checked.

```
pose → screen → solve → certify → register → choose what to study next → measure
```

Every reasoning part already existed. What is new is the cycle, its bookkeeping,
and — after the first two runs — a generator that can pose a task the system
cannot already answer.

| step | component | file |
|---|---|---|
| pose | compose primitives, decide relations exactly, hide the construction | `geometry_self_posing.py` |
| screen | the current solver at a small budget decides how hard a task is | `geometry_self_improvement.screen` |
| solve | the relational solver, unchanged | `geometry_relational_search.py` |
| certify | exact certification over QQ(inputs) | `geometry_relational_edit.define`, `geometry_relational_library.certify_entry` |
| register | the retrieval interface the enumerated programs already use | `geometry_acquired_library.py` |
| policy | budgets, family order, library breadth — as data | the solver's `config` |

The only change inside the solver is three lines: a `family_order` in the
configuration reorders the families that are offered. Without that key the
behaviour is unchanged and the existing suites pass.

## 2. How a task is posed

1. a configuration of points with no repetition and no collinear triple;
2. a construction: primitives composed and executed exactly at rational
   coordinates, refusing any step whose applicability fails;
3. the relations that hold of the constructed point are decided exactly by
   `atom_holds`, with the prerequisites each predicate needs; relations true of
   every configuration are discarded;
4. the construction, the intermediate points and the answer are hidden; the
   published task is the configuration and the goal relations over the unknown;
5. the solver receives the published part only.

A task is refused unless no input point already satisfies the goals, some pair of
the goals leaves finitely many candidates, and the constructed point is among the
candidates satisfying all of them. The solver may answer with a different
construction; only the goals are checked.

**A ladder** poses one construction twice: the base task asks for the point the
first steps make, the top task for the point the whole construction makes, and
each extension step consumes the point the previous step produced. An operation
acquired from the base is then exactly the block the top needs — whether the
search finds and uses it is the question, not an assumption.

## 3. What is acquired, and what is refused

The solution term becomes a program over at most three slots; the task's goals
become declared guarantees; each is decided by `certify_entry` over the rational
function field. A guarantee that held only at the configuration where the task
was posed is dropped and recorded as such. What survives is registered with its
certificates and becomes retrievable like any enumerated program. An acquired
operation is spliced into a plan as its own primitive steps, and every step is
charged: reuse is not free.

## 4. What crosses a task boundary

The library and the policy. Nothing else: every task gets a fresh solver, so no
coordinates, no solution and no executed-step cache travels. The runs record the
module digests before and after and report `sources_unchanged`.

## 5. The three runs

**Run 1 — starting from an empty library.** 22 unseen tasks: 18 solved before
learning, 20 after, with primitive executions falling from 78 to 48 and checks
from 5,436 to 4,976. Three operations were acquired, all in the first stage; the
second stage acquired nothing because every solution repeated a program already
held. The learned policy changed nothing. The memorisation probes were all
answered, with the acquired operations used in 11 of 12.

**Run 2 — starting from the vocabulary the repository already enumerates** (281
programs to depth two, built in about a minute). 12 of 12 unseen tasks were
solved *before* learning; nothing was acquired; nothing could improve.

That contrast is the finding, and it is about the generator, not the learner: the
tasks being posed were inside the vocabulary the system already had.

**Run 3 — a task family the starting vocabulary cannot answer directly.** Three
changes, each a statement about the task: five input points instead of four;
goals that must mention at least four distinct named points, which is more than
the three slots retrieval can bind, so the library cannot answer the goal
directly and the search has to compose; and goals that must mix predicates, with
circle and angle conditions preferred. Screening against the full starting
vocabulary then produces hard tasks — for example a point required to be
concyclic with three others while meeting a length and a perpendicularity
condition, which the starting system does not solve within its budget.

An example of a posed pair, as the solver receives it and as the generator knows
it:

```
base  点 a(-6,1), b(-2,-8), c(-6,-6), d(-3,1) が与えられている。
      次をすべて満たす点 u を作図せよ: 線分da と 線分du の長さが等しい、
      かつ 直線au と 直線ad は平行である、かつ a, u, d は同一直線上にある。
      hidden: midpoint(c,a) -> mirror(a,d);  answer (0, 1);  candidates 1

top   同じ配置で: 直線da と 直線ub は直交する、かつ 線分bd と 線分ud の
      長さが等しい、かつ 直線ac と 直線bu は平行である。
      hidden: midpoint(c,a) -> mirror(a,d) -> reflect(b,d,·);  answer (-2, 10)
```

## 6. What this does not claim

* The primitives, the predicates, the posing rules, the ladder idea, the
  screening thresholds and the shape of the policy candidates are supplied by a
  person. What the system does is pose, solve, decide which guarantees
  generalise, keep them, choose a policy from what it recorded, and use both on
  tasks it has not seen.
* The transfer set shares its ladders with the training set by design; the
  generalisation set does not, and they are reported apart.
* A task is refused unless a rational non-input solution exists. Nothing here
  decides real solvability.
* The geometry fragment has seven primitives and no line or circle carrier:
  circle conditions are `cyclic` and `cong`, angle conditions are `eqangle`.
* No preregistered evaluation is affected.

## 7. Run 4: the retrieval limit, and the loop closing

Run 3 solved its training tasks but acquired nothing. The refusals named the
reason exactly: *"4 distinct points at the interface, more than the retrieval
slots"*. Retrieval bound at most three named points, so precisely the tasks that
were made hard by mentioning four or five points produced operations that could
not be stored. The property that made a task worth learning from also made what
was learned unstorable.

The limit is now a configuration value (`library_slots`), left at three for the
enumerated index that was written over three, and set to five for a library that
holds operations over more. Re-running run 3's tasks — the same ladders, reused
rather than re-posed — with that one change:

| condition | set | solved | search states | applications | checks | acquired operations used |
|---|---|---:|---:|---:|---:|---:|
| A start | transfer | 6/6 | 41 | 11 | 909 | 0 |
| B library | transfer | 6/6 | 41 | 11 | 909 | 4 |
| C library and policy | transfer | 6/6 | **35** | 11 | **683** | 4 |
| A start | generalisation | 3/4 | 87 | 22 | 858 | 0 |
| B library | generalisation | 3/4 | 87 | 22 | 858 | 2 |
| C library and policy | generalisation | 3/4 | 87 | 22 | **705** | 2 |

Three operations were acquired from five solved base tasks: one of one step, one
of two, one of three, with guarantees over four slots — none of which could have
been kept before. They are used on tasks whose ladders were never trained on as
well as on the ones that were.

What improved: the cost. Checks fall by a quarter on the transfer set and by a
sixth on the generalisation set, and the route is found with fewer search states.
What did not: the set of solved tasks. The one hard generalisation task — a point
required to be concyclic with three others while meeting a length and a
perpendicularity condition — is unsolved in every condition, and the acquired
operations do not reach it.

The bottleneck that remains is the one run 1 already pointed at, now with the
retrieval limit removed from in front of it: a composite construction is reachable
only when the intermediate hole carries a spec, so the search cannot assemble an
arbitrary two-step construction by itself, and an operation can only be acquired
from a task that was solved.
