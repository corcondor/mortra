"""Normalize legacy AlphaGeometry construction syntax by typed I/O roles.

Older JGEX corpora sometimes omit a construction's output arguments because
the left-hand side already names them, and sometimes place those outputs at the
end of the right-hand side.  Current Newclid definitions require every
argument in definition order.  This module reconciles the two dialects from a
construction's declared ``output_points`` rather than from problem names.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from newclid.jgex.clause import JGEXClause, JGEXConstruction
from newclid.jgex.definition import JGEXDefinition
from newclid.jgex.formulation import JGEXFormulation
from newclid.predicate_types import PredicateArgument


@dataclass(frozen=True)
class JGEXNormalizationReport:
    rewritten_constructions: int = 0
    unchanged_constructions: int = 0
    unresolved_constructions: int = 0

    def __add__(self, other: "JGEXNormalizationReport") -> "JGEXNormalizationReport":
        return JGEXNormalizationReport(
            rewritten_constructions=(
                self.rewritten_constructions + other.rewritten_constructions
            ),
            unchanged_constructions=(
                self.unchanged_constructions + other.unchanged_constructions
            ),
            unresolved_constructions=(
                self.unresolved_constructions + other.unresolved_constructions
            ),
        )


def _semantic_point_name(value: PredicateArgument) -> str:
    return str(value).split("@", maxsplit=1)[0]


def normalize_legacy_construction(
    construction: JGEXConstruction,
    clause_points: tuple[PredicateArgument, ...],
    definition: JGEXDefinition | None,
) -> tuple[JGEXConstruction, JGEXNormalizationReport]:
    """Return a construction with outputs aligned to its definition signature."""

    if definition is None or not definition.output_points:
        return construction, JGEXNormalizationReport(unchanged_constructions=1)

    output_variables = tuple(definition.output_points)
    if len(clause_points) != len(output_variables):
        return construction, JGEXNormalizationReport(unresolved_constructions=1)

    definition_args = tuple(definition.args)
    non_output_variables = tuple(
        variable for variable in definition_args if variable not in output_variables
    )
    original_args = construction.args

    if len(original_args) == len(non_output_variables):
        output_values = clause_points
        non_output_values = original_args
    elif len(original_args) == len(definition_args):
        remaining = list(original_args)
        matched_outputs: list[PredicateArgument] = []
        for declared_output in clause_points:
            declared_name = _semantic_point_name(declared_output)
            match = next(
                (
                    index
                    for index, value in enumerate(remaining)
                    if _semantic_point_name(value) == declared_name
                ),
                None,
            )
            if match is None:
                return construction, JGEXNormalizationReport(
                    unresolved_constructions=1
                )
            matched_outputs.append(remaining.pop(match))
        output_values = tuple(matched_outputs)
        non_output_values = tuple(remaining)
        if len(non_output_values) != len(non_output_variables):
            return construction, JGEXNormalizationReport(unresolved_constructions=1)
    else:
        return construction, JGEXNormalizationReport(unresolved_constructions=1)

    values_by_variable: dict[str, PredicateArgument] = {
        str(variable): value
        for variable, value in zip(output_variables, output_values, strict=True)
    }
    values_by_variable.update(
        {
            str(variable): value
            for variable, value in zip(
                non_output_variables, non_output_values, strict=True
            )
        }
    )
    normalized_args = tuple(values_by_variable[str(variable)] for variable in definition_args)
    normalized = JGEXConstruction.from_name_and_args(
        construction.name, normalized_args
    )
    if normalized == construction:
        return construction, JGEXNormalizationReport(unchanged_constructions=1)
    return normalized, JGEXNormalizationReport(rewritten_constructions=1)


def normalize_legacy_clause(
    clause: JGEXClause,
    definitions: Mapping[str, JGEXDefinition],
) -> tuple[JGEXClause, JGEXNormalizationReport]:
    constructions: list[JGEXConstruction] = []
    report = JGEXNormalizationReport()
    for construction in clause.constructions:
        normalized, item_report = normalize_legacy_construction(
            construction,
            clause.points,
            definitions.get(construction.name),
        )
        constructions.append(normalized)
        report += item_report
    return (
        JGEXClause(points=clause.points, constructions=tuple(constructions)),
        report,
    )


def normalize_legacy_formulation(
    formulation: JGEXFormulation,
    definitions: Mapping[str, JGEXDefinition],
) -> tuple[JGEXFormulation, JGEXNormalizationReport]:
    """Normalize setup and auxiliary clauses while preserving goals verbatim."""

    report = JGEXNormalizationReport()
    setup: list[JGEXClause] = []
    auxiliary: list[JGEXClause] = []
    for clause in formulation.setup_clauses:
        normalized, item_report = normalize_legacy_clause(clause, definitions)
        setup.append(normalized)
        report += item_report
    for clause in formulation.auxiliary_clauses:
        normalized, item_report = normalize_legacy_clause(clause, definitions)
        auxiliary.append(normalized)
        report += item_report
    return (
        JGEXFormulation(
            name=formulation.name,
            setup_clauses=tuple(setup),
            auxiliary_clauses=tuple(auxiliary),
            goals=formulation.goals,
        ),
        report,
    )


def report_as_dict(report: JGEXNormalizationReport) -> dict[str, Any]:
    return {
        "rewritten_constructions": report.rewritten_constructions,
        "unchanged_constructions": report.unchanged_constructions,
        "unresolved_constructions": report.unresolved_constructions,
    }
