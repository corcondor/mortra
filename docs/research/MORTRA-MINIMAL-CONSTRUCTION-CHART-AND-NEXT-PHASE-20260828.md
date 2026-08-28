# MORTRA: minimal construction chart and next research phase

Date: 2026-08-28
Frozen cohort: HAGeo held-out 89
Policy: no external LLM, no expected-answer lookup, no problem-name branch

## Purpose

The previous generated-action normalization removed 18 of 1,505 duplicate
actions (1.196%) but added no certified solve.  This experiment asks a stricter
question:

> Can one small, reusable representation chart add a non-vacuous proof to the
> frozen capability union, while preserving every natural-language domain
> condition that JGEX dropped?

The longer-term purpose is to identify the unit that can be inverted for
problem generation and transported to algebraic geometry and manifolds.

## Hypotheses

### H0: normalization alone cannot improve reachability

Deduplicating equivalent actions can reduce work, but it cannot create a
missing theorem edge.  Therefore a 1.196% reduction need not change the solved
set.

### H1: a typed semantic condition plus an executable construction chart can
increase the certified solved set

For the unresolved construction containing a symmedian point and three
perpendicular projections, the missing reusable chain is:

```text
acute-domain semantics
  -> directed-angle symmedian construction
  -> second Lemoine circle
  -> harmonic power / cyclicity
  -> internal angle bisectors
  -> Pascal direction
  -> altitude incidence
```

### H2: the same chart is a seed for reversible problem generation

A chart is generation-capable only when its domain, forward proof, reverse
construction and invariant checks are explicit.  A theorem-specific answer is
not enough.

## Method

### 1. Preserve semantics that JGEX erased

`geometry_natural_semantics.py` implements a finite, auditable grammar for:

- `acute(A,B,C)`
- `between(D1,B,C)`
- `between(D2,B,C)`

The natural statement and JGEX source are hashed independently.  The chart is
not admitted when only the bare JGEX construction is supplied.

This guard is necessary, not cosmetic.  With
`B=(0,0), C=(1,0), A=(0.4,0.3)`, the JGEX construction is defined but the
incenter of `PXY` does not lie on the altitude.  The dropped acute condition
changes the truth value.

### 2. Reconstruct the official proof as an exact chart

The chart follows the official 2021 GOWACA P5 proof structure.  Normalize

```text
B=(0,0), C=(1,0), A=(u,v)
```

and set `s=u^2+v^2`, `t=s-u`, `h=1+t`.  Acuteness gives

```text
v>0, u>0, 1-u>0, t>0, h>0.
```

The two `on_aline` clauses give the symmedian point

```text
K=((u+s)/(2h), v/(2h)).
```

The perpendicular projections and auxiliary intersections produce
`X,Y,X1,Y1,V,W`.  Exact replay verifies

```text
KX = KY = KX1 = KY1 = KV = KW,
```

so the six points lie on the second Lemoine circle.  The harmonic-power step is
replayed as the exact determinant `P,K,X,Y` cyclic.  Two squared bisector
identities are supplemented by oriented sign certificates; therefore `XW` and
`YV` are internal, not merely unoriented, bisectors.  Their intersection is

```text
I=(u, -u(u-1)t/(vh)),
```

and hence `I_x=A_x=D_x=u`.  This is the coordinate replay of the final Pascal
step, whose third opposite-side intersection is the point at infinity in the
altitude direction.

