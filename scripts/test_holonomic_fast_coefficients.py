import random

import pytest

from math_os_prototype.holonomic_fast_coefficients import coefficients as fast
from math_os_prototype.holonomic_route_discovery import coefficients as reference

H = {"op": "hyper", "a": ["1/2", "1/3"], "b": ["3/2"]}


@pytest.mark.parametrize("program", [
    H,
    {"op": "poly", "coefficients": [0, "1/2", -4]},
    {"op": "diff", "child": H},
    {"op": "scale", "factor": "-5/3", "child": H},
    {"op": "add", "left": H, "right": {"op": "diff", "child": H}},
    {"op": "mul", "left": H, "right": H},
    {"op": "pullback", "child": H, "numerator": [0, 1, -1], "denominator": [2, 1, 1]},
    {"op": "diff", "child": {"op": "pullback", "child": H, "numerator": [0, -1], "denominator": [1, -1]}},
])
def test_all_operations_agree_exactly(program):
    for size in (0, 1, 8, 24):
        assert fast(program, size) == reference(program, size)


def test_random_compositions_match_reference_and_cache_is_not_mutated():
    rng = random.Random(728)
    pool = [H, {"op": "poly", "coefficients": [1, -1]}]
    for _ in range(20):
        child = rng.choice(pool)
        op = rng.choice(["diff", "scale", "mul", "add", "pullback"])
        if op in ("mul", "add"):
            p = {"op": op, "left": child, "right": rng.choice(pool[:2])}
        elif op == "diff":
            p = {"op": op, "child": child}
        elif op == "scale":
            p = {"op": op, "child": child, "factor": "-2/3"}
        else:
            p = {"op": op, "child": child, "numerator": [0, 1], "denominator": [1, -1]}
        pool.append(p)
        assert fast(p, 20) == reference(p, 20)
        assert fast(H, 20) == reference(H, 20)


def test_inner_derivative_budget_and_bad_float_rejected():
    with pytest.raises(ValueError):
        fast({"op": "diff", "child": H}, 512)
    with pytest.raises(ValueError):
        fast({"op": "poly", "coefficients": [0.5]}, 4)


@pytest.mark.parametrize("degree", [1, 2])
def test_full_relation_search_is_identical_across_backends(degree):
    from math_os_prototype.holonomic_joint_relations import make_features, guess_relations
    features = make_features([H, {"op": "hyper", "a": [1, 1], "b": [2]}],
                             degree_x=1, derivatives=1, product_degree=degree)
    assert guess_relations(features, coefficient_backend="flint") == guess_relations(features)
