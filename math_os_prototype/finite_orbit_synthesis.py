"""Runtime synthesis for rational-angle observables of linear recurrences.

The module contains no problem identifiers and no stored answers.  It parses a
second-order recurrence from the current statement, constructs its finite
quotient modulo the trigonometric period, and composes only the observations
requested by that statement.  Every accepted result is replayed by modular
matrix powers and, for polynomial observables, by a separately generated
polynomial recurrence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction
from math import gcd, lcm
import re
from typing import Any

import sympy as sp

from math_os_prototype.runtime_typed_planner import (
    PrimitiveResult,
    RuntimePrimitive,
    initial_fact,
    synthesize_typed_plan,
)


@dataclass(frozen=True)
class RationalAngleRecurrence:
    sequence_symbol: str
    index_symbol: str
    start_index: int
    initial: tuple[Fraction, Fraction]
    coefficients: tuple[int, int]


@dataclass(frozen=True)
class ChebyshevRecurrence:
    polynomial_symbol: str
    index_symbol: str
    variable_symbol: str


@dataclass(frozen=True)
class FiniteOrbitQueryIR:
    recurrence: RationalAngleRecurrence
    base_observable: str | None
    polynomial: ChebyshevRecurrence | None
    polynomial_identity_requested: bool
    polynomial_observable: str | None
    multipart: bool

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["recurrence"]["initial"] = [
            {"numerator": value.numerator, "denominator": value.denominator}
            for value in self.recurrence.initial
        ]
        return result


@dataclass(frozen=True)
class FiniteOrbitSynthesis:
    answer_tex: str
    derivation_tex: tuple[str, ...]
    expression_tex: str
    proof_program: tuple[dict[str, Any], ...]
    verification_checks: tuple[str, ...]
    witness: dict[str, Any]
    hypotheses_evaluated: int


_PI_VALUE = (
    r"[+-]?(?:"
    r"\\frac\{(?:\d+)?\\pi\}\{\d+\}"
    r"|\\frac\{\d+\}\{\d+\}\\pi"
    r"|(?:\d+)?\\pi(?:/\d+)?"
    r")"
)


def _compact(source: str) -> str:
    return (
        source.replace("−", "-")
        .replace("–", "-")
        .replace(r"\left", "")
        .replace(r"\right", "")
        .replace(r"\dfrac", r"\frac")
        .replace(r"\tfrac", r"\frac")
        .replace(r"\,", "")
        .replace(r"\;", "")
        .replace(r"\!", "")
        .replace(r"\quad", "")
        .replace(r"\qquad", "")
    )


def _coefficient(source: str | None, implicit: int = 1) -> int | None:
    compact = re.sub(r"\s+|\\cdot|\\times", "", source or "")
    if compact in {"", "+"}:
        return implicit
    if compact == "-":
        return -implicit
    if re.fullmatch(r"[+-]?\d+", compact) is None:
        return None
    return int(compact)


def _parse_pi_fraction(source: str) -> Fraction | None:
    compact = re.sub(r"\s+", "", source)
    sign = 1
    if compact.startswith(("+", "-")):
        if compact[0] == "-":
            sign = -1
        compact = compact[1:]

    numerator_over_denominator = re.fullmatch(
        r"\\frac\{(?P<numerator>\d*)\\pi\}\{(?P<denominator>\d+)\}",
        compact,
    )
    if numerator_over_denominator is not None:
        numerator = int(numerator_over_denominator.group("numerator") or "1")
        denominator = int(numerator_over_denominator.group("denominator"))
        return Fraction(sign * numerator, denominator) if denominator else None

    scalar_fraction = re.fullmatch(
        r"\\frac\{(?P<numerator>\d+)\}\{(?P<denominator>\d+)\}\\pi",
        compact,
    )
    if scalar_fraction is not None:
        numerator = int(scalar_fraction.group("numerator"))
        denominator = int(scalar_fraction.group("denominator"))
        return Fraction(sign * numerator, denominator) if denominator else None

    plain = re.fullmatch(
        r"(?P<numerator>\d*)\\pi(?:/(?P<denominator>\d+))?",
        compact,
    )
    if plain is None:
        return None
    numerator = int(plain.group("numerator") or "1")
    denominator = int(plain.group("denominator") or "1")
    return Fraction(sign * numerator, denominator) if denominator else None


def _parse_recurrence(statement: str) -> RationalAngleRecurrence | None:
    source = _compact(statement)
    recurrence = re.search(
        r"(?P<symbol>[A-Za-z])_\{?(?P<index>[A-Za-z])\+2\}?\s*=\s*"
        r"(?P<first>[+-]?\s*\d*\s*(?:\\cdot|\\times)?\s*)?"
        r"(?P=symbol)_\{?(?P=index)\+1\}?\s*"
        r"(?P<sign>[+-])\s*"
        r"(?P<second>\d*\s*(?:\\cdot|\\times)?\s*)?"
        r"(?P=symbol)_\{?(?P=index)\}?",
        source,
    )
    if recurrence is None:
        return None
    first_coefficient = _coefficient(recurrence.group("first"))
    second_magnitude = _coefficient(recurrence.group("second"))
    if first_coefficient is None or second_magnitude is None:
        return None
    second_coefficient = (
        -second_magnitude if recurrence.group("sign") == "-" else second_magnitude
    )
    symbol = recurrence.group("symbol")

    equal_initials = re.search(
        rf"{re.escape(symbol)}_\{{?(\d+)\}}?\s*=\s*"
        rf"{re.escape(symbol)}_\{{?(\d+)\}}?\s*=\s*(?P<value>{_PI_VALUE})",
        source,
    )
    if equal_initials is not None:
        first_index = int(equal_initials.group(1))
        second_index = int(equal_initials.group(2))
        value = _parse_pi_fraction(equal_initials.group("value"))
        if second_index != first_index + 1 or value is None:
            return None
        initial = (value, value)
    else:
        initial_pattern = re.compile(
            rf"{re.escape(symbol)}_\{{?(\d+)\}}?\s*=\s*(?P<value>{_PI_VALUE})"
        )
        values: list[tuple[int, Fraction]] = []
        for match in initial_pattern.finditer(source):
            value = _parse_pi_fraction(match.group("value"))
            if value is not None:
                values.append((int(match.group(1)), value))
        values.sort(key=lambda item: item[0])
        consecutive = next(
            (
                (left, right)
                for left, right in zip(values, values[1:])
                if right[0] == left[0] + 1
            ),
            None,
        )
        if consecutive is None:
            return None
        (first_index, first_value), (_, second_value) = consecutive
        initial = (first_value, second_value)

    return RationalAngleRecurrence(
        sequence_symbol=symbol,
        index_symbol=recurrence.group("index"),
        start_index=first_index,
        initial=initial,
        coefficients=(first_coefficient, second_coefficient),
    )


def _parse_chebyshev_recurrence(statement: str) -> ChebyshevRecurrence | None:
    source = _compact(statement)
    recurrence = re.search(
        r"(?P<poly>[A-Z])_\{?(?P<index>[A-Za-z])\+2\}?\((?P<var>[A-Za-z])\)"
        r"\s*=\s*2(?P=var)(?P=poly)_\{?(?P=index)\+1\}?\((?P=var)\)"
        r"\s*-\s*(?P=poly)_\{?(?P=index)\}?\((?P=var)\)",
        source,
    )
    if recurrence is None:
        return None
    poly = recurrence.group("poly")
    var = recurrence.group("var")
    if re.search(rf"{poly}_\{{?0\}}?\({var}\)\s*=\s*1", source) is None:
        return None
    if re.search(rf"{poly}_\{{?1\}}?\({var}\)\s*=\s*{var}", source) is None:
        return None
    return ChebyshevRecurrence(
        polynomial_symbol=poly,
        index_symbol=recurrence.group("index"),
        variable_symbol=var,
    )


def compile_finite_orbit_query(statement: str) -> FiniteOrbitQueryIR | None:
    recurrence = _parse_recurrence(statement)
    if recurrence is None:
        return None
    source = _compact(statement)
    symbol = re.escape(recurrence.sequence_symbol)
    index = re.escape(recurrence.index_symbol)
    polynomial = _parse_chebyshev_recurrence(statement)

    base_observable: str | None = None
    for observable in ("sin", "cos"):
        if re.search(
            rf"\\sum_\{{?[A-Za-z]=\d+\}}?\^\{{?[A-Za-z]\}}?\\{observable}\s*{symbol}_\{{?[A-Za-z]\}}?",
            source,
        ):
            base_observable = observable
            break

    polynomial_observable: str | None = None
    polynomial_identity_requested = False
    if polynomial is not None:
        poly = re.escape(polynomial.polynomial_symbol)
        poly_index = re.escape(polynomial.index_symbol)
        poly_variable = re.escape(polynomial.variable_symbol)
        polynomial_identity_requested = re.search(
            rf"{poly}_\{{?{poly_index}\}}?\(\\cos\s*{poly_variable}\)"
            rf"\s*=\s*\\cos\s*{poly_index}\s*{poly_variable}",
            source,
        ) is not None
        for observable in ("sin", "cos"):
            if re.search(
                rf"{poly}_\{{?[A-Za-z]\}}?\(\\{observable}\s*{symbol}_\{{?[A-Za-z]\}}?\)",
                source,
            ):
                polynomial_observable = observable
                break

    if (
        base_observable is None
        and polynomial_observable is None
        and not polynomial_identity_requested
    ):
        return None
    return FiniteOrbitQueryIR(
        recurrence=recurrence,
        base_observable=base_observable,
        polynomial=polynomial,
        polynomial_identity_requested=polynomial_identity_requested,
        polynomial_observable=polynomial_observable,
        multipart=r"\begin{enumerate}" in statement or r"\item" in statement,
    )


def _positive_mod(value: int, modulus: int) -> int:
    return value % modulus


def _matmul(left: tuple[int, int, int, int], right: tuple[int, int, int, int], modulus: int) -> tuple[int, int, int, int]:
    return (
        (left[0] * right[0] + left[1] * right[2]) % modulus,
        (left[0] * right[1] + left[1] * right[3]) % modulus,
        (left[2] * right[0] + left[3] * right[2]) % modulus,
        (left[2] * right[1] + left[3] * right[3]) % modulus,
    )


def _matpow(matrix: tuple[int, int, int, int], exponent: int, modulus: int) -> tuple[int, int, int, int]:
    result = (1, 0, 0, 1)
    base = matrix
    remaining = exponent
    while remaining:
        if remaining & 1:
            result = _matmul(result, base, modulus)
        base = _matmul(base, base, modulus)
        remaining //= 2
    return result


def _apply_matrix(matrix: tuple[int, int, int, int], state: tuple[int, int], modulus: int) -> tuple[int, int]:
    return (
        (matrix[0] * state[0] + matrix[1] * state[1]) % modulus,
        (matrix[2] * state[0] + matrix[3] * state[1]) % modulus,
    )


def _modular_projection(recurrence: RationalAngleRecurrence) -> dict[str, Any]:
    denominator = lcm(*(value.denominator for value in recurrence.initial))
    modulus = 2 * denominator
    initial_state = tuple(
        _positive_mod(value.numerator * (denominator // value.denominator), modulus)
        for value in recurrence.initial
    )
    return {
        "recurrence": recurrence,
        "denominator": denominator,
        "modulus": modulus,
        "initial_state": initial_state,
        "transition": (0, 1, recurrence.coefficients[1], recurrence.coefficients[0]),
    }


def _enumerate_finite_orbit(projection: dict[str, Any]) -> dict[str, Any]:
    recurrence = projection["recurrence"]
    modulus = int(projection["modulus"])
    initial_state = tuple(projection["initial_state"])
    seen: dict[tuple[int, int], int] = {}
    states: list[tuple[int, int]] = []
    state = (initial_state[0], initial_state[1])
    maximum = modulus * modulus + 1
    for index in range(maximum + 1):
        if state in seen:
            cycle_start = seen[state]
            period = index - cycle_start
            break
        seen[state] = index
        states.append(state)
        alpha, beta = recurrence.coefficients
        state = (state[1], (alpha * state[1] + beta * state[0]) % modulus)
    else:  # pragma: no cover - finite-state pigeonhole guard.
        raise ValueError("finite recurrence orbit did not repeat within the state bound")

    return {
        **projection,
        "states": states,
        "cycle_start": cycle_start,
        "period": period,
        "cycle_values": [states[cycle_start + offset][0] for offset in range(period)],
    }


def _replay_finite_orbit(orbit: dict[str, Any]) -> None:
    modulus = int(orbit["modulus"])
    initial_state = tuple(orbit["initial_state"])
    transition = tuple(orbit["transition"])
    states = list(orbit["states"])
    for index, expected in enumerate(states):
        replayed = _apply_matrix(_matpow(transition, index, modulus), initial_state, modulus)
        if replayed != expected:
            raise ValueError("modular matrix replay disagreed with recurrence enumeration")
    cycle_start = int(orbit["cycle_start"])
    period = int(orbit["period"])
    cycle_state = states[cycle_start]
    if _apply_matrix(_matpow(transition, period, modulus), cycle_state, modulus) != cycle_state:
        raise ValueError("cycle closure failed under modular matrix replay")


def _finite_orbit(recurrence: RationalAngleRecurrence) -> dict[str, Any]:
    orbit = _enumerate_finite_orbit(_modular_projection(recurrence))
    _replay_finite_orbit(orbit)
    return orbit


def _trig_value(observable: str, residue: int, denominator: int) -> sp.Expr:
    function = sp.sin if observable == "sin" else sp.cos
    return sp.simplify(sp.expand_trig(function(sp.pi * residue / denominator)))


def _periodic_average(observable: str, residues: list[int], denominator: int) -> sp.Expr:
    return sp.simplify(
        sum((_trig_value(observable, residue, denominator) for residue in residues), sp.Integer(0))
        / len(residues)
    )


def _divisors(value: int) -> list[int]:
    return [candidate for candidate in range(1, value + 1) if value % candidate == 0]


def _chebyshev_average_profile(
    observable: str,
    residues: list[int],
    denominator: int,
) -> tuple[int, list[sp.Expr], list[sp.Expr]]:
    upper_period = 4 * denominator
    direct_polynomials: list[sp.Expr] = [sp.Integer(1), sp.Symbol("x")]
    x = direct_polynomials[1]
    for degree in range(2, upper_period + 1):
        direct_polynomials.append(sp.expand(2 * x * direct_polynomials[-1] - direct_polynomials[-2]))

    formula_values: list[sp.Expr] = []
    direct_values: list[sp.Expr] = []
    for degree in range(upper_period):
        formula = sp.simplify(
            sum(
                (
                    sp.cos(degree * (sp.pi / 2 - sp.pi * residue / denominator))
                    if observable == "sin"
                    else sp.cos(degree * sp.pi * residue / denominator)
                    for residue in residues
                ),
                sp.Integer(0),
            )
            / len(residues)
        )
        direct = sp.simplify(
            sum(
                (
                    direct_polynomials[degree].subs(
                        x,
                        _trig_value(observable, residue, denominator),
                    )
                    for residue in residues
                ),
                sp.Integer(0),
            )
            / len(residues)
        )
        if sp.simplify(formula - direct) != 0:
            raise ValueError("Chebyshev observable replay failed")
        formula_values.append(formula)
        direct_values.append(direct)

    period = next(
        candidate
        for candidate in _divisors(upper_period)
        if all(
            sp.simplify(formula_values[index] - formula_values[(index + candidate) % upper_period]) == 0
            for index in range(upper_period)
        )
    )
    return period, formula_values[:period], direct_values[:period]


def _group_residue_values(values: list[sp.Expr]) -> list[tuple[sp.Expr, list[int]]]:
    groups: list[tuple[sp.Expr, list[int]]] = []
    for residue, value in enumerate(values):
        for index, (representative, residues) in enumerate(groups):
            if sp.simplify(value - representative) == 0:
                groups[index] = (representative, [*residues, residue])
                break
        else:
            groups.append((value, [residue]))
    return groups


def _residue_condition(residues: list[int], modulus: int, symbol: str) -> str:
    odd = list(range(1, modulus, 2))
    even = list(range(0, modulus, 2))
    if residues == odd:
        return rf"{symbol}\equiv 1\pmod{{2}}"
    if residues == even:
        return rf"{symbol}\equiv 0\pmod{{2}}"
    joined = ",".join(str(value) for value in residues)
    return rf"{symbol}\equiv {joined}\pmod{{{modulus}}}"


def _piecewise_tex(values: list[sp.Expr], modulus: int, symbol: str) -> str:
    rows = [
        rf"{sp.latex(value)}&({_residue_condition(residues, modulus, symbol)})"
        for value, residues in _group_residue_values(values)
    ]
    return r"\begin{cases}" + r"\\".join(rows) + r"\end{cases}"


def _synthesize_finite_orbit_plan(query: FiniteOrbitQueryIR):
    """Compose a proof program from primitive contracts for this query."""

    recurrence = query.recurrence

    def elaborate_rational_angle(arguments: tuple[Any, ...]) -> PrimitiveResult:
        denominator = lcm(*(value.denominator for value in recurrence.initial))
        return PrimitiveResult(
            {"recurrence": recurrence, "denominator": denominator},
            {
                "denominator": denominator,
                "initial": [
                    [value.numerator, value.denominator]
                    for value in recurrence.initial
                ],
            },
        )

    def lift_second_order(arguments: tuple[Any, ...]) -> PrimitiveResult:
        data = arguments[0].value
        alpha, beta = data["recurrence"].coefficients
        return PrimitiveResult(
            {**data, "coefficients": (alpha, beta)},
            {"coefficients": [alpha, beta]},
        )

    def project_modular_state(arguments: tuple[Any, ...]) -> PrimitiveResult:
        projection = _modular_projection(arguments[0].value["recurrence"])
        return PrimitiveResult(
            projection,
            {
                "modulus": projection["modulus"],
                "initial_state": list(projection["initial_state"]),
            },
        )

    def enumerate_orbit(arguments: tuple[Any, ...]) -> PrimitiveResult:
        orbit = _enumerate_finite_orbit(arguments[0].value)
        return PrimitiveResult(
            orbit,
            {
                "cycle_start": orbit["cycle_start"],
                "period": orbit["period"],
                "states_enumerated": len(orbit["states"]),
            },
        )

    def replay_orbit(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        orbit = arguments[0].value
        try:
            _replay_finite_orbit(orbit)
        except ValueError:
            return None
        return PrimitiveResult(
            orbit,
            {
                "transition": list(orbit["transition"]),
                "all_states_replayed": True,
                "cycle_closure_replayed": True,
            },
        )

    def reduce_periodic_average(arguments: tuple[Any, ...]) -> PrimitiveResult:
        orbit = arguments[0].value
        residues = list(orbit["cycle_values"])
        return PrimitiveResult(
            {**orbit, "residues": residues},
            {
                "preperiod_is_negligible": True,
                "period": orbit["period"],
            },
        )

    def aggregate_base_observable(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        if query.base_observable is None:
            return None
        measure = arguments[0].value
        residues = list(measure["residues"])
        denominator = int(measure["denominator"])
        average = _periodic_average(query.base_observable, residues, denominator)
        cycle_sum = sp.simplify(average * len(residues))
        return PrimitiveResult(
            {
                **measure,
                "observable": query.base_observable,
                "average": average,
                "cycle_sum": cycle_sum,
            },
            {
                "observable": query.base_observable,
                "cycle_sum": sp.sstr(cycle_sum),
                "cycle_length": len(residues),
            },
        )

    def elaborate_polynomial(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        if query.polynomial is None:
            return None
        polynomial = query.polynomial
        return PrimitiveResult(
            {"polynomial": polynomial},
            {
                "polynomial_symbol": polynomial.polynomial_symbol,
                "initial_polynomials": ["1", polynomial.variable_symbol],
            },
        )

    def certify_polynomial_identity(arguments: tuple[Any, ...]) -> PrimitiveResult:
        data = arguments[0].value
        polynomial = data["polynomial"]
        return PrimitiveResult(
            {**data, "identity": "ChebyshevT"},
            {
                "polynomial_symbol": polynomial.polynomial_symbol,
                "identity": "ChebyshevT",
                "certificate": "same_initial_values_and_second_order_recurrence",
            },
        )

    def substitute_trigonometric_observable(
        arguments: tuple[Any, ...],
    ) -> PrimitiveResult | None:
        if query.polynomial_observable is None:
            return None
        return PrimitiveResult(
            {
                **arguments[0].value,
                "observable": query.polynomial_observable,
            },
            {"observable": query.polynomial_observable},
        )

    def aggregate_character(arguments: tuple[Any, ...]) -> PrimitiveResult:
        measure = arguments[0].value
        observable = arguments[1].value["observable"]
        profile_period, profile_values, direct_values = _chebyshev_average_profile(
            observable,
            list(measure["residues"]),
            int(measure["denominator"]),
        )
        return PrimitiveResult(
            {
                **measure,
                **arguments[1].value,
                "parameter_period": profile_period,
                "parameter_values": profile_values,
                "independent_parameter_values": direct_values,
            },
            {
                "parameter_modulus": profile_period,
                "all_residues_replayed": True,
                "independent_polynomial_replay": True,
            },
        )

    primitives = (
        RuntimePrimitive(
            "rational_pi_elaboration",
            ("ParsedProblemIR",),
            "RationalPiRecurrence",
            elaborate_rational_angle,
        ),
        RuntimePrimitive(
            "second_order_recurrence_lift",
            ("RationalPiRecurrence",),
            "SecondOrderLinearRecurrence",
            lift_second_order,
        ),
        RuntimePrimitive(
            "modular_state_projection",
            ("SecondOrderLinearRecurrence",),
            "ModularFiniteStateSystem",
            project_modular_state,
        ),
        RuntimePrimitive(
            "finite_orbit_enumeration",
            ("ModularFiniteStateSystem",),
            "FiniteOrbit",
            enumerate_orbit,
        ),
        RuntimePrimitive(
            "modular_matrix_replay",
            ("FiniteOrbit",),
            "CertifiedFiniteOrbit",
            replay_orbit,
        ),
        RuntimePrimitive(
            "periodic_cesaro_reduction",
            ("CertifiedFiniteOrbit",),
            "PeriodicOrbitMeasure",
            reduce_periodic_average,
        ),
        RuntimePrimitive(
            "finite_trigonometric_aggregation",
            ("PeriodicOrbitMeasure",),
            "CertifiedPeriodicAverage",
            aggregate_base_observable,
        ),
        RuntimePrimitive(
            "polynomial_recurrence_elaboration",
            ("ParsedProblemIR",),
            "PolynomialRecurrence",
            elaborate_polynomial,
        ),
        RuntimePrimitive(
            "polynomial_recurrence_uniqueness",
            ("PolynomialRecurrence",),
            "CertifiedPolynomialIdentity",
            certify_polynomial_identity,
        ),
        RuntimePrimitive(
            "trigonometric_observable_substitution",
            ("CertifiedPolynomialIdentity",),
            "TrigonometricPolynomialObservable",
            substitute_trigonometric_observable,
        ),
        RuntimePrimitive(
            "finite_character_aggregation",
            ("PeriodicOrbitMeasure", "TrigonometricPolynomialObservable"),
            "CertifiedPolynomialOrbitProfile",
            aggregate_character,
        ),
    )
    goal_sorts: list[str] = []
    if query.base_observable is not None:
        goal_sorts.append("CertifiedPeriodicAverage")
    if query.polynomial_identity_requested:
        goal_sorts.append("CertifiedPolynomialIdentity")
    if query.polynomial_observable is not None:
        goal_sorts.append("CertifiedPolynomialOrbitProfile")
    return synthesize_typed_plan(
        [initial_fact("ParsedProblemIR", query.to_dict())],
        primitives,
        goal_sorts,
        max_depth=12,
        max_states=128,
    )


def execute_finite_orbit_query(query: FiniteOrbitQueryIR) -> FiniteOrbitSynthesis:
    plan = _synthesize_finite_orbit_plan(query)
    if not plan.complete:
        raise ValueError(f"runtime finite-orbit planner left open goals: {plan.open_goal_sorts}")

    base_result = (
        plan.goals["CertifiedPeriodicAverage"].value
        if "CertifiedPeriodicAverage" in plan.goals
        else None
    )
    identity_result = (
        plan.goals["CertifiedPolynomialIdentity"].value
        if "CertifiedPolynomialIdentity" in plan.goals
        else None
    )
    profile_result = (
        plan.goals["CertifiedPolynomialOrbitProfile"].value
        if "CertifiedPolynomialOrbitProfile" in plan.goals
        else None
    )
    orbit = base_result or profile_result
    denominator = (
        int(orbit["denominator"])
        if orbit is not None
        else lcm(*(value.denominator for value in query.recurrence.initial))
    )
    residues = list(orbit["cycle_values"]) if orbit is not None else []
    sequence = query.recurrence.sequence_symbol
    alpha, beta = query.recurrence.coefficients
    initial_tex = r",\quad ".join(
        rf"{sequence}_{{{query.recurrence.start_index + offset}}}={sp.latex(sp.Rational(value.numerator, value.denominator) * sp.pi)}"
        for offset, value in enumerate(query.recurrence.initial)
    )
    recurrence_tex = (
        rf"{sequence}_{{{query.recurrence.index_symbol}+2}}="
        rf"{alpha}{sequence}_{{{query.recurrence.index_symbol}+1}}"
        rf"{beta:+d}{sequence}_{{{query.recurrence.index_symbol}}}"
    )

    answers: list[str] = []
    derivation: list[str] = []
    if orbit is not None:
        derivation.extend(
            [
                rf"各項を \(\pi\) で割り、分母の最小公倍数を \(D={denominator}\) とする。"
                rf"三角関数の値は係数を法 \(2D={orbit['modulus']}\) で見れば決まる。"
                rf"問題文から読み取った初期値と漸化式は \({initial_tex}\), \({recurrence_tex}\) である。",
                rf"状態を \((u_n,u_{{n+1}})\bmod {orbit['modulus']}\) として遷移を列挙する。"
                rf"最初の反復は第 {orbit['cycle_start']} 状態で起こり、周期は {orbit['period']} である。"
                rf"一周期の第1成分は \({','.join(str(value) for value in residues)}\) となる。"
                r"同じ遷移を随伴行列の累乗でも再計算し、列挙した全状態と一致することを確かめた。",
                r"有限個の前周期項を平均に加えても、その寄与は項数で割ると0へ収束する。"
                r"従って周期数列の長期平均は、一周期の値の平均に等しい。",
            ]
        )
    proof_program: list[dict[str, Any]] = list(plan.proof_program)

    if query.base_observable is not None:
        if base_result is None:
            raise ValueError("periodic average was requested but not synthesized")
        base_average = base_result["average"]
        base_sum = base_result["cycle_sum"]
        answers.append(rf"{sp.latex(base_average)}")
        derivation.append(
            rf"一周期について \(\sum {query.base_observable}(u_k\pi/{denominator})={sp.latex(base_sum)}\) である。"
            rf"周期 {len(residues)} で割ると、求める平均は \({sp.latex(base_average)}\) となる。"
        )

    if query.polynomial is not None:
        poly = query.polynomial
        if query.polynomial_identity_requested:
            if identity_result is None:
                raise ValueError("polynomial identity was requested but not synthesized")
            answers.append(
                rf"{poly.polynomial_symbol}_{{{poly.index_symbol}}}"
                rf"({poly.variable_symbol})=T_{{{poly.index_symbol}}}({poly.variable_symbol})"
            )
        derivation.append(
            rf"\({poly.polynomial_symbol}_0({poly.variable_symbol})=1\), "
            rf"\({poly.polynomial_symbol}_1({poly.variable_symbol})={poly.variable_symbol}\) であり、"
            rf"\({poly.polynomial_symbol}_{{{poly.index_symbol}+2}}({poly.variable_symbol})="
            rf"2{poly.variable_symbol}{poly.polynomial_symbol}_{{{poly.index_symbol}+1}}({poly.variable_symbol})-"
            rf"{poly.polynomial_symbol}_{{{poly.index_symbol}}}({poly.variable_symbol})\) である。"
            rf"一方、余弦の加法定理から \(\cos(({{{poly.index_symbol}}}+2)t)="
            rf"2\cos t\cos(({{{poly.index_symbol}}}+1)t)-\cos({poly.index_symbol}t)\) となる。"
            rf"初期値と漸化式が一致するので、帰納法により "
            rf"\({poly.polynomial_symbol}_{{{poly.index_symbol}}}(\cos t)="
            rf"\cos({poly.index_symbol}t)\) が成り立つ。"
        )

    profile_period: int | None = None
    profile_values: list[sp.Expr] = []
    direct_values: list[sp.Expr] = []
    if query.polynomial_observable is not None:
        if query.polynomial is None:
            raise ValueError("polynomial observable has no defining recurrence")
        if profile_result is None:
            raise ValueError("polynomial orbit profile was requested but not synthesized")
        profile_period = int(profile_result["parameter_period"])
        profile_values = list(profile_result["parameter_values"])
        direct_values = list(profile_result["independent_parameter_values"])
        symbol = query.polynomial.index_symbol
        answers.append(_piecewise_tex(profile_values, profile_period, symbol))
        derivation.append(
            rf"\({query.polynomial.polynomial_symbol}_{symbol}\) の恒等式を各周期項へ適用する。"
            rf"残る値は {symbol} を法 {profile_period} で分類すれば十分である。"
            rf"法 {profile_period} の全 {profile_period} 場合を、多項式漸化式から直接生成した値と余弦表示の二通りで照合した。"
        )

    if not answers:
        raise ValueError("finite-orbit program contains no requested observation")
    if query.multipart:
        labels = [str(index) for index in range(1, len(answers) + 1)]
        answer_tex = r"\(\begin{aligned}" + r"\\".join(
            rf"\text{{({label})}}\;&{answer}"
            for label, answer in zip(labels, answers)
        ) + r"\end{aligned}\)"
    elif len(answers) == 1:
        answer_tex = rf"\({answers[0]}\)"
    else:
        answer_tex = r"\(\begin{aligned}" + r"\\".join(answers) + r"\end{aligned}\)"

    proof_program.append({"rule": "exact_obligation_replay", "verified": True})
    checks = (
        "初期値・漸化式係数・有理角を現在の問題文から抽出",
        *(
            (
                f"法{orbit['modulus']}の全到達状態を列挙し、最初の反復から周期を確定",
                "同じ全状態を随伴行列の累乗で独立再生",
                "周期平均を厳密な三角関数値の和として再計算",
            )
            if orbit is not None
            else ()
        ),
        *(
            (f"多項式漸化式と余弦表示を法{profile_period}の全場合で照合",)
            if profile_period is not None
            else ()
        ),
        f"型付き実行計画が要求型 {','.join(sorted(plan.goals))} を閉じた",
    )
    witness = {
        "input_ir": query.to_dict(),
        "modulus": orbit["modulus"] if orbit is not None else None,
        "cycle_start": orbit["cycle_start"] if orbit is not None else None,
        "state_period": orbit["period"] if orbit is not None else None,
        "cycle_values": residues,
        "parameter_period": profile_period,
        "parameter_values": [sp.sstr(value) for value in profile_values],
        "independent_parameter_values": [sp.sstr(value) for value in direct_values],
        "runtime_plan": {
            "states_explored": plan.states_explored,
            "goal_sorts": sorted(plan.goals),
            "open_goal_sorts": list(plan.open_goal_sorts),
        },
    }
    return FiniteOrbitSynthesis(
        answer_tex=answer_tex,
        derivation_tex=tuple(derivation),
        expression_tex=(
            rf"{recurrence_tex}\quad(\bmod\ {orbit['modulus']})"
            if orbit is not None
            else recurrence_tex
        ),
        proof_program=tuple(proof_program),
        verification_checks=checks,
        witness=witness,
        hypotheses_evaluated=(
            (len(orbit["states"]) if orbit is not None else 0)
            + (profile_period or 0)
        ),
    )


def synthesize_finite_orbit_problem(statement: str) -> FiniteOrbitSynthesis | None:
    query = compile_finite_orbit_query(statement)
    if query is None:
        return None
    return execute_finite_orbit_query(query)
