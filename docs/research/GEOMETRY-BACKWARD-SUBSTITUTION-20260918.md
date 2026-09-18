# Asking what the intermediate point would have to be

Repository: `corcondor/mortra`. Branch: `codex/operation-contracts-20260918`.
Base: `4914838`, whose acquisition, reuse and cost results are kept unchanged.
Status: implemented, measured, with the failure it was written for reproduced
first.

## 1. The failure, located

One task from the stored set, never solved:

> Given a(0, −8), b(−5, −8), c(5, 4), d(−9, −2), e(5, 2), construct a point u
> such that |eu| = |ab|, line ue is parallel to line ec, and u, e, c are
> collinear.

The search stops at once, and not for want of budget:

* the three goal atoms canonicalise to `coll(c,e,v)`, `cong(a,b,e,v)`,
  `para(c,e,e,v)`;
* `_matchings` returns **nothing for all seven primitives**: no primitive
  guarantees that conjunction about its output, so no last operation is offered;
* the guaranteed phase ends with its plans exhausted after one round; the
  partial phase drops one atom at a time, executes 128 plans and finds nothing;
* the run stops with `directed_phases_complete` after **16 applications**, and
  raising the budget to 340 or to 1000 changes nothing — the same 16
  applications, the same stop. There is nothing left to try, only more budget to
  leave unspent.

That is the shape of the gap: the search can only offer a last operation whose
own guarantee matches a goal, and it can only fill an argument hole that carries
a specification. A construction whose intermediate point is constrained only
through the final goal is unreachable.

## 2. What was added

`geometry_backsubstitution.py`. For a candidate last operation

```
u = F(w, q1, ..., qk)        w unknown, the other arguments bound to known points
```

the kernel already publishes F's output as a rational function of its inputs —
`primitive_contracts()[F]["witness"]`, the same witness the certification path
uses. Substituting it into the goal polynomials turns a condition on `u` into a
condition on `w`:

```
Goal(F(w, q...)) = 0        and        Defined(F(w, q...)) ≠ 0
```

This is one procedure for every primitive, every goal predicate and every
binding; nothing is written for a particular task. What it produces is kept as
polynomials, so a condition with no name in the geometric vocabulary is kept
rather than dropped, and:

* every goal becomes a conjunct about the **same** unknown, never a separate
  point per condition;
* denominators of the substituted expressions are kept as non-zero conditions
  rather than cancelled away;
* the primitive's guards become non-zero conditions on the unknown, and an
  applicability atom mentioning the unknown is carried with it;
* a substituted goal that reduces to a non-zero constant refuses the binding at
  once; one that reduces to zero is a goal that holds for every admissible `w`;
* a degree or term bound reached raises `BackwardBudget`, which the search
  records as an unfinished search — never as an impossible goal.

No polynomial system is solved. A point is decided against a specification by
exact substitution, which is what the rest of the search already does.

## 3. How it runs inside the search

A phase of its own, off unless `backward_substitution` is set, entered only
after the directed phases have finished or run out, with its own application
allowance (`backward_applications`, default 300) and a small reserve so that
the operation it finds can still be executed.

Specifications are produced one at a time, cheapest operation first, and every
point already known is decided against each as soon as it exists — so the
specification drives the search for a point, not the other way round. Only then
are short constructions built, one at a time, each decided as it appears. Steps
go through the same execution cache as the rest of the search, so nothing is
recomputed within a task, and a point that meets the goals outright while being
built is recorded as such (`backward_forward_construction`) rather than
credited to the specification.

Acceptance is unchanged: primitive re-execution from the inputs and the exact
check of every original goal.

## 4. The development task, end to end

The specification the search generated, for `midpoint` with its second argument
bound to `e`:

```
wx² − 10·wx + wy² − 4·wy − 71 = 0        from  |eu| = |ab|
5 − wx = 0                               from  ue ∥ ec
5 − wx = 0                               from  u, e, c collinear
```

The point it found for that specification: `foot(a, c, e)` = (5, −8) — the foot
of the perpendicular from a to the line ce. Then the last operation:

```
u = midpoint(foot(a, c, e), e) = (5, −3)
```

Checked the way every solution is checked: re-executed from the input points
(residuals 0) and all three goals decided exactly. The generator's own hidden
construction was `mirror(d,b) → mirror(b,a) → midpoint(e, ·)`, also giving
(5, −3); the search found a different construction, which the protocol allows.

Cost: 17 applications, 0.13 s in the backward phase, 5 specifications built, 44
expression terms.

## 5. What was acquired from it

Through the existing path — `define`, exact certification over QQ(inputs),
`register`:

```
body:  foot(p1, p2, p0) → midpoint(p0, ·)          four slots
kept:  para(v, p0, p0, p2),  coll(v, p0, p2)       certified for every configuration
refused: cong(p0, v, p1, p3)                        held only at this configuration
```

The length condition was the reason the task was hard and it is exactly the one
that does not generalise; it is recorded as instance-only instead of being kept
as a guarantee. In a sample of 40 stored tasks the new operation was retrieved
for one — the task it came from. No cross-task reuse of this particular
operation was observed.

## 6. The comparison

A task is *budget-immune* when the search stops with its plans exhausted while
its application budget is unspent: raising the budget cannot help it. Of the
**111 tasks stored by earlier runs**, 105 are solved at a budget of 600 and
**6 are budget-immune**. With the backward path all 6 are solved, 5 of them
through a generated specification.

On the 5 budget-immune tasks that are not the development task:

| condition | solved | through a specification | applications | search states | checks | seconds |
|---|---:|---:|---:|---:|---:|---:|
| C0 learned library and policy | 1/5 | 0 | 45 | 1029 | 6947 | 263 |
| C0 at C1's total budget | 2/5 | 0 | 47 | 525 | 3800 | 33 |
| C1 backward path on | **3/5** | 1 | 340 | 779 | 6491 | 343 |
| C2 after learning with it on | **3/5** | 2 | **31** | 1022 | 6817 | 189 |

And on the development task itself: C0 fails at 40, at 340 and at 1000
applications; C1 solves it through a specification.

C0 against C1 is the mechanism: two more tasks, and the one no budget reaches.
C1 against C2 is experience: the same three tasks answered with 31 applications
instead of 340, and two of them through a specification rather than one.

Peak memory stayed between 5 and 11 MB per task; the whole comparison ran in one
process.

## 7. What this does not claim

* The substitution is general, but the *search for a point* that satisfies a
  specification is still generate-and-test over short constructions with a
  budget. Two of the five unseen budget-immune tasks remain unsolved.
* Only one argument of the last operation is left unknown. Constructions needing
  two unknown points at once are not reached, and the shared constraint between
  them is not yet expressed.
* A bound reached is reported as an unfinished search; nothing here decides that
  a goal is unreachable.
* The generator, the audit path and the acquisition gate are unchanged from
  `4914838`; the results recorded there stand.
* No preregistered evaluation is affected.
