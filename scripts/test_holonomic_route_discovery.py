"""Standard fixtures, excluded from autonomous discovery measurements."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sympy as sp
from math_os_prototype import holonomic_route_discovery as route
from math_os_prototype.holonomic_route_discovery import (
    X, N, annihilator, certify_equal, coefficients, operator_coefficients,
    rational, replay_certificate, right_remainder, uniqueness_bound, validate,
)


def hyper(a, b=()):
    return {"op": "hyper", "a": list(a), "b": list(b)}


class HolonomicRouteTests(unittest.TestCase):
    def test_coefficients_validate_tree_once_but_recheck_mutable_inputs(self):
        p = hyper(["1/2"])
        for _ in range(10):
            p = {"op": "scale", "factor": 2, "child": p}
        original = deepcopy(p)
        route._coefficients.cache_clear()
        with patch.object(route, "validate", wraps=route.validate) as checked:
            self.assertEqual(coefficients(p, 3), (1024, 512, 384))
        self.assertEqual(checked.call_count, 11)
        self.assertEqual(p, original)
        p["child"]["factor"] = 0
        with self.assertRaises(ValueError):
            coefficients(p, 3)

    def test_derivative_does_not_bypass_internal_coefficient_budget(self):
        route._coefficients.cache_clear()
        with self.assertRaisesRegex(ValueError, "coefficient budget"):
            coefficients({"op": "diff", "child": hyper([1])}, 512)

    def test_nested_invalid_ode_is_checked_even_for_zero_requested_terms(self):
        p = {"op": "diff", "child": {"op": "ode", "operator": [[0]], "initial": [1]}}
        with self.assertRaises(ValueError):
            coefficients(p, 0)

    def test_hyper_coefficients(self):
        self.assertEqual(coefficients(hyper(["1/2", "1/2"], [1]), 4),
                         (1, sp.Rational(1, 4), sp.Rational(9, 64), sp.Rational(25, 256)))

    def test_parameter_cancellation_is_not_a_stored_identity(self):
        cert = certify_equal(hyper(["1/2", 1], [1]), hyper(["1/2"]))
        self.assertEqual(cert["status"], "exact_formal_series_equality")
        self.assertTrue(replay_certificate(cert))
        self.assertFalse(cert["special_value_proved"])

    def test_derivative_identity(self):
        lhs = {"op": "scale", "factor": 4, "child": {"op": "diff", "child": hyper(["1/2", "1/2"], [1])}}
        rhs = hyper(["3/2", "3/2"], [2])
        self.assertTrue(replay_certificate(certify_equal(lhs, rhs)))

    def test_product(self):
        lhs = {"op": "mul", "left": hyper(["1/2"]), "right": hyper(["1/2"])}
        self.assertTrue(replay_certificate(certify_equal(lhs, hyper([1]))))

    def test_pullback(self):
        lhs = {"op": "pullback", "child": hyper([1]), "numerator": [0, 1], "denominator": [1, 1]}
        rhs = {"op": "poly", "coefficients": [1, 1]}
        self.assertTrue(replay_certificate(certify_equal(lhs, rhs)))

    def test_composition_does_not_mutate_cached_operator(self):
        p = hyper(["1/2", "1/2"], [1])
        before = operator_coefficients(annihilator(p))
        annihilator({"op": "pullback", "child": p, "numerator": [0, 1], "denominator": [1, 1]})
        self.assertEqual(before, operator_coefficients(annihilator(p)))

    def test_late_prefix_collision_is_refuted(self):
        a = {"op": "poly", "coefficients": [1]}
        b = {"op": "poly", "coefficients": [1]+[0]*23+[1]}
        self.assertEqual(coefficients(a, 16), coefficients(b, 16))
        cert = certify_equal(a, b)
        self.assertEqual(cert, {"status": "refuted", "first_mismatch": 24})

    def test_singular_origin_needs_more_than_ode_order(self):
        bound = uniqueness_bound((-24, X))
        self.assertEqual(bound["required_initial_coefficients"], 25)
        self.assertEqual(bound["nonnegative_integer_roots"], [24])

    def test_noncommutative_division(self):
        self.assertEqual(right_remainder((1, X), (0, 1)), (1, 0))
        self.assertEqual(right_remainder((0, 2, X), (0, X)), (0, 0, 0))

    def test_bad_domain_inputs(self):
        for p in [hyper([1, 1], [0]), hyper([1, 1], [-1]), hyper([1, 1, 1], [1]),
                  {"op": "pullback", "child": hyper([1]), "numerator": [1], "denominator": [1]},
                  {"op": "pullback", "child": hyper([1]), "numerator": [0, 1], "denominator": [0, 1]}]:
            with self.assertRaises(ValueError):
                validate(p)
        for value in [0.5, "pi", "1/0", True, "__import__('os')"]:
            with self.assertRaises(ValueError):
                rational(value)

    def test_tamper(self):
        cert = certify_equal(hyper(["1/2", 1], [1]), hyper(["1/2"]))
        for field, value in [("common_operator", ["0"]), ("initial_coefficients", ["2"]),
                             ("special_value_proved", True), ("sha256", "wrong")]:
            changed = deepcopy(cert)
            changed[field] = value
            self.assertFalse(replay_certificate(changed))

    def test_zero_and_terminating_series(self):
        a = hyper([-2])
        b = {"op": "poly", "coefficients": [1, -2, 1]}
        self.assertTrue(replay_certificate(certify_equal(a, b)))
        zero = {"op": "poly", "coefficients": [0]}
        self.assertTrue(replay_certificate(certify_equal(zero, zero)))


if __name__ == "__main__":
    unittest.main()
