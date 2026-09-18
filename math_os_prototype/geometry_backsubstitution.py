"""Reading a goal backwards through a primitive, to get the condition its input must meet.

The contract-directed search offers a last operation only when one of the
operation's guaranteed relations matches a goal atom syntactically. A goal such
as "u is collinear with e and c, at the distance |ab| from e, on a line parallel
to ec" matches nothing, because no primitive guarantees that conjunction about
its output; so no last operation is offered at all and the search never gets to
ask what its input would have to be.

This module asks that question. For a candidate last operation

    u = F(w, q1, ..., qk)          w unknown, the other arguments known points

the kernel already publishes F's output as a rational function of its inputs
(`primitive_contracts()[F]["witness"]`). Substituting that function into the
goal polynomials turns a condition on u into a condition on w:

    Goal(F(w, q...)) = 0     together with     Defined(F(w, q...)) != 0

The result is the specification the intermediate point must satisfy. It is not a
formula written for one problem: the substitution is the same for every
primitive, every goal predicate and every binding, and what comes out is kept as
polynomials rather than translated back into the geometric vocabulary, so a
condition with no name in that vocabulary is kept rather than dropped.

Nothing here solves polynomial systems. A specification is decided at a
candidate point by exact substitution, which is what the rest of the search
already does with its points.
"""
from __future__ import annotations

from collections import Counter
from functools import lru_cache

import sympy as sp

from math_os_prototype import geometry_contracts as gc
from math_os_prototype import geometry_relational_dsl as rdsl
from math_os_prototype import geometry_semantic_dsl as dsl

UNKNOWN = (sp.Symbol("wx", real=True), sp.Symbol("wy", real=True))
OUTPUT = (sp.Symbol("ux", real=True), sp.Symbol("uy", real=True))


class BackwardBudget(RuntimeError):
    """The expression work reached its bound: the search is incomplete, not the goal impossible."""


def charge(counter, kind, amount=1):
    if counter is not None:
        counter[kind] += amount


# ---------------------------------------------------------------------------
# The two sides of the substitution
# ---------------------------------------------------------------------------

def goal_polynomials(goal_atoms, coordinates, *, unknown="u", counter=None):
    """Each goal atom as a polynomial in the unknown's coordinates, the rest concrete."""
    elaborator = gc._JGEXElaborator()
    elaborator.coordinates.update({name: tuple(sp.Rational(v) for v in xy)
                                   for name, xy in coordinates.items() if name != unknown})
    elaborator.coordinates[unknown] = OUTPUT
    polynomials = []
    for predicate, arguments in goal_atoms:
        charge(counter, "backward_goal_polynomials")
        polynomials.append((predicate, tuple(arguments), sp.expand(dsl.lower(elaborator, predicate,
                                                                            tuple(arguments)))))
    return polynomials


@lru_cache(maxsize=None)
def witness_expressions(family):
    """The primitive's output as two rational functions of its inputs, from its kernel certificate."""
    contract = rdsl.primitive_contracts()[family]
    parameters = tuple(contract["params"])
    symbols = {p+a: sp.Symbol(p+a, real=True) for p in parameters for a in ("x", "y")}
    witness = tuple(gc.parse(expression, symbols) for expression in contract["witness"]["y"])
    guards = tuple(gc.parse(guard, symbols) for guard in contract["guards"])
    return parameters, witness, guards, symbols


def _replacement(parameters, symbols, binding, unknown_parameter, coordinates):
    replacement = {}
    for parameter in parameters:
        if parameter == unknown_parameter:
            replacement[symbols[parameter+"x"]] = UNKNOWN[0]
            replacement[symbols[parameter+"y"]] = UNKNOWN[1]
        else:
            x, y = coordinates[binding[parameter]]
            replacement[symbols[parameter+"x"]] = sp.Rational(x)
            replacement[symbols[parameter+"y"]] = sp.Rational(y)
    return replacement