The official source used to reconstruct the chart is the
[2021 GOWACA official solutions](https://services.artofproblemsolving.com/download.php?id=YXR0YWNobWVudHMvNS9hL2I1ZWQxNWZjYmVjNmUzZTA0MWE1ZTEzN2Y3MWUyNDhhY2IwNjNiLnBkZg%3D%3D&rn=Z293YWNhX3NvbC5wZGY%3D).

### 3. Frozen cohort and negative controls

The chart registry was run over all 13 previously unresolved frozen problems.
Controls were:

- omit the natural statement;
- replace `acute triangle` by `triangle`;
- evaluate a concrete non-acute counterexample;
- retain an existing quantifier-repaired proof and verify that it is excluded
  from raw benchmark admission.

## Results

| Measure | Control | Treatment | Change |
|---|---:|---:|---:|
| certified solved | 76/89 | 77/89 | +1 |
| certified score | 85.393% | 86.517% | +1.124 percentage points |
| unresolved | 13 | 12 | -1 |
| chart residuals | - | 41/41 zero | exact replay |
| ambiguous matches | - | 0 | none |
| vacuous/unit-ideal exclusions | 0 | 0 | none |
| chart/certificate regression tests | - | 187/187 passed | no regression |

The 13-problem audit found two mathematical matches.  One was an older proof
that becomes true only after changing an under-specified one-output
intersection into an existential statement.  It is now rejected by the audit,
artifact writer and certificate verifier.  The only admitted new result is
`2021GOWACAp5`.

Hash chain:

```text
JGEX source       788999f852d32dd23fc5997062437e2d762fc86b4f6bf83a582334c1b83fa78f
natural statement 0ae4d2dff38b5bf1a40bb0a9d794e615adb95a7298c960b543ec1c6691f6572c
chart certificate b01b47e337b024bfededd0db6a031ee6b74c39daead5106c1d3247f7c4a90cde
portfolio file    5473071d0ae51bc8a40195f0d8c6a7c499c77043dd72a8262c6c7544c353695a
```

## Discussion

### Why the score moved this time

Normalization changes the number of representations of an existing edge.
The new chart adds a missing composite edge between five representations.  In
reachability terms:

```text
deduplication: E -> E / equivalence       (same reachable vertices)
new chart:     E -> E union {composite}   (larger reachable set)
```

The useful unit is therefore not another isolated rule.  It is a typed chart
with domain conditions, intermediate invariants and a replayable composite
certificate.

### What is still missing in the remaining 12

1. **Natural semantics**: arc choice, second intersection, internal/external,
   segment/ray order and nondegeneracy must survive elaboration.
2. **Circle/projective charts**: pole-polar, power, radical center, Miquel and
   coaxality still occur repeatedly.
3. **Bidirectional angle/circle charts**: tangent-chord and inscribed-angle
   implications need forward and reverse forms.
4. **Affine/complex charts**: multiple circumcenters, inversion and similarity
   centers need a common exact representation.
5. **Three-dimensional and ordered geometry types**: these are not yet in the
   frozen geometry kernel.

These are reachability gaps.  Increasing depth without adding the missing
composite cannot close them.

## Common IR for the next phase

The minimum domain-independent record is:

```text
TypedObject(type, parameters, coordinates?)
TypedMorphism(domain, codomain, preconditions, postconditions)
RepresentationChart(forward, reverse, invariants, domain_of_definition)
ProofDAG(obligations, alternatives, certificates)
ProblemView(statement, diagram, goal, solution)
```

Every representation change must retain:

- source and target types;
- branch and nonzero conditions;
- forward and reverse proof obligations;
- an invariant that can be checked in both representations;
- a certificate hash tied to the original statement.

### Algebraic geometry

Start with the already used bridge

```text
incidence scene <-> polynomial ideal + saturation <-> constructible set.
```

This is a controlled move from Euclidean geometry to affine algebraic geometry.
The first objects should be ideals, varieties on explicit affine charts,
open-set conditions and rational maps.  General schemes are premature until
round-trip certificates work on this layer.

### Higher-dimensional manifolds

Use the same chart contract literally:

```text
local coordinates <-> transition map <-> invariant tensor/relation.
```

The entry criterion is exact overlap consistency and invariant preservation on
two or more charts.  Rendering a 3D scene alone is not a manifold reasoner.

### Mathematical "standard model"

This name should mean a measured compression target, not a claim of a finished
theory: find a small generator set and normal forms whose typed compositions
cover many theorem families.  Report compression, coverage and newly certified
solves separately.

### Problem generation

Invert a certified chart only after all of the following hold:

1. forward proof replay succeeds;
2. reverse construction replay succeeds;
3. the generated statement round-trips through the typed IR;
4. the generated diagram satisfies the same branch conditions;
5. the answer and readable proof are regenerated from the certificate;
6. novelty is structural, not a numerical substitution;
7. non-vacuity and uniqueness are checked independently.

## Decision and migration gates

Work on generation and algebraic geometry should begin now, but as a parallel
track using the common IR, not by abandoning the remaining geometry evidence.
The next phase is admitted only when:

- one chart transfers to at least three held-out problems without modification;
- forward/reverse round-trip residuals are all zero;
- natural-language qualifiers survive parse -> IR -> statement;
- a generated problem includes diagram, proof and answer from one certificate;
- a frozen non-geometry benchmark is defined before tuning.

The current +1 is a certified capability improvement.  Because the chart was
chosen after inspecting the unresolved problem and its official proof, it is
not evidence of unseen held-out transfer.  That distinction remains explicit.

## Reproduction

```powershell
python -m pytest worker/backend/test_second_lemoine_harmonic_incenter_chart.py -q
python scripts/audit_exact_chart_unresolved.py --union data/hageo-certified-capability-union-plus-orthic-parallel-chord-two-tangents-chart-2026-08-27.json --dataset data/hageo-409-jgex-2026-08-18.txt --natural-dataset data/hageo-409-natural-language-2026-08-26.json --output data/exact-chart-remaining13-natural-runtime-audit-2026-08-28.json
python scripts/update_hageo_capability_union.py --base data/hageo-certified-capability-union-plus-orthic-parallel-chord-two-tangents-chart-2026-08-27.json --addition artifacts/exact-chart-runtime-v24/2021GOWACAp5.artifact.json --frozen-baseline data/hageo-409-heldout-native-baseline-2026-08-18.json --output data/hageo-certified-capability-union-plus-second-lemoine-chart-2026-08-28.json
python scripts/audit_hageo_nonvacuous_union.py --union data/hageo-certified-capability-union-plus-second-lemoine-chart-2026-08-28.json --frozen-baseline data/hageo-409-heldout-native-baseline-2026-08-18.json --output data/hageo-certified-capability-union-plus-second-lemoine-chart-nonvacuous-audit-2026-08-28.json
```
