"""Concept-tree problem synthesis: problems as typed composition trees.

This realises the "colored building blocks in a tree" idea. A problem is a
*typed tree* (a tree tensor network in the diagrammatic sense): leaves are
parameterised base objects, internal nodes are typed operations that combine
their children, and the root is the queried quantity. Swapping or rebranching a
node yields a different problem -- including unseen ones.

Only a numerically *certified* clean closed form survives: the engine evaluates
the whole tree bottom-up as a function of the family parameter, finds the
queried extremum, and keeps the problem only when the extreme value matches a
short exact closed form to high precision AND is attained in the interior (a
non-degenerate, "beautiful" answer). This filter is the mechanical stand-in for
"美しい結果": most trees are rejected; the survivors are the interesting ones.

Verification here is numeric certification to 1e-9, not symbolic proof. It is a
prototype of the vocabulary-as-tree generator, distinct from the
symbolically-proven parametric engine and hand-authored pool.
"""

from __future__ import annotations

import argparse
import itertools
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

import numpy as np
import sympy as sp


# ---------------------------------------------------------------------------
# Typed tree
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Node:
    op: str
    sort: str
    params: dict[str, Any] = field(default_factory=dict)
    children: tuple["Node", ...] = ()

    def signature(self) -> str:
        inner = ",".join(child.signature() for child in self.children)
        param = ",".join(f"{k}={v}" for k, v in sorted(self.params.items()))
        return f"{self.op}[{param}]({inner})"


# A base even-quartic block:  x^4 - c x^2 + t,  0<t<c^2/4  =>  roots ±u,±v.
def base(c: int) -> Node:
    return Node("EvenQuartic", "RootConfig", {"c": c})


def embed(child: Node, k: int) -> Node:
    return Node("Embed", "PointConfig", {"k": k}, (child,))


def observable(child: Node, name: str) -> Node:
    return Node(name, "ParamReal", {}, (child,))


def combine(left: Node, right: Node, name: str) -> Node:
    # A genuine branching node: two observable subtrees merge into one.
    return Node(name, "ParamReal", {}, (left, right))


def query(child: Node, kind: str) -> Node:
    return Node(kind, "Real", {}, (child,))


# ---------------------------------------------------------------------------
# Numeric evaluation of a subtree to a function of t (given c)
# ---------------------------------------------------------------------------
def _roots(c: float, t: float) -> list[float] | None:
    discriminant = c * c - 4.0 * t
    if discriminant <= 0.0:
        return None
    w = float(np.sqrt(discriminant))
    u2 = (c + w) / 2.0
    v2 = (c - w) / 2.0
    if v2 <= 0.0:
        return None
    u = float(np.sqrt(u2))
    v = float(np.sqrt(v2))
    return [-u, -v, v, u]


def _points(c: float, t: float, k: int) -> np.ndarray | None:
    real = _roots(c, t)
    if real is None:
        return None
    return np.array([[x, x**k] for x in real])


def _hull_area(points: np.ndarray) -> float:
    ctr = points.mean(axis=0)
    ang = np.arctan2(points[:, 1] - ctr[1], points[:, 0] - ctr[0])
    h = points[np.argsort(ang)]
    return 0.5 * abs(
        np.dot(h[:, 0], np.roll(h[:, 1], -1)) - np.dot(h[:, 1], np.roll(h[:, 0], -1))
    )


def _sum_sq_pair_distance(points: np.ndarray) -> float:
    total = 0.0
    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            total += float(np.sum((points[i] - points[j]) ** 2))
    return total


def _max_pair_distance(points: np.ndarray) -> float:
    best = 0.0
    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            best = max(best, float(np.sqrt(np.sum((points[i] - points[j]) ** 2))))
    return best


OBSERVABLES: dict[str, Callable[[np.ndarray], float]] = {
    "HullArea": _hull_area,
    "SumSqPairDistance": _sum_sq_pair_distance,
    "MaxPairDistance": _max_pair_distance,
}


