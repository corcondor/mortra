# GCLC / Newclid concrete certificate bridge

## Question

Can a theorem proved by GCLC's Wu or Groebner prover be returned as a concrete
Newclid obligation without trusting an engine-level success flag?

The acceptance path is:

```text
GCLC construction and conjecture
  -> native Wu / Groebner run
  -> typed point and relation lowering
  -> exact construction equations + NDG conditions
  -> independent exact replay
  -> canonical Newclid predicate
```

No external LLM, problem ID branch, answer lookup, or dataset auxiliary clause is
used by the bridge.

## Concrete bridge

`worker/backend/gclc_newclid_bridge.py` supports the following finite vocabulary:

```text
point / midpoint / online / line / parallel / perp / intersec
coll / para / perp / cong
```

For small systems it stores a Groebner quotient certificate. For larger
incidence systems it eliminates constructions in their declared order and
stores every nonzero rational denominator as an NDG obligation. Affine-only
theorems quotient coordinate redundancy by fixing three non-collinear free
points to a standard affine frame.

Unknown semantic commands are rejected. They are not silently ignored.

## Five-case result

The experiment uses official GCLC examples: midpoint, orthocenter, Gauss,
Pappus, and Pappus hexagon.

| Prover / verifier | proved or replayed |
|---|---:|
| GCLC Wu | 5/5 |
| GCLC Groebner, 60 seconds | 3/5 |
| GCLC Groebner, 120 seconds | 3/5 |
| MORTRA independent exact replay | 5/5 |
| canonical Newclid predicate | 5/5 |
| strict: both native methods + replay | 3/5 |
| portfolio: one native method + independent replay | 5/5 |

At 120 seconds, GCLC Groebner stopped on Pappus after about 127 seconds and on
Pappus hexagon after about 131 seconds. Wu proved both. The construction-order
replay proved both with explicit denominators. This is evidence for algorithmic
complementarity, not evidence that every geometry problem is solved.

## Frozen IMO obligation

A second generic bridge lowers the JGEX vocabulary

```text
r_triangle / foot / on_line / on_circle -> cong
```

to executable polynomial constraints. It applies Euclidean gauge fixing,
eliminates the foot and line intersections, retains locus parameters, and
reduces the goal modulo the remaining circle equations.

On official `2012_p5`:

| system | result |
|---|---:|
| Yuclid all-AR baseline | saturated unsolved |
| exact JGEX backend | exact remainder 0 |
| frozen 30-problem symbolic portfolio, first stage | **17/30 -> 18/30** |

The dataset auxiliary clause is hidden. The backend contains no `2012_p5`
branch. A point-renamed copy is also accepted, while an altered false goal is
rejected. This is one held obligation and therefore does not yet establish
broad generalization.

## Frozen 13-problem continuation

The vocabulary was then extended only with deterministic geometric morphisms:

```text
triangle / midpoint / orthocenter / circumcenter
four-point cyclic goal
distinct-root closure for the same line-circle locus
```

The last rule is the generic identity

```text
f(t1) = 0, f(t2) = 0, t1 != t2
  => (f(t1) - f(t2)) / (t1 - t2) = 0.
```

It exposes the Vieta relation between two distinct intersections without
registering a theorem-specific lemma. The same frozen backend was run on all 13
baseline-unsolved obligations with a per-problem 120-second process limit.

| status | count |
|---|---:|
| exact proved | 2 |
| unsupported vocabulary | 10 |
| timeout | 1 |
| unproved after lowering | 0 |

The exact proofs are `2008_p1a` and `2012_p5`. For `2008_p1a`, the certificate
contains 9 equations, 5 NDGs, 37 Groebner basis elements, 37 quotient terms, and
remainder 0. Its explicit assumptions include `diff a1 a2`, `diff b1 b2`, and
`diff c1 c2`. The six-point cyclic `2008_p1b` reached the 120-second limit.

The resulting symbolic portfolio was **19/30 = 63.3%**. This remains a
portfolio score rather than a Newclid-native score. At this stage the next
unsupported boundary was `incenter/incenter2`, `on_tline`, `on_dia`,
`on_pline`, and `angle_bisector`.

