"""Generate verified hard candidates from proof motifs, not surface templates."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import sympy as sp

try:
    from math_os_prototype.category_semantics import compile_typed_semantic_graph
    from math_os_prototype.morphology_graph import certify_morphology_path
    from math_os_prototype.proof_graph import certify_proof_graph
except ImportError:  # pragma: no cover
    from category_semantics import compile_typed_semantic_graph
    from morphology_graph import certify_morphology_path
    from proof_graph import certify_proof_graph


MORPHISM_CHAIN = [
    "UniformLatticePair",
    "CoefficientInstantiation",
    "QuadraticDiscriminant",
    "DiscriminantFilter",
    "LatticeRescaling",
    "ScalingLimit",
    "RegionLimit",
    "RegionMeasure",
    "AreaObservation",
    "RootDifference",
    "RestrictedMoment",
    "RestrictedAverage",
]

# Operations expected to be recoverable directly from the Japanese/TeX
# surface. Atlas-edge morphisms above are checked separately against the
# explicit morphology path; they need not occur as literal surface words.
SURFACE_MORPHISM_CHAIN = [
    "UniformLatticePair",
    "QuadraticDiscriminant",
    "LatticeRescaling",
    "RegionLimit",
    "AreaObservation",
    "RootDifference",
    "RestrictedAverage",
]

MORPHOLOGY_PATH = [
    "QuadraticCoefficientFamily",
    "CoefficientLattice",
    "DiscriminantFeasibleLattice",
    "SemialgebraicRegion",
    "MeasureObservable",
    "ConditionalMomentObservable",
]


def _proof_graph() -> dict[str, Any]:
    return {
        "nodes": [
            {"id": "grid", "kind": "object", "label": "finite lattice of coefficient pairs"},
            {"id": "quadratic", "kind": "object", "label": "quadratic family and its roots"},
            {"id": "rescale", "kind": "transform", "morphism": "LatticeRescaling"},
            {"id": "disc", "kind": "transform", "morphism": "QuadraticDiscriminant"},
            {"id": "region", "kind": "lemma", "morphism": "RegionLimit"},
            {"id": "area", "kind": "transform", "morphism": "AreaObservation"},
            {"id": "gap", "kind": "transform", "morphism": "RootDifference"},
            {"id": "average", "kind": "lemma", "morphism": "RestrictedAverage"},
            {"id": "q1", "kind": "query", "label": "limiting proportion"},
            {"id": "q2", "kind": "query", "label": "limiting restricted average"},
        ],
        "edges": [
            {"source": "grid", "target": "rescale"},
            {"source": "quadratic", "target": "disc"},
            {"source": "rescale", "target": "region"},
            {"source": "disc", "target": "region"},
            {"source": "region", "target": "area"},
            {"source": "area", "target": "q1"},
            {"source": "quadratic", "target": "gap"},
            {"source": "gap", "target": "average"},
            {"source": "region", "target": "average"},
            {"source": "average", "target": "q2"},
        ],
    }


def _exact_backend() -> tuple[sp.Expr, sp.Expr]:
    x, y = sp.symbols("x y", nonnegative=True)
    area = sp.integrate(x**2 / 4, (x, 0, 1))
    first_moment = sp.integrate(
        sp.integrate(sp.sqrt(x**2 - 4 * y), (y, 0, x**2 / 4)),
        (x, 0, 1),
    )
    return sp.simplify(area), sp.simplify(first_moment / area)


def _finite_check(n: int = 1000) -> dict[str, float]:
    count = 0
    gap_sum = 0.0
    for a in range(1, n + 1):
        upper = a * a // (4 * n)
        for b in range(1, upper + 1):
            count += 1
            gap_sum += math.sqrt((a / n) ** 2 - 4 * b / n)
    return {
        "n": float(n),
        "proportion": count / (n * n),
        "restricted_average": gap_sum / count,
    }


def _semantic_chain_check(statement: str, solution: str) -> dict[str, Any]:
    statement_graph = compile_typed_semantic_graph(statement)
    solution_graph = compile_typed_semantic_graph(solution)
    observed = {
        item.name
        for graph in (statement_graph, solution_graph)
        for item in graph.morphisms
    }
    missing = [name for name in SURFACE_MORPHISM_CHAIN if name not in observed]
    return {
        "passed": not missing and statement_graph.status == "type_checked",
        "expected": SURFACE_MORPHISM_CHAIN,
        "observed": sorted(observed),
        "missing": missing,
        "statement_status": statement_graph.status,
        "solution_status": solution_graph.status,
    }


def synthesize() -> dict[str, Any]:
    area, average = _exact_backend()
    finite = _finite_check()
    proof_graph = _proof_graph()
    certificate = certify_proof_graph(proof_graph)
    morphology_certificate = certify_morphology_path(
        MORPHOLOGY_PATH,
        morphism_chain=MORPHISM_CHAIN,
    )
    exact_ok = area == sp.Rational(1, 12) and average == sp.Rational(1, 2)
    independent_ok = (
        abs(finite["proportion"] - 1 / 12) < 5e-4
        and abs(finite["restricted_average"] - 1 / 2) < 5e-4
    )
    statement = r"""正の整数 \(n\) に対し，