def observable_function(node: Node) -> Callable[[float, float], float | None]:
    """Return g(c, t) for a ParamReal subtree."""

    if node.op in OBSERVABLES:
        k = node.children[0].params["k"]
        fn = OBSERVABLES[node.op]

        def g(c: float, t: float) -> float | None:
            pts = _points(c, t, k)
            return None if pts is None else fn(pts)

        return g

    if node.op in ("Difference", "Ratio"):
        left = observable_function(node.children[0])
        right = observable_function(node.children[1])

        def g(c: float, t: float) -> float | None:
            a = left(c, t)
            b = right(c, t)
            if a is None or b is None:
                return None
            if node.op == "Difference":
                return a - b
            return a / b if abs(b) > 1e-12 else None

        return g

    raise ValueError(f"not a ParamReal node: {node.op}")


# ---------------------------------------------------------------------------
# Symbolic evaluation: exact function of t, then symbolic extremum.
# Roots of x^4 - c x^2 + t are +-u, +-v with u = sqrt((c+w)/2), v = sqrt((c-w)/2),
# w = sqrt(c^2 - 4t).  Point i (canonical order [-u,-v,v,u]) maps to (r, r^k).
# ---------------------------------------------------------------------------
_T = sp.symbols("t", positive=True)


def _symbolic_roots(c: int) -> list[sp.Expr]:
    w = sp.sqrt(sp.Integer(c) ** 2 - 4 * _T)
    u = sp.sqrt((sp.Integer(c) + w) / 2)
    v = sp.sqrt((sp.Integer(c) - w) / 2)
    return [-u, -v, v, u]


def _symbolic_points(c: int, k: int) -> list[tuple[sp.Expr, sp.Expr]]:
    return [(r, r**k) for r in _symbolic_roots(c)]


def _hull_order(c: int, k: int) -> list[int] | None:
    pts = _points(float(c), c * c / 8.0, k)
    if pts is None:
        return None
    ctr = pts.mean(axis=0)
    ang = np.arctan2(pts[:, 1] - ctr[1], pts[:, 0] - ctr[0])
    return list(np.argsort(ang))


def _symbolic_shoelace(points: list[tuple[sp.Expr, sp.Expr]], order: list[int]) -> sp.Expr:
    ordered = [points[i] for i in order]
    n = len(ordered)
    signed = sum(
        ordered[i][0] * ordered[(i + 1) % n][1] - ordered[(i + 1) % n][0] * ordered[i][1]
        for i in range(n)
    )
    return sp.simplify(signed / 2)


def symbolic_paramreal(node: Node, c: int) -> sp.Expr | None:
    """Exact observable as a function of t, or None if no symbolic route."""

    if node.op == "HullArea":
        k = node.children[0].params["k"]
        order = _hull_order(c, k)
        if order is None:
            return None
        signed = _symbolic_shoelace(_symbolic_points(c, k), order)
        sample = float(sp.N(signed.subs(_T, c * c / 8.0)))
        return sp.simplify(signed if sample >= 0 else -signed)

    if node.op == "SumSqPairDistance":
        k = node.children[0].params["k"]
        pts = _symbolic_points(c, k)
        total = sum(
            (pts[i][0] - pts[j][0]) ** 2 + (pts[i][1] - pts[j][1]) ** 2
            for i in range(len(pts))
            for j in range(i + 1, len(pts))
        )
        return sp.simplify(total)

    if node.op == "Difference":
        left = symbolic_paramreal(node.children[0], c)
        right = symbolic_paramreal(node.children[1], c)
        if left is None or right is None:
            return None
        return sp.simplify(left - right)

    return None


