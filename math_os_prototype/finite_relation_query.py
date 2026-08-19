"""Executable finite-set and state relations for arithmetic prose.

Only two algebraic laws are introduced here:

* Partition: total = number_of_fibres * fibre_size
* StateTransition: final = initial + signed_delta

Nouns and numeric values are alpha-renamable inputs.  The compiler emits an
equation with one typed hole and the backend solves and rechecks that equation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction
import re
from typing import Any

import sympy as sp

try:
    from math_os_prototype.quantity_reasoner import NUMBER_RE, parse_number
except ImportError:
    from quantity_reasoner import NUMBER_RE, parse_number


@dataclass(frozen=True)
class FiniteRelationQueryIR:
    relation: str
    equation: str
    variable: str
    output_sort: str
    premise_values: list[str]
    evidence: list[str]
    lowering_certificate: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _number(raw: str) -> Fraction | None:
    return parse_number(raw.strip())


def _show(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def _numeric_values(source: str) -> list[Fraction]:
    values: list[Fraction] = []
    for match in re.finditer(NUMBER_RE, source):
        value = parse_number(match.group(0))
        if value is not None:
            values.append(value)
    return values


def _partition_ir(
    total: Fraction,
    known_factor: Fraction,
    source_values: list[Fraction],
    evidence: list[str],
    output_sort: str,
) -> FiniteRelationQueryIR | None:
    if total < 0 or known_factor <= 0 or sorted(source_values) != sorted([total, known_factor]):
        return None
    return FiniteRelationQueryIR(
        relation="Partition",
        equation=f"{_show(total)}={_show(known_factor)}*x",
        variable="x",
        output_sort=output_sort,
        premise_values=[_show(value) for value in source_values],
        evidence=evidence,
        lowering_certificate={
            "kind": "typed_finite_relation",
            "law": "total = fibre_count * fibre_size",
            "hole_count": 1,
            "all_numeric_premises_consumed": True,
        },
    )


def compile_finite_relation_query(text: str) -> FiniteRelationQueryIR | None:
    source = re.sub(r"\s+", " ", text.lower().replace("’", "'").replace(r"\$", "$")).strip()
    if "\\" in source:
        return None
    values = _numeric_values(source)

    # A finite set distributed over an indexed family; the query observes one fibre.
    among = re.search(
        rf"(?P<total>{NUMBER_RE})\s+[a-z-]+\s+[^.?!]{{0,45}}?\bamong\s+"
        rf"(?P<count>{NUMBER_RE})\s+(?:friends?|people|persons?|children|students?)\b",
        source,
    )
    if among and re.search(r"\bhow\s+many\b[^?]*\beach\b|\bhow\s+many\s+would\s+each\b", source):
        total, count = _number(among.group("total")), _number(among.group("count"))
        if total is not None and count is not None:
            return _partition_ir(total, count, values, [among.group(0), "query: fibre_size"], "FibreSize")

    # A container family and its total contents; observe contents per container.
    containers = re.search(
        rf"(?P<count>{NUMBER_RE})\s+(?:bags?|boxes?|packs?|packets?|baskets?|crates?)\b"
        rf".*?\btotal\s+(?P<total>{NUMBER_RE})\b",
        source,
    )
    if containers and re.search(r"\bhow\s+many\b[^?]*\beach\s+(?:bag|box|pack|packet|basket|crate)\b", source):
        total, count = _number(containers.group("total")), _number(containers.group("count"))
        if total is not None and count is not None:
            return _partition_ir(total, count, values, [containers.group(0), "query: fibre_size"], "FibreSize")

    # A group size is given and the number of groups is queried.
    grouped = re.search(
        rf"\bgroups?\s+of\s+(?P<size>{NUMBER_RE})\b.*?\b(?:has|have|total(?:s|ed)?)\s+"
        rf"(?P<total>{NUMBER_RE})\b",
        source,
    )
    if grouped and re.search(r"\bhow\s+many\s+groups?\b", source):
        total, size = _number(grouped.group("total")), _number(grouped.group("size"))
        if total is not None and size is not None:
            return _partition_ir(total, size, values, [grouped.group(0), "query: fibre_count"], "FibreCount")

    # Total objects and an explicit per-person fibre size; observe the index set size.
    per_person = re.search(
        rf"(?P<total>{NUMBER_RE})\s+[a-z-]+\b.*?\beach\b[^.?!]{{0,45}}?\b(?:get|gets|receive|receives|take|takes)\s+"
        rf"(?P<size>{NUMBER_RE})\b",
        source,
    )
    if per_person and re.search(r"\bhow\s+many\s+(?:friends?|people|persons?|children|students?)\b", source):
        total, size = _number(per_person.group("total")), _number(per_person.group("size"))
        if total is not None and size is not None:
            return _partition_ir(total, size, values, [per_person.group(0), "query: fibre_count"], "FibreCount")

    # Cutting every source object into a fixed number of slices is the same map.
    sliced = re.search(
        rf"\beach\s+[a-z-]+\s+into\s+(?P<size>{NUMBER_RE})\s+slices?\b"
        rf".*?\btotal\s+(?P<total>{NUMBER_RE})\b",
        source,
    )
    if sliced and re.search(r"\bhow\s+many\b[^?]*(?:had|have|make|made)\b", source):
        total, size = _number(sliced.group("total")), _number(sliced.group("size"))
        if total is not None and size is not None:
            return _partition_ir(total, size, values, [sliced.group(0), "query: source_count"], "FibreCount")

    # Observe the nonnegative transition magnitude between two explicit states.
    states = re.search(
        rf"\bhad\s+(?P<initial>{NUMBER_RE})\s+(?P<object>[a-z-]+)\b"
        rf".*?\bnow\b[^.?!]{{0,40}}?\bhas\s+(?P<final>{NUMBER_RE})\s+(?P=object)\b",
        source,
    )
    if states and re.search(r"\bhow\s+many\s+did\b", source):
        initial, final = _number(states.group("initial")), _number(states.group("final"))
        if initial is not None and final is not None and sorted(values) == sorted([initial, final]):
            sign = 1 if final >= initial else -1
            return FiniteRelationQueryIR(
                relation="StateTransition",
                equation=f"{_show(final)}={_show(initial)}{'+x' if sign > 0 else '-x'}",
                variable="x",
                output_sort=f"Delta[{states.group('object')}]",
                premise_values=[_show(value) for value in values],
                evidence=[states.group(0), "query: transition_magnitude"],
                lowering_certificate={
                    "kind": "typed_finite_relation",
                    "law": "final = initial + signed_delta",
                    "hole_count": 1,
                    "all_numeric_premises_consumed": True,
                },
            )
    return None


def execute_finite_relation_query(payload: dict[str, Any]) -> dict[str, Any]:
    variable = sp.Symbol(str(payload["variable"]), real=True, nonnegative=True)
    left, right = str(payload["equation"]).split("=", 1)
    relation = sp.Eq(sp.sympify(left, locals={variable.name: variable}), sp.sympify(right, locals={variable.name: variable}))
    solutions = sp.solve(relation, variable)
    solutions = [value for value in solutions if value.is_nonnegative is not False and not value.free_symbols]
    if len(solutions) != 1:
        raise ValueError("finite relation does not determine one nonnegative observation")
    value = sp.simplify(solutions[0])
    if sp.simplify(relation.lhs.subs(variable, value) - relation.rhs.subs(variable, value)) != 0:
        raise ValueError("finite relation solution failed substitution verification")
    return {
        "answer_exact": sp.sstr(value),
        "query_operator": payload["relation"],
        "output_sort": payload["output_sort"],
        "constraint_count": 1,
        "verified": True,
    }
