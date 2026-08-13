# MORTRA Executable Construction Benchmark v0.1

Date: 2026-08-13

## Research question

Can one typed mathematical state drive all of the following without replacing
the construction by a display-only illustration?

1. auxiliary-object synthesis;
2. independent geometric verification;
3. a dynamic 2D construction history;
4. a volumetric 3D representation made from planar constructions;
5. a path suitable for a physical drawing device;
6. measurable improvement on held-out geometric tasks.

Counting circles is not sufficient. A hundred unrelated circles are not a
stronger mathematical representation than one meaningful circle. The benchmark
therefore measures the relations and invariants that connect the primitives.

The converse is also important: circles and straight lines are not a universal
diagram language. Dynkin diagrams, Cayley graphs, tensor networks, Voronoi
tessellations, robot configuration spaces, and positive-genus polyhedra carry
different kinds of information. The 96-circle torus is one stress test for a
surface exposed by planar sections, not the ontology of MORTRA.

## Representation hierarchy

The general representation target is a sparse, typed cellular complex together
with a separate embedding:

```text
abstract cells and incidence              geometric realization
0-cells: points / graph nodes / tensors   coordinates or symbolic positions
1-cells: edges / curves / paths           line, arc, spline, geodesic
2-cells: regions / faces                   polygonal or curved patch
3+-cells: volumes / configuration cells   mesh, implicit set, manifold chart
labels: group elements / tensor ports / constraints / orientation
```

The chain condition `boundary(boundary(cell)) = 0` verifies attachment
consistency independently of a drawing. The embedding then adds metric and
visibility constraints. This separation is required because a Cayley graph can
be combinatorially correct under many layouts, while a Voronoi diagram also has
metric nearest-site obligations and a robot path lives in configuration space.

Benchmark tracks must therefore include at least:

1. labelled 1-complexes: Dynkin/Cayley/tensor-network connectivity;
2. planar subdivisions: Voronoi/Delaunay duality and region coverage;
3. 2-complexes in 3D: polyhedral incidence, Euler characteristic, orientability;
4. configuration-space paths: collision freedom, continuity, and endpoint goals;
5. sectional/orbit constructions: the current 96-circle torus experiment.

## Formal object

The current experiment uses two related contracts.

### Euclidean construction log

```text
typed point constraints
  -> constructible loci (line / circle / perpendicular bisector)
  -> locus intersections
  -> candidate points
  -> constraint verification
  -> append-only construction history
```

The operation vocabulary has seven members:

```text
given point
line through two points
circle from centre and through-point
line-line intersection
line-circle intersection
circle-circle intersection
witness selection by all constraints
```

Problem names, theorem names, and numeric answers are absent from this
vocabulary.

### Spatial circle family

A ring torus is represented by the invariant

```text
(sqrt(x^2+y^2)-R)^2 + z^2 = r^2,  R > r > 0.
```

It is exposed by two families of planar circles:

```text
profile circle --SO(2) action--> 48 meridian circles
profile point  --SO(2) orbit-->  48 parallel circles
```

The output is not a triangle mesh. It is 96 executable planar constructions
whose superposition reveals the same 3D object. Each sampled point must satisfy
its plane, its circle, and the shared torus invariant.

## Current measured result

The artifact is `data/euclidean-construction-experiment.json`.

| Track | Baseline | Construction | False acceptance |
|---|---:|---:|---:|
| Typed auxiliary-point tasks | 1/12 | 12/12 | 0/4 negatives |

The 2D design artifact contains 19 circles, 18 derived centres, 17 intersection
steps, and 42 state transitions. The 3D artifact contains 96 planar circles and
4,608 independently checked samples. Maximum torus-invariant residual is below
`5e-15`.

This is a bounded mechanism experiment. It is not the frozen 522-problem score,
not a Lean proof, and not yet evidence of general visual creativity.

## External benchmark atlas

No single public benchmark currently covers theorem proving, parametric
construction, dynamic presentation, 3D semantic transport, and design quality.
MORTRA should therefore report separate tracks rather than collapse them into
one score.

### Proof and auxiliary construction

- [IMO-AG-30 / AlphaGeometry](https://www.nature.com/articles/s41586-023-06747-5):
  olympiad theorem proving where auxiliary construction is exogenous term
  generation.
- [FormalGeo](https://formalgeo.github.io/): formal predicates, theorems,
  construction descriptions, proof search, and geometry datasets.
- [GeoLaux](https://arxiv.org/abs/2508.06226): long-step geometry problems that
  require auxiliary lines.

Metrics: formalization rate, proof rate, auxiliary-construction recall, invalid
proof rate, search nodes, and time.

### Constraint construction and CAD

- [SketchGraphs](https://github.com/PrincetonLIPS/SketchGraphs): 15 million real
  CAD sketches represented as construction sequences and geometric constraint
  graphs.
- [Vitruvion](https://openreview.net/forum?id=Ow1C7s3UcY) and
  [SketchGen](https://openreview.net/forum?id=Oeb2LbHAfJ4): constrained sketch
  generation and constraint inference.

Metrics for MORTRA: parse coverage, solved-constraint rate, remaining degrees of
freedom, edit propagation, invalid geometry rate, and held-out graph novelty.
Sequence likelihood is not a useful primary metric for a non-LLM system.

### Design and spatial transport

There is no established benchmark for "mathematically valid construction ->
logo/motion/3D experience". This must be measured with explicit submetrics:

1. invariant residual and independent replay;
2. transformation equivariance;
3. connected dependency graph;
4. primitive and relation diversity;
5. topology of the reconstructed object;
6. silhouette stability across held-out views;
7. human preference under blinded comparison;
8. ablation: remove a construction family and measure recognition/proof loss.

Recent public references now make part of this measurable. Math-Vision Diagrams
contains 2,920 competition-grade diagram tasks across 16 disciplines and
explicitly separates visual interpretability, semantic faithfulness, and
mathematical validity. OmniSch demonstrates the complementary diagram-to-graph
track: dense schematics must be recovered as attributed connectivity rather
than judged only as images.

## Acceptance criteria for the next version

1. Import a fixed SketchGraphs test slice without training on it.
2. Add at least circle, arc, tangent, coincidence, parallel, perpendicular,
   symmetry, and dimension constraints to the executable IR.
3. Run FormalGeo/GeoLaux auxiliary-construction cases through a fixed parser.
4. Compare proof search with and without diagram-derived construction proposals.
5. Add held-out examples of labelled graphs, planar subdivisions, cell
   complexes, and configuration-space paths; do not count success on one class
   as coverage of another.
6. Evaluate at least three spatial targets (torus, sphere sections, ruled
   surface) generated from planar families.
7. Run a fixed Math-Vision Diagrams slice and report semantic, geometric, and
   rendering validity separately.
8. Obtain blinded human ratings for logo naturalness and mathematical legibility.

Until these are met, the correct claim is: MORTRA can replay and verify one
nontrivial 2D/3D construction family, not that it has general construction or
design intelligence.
