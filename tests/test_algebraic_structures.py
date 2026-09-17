"""Certified algebraic structures and the connections between them."""
from fractions import Fraction
from itertools import combinations
import random

import pytest
import sympy as sp

from math_os_prototype import algebraic_cohort as ac
from math_os_prototype import algebraic_reduction_search as ars
from math_os_prototype import algebraic_structures as alg


def torus_facets():
    index = lambda i, j: 3*(i % 3)+(j % 3)
    facets = []
    for i in range(3):
        for j in range(3):
            a, b, c, d = index(i, j), index(i+1, j), index(i, j+1), index(i+1, j+1)
            facets += [(a, b, d), (a, c, d)]
    return facets


SPACES = {"circle": ([(0, 1), (1, 2), (0, 2)], [1, 1]),
          "disk": ([(0, 1, 2)], [1, 0, 0]),
          "sphere": ([(0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3)], [1, 0, 1]),
          "torus": (torus_facets(), [1, 2, 1])}


@pytest.mark.parametrize("name", sorted(SPACES))
def test_homology_is_kernel_modulo_image(name):
    facets, expected = SPACES[name]
    K = alg.simplicial_chain_complex(alg.closure(facets))
    assert K.certify_differential()
    assert alg.betti_numbers(K) == expected
    for q in range(len(K.dims)):
        result = alg.homology(K, q)
        assert result["betti"] == expected[q]
        assert all(not K.d(q).apply(z) for z in result["representatives"])


def test_kernel_certificate_and_presentation_map_descent():
    A = alg.SparseMatrix.from_rows([[1, 2, 3], [2, 4, 6], [1, 0, 1]])
    K = alg.kernel(A)
    assert alg.certify_kernel(A, K) and K.ncols == 1
    source = alg.SparseMatrix.from_rows([[1], [1]])            # coker: QQ^2 / <(1,1)>
    target = alg.SparseMatrix.from_rows([[1], [0], [1]])       # coker: QQ^3 / <(1,0,1)>
    descends = alg.SparseMatrix.from_rows([[1, 0], [0, 0], [0, 1]])
    S = alg.solve_presentation_map(descends, source, target)
    assert S is not None and alg.certify_presentation_map(descends, source, target, S)
    breaks = alg.SparseMatrix.from_rows([[1, 0], [0, 1], [0, 0]])
    assert alg.solve_presentation_map(breaks, source, target) is None


def test_reduction_moves_compose_to_a_certified_equivalence_and_preserve_homology():
    K = alg.simplicial_chain_complex(alg.closure(torus_facets()))
    rng = random.Random(11)
    current, composite = K, None
    for _ in range(3):
        q = rng.randrange(0, len(current.dims)-1)
        sigma = next(j for j in range(current.dims[q+1]) if current.d(q+1).columns[j])
        tau = sorted(current.d(q+1).columns[sigma])[0]
        D, F, G, h = alg.reduction_move(current, q, sigma, tau)
        assert alg.certify_homotopy_equivalence(current, D, F, G, h, {})
        step = (F, G, h, {})
        composite = step if composite is None else alg.compose_equivalences(composite, step)
        current = D
    F, G, h_C, h_E = composite
    assert alg.certify_homotopy_equivalence(K, current, F, G, h_C, h_E)
    assert alg.betti_numbers(current) == [1, 2, 1]


def test_homology_is_functorial():
    K = alg.simplicial_chain_complex(alg.closure(torus_facets()))
    D1, F1, G1, h1 = alg.reduction_move(K, 1, 0, sorted(K.d(2).columns[0])[0])
    D2, F2, G2, h2 = alg.reduction_move(D1, 0, 0, sorted(D1.d(1).columns[0])[0])
    for q in range(3):
        direct = alg.induced_map_on_homology(F2.compose(F1), q)
        stepwise = alg.induced_map_on_homology(F2, q).compose(alg.induced_map_on_homology(F1, q))
        assert direct.equals(stepwise)
        round_trip = alg.induced_map_on_homology(G1.compose(G2), q).compose(direct)
        assert round_trip.equals(alg.SparseMatrix.identity(round_trip.nrows))


def test_search_strategies_agree_with_an_independent_reference_and_lift_valid_representatives():
    cohort = ac.generate(20260917102, 4)
    for task in cohort["tasks"]:
        simplices = ac.rips_simplices([tuple(p) for p in task["points"]], task["r2"])
        K = alg.simplicial_chain_complex(simplices)
        truth = ac.reference_betti(simplices)
        for strategy in ("direct", "collapse", "markowitz-inf", "explore"):
            record = ars.solve_homology(K, strategy, top=1)
            assert record["betti"] == truth
            for q, reps in record["representatives"].items():
                vectors = [{i: v for (d, i), v in r.items()} for r in reps]
                assert all(not K.d(q).apply(v) for v in vectors)
                boundaries = alg.image(K.d(q+1))
                assert alg.rank(alg.SparseMatrix(K.dims[q], boundaries.columns+vectors)) == boundaries.ncols+len(vectors)


