# Ten directives, one search, and what a round leaves for the next

Repository: `corcondor/mortra`. Branch: `codex/operation-contracts-20260918`.
Base: `6e19afd`. The geometric core is unchanged: seven primitives, ten
predicates, read from the source and recorded with every run.

## 1. What the existing connection already had, and what it did not

Two things were checked before anything was built.

**Where a formal requirement can be handed over.** `check()` already decided four
kinds of condition — points that must appear, a count, a relation every emitted
point satisfies, a region every emitted point lies in. But `synthesise_rule()`
searched on one of them only: a list of target points. The checking language was
richer than the search.

**What a later search consults.** For the relational solver there is an update
path — `propose_policies`, `choose_policy`, the acquired library. For the drawing
search there was **nothing**: macros were rebuilt inside the script on every run
and nothing survived it. Saving pictures and logs is not that.

So two connections were added, and only two:

* `synthesise_for(requirement, ...)` — the search is driven by whatever the
  requirement says a single point must satisfy, with the target-point case as a
  fast path. A requirement that names no point now drives a search.
* `geometry_drawing_experience` — a record of what a round leaves: the bodies
  (macros), the whole programs including their recursion (rules), and how often
  each operator has been part of something that worked (the order the
  enumeration sorts by). The search reads all three back.

## 2. The ten requirements

One search, no solver per picture. What differs is the inputs, the shared
variables, what repeats and which conditions must hold.

| task | what the requirement says |
|---|---|
| curve-seven | seven named points of a quadratic |
| curve-three | three named points — deliberately weaker |
| lattice-row | three lattice points, all collinear, six distinct, none a given point |
| lattice-two-directions | the whole 3×3 patch, eight distinct, none a given point |
| orbit-quarter-turn | three points of a four-fold orbit, four distinct |
| midpoint-chain | three points of a halving chain |
| all-on-a-line | five distinct points on the line of the first two, none given |
| inside-a-disk | five distinct points inside a disk, none given |
| curve-inside-a-disk | two named points, all points inside a disk |
| count-eight | seven distinct collinear points, none given |

The directive is Japanese prose written by a person and the formal requirement
beside it was written by a person too. That is recorded with every task: nothing
here reads natural language.

## 3. Three things the first attempts caught, all of them mine

The first round "solved" ten of ten, and three of those answers drew nothing:
`all-on-a-line` emitted `p0`, `inside-a-disk` emitted the centre,
`curve-inside-a-disk` emitted a given point. The requirements permitted it. Two
general conditions now refuse it — `exclude_inputs` (no emitted point may be one
of the given points) and `distinct_count` — and they are conditions of the
requirement, not of one task.

The second round exposed the same thing at the level of a figure: the lattice
task asked for three lattice points and got three points scattered anywhere. A
lattice is not "contains these three points"; it is the orbit of a point under
two translations, and **the requirement language cannot say that**. It can name
points and it can state a relation every point satisfies. Listing the whole patch
made the task honest and the answer became a lattice.

The third was a methodological error: the scoring, fixed in advance, demanded
eight distinct points while the requirement demanded five. The search was being
graded on something it had never been told. They are the same number now.

## 4. What one round leaves, and what the next one does with it

After the first round the record holds **7 macros, 9 rules (all recursive)**, and
an operator order in which `midpoint` has been used twelve times and `mirror`
four. The second round reads it.

| task | A: no experience | B: reading it | what B reused |
|---|---:|---:|---|
| curve-seven | 89 | 116 | `rule:fd85072f4ebf` |
| curve-three | 54 | **31** | a macro and a rule |
| lattice-row | 13 | 13 | `rule:2583dbf006c7` |
| lattice-two-directions | 14 | **13** | `rule:fde68089f832` |
| orbit-quarter-turn | 1808 | 3184 | — |
| midpoint-chain | 1 | 1 | — |
| all-on-a-line | 1 | 1 | — |
| inside-a-disk | 1 | 1 | — |
| curve-inside-a-disk | 406 | **68** | a macro |
| count-eight | 1 | 1 | — |

| | solved | scored | nodes | programs checked | primitive applications | seconds |
|---|---:|---:|---:|---:|---:|---:|
| A | 10/10 | 10 | 2,388 | 11,564 | 2,388 | 126 |
| B | 10/10 | 10 | 3,429 | 18,534 | 4,005 | 92 |

What actually changed, concretely: two tasks reached a point through a macro
instead of three primitive steps, and **four tasks called a whole rule an earlier
round had built**, recursion and shared variables included — which is exactly
what a macro cannot hold, and the reason the rule store was added. The largest
single effect is `curve-inside-a-disk`, 406 nodes to 68.

And the cost: the node total is **higher** in B, not lower, and so are the checks
and the primitive applications. Wall time is lower. Nodes and seconds move in
opposite directions here, so neither is a proxy for the other.

## 5. The obstacle that appeared twice, and the one change

Before the budget was per body, B lost `curve-seven` — a task A solved in 89
nodes. The reason was exact: with macros in the table the enumeration found
**twelve** candidate bodies instead of two, and the recursion budget of 400 call
candidates was **shared across bodies**, so it was spent on the early ones and
the body that would have closed never got any. The budget is now per body, and
that alone took A from 8/10 to 10/10.

The same shape appeared again at the next level up. With more operators every
level of the enumeration is larger, so a fixed node budget reaches less far: B at
the same budget lost `orbit-quarter-turn`, which A solved at 1808 nodes. Raising
the budget in proportion to the operator count — 2500 to 4600 for 7 primitives
plus 6 macros — restored it at 3184 nodes.

**If one thing changes next, it is that**: the node budget is a fixed number
while the branching factor grows with everything the system learns, so every
acquisition quietly buys speed on the easy tasks with reach on the hard ones.
Either the budget follows the operator count, or the enumeration stops being
level-by-level and becomes best-first. The second is the real answer and the
larger change; the first is one line and is what the measurement above used.

## 6. What this is not

* Not natural-language understanding. Every formal requirement was written by a
  person beside the directive, and that is recorded per task.
* Not a crystal structure analysis. One lattice task is practice for that, and a
  patch of a square lattice drawn exactly is all it shows.
* Not a claim that the fragment is saturated. Ten tasks that the core happens to
  reach say nothing about the ones it does not.
* Macros and rules carry no geometric guarantee. Nothing was certified in this
  round; what was measured is search cost and whether the stated conditions hold.

## 7. Running it

```
python scripts/run_drawing_round.py --output reports/drawing-round/A
python scripts/run_drawing_round.py --output reports/drawing-round/B \
    --experience reports/drawing-round/experience-B.json --update --node-budget 4600
```
