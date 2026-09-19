# Drawing programs the search builds

Repository: `corcondor/mortra`. Branch: `codex/operation-contracts-20260918`.
Base: `5cecbc1`, with `e2d1b46` as the drawing connection it stands on.

The geometry does not move. Seven primitives — `circle`, `foot`,
`intersection_ll`, `midpoint`, `mirror`, `orthocenter`, `reflect` — and ten
predicates — `coll`, `cong`, `cyclic`, `diff`, `eqangle`, `midp`, `ncoll`,
`npara`, `para`, `perp` — read from the source and recorded with every run. What
changed is that the *assembly* stopped being Python.

## 1. The execution language, and what it is not

```
let   x = op(args...)     a construction step: a primitive, an acquired
                          operation, or a macro
emit  x                   keep a point for the drawing
call  rule(args...)       a recursive call, one depth lower
keep  x where relation    keep a point only when an existing relation holds
```

These are additions to the **execution language**, not to the geometry: no
predicate, no primitive, no theorem. They are counted in the cost of any search
that uses them. Recursion is bounded by a depth the caller supplies and every
call lowers, so every program terminates — and nothing here is a claim about
unbounded repetition. A program is a value:

```json
{"name": "r", "params": [...], "body": [...], "emit": [...], "calls": [...]}
```

It is kept as a rule, never expanded into thousands of stored instructions; the
points exist when it is run.

## 2. Where the existing search could not be used, and what was added

A point-level hole asks: *a construction whose output is this point*. That is an
equality, and an equality goal matches no primitive's guarantee — the
contract-directed search offers **no candidate at all** (measured: zero
applications), and backward substitution does not rescue it either (162
applications, no answer).

So one thing was added: a bounded **bottom-up enumeration** over the operators,
cheapest arity first, with a node budget. An acquired operation or a macro takes
part in it as an operator like any other, which is the only way holding
something can make a later search shorter. The recursion is then closed by
trying the argument tuples the body's own names allow, running each combination
at the depth the requirement will be run at, and keeping one that produces every
wanted point still missing. The search stops at the first body that closes, so
the node count it reports is what it cost to succeed.

Three mistakes were found and fixed while building it, each of which had made the
search look less capable than it is: the enumeration discarded, by value, the
construction a recursion could be built on; call tuples were judged one at a time
although a target can be produced only by a call made inside another call; and
points were compared across types that are equal but do not hash alike.

## 3. What the search built

The requirement is a few points that must be among those emitted. Nothing else —
no technique, no order of operations, no hint of what to share.

**Seven points of a curve.** From `p0=(0,0)`, `p1=(4,6)`, `p2=(8,0)` and the
seven points at `t = k/8`, the search returned:

```
r(p0, p1, p2):
    v1 = midpoint(p0, p1)
    v2 = midpoint(p1, p2)
    v3 = midpoint(v1, v2)
    emit v3
    call r(p0, v1, v3)
    call r(p2, v2, v3)
```

That is de Casteljau subdivision, and it was not written here: the operators,
their arguments, the emitted name and what each call passes were all chosen by
the search, in **89 nodes and half a second**. Every wanted point is checked
exactly.

**Three points of a curve.** The same inputs with only three wanted points admit
a shorter program, and the search returns it — `midpoint(p0,p2)` then
`midpoint(p1, ·)`, two steps instead of three. That is correct behaviour: a
weaker specification does not pin the rule, and matching a hidden construction is
not the success condition. It is the extra four points that pin it.

## 4. Changing the inputs, not the source

| intervention | result |
|---|---|
| depth 1 to 6 | 1, 3, 7, 15, 31, 63 points — the recursion, unchanged program |
| input points moved | runs, 31 points at depth 5, a different arc |
| resolution doubled | the same points, the same radius in paper units |

The images are `depth-2`, `depth-3`, `depth-5`, `inputs-moved` and
`resolution-doubled`, all drawn by the renderer that already existed, all black
disks of one radius, each checked to contain nothing else.

What is *not* claimed: moving the inputs preserves what the program's own
contract preserves, and nothing more. The figure changes with the inputs, which
is the point.

## 5. Reuse, measured

The acquisition gate was offered both synthesised bodies and kept neither:
**nothing they guarantee certified**. That is the same wall as before — the
relation that would make such a body worth retrieving mentions the intermediate
point the body itself constructs, and a declared guarantee may only mention the
operation's own parameters.

So the reuse that was measured is of a different kind, and is labelled as such: a
**macro** — a body kept so a later search reaches the same point in one step
instead of three. A macro carries no guarantee, is never offered to the
relational retrieval, and is reported apart from anything certified.

| | solved | nodes | primitive applications | bodies tried | seconds |
|---|---:|---:|---:|---:|---:|
| A: the core only | 3/3 | 214 | 3,894 | 5 | 1.25 |
| B: with two macros | 3/3 | 227 | 6,277 | 13 | 0.76 |

and per requirement:

| requirement | A nodes | B nodes | B used |
|---|---:|---:|---|
| three points of a curve | 54 | **25** | `macro:2752458dbddc` |
| seven points of a curve | 89 | 110 | — |
| a curve on a different triangle (unseen) | 71 | 92 | — |

Honestly: the macro learned on the harder requirement halves the work on the
easier one — 54 nodes to 25, 0.40 s to 0.10 s — and costs nodes on the two
requirements where it does not apply, because every extra operator is another
thing to enumerate. Over the three, the node count is slightly worse and the
wall time slightly better, and 2.4 s of acquisition is charged to B on top. The
unseen requirement was already reachable without any macro, so reuse could not
improve reachability there, only cost — and it did not.

## 6. What is not claimed

* Nothing here is an artistic technique the system discovered, and nothing here
  is image understanding.
* `let`, `emit`, `call` and `keep` are new, in the execution language. They are
  recorded as an addition and counted, not hidden.
* A bounded run proves nothing about unbounded recursion. The depth is given, and
  every count reported is at a stated depth.
* Macros are search abstractions with no geometric content. Nothing was certified
  in this experiment.
* A plane, rational coordinates, and the seven primitives. No three dimensions,
  no irrational constructions.

## 7. Running it

```
python scripts/run_drawing_synthesis.py --output reports/drawing-synthesis
python -m pytest tests/test_geometry_drawing_program.py
```