## Expanded 19-construction experiment

The exact lowering vocabulary was expanded by general construction semantics,
without problem-name branches:

```text
on_tline / on_pline / on_dia
angle_bisector / incenter / incenter2
mirror / reflect / on_bline / on_aline / eqangle3
```

Parallel and perpendicular loci use direction vectors. A diameter circle uses
a one-parameter rational chart. Angle equality uses the determinant/dot-product
polynomial for equality of two directed angles. Incenter coordinates introduce
side-length variables with equations `length^2 = squared_distance`; the
principal-length interpretation and every rational denominator remain explicit
certificate assumptions. `incenter2` is the incenter followed by three typed
orthogonal projections.

Thirteen construction and falsification tests pass, including point renaming,
an altered false congruence, an altered perpendicular/parallel claim, and a
false mirror-distance claim. Five legacy-dialect tests also pass. Coordinate
annotations such as `x@4.96_-0.13` are now treated as sketch metadata rather
than different semantic point names.

With a 60-second per-problem process limit on all 13 baseline-unsolved IMO
obligations:

| status | count |
|---|---:|
| exact proved | 2 |
| unsupported vocabulary | 1 |
| timeout | 10 |
| unproved after lowering | 0 |
| execution error | 0 |

The 60-second proofs are `2009_p2` and `2012_p5`. `2009_p2` is the new gain:
the same generic perpendicular-line, point-mirror, line-intersection, and
circumcenter morphisms produce an exact remainder of zero in about 10 seconds.
The previously certified `2008_p1a` requires more than 60 seconds in this run;
it was rerun alone with a 120-second limit and replayed exactly in 65.90
seconds.

The certificate union is therefore `2008_p1a`, `2009_p2`, and `2012_p5`, and
the symbolic portfolio rises from **19/30 to 20/30 = 66.7%**. The merge tool
accepts only reports containing `exact_replay=true`, `remainder=0`, and
nonconflicting certificate hashes.

This experiment also falsifies the claim that vocabulary coverage alone is
enough. Six formerly unsupported obligations become executable but exceed 60
seconds. `2015_p3` still exceeds 120 seconds after rational diameter-circle
parameterization, and `2019_p6` exceeds 120 seconds after incenter lowering.
The next backend boundary is construction-order triangular elimination rather
than more surface templates. The remaining true vocabulary boundary on this
set is `cc_tangent` in `2008_p6`.

The benchmark runner keeps a finite per-problem budget for fair comparison and
process isolation. Passing `--timeout-seconds 0` enables an unbounded
deep-research run; a benchmark timeout is not recorded as a mathematical
refutation.

## Falsification and limits

- Altered Pappus and altered congruence conclusions are rejected.
- An unsupported `circle` GCLC command is rejected instead of being ignored.
- The `20/30` score is a MORTRA symbolic portfolio score, not a Newclid-native
  proof score.
- Native proof-state injection is still absent. The current exchange boundary
  is a canonical predicate plus an independently replayable exact certificate.
- The next scientific test is to freeze the lowering vocabulary and run it on
  all 13 baseline-unsolved IMO obligations, reporting accepted, rejected,
  unsupported, and timeout separately.

## Reproduction artifacts

- `data/gclc-newclid-concrete-certificate-bridge-2026-08-15.json`
- `data/gclc-newclid-concrete-certificate-bridge-120s-2026-08-15.json`
- `data/jgex-exact-portfolio-2012-p5-2026-08-15.json`
- `data/jgex-exact-frozen-unsolved13-root-closure-2026-08-15.json`
- `data/jgex-exact-frozen-unsolved13-expanded19-60s-2026-08-16.json`
- `data/jgex-exact-2008-p1a-expanded19-120s-2026-08-16.json`
- `data/jgex-exact-portfolio-expanded19-2026-08-16.json`
- `worker/backend/test_gclc_newclid_bridge.py`
- `worker/backend/test_jgex_exact_constraint_bridge.py`
