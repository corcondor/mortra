"""Generalization benchmark protocol for MathOS.

This runner implements the nine checks requested for the current MathOS kernel:

1. same-structure pair generation
2. surface transformation
3. numeric transformation
4. held-out split
5. LiftCertificate match rate
6. backend success rate
7. wrong-answer rate
8. rejection rate
9. surface-template ablation

The generated answers are evaluation oracles only.  They are not passed into the
solver.  The solver sees only the problem text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from fractions import Fraction
from math import comb, isqrt
from pathlib import Path
from typing import Any

try:
    import sympy as sp
except ImportError:  # pragma: no cover
    sp = None

try:
    from math_os_prototype.category_semantics import compile_typed_semantic_graph
    from math_os_prototype.lift_backend import solve_from_lift_certificates
    from math_os_prototype.public_benchmark import answers_match, normalize_answer
    from math_os_prototype.reasoning_pipeline import run_reasoning_pipeline
    from math_os_prototype.web_app import extract_answer_from_pipeline_data
except ImportError:  # Allows direct script execution.
    from category_semantics import compile_typed_semantic_graph
    from lift_backend import solve_from_lift_certificates
    from public_benchmark import answers_match, normalize_answer
    from reasoning_pipeline import run_reasoning_pipeline
    from web_app import extract_answer_from_pipeline_data


DEFAULT_OUTPUT = Path("math_os_prototype/generalization_benchmark_protocol.json")


@dataclass(frozen=True)
class GeneralizationCase:
    case_id: str
    family_id: str
    pair_group: str
    split: str
    transform: str
    problem: str
    expected: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class SameStructurePair:
    pair_id: str
    family_id: str
    left_case_id: str
    right_case_id: str
    transform: str
    split: str


@dataclass
class GeneralizationRecord:
    mode: str
    case_id: str
    family_id: str
    pair_group: str
    split: str
    transform: str
    expected: str
    answer: str | None
    exact_match: bool
    answered: bool
    wrong: bool
    rejected: bool
    lift_admissible: bool
    lift_family_match: bool
    certificate_signatures: list[str]
    parser_intent: str
    verifier_status: str
    error: str | None
    problem: str


def ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def split_for(group_key: str) -> str:
    bucket = int(hashlib.sha256(group_key.encode("utf-8")).hexdigest()[:8], 16) % 10
    if bucket < 6:
        return "dev"
    if bucket < 8:
        return "calib"
    return "held_out"


def format_fraction(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def sqrt_answer(value: int) -> str:
    root = isqrt(value)
    if root * root == value:
        return str(root)
    return f"sqrt({value})"


def make_case(
    *,
    family_id: str,
    seed: int,
    variant: str,
    transform: str,
    problem: str,
    expected: str,
    metadata: dict[str, Any],
) -> GeneralizationCase:
    pair_group = f"{family_id}:{seed}"
    return GeneralizationCase(
        case_id=f"{family_id}:{seed}:{variant}",
        family_id=family_id,
        pair_group=pair_group,
        split=split_for(pair_group),
        transform=transform,
        problem=problem,
        expected=expected,
        metadata=metadata,
    )


def generate_generalization_cases(seeds: int = 8) -> list[GeneralizationCase]:
    cases: list[GeneralizationCase] = []
    triples = [(3, 4, 5), (5, 12, 13), (8, 15, 17), (7, 24, 25), (20, 21, 29), (9, 40, 41)]
    for seed in range(seeds):
        # Discrete affine sequence: same recurrence, different text/numbers.
        n = 12 + seed * 7
        a = 2 + seed
        d = 3 + (seed % 5)
        b = a + d
        answer = str(a + (n - 1) * d)
        family = "discrete_affine_sequence.nth_term"
        cases.extend(
            [
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="base",
                    transform="base",
                    problem=f"Find the {ordinal(n)} term of the arithmetic sequence whose first term is {a} and second term is {b}.",
                    expected=answer,
                    metadata={"n": n, "a": a, "d": d},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="surface",
                    transform="surface",
                    problem=f"In an arithmetic sequence, the first term is {a} and the second term is {b}. What is the {ordinal(n)} term?",
                    expected=answer,
                    metadata={"n": n, "a": a, "d": d},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="numeric",
                    transform="numeric",
                    problem=f"Find the {ordinal(n + 2)} term of the arithmetic sequence whose first term is {a + 1} and second term is {b + 2}.",
                    expected=str((a + 1) + ((n + 2) - 1) * ((b + 2) - (a + 1))),
                    metadata={"n": n + 2, "a": a + 1, "d": (b + 2) - (a + 1)},
                ),
            ]
        )

        # Inner-product distance.
        x, y, hyp = triples[seed % len(triples)]
        family = "inner_product_geometry.distance"
        cases.extend(
            [
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="base",
                    transform="base",
                    problem=f"Find the distance from the origin to the point ({x},{y}).",
                    expected=str(hyp),
                    metadata={"x": x, "y": y},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="surface",
                    transform="surface",
                    problem=f"Compute the distance from the origin to the point ({x},{y}).",
                    expected=str(hyp),
                    metadata={"x": x, "y": y},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="numeric",
                    transform="numeric",
                    problem=f"Find the distance from the origin to the point ({x + 1},{y + 2}).",
                    expected=sqrt_answer((x + 1) ** 2 + (y + 2) ** 2),
                    metadata={"x": x + 1, "y": y + 2},
                ),
            ]
        )

        # Affine midpoint observable.
        x1, y1 = seed + 2, 2 * seed + 6
        x2, y2 = seed + 8, 2 * seed + 10
        answer_fraction = Fraction(x1 + x2 + y1 + y2, 2)
        family = "affine_geometry.midpoint_observable"
        cases.extend(
            [
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="base",
                    transform="base",
                    problem=f"Find the sum of the coordinates of the midpoint of ({x1},{y1}) and ({x2},{y2}).",
                    expected=format_fraction(answer_fraction),
                    metadata={"points": [(x1, y1), (x2, y2)]},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="surface",
                    transform="surface",
                    problem=f"Compute the sum of the coordinates of the midpoint of ({x1},{y1}) and ({x2},{y2}).",
                    expected=format_fraction(answer_fraction),
                    metadata={"points": [(x1, y1), (x2, y2)]},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="numeric",
                    transform="numeric",
                    problem=f"Find the sum of the coordinates of the midpoint of ({x1 + 1},{y1}) and ({x2},{y2 + 3}).",
                    expected=format_fraction(Fraction((x1 + 1) + x2 + y1 + (y2 + 3), 2)),
                    metadata={"points": [(x1 + 1, y1), (x2, y2 + 3)]},
                ),
            ]
        )

        # Quotient ring residue.
        base = 2 + seed
        exponent = 8 + seed
        modulus = 5 + 2 * (seed % 5)
        family = "quotient_ring.residue"
        cases.extend(
            [
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="base",
                    transform="base",
                    problem=f"What is the remainder of {base}^{exponent} when it is divided by {modulus}?",
                    expected=str(pow(base, exponent, modulus)),
                    metadata={"base": base, "exponent": exponent, "modulus": modulus},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="surface",
                    transform="surface",
                    problem=f"Compute the remainder of {base}^{exponent} when divided by {modulus}.",
                    expected=str(pow(base, exponent, modulus)),
                    metadata={"base": base, "exponent": exponent, "modulus": modulus},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="numeric",
                    transform="numeric",
                    problem=f"What is the remainder of {base + 1}^{exponent + 2} when it is divided by {modulus + 2}?",
                    expected=str(pow(base + 1, exponent + 2, modulus + 2)),
                    metadata={"base": base + 1, "exponent": exponent + 2, "modulus": modulus + 2},
                ),
            ]
        )

        # Ordered-field percent scalar action.
        bill = 40 + 5 * seed
        percent = 10 + 5 * (seed % 4)
        paid = bill + Fraction(bill * percent, 100)
        family = "ordered_field.scalar_percent_action"
        cases.extend(
            [
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="base",
                    transform="base",
                    problem=f"What percent tip is paid if a ${bill} bill is paid with ${format_fraction(paid)}?",
                    expected=str(percent),
                    metadata={"bill": bill, "paid": format_fraction(paid)},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="surface",
                    transform="surface",
                    problem=f"A ${bill} bill is paid with ${format_fraction(paid)}. Find the percent tip.",
                    expected=str(percent),
                    metadata={"bill": bill, "paid": format_fraction(paid)},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="numeric",
                    transform="numeric",
                    problem=f"What percent tip is paid if a ${bill + 10} bill is paid with ${format_fraction(Fraction((bill + 10) * (100 + percent), 100))}?",
                    expected=str(percent),
                    metadata={"bill": bill + 10, "paid": format_fraction(Fraction((bill + 10) * (100 + percent), 100))},
                ),
            ]
        )

        # Clock as circle group action.
        hour = 1 + (seed % 11)
        angle = min(30 * (hour % 12), 360 - 30 * (hour % 12))
        family = "circle_group.clock_angle"
        cases.extend(
            [
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="base",
                    transform="base",
                    problem=f"A clock reads {hour}:00. What is the smaller angle between the hands?",
                    expected=str(angle),
                    metadata={"hour": hour},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="surface",
                    transform="surface",
                    problem=f"When a clock reads {hour}:00, compute the smaller angle between the hands.",
                    expected=str(angle),
                    metadata={"hour": hour},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="numeric",
                    transform="numeric",
                    problem=f"A clock reads {((hour + 3 - 1) % 12) + 1}:00. What is the smaller angle between the hands?",
                    expected=str(min(30 * (((hour + 3 - 1) % 12) + 1), 360 - 30 * (((hour + 3 - 1) % 12) + 1))),
                    metadata={"hour": ((hour + 3 - 1) % 12) + 1},
                ),
            ]
        )

        # Probability complement.
        numerator = 1 + (seed % 4)
        denominator = numerator + 3 + (seed % 3)
        p = Fraction(numerator, denominator)
        family = "probability.complement_event"
        cases.extend(
            [
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="base",
                    transform="base",
                    problem=f"The probability that event A occurs is {format_fraction(p)}. What is the probability that event A does not occur?",
                    expected=format_fraction(1 - p),
                    metadata={"p": format_fraction(p)},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="surface",
                    transform="surface",
                    problem=f"If the probability that a result happens equals {format_fraction(p)}, compute the probability that it does not happen.",
                    expected=format_fraction(1 - p),
                    metadata={"p": format_fraction(p)},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="numeric",
                    transform="numeric",
                    problem=f"The probability that event A occurs is {format_fraction(Fraction(numerator + 1, denominator + 2))}. What is the probability that event A does not occur?",
                    expected=format_fraction(1 - Fraction(numerator + 1, denominator + 2)),
                    metadata={"p": format_fraction(Fraction(numerator + 1, denominator + 2))},
                ),
            ]
        )

        # Absolute-value equation over ordered fields.
        a = seed + 1
        b_abs = seed + 5
        family = "ordered_field.absolute_value_equation"
        expected_abs = str(min_absolute_value_solutions(1, a, 2, -b_abs))
        cases.extend(
            [
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="base",
                    transform="base",
                    problem=f"Find the smallest solution of |x + {a}| = |2*x - {b_abs}|.",
                    expected=expected_abs,
                    metadata={"a": a, "b": b_abs},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="surface",
                    transform="surface",
                    problem=f"Solve |x + {a}| = |2*x - {b_abs}| and give the smallest value of x.",
                    expected=expected_abs,
                    metadata={"a": a, "b": b_abs},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="numeric",
                    transform="numeric",
                    problem=f"Find the smallest solution of |x + {a + 2}| = |2*x - {b_abs + 3}|.",
                    expected=str(min_absolute_value_solutions(1, a + 2, 2, -(b_abs + 3))),
                    metadata={"a": a + 2, "b": b_abs + 3},
                ),
            ]
        )

        # Quadratic interval over real closed fields.
        left_root = -(seed + 1)
        right_root = seed + 4
        b_quad = -(left_root + right_root)
        c_quad = left_root * right_root
        family = "real_closed_field.quadratic_interval"
        cases.extend(
            [
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="base",
                    transform="base",
                    problem=f"For what values of x is x^2 {signed_term(b_quad)}*x {signed_term(c_quad)} <= 0?",
                    expected=f"x \\in [{left_root},{right_root}]",
                    metadata={"roots": [left_root, right_root]},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="surface",
                    transform="surface",
                    problem=f"Solve x^2 {signed_term(b_quad)}*x {signed_term(c_quad)} <= 0 for x.",
                    expected=f"x \\in [{left_root},{right_root}]",
                    metadata={"roots": [left_root, right_root]},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="numeric",
                    transform="numeric",
                    problem=f"For what values of x is x^2 {signed_term(b_quad - 2)}*x {signed_term((left_root - 1) * (right_root + 3))} <= 0?",
                    expected=f"x \\in [{left_root - 1},{right_root + 3}]",
                    metadata={"roots": [left_root - 1, right_root + 3]},
                ),
            ]
        )

        # Compound growth rate.
        years = 2 + (seed % 3)
        rate = 5 + 5 * (seed % 4)
        principal = 100**years
        final_amount = Fraction(principal * (100 + rate) ** years, 100**years)
        family = "ordered_field.compound_growth_rate"
        cases.extend(
            [
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="base",
                    transform="base",
                    problem=f"Alex invests {principal} dollars. It compounds annually. After {years} years it has grown to {format_fraction(final_amount)} dollars. What is the interest rate?",
                    expected=str(rate),
                    metadata={"years": years, "rate": rate},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="surface",
                    transform="surface",
                    problem=f"An investment of {principal} dollars compounds annually and has grown to {format_fraction(final_amount)} dollars after {years} years. Find the interest rate.",
                    expected=str(rate),
                    metadata={"years": years, "rate": rate},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="numeric",
                    transform="numeric",
                    problem=f"Alex invests {principal * 2} dollars. It compounds annually. After {years} years it has grown to {format_fraction(Fraction((principal * 2) * (100 + rate) ** years, 100**years))} dollars. What is the interest rate?",
                    expected=str(rate),
                    metadata={"years": years, "rate": rate},
                ),
            ]
        )

        # Base notation as polynomial evaluation.
        base_value = 6 + (seed % 5)
        addend = base_value - 1
        family = "polynomial_notation.base_expansion"
        cases.extend(
            [
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="base",
                    transform="base",
                    problem=f"For what positive base b is the equation 12_b + {addend} = 21_b is valid?",
                    expected=str(base_value),
                    metadata={"base": base_value},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="surface",
                    transform="surface",
                    problem=f"Find the positive base b for which the equation 12_b + {addend} = 21_b is valid.",
                    expected=str(base_value),
                    metadata={"base": base_value},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="numeric",
                    transform="numeric",
                    problem=f"For what positive base b is the equation 13_b + {base_value - 2} = 21_b is valid?",
                    expected=str(base_value),
                    metadata={"base": base_value},
                ),
            ]
        )

        # Quadratic equation root observable via Vieta.
        r1 = seed + 1
        r2 = seed + 4
        b_vieta = -(r1 + r2)
        c_vieta = r1 * r2
        family = "real_closed_field.quadratic_root_observable"
        cases.extend(
            [
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="base",
                    transform="base",
                    problem=f"The roots of x^2 {signed_term(b_vieta)}*x {signed_term(c_vieta)} = 0 are alpha and beta. Find the sum of the roots.",
                    expected=str(r1 + r2),
                    metadata={"roots": [r1, r2]},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="surface",
                    transform="surface",
                    problem=f"For the quadratic equation x^2 {signed_term(b_vieta)}*x {signed_term(c_vieta)} = 0, compute the sum of its roots.",
                    expected=str(r1 + r2),
                    metadata={"roots": [r1, r2]},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="numeric",
                    transform="numeric",
                    problem=f"The roots of x^2 {signed_term(-(r1 + r2 + 3))}*x {signed_term((r1 + 1) * (r2 + 2))} = 0 are alpha and beta. Find the sum of the roots.",
                    expected=str((r1 + 1) + (r2 + 2)),
                    metadata={"roots": [r1 + 1, r2 + 2]},
                ),
            ]
        )

        # Polynomial remainder theorem.
        a_poly = 1 + (seed % 4)
        b_poly = seed + 2
        c_poly = 3 * seed + 1
        t_poly = seed + 2
        family = "polynomial_ring.remainder_linear_divisor"
        poly_text = f"{a_poly}*x^2 + {b_poly}*x + {c_poly}"
        cases.extend(
            [
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="base",
                    transform="base",
                    problem=f"Find the remainder of {poly_text} when divided by x - {t_poly}.",
                    expected=str(a_poly * t_poly**2 + b_poly * t_poly + c_poly),
                    metadata={"a": a_poly, "b": b_poly, "c": c_poly, "t": t_poly},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="surface",
                    transform="surface",
                    problem=f"What is the remainder of {poly_text} when it is divided by x - {t_poly}?",
                    expected=str(a_poly * t_poly**2 + b_poly * t_poly + c_poly),
                    metadata={"a": a_poly, "b": b_poly, "c": c_poly, "t": t_poly},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="numeric",
                    transform="numeric",
                    problem=f"Find the remainder of {a_poly + 1}*x^2 + {b_poly + 2}*x + {c_poly + 3} when divided by x - {t_poly + 1}.",
                    expected=str((a_poly + 1) * (t_poly + 1) ** 2 + (b_poly + 2) * (t_poly + 1) + c_poly + 3),
                    metadata={"a": a_poly + 1, "b": b_poly + 2, "c": c_poly + 3, "t": t_poly + 1},
                ),
            ]
        )

        # Repeated linear divisor remainder via Taylor jet.
        n_power = 5 + seed
        root_power = 1 + (seed % 3)
        family = "polynomial_ring.remainder_repeated_linear_divisor"
        cases.extend(
            [
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="base",
                    transform="base",
                    problem=f"Find the remainder of x^{n_power} when divided by (x - {root_power})^2.",
                    expected=repeated_linear_remainder_answer(n_power, root_power),
                    metadata={"n": n_power, "a": root_power},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="surface",
                    transform="surface",
                    problem=f"What is the remainder when x^{n_power} is divided by (x - {root_power})^2?",
                    expected=repeated_linear_remainder_answer(n_power, root_power),
                    metadata={"n": n_power, "a": root_power},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="numeric",
                    transform="numeric",
                    problem=f"Find the remainder of x^{n_power + 1} when divided by (x - {root_power + 1})^2.",
                    expected=repeated_linear_remainder_answer(n_power + 1, root_power + 1),
                    metadata={"n": n_power + 1, "a": root_power + 1},
                ),
            ]
        )

        # 2x2 linear system as a vector-space coordinate problem.
        x0 = seed + 2
        y0 = seed + 3
        a1, b1 = 2 + (seed % 3), 1 + (seed % 2)
        a2, b2 = 1 + (seed % 4), -(2 + (seed % 3))
        c1 = a1 * x0 + b1 * y0
        c2 = a2 * x0 + b2 * y0
        family = "vector_space.linear_system_2x2"
        cases.extend(
            [
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="base",
                    transform="base",
                    problem=f"Solve the system {a1}*x {signed_term(b1)}*y = {c1} and {a2}*x {signed_term(b2)}*y = {c2}. Find x + y.",
                    expected=str(x0 + y0),
                    metadata={"solution": [x0, y0]},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="surface",
                    transform="surface",
                    problem=f"For the system {a1}*x {signed_term(b1)}*y = {c1} and {a2}*x {signed_term(b2)}*y = {c2}, compute x + y.",
                    expected=str(x0 + y0),
                    metadata={"solution": [x0, y0]},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="numeric",
                    transform="numeric",
                    problem=f"Solve the system {a1 + 1}*x {signed_term(b1)}*y = {(a1 + 1) * (x0 + 1) + b1 * (y0 + 2)} and {a2}*x {signed_term(b2 - 1)}*y = {a2 * (x0 + 1) + (b2 - 1) * (y0 + 2)}. Find x + y.",
                    expected=str((x0 + 1) + (y0 + 2)),
                    metadata={"solution": [x0 + 1, y0 + 2]},
                ),
            ]
        )

        # Logarithm and exponential inverse charts.
        log_base = 2 + (seed % 4)
        log_value = 2 + (seed % 5)
        family = "elementary_functions.log_equation"
        cases.extend(
            [
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="base",
                    transform="base",
                    problem=f"If log base {log_base} of x equals {log_value}, find x.",
                    expected=str(log_base**log_value),
                    metadata={"base": log_base, "value": log_value},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="surface",
                    transform="surface",
                    problem=f"Solve log base {log_base} of x = {log_value}.",
                    expected=str(log_base**log_value),
                    metadata={"base": log_base, "value": log_value},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="numeric",
                    transform="numeric",
                    problem=f"If log base {log_base + 1} of x equals {log_value + 1}, find x.",
                    expected=str((log_base + 1) ** (log_value + 1)),
                    metadata={"base": log_base + 1, "value": log_value + 1},
                ),
            ]
        )

        exp_base = 2 + (seed % 3)
        exp_value = 3 + (seed % 5)
        family = "elementary_functions.exponential_equation"
        cases.extend(
            [
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="base",
                    transform="base",
                    problem=f"Solve {exp_base}^x = {exp_base**exp_value} for x.",
                    expected=str(exp_value),
                    metadata={"base": exp_base, "value": exp_value},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="surface",
                    transform="surface",
                    problem=f"If {exp_base}^x = {exp_base**exp_value}, compute x.",
                    expected=str(exp_value),
                    metadata={"base": exp_base, "value": exp_value},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="numeric",
                    transform="numeric",
                    problem=f"Solve {exp_base + 1}^x = {(exp_base + 1) ** (exp_value + 1)} for x.",
                    expected=str(exp_value + 1),
                    metadata={"base": exp_base + 1, "value": exp_value + 1},
                ),
            ]
        )

        # Trigonometric unit-circle invariant.
        sin_num = 1 + (seed % 3)
        sin_den = sin_num + 3
        family = "elementary_functions.trig_pythagorean"
        cases.extend(
            [
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="base",
                    transform="base",
                    problem=f"If sin(theta) = {sin_num}/{sin_den} and theta is acute, find cos^2(theta).",
                    expected=format_fraction(1 - Fraction(sin_num, sin_den) ** 2),
                    metadata={"sin": [sin_num, sin_den]},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="surface",
                    transform="surface",
                    problem=f"Given sin(theta) = {sin_num}/{sin_den} for an acute angle, compute cos^2(theta).",
                    expected=format_fraction(1 - Fraction(sin_num, sin_den) ** 2),
                    metadata={"sin": [sin_num, sin_den]},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="numeric",
                    transform="numeric",
                    problem=f"If sin(theta) = {sin_num + 1}/{sin_den + 2} and theta is acute, find cos^2(theta).",
                    expected=format_fraction(1 - Fraction(sin_num + 1, sin_den + 2) ** 2),
                    metadata={"sin": [sin_num + 1, sin_den + 2]},
                ),
            ]
        )

        # Combinatorics and binomial probability.
        n_choose = 7 + seed
        k_choose = 2 + (seed % 3)
        family = "combinatorics.binomial_coefficient"
        cases.extend(
            [
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="base",
                    transform="base",
                    problem=f"How many ways are there to choose {k_choose} objects from {n_choose} objects?",
                    expected=str(comb(n_choose, k_choose)),
                    metadata={"n": n_choose, "k": k_choose},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="surface",
                    transform="surface",
                    problem=f"Select {k_choose} students from {n_choose} students. How many ways?",
                    expected=str(comb(n_choose, k_choose)),
                    metadata={"n": n_choose, "k": k_choose},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="numeric",
                    transform="numeric",
                    problem=f"How many ways are there to choose {k_choose + 1} objects from {n_choose + 2} objects?",
                    expected=str(comb(n_choose + 2, k_choose + 1)),
                    metadata={"n": n_choose + 2, "k": k_choose + 1},
                ),
            ]
        )

        n_trials = 4 + (seed % 4)
        k_success = 1 + (seed % min(3, n_trials))
        p_success = Fraction(1 + (seed % 2), 3 + (seed % 3))
        family = "probability.binomial_exact"
        expected_prob = Fraction(comb(n_trials, k_success)) * p_success**k_success * (1 - p_success) ** (n_trials - k_success)
        cases.extend(
            [
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="base",
                    transform="base",
                    problem=f"In {n_trials} independent trials with success probability {format_fraction(p_success)}, what is the probability of exactly {k_success} successes?",
                    expected=format_fraction(expected_prob),
                    metadata={"n": n_trials, "k": k_success, "p": format_fraction(p_success)},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="surface",
                    transform="surface",
                    problem=f"There are {n_trials} independent trials, each with success probability {format_fraction(p_success)}. Find the probability of exactly {k_success} successes.",
                    expected=format_fraction(expected_prob),
                    metadata={"n": n_trials, "k": k_success, "p": format_fraction(p_success)},
                ),
                make_case(
                    family_id=family,
                    seed=seed,
                    variant="numeric",
                    transform="numeric",
                    problem=f"In {n_trials + 1} independent trials with success probability {format_fraction(p_success)}, what is the probability of exactly {k_success} successes?",
                    expected=format_fraction(Fraction(comb(n_trials + 1, k_success)) * p_success**k_success * (1 - p_success) ** (n_trials + 1 - k_success)),
                    metadata={"n": n_trials + 1, "k": k_success, "p": format_fraction(p_success)},
                ),
            ]
        )

        # Vector and coordinate geometry.
        u1, u2 = seed + 1, seed + 3
        v1, v2 = 2 * seed + 1, -(seed + 2)
        family = "inner_product_geometry.dot_product"
        cases.extend(
            [
                make_case(family_id=family, seed=seed, variant="base", transform="base", problem=f"Find the dot product of vectors ({u1},{u2}) and ({v1},{v2}).", expected=str(u1 * v1 + u2 * v2), metadata={"u": [u1, u2], "v": [v1, v2]}),
                make_case(family_id=family, seed=seed, variant="surface", transform="surface", problem=f"Compute the dot product of ({u1},{u2}) and ({v1},{v2}).", expected=str(u1 * v1 + u2 * v2), metadata={"u": [u1, u2], "v": [v1, v2]}),
                make_case(family_id=family, seed=seed, variant="numeric", transform="numeric", problem=f"Find the dot product of vectors ({u1 + 1},{u2}) and ({v1},{v2 - 1}).", expected=str((u1 + 1) * v1 + u2 * (v2 - 1)), metadata={"u": [u1 + 1, u2], "v": [v1, v2 - 1]}),
            ]
        )

        m1, line_b1 = 1 + (seed % 4), seed + 2
        m2, line_b2 = -(2 + (seed % 3)), 3 * seed + 8
        family = "affine_geometry.line_intersection"
        line_sum = line_intersection_coordinate_sum(m1, line_b1, m2, line_b2)
        cases.extend(
            [
                make_case(family_id=family, seed=seed, variant="base", transform="base", problem=f"Find the sum of the coordinates of the intersection of y = {m1}*x {signed_term(line_b1)} and y = {m2}*x {signed_term(line_b2)}.", expected=format_fraction(line_sum), metadata={"lines": [m1, line_b1, m2, line_b2]}),
                make_case(family_id=family, seed=seed, variant="surface", transform="surface", problem=f"Compute x+y for the intersection of y = {m1}*x {signed_term(line_b1)} and y = {m2}*x {signed_term(line_b2)}.", expected=format_fraction(line_sum), metadata={"lines": [m1, line_b1, m2, line_b2]}),
                make_case(family_id=family, seed=seed, variant="numeric", transform="numeric", problem=f"Find the sum of the coordinates of the intersection of y = {m1 + 1}*x {signed_term(line_b1)} and y = {m2}*x {signed_term(line_b2 + 2)}.", expected=format_fraction(line_intersection_coordinate_sum(m1 + 1, line_b1, m2, line_b2 + 2)), metadata={"lines": [m1 + 1, line_b1, m2, line_b2 + 2]}),
            ]
        )

        dx, dy, hyp = triples[seed % len(triples)]
        h, k0 = seed, -seed
        family = "euclidean_geometry.circle_radius"
        cases.extend(
            [
                make_case(family_id=family, seed=seed, variant="base", transform="base", problem=f"A circle with center ({h},{k0}) passes through ({h + dx},{k0 + dy}). Find its radius.", expected=str(hyp), metadata={"center": [h, k0], "point": [h + dx, k0 + dy]}),
                make_case(family_id=family, seed=seed, variant="surface", transform="surface", problem=f"Find the radius of the circle with center ({h},{k0}) passes through ({h + dx},{k0 + dy}).", expected=str(hyp), metadata={"center": [h, k0], "point": [h + dx, k0 + dy]}),
                make_case(family_id=family, seed=seed, variant="numeric", transform="numeric", problem=f"A circle with center ({h + 1},{k0}) passes through ({h + 1 + dx},{k0 + dy + 1}). Find its radius.", expected=sqrt_answer(dx**2 + (dy + 1) ** 2), metadata={"center": [h + 1, k0], "point": [h + 1 + dx, k0 + dy + 1]}),
            ]
        )

        # Polynomial calculus.
        a_calc = 1 + (seed % 4)
        b_calc = seed + 2
        c_calc = seed - 3
        t_calc = seed + 1
        family = "calculus.polynomial_derivative_value"
        cases.extend(
            [
                make_case(family_id=family, seed=seed, variant="base", transform="base", problem=f"Let f(x) = {a_calc}*x^2 {signed_term(b_calc)}*x {signed_term(c_calc)}. At x = {t_calc}, find the derivative value.", expected=str(2 * a_calc * t_calc + b_calc), metadata={"a": a_calc, "b": b_calc, "c": c_calc, "t": t_calc}),
                make_case(family_id=family, seed=seed, variant="surface", transform="surface", problem=f"For f(x) = {a_calc}*x^2 {signed_term(b_calc)}*x {signed_term(c_calc)}, at x = {t_calc}, compute the slope.", expected=str(2 * a_calc * t_calc + b_calc), metadata={"a": a_calc, "b": b_calc, "c": c_calc, "t": t_calc}),
                make_case(family_id=family, seed=seed, variant="numeric", transform="numeric", problem=f"Let f(x) = {a_calc + 1}*x^2 {signed_term(b_calc + 2)}*x {signed_term(c_calc)}. At x = {t_calc + 1}, find the derivative value.", expected=str(2 * (a_calc + 1) * (t_calc + 1) + b_calc + 2), metadata={"a": a_calc + 1, "b": b_calc + 2, "c": c_calc, "t": t_calc + 1}),
            ]
        )

        r_int = 2 + (seed % 4)
        family = "calculus.polynomial_definite_integral"
        cases.extend(
            [
                make_case(family_id=family, seed=seed, variant="base", transform="base", problem=f"Compute the integral from 0 to {r_int} of {a_calc}*x^2 {signed_term(b_calc)}*x {signed_term(c_calc)} dx.", expected=format_fraction(poly_integral_0_r(a_calc, b_calc, c_calc, r_int)), metadata={"a": a_calc, "b": b_calc, "c": c_calc, "r": r_int}),
                make_case(family_id=family, seed=seed, variant="surface", transform="surface", problem=f"Find the integral from 0 to {r_int} of {a_calc}*x^2 {signed_term(b_calc)}*x {signed_term(c_calc)} dx.", expected=format_fraction(poly_integral_0_r(a_calc, b_calc, c_calc, r_int)), metadata={"a": a_calc, "b": b_calc, "c": c_calc, "r": r_int}),
                make_case(family_id=family, seed=seed, variant="numeric", transform="numeric", problem=f"Compute the integral from 0 to {r_int + 1} of {a_calc + 1}*x^2 {signed_term(b_calc)}*x {signed_term(c_calc + 2)} dx.", expected=format_fraction(poly_integral_0_r(a_calc + 1, b_calc, c_calc + 2, r_int + 1)), metadata={"a": a_calc + 1, "b": b_calc, "c": c_calc + 2, "r": r_int + 1}),
            ]
        )
    return cases


def min_absolute_value_solutions(a: int, b: int, c: int, d: int) -> Fraction:
    solutions = []
    denom = a - c
    if denom:
        solutions.append(Fraction(d - b, denom))
    denom = a + c
    if denom:
        solutions.append(Fraction(-d - b, denom))
    return min(solutions)


def signed_term(value: int) -> str:
    return f"+ {value}" if value >= 0 else f"- {abs(value)}"


def digits_in_base_to_int(digits: str, base: int) -> int:
    value = 0
    for digit in digits:
        value = value * base + int(digit)
    return value


def line_intersection_coordinate_sum(m1: int, b1: int, m2: int, b2: int) -> Fraction:
    x = Fraction(b2 - b1, m1 - m2)
    y = m1 * x + b1
    return x + y


def poly_integral_0_r(a: int, b: int, c: int, r: int) -> Fraction:
    r_fraction = Fraction(r)
    return Fraction(a) * r_fraction**3 / 3 + Fraction(b) * r_fraction**2 / 2 + Fraction(c) * r_fraction


def repeated_linear_remainder_answer(n: int, a: int) -> str:
    constant = a**n
    slope = n * (a ** (n - 1))
    intercept = constant - slope * a
    if slope == 0:
        return str(intercept)
    if intercept == 0:
        return f"{slope}*x"
    sign = "+" if intercept > 0 else "-"
    return f"{slope}*x {sign} {abs(intercept)}"


def int_to_base_digits(value: int, base: int) -> str:
    if value == 0:
        return "0"
    digits = []
    while value:
        digits.append(str(value % base))
        value //= base
    return "".join(reversed(digits))


def generate_same_structure_pairs(cases: list[GeneralizationCase]) -> list[SameStructurePair]:
    by_group: dict[str, dict[str, GeneralizationCase]] = {}
    for case in cases:
        by_group.setdefault(case.pair_group, {})[case.transform] = case
    pairs: list[SameStructurePair] = []
    for pair_group, variants in sorted(by_group.items()):
        base = variants.get("base")
        if base is None:
            continue
        for transform in ("surface", "numeric"):
            other = variants.get(transform)
            if other is None:
                continue
            pairs.append(
                SameStructurePair(
                    pair_id=f"{base.case_id}::{other.case_id}",
                    family_id=base.family_id,
                    left_case_id=base.case_id,
                    right_case_id=other.case_id,
                    transform=transform,
                    split=base.split,
                )
            )
    return pairs


def certificate_signatures(certs: list[dict[str, Any]]) -> list[str]:
    return sorted(str(cert.get("canonical_signature") or "") for cert in certs if cert.get("canonical_signature"))


def evaluate_case(case: GeneralizationCase, *, mode: str) -> GeneralizationRecord:
    allow_specialized = mode == "surface_template_ablation"
    try:
        if mode == "certified_lift_backend":
            semantic_graph = compile_typed_semantic_graph(case.problem).to_dict()
            admissible_certs = [cert for cert in semantic_graph.get("lift_certificates", []) or [] if cert.get("admissible")]
            lift_family_match = any(cert.get("family_id") == case.family_id for cert in admissible_certs)
            backend_result = solve_from_lift_certificates(semantic_graph)
            answer = str(backend_result["answer_exact"]) if backend_result else None
            parser_intent = str(backend_result.get("provenance") if backend_result else "certified_lift_backend")
            verifier_status = str(semantic_graph.get("status") or "")
        else:
            result = run_reasoning_pipeline(case.problem, allow_specialized=allow_specialized)
            data = json.loads(result.to_json())
            semantic_graph = data.get("semantic_graph") or {}
            certs = semantic_graph.get("lift_certificates") or []
            admissible_certs = [cert for cert in certs if cert.get("admissible")]
            lift_family_match = any(cert.get("family_id") == case.family_id for cert in admissible_certs)
            answer = extract_answer_from_pipeline_data(data)
            parser_intent = str((data.get("parser") or {}).get("intent") or "")
            verifier_status = str((data.get("verifier_gate") or {}).get("status") or "")
        exact = answers_match(answer, case.expected)
        answered = answer is not None
        return GeneralizationRecord(
            mode=mode,
            case_id=case.case_id,
            family_id=case.family_id,
            pair_group=case.pair_group,
            split=case.split,
            transform=case.transform,
            expected=case.expected,
            answer=normalize_answer(answer) if answer is not None else None,
            exact_match=bool(exact),
            answered=answered,
            wrong=bool(answered and not exact),
            rejected=not bool(admissible_certs),
            lift_admissible=bool(admissible_certs),
            lift_family_match=lift_family_match,
            certificate_signatures=certificate_signatures(admissible_certs),
            parser_intent=parser_intent,
            verifier_status=verifier_status,
            error=None,
            problem=case.problem,
        )
    except Exception as exc:
        return GeneralizationRecord(
            mode=mode,
            case_id=case.case_id,
            family_id=case.family_id,
            pair_group=case.pair_group,
            split=case.split,
            transform=case.transform,
            expected=case.expected,
            answer=None,
            exact_match=False,
            answered=False,
            wrong=False,
            rejected=True,
            lift_admissible=False,
            lift_family_match=False,
            certificate_signatures=[],
            parser_intent="error",
            verifier_status="error",
            error=str(exc),
            problem=case.problem,
        )


def run_generalization_benchmark(seeds: int = 8, modes: list[str] | None = None) -> dict[str, Any]:
    modes = modes or ["cold", "certified_lift_backend", "surface_template_ablation"]
    cases = generate_generalization_cases(seeds=seeds)
    pairs = generate_same_structure_pairs(cases)
    records: list[GeneralizationRecord] = []
    for mode in modes:
        for case in cases:
            records.append(evaluate_case(case, mode=mode))
    return summarize_protocol(cases, pairs, records)


def summarize_protocol(
    cases: list[GeneralizationCase],
    pairs: list[SameStructurePair],
    records: list[GeneralizationRecord],
) -> dict[str, Any]:
    records_by_mode: dict[str, list[GeneralizationRecord]] = {}
    for record in records:
        records_by_mode.setdefault(record.mode, []).append(record)

    mode_summaries = {mode: summarize_records(mode_records, pairs) for mode, mode_records in records_by_mode.items()}
    ablation = summarize_ablation(records_by_mode.get("cold", []), records_by_mode.get("surface_template_ablation", []))
    generated = {
        "case_count": len(cases),
        "same_structure_pair_count": len(pairs),
        "family_counts": count_by([case.family_id for case in cases]),
        "split_counts": count_by([case.split for case in cases]),
        "transform_counts": count_by([case.transform for case in cases]),
    }
    return {
        "protocol": [
            "same_structure_pair_generation",
            "surface_transformation",
            "numeric_transformation",
            "held_out_split",
            "lift_certificate_match_rate",
            "backend_success_rate",
            "wrong_answer_rate",
            "rejection_rate",
            "surface_template_ablation",
        ],
        "generated": generated,
        "modes": mode_summaries,
        "surface_template_ablation": ablation,
        "cases": [asdict(case) for case in cases],
        "pairs": [asdict(pair) for pair in pairs],
        "records": [asdict(record) for record in records],
    }


def summarize_records(records: list[GeneralizationRecord], pairs: list[SameStructurePair]) -> dict[str, Any]:
    by_case = {record.case_id: record for record in records}
    total = len(records)
    answered = sum(record.answered for record in records)
    correct = sum(record.exact_match for record in records)
    wrong = sum(record.wrong for record in records)
    rejected = sum(record.rejected for record in records)
    lift_admissible = sum(record.lift_admissible for record in records)
    family_match = sum(record.lift_family_match for record in records)
    pair_checks = []
    for pair in pairs:
        left = by_case.get(pair.left_case_id)
        right = by_case.get(pair.right_case_id)
        if not left or not right:
            continue
        shared = sorted(set(left.certificate_signatures) & set(right.certificate_signatures))
        pair_checks.append(
            {
                "pair_id": pair.pair_id,
                "family_id": pair.family_id,
                "transform": pair.transform,
                "split": pair.split,
                "matched": bool(shared),
                "shared_signatures": shared,
            }
        )
    pair_match = sum(item["matched"] for item in pair_checks)
    return {
        "total": total,
        "answered": answered,
        "correct": correct,
        "wrong": wrong,
        "rejected": rejected,
        "lift_admissible": lift_admissible,
        "lift_family_match": family_match,
        "answered_rate": answered / total if total else 0.0,
        "backend_success_rate": correct / total if total else 0.0,
        "precision": correct / answered if answered else 0.0,
        "wrong_rate_total": wrong / total if total else 0.0,
        "wrong_rate_answered": wrong / answered if answered else 0.0,
        "rejection_rate": rejected / total if total else 0.0,
        "lift_admissible_rate": lift_admissible / total if total else 0.0,
        "lift_family_match_rate": family_match / total if total else 0.0,
        "lift_certificate_pair_match_rate": pair_match / len(pair_checks) if pair_checks else 0.0,
        "by_split": summarize_groups(records, "split"),
        "by_family": summarize_groups(records, "family_id"),
        "by_transform": summarize_groups(records, "transform"),
        "pair_checks": pair_checks,
    }


def summarize_groups(records: list[GeneralizationRecord], attr: str) -> dict[str, Any]:
    groups: dict[str, list[GeneralizationRecord]] = {}
    for record in records:
        groups.setdefault(str(getattr(record, attr)), []).append(record)
    output = {}
    for key, items in sorted(groups.items()):
        total = len(items)
        answered = sum(item.answered for item in items)
        correct = sum(item.exact_match for item in items)
        wrong = sum(item.wrong for item in items)
        rejected = sum(item.rejected for item in items)
        lift_family_match = sum(item.lift_family_match for item in items)
        output[key] = {
            "total": total,
            "answered": answered,
            "correct": correct,
            "wrong": wrong,
            "rejected": rejected,
            "backend_success_rate": correct / total if total else 0.0,
            "wrong_rate_total": wrong / total if total else 0.0,
            "rejection_rate": rejected / total if total else 0.0,
            "lift_family_match_rate": lift_family_match / total if total else 0.0,
        }
    return output


def summarize_ablation(cold: list[GeneralizationRecord], ablation: list[GeneralizationRecord]) -> dict[str, Any]:
    cold_by_id = {record.case_id: record for record in cold}
    ablation_by_id = {record.case_id: record for record in ablation}
    shared_ids = sorted(set(cold_by_id) & set(ablation_by_id))
    improved = []
    regressed = []
    unchanged = 0
    surface_intents = 0
    for case_id in shared_ids:
        left = cold_by_id[case_id]
        right = ablation_by_id[case_id]
        if right.parser_intent.startswith("arithmetic_nl_allfield_"):
            surface_intents += 1
        if not left.exact_match and right.exact_match:
            improved.append(case_id)
        elif left.exact_match and not right.exact_match:
            regressed.append(case_id)
        else:
            unchanged += 1
    return {
        "compared": len(shared_ids),
        "improved": len(improved),
        "regressed": len(regressed),
        "unchanged": unchanged,
        "surface_template_intent_count": surface_intents,
        "improved_case_ids": improved,
        "regressed_case_ids": regressed,
    }


def count_by(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def write_outputs(result: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    jsonl_path = output.with_suffix(".jsonl")
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for record in result["records"]:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    report_path = output.with_name(output.stem + "_report.md")
    report_path.write_text(render_markdown_report(result, output, jsonl_path), encoding="utf-8")


def render_markdown_report(result: dict[str, Any], output: Path, jsonl_path: Path) -> str:
    generated = result["generated"]
    lines = [
        "# Generalization Benchmark Protocol",
        "",
        "## Scope",
        "",
        "This report tests whether generated problems can be lifted to the same abstract structure before claiming generalization.",
        "",
        "## Protocol Coverage",
        "",
    ]
    for index, item in enumerate(result["protocol"], start=1):
        lines.append(f"{index}. {item}")
    lines.extend(
        [
            "",
            "## Generated Data",
            "",
            f"- cases: {generated['case_count']}",
            f"- same-structure pairs: {generated['same_structure_pair_count']}",
            f"- splits: `{generated['split_counts']}`",
            f"- transforms: `{generated['transform_counts']}`",
            "",
            "## Mode Summary",
            "",
            "| mode | total | lift family match | pair match | success | answered | wrong/answered | rejected |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for mode, summary in result["modes"].items():
        lines.append(
            "| {mode} | {total} | {lf:.3f} | {pm:.3f} | {bs:.3f} | {ar:.3f} | {wa:.3f} | {rr:.3f} |".format(
                mode=mode,
                total=summary["total"],
                lf=summary["lift_family_match_rate"],
                pm=summary["lift_certificate_pair_match_rate"],
                bs=summary["backend_success_rate"],
                ar=summary["answered_rate"],
                wa=summary["wrong_rate_answered"],
                rr=summary["rejection_rate"],
            )
        )
    lines.extend(
        [
            "",
            "## Split Summary",
            "",
            "| mode | split | total | success | wrong/total | rejected | lift family match |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for mode, summary in result["modes"].items():
        for split, item in summary["by_split"].items():
            lines.append(
                "| {mode} | {split} | {total} | {success:.3f} | {wrong:.3f} | {rejected:.3f} | {lift:.3f} |".format(
                    mode=mode,
                    split=split,
                    total=item["total"],
                    success=item["backend_success_rate"],
                    wrong=item["wrong_rate_total"],
                    rejected=item["rejection_rate"],
                    lift=item["lift_family_match_rate"],
                )
            )
    lines.extend(
        [
            "",
            "## Family Summary",
            "",
            "| mode | family | total | success | wrong/total | rejected |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for mode, summary in result["modes"].items():
        for family, item in summary["by_family"].items():
            lines.append(
                "| {mode} | `{family}` | {total} | {success:.3f} | {wrong:.3f} | {rejected:.3f} |".format(
                    mode=mode,
                    family=family,
                    total=item["total"],
                    success=item["backend_success_rate"],
                    wrong=item["wrong_rate_total"],
                    rejected=item["rejection_rate"],
                )
            )
    ablation = result["surface_template_ablation"]
    lines.extend(
        [
            "",
            "## Surface Template Ablation",
            "",
            f"- compared: {ablation['compared']}",
            f"- improved: {ablation['improved']}",
            f"- regressed: {ablation['regressed']}",
            f"- surface-template intents: {ablation['surface_template_intent_count']}",
            "",
            "## Files",
            "",
            f"- json: `{output}`",
            f"- jsonl: `{jsonl_path}`",
        ]
    )
    return "\n".join(lines) + "\n"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the MathOS generalization benchmark protocol.")
    parser.add_argument("--seeds", type=int, default=8)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--mode",
        action="append",
        choices=["cold", "certified_lift_backend", "surface_template_ablation"],
        help="Mode to run. May be passed multiple times. Defaults to both modes.",
    )
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    result = run_generalization_benchmark(seeds=args.seeds, modes=args.mode)
    write_outputs(result, args.output)
    summary = {
        "generated": result["generated"],
        "modes": {
            mode: {
                key: summary[key]
                for key in (
                    "total",
                    "lift_family_match_rate",
                    "lift_certificate_pair_match_rate",
                    "backend_success_rate",
                    "wrong_rate_answered",
                    "rejection_rate",
                )
            }
            for mode, summary in result["modes"].items()
        },
        "surface_template_ablation": result["surface_template_ablation"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json: {args.output}")
    print(f"jsonl: {args.output.with_suffix('.jsonl')}")
    print(f"report: {args.output.with_name(args.output.stem + '_report.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
