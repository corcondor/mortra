import pytest

pytest.importorskip("newclid")

from newclid.deductors.sympy_ar.ar_table import ARTable
from newclid.deductors.sympy_ar.table_ratios import RatiosTable
from newclid.jgex.formulation import JGEXFormulation
from newclid.jgex.problem_builder import JGEXProblemBuilder
from newclid.api import GeometricSolverBuilder, PythonDefault
import numpy as np

from worker.backend.newclid_sympy_ar_compat import (
    enumerate_lconsts_items,
    install_variadic_diff_compat,
)


def test_constant_length_enumerator_uses_dictionary_items() -> None:
    table = RatiosTable(ARTable())
    # An empty table is sufficient to distinguish the repaired collection
    # protocol from the upstream unpacking failure once deductions begin.
    assert list(enumerate_lconsts_items(table)) == []


def test_variadic_diff_from_official_rules_is_numerically_constructible() -> None:
    install_variadic_diff_compat()
    formulation = JGEXFormulation.from_text(
        "a b c = triangle a b c ? cong a b a b"
    )
    builder = JGEXProblemBuilder(rng=np.random.default_rng(5), problem=formulation)
    setup = builder.build()

    from newclid.predicates import predicate_from_construction
    from newclid.predicate_types import PredicateArgument
    from newclid.predicates._index import PredicateType
    from newclid.problem import PredicateConstruction

    construction = PredicateConstruction.from_predicate_type_and_args(
        PredicateType.DIFFERENT,
        tuple(PredicateArgument(name) for name in ("a", "b", "c")),
    )
    solver = GeometricSolverBuilder(
        rng=np.random.default_rng(5),
        api_default=PythonDefault(use_sympy_ar=False),
    ).build(setup)
    predicate = predicate_from_construction(
        construction,
        solver.proof_state.symbols.points,
    )

    assert predicate is not None
    assert len(predicate.points) == 3
