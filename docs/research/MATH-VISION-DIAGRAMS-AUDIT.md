# Math-Vision Diagrams audit for MORTRA

Date: 2026-08-13
Paper: [Math-Vision Diagrams](https://arxiv.org/abs/2608.08964)

## What the paper actually contributes

This is primarily a benchmark, not a new construction engine. It selects 2,920
diagram-dependent images from the 3,040-problem MathVision dataset and creates a
self-contained English `Draw ...` prompt for each reference image.

The prompt is not normally the original competition problem. Three model
families describe the reference image, a separate vision model resolves
conflicts, Llama 3.3-70B condenses the descriptions, and human mathematical
experts audit a sample for completeness, correctness, and clarity. The paper
therefore measures caption-conditioned reconstruction more directly than
problem-to-diagram mathematical elaboration.

## Does it specify a construction method?

Only at the execution level. Code models may emit TikZ, SVG, or
Python/Matplotlib, which is compiled into a raster image. The appendix gives one
representative LLM response for an incircle: choose triangle coordinates,
compute side lengths, Heron area, incenter, and inradius, then draw the result.

The choice of construction, coordinates, formulas, and program is made by each
LLM. The benchmark does not expose or prescribe a common symbolic search
algorithm. The generation policy is therefore black-box for closed models and
model-dependent for open models. The surrounding compilation pipeline is not
black-box.

## Published automatic metrics

| Metric | What it measures | Important limitation |
|---|---|---|
| Compile rate | executable output | compilable can still be mathematically wrong |
| DISTS | perceptual structure/texture distance | does not prove a constraint |
| CLIP cosine | broad semantic image similarity | can accept a plausible but wrong diagram |
| Edge IoU/F1 | Canny edge overlap | coordinate/style sensitive; topology is implicit |

The authors explicitly report that fixed Canny metrics operate near the floor
(best Edge IoU about 0.10) and call for metrics that compare mathematical
validity. This is the opening relevant to MORTRA.

## MORTRA extension implemented

MORTRA keeps the paper's evaluation axes but inserts an executable semantic
layer before raster comparison:

```text
prompt/problem
  -> typed cells, labels, incidence, constraints
  -> verify boundary^2 = 0 and backend constraints
  -> compare cell/label/incidence multisets up to identifier renaming
  -> compare Euler characteristic and Betti numbers
  -> render
  -> DISTS/CLIP/edge metrics when a reference raster exists
```

Current deterministic checks:

- an isomorphic diagram remains a strict match after every cell ID is changed;
- a face-attachment error is rejected even when primitive counts are identical;
- label omission is separated from topology and rendering;
- a 4,800-cell torus cellulation verifies
  `chi=0` and `(b0,b1,b2)=(1,2,1)`.

This is stronger mathematical validation than image similarity alone, but it is
not yet a score on the released 2,920 prompts. As of this audit, the paper says
the code and data will be open-sourced, but the arXiv record does not link a
repository and a direct repository search found no official release.

## Transfer to mathematical solving

Diagram generation does not automatically raise arithmetic, number theory, or
probability scores. The plausible transfer mechanism is narrower and testable:

1. elaborate a problem into typed mathematical structure;
2. construct a diagram from that structure;
3. read the generated diagram back into a second semantic representation;
4. reject or repair disagreements;
5. let the solver use verified incidences, regions, symmetries, and auxiliary
   objects;
6. compare held-out solving with this loop enabled versus disabled.

The required evidence is an improvement on held-out visual mathematics while
non-visual controls do not regress. A diagram-generation score by itself is not
evidence of general mathematical intelligence.