def symbolic_extremum(expr: sp.Expr, c: int, kind: str) -> tuple[sp.Expr, sp.Expr] | None:
    """Certify an exact global extremum over 0 < t < c^2/4."""

    hi = sp.Rational(c * c, 4)
    try:
        criticals = sp.solve(sp.diff(expr, _T), _T)
    except (NotImplementedError, sp.SympifyError):
        return None
    interior = [
        cc for cc in criticals if cc.is_real and cc.is_number and 0 < cc < hi
    ]
    if not interior:
        return None
    valued = []
    for cc in interior:
        value = sp.simplify(expr.subs(_T, cc))
        if value.is_real is False:
            continue
        valued.append((value, cc))
    if not valued:
        return None
    chooser = max if kind == "Maximize" else min
    best = chooser(valued, key=lambda item: float(sp.N(item[0])))
    try:
        boundaries = (
            sp.simplify(sp.limit(expr, _T, 0, dir="+")),
            sp.simplify(sp.limit(expr, _T, hi, dir="-")),
        )
    except (NotImplementedError, ValueError, TypeError):
        return None
    finite_boundaries = [
        value for value in boundaries
        if value.is_real is not False and value.is_finite is True
    ]
    if len(finite_boundaries) != 2:
        return None
    best_numeric = float(sp.N(best[0]))
    boundary_numeric = [float(sp.N(value)) for value in finite_boundaries]
    if kind == "Maximize" and best_numeric <= max(boundary_numeric):
        return None
    if kind == "Minimize" and best_numeric >= min(boundary_numeric):
        return None
    return sp.nsimplify(sp.simplify(best[0])), best[1]


# ---------------------------------------------------------------------------
# Closed-form certification of the queried extremum
# ---------------------------------------------------------------------------
_SURD_BASES: tuple[sp.Expr, ...] = (
    sp.sqrt(2), sp.sqrt(3), sp.sqrt(5), sp.sqrt(6),
    sp.sqrt(7), sp.sqrt(10), sp.sqrt(13), sp.sqrt(15),
)
_MAX_DENOM = 64
_MAX_RADICAND = 30


def _acceptable(candidate: sp.Expr) -> bool:
    """Reject nsimplify overfits: exact, bounded denominators, small surds only."""

    if candidate.free_symbols or candidate.atoms(sp.Float):
        return False
    for rational in candidate.atoms(sp.Rational):
        if abs(int(rational.q)) > _MAX_DENOM:
            return False
    for power in candidate.atoms(sp.Pow):
        base_expr, exponent = power.as_base_exp()
        if exponent == sp.Rational(1, 2):
            if not (base_expr.is_Integer and 0 <= int(base_expr) <= _MAX_RADICAND):
                return False
        elif not exponent.is_Integer:
            return False
    return sp.count_ops(candidate) <= 9


def _closed_form(value: float, tol: float = 1e-9) -> sp.Expr | None:
    """Detect a short exact closed form matching a high-precision value.

    Pure rationals (small denominator) are tried first, then a single small
    surd extension. Candidates that need a large radicand or denominator, or
    that only match within a loose tolerance, are rejected as nsimplify
    overfits to numeric noise.
    """

    # pure rational first
    rational = sp.nsimplify(value, rational=True, tolerance=tol)
    if _acceptable(rational) and abs(float(rational) - value) < tol:
        return rational
    for surd in _SURD_BASES:
        try:
            candidate = sp.nsimplify(value, [surd], tolerance=tol, rational=False)
        except (ValueError, TypeError, sp.SympifyError):
            continue
        candidate = sp.simplify(candidate)
        if _acceptable(candidate) and abs(float(candidate) - value) < tol:
            return candidate
    return None


