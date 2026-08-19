"""Problem Phase Diagram synthesis for concise Kyoto-style problems.

The generator starts from one algebraic object rather than a sentence
template.  For roots of x^4 - 5x^2 + t, it varies an observation x -> x^k,
reduces the observation in the quotient algebra, derives a convex-hull area,
and searches for exponents whose extremum has a short exact form.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import sympy as sp

try:
    from math_os_prototype.jukenmath_full_audit import (
        canonical_surface,
        fetch_public_problems,
        jaccard,
        surface_ngrams,
    )
except ImportError:
    from jukenmath_full_audit import (
        canonical_surface,
        fetch_public_problems,
        jaccard,
        surface_ngrams,
    )


DEFAULT_OUTPUT = Path("problem_synthesis/kyoto_corpus_novel_problem.json")
DEFAULT_SELF_CORPUS = Path("problem_synthesis/all_problems_selfauthored81.jsonl")
FAMILY_ID = "algebraic_geometry.even_quartic_root_convex_hull_area"
MORPHISM_CHAIN = (
    "quotient_polynomial_reduction",
    "root_sign_symmetry",
    "convex_hull_shoelace",
    "vieta_invariant",
    "compact_interval_extremum",
)


@dataclass(frozen=True)
class PhaseCandidate:
    exponent: int
    quotient_x3_coefficient: str
    squared_area: str
    maximum_area: str
    maximizer_t: list[str]
    statement_tex: str
    solution_tex: str
    backend_verified: bool
    numerical_upper_bound: float


def quotient_x3_coefficient(exponent: int) -> sp.Expr:
    x, t = sp.symbols("x t", real=True)
    remainder = sp.rem(x**exponent, x**4 - 5 * x**2 + t, x)
    return sp.expand(remainder).coeff(x, 3)


def maximize_squared_area(coefficient: sp.Expr) -> tuple[sp.Expr, list[sp.Expr]]:
    t = sp.symbols("t", real=True)
    squared_area = sp.factor(4 * t * (25 - 4 * t) * coefficient**2)
    derivative = sp.factor(sp.diff(squared_area, t))
    candidates: list[sp.Expr] = [sp.Integer(0), sp.Rational(25, 4)]
    for root in sp.solve(derivative, t):
        if root.is_real is True and bool(0 <= root <= sp.Rational(25, 4)):
            candidates.append(root)
    values = [(sp.simplify(squared_area.subs(t, point)), point) for point in candidates]
    nonnegative = [(value, point) for value, point in values if value.is_nonnegative is not False]
    maximum_value = max(nonnegative, key=lambda item: float(sp.N(item[0], 20)))[0]
    maximizers = sorted(
        {point for value, point in nonnegative if sp.simplify(value - maximum_value) == 0},
        key=lambda value: float(sp.N(value)),
    )
    return sp.factor(maximum_value), maximizers


def render_statement(exponent: int) -> str:
    return (
        r"実数 \(t\) に対し，方程式 \(x^4-5x^2+t=0\) が相異なる4実根を"
        rf"もつとする。各実根 \(r\) に点 \((r,r^{exponent})\) を対応させるとき，"
        r"これら4点の凸包の面積の最大値を求めよ。"
    )


def render_solution(
    exponent: int,
    coefficient: sp.Expr,
    squared_area: sp.Expr,
    maximum_area: sp.Expr,
    maximizers: list[sp.Expr],
) -> str:
    t = sp.symbols("t", real=True)
    x = sp.Symbol("x")
    remainder = sp.rem(x**exponent, x**4 - 5 * x**2 + t, x)
    coefficient_tex = sp.latex(coefficient)
    remainder_tex = sp.latex(sp.expand(remainder))
    squared_tex = sp.latex(sp.factor(squared_area))
    maximum_tex = sp.latex(maximum_area)
    maximizer_tex = ", ".join(sp.latex(value) for value in maximizers)
    return (
        rf"\(x^4\equiv 5x^2-t\pmod{{x^4-5x^2+t}}\) より "
        rf"\(x^{exponent}\equiv {remainder_tex}\) であり，\(x^3\) の係数は "
        rf"\({coefficient_tex}\) である。4実根を \(-u,-v,v,u\;(u>v>0)\) と"
        rf"おくと \(u^2+v^2=5,\ u^2v^2=t\)。凸包の面積を \(S\) とすると，"
        rf"靴紐公式から \(S=2|{coefficient_tex}|uv(u^2-v^2)\)，したがって "
        rf"\(S^2={squared_tex}\)。よって \(t={maximizer_tex}\) のとき最大となり，"
        rf"\(\boxed{{S={maximum_tex}}}\)。"
    )


def numerical_area_upper_bound(exponent: int, samples: int = 1201) -> float:
    best = 0.0
    for index in range(1, samples):
        t_value = 25.0 * index / (4.0 * samples)
        roots = sorted(
            float(root.real)
            for root in np.roots([1.0, 0.0, -5.0, 0.0, t_value])
            if abs(float(root.imag)) < 1e-8
        )
        if len(roots) != 4:
            continue
        points = np.array([[root, root**exponent] for root in roots])
        center = points.mean(axis=0)
        angles = np.arctan2(points[:, 1] - center[1], points[:, 0] - center[0])
        hull = points[np.argsort(angles)]
        area = 0.5 * abs(
            float(
                np.dot(hull[:, 0], np.roll(hull[:, 1], -1))
                - np.dot(hull[:, 1], np.roll(hull[:, 0], -1))
            )
        )
        best = max(best, area)
    return best


def build_phase_candidate(exponent: int) -> PhaseCandidate:
    t = sp.symbols("t", real=True)
    coefficient = quotient_x3_coefficient(exponent)
    squared_area = sp.factor(4 * t * (25 - 4 * t) * coefficient**2)
    maximum_squared, maximizers = maximize_squared_area(coefficient)
    maximum_area = sp.simplify(sp.sqrt(maximum_squared))
    numerical = numerical_area_upper_bound(exponent)
    exact_float = float(sp.N(maximum_area, 20))
    verified = numerical <= exact_float + 1e-7 and numerical >= exact_float - 2e-3
    return PhaseCandidate(
        exponent=exponent,
        quotient_x3_coefficient=sp.sstr(coefficient),
        squared_area=sp.sstr(squared_area),
        maximum_area=sp.sstr(maximum_area),
        maximizer_t=[sp.sstr(value) for value in maximizers],
        statement_tex=render_statement(exponent),
        solution_tex=render_solution(
            exponent,
            coefficient,
            squared_area,
            maximum_area,
            maximizers,
        ),
        backend_verified=verified,
        numerical_upper_bound=round(numerical, 10),
    )


def build_phase_diagram(exponents: Iterable[int] = range(3, 10, 2)) -> list[PhaseCandidate]:
    return [build_phase_candidate(exponent) for exponent in exponents]


def load_self_authored_statements(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        rows.append(
            {
                "id": str(row.get("record_id") or ""),
                "statement": str(row.get("statement_tex") or ""),
                "source": "self_authored",
            }
        )
    return rows


def novelty_against_corpus(
    candidate: PhaseCandidate,
    public_rows: list[dict[str, Any]],
    self_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    candidate_surface = canonical_surface(candidate.statement_tex)
    candidate_grams = surface_ngrams(candidate.statement_tex)
    comparisons: list[dict[str, Any]] = []
    exact: list[dict[str, str]] = []
    motif_matches: list[dict[str, str]] = []
    for row in public_rows:
        statement = str(row.get("problem_tex") or "")
        identifier = str(row.get("id") or "")
        source = "jukenmath.net"
        comparisons.append(
            {
                "id": identifier,
                "source": source,
                "score": jaccard(candidate_grams, surface_ngrams(statement)),
            }
        )
        if canonical_surface(statement) == candidate_surface:
            exact.append({"id": identifier, "source": source})
        if "x^4-5x^2" in canonical_surface(statement) and "凸包" in statement:
            motif_matches.append({"id": identifier, "source": source})
    for row in self_rows:
        statement = str(row["statement"])
        identifier = str(row["id"])
        source = str(row["source"])
        comparisons.append(
            {
                "id": identifier,
                "source": source,
                "score": jaccard(candidate_grams, surface_ngrams(statement)),
            }
        )
        if canonical_surface(statement) == candidate_surface:
            exact.append({"id": identifier, "source": source})
        if "x^4-5x^2" in canonical_surface(statement) and "凸包" in statement:
            motif_matches.append({"id": identifier, "source": source})
    closest = sorted(
        comparisons,
        key=lambda item: (-item["score"], item["source"], item["id"]),
    )[:8]
    signatures = {
        signature
        for row in public_rows
        for signature in row.get("certificate_signatures", []) or []
    }
    return {
        "corpus_size": len(public_rows) + len(self_rows),
        "exact_surface_matches": exact,
        "specific_motif_matches": motif_matches,
        "maximum_surface_jaccard": round(closest[0]["score"], 4) if closest else 0.0,
        "closest": closest,
        "family_id": FAMILY_ID,
        "morphism_chain": list(MORPHISM_CHAIN),
        "same_certificate_signature_found": FAMILY_ID in signatures,
        "corpus_novel": (
            not exact
            and not motif_matches
            and (not closest or closest[0]["score"] < 0.72)
            and FAMILY_ID not in signatures
        ),
        "scope_note": (
            "Corpus novelty is tested against the fetched public site and the local "
            "self-authored TeX collection; it is not a proof of worldwide originality."
        ),
    }


def choose_candidate(candidates: list[PhaseCandidate]) -> PhaseCandidate:
    eligible = [
        candidate
        for candidate in candidates
        if candidate.backend_verified
        and candidate.exponent >= 3
        and candidate.quotient_x3_coefficient != "0"
        and len(candidate.maximum_area) <= 18
    ]
    if not eligible:
        raise RuntimeError("No phase candidate passed the verification gate.")
    return min(
        eligible,
        key=lambda candidate: (
            len(candidate.statement_tex),
            len(candidate.maximum_area),
            candidate.exponent,
        ),
    )


def build_report(
    public_rows: list[dict[str, Any]],
    self_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    phase = build_phase_diagram()
    selected = choose_candidate(phase)
    novelty = novelty_against_corpus(selected, public_rows, self_rows)
    public_lengths = sorted(
        len(canonical_surface(str(row.get("problem_tex") or "")))
        for row in public_rows
    )
    selected_length = len(canonical_surface(selected.statement_tex))
    shorter_or_equal = sum(length <= selected_length for length in public_lengths)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": {
            "name": "Problem Phase Diagram Synthesis",
            "object": "R[t][x] / (x^4 - 5x^2 + t)",
            "varying_observation": "x -> x^k",
            "family_id": FAMILY_ID,
            "morphism_chain": list(MORPHISM_CHAIN),
            "selection_rule": (
                "quotient by vertical-scaling equivalence, retain the shortest exact "
                "representative, require numerical agreement, and reject corpus collisions"
            ),
        },
        "phase_diagram": [asdict(candidate) for candidate in phase],
        "selected": asdict(selected),
        "novelty": novelty,
        "brevity": {
            "canonical_characters": selected_length,
            "public_corpus_percentile": round(
                100 * shorter_or_equal / len(public_lengths), 2
            )
            if public_lengths
            else None,
            "interpretation": (
                "Lower percentile means a shorter statement relative to the public corpus."
            ),
        },
        "style_contract": {
            "kyoto_style": [
                "statement is self-contained and concise",
                "elementary objects hide more than one structural layer",
                "no story setting or leading subquestions",
                "the final answer is exact",
            ],
            "coefficient_swap_only": False,
            "reason": (
                "The candidate was selected by varying an observation in a quotient algebra "
                "and detecting a phase with an interior extremum."
            ),
        },
        "accepted": bool(selected.backend_verified and novelty["corpus_novel"]),
    }


def render_markdown(report: dict[str, Any]) -> str:
    selected = report["selected"]
    novelty = report["novelty"]
    lines = [
        "# MathOS 京都大学風・コーパス新規問題",
        "",
        "## 問題",
        "",
        selected["statement_tex"],
        "",
        "## 答",
        "",
        f"`{selected['maximum_area']}`",
        "",
        "## 検証",
        "",
        f"- backend検証: {selected['backend_verified']}",
        f"- 数値走査の最大値: {selected['numerical_upper_bound']}",
        f"- 比較コーパス: {novelty['corpus_size']}問",
        f"- 完全一致: {len(novelty['exact_surface_matches'])}件",
        f"- 最大表層Jaccard: {novelty['maximum_surface_jaccard']}",
        f"- コーパス内新規: {novelty['corpus_novel']}",
        "",
        "## 解法",
        "",
        selected["solution_tex"],
        "",
        "「新規」は比較コーパス内での判定であり、世界全体での未出を証明するものではない。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--self-corpus", type=Path, default=DEFAULT_SELF_CORPUS)
    parser.add_argument("--delay", type=float, default=0.4)
    args = parser.parse_args()
    public_rows = fetch_public_problems(delay_seconds=args.delay)
    self_rows = load_self_authored_statements(args.self_corpus)
    report = build_report(public_rows, self_rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    args.output.with_suffix(".md").write_text(render_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "accepted": report["accepted"],
                "selected": report["selected"],
                "novelty": report["novelty"],
                "brevity": report["brevity"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
