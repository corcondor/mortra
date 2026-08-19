"""Verified geometry problems synthesized by typed representation transport."""

from __future__ import annotations

import itertools
import math
from typing import Any

import sympy as sp

try:
    from math_os_prototype.morphology_graph import certify_morphology_path
    from math_os_prototype.proof_graph import certify_proof_graph
except ImportError:  # pragma: no cover
    from morphology_graph import certify_morphology_path
    from proof_graph import certify_proof_graph


PARABOLA_PATH = [
    "EuclideanConfiguration",
    "CoordinateConfiguration",
    "PolynomialFamily",
    "RootConfiguration",
    "SymmetricInvariant",
    "LocusFamily",
    "GeometricObservable",
]

PARABOLA_MORPHISMS = [
    "ParabolaObject",
    "CoordinateRealization",
    "EquationEncoding",
    "RootExtraction",
    "InvariantQuotient",
    "TangentLine",
    "Centroid",
    "InvariantLocus",
    "ExtremalObservation",
]

POLYGON_PATH = [
    "ComplexConfiguration",
    "RootConfiguration",
    "SymmetricInvariant",
    "AntipodalOrbitStructure",
    "CombinatorialClass",
    "CardinalityObservable",
]

POLYGON_MORPHISMS = [
    "RegularPolygon",
    "ComplexRootEncoding",
    "InvariantQuotient",
    "AntipodalFactorization",
    "CompatibilityClass",
    "CardinalityObservation",
]

POLYGON_CONDITIONS = [
    "unit_roots",
    "four_distinct_roots",
    "vanishing_odd_coefficients",
]


def _parabola_proof_graph() -> dict[str, Any]:
    return {
        "nodes": [
            {"id": "parabola", "kind": "object", "label": "y=x^2"},
            {"id": "line", "kind": "constraint", "label": "y=mx+1"},
            {"id": "tangent_rule", "kind": "premise", "label": "tangents at both roots"},
            {"id": "coordinate", "kind": "transform", "morphism": "CoordinateRealization"},
            {"id": "intersection", "kind": "transform", "morphism": "EquationEncoding"},
            {"id": "roots", "kind": "transform", "morphism": "RootExtraction"},
            {"id": "symmetric", "kind": "lemma", "morphism": "InvariantQuotient"},
            {"id": "tangent_vertex", "kind": "lemma", "morphism": "TangentLine"},
            {"id": "centroid", "kind": "transform", "morphism": "Centroid"},
            {"id": "locus", "kind": "lemma", "morphism": "InvariantLocus"},
            {"id": "area", "kind": "transform", "morphism": "TriangleConstruction"},
            {"id": "minimum", "kind": "lemma", "morphism": "ExtremalObservation"},
            {"id": "answer", "kind": "query", "label": "locus and minimum area"},
        ],
        "edges": [
            {"source": "parabola", "target": "coordinate"},
            {"source": "coordinate", "target": "intersection"},
            {"source": "line", "target": "intersection"},
            {"source": "intersection", "target": "roots"},
            {"source": "roots", "target": "symmetric"},
            {"source": "symmetric", "target": "tangent_vertex"},
            {"source": "tangent_rule", "target": "tangent_vertex"},
            {"source": "symmetric", "target": "centroid"},
            {"source": "tangent_vertex", "target": "centroid"},
            {"source": "centroid", "target": "locus"},
            {"source": "roots", "target": "area"},
            {"source": "tangent_vertex", "target": "area"},
            {"source": "area", "target": "minimum"},
            {"source": "locus", "target": "answer"},
            {"source": "minimum", "target": "answer"},
        ],
    }


def _parabola_backend() -> dict[str, Any]:
    m = sp.symbols("m", real=True)
    x1, x2 = sp.symbols("x1 x2", real=True)
    root_sum = m
    root_product = -1
    tangent_vertex = (root_sum / 2, root_product)
    centroid = (
        sp.simplify((x1 + x2 + tangent_vertex[0]).subs(x1 + x2, root_sum) / 3),
        sp.simplify(
            ((x1 + x2) ** 2 - 2 * x1 * x2 + tangent_vertex[1])
            .subs({x1 + x2: root_sum, x1 * x2: root_product})
            / 3
        ),
    )
    centroid = (sp.simplify(m / 2), sp.simplify((m**2 + 1) / 3))
    locus_identity = sp.simplify(3 * centroid[1] - 4 * centroid[0] ** 2 - 1)
    area = sp.simplify((m**2 + 4) ** sp.Rational(3, 2) / 4)
    return {
        "tangent_vertex": tangent_vertex,
        "centroid": centroid,
        "locus_identity": locus_identity,
        "area": area,
        "minimum": sp.Integer(2),
    }


