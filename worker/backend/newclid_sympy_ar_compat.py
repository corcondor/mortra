"""Compatibility wrapper for Newclid's SymPy constant-length enumerator.

Newclid 3.0 stores ``RatiosTable.expected_lconsts`` as a dictionary but its
enumerator iterates over the dictionary keys as if they were ``(key, value)``
pairs.  Keep the upstream deductor intact except for that collection boundary.
"""

from __future__ import annotations

from fractions import Fraction
import importlib
from typing import Iterator, cast

import sympy as sp
from newclid.deductors.sympy_ar.algebraic_manipulator import SympyARDeductor
from newclid.deductors.sympy_ar.table_ratios import RatiosTable
from newclid.numerical import close_enough
from newclid.predicate_types import PredicateArgument
from newclid.predicates._index import PredicateType
from newclid.predicates.different import Diff
from newclid.problem import PredicateConstruction
from newclid.tools import fraction_to_ratio, get_quotient


def enumerate_lconsts_items(
    table: RatiosTable,
) -> Iterator[tuple[PredicateConstruction, sp.Expr]]:
    """Enumerate constant lengths from the table's dictionary items."""

    for segment, expected_length_value in table.expected_lconsts.copy().items():
        lconst_expression = cast(sp.Expr, segment)
        subbed_in = table.inner_table.substitute_in_existing_expressions(
            lconst_expression
        )
        if subbed_in.free_symbols:
            continue

        length: sp.Expr = sp.exp(subbed_in)
        if not close_enough(float(length), expected_length_value):
            continue

        p0, p1 = table.sympy_symbol_to_str_symbol[segment]
        points = tuple(PredicateArgument(point.name) for point in (p0, p1))
        length_arg = PredicateArgument(
            fraction_to_ratio(Fraction(get_quotient(length)))
        )
        yield (
            PredicateConstruction.from_predicate_type_and_args(
                PredicateType.CONSTANT_LENGTH,
                points + (length_arg,),
            ),
            lconst_expression,
        )


class MORTRASympyARDeductor(SympyARDeductor):
    """Newclid's SymPy AR deductor with the constant-length iterator repaired."""

    def __init__(self) -> None:
        super().__init__()
        self.ratio_enumerators[0] = enumerate_lconsts_items


def install_variadic_diff_compat() -> None:
    """Teach Newclid 3.0's constructor about its own variadic ``diff`` rules."""

    predicates = importlib.import_module("newclid.predicates")
    original = predicates.predicate_from_construction
    if getattr(original, "_mortra_variadic_diff", False):
        return

    def predicate_from_construction_compat(construction, points_registry):
        if construction.predicate_type == PredicateType.DIFFERENT:
            canonical_args = Diff.preparse(construction.args)
            if canonical_args is None:
                return None
            return Diff(
                points=tuple(points_registry.names2points(canonical_args))
            )
        return original(construction, points_registry)

    predicate_from_construction_compat._mortra_variadic_diff = True
    predicates.predicate_from_construction = predicate_from_construction_compat
    # Newclid imports this function directly in several runtime modules.  Keep
    # those bound references synchronized without modifying site-packages.
    for module_name in (
        "newclid.agent.follow_deductions",
        "newclid.agent.human_agent",
        "newclid.deductors.sympy_ar.algebraic_manipulator",
        "newclid.problem",
        "newclid.proof_data",
        "newclid.proof_state",
        "newclid.rule_matching.mapping_matcher",
    ):
        module = importlib.import_module(module_name)
        if hasattr(module, "predicate_from_construction"):
            module.predicate_from_construction = predicate_from_construction_compat


__all__ = [
    "MORTRASympyARDeductor",
    "enumerate_lconsts_items",
    "install_variadic_diff_compat",
]
