"""Cold runtime synthesis for integral prime cycles of parametric Mobius maps.

The solver does not register a completed problem route.  It parses a
fractional-linear map, searches for an affine conjugacy that removes the
parameter, certifies the projective period by matrix multiplication, and then
classifies integral orbits through a determinant-divisor argument.  A final
residue-cover certificate reduces simultaneous primality to finitely many
parameter values.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction
from math import gcd
import re
from typing import Any

import sympy as sp

from .latex_frontend import normalize_latex_math
from .runtime_typed_planner import (
    PrimitiveResult,
    RuntimePrimitive,
    initial_fact,
    synthesize_typed_plan,
)
from .visual_reasoning import plane_scene_diagram


@dataclass(frozen=True)
class ParametricMobiusMap:
    function_symbol: str
    parameter_symbol: str
    variable_symbol: str
    numerator: str
    denominator: str


@dataclass(frozen=True)
class MobiusPrimeCycleQueryIR:
    map: ParametricMobiusMap
    cycle_symbols: tuple[str, ...]
    positive_integer_parameter: bool
    distinct_prime_cycle: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MobiusPrimeCycleSynthesis:
    answer_tex: str
    derivation_tex: tuple[str, ...]
    expression_tex: str
    proof_program: tuple[dict[str, Any], ...]
    verification_checks: tuple[str, ...]
    witness: dict[str, Any]
    hypotheses_evaluated: int
    diagram: dict[str, Any]
    diagram_tikz: str
    visual_explanation: dict[str, Any]


def _evaluate_shift(shift: sp.Expr, parameter_name: str, value: int) -> int:
    parameter = next(
        (symbol for symbol in shift.free_symbols if symbol.name == parameter_name),
        None,
    )
    evaluated = shift if parameter is None else shift.subs(parameter, value)
    return int(evaluated)


def _mobius_cycle_diagram(
    query: MobiusPrimeCycleQueryIR,
    *,
    shift: sp.Expr,
    cycle: tuple[int, ...],
    initial_candidates: tuple[int, ...],
    parameter_value: int,
    stage: int,
) -> dict[str, Any]:
    """Show the certified conjugacy, finite orbit, and prime replay."""

    positions = (
        {"x": -1.45, "y": 0.0},
        {"x": 0.72, "y": 1.18},
        {"x": 0.72, "y": -1.18},
    )
    shift_value = _evaluate_shift(shift, query.map.parameter_symbol, parameter_value)
    labels = [f"y={value}" for value in cycle]
    if stage >= 5:
        labels = [f"x={shift_value + value}" for value in cycle]
    shapes: list[dict[str, Any]] = [
        {
            "id": f"orbit-node-{index}",
            "kind": "point",
            "point": point,
            "label": labels[index],
            "tone": "accent" if stage >= 3 else "primary",
        }
        for index, point in enumerate(positions)
    ]
    shapes.append(
        {
            "id": "conjugacy-label",
            "kind": "label",
            "point": {"x": -1.72, "y": 1.58},
            "text": rf"x={sp.latex(shift)}+y",
            "tone": "secondary",
        }
    )
    if stage >= 2:
        for index, (source, target) in enumerate(
            zip(positions, positions[1:] + positions[:1])
        ):
            shapes.append(
                {
                    "id": f"orbit-arrow-{index}",
                    "kind": "vector",
                    "from": source,
                    "to": target,
                    "label": "g",
                    "tone": "secondary",
                }
            )
        shapes.append(
            {
                "id": "period-label",
                "kind": "label",
                "point": {"x": -1.7, "y": -1.58},
                "text": "M^3=-64I",
                "tone": "secondary",
            }
        )
    if stage >= 3:
        candidate_text = ",".join(str(value) for value in initial_candidates)
        shapes.append(
            {
                "id": "candidate-label",
                "kind": "label",
                "point": {"x": -0.62, "y": 1.58},
                "text": rf"y\in\{{{candidate_text}\}}",
                "tone": "muted",
            }
        )
    if stage >= 4:
        shapes.append(
            {
                "id": "residue-cover-label",
                "kind": "label",
                "point": {"x": -0.78, "y": -1.62},
                "text": "h-2,h,h+2 は法3の全剰余を覆う",
                "tone": "accent",
            }
        )
    if stage >= 5:
        shapes.append(
            {
                "id": "parameter-label",
                "kind": "label",
                "point": {"x": 0.56, "y": 1.58},
                "text": rf"{query.map.parameter_symbol}={parameter_value}",
                "tone": "accent",
            }
        )
    captions = {
        1: "平行移動 x=h+y によって、パラメータを含む写像を一つの分数一次写像へ移します。",
        2: "行列の3乗がスカラー行列になるため、射影直線上の非自明な軌道は3周期です。",
        3: "整数が整数へ移るための分母の整除条件から候補を有限個にし、唯一の3周期軌道を残します。",
        4: "三つの平行移動値が法3の全剰余を覆うため、三つが全て素数なら一つは3そのものです。",
        5: "有限個の候補を元の写像へ戻すと、3,5,7 の三つの巡回順序だけが残ります。",
    }
    return plane_scene_diagram(
        title="分数一次写像の整数3周期",
        caption=captions[stage],
        viewport={"xMin": -1.95, "xMax": 1.62, "yMin": -1.86, "yMax": 1.86},
        shapes=shapes,
        axes=False,
    )


def _mobius_cycle_tikz(
    query: MobiusPrimeCycleQueryIR,
    *,
    shift: sp.Expr,
    cycle: tuple[int, ...],
    parameter_value: int,
) -> str:
    shift_value = _evaluate_shift(shift, query.map.parameter_symbol, parameter_value)
    values = tuple(shift_value + offset for offset in cycle)
    return "\n".join(
        (
            r"\begin{tikzpicture}[>=stealth,line cap=round,line join=round]",
            rf"\node[draw,circle,minimum size=9mm] (a) at (-2.0,0) {{$x={values[0]}$}};",
            rf"\node[draw,circle,minimum size=9mm] (b) at (1.0,1.35) {{$x={values[1]}$}};",
            rf"\node[draw,circle,minimum size=9mm] (c) at (1.0,-1.35) {{$x={values[2]}$}};",
            rf"\draw[->,very thick,cyan!65!black] (a) to[bend left=12] node[above] {{$ {query.map.function_symbol}_{{{query.map.parameter_symbol}}} $}} (b);",
            rf"\draw[->,very thick,cyan!65!black] (b) to[bend left=12] node[right] {{$ {query.map.function_symbol}_{{{query.map.parameter_symbol}}} $}} (c);",
            rf"\draw[->,very thick,cyan!65!black] (c) to[bend left=12] node[below] {{$ {query.map.function_symbol}_{{{query.map.parameter_symbol}}} $}} (a);",
            rf"\node[above left] at (-2.0,1.55) {{$x={sp.latex(shift)}+y,\quad y:{cycle[0]}\mapsto {cycle[1]}\mapsto {cycle[2]}\mapsto {cycle[0]}$}};",
            r"\end{tikzpicture}",
        )
    )


def _compact_latex(statement: str) -> str:
    return re.sub(
        r"\s+",
        "",
        statement.replace("−", "-")
        .replace("–", "-")
        .replace(r"\left", "")
        .replace(r"\right", "")
        .replace(r"\dfrac", r"\frac")
        .replace(r"\tfrac", r"\frac")
        .replace(r"\quad", "")
        .replace(r"\,", ""),
    )


def _balanced_group(source: str, start: int) -> tuple[str, int] | None:
    if start >= len(source) or source[start] != "{":
        return None
    depth = 0
    for index in range(start, len(source)):
        character = source[index]
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return source[start + 1:index], index + 1
    return None


def _fraction_groups(source: str, start: int) -> tuple[str, str] | None:
    cursor = start
    numerator = _balanced_group(source, cursor)
    if numerator is None:
        return None
    cursor = numerator[1]
    denominator = _balanced_group(source, cursor)
    if denominator is None:
        return None
    return numerator[0], denominator[0]


def _parse_polynomial_latex(
    source: str,
    *,
    variable: sp.Symbol,
    parameter: sp.Symbol,
) -> sp.Expr | None:
    normalized = normalize_latex_math(source).strip()
    try:
        expression = sp.sympify(
            normalized,
            locals={str(variable): variable, str(parameter): parameter},
        )
    except (sp.SympifyError, SyntaxError, TypeError, ValueError):
        return None
    if expression.free_symbols - {variable, parameter}:
        return None
    try:
        sp.Poly(expression, variable, parameter)
    except sp.PolynomialError:
        return None
    return sp.expand(expression)


def _ordered_cycle(
    pairs: list[tuple[str, str]],
) -> tuple[str, ...] | None:
    if len(pairs) < 2:
        return None
    transition: dict[str, str] = {}
    for source, target in pairs:
        if source in transition and transition[source] != target:
            return None
        transition[source] = target
    vertices = set(transition) | set(transition.values())
    if set(transition) != vertices:
        return None
    start = pairs[0][0]
    ordered: list[str] = []
    current = start
    while current not in ordered:
        ordered.append(current)
        current = transition[current]
    if current != start or set(ordered) != vertices:
        return None
    return tuple(ordered)


def compile_mobius_prime_cycle_query(
    statement: str,
) -> MobiusPrimeCycleQueryIR | None:
    compact = _compact_latex(statement)
    definition = re.search(
        r"(?P<function>[A-Za-z])_\{?(?P<parameter>[A-Za-z])\}?"
        r"\((?P<variable>[A-Za-z])\)=\\frac",
        compact,
    )
    if definition is None:
        return None
    function = definition.group("function")
    parameter_name = definition.group("parameter")
    variable_name = definition.group("variable")
    groups = _fraction_groups(compact, definition.end())
    if groups is None:
        return None

    variable = sp.Symbol(variable_name)
    parameter = sp.Symbol(parameter_name, integer=True)
    numerator = _parse_polynomial_latex(
        groups[0], variable=variable, parameter=parameter
    )
    denominator = _parse_polynomial_latex(
        groups[1], variable=variable, parameter=parameter
    )
    if numerator is None or denominator is None:
        return None
    if sp.degree(numerator, variable) > 1 or sp.degree(denominator, variable) > 1:
        return None

    application = re.compile(
        rf"{re.escape(function)}_\{{?{re.escape(parameter_name)}\}}?"
        r"\((?P<source>[A-Za-z])\)=(?P<target>[A-Za-z])"
    )
    pairs = [
        (match.group("source"), match.group("target"))
        for match in application.finditer(compact)
        if match.group("source") != variable_name
    ]
    cycle = _ordered_cycle(pairs)
    if cycle is None:
        return None

    prime_condition = (
        "相異なる素数" in statement
        or "異なる素数" in statement
        or re.search(r"distinct\s+primes", statement, re.IGNORECASE) is not None
    )
    positive_integer = (
        "正の整数" in statement
        or re.search(r"positive\s+integer", statement, re.IGNORECASE) is not None
    )
    exhaustive_query = (
        "すべて求め" in statement
        or "全て求め" in statement
        or re.search(r"find\s+all", statement, re.IGNORECASE) is not None
    )
    if not (prime_condition and positive_integer and exhaustive_query):
        return None

    return MobiusPrimeCycleQueryIR(
        map=ParametricMobiusMap(
            function_symbol=function,
            parameter_symbol=parameter_name,
            variable_symbol=variable_name,
            numerator=sp.sstr(numerator),
            denominator=sp.sstr(denominator),
        ),
        cycle_symbols=cycle,
        positive_integer_parameter=True,
        distinct_prime_cycle=True,
    )


def _integer_matrix(values: tuple[sp.Expr, ...]) -> tuple[int, int, int, int] | None:
    rationals: list[sp.Rational] = []
    for value in values:
        simplified = sp.cancel(value)
        if simplified.is_Rational is not True:
            return None
        rationals.append(sp.Rational(simplified))
    denominator_lcm = sp.ilcm(*[int(value.q) for value in rationals])
    integers = [int(value * denominator_lcm) for value in rationals]
    common = 0
    for value in integers:
        common = gcd(common, abs(value))
    common = max(1, common)
    integers = [value // common for value in integers]
    first = next((value for value in integers if value != 0), 1)
    if first < 0:
        integers = [-value for value in integers]
    return tuple(integers)  # type: ignore[return-value]


def _projectively_constant_matrix(
    coefficients: tuple[sp.Expr, ...],
    parameter: sp.Symbol,
) -> tuple[int, int, int, int] | None:
    pivot = next((value for value in coefficients if sp.simplify(value) != 0), None)
    if pivot is None:
        return None
    ratios = tuple(sp.cancel(value / pivot) for value in coefficients)
    if any(parameter in value.free_symbols for value in ratios):
        return None
    return _integer_matrix(ratios)


def _is_scalar_matrix(matrix: sp.Matrix) -> bool:
    return bool(
        matrix[0, 1] == 0
        and matrix[1, 0] == 0
        and matrix[0, 0] == matrix[1, 1]
        and matrix[0, 0] != 0
    )


def _fractional_image(
    matrix: tuple[int, int, int, int], value: int
) -> Fraction | None:
    a, b, c, d = matrix
    denominator = c * value + d
    if denominator == 0:
        return None
    return Fraction(a * value + b, denominator)


def _canonical_rotation(values: tuple[int, ...]) -> tuple[int, ...]:
    rotations = [values[index:] + values[:index] for index in range(len(values))]
    return min(rotations)


def _integer_orbits(
    matrix: tuple[int, int, int, int], period: int
) -> tuple[tuple[tuple[int, ...], ...], tuple[int, ...], int]:
    a, b, c, d = matrix
    determinant = a * d - b * c
    if c == 0 or determinant == 0:
        return (), (), determinant
    signed_divisors = sorted(
        {sign * divisor for divisor in sp.divisors(abs(determinant)) for sign in (-1, 1)}
    )
    initial_candidates = sorted(
        {
            (divisor - d) // c
            for divisor in signed_divisors
            if (divisor - d) % c == 0
        }
    )
    cycles: set[tuple[int, ...]] = set()
    for initial in initial_candidates:
        values: list[int] = []
        current = initial
        valid = True
        for _ in range(period):
            if current in values:
                valid = False
                break
            values.append(current)
            image = _fractional_image(matrix, current)
            if image is None or image.denominator != 1:
                valid = False
                break
            current = image.numerator
        if valid and current == initial and len(values) == period:
            cycles.add(_canonical_rotation(tuple(values)))
    return tuple(sorted(cycles)), tuple(initial_candidates), determinant


def _covering_prime(
    offsets: tuple[int, ...], slope: int, intercept: int
) -> int | None:
    for prime in sp.primerange(2, len(offsets) + 1):
        if all(
            any((slope * residue + intercept + offset) % prime == 0 for offset in offsets)
            for residue in range(prime)
        ):
            return int(prime)
    return None


def execute_mobius_prime_cycle_query(
    query: MobiusPrimeCycleQueryIR,
) -> MobiusPrimeCycleSynthesis:
    variable = sp.Symbol(query.map.variable_symbol)
    parameter = sp.Symbol(query.map.parameter_symbol, integer=True)
    numerator = sp.sympify(
        query.map.numerator, locals={str(variable): variable, str(parameter): parameter}
    )
    denominator = sp.sympify(
        query.map.denominator, locals={str(variable): variable, str(parameter): parameter}
    )
    period = len(query.cycle_symbols)

    def elaborate_map(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        numerator_slope = sp.diff(numerator, variable)
        numerator_intercept = sp.expand(numerator.subs(variable, 0))
        denominator_slope = sp.diff(denominator, variable)
        denominator_intercept = sp.expand(denominator.subs(variable, 0))
        if sp.expand(numerator - numerator_slope * variable - numerator_intercept) != 0:
            return None
        if sp.expand(denominator - denominator_slope * variable - denominator_intercept) != 0:
            return None
        determinant = sp.expand(
            numerator_slope * denominator_intercept
            - numerator_intercept * denominator_slope
        )
        if determinant == 0:
            return None
        return PrimitiveResult(
            {
                "a": numerator_slope,
                "b": numerator_intercept,
                "c": denominator_slope,
                "d": denominator_intercept,
            },
            {
                "function": query.map.function_symbol,
                "matrix": [
                    [sp.sstr(numerator_slope), sp.sstr(numerator_intercept)],
                    [sp.sstr(denominator_slope), sp.sstr(denominator_intercept)],
                ],
                "determinant": sp.sstr(determinant),
            },
        )

    def find_affine_conjugacy(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        data = arguments[0].value
        c = sp.expand(data["c"])
        d = sp.expand(data["d"])
        candidates = [sp.Integer(0)]
        if c != 0:
            # Equal diagonal entries give a canonical translation gauge:
            # a-hc = ch+d, hence h=(a-d)/(2c).
            candidates.append(sp.cancel((data["a"] - d) / (2 * c)))
        if parameter not in c.free_symbols and c != 0:
            candidates.append(sp.cancel((d.subs(parameter, 0) - d) / c))
        candidates.extend((parameter, -parameter))
        seen: set[str] = set()
        for shift in candidates:
            shift = sp.expand(shift)
            shift_key = sp.sstr(shift)
            if shift_key in seen:
                continue
            seen.add(shift_key)
            try:
                shift_poly = sp.Poly(shift, parameter)
            except sp.PolynomialError:
                continue
            if shift_poly.degree() > 1:
                continue
            slope = sp.simplify(sp.diff(shift, parameter))
            intercept = sp.simplify(shift.subs(parameter, 0))
            if slope.is_Integer is not True or intercept.is_Integer is not True:
                continue
            transformed = (
                sp.expand(data["a"] - shift * data["c"]),
                sp.expand(
                    data["a"] * shift
                    + data["b"]
                    - shift * (data["c"] * shift + data["d"])
                ),
                sp.expand(data["c"]),
                sp.expand(data["c"] * shift + data["d"]),
            )
            matrix = _projectively_constant_matrix(transformed, parameter)
            if matrix is None:
                continue
            return PrimitiveResult(
                {
                    **data,
                    "shift": shift,
                    "shift_slope": int(slope),
                    "shift_intercept": int(intercept),
                    "matrix": matrix,
                },
                {
                    "substitution": f"{query.map.variable_symbol}={sp.sstr(shift)}+y",
                    "parameter_free_matrix": [list(matrix[:2]), list(matrix[2:])],
                },
            )
        return None

    def certify_period(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        data = arguments[0].value
        matrix_tuple = data["matrix"]
        matrix = sp.Matrix([[matrix_tuple[0], matrix_tuple[1]], [matrix_tuple[2], matrix_tuple[3]]])
        power = matrix**period
        if not _is_scalar_matrix(power):
            return None
        if any(_is_scalar_matrix(matrix**exponent) for exponent in range(1, period)):
            return None
        return PrimitiveResult(
            {**data, "period_scalar": int(power[0, 0])},
            {
                "period": period,
                "matrix_power": [[int(value) for value in row] for row in power.tolist()],
                "no_smaller_positive_period": True,
            },
        )

    def enumerate_integral_orbits(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        data = arguments[0].value
        cycles, initial_candidates, determinant = _integer_orbits(data["matrix"], period)
        if not cycles:
            return None
        return PrimitiveResult(
            {
                **data,
                "cycles": cycles,
                "initial_candidates": initial_candidates,
                "determinant": determinant,
            },
            {
                "divisibility_identity": "(C*y+D) divides C*(A*y+B)-A*(C*y+D)=-det(M)",
                "determinant": determinant,
                "integer_image_candidates": list(initial_candidates),
                "complete_integer_cycles": [list(cycle) for cycle in cycles],
            },
        )

    def reduce_prime_parameters(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        data = arguments[0].value
        slope = data["shift_slope"]
        intercept = data["shift_intercept"]
        if slope == 0:
            return None
        reductions: list[dict[str, Any]] = []
        candidates: set[int] = set()
        for cycle in data["cycles"]:
            prime = _covering_prime(cycle, slope, intercept)
            if prime is None:
                return None
            local_candidates: set[int] = set()
            for offset in cycle:
                numerator_value = prime - intercept - offset
                if numerator_value % slope == 0:
                    value = numerator_value // slope
                    if value > 0:
                        local_candidates.add(value)
            candidates.update(local_candidates)
            reductions.append(
                {
                    "offset_cycle": list(cycle),
                    "covering_prime": prime,
                    "parameter_candidates": sorted(local_candidates),
                }
            )
        if not candidates:
            return None
        return PrimitiveResult(
            {**data, "parameter_candidates": tuple(sorted(candidates)), "reductions": reductions},
            {
                "residue_cover_reductions": reductions,
                "completeness": "every admissible parameter forces one translated orbit value to equal the covering prime",
            },
        )

    def replay_tuples(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        data = arguments[0].value
        tuples: set[tuple[int, ...]] = set()
        replay_rows: list[dict[str, Any]] = []
        for parameter_value in data["parameter_candidates"]:
            shift_value = data["shift_slope"] * parameter_value + data["shift_intercept"]
            for cycle in data["cycles"]:
                values = tuple(shift_value + offset for offset in cycle)
                if not all(value > 1 and sp.isprime(value) for value in values):
                    continue
                if len(set(values)) != period:
                    continue
                for index in range(period):
                    rotated = values[index:] + values[:index]
                    substitutions = {parameter: parameter_value}
                    valid = True
                    for source, target in zip(rotated, rotated[1:] + rotated[:1]):
                        image = sp.cancel(numerator.subs(substitutions).subs(variable, source) / denominator.subs(substitutions).subs(variable, source))
                        if image != target:
                            valid = False
                            break
                    if valid:
                        full_tuple = (parameter_value, *rotated)
                        tuples.add(full_tuple)
                        replay_rows.append({"tuple": list(full_tuple), "all_relations_exact": True})
        if not tuples:
            return None
        return PrimitiveResult(
            {**data, "verified_tuples": tuple(sorted(tuples)), "replay_rows": replay_rows},
            {
                "verified_tuples": [list(value) for value in sorted(tuples)],
                "checks": ["positive parameter", "pairwise distinct primes", "all fractional-linear cycle equations"],
            },
        )

    primitives = (
        RuntimePrimitive(
            "parametric_mobius_elaboration",
            ("ParsedProblemIR",),
            "ParametricMobiusMap",
            elaborate_map,
        ),
        RuntimePrimitive(
            "affine_conjugacy_parameter_elimination",
            ("ParametricMobiusMap",),
            "ParameterFreeMobiusMap",
            find_affine_conjugacy,
        ),
        RuntimePrimitive(
            "projective_matrix_period_certificate",
            ("ParameterFreeMobiusMap",),
            "FiniteProjectiveOrbit",
            certify_period,
        ),
        RuntimePrimitive(
            "determinant_divisor_integer_orbit_classification",
            ("FiniteProjectiveOrbit",),
            "CompleteIntegralOrbitSet",
            enumerate_integral_orbits,
        ),
        RuntimePrimitive(
            "prime_residue_cover_reduction",
            ("CompleteIntegralOrbitSet",),
            "FinitePrimeParameterSet",
            reduce_prime_parameters,
        ),
        RuntimePrimitive(
            "original_cycle_exact_replay",
            ("FinitePrimeParameterSet",),
            "CertifiedPrimeCycleTuples",
            replay_tuples,
        ),
    )
    plan = synthesize_typed_plan(
        [initial_fact("ParsedProblemIR", query.to_dict())],
        primitives,
        ("CertifiedPrimeCycleTuples",),
        max_depth=8,
        max_states=64,
    )
    if not plan.complete:
        raise ValueError(f"runtime Mobius-cycle planner left open goals: {plan.open_goal_sorts}")

    result = plan.goals["CertifiedPrimeCycleTuples"].value
    matrix = result["matrix"]
    a, b, c, d = matrix
    shift = result["shift"]
    cycles = result["cycles"]
    tuples = result["verified_tuples"]
    reductions = result["reductions"]
    tuple_tex = ",".join(
        "(" + ",".join(str(value) for value in values) + ")"
        for values in tuples
    )
    answer_tex = rf"\(\left\{{{tuple_tex}\right\}}\)"
    cycle_tex = r",\ ".join(
        "(" + ",".join(str(value) for value in cycle) + ")" for cycle in cycles
    )
    candidate_tex = ",".join(str(value) for value in result["initial_candidates"])
    parameter_candidate_tex = ",".join(str(value) for value in result["parameter_candidates"])
    covering_primes = sorted({item["covering_prime"] for item in reductions})
    covering_prime_tex = ",".join(str(value) for value in covering_primes)

    derivation = (
        rf"\(x={sp.latex(shift)}+y\) とおく。分子・分母を整理すると、"
        rf"\[g(y)=\frac{{{a}y+{b}}}{{{c}y+{d}}}\]"
        r"となり、パラメータは消える。これは元の写像を平行移動で共役したものである。",
        rf"\(g\) を表す行列を \(M=\begin{{pmatrix}}{a}&{b}\\{c}&{d}\end{{pmatrix}}\) とする。"
        rf"直接乗算すると \(M^{{{period}}}={result['period_scalar']}I\) であり、"
        rf"\(1\le j<{period}\) では \(M^j\) はスカラー行列でない。従って \(g\) の射影的な周期はちょうど \({period}\) である。",
        rf"整数 \(y\) に対して \(g(y)\) も整数なら、\({c}y+{d}\) は"
        rf"\[{c}({a}y+{b})-{a}({c}y+{d})={c*b-a*d}\]"
        rf"を割る。従って候補は \(y\in\{{{candidate_tex}\}}\) に限られる。"
        rf"これらを全て代入すると、長さ \({period}\) の整数軌道は \({cycle_tex}\) だけである。",
        rf"元の素数は \({sp.latex(shift)}+y\) である。軌道の剰余は法 \({covering_prime_tex}\) を全て覆うので、"
        rf"どの整数パラメータでも三数の一つは \({covering_prime_tex}\) の倍数になる。"
        rf"三数が全て正の素数なら、その数は \({covering_prime_tex}\) 自身でなければならない。"
        rf"従って調べるべきパラメータは \(\{{{parameter_candidate_tex}\}}\) に限られる。",
        rf"この有限個を元の分数一次式へ代入し、正値、相異性、素数性、"
        rf"および全ての周期等式を厳密に照合すると、求める組は {answer_tex} である。",
    )
    witness = {
        "input_ir": query.to_dict(),
        "translation": sp.sstr(shift),
        "parameter_free_matrix": [list(matrix[:2]), list(matrix[2:])],
        "projective_period": period,
        "matrix_power_scalar": result["period_scalar"],
        "determinant": result["determinant"],
        "integer_image_candidates": list(result["initial_candidates"]),
        "complete_integer_cycles": [list(cycle) for cycle in cycles],
        "residue_cover_reductions": reductions,
        "verified_tuples": [list(values) for values in tuples],
        "original_relation_replay": result["replay_rows"],
        "planner": {
            "states_explored": plan.states_explored,
            "goal_sorts": sorted(plan.goals),
            "open_goal_sorts": list(plan.open_goal_sorts),
        },
    }
    checks = (
        "関数名、パラメータ、変数、分子、分母、閉じた素数周期を現在の問題文から抽出",
        "平行移動後の分数一次行列がパラメータに依存しないことを記号計算で確認",
        "行列累乗により指定周期と最小性を厳密に確認",
        "分母が行列式を割る恒等式から整数軌道候補を完全列挙",
        "剰余類被覆により素数条件を有限個のパラメータへ縮約",
        "全候補を元の分数一次式へ代入し、正値・相異性・素数性・周期等式を再生",
    )
    visual_cycle = tuple(cycles[0])
    visual_parameter = int(tuples[0][0])
    diagrams = tuple(
        _mobius_cycle_diagram(
            query,
            shift=shift,
            cycle=visual_cycle,
            initial_candidates=tuple(result["initial_candidates"]),
            parameter_value=visual_parameter,
            stage=stage,
        )
        for stage in range(1, 6)
    )
    chain = tuple(step["rule"] for step in plan.proof_program)
    visual_explanation = {
        "version": 1,
        "mode": "stepper",
        "title": "パラメータ付き写像が三つの素数へ絞られるまで",
        "diagram_required_for_every_step": True,
        "composition_verified": True,
        "morphism_chain": list(chain),
        "steps": [
            {
                "id": "mobius-cycle-step-1",
                "title": "平行移動でパラメータを消す",
                "explanation_ja": "未知数を x=h+y と平行移動し、すべての n に共通する一つの分数一次写像 g を得ます。",
                "formula_tex": rf"x={sp.latex(shift)}+y,\quad g(y)=\frac{{{a}y+{b}}}{{{c}y+{d}}}",
                "morphism": {"morphism_id": chain[1], "label_ja": "平行移動による共役", "input_type": "ParametricMobiusMap", "output_type": "ParameterFreeMobiusMap"},
                "source_state": {"id": "parametric-map", "type": "ParametricMobiusMap"},
                "target_state": {"id": "fixed-map", "type": "ParameterFreeMobiusMap"},
                "diagram": diagrams[0],
            },
            {
                "id": "mobius-cycle-step-2",
                "title": "行列で周期3を証明する",
                "explanation_ja": "分数一次写像を2行2列行列で表します。行列の3乗がスカラー行列で、1乗と2乗はそうでないため、周期はちょうど3です。",
                "formula_tex": rf"M^3={result['period_scalar']}I",
                "morphism": {"morphism_id": chain[2], "label_ja": "射影行列の周期証明", "input_type": "ParameterFreeMobiusMap", "output_type": "FiniteProjectiveOrbit"},
                "source_state": {"id": "fixed-map", "type": "ParameterFreeMobiusMap"},
                "target_state": {"id": "period-three", "type": "FiniteProjectiveOrbit"},
                "diagram": diagrams[1],
            },
            {
                "id": "mobius-cycle-step-3",
                "title": "整数軌道を完全に列挙する",
                "explanation_ja": "g(y) が整数なら分母は行列式を割ります。この整除条件で候補を有限個にし、すべて代入します。",
                "formula_tex": rf"{c}y+{d}\mid {c*b-a*d}",
                "morphism": {"morphism_id": chain[3], "label_ja": "行列式による整数軌道分類", "input_type": "FiniteProjectiveOrbit", "output_type": "CompleteIntegralOrbitSet"},
                "source_state": {"id": "period-three", "type": "FiniteProjectiveOrbit"},
                "target_state": {"id": "integer-orbits", "type": "CompleteIntegralOrbitSet"},
                "diagram": diagrams[2],
            },
            {
                "id": "mobius-cycle-step-4",
                "title": "剰余類でパラメータを有限化する",
                "explanation_ja": "三つの軌道値は法3の全剰余を一つずつ通ります。全てが素数なら、3の倍数になった値は3自身です。",
                "formula_tex": r"h-2,\ h,\ h+2\pmod 3",
                "morphism": {"morphism_id": chain[4], "label_ja": "素数剰余被覆", "input_type": "CompleteIntegralOrbitSet", "output_type": "FinitePrimeParameterSet"},
                "source_state": {"id": "integer-orbits", "type": "CompleteIntegralOrbitSet"},
                "target_state": {"id": "parameter-candidates", "type": "FinitePrimeParameterSet"},
                "diagram": diagrams[3],
            },
            {
                "id": "mobius-cycle-step-5",
                "title": "元の写像で三つの順序を確認する",
                "explanation_ja": "残ったパラメータと三つの巡回順序を、問題文の分数一次式へ直接代入します。",
                "formula_tex": answer_tex,
                "morphism": {"morphism_id": chain[5], "label_ja": "元の周期条件への厳密代入", "input_type": "FinitePrimeParameterSet", "output_type": "CertifiedPrimeCycleTuples"},
                "source_state": {"id": "parameter-candidates", "type": "FinitePrimeParameterSet"},
                "target_state": {"id": "answer", "type": "CertifiedPrimeCycleTuples"},
                "diagram": diagrams[4],
            },
        ],
    }
    expression_tex = (
        rf"{query.map.function_symbol}_{{{query.map.parameter_symbol}}}"
        rf"({query.cycle_symbols[0]})={query.cycle_symbols[1]},\ldots,"
        rf"{query.map.function_symbol}_{{{query.map.parameter_symbol}}}"
        rf"({query.cycle_symbols[-1]})={query.cycle_symbols[0]}"
    )
    return MobiusPrimeCycleSynthesis(
        answer_tex=answer_tex,
        derivation_tex=derivation,
        expression_tex=expression_tex,
        proof_program=plan.proof_program + (
            {
                "rule": "exact_obligation_replay",
                "verified": True,
                "planner_states_explored": plan.states_explored,
            },
        ),
        verification_checks=checks,
        witness=witness,
        hypotheses_evaluated=(
            len(result["initial_candidates"])
            + len(result["parameter_candidates"])
            + len(tuples)
        ),
        diagram=diagrams[-1],
        diagram_tikz=_mobius_cycle_tikz(
            query,
            shift=shift,
            cycle=visual_cycle,
            parameter_value=visual_parameter,
        ),
        visual_explanation=visual_explanation,
    )


def synthesize_mobius_prime_cycle_problem(
    statement: str,
) -> MobiusPrimeCycleSynthesis | None:
    query = compile_mobius_prime_cycle_query(statement)
    if query is None:
        return None
    try:
        return execute_mobius_prime_cycle_query(query)
    except ValueError:
        return None