def evaluate(tree: Node) -> dict[str, Any] | None:
    """Evaluate a query tree: returns a certified problem dict or None."""

    if tree.sort != "Real":
        raise ValueError("top node must be a Real query")
    kind = tree.op  # Maximize / Minimize
    param_node = tree.children[0]
    obs = observable_function(param_node)
    c = _base_c(param_node)

    # Most concept trees have an exact symbolic observable.  Prove their
    # global interior extremum before invoking the bounded numeric fallback.
    try:
        expr = symbolic_paramreal(param_node, int(round(c)))
    except Exception:
        expr = None
    if expr is not None:
        extremum = symbolic_extremum(expr, int(round(c)), kind)
        if extremum is not None:
            value, point = extremum
            numeric_point = float(sp.N(point))
            numeric_value = obs(c, numeric_point)
            if (
                not value.free_symbols
                and not value.atoms(sp.Float)
                and numeric_value is not None
                and abs(float(sp.N(value)) - numeric_value) < 1e-7
            ):
                return {
                    "tree_signature": tree.signature(),
                    "answer_exact": sp.sstr(sp.simplify(value)),
                    "answer_tex": sp.latex(sp.simplify(value)),
                    "extreme_value_numeric": round(numeric_value, 10),
                    "maximizer_t_numeric": round(numeric_point, 8),
                    "query": kind,
                    "certified": True,
                    "certification": "symbolic_proof_global_extremum_with_boundary_limits",
                }

    hi = c * c / 4.0
    sign = 1.0 if kind == "Maximize" else -1.0

    def scan(lo: float, high: float, count: int) -> tuple[float, float] | None:
        best: tuple[float, float] | None = None
        for t in np.linspace(lo, high, count):
            val = obs(c, float(t))
            if val is not None and np.isfinite(val):
                score = sign * val
                if best is None or score > best[0]:
                    best = (score, float(t))
        return best

    coarse = scan(hi * 1e-4, hi * (1 - 1e-4), 1200)
    if coarse is None:
        return None
    best_t = coarse[1]

    # interior attainment: reject open-boundary (degenerate) extrema.
    if not (hi * 0.02 < best_t < hi * 0.98):
        return None

    # refine locally to ~1e-12 so closed-form detection is not fooled by grid error.
    window = hi / 1200
    for _ in range(5):
        refined = scan(max(best_t - window, hi * 1e-6), min(best_t + window, hi), 160)
        if refined is None:
            break
        best_t = refined[1]
        window /= 50
    best_val = obs(c, best_t)
    if best_val is None:
        return None

    # Prefer a symbolic proof: exact function of t, exact critical point, exact
    # value that must agree with the numeric extremum. Fall back to numeric
    # closed-form certification when no symbolic route exists.
    certification = "numeric_closed_form_match_1e-9_interior_attained"
    closed: sp.Expr | None = None
    if expr is not None:
        extremum = symbolic_extremum(expr, int(round(c)), kind)
        if extremum is not None:
            value, _ = extremum
            if not value.free_symbols and not value.atoms(sp.Float):
                if abs(float(value) - best_val) < 1e-6:
                    closed = sp.simplify(value)
                    certification = "symbolic_proof_interior_critical_point"

    if closed is None:
        closed = _closed_form(best_val)
    if closed is None:
        return None

    return {
        "tree_signature": tree.signature(),
        "answer_exact": sp.sstr(closed),
        "answer_tex": sp.latex(closed),
        "extreme_value_numeric": round(best_val, 10),
        "maximizer_t_numeric": round(best_t, 8),
        "query": kind,
        "certified": True,
        "certification": certification,
    }


def _base_c(node: Node) -> float:
    if node.op == "EvenQuartic":
        return float(node.params["c"])
    for child in node.children:
        try:
            return _base_c(child)
        except ValueError:
            continue
    raise ValueError("no base found")


# ---------------------------------------------------------------------------
# Rendering (compositional)
# ---------------------------------------------------------------------------
_EMBED_LABEL = {
    2: r"(r,r^2)", 3: r"(r,r^3)", 4: r"(r,r^4)", 5: r"(r,r^5)",
}
_OBS_LABEL = {
    "HullArea": "これら4点の凸包の面積",
    "SumSqPairDistance": "これら4点の相異なる2点間の距離の平方の総和",
    "MaxPairDistance": "これら4点のうち最も離れた2点間の距離",
}
_QUERY_LABEL = {"Maximize": "の最大値", "Minimize": "の最小値"}


