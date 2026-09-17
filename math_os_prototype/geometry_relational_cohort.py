"""Task-only generator for point-construction cohorts (docs/research/GEOMETRY-RELATIONAL-DSL-20260917.md).

The filter reads only the generated task: exact solving of the goal's two
polynomial equations in (ux, uy) and the existing certify_atom. No solver,
construction family, witness or search result is consulted.
"""
from __future__ import annotations

from collections import Counter
from itertools import combinations
import random

import sympy as sp

from math_os_prototype import geometry_relational_dsl as rdsl

GOAL_PREDICATES = ("coll", "perp", "para", "cong", "cyclic", "midp", "eqangle")
NAMES = ("a", "b", "c", "d")


def _points(rng):
    for _ in range(10000):
        points = {n: [rng.randint(-9, 9), rng.randint(-9, 9)] for n in NAMES}
        xy = list(points.values())
        if len({tuple(p) for p in xy}) != len(xy):
            continue
        if any((b[0]-a[0])*(c[1]-a[1]) == (b[1]-a[1])*(c[0]-a[0]) for a, b, c in combinations(xy, 3)):
            continue
        return points
    raise ValueError("point generator exhausted its rejection bound")


def _atom(rng):
    predicate = rng.choice(GOAL_PREDICATES)
    arity = rdsl.PREDICATE_ARITIES[predicate]
    while True:
        args = [rng.choice(("u",)+NAMES) for _ in range(arity)]
        if "u" in args:
            return {"predicate": predicate, "points": args}


def rational_solutions(goals, points):
    """All rational (ux, uy) solving both lowered goal equations, or None if the complex solution set is infinite."""
    ux, uy = sp.Symbol("ux"), sp.Symbol("uy")
    coordinates = {n: tuple(sp.Integer(v) for v in xy) for n, xy in points.items()}
    polynomials = []
    for g in goals:
        elaborator = rdsl.gc._JGEXElaborator()
        elaborator.coordinates.update(coordinates)
        elaborator.coordinates["u"] = (ux, uy)
        polynomials.append(sp.expand(rdsl.dsl.lower(elaborator, g["predicate"], tuple(g["points"]))))
    if any(p == 0 for p in polynomials):
        return None
    first, second = (sp.Poly(p, ux, uy) for p in polynomials)
    if sp.gcd(first, second).total_degree() > 0:
        return None
    resultant = sp.Poly(sp.resultant(first.as_expr(), second.as_expr(), uy), ux)
    if resultant.is_zero:
        return None
    solutions = set()
    for x in _rational_roots(resultant):
        common = sp.gcd(sp.Poly(first.as_expr().subs(ux, x), uy), sp.Poly(second.as_expr().subs(ux, x), uy))
        if common.is_zero:
            return None
        for y in _rational_roots(common):
            solutions.add((x, y))
    return sorted(solutions)


def _rational_roots(polynomial):
    """Rational roots of a univariate polynomial from its linear factors over QQ."""
    if polynomial.is_zero or polynomial.degree() <= 0:
        return []
    roots = set()
    for factor, _ in sp.factor_list(polynomial.as_expr(), *polynomial.gens, domain=sp.QQ)[1]:
        linear = sp.Poly(factor, *polynomial.gens)
        if linear.degree() == 1:
            roots.add(-linear.nth(0)/linear.nth(1))
    return sorted(roots)


def generate(seed, count, *, rejection_bound=200000):
    rng = random.Random(seed)
    tasks, rejections, seen = [], Counter(), set()
    for _ in range(rejection_bound):
        if len(tasks) == count:
            break
        points = _points(rng)
        goals = [_atom(rng), _atom(rng)]
        key = tuple(sorted(rdsl.canonical_atom(g["predicate"], tuple(g["points"])) for g in goals))
        if key[0] == key[1]:
            rejections["duplicate_atoms"] += 1
            continue
        solutions = rational_solutions(goals, points)
        if solutions is None:
            rejections["not_finite"] += 1
            continue
        coordinates = {n: tuple(sp.Integer(v) for v in xy) for n, xy in points.items()}
        def satisfies(xy):
            local = dict(coordinates, u=xy)
            return all(rdsl.atom_holds(g["predicate"], tuple(g["points"]), local) for g in goals)
        if any(all(rdsl.atom_holds(g["predicate"], tuple(xy_name if a == "u" else a for a in g["points"]), coordinates)
                   for g in goals) for xy_name in NAMES):
            rejections["input_point_satisfies_goal"] += 1
            continue
        valid = [xy for xy in solutions if xy not in set(coordinates.values()) and satisfies(xy)]
        if not valid:
            rejections["no_rational_nondegenerate_solution" if solutions else "no_rational_solution"] += 1
            continue
        signature = (tuple((n, tuple(xy)) for n, xy in sorted(points.items())), key)
        if signature in seen:
            rejections["duplicate_task"] += 1
            continue
        seen.add(signature)
        tasks.append({"points": points, "goals": goals,
                      "evaluator_solution_count": len(valid)})
    if len(tasks) != count:
        raise ValueError("cohort generator exhausted its rejection bound")
    counts = Counter(g["predicate"] for t in tasks for g in t["goals"])
    return {"seed": seed, "tasks": tasks, "rejections": dict(rejections), "predicate_counts": dict(counts),
            "rule": "uniform predicate, uniform argument tuple over {u,a,b,c,d} containing u; finite complex solution set; "
                    "a rational non-input solution satisfying both atoms with prerequisites; no input point satisfies the goal"}