\[
S_n=\left\{(a,b)\in\{1,2,\ldots,n\}^2\ \middle|\
x^2-\frac{a}{\sqrt n}x+b=0\text{ が実数解をもつ}\right\}
\]
とする。また \((a,b)\in S_n\) に対応する二解を
\(\alpha_{a,b},\beta_{a,b}\) とし，
\[
M_n=\frac1{|S_n|}\sum_{(a,b)\in S_n}
\frac{|\alpha_{a,b}-\beta_{a,b}|}{\sqrt n}
\]
とおく。次の極限を求めよ。
\[
\text{(1) }\lim_{n\to\infty}\frac{|S_n|}{n^2},
\qquad
\text{(2) }\lim_{n\to\infty}M_n.
\]"""
    solution = r"""判別式より \((a,b)\in S_n\) は \(a^2\ge4bn\) と同値である。
\(u=a/n,\ v=b/n\) とおくと，格子点は領域
\(D=\{(u,v)\mid0\le u\le1,\ 0\le v\le u^2/4\}\) を近似する。したがって
\[
\lim_{n\to\infty}\frac{|S_n|}{n^2}
=\iint_Ddu\,dv=\int_0^1\frac{u^2}{4}\,du=\frac1{12}.
\]
また二解の差は判別式の平方根だから
\[
\frac{|\alpha_{a,b}-\beta_{a,b}|}{\sqrt n}
=\sqrt{u^2-4v}.
\]
よってリーマン和により
\[
\lim_{n\to\infty}M_n
=\frac{\displaystyle\int_0^1\int_0^{u^2/4}\sqrt{u^2-4v}\,dv\,du}
{\displaystyle\int_0^1u^2/4\,du}
=\frac{1/24}{1/12}=\frac12.
\]"""
    semantic_check = _semantic_chain_check(statement, solution)
    problem = {
        "accepted": bool(
            exact_ok
            and independent_ok
            and certificate["interaction_verified"]
            and morphology_certificate["valid"]
            and semantic_check["passed"]
        ),
        "answer_exact": ["1/12", "1/2"],
        "answer_tex": r"\(\dfrac1{12},\ \dfrac12\)",
        "candidate_id": "motif:quadratic-root-lattice-limit:001",
        "constraint_skeleton": [
            "1<=a,b<=n",
            "discriminant>=0",
            "n->infinity",
        ],
        "difficulty": "unrated_human",
        "domain": "probability_algebra_analysis",
        "family_id": "motif.quadratic_root_lattice_limit",
        "lift_certificate": {
            "type_checked": True,
            "morphism_chain": MORPHISM_CHAIN,
            "constraint_skeleton": ["finite_grid", "real_root_event", "scaling_limit"],
            "query_signature": "Pair(Limit(Probability),Limit(RestrictedAverage))",
        },
        "novelty": {"corpus_novel": True, "provisional": True},
        "proof_graph": proof_graph,
        "proof_graph_certificate": certificate,
        "morphology_path": MORPHOLOGY_PATH,
        "morphology_certificate": morphology_certificate,
        "solution_tex": solution,
        "statement_tex": statement,
        "verification": {
            "exact_backend": exact_ok,
            "independent_check": independent_ok,
            "method": "symbolic_double_integral_plus_finite_lattice_check",
            "finite_check": finite,
            "semantic_chain_check": semantic_check,
        },
    }
    return {
        "method": "selfauthored_proof_motif_guided_synthesis",
        "problems": [problem],
        "summary": {
            "generated": 1,
            "accepted": int(problem["accepted"]),
            "interaction_verified": int(certificate["interaction_verified"]),
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
