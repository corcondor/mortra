"""Problem Phase Diagram Synthesis for MathOS.

Phase 0 focuses on one deliberately narrow family:

    a_n = integral_1^n log(floor(alpha*x + beta) + gamma) dx,
    ask limit exp(a_n/n) / n^p.

The point is not to "generate text" directly.  The point is to generate a
parameterized mathematical object, solve/probe it, classify the parameter
region, and surface good problem candidates plus repair suggestions.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable


DEFAULT_OUTPUT_DIR = Path("C:/Users/81808/.openclaw/workspace/math_os_prototype/problem_synthesis")


@dataclass(frozen=True)
class ProblemFamily:
    name: str
    theme: str
    description: str
    invariant: str


@dataclass(frozen=True)
class CandidateProblem:
    candidate_id: str
    alpha: Fraction
    beta: Fraction
    gamma: int
    p: Fraction
    lower: Fraction = Fraction(1, 1)

    def min_floor_argument(self) -> int:
        return floor_fraction(self.alpha * self.lower + self.beta) + self.gamma

    def expression_text(self) -> str:
        return f"floor({fraction_plain(self.alpha)}*x + {self.beta}) + {self.gamma}"

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "alpha": fraction_plain(self.alpha),
            "beta": fraction_plain(self.beta),
            "gamma": self.gamma,
            "p": fraction_plain(self.p),
            "lower": fraction_plain(self.lower),
            "expression": self.expression_text(),
        }

    def with_patch(self, patch: dict[str, Any], *, suffix: str) -> "CandidateProblem":
        return CandidateProblem(
            candidate_id=f"{self.candidate_id}-{suffix}",
            alpha=parse_fraction(str(patch.get("alpha", fraction_plain(self.alpha)))),
            beta=parse_fraction(str(patch.get("beta", fraction_plain(self.beta)))),
            gamma=int(patch.get("gamma", self.gamma)),
            p=parse_fraction(str(patch.get("p", fraction_plain(self.p)))),
            lower=parse_fraction(str(patch.get("lower", fraction_plain(self.lower)))),
        )


@dataclass(frozen=True)
class GeometrySweepCandidate:
    candidate_id: str
    task: str
    a: int
    b: int
    c: int
    d: int
    parameter: str = "t"

    def equation_expr(self) -> str:
        return format_polynomial_terms(
            [
                (self.a, f"{self.parameter}*x"),
                (self.b, f"{self.parameter}**2"),
                (self.c, "x"),
                (self.d, ""),
            ],
            tex=False,
        )

    def equation_tex(self) -> str:
        return format_polynomial_terms(
            [
                (self.a, f"{self.parameter}x"),
                (self.b, f"{self.parameter}^2"),
                (self.c, "x"),
                (self.d, ""),
            ],
            tex=True,
        )

    def dsl_source(self) -> str:
        domain = "R"
        return f"task {self.task}; family y = {self.equation_expr()}; param {self.parameter} in {domain}"

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "task": self.task,
            "a": self.a,
            "b": self.b,
            "c": self.c,
            "d": self.d,
            "parameter": self.parameter,
            "family": f"y = {self.equation_expr()}",
            "dsl": self.dsl_source(),
        }

    def with_patch(self, patch: dict[str, Any], *, suffix: str) -> "GeometrySweepCandidate":
        return GeometrySweepCandidate(
            candidate_id=f"{self.candidate_id}-{suffix}",
            task=str(patch.get("task", self.task)),
            a=int(patch.get("a", self.a)),
            b=int(patch.get("b", self.b)),
            c=int(patch.get("c", self.c)),
            d=int(patch.get("d", self.d)),
            parameter=str(patch.get("parameter", self.parameter)),
        )


@dataclass
class RepairAction:
    kind: str
    description: str
    patch: dict[str, Any] = field(default_factory=dict)


@dataclass
class SolverTrace:
    status: str
    asymptotic_law: str
    predicted_limit: str
    proof_sketch: list[str]
    numeric_samples: list[dict[str, Any]]
    warnings: list[str] = field(default_factory=list)


@dataclass
class EvaluationResult:
    candidate: dict[str, Any]
    labels: list[str]
    phase: str
    solved: bool
    closed_form: bool
    degenerate: bool
    nontrivial: bool
    finite_answer: bool
    answer: str
    answer_tex: str
    problem_tex: str
    estimated_difficulty: dict[str, Any]
    score: float
    component_scores: dict[str, float]
    solver_trace: dict[str, Any]
    repair_actions: list[dict[str, Any]]


@dataclass
class PhaseDiagram:
    family: dict[str, Any]
    generated_at: str
    total_candidates: int
    phase_counts: dict[str, int]
    label_counts: dict[str, int]
    top_candidates: list[dict[str, Any]]
    results: list[dict[str, Any]]


@dataclass
class RepairStep:
    step_index: int
    action: dict[str, Any]
    before: dict[str, Any]
    after: dict[str, Any]


@dataclass
class RepairTrace:
    original: dict[str, Any]
    final: dict[str, Any]
    successful: bool
    steps: list[dict[str, Any]]


FLOOR_LOG_FAMILY = ProblemFamily(
    name="floor_log_integral_limit",
    theme="floor / integral / asymptotic limit",
    description=(
        "Generate floor-function integral limit problems and classify the "
        "parameter phase into invalid, divergent, vanishing, and finite closed-form regions."
    ),
    invariant=(
        "For alpha>0 and floor(alpha*x+beta)+gamma positive on [1,infty), "
        "integral_1^n log(floor(alpha*x+beta)+gamma) dx = "
        "n log n + n(log(alpha)-1) + O(log n)."
    ),
)


GEOMETRY_SWEEP_FAMILY = ProblemFamily(
    name="quadratic_sweep_region_envelope",
    theme="passing region / envelope / parameter elimination",
    description=(
        "Generate curve families y = a*t*x + b*t^2 + c*x + d, then ask either "
        "for the passing region or the envelope.  The same generated object is "
        "sent to the existing Geometry DSL backend."
    ),
    invariant=(
        "For b != 0, eliminating the real parameter t from y = a*t*x + b*t^2 + c*x + d "
        "gives a quadratic boundary.  Region queries use exists t in R; envelope "
        "queries use resultant(F, dF/dt)."
    ),
)


def format_polynomial_terms(terms: list[tuple[int, str]], *, tex: bool) -> str:
    rendered: list[str] = []
    for coefficient, body in terms:
        if coefficient == 0:
            continue
        magnitude = abs(coefficient)
        if body:
            if tex:
                core = body if magnitude == 1 else f"{magnitude}{body}"
            else:
                core = body if magnitude == 1 else f"{magnitude}*{body}"
        else:
            core = str(magnitude)
        if not rendered:
            rendered.append(f"-{core}" if coefficient < 0 else core)
        else:
            rendered.append(f" - {core}" if coefficient < 0 else f" + {core}")
    return "".join(rendered) if rendered else "0"


def floor_fraction(value: Fraction) -> int:
    return value.numerator // value.denominator


def fraction_plain(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def fraction_tex(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    if value.numerator < 0:
        return f"-\\frac{{{abs(value.numerator)}}}{{{value.denominator}}}"
    return f"\\frac{{{value.numerator}}}{{{value.denominator}}}"


def signed_fraction_tex(value: Fraction) -> str:
    if value == 0:
        return ""
    if value > 0:
        return f"+{fraction_tex(value)}"
    return fraction_tex(value)


def floor_linear_tex(candidate: CandidateProblem) -> str:
    alpha = "" if candidate.alpha == 1 else fraction_tex(candidate.alpha)
    if alpha and candidate.alpha.denominator != 1:
        alpha_part = f"{alpha}x"
    elif alpha:
        alpha_part = f"{alpha}x"
    else:
        alpha_part = "x"
    beta = signed_fraction_tex(candidate.beta)
    inside = f"{alpha_part}{beta}"
    gamma = signed_fraction_tex(Fraction(candidate.gamma, 1))
    return f"\\lfloor {inside}\\rfloor{gamma}"


def answer_for(candidate: CandidateProblem) -> tuple[str, str, str]:
    if candidate.p < 1:
        return "infinity", "\\infty", "divergent"
    if candidate.p > 1:
        return "0", "0", "vanishing"
    if candidate.alpha.denominator == 1:
        if candidate.alpha.numerator == 1:
            return "1/e", "\\frac{1}{e}", "finite_closed"
        return f"{candidate.alpha.numerator}/e", f"\\frac{{{candidate.alpha.numerator}}}{{e}}", "finite_closed"
    return (
        f"{candidate.alpha.numerator}/({candidate.alpha.denominator}e)",
        f"\\frac{{{candidate.alpha.numerator}}}{{{candidate.alpha.denominator}e}}",
        "finite_closed",
    )


def render_problem_tex(candidate: CandidateProblem) -> str:
    p_tex = "" if candidate.p == 1 else f"^{{{fraction_tex(candidate.p)}}}"
    body = floor_linear_tex(candidate)
    return (
        "以下，$\\lfloor x\\rfloor$で$x$以下の最大の整数を表す。正の整数$n$に対して\n"
        "\\[\n"
        f"a_n=\\int_1^n \\log\\left({body}\\right)\\,dx\n"
        "\\]\n"
        "と定める。このとき\n"
        "\\[\n"
        f"\\lim_{{n\\to\\infty}} \\frac{{e^{{a_n/n}}}}{{n{p_tex}}}\n"
        "\\]\n"
        "を求めよ。"
    )


def generate_candidates(limit: int = 120) -> list[CandidateProblem]:
    alphas = [
        Fraction(1, 2),
        Fraction(2, 3),
        Fraction(3, 4),
        Fraction(1, 1),
        Fraction(3, 2),
        Fraction(2, 1),
        Fraction(3, 1),
        Fraction(4, 1),
    ]
    betas = [
        Fraction(-3, 1),
        Fraction(-5, 2),
        Fraction(-2, 1),
        Fraction(-3, 2),
        Fraction(-1, 1),
        Fraction(-1, 2),
        Fraction(0, 1),
        Fraction(1, 3),
        Fraction(1, 2),
        Fraction(2, 3),
        Fraction(1, 1),
        Fraction(3, 2),
        Fraction(2, 1),
    ]
    gammas = [0, 1, 2, 3, 4]
    powers = [Fraction(0, 1), Fraction(1, 1), Fraction(2, 1)]

    candidates: list[CandidateProblem] = []
    index = 0
    # Interleave alpha values early so small limits still produce a useful
    # phase diagram rather than a diagram for only the first slope.
    for beta in betas:
        for gamma in gammas:
            for p in powers:
                for alpha in alphas:
                    index += 1
                    candidates.append(
                        CandidateProblem(
                            candidate_id=f"floorlog-{index:04d}",
                            alpha=alpha,
                            beta=beta,
                            gamma=gamma,
                            p=p,
                        )
                    )
                    if len(candidates) >= limit:
                        return candidates
    return candidates


def piecewise_integral_log(candidate: CandidateProblem, n: int) -> float:
    """Numerically integrate exactly by splitting floor-constant intervals."""
    if n <= candidate.lower:
        return 0.0
    alpha = candidate.alpha
    beta = Fraction(candidate.beta, 1)
    gamma = candidate.gamma
    start = candidate.lower
    end = Fraction(n, 1)
    m_min = floor_fraction(alpha * start + beta) - 2
    m_max = floor_fraction(alpha * end + beta) + 2
    total = 0.0
    for m in range(m_min, m_max + 1):
        left = (Fraction(m, 1) - beta) / alpha
        right = (Fraction(m + 1, 1) - beta) / alpha
        if right <= start or left >= end:
            continue
        interval_left = max(left, start)
        interval_right = min(right, end)
        if interval_right <= interval_left:
            continue
        value = m + gamma
        if value <= 0:
            raise ValueError(f"log domain error: floor value + gamma = {value}")
        total += float(interval_right - interval_left) * math.log(value)
    return total


def numeric_probe(candidate: CandidateProblem) -> list[dict[str, Any]]:
    samples = []
    for n in (20, 50, 100, 200):
        try:
            integral = piecewise_integral_log(candidate, n)
            value = math.exp(integral / n) / (float(n) ** float(candidate.p))
            samples.append(
                {
                    "n": n,
                    "integral": round(integral, 10),
                    "value": value if math.isfinite(value) else str(value),
                }
            )
        except Exception as exc:
            samples.append({"n": n, "error": f"{type(exc).__name__}: {str(exc)}"})
            break
    return samples


def numeric_status(candidate: CandidateProblem, answer: str, samples: list[dict[str, Any]]) -> str:
    if not samples or any("error" in item for item in samples):
        return "failed"
    values = [item["value"] for item in samples if isinstance(item.get("value"), float)]
    if not values:
        return "failed"
    last = values[-1]
    if answer == "0":
        return "supports_vanishing" if abs(last) < 0.05 else "inconclusive"
    if answer == "infinity":
        return "supports_divergence" if values[-1] > values[0] * 2 else "inconclusive"
    predicted = float(candidate.alpha) / math.e
    relative_error = abs(last - predicted) / max(abs(predicted), 1e-9)
    return "supports_limit" if relative_error < 0.08 else "inconclusive"


def solve_candidate(candidate: CandidateProblem) -> SolverTrace:
    min_value = candidate.min_floor_argument()
    if candidate.alpha <= 0:
        return SolverTrace(
            status="invalid",
            asymptotic_law="alpha must be positive",
            predicted_limit="undefined",
            proof_sketch=[],
            numeric_samples=[],
            warnings=["alpha is not positive"],
        )
    if min_value <= 0:
        repair = 1 - min_value
        return SolverTrace(
            status="invalid_domain",
            asymptotic_law="log(floor(alpha*x+beta)+gamma) is not positive on [1,infty)",
            predicted_limit="undefined",
            proof_sketch=[],
            numeric_samples=numeric_probe(candidate),
            warnings=[f"increase gamma by at least {repair} or move the lower bound"],
        )

    answer, _, phase = answer_for(candidate)
    samples = numeric_probe(candidate)
    status = numeric_status(candidate, answer, samples)
    return SolverTrace(
        status=status,
        asymptotic_law=(
            "A_n = n log n + n(log(alpha)-1) + O(log n), "
            "so exp(A_n/n) = (alpha/e)n(1+o(1))."
        ),
        predicted_limit=answer,
        proof_sketch=[
            "floor(alpha*x+beta)+gamma = alpha*x + O(1) as x -> infinity.",
            "log(floor(alpha*x+beta)+gamma) = log x + log(alpha) + O(1/x).",
            "Integrating gives A_n = n log n + n(log(alpha)-1) + O(log n).",
            "Therefore exp(A_n/n)/n^p has phase: infinity for p<1, alpha/e for p=1, 0 for p>1.",
        ],
        numeric_samples=samples,
        warnings=[] if status in {"supports_limit", "supports_vanishing", "supports_divergence"} else ["numeric probe was inconclusive"],
    )


def repair_actions(candidate: CandidateProblem, phase: str) -> list[RepairAction]:
    actions: list[RepairAction] = []
    min_value = candidate.min_floor_argument()
    if min_value <= 0:
        actions.append(
            RepairAction(
                kind="fix_domain",
                description="Make the logarithm positive on the whole integration interval.",
                patch={"gamma": candidate.gamma + (1 - min_value)},
            )
        )
    if candidate.p != 1:
        actions.append(
            RepairAction(
                kind="move_to_finite_phase",
                description="Set p=1 to land on the finite nonzero asymptotic boundary.",
                patch={"p": "1"},
            )
        )
    if abs(candidate.beta) + abs(candidate.gamma) == 0 and phase == "finite_closed":
        actions.append(
            RepairAction(
                kind="increase_nontriviality",
                description="Add a harmless shift inside the floor/log to hide the asymptotic constant without changing the phase.",
                patch={"beta": fraction_plain(candidate.beta - 1), "gamma": candidate.gamma + 2},
            )
        )
    if max(abs(candidate.beta), abs(candidate.gamma), candidate.alpha.numerator, candidate.alpha.denominator) > 4:
        actions.append(
            RepairAction(
                kind="simplify_coefficients",
                description="Reduce coefficient size to keep the statement contest-clean.",
                patch={},
            )
        )
    return actions


def evaluate_candidate(candidate: CandidateProblem) -> EvaluationResult:
    min_value = candidate.min_floor_argument()
    trace = solve_candidate(candidate)
    answer, answer_tex, phase = answer_for(candidate)
    labels: list[str] = []

    if trace.status == "invalid_domain":
        phase = "invalid_domain"
        answer = "undefined"
        answer_tex = "\\text{undefined}"
        labels.extend(["invalid_domain", "degenerate"])
    elif candidate.p < 1:
        labels.extend(["valid_domain", "divergent_phase", "degenerate"])
    elif candidate.p > 1:
        labels.extend(["valid_domain", "vanishing_phase", "degenerate"])
    else:
        labels.extend(["valid_domain", "finite_closed", "clean_asymptotic"])

    if min_value == 1 and "valid_domain" in labels:
        labels.append("near_domain_boundary")
    if abs(candidate.beta) + abs(candidate.gamma) > 0 and candidate.p == 1 and min_value > 0:
        labels.append("hidden_shift")
    if candidate.alpha.denominator > 1:
        labels.append("rational_slope")
    if trace.status.startswith("supports"):
        labels.append("numeric_supported")

    closed_form = phase == "finite_closed"
    degenerate = "degenerate" in labels
    nontrivial = closed_form and (abs(candidate.beta) + abs(candidate.gamma) > 0 or candidate.alpha.denominator > 1)
    finite_answer = phase == "finite_closed"
    difficulty = estimate_difficulty(candidate, phase, labels, min_value)

    component_scores = score_components(candidate, trace, phase, labels, min_value, difficulty)
    score = round(sum(component_scores.values()), 3)
    if score >= 72 and closed_form and not degenerate:
        labels.append("good_candidate")
    if 58 <= score < 72 and closed_form and not degenerate:
        labels.append("borderline_candidate")

    return EvaluationResult(
        candidate=candidate.to_json_dict(),
        labels=labels,
        phase=phase,
        solved=trace.status in {"supports_limit", "supports_vanishing", "supports_divergence", "inconclusive"},
        closed_form=closed_form,
        degenerate=degenerate,
        nontrivial=nontrivial,
        finite_answer=finite_answer,
        answer=answer,
        answer_tex=answer_tex,
        problem_tex=render_problem_tex(candidate),
        estimated_difficulty=difficulty,
        score=score,
        component_scores=component_scores,
        solver_trace=asdict(trace),
        repair_actions=[asdict(action) for action in repair_actions(candidate, phase)],
    )


def score_components(
    candidate: CandidateProblem,
    trace: SolverTrace,
    phase: str,
    labels: list[str],
    min_value: int,
    difficulty: dict[str, Any],
) -> dict[str, float]:
    components = {
        "validity": 0.0,
        "finite_closed_form": 0.0,
        "nontriviality": 0.0,
        "beauty": 0.0,
        "numeric_support": 0.0,
        "phase_boundary": 0.0,
        "difficulty_fit": 0.0,
        "penalty": 0.0,
    }
    if "valid_domain" in labels:
        components["validity"] = 18.0
    else:
        components["penalty"] -= 35.0
    if phase == "finite_closed":
        components["finite_closed_form"] = 25.0
    elif phase in {"divergent", "vanishing"}:
        components["finite_closed_form"] = 4.0
        components["penalty"] -= 12.0

    if phase == "finite_closed":
        shift_complexity = abs(candidate.beta) + abs(candidate.gamma)
        if shift_complexity:
            components["nontriviality"] += min(18.0, 8.0 + 2.0 * shift_complexity)
        if candidate.alpha.denominator > 1:
            components["nontriviality"] += 5.0
        if min_value == 1:
            components["phase_boundary"] = 9.0
        components["beauty"] = 20.0 - min(8.0, coefficient_complexity(candidate))
        components["difficulty_fit"] = difficulty["fit_score"]
    if trace.status in {"supports_limit", "supports_vanishing", "supports_divergence"}:
        components["numeric_support"] = 10.0
    if coefficient_complexity(candidate) > 9:
        components["penalty"] -= 8.0
    if phase == "finite_closed" and abs(candidate.beta) + abs(candidate.gamma) > 5:
        components["penalty"] -= 5.0
    return components


def estimate_difficulty(candidate: CandidateProblem, phase: str, labels: list[str], min_value: int) -> dict[str, Any]:
    """Heuristic contest-style difficulty estimate for the generated problem.

    This is intentionally symbolic and cheap.  It scores the proof obligations:
    domain check, floor asymptotic, integral asymptotic, normalization, and
    hidden shift.  It is not a student-performance model yet.
    """
    proof_obligations = []
    if phase == "invalid_domain":
        proof_obligations.append("repair log-domain positivity")
    else:
        proof_obligations.append("check log-domain positivity")
        proof_obligations.append("control floor perturbation")
        proof_obligations.append("integrate log-asymptotic")
        proof_obligations.append("normalize exponential limit")
    if "near_domain_boundary" in labels:
        proof_obligations.append("handle endpoint boundary")
    if "hidden_shift" in labels:
        proof_obligations.append("notice asymptotically irrelevant shift")
    if candidate.alpha.denominator > 1:
        proof_obligations.append("track rational slope constant")

    raw = len(proof_obligations)
    if phase in {"divergent", "vanishing"}:
        raw -= 1
    if coefficient_complexity(candidate) > 5:
        raw += 1
    if min_value <= 0:
        raw -= 2
    raw = max(1, raw)
    if raw <= 3:
        level = "easy"
    elif raw <= 5:
        level = "medium"
    elif raw <= 7:
        level = "hard"
    else:
        level = "too_busy"

    # We want medium-hard candidates: not one-line, not overcomplicated.
    fit_score_by_level = {
        "easy": 3.0,
        "medium": 8.0,
        "hard": 10.0,
        "too_busy": 2.0,
    }
    return {
        "level": level,
        "raw": raw,
        "proof_obligations": proof_obligations,
        "fit_score": fit_score_by_level[level],
    }


def coefficient_complexity(candidate: CandidateProblem) -> float:
    return (
        float(abs(candidate.beta))
        + abs(candidate.gamma)
        + abs(candidate.alpha.numerator)
        + abs(candidate.alpha.denominator)
        + abs(candidate.p.numerator)
        + abs(candidate.p.denominator)
    ) / 2.5


def build_phase_diagram(results: list[EvaluationResult], *, family: ProblemFamily, top_k: int) -> PhaseDiagram:
    phase_counts = Counter(result.phase for result in results)
    label_counts = Counter(label for result in results for label in result.labels)
    ranked = sorted(
        [result for result in results if "good_candidate" in result.labels or "borderline_candidate" in result.labels],
        key=lambda item: item.score,
        reverse=True,
    )
    top = select_diverse_top_candidates(ranked, top_k=top_k)
    return PhaseDiagram(
        family=asdict(family),
        generated_at=datetime.now(timezone.utc).isoformat(),
        total_candidates=len(results),
        phase_counts=dict(phase_counts),
        label_counts=dict(label_counts),
        top_candidates=[asdict(item) for item in top],
        results=[asdict(item) for item in results],
    )


def select_diverse_top_candidates(ranked: list[EvaluationResult], *, top_k: int) -> list[EvaluationResult]:
    top: list[EvaluationResult] = []
    seen_keys: set[tuple[str, str, int, str]] = set()
    answer_counts: Counter[str] = Counter()
    alpha_counts: Counter[str] = Counter()
    answer_cap = max(2, top_k // 4)
    alpha_cap = max(2, top_k // 3)

    def try_add(result: EvaluationResult, *, enforce_caps: bool) -> None:
        if len(top) >= top_k:
            return
        key = structural_equivalence_key(result)
        if key in seen_keys:
            return
        answer = result.answer
        alpha = result.candidate["alpha"]
        if enforce_caps and (answer_counts[answer] >= answer_cap or alpha_counts[alpha] >= alpha_cap):
            return
        seen_keys.add(key)
        answer_counts[answer] += 1
        alpha_counts[alpha] += 1
        top.append(result)

    for result in ranked:
        try_add(result, enforce_caps=True)
    # If the caps were too strict for a small search space, fill the list while
    # still respecting structural equivalence.
    for result in ranked:
        try_add(result, enforce_caps=False)
    return top


def structural_equivalence_key(result: EvaluationResult) -> tuple[str, str, int, str]:
    """Collapse floor(alpha*x+beta)+gamma by integer shifts of beta.

    floor(alpha*x + q + r) + gamma = floor(alpha*x + r) + (gamma + q)
    for integer q and 0 <= r < 1.
    """
    candidate = result.candidate
    beta = Fraction(candidate["beta"])
    beta_floor = floor_fraction(beta)
    beta_frac = beta - beta_floor
    return (candidate["alpha"], fraction_plain(beta_frac), int(candidate["gamma"]) + beta_floor, candidate["p"])


def summarize_result(result: EvaluationResult) -> dict[str, Any]:
    return {
        "candidate_id": result.candidate["candidate_id"],
        "params": result.candidate,
        "phase": result.phase,
        "score": result.score,
        "answer": result.answer,
        "labels": result.labels,
        "difficulty": result.estimated_difficulty,
    }


def choose_repair_action(candidate: CandidateProblem, result: EvaluationResult) -> RepairAction | None:
    actions = repair_actions(candidate, result.phase)
    priority = {
        "fix_domain": 0,
        "move_to_finite_phase": 1,
        "increase_nontriviality": 2,
        "simplify_coefficients": 3,
    }
    usable = [action for action in actions if action.patch]
    if not usable:
        return None
    usable.sort(key=lambda action: priority.get(action.kind, 99))
    return usable[0]


def repair_candidate(candidate: CandidateProblem, *, max_steps: int = 4) -> RepairTrace:
    current = candidate
    original_result = evaluate_candidate(current)
    steps: list[dict[str, Any]] = []
    seen = {canonical_candidate_key(current)}

    for step_index in range(1, max_steps + 1):
        before = evaluate_candidate(current)
        if "good_candidate" in before.labels:
            break
        action = choose_repair_action(current, before)
        if action is None:
            break
        repaired = current.with_patch(action.patch, suffix=f"r{step_index}")
        key = canonical_candidate_key(repaired)
        if key in seen:
            break
        seen.add(key)
        after = evaluate_candidate(repaired)
        steps.append(
            asdict(
                RepairStep(
                    step_index=step_index,
                    action=asdict(action),
                    before=summarize_result(before),
                    after=summarize_result(after),
                )
            )
        )
        current = repaired
        if "good_candidate" in after.labels:
            break

    final_result = evaluate_candidate(current)
    return RepairTrace(
        original=summarize_result(original_result),
        final=summarize_result(final_result),
        successful="good_candidate" in final_result.labels,
        steps=steps,
    )


def canonical_candidate_key(candidate: CandidateProblem) -> tuple[str, str, int, str, str]:
    beta_floor = floor_fraction(candidate.beta)
    beta_frac = candidate.beta - beta_floor
    return (
        fraction_plain(candidate.alpha),
        fraction_plain(beta_frac),
        candidate.gamma + beta_floor,
        fraction_plain(candidate.p),
        fraction_plain(candidate.lower),
    )


def run_repair_experiment(*, limit: int, repair_limit: int, max_steps: int, top_k: int) -> dict[str, Any]:
    candidates = generate_candidates(limit=limit)
    initial_results = [evaluate_candidate(candidate) for candidate in candidates]
    repair_pool = [
        (candidate, result)
        for candidate, result in zip(candidates, initial_results)
        if "good_candidate" not in result.labels
    ][:repair_limit]
    traces = [asdict(repair_candidate(candidate, max_steps=max_steps)) for candidate, _ in repair_pool]

    transitions = Counter(
        f"{trace['original']['phase']} -> {trace['final']['phase']}"
        for trace in traces
    )
    successes = [trace for trace in traces if trace["successful"]]
    score_deltas = [
        trace["final"]["score"] - trace["original"]["score"]
        for trace in traces
        if trace["steps"]
    ]
    repaired_results = [
        evaluate_candidate(candidate_from_params(trace["final"]["params"]))
        for trace in traces
    ]
    diagram = build_phase_diagram(repaired_results, family=FLOOR_LOG_FAMILY, top_k=top_k)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input": {
            "limit": limit,
            "repair_limit": repair_limit,
            "max_steps": max_steps,
            "top_k": top_k,
        },
        "summary": {
            "attempted": len(traces),
            "successful": len(successes),
            "success_rate": round(len(successes) / len(traces), 4) if traces else 0.0,
            "transitions": dict(transitions),
            "mean_score_delta": round(sum(score_deltas) / len(score_deltas), 3) if score_deltas else 0.0,
            "max_score_delta": round(max(score_deltas), 3) if score_deltas else 0.0,
        },
        "top_repaired_candidates": diagram.top_candidates,
        "traces": traces,
    }


def candidate_from_params(params: dict[str, Any]) -> CandidateProblem:
    return CandidateProblem(
        candidate_id=str(params["candidate_id"]),
        alpha=parse_fraction(str(params["alpha"])),
        beta=parse_fraction(str(params["beta"])),
        gamma=int(params["gamma"]),
        p=parse_fraction(str(params["p"])),
        lower=parse_fraction(str(params.get("lower", "1"))),
    )


def render_geometry_problem_tex(candidate: GeometrySweepCandidate) -> str:
    task_text = "通過領域" if candidate.task == "region" else "包絡線"
    return (
        f"実数${candidate.parameter}$に対して，曲線\n"
        "\\[\n"
        f"y={candidate.equation_tex()}\n"
        "\\]\n"
        f"が定まる。この曲線族の{task_text}を求めよ。"
    )


def import_sympy():
    import sympy as sp

    return sp


def primitive_polynomial_normal_form(expression: str) -> dict[str, Any]:
    sp = import_sympy()
    x, y = sp.symbols("x y")
    expr = sp.sympify(expression.replace("^", "**"), locals={"x": x, "y": y})
    numerator = sp.together(sp.expand(expr)).as_numer_denom()[0]
    poly = sp.Poly(sp.expand(numerator), x, y)
    denominators = [sp.denom(coeff) for coeff in poly.coeffs()] or [1]
    lcm = 1
    for denominator in denominators:
        lcm = int(sp.ilcm(lcm, int(denominator)))
    integer_expr = sp.expand(poly.as_expr() * lcm)
    integer_poly = sp.Poly(integer_expr, x, y)
    coefficients = [int(coeff) for coeff in integer_poly.coeffs()]
    content = 0
    for coefficient in coefficients:
        content = math.gcd(content, abs(coefficient))
    if content:
        integer_expr = sp.expand(integer_expr / content)
    integer_poly = sp.Poly(integer_expr, x, y)
    leading_coeff = int(integer_poly.terms()[0][1]) if integer_poly.terms() else 1
    sign_flipped = leading_coeff < 0
    if sign_flipped:
        integer_expr = sp.expand(-integer_expr)
    return {
        "polynomial": sp.sstr(sp.factor(integer_expr)),
        "sign_flipped": sign_flipped,
    }


def canonical_region_inequality(inequality: str) -> dict[str, Any]:
    sp = import_sympy()
    x, y = sp.symbols("x y")
    match = re.search(r"(<=|>=|<|>)", inequality)
    if not match:
        return {"kind": "region", "normal_form": inequality, "parse_status": "unparsed"}
    operator = match.group(1)
    left = inequality[: match.start()].strip()
    right = inequality[match.end() :].strip()
    lhs = sp.sympify(left.replace("^", "**"), locals={"x": x, "y": y})
    rhs = sp.sympify(right.replace("^", "**"), locals={"x": x, "y": y})
    normal = primitive_polynomial_normal_form(sp.sstr(lhs - rhs))
    canonical_operator = operator
    if normal["sign_flipped"]:
        canonical_operator = {"<=": ">=", ">=": "<=", "<": ">", ">": "<"}[operator]
    return {
        "kind": "region",
        "normal_form": f"{normal['polynomial']} {canonical_operator} 0",
        "boundary_polynomial": normal["polynomial"],
        "operator": canonical_operator,
        "parse_status": "ok",
    }


def canonical_envelope_relation(relation: str) -> dict[str, Any]:
    relation_text = relation.strip()
    if relation_text.endswith("= 0"):
        relation_text = relation_text[:-3].strip()
    elif "=" in relation_text:
        left, right = relation_text.split("=", 1)
        relation_text = f"({left}) - ({right})"
    normal = primitive_polynomial_normal_form(relation_text)
    return {
        "kind": "envelope",
        "normal_form": f"{normal['polynomial']} = 0",
        "boundary_polynomial": normal["polynomial"],
        "parse_status": "ok",
    }


def canonical_geometry_answer(candidate: GeometrySweepCandidate, result: dict[str, Any], answer: str) -> dict[str, Any]:
    try:
        if candidate.task == "region":
            closed_form = result.get("closed_form", {})
            inequality = closed_form.get("inequality")
            if inequality:
                return canonical_region_inequality(inequality)
            relation = closed_form.get("relation")
            if relation:
                normal = canonical_envelope_relation(relation)
                normal["kind"] = "region_relation"
                return normal
        if candidate.task == "envelope":
            return canonical_envelope_relation(answer)
    except Exception as exc:
        return {
            "kind": candidate.task,
            "normal_form": answer,
            "parse_status": "error",
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {"kind": candidate.task, "normal_form": answer, "parse_status": "unavailable"}


def generate_geometry_candidates(limit: int = 80) -> list[GeometrySweepCandidate]:
    candidates: list[GeometrySweepCandidate] = []
    index = 0
    for a in (1, 0, 2, 3, -1):
        for b in (-1, 0, -2, 1, 2):
            for c in (0, 1, -1):
                for d in (0, 1, -2):
                    for task in ("region", "envelope"):
                        index += 1
                        candidates.append(
                            GeometrySweepCandidate(
                                candidate_id=f"geosweep-{index:04d}",
                                task=task,
                                a=a,
                                b=b,
                                c=c,
                                d=d,
                            )
                        )
                        if len(candidates) >= limit:
                            return candidates
    return candidates


def evaluate_geometry_candidate(candidate: GeometrySweepCandidate) -> dict[str, Any]:
    try:
        from math_os_prototype.geometry_dsl import run_geometry_dsl
    except ModuleNotFoundError:  # pragma: no cover - direct script execution.
        from geometry_dsl import run_geometry_dsl

    labels = ["geometry_sweep", candidate.task, "quadratic_parameter"]
    try:
        execution = run_geometry_dsl(candidate.dsl_source())
        result = execution["result"]
        if candidate.task == "region":
            closed_form = result.get("closed_form", {})
            answer = closed_form.get("inequality") or closed_form.get("relation") or json.dumps(closed_form, ensure_ascii=False)
            phase = "closed_region" if closed_form.get("type") == "quadratic_range" and "inequality" in closed_form else "partial_region"
            if closed_form.get("sense"):
                labels.append(closed_form["sense"])
        else:
            answer = f"{result['envelope_relation']} = 0"
            phase = "closed_envelope"
        labels.extend(["sympy_supported", "nondegenerate"])
        if candidate.c != 0 or candidate.d != 0:
            labels.append("affine_shift")
        normal_form = canonical_geometry_answer(candidate, result, answer)
        difficulty = estimate_geometry_difficulty(candidate, phase, labels)
        component_scores = geometry_score_components(candidate, phase, labels, difficulty)
        score = round(sum(component_scores.values()), 3)
        return {
            "candidate": candidate.to_json_dict(),
            "labels": labels,
            "phase": phase,
            "answer": answer,
            "normal_form": normal_form,
            "problem_tex": render_geometry_problem_tex(candidate),
            "estimated_difficulty": difficulty,
            "score": score,
            "component_scores": component_scores,
            "execution": execution,
            "curriculum_item": geometry_curriculum_item(candidate, phase, answer, normal_form),
        }
    except Exception as exc:
        phase = "geometry_error"
        labels.extend(["error"])
        difficulty = estimate_geometry_difficulty(candidate, phase, labels)
        return {
            "candidate": candidate.to_json_dict(),
            "labels": labels,
            "phase": phase,
            "answer": "undefined",
            "normal_form": {"kind": candidate.task, "normal_form": "undefined", "parse_status": "error"},
            "problem_tex": render_geometry_problem_tex(candidate),
            "estimated_difficulty": difficulty,
            "score": -40.0,
            "component_scores": {"penalty": -40.0},
            "execution": {"error": f"{type(exc).__name__}: {exc}"},
            "curriculum_item": None,
        }


def geometry_curriculum_item(
    candidate: GeometrySweepCandidate,
    phase: str,
    answer: str,
    normal_form: dict[str, Any],
) -> dict[str, Any] | None:
    if phase not in {"closed_region", "closed_envelope"} or normal_form.get("parse_status") != "ok":
        return None
    return {
        "source": "problem_phase_synthesis.geometry_sweep",
        "input_tex": render_geometry_problem_tex(candidate),
        "dsl": candidate.dsl_source(),
        "task": candidate.task,
        "expected_answer": answer,
        "normal_form": normal_form,
        "strategy": "existential_elimination" if candidate.task == "region" else "envelope_resultant",
        "proof_obligations": estimate_geometry_difficulty(candidate, phase, ["affine_shift"] if candidate.c or candidate.d else [])[
            "proof_obligations"
        ],
    }


def estimate_geometry_difficulty(candidate: GeometrySweepCandidate, phase: str, labels: list[str]) -> dict[str, Any]:
    proof_obligations = [
        "encode a one-parameter curve family",
        "choose the correct existential/envelope observation",
    ]
    if candidate.task == "region":
        proof_obligations.append("eliminate an existential real parameter")
        proof_obligations.append("turn the quadratic range into an inequality")
    else:
        proof_obligations.append("differentiate F with respect to the parameter")
        proof_obligations.append("eliminate the parameter by resultant")
    if "affine_shift" in labels:
        proof_obligations.append("track affine translation of the boundary")
    if abs(candidate.a) > 1 or abs(candidate.b) > 1:
        proof_obligations.append("track coefficient scaling")

    raw = len(proof_obligations)
    if phase in {"geometry_error", "partial_region"}:
        raw = max(1, raw - 2)
    if raw <= 3:
        level = "easy"
    elif raw <= 5:
        level = "medium"
    elif raw <= 7:
        level = "hard"
    else:
        level = "too_busy"
    fit_score = {"easy": 4.0, "medium": 9.0, "hard": 10.0, "too_busy": 3.0}[level]
    return {
        "level": level,
        "raw": raw,
        "proof_obligations": proof_obligations,
        "fit_score": fit_score,
    }


def geometry_score_components(
    candidate: GeometrySweepCandidate,
    phase: str,
    labels: list[str],
    difficulty: dict[str, Any],
) -> dict[str, float]:
    components = {
        "closed_backend_result": 0.0,
        "nontriviality": 0.0,
        "beauty": 0.0,
        "difficulty_fit": 0.0,
        "task_value": 0.0,
        "penalty": 0.0,
    }
    if phase in {"closed_region", "closed_envelope"}:
        components["closed_backend_result"] = 40.0
        components["difficulty_fit"] = difficulty["fit_score"]
    else:
        components["penalty"] -= 25.0
    if "affine_shift" in labels:
        components["nontriviality"] += 10.0
    if abs(candidate.a) > 1 or abs(candidate.b) > 1:
        components["nontriviality"] += 8.0
    components["task_value"] = 10.0 if candidate.task == "region" else 12.0
    complexity = abs(candidate.a) + abs(candidate.b) + abs(candidate.c) + abs(candidate.d)
    components["beauty"] = 18.0 - min(10.0, complexity)
    if complexity > 7:
        components["penalty"] -= 4.0
    return components


def geometry_candidate_success(result: dict[str, Any]) -> bool:
    return (
        result["phase"] in {"closed_region", "closed_envelope"}
        and result["score"] >= 84.0
        and result.get("normal_form", {}).get("parse_status") == "ok"
    )


def geometry_repair_actions(candidate: GeometrySweepCandidate, result: dict[str, Any]) -> list[RepairAction]:
    actions: list[RepairAction] = []
    if candidate.a == 0:
        actions.append(
            RepairAction(
                kind="restore_x_parameter_coupling",
                description="Make the parameter actually move the curve in the x direction.",
                patch={"a": 1},
            )
        )
    if candidate.b == 0 or result["phase"] in {"partial_region", "geometry_error"}:
        actions.append(
            RepairAction(
                kind="restore_quadratic_parameter",
                description="Add a nonzero t^2 coefficient so elimination produces a quadratic boundary.",
                patch={"b": -1},
            )
        )
    if result["phase"] in {"closed_region", "closed_envelope"} and "affine_shift" not in result["labels"]:
        actions.append(
            RepairAction(
                kind="add_affine_shift",
                description="Add a harmless translation so the final boundary is not the base parabola.",
                patch={"d": 1},
            )
        )
    if result["phase"] in {"closed_region", "closed_envelope"} and result["score"] < 84.0:
        patch: dict[str, Any] = {}
        if candidate.b != 0 and abs(candidate.b) == 1:
            patch["b"] = -2 if candidate.b < 0 else 2
        elif candidate.a != 0 and abs(candidate.a) == 1:
            patch["a"] = 2 if candidate.a > 0 else -2
        if patch:
            actions.append(
                RepairAction(
                    kind="increase_elimination_texture",
                    description="Slightly scale the moving term so the boundary is less immediate while staying closed-form.",
                    patch=patch,
                )
            )
    complexity = abs(candidate.a) + abs(candidate.b) + abs(candidate.c) + abs(candidate.d)
    if complexity > 7:
        actions.append(
            RepairAction(
                kind="simplify_geometry_coefficients",
                description="Reduce coefficients while preserving a nontrivial quadratic sweep.",
                patch={"a": 1 if candidate.a >= 0 else -1, "b": -2 if candidate.b < 0 else 2},
            )
        )
    return actions


def choose_geometry_repair_action(candidate: GeometrySweepCandidate, result: dict[str, Any]) -> RepairAction | None:
    priority = {
        "restore_x_parameter_coupling": 0,
        "restore_quadratic_parameter": 1,
        "add_affine_shift": 2,
        "increase_elimination_texture": 3,
        "simplify_geometry_coefficients": 4,
    }
    actions = [action for action in geometry_repair_actions(candidate, result) if action.patch]
    if not actions:
        return None
    actions.sort(key=lambda action: priority.get(action.kind, 99))
    return actions[0]


def summarize_geometry_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": result["candidate"]["candidate_id"],
        "params": result["candidate"],
        "phase": result["phase"],
        "score": result["score"],
        "answer": result["answer"],
        "normal_form": result.get("normal_form"),
        "labels": result["labels"],
        "difficulty": result["estimated_difficulty"],
    }


def canonical_geometry_candidate_key(candidate: GeometrySweepCandidate) -> tuple[str, int, int, int, int]:
    return (candidate.task, candidate.a, candidate.b, candidate.c, candidate.d)


def repair_geometry_candidate(candidate: GeometrySweepCandidate, *, max_steps: int = 4) -> dict[str, Any]:
    current = candidate
    original_result = evaluate_geometry_candidate(current)
    steps: list[dict[str, Any]] = []
    seen = {canonical_geometry_candidate_key(current)}

    for step_index in range(1, max_steps + 1):
        before = evaluate_geometry_candidate(current)
        if geometry_candidate_success(before):
            break
        action = choose_geometry_repair_action(current, before)
        if action is None:
            break
        repaired = current.with_patch(action.patch, suffix=f"gr{step_index}")
        key = canonical_geometry_candidate_key(repaired)
        if key in seen:
            break
        seen.add(key)
        after = evaluate_geometry_candidate(repaired)
        steps.append(
            asdict(
                RepairStep(
                    step_index=step_index,
                    action=asdict(action),
                    before=summarize_geometry_result(before),
                    after=summarize_geometry_result(after),
                )
            )
        )
        current = repaired
        if geometry_candidate_success(after):
            break

    final_result = evaluate_geometry_candidate(current)
    return {
        "original": summarize_geometry_result(original_result),
        "final": summarize_geometry_result(final_result),
        "successful": geometry_candidate_success(final_result),
        "steps": steps,
    }


def geometry_candidate_from_params(params: dict[str, Any]) -> GeometrySweepCandidate:
    return GeometrySweepCandidate(
        candidate_id=str(params["candidate_id"]),
        task=str(params["task"]),
        a=int(params["a"]),
        b=int(params["b"]),
        c=int(params["c"]),
        d=int(params["d"]),
        parameter=str(params.get("parameter", "t")),
    )


def run_geometry_repair_experiment(*, limit: int, repair_limit: int, max_steps: int, top_k: int) -> dict[str, Any]:
    candidates = generate_geometry_candidates(limit=limit)
    initial_results = [evaluate_geometry_candidate(candidate) for candidate in candidates]
    repair_pool = [
        (candidate, result)
        for candidate, result in zip(candidates, initial_results)
        if not geometry_candidate_success(result)
    ][:repair_limit]
    traces = [repair_geometry_candidate(candidate, max_steps=max_steps) for candidate, _ in repair_pool]
    transitions = Counter(
        f"{trace['original']['phase']} -> {trace['final']['phase']}"
        for trace in traces
    )
    successes = [trace for trace in traces if trace["successful"]]
    score_deltas = [
        trace["final"]["score"] - trace["original"]["score"]
        for trace in traces
        if trace["steps"]
    ]
    repaired_results = [
        evaluate_geometry_candidate(geometry_candidate_from_params(trace["final"]["params"]))
        for trace in traces
    ]
    return {
        "family": asdict(GEOMETRY_SWEEP_FAMILY),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input": {
            "limit": limit,
            "repair_limit": repair_limit,
            "max_steps": max_steps,
            "top_k": top_k,
        },
        "summary": {
            "attempted": len(traces),
            "successful": len(successes),
            "success_rate": round(len(successes) / len(traces), 4) if traces else 0.0,
            "transitions": dict(transitions),
            "mean_score_delta": round(sum(score_deltas) / len(score_deltas), 3) if score_deltas else 0.0,
            "max_score_delta": round(max(score_deltas), 3) if score_deltas else 0.0,
        },
        "top_repaired_candidates": select_diverse_geometry_candidates(repaired_results, top_k=top_k),
        "curriculum_items": [
            result["curriculum_item"]
            for result in repaired_results
            if result.get("curriculum_item") and geometry_candidate_success(result)
        ],
        "traces": traces,
    }


def select_diverse_geometry_candidates(results: list[dict[str, Any]], *, top_k: int) -> list[dict[str, Any]]:
    ranked = sorted(results, key=lambda item: item["score"], reverse=True)
    top: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    task_counts: Counter[str] = Counter()
    for result in ranked:
        candidate = result["candidate"]
        key = (candidate["task"], result.get("normal_form", {}).get("normal_form", result["answer"]))
        if key in seen:
            continue
        if task_counts[candidate["task"]] >= max(2, top_k // 2):
            continue
        seen.add(key)
        task_counts[candidate["task"]] += 1
        top.append(result)
        if len(top) >= top_k:
            return top
    for result in ranked:
        candidate = result["candidate"]
        key = (candidate["task"], result.get("normal_form", {}).get("normal_form", result["answer"]))
        if key not in seen:
            seen.add(key)
            top.append(result)
        if len(top) >= top_k:
            break
    return top


def run_geometry_phase_synthesis(*, limit: int, top_k: int) -> dict[str, Any]:
    candidates = generate_geometry_candidates(limit=limit)
    results = [evaluate_geometry_candidate(candidate) for candidate in candidates]
    phase_counts = Counter(result["phase"] for result in results)
    label_counts = Counter(label for result in results for label in result["labels"])
    return {
        "family": asdict(GEOMETRY_SWEEP_FAMILY),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_candidates": len(results),
        "phase_counts": dict(phase_counts),
        "label_counts": dict(label_counts),
        "top_candidates": select_diverse_geometry_candidates(results, top_k=top_k),
        "curriculum_items": [
            result["curriculum_item"]
            for result in results
            if result.get("curriculum_item") and geometry_candidate_success(result)
        ],
        "results": results,
    }


def render_markdown(diagram: PhaseDiagram) -> str:
    lines: list[str] = []
    lines.append("# Problem Phase Diagram Synthesis")
    lines.append("")
    lines.append(f"Generated: {diagram.generated_at}")
    lines.append("")
    lines.append("## Family")
    lines.append("")
    lines.append(f"- Name: `{diagram.family['name']}`")
    lines.append(f"- Theme: {diagram.family['theme']}")
    lines.append(f"- Invariant: {diagram.family['invariant']}")
    lines.append("")
    lines.append("## Phase Counts")
    lines.append("")
    for phase, count in sorted(diagram.phase_counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {phase}: {count}")
    lines.append("")
    lines.append("## Label Counts")
    lines.append("")
    for label, count in sorted(diagram.label_counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {label}: {count}")
    lines.append("")
    lines.append("## Top Candidates")
    lines.append("")
    if not diagram.top_candidates:
        lines.append("No good candidates found under the current scoring rule.")
    for index, result in enumerate(diagram.top_candidates, start=1):
        candidate = result["candidate"]
        lines.append(f"### {index}. {candidate['candidate_id']} score={result['score']}")
        lines.append("")
        lines.append(f"- params: alpha={candidate['alpha']}, beta={candidate['beta']}, gamma={candidate['gamma']}, p={candidate['p']}")
        lines.append(f"- labels: {', '.join(result['labels'])}")
        lines.append(f"- answer: ${result['answer_tex']}$")
        lines.append("- problem:")
        lines.append("")
        lines.append("```tex")
        lines.append(result["problem_tex"])
        lines.append("```")
        lines.append("")
        lines.append("- numeric probe:")
        for sample in result["solver_trace"]["numeric_samples"][-2:]:
            lines.append(f"  - {json.dumps(sample, ensure_ascii=False)}")
        lines.append("")
    lines.append("## Repair Examples")
    lines.append("")
    repair_rows = []
    for result in diagram.results:
        if result.get("repair_actions"):
            repair_rows.append(result)
        if len(repair_rows) >= 8:
            break
    for result in repair_rows:
        candidate = result["candidate"]
        lines.append(f"- {candidate['candidate_id']} phase={result['phase']} params={candidate}")
        for action in result["repair_actions"]:
            lines.append(f"  - {action['kind']}: {action['description']} patch={action['patch']}")
    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append(
        "The finite nonzero phase appears at `p=1`.  This is the first useful "
        "problem-making boundary: `p<1` diverges, `p>1` vanishes, while `p=1` "
        "keeps a simple closed form `alpha/e` despite the floor-function perturbation."
    )
    lines.append(
        "Good candidates are deliberately close to a domain boundary or include "
        "a harmless shift.  Those parameters create proof work without making "
        "the final answer ugly."
    )
    return "\n".join(lines) + "\n"


def write_outputs(diagram: PhaseDiagram, *, output_dir: Path, prefix: str) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{prefix}.json"
    jsonl_path = output_dir / f"{prefix}.jsonl"
    md_path = output_dir / f"{prefix}_report.md"
    json_path.write_text(json.dumps(asdict(diagram), ensure_ascii=False, indent=2), encoding="utf-8")
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for item in diagram.results:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    md_path.write_text(render_markdown(diagram), encoding="utf-8")
    return json_path, jsonl_path, md_path


def write_repair_outputs(repair_report: dict[str, Any], *, output_dir: Path, prefix: str) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{prefix}.json"
    md_path = output_dir / f"{prefix}_report.md"
    json_path.write_text(json.dumps(repair_report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_repair_markdown(repair_report), encoding="utf-8")
    return json_path, md_path


def write_geometry_outputs(report: dict[str, Any], *, output_dir: Path, prefix: str) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{prefix}.json"
    md_path = output_dir / f"{prefix}_report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_geometry_markdown(report), encoding="utf-8")
    return json_path, md_path


def write_geometry_repair_outputs(report: dict[str, Any], *, output_dir: Path, prefix: str) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{prefix}.json"
    md_path = output_dir / f"{prefix}_report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_geometry_repair_markdown(report), encoding="utf-8")
    return json_path, md_path


def render_geometry_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Geometry Sweep Phase Synthesis")
    lines.append("")
    lines.append(f"Generated: {report['generated_at']}")
    lines.append("")
    lines.append("## Family")
    lines.append("")
    lines.append(f"- Name: `{report['family']['name']}`")
    lines.append(f"- Theme: {report['family']['theme']}")
    lines.append(f"- Invariant: {report['family']['invariant']}")
    lines.append("")
    lines.append("## Phase Counts")
    lines.append("")
    for phase, count in sorted(report["phase_counts"].items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {phase}: {count}")
    lines.append("")
    lines.append("## Label Counts")
    lines.append("")
    for label, count in sorted(report["label_counts"].items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {label}: {count}")
    lines.append("")
    lines.append("## Top Candidates")
    lines.append("")
    for index, result in enumerate(report["top_candidates"], start=1):
        candidate = result["candidate"]
        lines.append(f"### {index}. {candidate['candidate_id']} score={result['score']}")
        lines.append("")
        lines.append(
            f"- task: {candidate['task']}; params: "
            f"a={candidate['a']}, b={candidate['b']}, c={candidate['c']}, d={candidate['d']}"
        )
        lines.append(f"- dsl: `{candidate['dsl']}`")
        lines.append(f"- phase: {result['phase']}")
        lines.append(f"- answer: `{result['answer']}`")
        lines.append(f"- normal form: `{result.get('normal_form', {}).get('normal_form')}`")
        lines.append(f"- difficulty: {result['estimated_difficulty']['level']}")
        lines.append("")
        lines.append("```tex")
        lines.append(result["problem_tex"])
        lines.append("```")
        lines.append("")
    lines.append("## Curriculum Export")
    lines.append("")
    lines.append(f"- Verified curriculum items: {len(report.get('curriculum_items', []))}")
    lines.append(
        "- Each item contains input TeX, Geometry DSL, expected answer, algebraic normal form, "
        "strategy tag, and proof obligations."
    )
    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append(
        "This theme uses the same generated curve family for two observations: "
        "`region` compiles to an existential real-parameter elimination problem, "
        "and `envelope` compiles to resultant(F, dF/dt)."
    )
    lines.append(
        "The generator is still narrow, but it is now a second phase family: "
        "MathOS can propose geometry problems, execute the Geometry DSL backend, "
        "score closed-form outputs, and diversify by observation and curvature."
    )
    return "\n".join(lines) + "\n"


def render_geometry_repair_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Geometry Sweep Repair Loop Report")
    lines.append("")
    lines.append(f"Generated: {report['generated_at']}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    summary = report["summary"]
    lines.append(f"- Attempted: {summary['attempted']}")
    lines.append(f"- Successful: {summary['successful']}")
    lines.append(f"- Success rate: {summary['success_rate']}")
    lines.append(f"- Mean score delta: {summary['mean_score_delta']}")
    lines.append(f"- Max score delta: {summary['max_score_delta']}")
    lines.append("")
    lines.append("Transitions:")
    for transition, count in sorted(summary["transitions"].items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {transition}: {count}")
    lines.append("")
    lines.append("## Top Repaired Candidates")
    lines.append("")
    for index, result in enumerate(report["top_repaired_candidates"], start=1):
        candidate = result["candidate"]
        lines.append(f"### {index}. {candidate['candidate_id']} score={result['score']}")
        lines.append("")
        lines.append(f"- task: {candidate['task']}")
        lines.append(f"- dsl: `{candidate['dsl']}`")
        lines.append(f"- answer: `{result['answer']}`")
        lines.append(f"- normal form: `{result.get('normal_form', {}).get('normal_form')}`")
        lines.append("")
        lines.append("```tex")
        lines.append(result["problem_tex"])
        lines.append("```")
        lines.append("")
    lines.append("## Repair Traces")
    lines.append("")
    for trace in report["traces"][:20]:
        lines.append(
            f"- {trace['original']['candidate_id']}: "
            f"{trace['original']['phase']}({trace['original']['score']}) -> "
            f"{trace['final']['phase']}({trace['final']['score']}) "
            f"success={trace['successful']}"
        )
        for step in trace["steps"]:
            action = step["action"]
            lines.append(
                f"  - step {step['step_index']} {action['kind']} patch={action['patch']}: "
                f"{step['before']['phase']} -> {step['after']['phase']}, "
                f"score {step['before']['score']} -> {step['after']['score']}"
            )
    lines.append("")
    lines.append("## Curriculum Export")
    lines.append("")
    lines.append(f"- Verified curriculum items: {len(report.get('curriculum_items', []))}")
    lines.append(
        "These are the generated problems that can be fed back into the solver benchmark "
        "as parser/router/strategy regression cases without storing problem-specific answers in code."
    )
    return "\n".join(lines) + "\n"


def render_repair_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Problem Repair Loop Report")
    lines.append("")
    lines.append(f"Generated: {report['generated_at']}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    summary = report["summary"]
    lines.append(f"- Attempted: {summary['attempted']}")
    lines.append(f"- Successful: {summary['successful']}")
    lines.append(f"- Success rate: {summary['success_rate']}")
    lines.append(f"- Mean score delta: {summary['mean_score_delta']}")
    lines.append(f"- Max score delta: {summary['max_score_delta']}")
    lines.append("")
    lines.append("Transitions:")
    for transition, count in sorted(summary["transitions"].items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {transition}: {count}")
    lines.append("")
    lines.append("## Top Repaired Candidates")
    lines.append("")
    for index, result in enumerate(report["top_repaired_candidates"][:10], start=1):
        candidate = result["candidate"]
        lines.append(f"### {index}. {candidate['candidate_id']} score={result['score']}")
        lines.append("")
        lines.append(f"- params: alpha={candidate['alpha']}, beta={candidate['beta']}, gamma={candidate['gamma']}, p={candidate['p']}")
        lines.append(f"- answer: ${result['answer_tex']}$")
        lines.append(f"- difficulty: {result['estimated_difficulty']['level']} ({', '.join(result['estimated_difficulty']['proof_obligations'])})")
        lines.append("")
        lines.append("```tex")
        lines.append(result["problem_tex"])
        lines.append("```")
        lines.append("")
    lines.append("## Repair Traces")
    lines.append("")
    for trace in report["traces"][:20]:
        lines.append(
            f"- {trace['original']['candidate_id']}: "
            f"{trace['original']['phase']}({trace['original']['score']}) -> "
            f"{trace['final']['phase']}({trace['final']['score']}) "
            f"success={trace['successful']}"
        )
        for step in trace["steps"]:
            action = step["action"]
            lines.append(
                f"  - step {step['step_index']} {action['kind']} patch={action['patch']}: "
                f"{step['before']['phase']} -> {step['after']['phase']}, "
                f"score {step['before']['score']} -> {step['after']['score']}"
            )
    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append(
        "This is the first point where MathOS is not only sampling candidates but "
        "also changing bad candidates into better ones.  `fix_domain` repairs "
        "log-domain failures, `move_to_finite_phase` moves divergent/vanishing "
        "limits onto the finite boundary, and `increase_nontriviality` hides a "
        "too-direct asymptotic constant with a harmless floor shift."
    )
    return "\n".join(lines) + "\n"


def parse_fraction(text: str) -> Fraction:
    text = text.strip()
    if "/" in text:
        numerator, denominator = text.split("/", 1)
        return Fraction(int(numerator), int(denominator))
    return Fraction(int(text), 1)


def run_phase_synthesis(*, limit: int, top_k: int) -> PhaseDiagram:
    candidates = generate_candidates(limit=limit)
    results = [evaluate_candidate(candidate) for candidate in candidates]
    return build_phase_diagram(results, family=FLOOR_LOG_FAMILY, top_k=top_k)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run MathOS Problem Phase Diagram Synthesis.")
    parser.add_argument("--theme", choices=["floor-log", "geometry"], default="floor-log")
    parser.add_argument("--limit", type=int, default=120, help="Number of candidates to generate.")
    parser.add_argument("--top-k", type=int, default=8, help="Number of top candidates to show.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--prefix", default="floor_log_phase0")
    parser.add_argument("--repair", action="store_true", help="Run candidate repair loop instead of only phase synthesis.")
    parser.add_argument("--repair-limit", type=int, default=80, help="Number of non-good candidates to attempt repairing.")
    parser.add_argument("--max-repair-steps", type=int, default=4)
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    if args.theme == "geometry":
        if args.repair:
            report = run_geometry_repair_experiment(
                limit=args.limit,
                repair_limit=args.repair_limit,
                max_steps=args.max_repair_steps,
                top_k=args.top_k,
            )
            json_path, md_path = write_geometry_repair_outputs(report, output_dir=args.output_dir, prefix=args.prefix)
            print(
                json.dumps(
                    {
                        "ok": True,
                        "json": str(json_path),
                        "report": str(md_path),
                        "summary": report["summary"],
                        "curriculum_items": len(report.get("curriculum_items", [])),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        report = run_geometry_phase_synthesis(limit=args.limit, top_k=args.top_k)
        json_path, md_path = write_geometry_outputs(report, output_dir=args.output_dir, prefix=args.prefix)
        print(
            json.dumps(
                {
                    "ok": True,
                    "json": str(json_path),
                    "report": str(md_path),
                    "total_candidates": report["total_candidates"],
                    "phase_counts": report["phase_counts"],
                    "label_counts": report["label_counts"],
                    "top_count": len(report["top_candidates"]),
                    "curriculum_items": len(report.get("curriculum_items", [])),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.repair:
        repair_report = run_repair_experiment(
            limit=args.limit,
            repair_limit=args.repair_limit,
            max_steps=args.max_repair_steps,
            top_k=args.top_k,
        )
        json_path, md_path = write_repair_outputs(repair_report, output_dir=args.output_dir, prefix=args.prefix)
        print(
            json.dumps(
                {
                    "ok": True,
                    "json": str(json_path),
                    "report": str(md_path),
                    "summary": repair_report["summary"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    diagram = run_phase_synthesis(limit=args.limit, top_k=args.top_k)
    json_path, jsonl_path, md_path = write_outputs(diagram, output_dir=args.output_dir, prefix=args.prefix)
    print(
        json.dumps(
            {
                "ok": True,
                "json": str(json_path),
                "jsonl": str(jsonl_path),
                "report": str(md_path),
                "total_candidates": diagram.total_candidates,
                "phase_counts": diagram.phase_counts,
                "label_counts": diagram.label_counts,
                "top_count": len(diagram.top_candidates),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