def intermediate_specification(goal_atoms, coordinates, family, binding, unknown_parameter, *,
                               counter=None, degree_bound=6, term_bound=400, polynomials=None):
    """What the unknown input of `family` must satisfy for its output to meet every goal.

    Returns the equalities the point must satisfy, the expressions that must stay
    non-zero for the operation to be defined, and the applicability atoms that
    mention the unknown. Returns None when the conditions cannot hold at all, and
    raises `BackwardBudget` when an expression passes the stated bounds.
    """
    parameters, witness, guards, symbols = witness_expressions(family)
    replacement = _replacement(parameters, symbols, binding, unknown_parameter, coordinates)
    charge(counter, "backward_substitutions")
    output = [expression.subs(replacement, simultaneous=True) for expression in witness]
    equalities, nonzero = [], []
    for expression in output:
        _, denominator = sp.fraction(sp.together(expression))
        if denominator.free_symbols:
            nonzero.append(sp.expand(denominator))
    for guard in guards:
        substituted = guard.subs(replacement, simultaneous=True)
        numerator, _ = sp.fraction(sp.together(substituted))
        numerator = sp.expand(numerator)
        if numerator == 0:
            charge(counter, "backward_guard_identically_zero")
            return None
        if numerator.free_symbols:
            nonzero.append(numerator)
    polynomials = polynomials if polynomials is not None else goal_polynomials(
        goal_atoms, coordinates, counter=counter)
    for predicate, arguments, polynomial in polynomials:
        charge(counter, "backward_goal_substitutions")
        substituted = polynomial.subs({OUTPUT[0]: output[0], OUTPUT[1]: output[1]}, simultaneous=True)
        numerator, denominator = sp.fraction(sp.together(substituted))
        numerator = sp.expand(numerator)
        charge(counter, "backward_expression_terms", len(sp.Add.make_args(numerator)))
        if numerator == 0:
            continue                                   # the goal holds for every admissible w
        if not numerator.free_symbols:
            charge(counter, "backward_unsatisfiable")
            return None                                # a non-zero constant: no w can satisfy it
        polynomial_form = sp.Poly(numerator, *UNKNOWN)
        if polynomial_form.total_degree() > degree_bound or len(polynomial_form.terms()) > term_bound:
            charge(counter, "backward_over_bound")
            raise BackwardBudget(f"{family}: degree {polynomial_form.total_degree()}, "
                                 f"{len(polynomial_form.terms())} terms")
        equalities.append(numerator)
        if denominator.free_symbols:
            nonzero.append(sp.expand(denominator))
    applicability = [(requirement["atom"], tuple(requirement["args"]))
                     for requirement in rdsl.primitive_contracts()[family]["pre"]
                     if unknown_parameter in requirement["args"]]
    if not equalities and not nonzero:
        charge(counter, "backward_empty_specification")
        return None
    return {"family": family, "unknown": unknown_parameter, "binding": dict(binding),
            "equalities": equalities, "nonzero": nonzero, "applicability": applicability,
            "degree": max((sp.Poly(e, *UNKNOWN).total_degree() for e in equalities), default=0),
            "terms": sum(len(sp.Poly(e, *UNKNOWN).terms()) for e in equalities)}


def satisfied(specification, point, *, counter=None):
    """Whether a concrete rational point meets the specification, decided exactly."""
    values = {UNKNOWN[0]: sp.Rational(point[0]), UNKNOWN[1]: sp.Rational(point[1])}
    for expression in specification["equalities"]:
        charge(counter, "backward_specification_checks")
        if sp.expand(expression.subs(values, simultaneous=True)) != 0:
            return False
    for expression in specification["nonzero"]:
        charge(counter, "backward_specification_checks")
        if sp.expand(expression.subs(values, simultaneous=True)) == 0:
            return False
    return True


def readable(specification):
    """The specification as text, for the record: equalities, non-zero conditions, applicability."""
    return {"family": specification["family"], "unknown_argument": specification["unknown"],
            "bound_arguments": specification["binding"],
            "equalities": [str(sp.factor(e)) for e in specification["equalities"]],
            "nonzero": [str(sp.factor(e)) for e in specification["nonzero"]],
            "applicability": [f"{atom}{args}" for atom, args in specification["applicability"]],
            "degree": specification["degree"], "terms": specification["terms"]}
