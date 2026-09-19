# Drawing with one black dot

Repository: `corcondor/mortra`. Branch: `codex/operation-contracts-20260918`.
Base: `35b9086`. Nothing in the fragment changed: the same seven primitives, the
same ten predicates, the same certification path.

## 1. The convention

A point becomes a black disk of one fixed radius, opaque, on white paper. One
radius for every image, no grey, no transparency, no post-processing. The only
thing that can carry tone is how many points are placed where.

Disks on a lattice of spacing `h` with `r = h/2` are tangent at closest and never
overlap, so the black fraction of a window holding whole disks is exactly
`(inked sites) x pi r^2 / area`, and the largest black fraction the convention
can reach is `pi/4 = 0.7854`. Targets above that are refused rather than
approximated. Every image checks that no two of its disks overlap.

Paper 4:3, one scale for both axes, `r = 1/64` of a unit, lattice spacing
`1/32`, 1200x900 px at 300 px per unit.

## 2. Where the points come from

The lattice is built by the fragment's own primitives. The unit square is halved
repeatedly — every inserted point is one `midpoint` of two points already there —
and the sheet is covered by translating that cell, where a translation is
`mirror(O, midpoint(P, T))`, two existing primitives and no new one. For the
sheet used here: **12,513 points from 23,933 primitive applications, in 3
seconds**.

Which lattice sites take ink is a separate rule, deliberately: an ordered-dither
threshold on the lattice indices. It is a plain deterministic iteration — no
randomness, no seed, same inputs give the same points — and it is not a geometric
operation and is not recorded as one.

## 3. Regions, without a new predicate

`in_closed_disk` is the relation the fragment can already write:

```
exists U V:  midp(P,U,V)  and  cong(O,U,O,A)  and  cong(O,V,O,A)
```

Writing `U = P+v`, `V = P-v`, the two `cong` atoms say
`|P-O|^2 + |v|^2 = |OA|^2`, and such a `v` exists exactly when `|P-O| <= |OA|`.
That inequality is what the code decides, on rationals, exactly. It is the
reduced form of the relation, not a new predicate, and the reduction assumes only
that the witnesses `U, V` may be real rather than rational — a rational witness
failing to exist is never read as the point being outside.

`on_closed_segment` is `coll(A,P,B)` intersected with the disk on `AB` as
diameter; `strictly_between` adds `diff`. The shadow is then

```
S = { X in W : exists P in K, P strictly between L and X }
```

and its execution replaces the existential by the one candidate it can have: for
a point light and a segment occluder, the points of `line(L,X)` that could
occlude are the points of `line(A,B)` on it, and two distinct lines meet in at
most one point — which the fragment's own `intersection_ll` produces. The
assumptions that make the two agree are stated with the result: the light is off
the line of the occluder, and a ray parallel to the occluder meets it nowhere and
is reported as unoccluded rather than as an error.

`coll(L,P,X)` alone would not do, and the tests hold it to that: an occluder
behind the light is collinear with light and point and casts nothing; an occluder
beyond the point does not shade it.

## 4. What came out

| image | dots | target black | measured | note |
|---|---:|---:|---:|---|
| a-pale | 1,593 | 0.10 | 0.0976 | error -0.0024 |
| b-dark | 9,585 | 0.60 | 0.5960 | error -0.0040 |
| c-ramp | 5,907 | 0.04 to 0.70 | 0.083 to 0.662 in 8 bands | monotone, largest band error 0.0061 |
| d-shadow | 5,977 | 0.55 in, 0.06 out | 0.543 in, 0.060 above, 0.060 below | 5,585 dots inside |
| d2-shadow | 2,465 | same | — | the same procedure, light and occluder moved |

Local uniformity: over both the aligned cell windows and windows deliberately off
the dither's period, the spread of measured coverage is below 1e-4. The pattern
is periodic, so this says the dither is even at this scale, not that an arbitrary
placement would be.

The shadow outline is built, not written down: each boundary ray meets each side
of the window through `intersection_ll`, the window corners in shadow are added,
and the ends of the occluder are added when the occluder itself stands inside the
window. For `d-shadow` that gives a hexagon of area 7.668 in the window; for
`d2-shadow` a pentagon of area 2.197. The regression configuration — light at the
origin, occluder from (1,-1) to (1,1), window [2,4]x[-5,5] — gives exactly the
four corners (2,-2), (2,2), (4,4), (4,-4) and area exactly 12, as a `Fraction`.

The area of a shadow and the area its ink covers are different numbers and are
reported separately.

## 5. What is new here and what was reused

Reused: `execute_primitive` for every constructed point; `midpoint`, `mirror` and
`intersection_ll`; the polynomial meaning the fragment gives `coll`, `cong`,
`midp` and `diff`; Pillow, already a dependency.

Newly connected, and recorded as output plumbing rather than as geometry: the
lattice iteration, the ordered-dither selection, an SVG writer, a PNG writer, and
a coverage measurement by sample cells.

No acquired operation was used. The drawing path needs a two-step translate
(`midpoint` then `mirror`), and none of the operations the loop has acquired has
that shape — the stored ones are `foot`/`intersection_ll`, `mirror`/`midpoint`,
`circle`/`mirror` and so on. That was checked rather than assumed.

## 6. What this is not

* Not an artistic technique the system discovered. It is the connection from
  geometry to ink, which is what was missing.
* The coverage figures are sample-cell approximations at a stated resolution, not
  exact areas.
* The grey along a disk's edge in a PNG is the rasteriser averaging a
  supersampled image, not a drawn tone. The SVG holds the disks themselves, and
  every image is checked to contain nothing but black circles of one radius.
* Nothing here says anything about physical shading: no source of finite size, no
  material, no indirect light.
* The plane is the whole setting. A solid casting a shadow on a floor is not
  modelled.

## 7. Running it

```
python scripts/run_ink_drawings.py --output reports/ink --depth 5 --pixels-per-unit 300
python -m pytest tests/test_geometry_ink.py
```