def test_dual_number_jacobian_equals_symbolic_jacobian():
    x, y, z = sp.symbols("x y z")
    rng = random.Random(3)
    for _ in range(5):
        exprs = [sum(rng.randint(-3, 3)*x**a*y**b*z**c for a in range(3) for b in range(3) for c in range(2)
                     if rng.random() < 0.3)+rng.randint(-5, 5) for _ in range(2)]
        point = [Fraction(rng.randint(-4, 4)) for _ in range(3)]
        polys = [sp.Poly(e, x, y, z) for e in exprs]
        def evaluate(poly, p):
            total = 0
            for (a, b, c), coefficient in poly.terms():
                total = total+int(coefficient)*p[0]**a*p[1]**b*p[2]**c
            return total
        J = alg.jacobian_by_dual_numbers([lambda p, poly=poly: evaluate(poly, p) for poly in polys], point)
        symbolic = sp.Matrix(exprs).jacobian([x, y, z]).subs(dict(zip((x, y, z), point)))
        assert J.to_rows() == [[Fraction(int(sp.Rational(v).p), int(sp.Rational(v).q)) for v in row]
                               for row in symbolic.tolist()]


def test_tangent_spaces_at_relational_goal_solutions_are_consistent():
    """Consistency check by rank-nullity: the evaluator's solution lies on every goal locus (the tangent-space
    computation verifies it), a nonzero gradient gives a 1-dimensional Zariski tangent space, and a rank-2
    Jacobian of the pair gives 0. It does not assert how often goal pairs are transversal."""
    from math_os_prototype import geometry_relational_cohort as gcohort
    from math_os_prototype import geometry_relational_dsl as rdsl
    ux, uy = sp.symbols("ux uy")
    cohort = gcohort.generate(20260917001, 6)
    checked = 0
    for task in cohort["tasks"]:
        coordinates = {n: (sp.Integer(a), sp.Integer(b)) for n, (a, b) in task["points"].items()}
        polys = []
        for goal in task["goals"]:
            elaborator = rdsl.gc._JGEXElaborator()
            elaborator.coordinates.update(coordinates)
            elaborator.coordinates["u"] = (ux, uy)
            polys.append(sp.Poly(sp.expand(rdsl.dsl.lower(elaborator, goal["predicate"], tuple(goal["points"]))), ux, uy))
        inputs = {tuple(v) for v in coordinates.values()}
        solution = next(s for s in gcohort.rational_solutions(task["goals"], task["points"]) if s not in inputs)
        point = [Fraction(int(sp.Rational(v).p), int(sp.Rational(v).q)) for v in solution]
        def evaluate(poly, p):
            total = 0
            for (a, b), coefficient in poly.terms():
                total = total+Fraction(int(sp.Rational(coefficient).p), int(sp.Rational(coefficient).q))*p[0]**a*p[1]**b
            return total
        functions = [lambda p, poly=poly: evaluate(poly, p) for poly in polys]
        singles = [alg.tangent_space([f], point) for f in functions]
        both = alg.tangent_space(functions, point)
        assert both["certified"] and all(s["certified"] for s in singles)
        if all(s["jacobian"].nonzeros() for s in singles) and alg.rank(both["jacobian"]) == 2:
            assert all(s["dimension"] == 1 for s in singles) and both["dimension"] == 0
            checked += 1
    assert checked >= 1


def test_persistence_barcode_equals_rank_invariant_and_graded_module():
    rng = random.Random(8)
    points = [(rng.randint(-10, 10), rng.randint(-10, 10)) for _ in range(8)]
    values = {}
    for i in range(len(points)):
        values[(i,)] = 0
    for i, j in combinations(range(len(points)), 2):
        values[(i, j)] = (points[i][0]-points[j][0])**2+(points[i][1]-points[j][1])**2
    for i, j, k in combinations(range(len(points)), 3):
        values[(i, j, k)] = max(values[(i, j)], values[(i, k)], values[(j, k)])
    level = {v: n for n, v in enumerate(sorted(set(values.values())))}
    filtration = [(s, level[v]) for s, v in values.items()]
    bars = alg.persistence_barcode(filtration)
    horizon = max(b for _, b in filtration)
    for q in (0, 1):
        for i in range(0, horizon+1, 4):
            for j in range(i, horizon+1, 4):
                assert alg.rank_invariant(filtration, q, i, j) == alg.barcode_rank(bars, q, i, j)
        for step in range(0, horizon+1, 4):
            graded = sum(1 for d, b, e in bars if d == q and b <= step and (e is None or step < e))
            assert graded == alg.rank_invariant(filtration, q, step, step)
        presentation = alg.persistence_module_presentation(bars, q)
        assert len(presentation) == sum(1 for d, _, _ in bars if d == q)


