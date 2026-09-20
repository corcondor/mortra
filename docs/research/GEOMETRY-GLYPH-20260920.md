# Masters, what survives between them, and the motion a slider cannot make

Repository: `corcondor/mortra`. Branch: `codex/operation-contracts-20260918`.
Base: `daf0f92`.

The source is a thread about variable fonts, read from text pasted into the
conversation. Nothing here browsed anything and no font file was read. The two
masters below were written by the development agent; they are not from a
typeface.

## 1. The thread says three things, and each is a statement about this fragment

> 平均というか、線形補間 (lerp) しかできないのが問題ですね。

`lerp(a, b, t) = a + t(b−a)`, and at `t = 1/2` that is this fragment's
`midpoint`, exactly — checked in a test. So a variable font's whole motion is one
of the seven primitives with a parameter. What the fragment constructs exactly is
the dyadic sliders, `t = k/2ⁿ`, by halving: `t = 3/8` is reachable and `t = 1/3`
is not.

> アウトライン描画に用いるde Casteljauはlerpの繰り返しで実現されています

Which is why, when the search in `reports/drawing-round` was given seven points
of a quadratic and nothing else, it returned subdivision by itself:

```
r(p0,p1,p2): v1 = midpoint(p0,p1); v2 = midpoint(p1,p2); v3 = midpoint(v1,v2)
             emit v3;  call r(p0,v1,v3);  call r(p2,v2,v3)
```

Three lerps and two calls. That is HOI written as a program rather than as a
stack of synchronised axes.

> 点を円弧に沿って動かせれば簡単なんですけど、今はとんでもない力技が必要です

This is the same wall this fragment has, and it was measured before the thread
was read: all seven primitives commute with a reflection and are rational maps,
so no rotation is among them and no composition of them is one either. Under
interpolation a point travels the straight segment between its two master
positions — checked: six steps from (3,0) to (−3,0) do not stay on the circle,
although both ends do.

## 2. What is new here: master compatibility, decided over QQ[t]

A designer depends on relations: these three points stay in line, these two
widths stay equal, this foot stays square. Whether such a relation survives *the
whole axis* is not a question about samples. The interpolated coordinates are
linear in `t`, so the relation's own polynomial becomes a polynomial in `t`, and

> the relation holds at every interpolation value **iff** that polynomial is the
> zero polynomial

which is decided exactly. On the two masters written here, of ten relations:

| relation | verdict |
|---|---|
| `coll(b,c,h)`, `para(a,d,b,c)`, `perp(a,b,a,d)`, `cong(a,b,d,c)`, `cong(a,d,b,c)`, `coll(g,k,c)`, `cong(g,k,h,m)` | preserved — the polynomial in `t` is identically zero |
| `coll(u,v,w)` | **holds at both masters and fails between them.** The polynomial is `t(t−1)`, so it holds only at `t = 0` and `t = 1` |
| `cong(u,v,x,y)` | **the same.** The polynomial is `−2t(t−1)` |
| `coll(a,d,b)` | does not hold at the masters either — an assumption that was wrong before interpolation was involved |

The `t(t−1)` is not a coincidence. These relations are quadratic in the
coordinates and the motion is linear, so the polynomial in `t` is a quadratic
vanishing at both masters: it is `c·t(t−1)`, and it is identically zero only when
`c` is. **A relation holding at both masters is in general not enough.** That is
the master-compatibility problem, and here it is answered with a certificate
rather than a sampling grid — including *where* it fails.

## 3. The arc

| motion | stays on the circle about the centre |
|---|---|
| interpolation, six steps | **no** |
| six sixtieth-turns | **yes**, and the sixth closes the circle exactly |

The turn is `geometry_quadratic.rot60`, added in `daf0f92`: it leaves the
rationals for `QQ(√3)` and it is the operation that moves a point along an arc
exactly. It costs the field — the coordinates are no longer rational — and it
does not give a right angle, which needs `√2`.

## 4. Recognition, and what that word is allowed to mean here

A glyph's signature is the set of relations of the fragment that hold of its
points — which triples are collinear, which pairs of segments are parallel,
perpendicular, equal. Measured on the stem corners: the light master has nine,
the bold master has the same nine, the interpolation at `t = 1/2` has the same
nine, and a deliberately altered outline does not.

So two outlines at different coordinates are matched by their structure. That is
**not** classification: nothing here names a letter, reads a font file or sees an
image. It is one outline matched against another by relations that are decided
exactly. And the compatibility result above is what tells you whether a signature
survives the axis at all — a relation in the signature that breaks between the
masters is one the recognition cannot rely on.

## 5. What is not claimed

* No font file was read, no image was seen, nothing was browsed. The masters are
  two point sets written in the script.
* Recognition here is matching one outline's relations against another's, not
  naming a character.
* The compatibility verdicts are exact over `QQ[t]`. The drawings are rasterised
  and are not.
* The fragment constructs the dyadic interpolation values only.
* Nothing here implements `avar2`, arcs in font paths, or any OpenType proposal.

## 6. Running it

```
python scripts/run_glyph_interpolation.py --output reports/glyph
python -m pytest tests/test_geometry_glyph.py tests/test_geometry_quadratic.py
```