def render(tree: Node) -> str | None:
    param_node = tree.children[0]
    c = int(_base_c(param_node))
    if param_node.op in OBSERVABLES:
        k = param_node.children[0].params["k"]
        obs = _OBS_LABEL.get(param_node.op)
        if obs is None:
            return None
        return (
            rf"実数 \(t\) に対し，方程式 \(x^4-{c}x^2+t=0\) が相異なる4実根を"
            rf"もつとする。各実根 \(r\) に点 \({_EMBED_LABEL[k]}\) を対応させるとき，"
            rf"{obs}{_QUERY_LABEL[tree.op]}を求めよ。"
        )
    if param_node.op == "Difference":
        left, right = param_node.children
        if left.op in OBSERVABLES and right.op in OBSERVABLES:
            k1 = left.children[0].params["k"]
            k2 = right.children[0].params["k"]
            l1 = _OBS_LABEL.get(left.op)
            l2 = _OBS_LABEL.get(right.op)
            if l1 and l2:
                return (
                    rf"実数 \(t\) に対し，方程式 \(x^4-{c}x^2+t=0\) が相異なる4実根を"
                    rf"もつとする。各実根 \(r\) に対し，点 \({_EMBED_LABEL[k1]}\) から"
                    rf"定まる「{l1}」から，点 \({_EMBED_LABEL[k2]}\) から定まる"
                    rf"「{l2}」を引いた差{_QUERY_LABEL[tree.op]}を求めよ。"
                )
    return None


# ---------------------------------------------------------------------------
# Tree enumeration
# ---------------------------------------------------------------------------
def enumerate_trees(
    c_values: tuple[int, ...] = (4, 5, 6, 7, 8, 9, 10, 12),
    exponents: tuple[int, ...] = (2, 3, 4, 5),
    observables: tuple[str, ...] = ("HullArea", "SumSqPairDistance", "MaxPairDistance"),
    queries: tuple[str, ...] = ("Maximize", "Minimize"),
    include_branching: bool = True,
) -> list[Node]:
    trees: list[Node] = []
    for c in c_values:
        b = base(c)
        for k in exponents:
            emb = embed(b, k)
            for obs in observables:
                for q in queries:
                    trees.append(query(observable(emb, obs), q))
        if include_branching:
            for k1, k2 in itertools.combinations(exponents, 2):
                left = observable(embed(b, k1), "HullArea")
                right = observable(embed(b, k2), "HullArea")
                for q in queries:
                    trees.append(query(combine(left, right, "Difference"), q))
    return trees


def synthesize(**kwargs: Any) -> dict[str, Any]:
    trees = enumerate_trees(**kwargs)
    certified: list[dict[str, Any]] = []
    seen_answers: set[tuple[str, str]] = set()
    for tree in trees:
        result = evaluate(tree)
        if result is None:
            continue
        statement = render(tree)
        if statement is None:
            continue
        key = (result["query"], result["answer_exact"])
        if key in seen_answers:
            continue
        seen_answers.add(key)
        certified.append({**result, "statement_tex": statement})
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": {
            "name": "Concept-Tree Problem Synthesis (prototype)",
            "idea": "problems as typed composition trees / tree tensor networks",
            "certification": "numeric closed-form match to 1e-9, interior extremum",
        },
        "summary": {
            "trees_explored": len(trees),
            "certified": len(certified),
        },
        "problems": certified,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=str, default="")
    args = parser.parse_args()
    report = synthesize()
    if args.output:
        from pathlib import Path

        Path(args.output).write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    print(
        json.dumps(
            {
                "summary": report["summary"],
                "sample": [
                    {
                        "tree": p["tree_signature"],
                        "answer": p["answer_exact"],
                        "statement": p["statement_tex"],
                    }
                    for p in report["problems"][:8]
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
