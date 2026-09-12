import random
import unittest
import sympy as sp
from math_os_prototype.finite_generator_problem_dna import (
    FiniteGeneratorSystem, LinearGenerator, binary_shear_system,
    discover_action_observable_basis, discover_transfer_recurrence,
)


class ActionObservableTests(unittest.TestCase):
    def test_aggregate_closure_is_smaller_than_action_closure(self):
        system = binary_shear_system()
        a, b = system.variables
        observation = a**4 + b**4
        self.assertEqual(discover_transfer_recurrence(system, observation).order, 3)
        result = discover_action_observable_basis(system, [observation])
        self.assertEqual(len(result["basis"]), 5)
        self.assertTrue(result["certificate_passed"])
        rng = random.Random(7423)
        point = system.seed_vector
        evaluate = lambda p: sp.Matrix([f.subs(dict(zip((a, b), p))) for f in result["basis"]])
        reduced = evaluate(point)
        for _ in range(128):
            i = rng.randrange(2)
            point = system.generators[i].matrix * point
            reduced = result["action_matrices"][i] * reduced
            self.assertEqual(reduced, evaluate(point))

    def test_complex_rotation_uses_existing_linear_action(self):
        angle = 2 * sp.pi / 5
        rotation = LinearGenerator.from_rows("Rotate", [
            [sp.cos(angle), -sp.sin(angle)], [sp.sin(angle), sp.cos(angle)]
        ])
        system = FiniteGeneratorSystem("plane", ("x", "y"), (rotation,), (1, 0))
        x, y = system.variables
        result = discover_action_observable_basis(system, [x*x+y*y])
        self.assertEqual(len(result["basis"]), 1)
        self.assertEqual(result["action_matrices"][0], sp.eye(1))
        self.assertEqual((rotation.matrix**5-sp.eye(2)).applyfunc(sp.simplify), sp.zeros(2))
        self.assertTrue(result["certificate_passed"])

    def test_scope_failures_are_not_certificates(self):
        system = binary_shear_system()
        a, b = system.variables
        with self.assertRaises(ValueError):
            discover_action_observable_basis(system, [a**4+b**4], maximum_dimension=4)
        with self.assertRaises(ValueError):
            discover_action_observable_basis(system, [0])
        with self.assertRaises(ValueError):
            discover_action_observable_basis(system, [sp.Float(0.1)*a])


if __name__ == "__main__":
    unittest.main()