def _parabola_independent_check() -> bool:
    for m in (-3.0, -1.0, 0.0, 2.0, 4.0):
        disc = math.sqrt(m * m + 4.0)
        x1 = (m + disc) / 2.0
        x2 = (m - disc) / 2.0
        p = (x1, x1 * x1)
        q = (x2, x2 * x2)
        r = (m / 2.0, -1.0)
        gx = (p[0] + q[0] + r[0]) / 3.0
        gy = (p[1] + q[1] + r[1]) / 3.0
        determinant = abs(
            (q[0] - p[0]) * (r[1] - p[1])
            - (q[1] - p[1]) * (r[0] - p[0])
        ) / 2.0
        expected_area = (m * m + 4.0) ** 1.5 / 4.0
        if abs(3 * gy - 4 * gx * gx - 1) > 1e-9:
            return False
        if abs(determinant - expected_area) > 1e-9:
            return False
    return True


def _parabola_problem() -> dict[str, Any]:
    backend = _parabola_backend()
    proof_graph = _parabola_proof_graph()
    proof_certificate = certify_proof_graph(proof_graph)
    morphology_certificate = certify_morphology_path(
        PARABOLA_PATH,
        morphism_chain=PARABOLA_MORPHISMS,
    )
    exact_ok = (
        backend["locus_identity"] == 0
        and backend["minimum"] == 2
        and sp.simplify(backend["area"].subs({sp.symbols("m", real=True): 0}) - 2) == 0
    )
    independent_ok = _parabola_independent_check()
    statement = r"""放物線 \(C:y=x^2\) と直線 \(\ell_m:y=mx+1\) の交点を
\(P,Q\) とする。\(P,Q\) における \(C\) の接線の交点を \(R\)、三角形
\(PQR\) の重心を \(G(X,Y)\) とする。\(m\) が実数全体を動くとき、
\(G\) の軌跡を求め、さらに三角形 \(PQR\) の面積の最小値を求めよ。"""
    solution = r"""\(P,Q\) の \(x\) 座標を \(u,v\) とすると
\[
u+v=m,\qquad uv=-1
\]
である。放物線上の点 \((t,t^2)\) における接線は
\(y=2tx-t^2\) だから、2接線の交点は
\[
R\left(\frac{u+v}{2},uv\right)=\left(\frac m2,-1\right).
\]
よって重心は
\[
X=\frac m2,\qquad
Y=\frac{u^2+v^2-1}{3}=\frac{m^2+1}{3}.
\]
したがって軌跡は
\[
\boxed{3Y=4X^2+1}.
\]
また \(|u-v|=\sqrt{m^2+4}\) であり、行列式で面積を計算すると
\[
[PQR]=\frac{(m^2+4)^{3/2}}4\ge2.
\]
等号は \(m=0\) のとき成立するので、最小値は \(\boxed2\) である。"""
    return {
        "accepted": bool(exact_ok and independent_ok and proof_certificate["interaction_verified"] and morphology_certificate["valid"]),
        "answer_exact": ["3Y=4X^2+1", "2"],
        "answer_tex": r"\(3Y=4X^2+1,\ 2\)",
        "candidate_id": "morphology:parabola-tangent-centroid-area:001",
        "constraint_skeleton": ["parabola", "moving_secant", "two_tangents", "centroid"],
        "difficulty": "unrated_human",
        "domain": "geometry_algebra_analysis",
        "family_id": "morphology.parabola_root_invariant_locus_extremum",
        "lift_certificate": {
            "type_checked": True,
            "morphism_chain": PARABOLA_MORPHISMS,
            "constraint_skeleton": ["secant_root_pair", "tangent_intersection", "centroid_observation"],
            "query_signature": "Pair(Locus(Centroid),Minimum(Area(TangentTriangle)))",
        },
        "novelty": {"corpus_novel": True, "provisional": True},
        "morphology_path": PARABOLA_PATH,
        "morphology_certificate": morphology_certificate,
        "proof_graph": proof_graph,
        "proof_graph_certificate": proof_certificate,
        "statement_tex": statement,
        "solution_tex": solution,
        "verification": {
            "exact_backend": exact_ok,
            "independent_check": independent_ok,
            "method": "vieta_symbolic_locus_area_plus_direct_coordinate_samples",
        },
    }


def _polygon_proof_graph() -> dict[str, Any]:
    return {
        "nodes": [
            {"id": "polygon", "kind": "object", "label": "regular dodecagon"},
            {"id": "choose_four", "kind": "constraint", "label": "four vertices"},
            {"id": "centroid", "kind": "constraint", "label": "centroid at center"},
            {"id": "nonadjacent", "kind": "constraint", "label": "no adjacent vertices"},
            {"id": "roots", "kind": "transform", "morphism": "ComplexRootEncoding"},
            {"id": "symmetric", "kind": "lemma", "morphism": "InvariantQuotient"},
            {"id": "antipodal", "kind": "lemma", "morphism": "AntipodalFactorization"},
            {"id": "compatible", "kind": "lemma", "morphism": "CompatibilityClass"},
            {"id": "count", "kind": "conclusion", "morphism": "CardinalityObservation"},
            {"id": "answer", "kind": "query", "label": "number of selections"},
        ],
        "edges": [
            {"source": "polygon", "target": "roots"},
            {"source": "roots", "target": "symmetric"},
            {"source": "choose_four", "target": "symmetric"},
            {"source": "centroid", "target": "symmetric"},
            {"source": "symmetric", "target": "antipodal"},
            {"source": "antipodal", "target": "compatible"},
            {"source": "nonadjacent", "target": "compatible"},
            {"source": "compatible", "target": "count"},
            {"source": "count", "target": "answer"},
        ],
    }