def test_every_ordering_and_exploration_reach_the_same_certified_minimal_model():
    from math_os_prototype import algebraic_minimal_models as amm
    cohort = ac.generate_model_tasks(20260917401, 2)
    for task in cohort["tasks"]:
        simplices = ac.rips_simplices([tuple(p) for p in task["points"]], task["r2"])
        K = alg.simplicial_chain_complex(simplices)
        truth = ac.reference_betti(simplices)
        sizes = set()
        for procedure in list(amm.ORDERINGS)+["explore"]:
            record = amm.minimal_model(K, procedure)
            assert record["solved"] and record["betti"] == truth
            sizes.add(record["model_size"])
            for q, reps in record["representatives"].items():
                vectors = [{i: v for (d, i), v in r.items()} for r in reps]
                assert all(not K.d(q).apply(v) for v in vectors)
        assert len(sizes) == 1
        budgeted = amm.minimal_model(K, "min-fill", budget=10)
        assert not budgeted["solved"] and budgeted["operations"] is None


def test_ordering_rule_is_learned_only_from_training_costs():
    from math_os_prototype import algebraic_minimal_models as amm
    training = [{"features": {"size": 10, "edges_per_vertex": 2.0, "triangles_per_edge": 1.0, "nonzeros_per_cell": 2.0},
                 "costs": {"min-fill": 100, "top-first": 150, "bottom-first": 60, "short-boundary": 90, "few-cofaces": 120}},
                {"features": {"size": 50, "edges_per_vertex": 6.0, "triangles_per_edge": 2.0, "nonzeros_per_cell": 3.0},
                 "costs": {"min-fill": 300, "top-first": 500, "bottom-first": 400, "short-boundary": 320, "few-cofaces": 450}}]
    rule = amm.learn_ordering_rule(training)
    assert rule(training[0]["features"]) == "bottom-first" and rule(training[1]["features"]) == "min-fill"
    assert rule.description["training_cost"] < rule.description["default_training_cost"]


def test_every_executed_move_has_the_minimum_live_key():
    from math_os_prototype import algebraic_minimal_models as amm
    task = ac.generate_model_tasks(20260917401, 1)["tasks"][0]
    K = alg.simplicial_chain_complex(ac.rips_simplices([tuple(p) for p in task["points"]], task["r2"]))
    for ordering, key in amm.ORDERINGS.items():
        reducer = amm.Reducer(K, ordering)
        c = reducer.complex
        while not reducer.finished():
            live = [key(c, sigma, tau) for tau in c.coboundary for sigma in c.coboundary[tau]]
            if not live:
                break
            smallest = min(live)
            before = len(c.moves)
            reducer.step(1)
            if len(c.moves) > before:
                assert reducer.last_key == smallest


def test_homotopy_certifier_refuses_mismatched_or_invalid_complexes():
    C = alg.ChainComplex([1, 1], {1: alg.SparseMatrix.from_rows([[1]])})
    D = alg.ChainComplex([1, 1], {1: alg.SparseMatrix.from_rows([[0]])})
    identity = {0: alg.SparseMatrix.identity(1), 1: alg.SparseMatrix.identity(1)}
    F = alg.ChainMap(D, D, identity)
    G = alg.ChainMap(D, D, identity)
    assert not alg.certify_homotopy_equivalence(C, D, F, G, {}, {})
    bad = alg.ChainComplex([1, 1, 1], {1: alg.SparseMatrix.from_rows([[1]]), 2: alg.SparseMatrix.from_rows([[1]])})
    zero = alg.ChainComplex([0, 0, 0], {1: alg.SparseMatrix.zero(0, 0), 2: alg.SparseMatrix.zero(0, 0)})
    F0 = alg.ChainMap(zero, bad, {})
    G0 = alg.ChainMap(bad, zero, {})
    assert not alg.certify_homotopy_equivalence(zero, bad, F0, G0, {}, {})


def test_duplicate_simplices_are_collapsed_and_filtrations_refuse_duplicates():
    K = alg.simplicial_chain_complex({(0,), (1,), (0, 1), (1, 0)})
    assert K.dims == [2, 1] and alg.betti_numbers(K) == [1, 0]
    with pytest.raises(ValueError):
        alg.filtered_boundary([((0,), 0), ((1,), 0), ((0, 1), 1), ((1, 0), 2)])
    with pytest.raises(ValueError):
        alg.Dual(Fraction(1), Fraction(1))**-1


def test_plucker_relation_invariance_and_incidence_by_kernel():
    rng = random.Random(4)
    for _ in range(30):
        u, v, w, z = ([rng.randint(-3, 3) for _ in range(4)] for _ in range(4))
        p = alg.plucker(u, v)
        assert alg.plucker_relation(p) == 0
        a, b, c, d = (rng.randint(-3, 3) for _ in range(4))
        moved = alg.plucker([a*x+b*y for x, y in zip(u, v)], [c*x+d*y for x, y in zip(u, v)])
        assert moved == tuple((a*d-b*c)*coordinate for coordinate in p)
        r = alg.plucker(w, z)
        if all(value == 0 for value in p) or all(value == 0 for value in r):
            continue
        meet = alg.plucker_pairing(p, r) == 0
        stacked = alg.SparseMatrix.from_rows([list(row) for row in zip(u, v, w, z)])
        assert meet == (alg.kernel(stacked).ncols > 0)
