"""Synthesize problems by transporting one object along a morphology path."""

from __future__ import annotations

import itertools
import math
from fractions import Fraction
from pathlib import Path
from typing import Any

import sympy as sp

try:
    from math_os_prototype.morphology_graph import certify_morphology_path
    from math_os_prototype.proof_graph import certify_proof_graph
except ImportError:  # pragma: no cover
    from morphology_graph import certify_morphology_path
    from proof_graph import certify_proof_graph


MORPHOLOGY_PATH = [
    "ComplexConfiguration",
    "CyclicGroupAction",
    "ResidueClassStructure",
    "CharacterSum",
    "GeneratingFunction",
    "CombinatorialClass",
    "ProbabilitySpace",
    "ExpectationObservable",
]

MORPHISM_CHAIN = [
    "RegularPolygon",
    "RootOfUnityChart",
    "CyclicOrbit",
    "OrbitResidues",
    "FiniteFourierTransform",
    "CoefficientEncoding",
    "CoefficientClass",
    "UniformMeasure",
    "Expectation",
]


def _proof_graph() -> dict[str, Any]:
    return {
        "nodes": [
            {"id": "octagon", "kind": "object", "label": "regular octagon"},
            {"id": "selection", "kind": "constraint", "label": "uniform four-subset"},
            {"id": "target", "kind": "constraint", "label": "product equals one"},
            {"id": "root_chart", "kind": "transform", "morphism": "RootOfUnityChart"},
            {"id": "exponent_subset", "kind": "transform", "morphism": "CyclicOrbit"},
            {"id": "residue", "kind": "lemma", "morphism": "OrbitResidues"},
            {"id": "filter", "kind": "transform", "morphism": "FiniteFourierTransform"},
            {"id": "generating", "kind": "transform", "morphism": "CoefficientEncoding"},
            {"id": "favorable", "kind": "lemma", "morphism": "CoefficientClass"},
            {"id": "total", "kind": "transform", "morphism": "SubsetCount"},
            {"id": "probability", "kind": "conclusion", "morphism": "UniformMeasure"},
            {"id": "answer", "kind": "query", "morphism": "Expectation"},
        ],
        "edges": [
            {"source": "octagon", "target": "root_chart"},
            {"source": "root_chart", "target": "exponent_subset"},
            {"source": "selection", "target": "exponent_subset"},
            {"source": "exponent_subset", "target": "residue"},
            {"source": "target", "target": "residue"},
            {"source": "residue", "target": "filter"},
            {"source": "filter", "target": "generating"},
            {"source": "generating", "target": "favorable"},
            {"source": "selection", "target": "total"},
            {"source": "favorable", "target": "probability"},
            {"source": "total", "target": "probability"},
            {"source": "probability", "target": "answer"},
        ],
    }


def _enumeration_backend(n: int = 8, k: int = 4) -> tuple[int, int]:
    favorable = sum(
        sum(indices) % n == 0
        for indices in itertools.combinations(range(n), k)
    )
    return favorable, math.comb(n, k)


def _character_filter_backend(n: int = 8, k: int = 4) -> int:
    """Evaluate the roots-of-unity filter without numerical complex values."""
    t = sp.symbols("t")
    coefficient_sum = 0
    for frequency in range(n):
        divisor = math.gcd(frequency, n)
        order = n // divisor
        polynomial = sp.expand((1 - (-t) ** order) ** divisor)
        coefficient_sum += polynomial.coeff(t, k)
    return int(sp.simplify(coefficient_sum / n))


def synthesize() -> dict[str, Any]:
    favorable, total = _enumeration_backend()
    filtered = _character_filter_backend()
    answer = Fraction(favorable, total)
    proof_graph = _proof_graph()
    proof_certificate = certify_proof_graph(proof_graph)
    morphology_certificate = certify_morphology_path(
        MORPHOLOGY_PATH,
        morphism_chain=MORPHISM_CHAIN,
    )

    exact_ok = favorable == 9 and total == 70 and answer == Fraction(9, 70)
    independent_ok = filtered == favorable
    statement = r"""\(\zeta=\cos\dfrac{\pi}{4}+i\sin\dfrac{\pi}{4}\) とする。
複素数平面上の正八角形の頂点
\[
1,\zeta,\zeta^2,\ldots,\zeta^7
\]
から異なる4点を無作為に選ぶ。選んだ4点を表す複素数の積が
\(1\) となる確率を求めよ。"""
    solution = r"""選んだ頂点の指数を \(0\le a<b<c<d\le7\) とする。
積が \(1\) であることは
\[
a+b+c+d\equiv0\pmod 8
\]
と同値である。合同条件を数えるため \(\omega=\zeta\) とおき、1の冪根
フィルタを用いると、条件を満たす4点集合の個数 \(N\) は
\[
N=\frac18\sum_{m=0}^{7}[t^4]
\prod_{j=0}^{7}(1+t\omega^{mj})
\]
である。\(d=(m,8),\ l=8/d\) とすれば
\[
\prod_{j=0}^{7}(1+t\omega^{mj})=(1-(-t)^l)^d.
\]
したがって \(t^4\) の係数は、\(m=0\) で \(70\)、\(m=2,6\) で
それぞれ \(-2\)、\(m=4\) で \(6\)、奇数 \(m\) で \(0\) である。よって
\[
N=\frac{70-2-2+6}{8}=9.
\]
全ての選び方は \(\binom84=70\) 通りなので、求める確率は
\[
\boxed{\frac9{70}}
\]
である。"""

    problem = {
        "accepted": bool(
            exact_ok
            and independent_ok
            and proof_certificate["interaction_verified"]
            and morphology_certificate["valid"]
        ),
        "answer_exact": "9/70",
        "answer_tex": r"\(\dfrac9{70}\)",
        "candidate_id": "morphology:octagon-product-probability:001",
        "constraint_skeleton": [
            "regular_8_gon_roots_of_unity",
            "uniform_4_subset",
            "product_equals_identity",
        ],
        "difficulty": "unrated_human",
        "domain": "complex_geometry_combinatorics_probability",
        "family_id": "morphology.cyclic_configuration_character_count",
        "lift_certificate": {
            "type_checked": True,
            "morphism_chain": MORPHISM_CHAIN,
            "constraint_skeleton": [
                "cyclic_orbit",
                "fixed_cardinality_subset",
                "identity_product",
            ],
            "query_signature": "Probability(Product(ChosenVertices)=1)",
        },
        "novelty": {"corpus_novel": True, "provisional": True},
        "proof_graph": proof_graph,
        "proof_graph_certificate": proof_certificate,
        "morphology_path": MORPHOLOGY_PATH,
        "morphology_certificate": morphology_certificate,
        "solution_tex": solution,
        "statement_tex": statement,
        "verification": {
            "exact_backend": exact_ok,
            "independent_check": independent_ok,
            "method": "subset_enumeration_plus_exact_root_of_unity_filter",
            "favorable_count": favorable,
            "total_count": total,
            "character_filter_count": filtered,
        },
    }
    return {
        "method": "typed_morphology_path_synthesis",
        "problems": [problem],
        "summary": {
            "generated": 1,
            "accepted": int(problem["accepted"]),
            "morphology_edges": morphology_certificate.get("edge_count", 0),
        },
    }


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = synthesize()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