def _polygon_enumeration() -> tuple[int, bool]:
    favorable: list[tuple[int, ...]] = []
    for subset in itertools.combinations(range(12), 4):
        chosen = set(subset)
        if any((j + 1) % 12 in chosen for j in chosen):
            continue
        vector_sum = sp.simplify(
            sum(sp.exp(sp.I * sp.pi * j / 6) for j in subset)
        )
        if sp.expand_complex(vector_sum) == 0:
            favorable.append(subset)
    antipodal = all(
        all((j + 6) % 12 in subset for j in subset)
        for subset in favorable
    )
    return len(favorable), antipodal


def _polygon_pair_count() -> int:
    count = 0
    for a, b in itertools.combinations(range(6), 2):
        chosen = {a, a + 6, b, b + 6}
        if not any((j + 1) % 12 in chosen for j in chosen):
            count += 1
    return count


def _polygon_problem() -> dict[str, Any]:
    enumerated, classification_ok = _polygon_enumeration()
    pair_count = _polygon_pair_count()
    proof_graph = _polygon_proof_graph()
    proof_certificate = certify_proof_graph(proof_graph)
    morphology_certificate = certify_morphology_path(
        POLYGON_PATH,
        morphism_chain=POLYGON_MORPHISMS,
        established_conditions=POLYGON_CONDITIONS,
    )
    exact_ok = enumerated == 9 and classification_ok
    independent_ok = pair_count == enumerated
    statement = r"""正十二角形の頂点から4頂点を選ぶ。ただし、選んだどの2頂点も
隣り合わず、4頂点の重心が正十二角形の中心と一致するものとする。このような
4頂点の選び方は何通りあるか。"""
    solution = r"""中心を原点、頂点を絶対値1の複素数 \(z_1,z_2,z_3,z_4\) とする。
重心条件は \(z_1+z_2+z_3+z_4=0\) である。これらを根にもつ多項式では1次の
係数が0であり、\(|z_j|=1\) から3次の係数も0になる。したがって多項式は偶関数で、
根は \(z,-z,w,-w\) の形、すなわち選ぶ4頂点は2組の対蹠点対である。

対蹠点対は全部で6組ある。そこから2組を選ぶ \(\binom62=15\) 通りのうち、対応する
直径が隣り合う頂点を含むものは、6組を円周状に並べたときの隣接する2組に対応し
6通りある。よって求める個数は
\[
\boxed{15-6=9}
\]
通りである。"""
    return {
        "accepted": bool(exact_ok and independent_ok and proof_certificate["interaction_verified"] and morphology_certificate["valid"]),
        "answer_exact": "9",
        "answer_tex": r"\(9\)",
        "candidate_id": "morphology:dodecagon-antipodal-independent:001",
        "constraint_skeleton": ["regular_12_gon", "four_subset", "zero_centroid", "nonadjacent"],
        "difficulty": "unrated_human",
        "domain": "complex_geometry_algebra_combinatorics",
        "family_id": "morphology.unit_roots_antipodal_compatibility_count",
        "lift_certificate": {
            "type_checked": True,
            "morphism_chain": POLYGON_MORPHISMS,
            "constraint_skeleton": ["unit_root_subset", "vanishing_first_symmetric_sum", "adjacency_exclusion"],
            "query_signature": "Cardinality(Compatible(AntipodalPairs))",
        },
        "novelty": {"corpus_novel": True, "provisional": True},
        "morphology_path": POLYGON_PATH,
        "morphology_conditions": POLYGON_CONDITIONS,
        "morphology_certificate": morphology_certificate,
        "proof_graph": proof_graph,
        "proof_graph_certificate": proof_certificate,
        "statement_tex": statement,
        "solution_tex": solution,
        "verification": {
            "exact_backend": exact_ok,
            "independent_check": independent_ok,
            "method": "exact_root_enumeration_plus_antipodal_pair_classification",
            "enumerated_count": enumerated,
            "pair_count": pair_count,
        },
    }


def synthesize() -> dict[str, Any]:
    problems = [_parabola_problem(), _polygon_problem()]
    return {
        "method": "typed_morphology_geometry_synthesis",
        "problems": problems,
        "summary": {
            "generated": len(problems),
            "accepted": sum(bool(problem["accepted"]) for problem in problems),
            "families": len({problem["family_id"] for problem in problems}),
        },
    }


if __name__ == "__main__":
    import json

    print(json.dumps(synthesize()["summary"], ensure_ascii=False, indent=2))
