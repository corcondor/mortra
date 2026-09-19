# Asking for a shadow and getting a construction

Repository: `corcondor/mortra`. Branch: `codex/operation-contracts-20260918`.
Base: `e2d1b46`. The fragment is unchanged: the same seven primitives, the same
ten predicates. The drawing is unchanged. The search is unchanged. What is new is
the translation of a wanted shadow into relations, and the handling of a
requirement that names more than one unknown point.

## 1. The one translation

An end of a shadow on a screen is where the boundary ray through the
corresponding end of the occluder meets that screen. So, with `P` the unknown:

```
X is an end of the shadow  <->  coll(k1, k2, P)      P is on the line it may sit on
                            and coll(L, X, P)        P is on the ray that carries X
                            and P strictly between L and X
```

The first two are goals the fragment states. The third is an inequality, which
this fragment cannot state and whose certifier decides only whether a polynomial
is zero — so it is kept apart, decided on the instance, and reported as such.
Every task in this experiment uses that one rule; nothing is written per task.

## 2. Where the existing search stopped

The wanted shadow names two unknown points. The solver's task is a set of given
points and goals over them and **one** unknown, so a goal set naming both cannot
be written in it at all. Collapsing them — asking one point to carry both ends —
is the faithful way to hand it over anyway, and it fails:

| run | solved | stop | plan expansions | checks | applications | seconds |
|---|---|---|---:|---:|---:|---:|
| directed search | no | application budget | 230 | 11,525 | 40 | 5 |
| with backward substitution | no | application budget | 230 | 11,525 | 332 | 317 |

The backward path builds 400 specifications and decides 194,499 of them against
candidate points, and still fails, correctly: no single point is on two different
rays from the light.

**The connection added** is `solve_system`. Each unknown is posed to the same
search as its own task over the given points and everything solved so far, so the
unknowns share the light and the placement line, and a later unknown may depend
on an earlier one. With it, each unknown of the development requirement is found
in **one application and one search state**.

## 3. The development requirement, end to end

Given a light at (0, 3/2), a placement line `x = 1`, a screen `x = 3` and a
wanted interval from (3, 3/5) to (3, 12/5), the search returns:

```
params: k1 k2 l s t w1 w2
  s1 = intersection_ll(k1, k2, l, s)     -> A = (1, 6/5)
  s2 = intersection_ll(k1, k2, l, t)     -> B = (1, 9/5)
```

re-runs from the inputs alone, and is checked by recomputing the shadow the
configuration casts: its ends on the screen are exactly (3, 3/5) and (3, 12/5).
The order conditions hold on the instance.

Three pictures, all from the existing dot renderer, all the same black disk:
`dev-1-wanted` (the given lines dotted, the wanted interval solid on the screen),
`dev-2-found` (the segment the search placed, solid on the placement line),
`dev-3-cast` (the shadow recomputed from that segment, dense inside and sparse
outside). The renderer is given point lists and nothing else.

## 4. Changing the request

| requirement | unknowns | result | steps |
|---|---|---|---:|
| the placement line is not parallel to the screen | A, B | solved and verified | 2 |
| **control**: the placement line is only met beyond the screen | A, B | refused — the order condition failed at B | — |
| the occluder is known, the light is wanted | L | solved and verified, recovering (0, 3/2) | 1 |
| the interval is given by its near end and its middle | A, T, B | solved and verified | 3 |

The control matters: its relations *are* satisfiable — a point of that line does
lie on the ray — and the search finds one. What fails is the order, because the
occluder would stand behind the screen. Without that condition the answer would
have been accepted.

The last one is the case where a later unknown depends on an earlier one: the far
end `T` is constructed as the reflection of the near end in the middle, and `B`
is then placed from `T`.

## 5. What the acquisition gate kept, and the comparison

| from | unknown | outcome |
|---|---|---|
| development | A | kept as operation 281: `intersection_ll(p0,p1,p2,p3)`, certified `coll(p0,p1,v)` and `coll(p2,p3,v)`, nothing instance-only |
| development | B | refused: an identical program is already indexed |
| training (near end and middle) | A, T, B | refused: an identical program is already indexed |

Two conditions, the requirements and the budget fixed before either ran, and
nothing acquired from the evaluation requirements themselves:

| | solved | plan expansions | applications | checks | library queries | seconds |
|---|---:|---:|---:|---:|---:|---:|
| A: enumerated vocabulary only | 4/4 | 10 | 10 | 202 | 1,200 | 0.27 |
| B: with what was acquired | 4/4 | 10 | 10 | 202 | 1,200 | 0.27 |

Plus 0.69 s of acquisition charged to B.

**There is no benefit.** B consulted the acquired operation during the search on
all four requirements — that is the retrieval path calling its certificate, not a
fold applied to a finished answer — and its answers contain it, and not one
number moved.

The reason is structural, and it is the finding of this experiment: **the
decomposition that made the problem solvable is what made every acquisition
trivial.** Each unknown, once the others are given, is one primitive away, and
the enumerated vocabulary already holds every one-step program. The thing worth
reusing — place a segment whose shadow is this interval — returns *two* points,
and an operation in this library returns one, so it cannot be stored as a single
operation at all. Inlining the chain does not rescue it either: the guarantee that
would make it worth retrieving mentions the intermediate point the composite
itself constructs, and a declared guarantee may only mention the parameters of
the operation it belongs to.

## 6. What is not claimed

* No artistic technique was discovered, and nothing here is image understanding.
* The order conditions are decided on the instance, not certified; this fragment
  has no procedure that could decide an inequality.
* The translation from a wanted shadow to relations is written by a person. What
  the system does is search for the points, return a program, and check it.
* One benefit was looked for and not found, and that is reported as it stands.

## 7. Running it

```
python scripts/run_shadow_design.py --output reports/shadow-design --depth 5
python -m pytest tests/test_geometry_shadow_design.py tests/test_geometry_ink.py
```
