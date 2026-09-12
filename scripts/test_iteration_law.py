"""Handwritten correctness fixtures for the connection; never discovery statistics.

The known example is kept as a regression only. The cases that matter here are
the boundaries: a family whose identity is not at zero, a family whose parameter
accumulates multiplicatively, and a law that is not affine in the accumulator.
Each has to be reported as the mismatch it is rather than worked around.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sympy as sp
from math_os_prototype.abstraction_correspondence import (
    CANDIDATE_REFUTED, NOT_APPLICABLE, NO_SOLUTION_IN_SPACE, OPEN_OBLIGATIONS,
    PROVED, RING_LAW, abstract_signature, compose_operations, composition_law,
    fill, induced_operation, operation_expressions, ring_expression, slot)
from math_os_prototype.iteration_law import (
    INDEX, accumulator_recurrence, identity_at, intertwined_power,
    iteration_law, parameter_closed_form, quantification, recovery_map,
    transfer)


def hyper(a, b=()):
    return {"op": "hyper", "a": list(a), "b": list(b)}


def add(left, right):
    return {"op": "add", "left": left, "right": right}


def mul(left, right):
    return {"op": "mul", "left": left, "right": right}


U, C, A0 = slot("u"), slot("c"), slot("a0")
SIGNATURE = abstract_signature([U, mul(U, U)], coordinate_names=["a0", "a1"],
                               parameter_names=["c"])
MORPHISM = {"u": add(U, C), "c": C}
WITNESS = {"u": hyper(["1/2"]), "c": hyper(["1/3"])}


def one_coordinate(body):
    """A one-parameter family on a single abstract coordinate."""
    return {"schema": "mortra.operation.v1", "body": [body],
            "coordinate_names": ["a0"], "parameter_names": ["c"],
            "domain": {"abstraction_map": [U]},
            "law": RING_LAW, "proved": True, "proofs": []}


SCALING = one_coordinate(mul(A0, C))                        # T_c(a) = c a
GROUP = one_coordinate(add(A0, add(C, mul(A0, C))))          # T_c(a) = a + c + a c


class DerivedOperationTests(unittest.TestCase):
    """The family under test is acquired, not written down."""

    def setUp(self):
        self.T = induced_operation(SIGNATURE, MORPHISM, WITNESS)

    def test_the_operation_is_acquired_with_its_intertwining_proof(self):
        self.assertEqual(self.T["status"], PROVED)
        self.assertEqual([str(e) for e in operation_expressions(self.T)],
                         ["sym_a0 + sym_c", "2*sym_a0*sym_c + sym_a1 + sym_c**2"])
        # each stored proof is alpha_i(S(u)) = T_i(alpha(u)) in independent symbols
        for proof in self.T["proofs"]:
            self.assertTrue(proof["proved"])
            self.assertEqual(proof["residual"], "0")
            self.assertEqual(proof["symbols"], ["sym_c", "sym_u"])


class QuantificationTests(unittest.TestCase):
    def setUp(self):
        self.T = induced_operation(SIGNATURE, MORPHISM, WITNESS)
        self.composed = compose_operations(self.T, self.T)
        self.law = composition_law(self.T, self.composed)

    def test_the_composition_law_is_quantified_over_independent_names(self):
        report = quantification(self.T, self.law)
        self.assertTrue(report["quantified"])
        self.assertEqual(report["symbols"],
                         ["sym_a0", "sym_a1", "sym_c", "sym_c_2"])
        self.assertEqual(report["residuals"], ["0", "0"])
        self.assertTrue(all(report["components_proved"]))

    def test_the_two_copies_are_not_aliased_to_one_parameter(self):
        self.assertEqual(self.composed["rename"], {"c": "c_2"})
        self.assertEqual(self.composed["parameter_names"], ["c", "c_2"])

    def test_a_vacuous_law_is_not_treated_as_quantified(self):
        identity = one_coordinate(A0)
        law = composition_law(identity, compose_operations(identity, identity))
        self.assertTrue(law["proved"])
        self.assertTrue(law["parameter_free_base"])
        self.assertFalse(quantification(identity, law)["quantified"])


class BaseCaseTests(unittest.TestCase):
    def test_the_zeroth_iterate_is_proved_not_assumed(self):
        T = induced_operation(SIGNATURE, MORPHISM, WITNESS)
        base = identity_at(T, 0)
        self.assertEqual(base["status"], PROVED)
        self.assertTrue(base["is_identity"])
        self.assertEqual([p["residual"] for p in base["proofs"]], ["0", "0"])

    def test_a_family_whose_identity_is_elsewhere_fails_the_base_case_at_zero(self):
        self.assertEqual(identity_at(SCALING, 0)["status"], OPEN_OBLIGATIONS)
        self.assertEqual(identity_at(SCALING, 1)["status"], PROVED)


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.T = induced_operation(SIGNATURE, MORPHISM, WITNESS)
        self.composed = compose_operations(self.T, self.T)
        self.law = composition_law(self.T, self.composed)

    def test_the_accumulation_is_read_off_the_law_not_chosen(self):
        bridge = accumulator_recurrence(self.T, self.composed, self.law)
        self.assertEqual(bridge["status"], PROVED)
        self.assertTrue(bridge["affine"])
        self.assertEqual(bridge["degree"], 1)
        self.assertEqual(bridge["accumulator"], "s")
        self.assertEqual(bridge["fresh"], "c_2")
        self.assertEqual(sp.sympify(bridge["multiplier"]), 1)
        self.assertEqual(sp.sympify(bridge["increment"]), sp.Symbol("sym_c"))

    def test_the_inner_copy_is_the_accumulator(self):
        # compose_operations renames the outer copy, and in T^(k+1) = T . T^k the
        # inner factor is T^k, so the base's own parameter name is the accumulator.
        bridge = accumulator_recurrence(self.T, self.composed, self.law)
        self.assertEqual(bridge["fresh"], self.composed["rename"]["c"])

    def test_a_law_of_degree_two_in_the_accumulator_is_refused(self):
        quadratic = dict(self.law,
                         parameter_program=add(mul(slot("c"), slot("c")),
                                               slot("c_2")))
        bridge = accumulator_recurrence(self.T, self.composed, quadratic)
        self.assertEqual(bridge["status"], NOT_APPLICABLE)
        self.assertFalse(bridge["affine"])
        self.assertEqual(bridge["degree"], 2)
        self.assertIn("degree 2", bridge["reason"])


class ParameterInductionTests(unittest.TestCase):
    def test_an_additive_accumulation_is_certified_for_every_n(self):
        T = induced_operation(SIGNATURE, MORPHISM, WITNESS)
        composed = compose_operations(T, T)
        bridge = accumulator_recurrence(T, composed, composition_law(T, composed))
        closed = parameter_closed_form(bridge)
        self.assertEqual(closed["status"], PROVED)
        self.assertEqual(closed["scope"], "all_finite_words")
        self.assertTrue(closed["base_case_exact"])
        self.assertTrue(closed["all_steps_exact"])
        self.assertFalse(closed["fit_used_as_proof"])
        self.assertEqual(sp.sympify(closed["closed_form"]),
                         sp.Symbol("sym_c") * sp.Symbol("sym_n"))

    def test_a_multiplicative_accumulation_is_refused_not_guessed(self):
        composed = compose_operations(SCALING, SCALING)
        law = composition_law(SCALING, composed)
        self.assertTrue(law["proved"])
        bridge = accumulator_recurrence(SCALING, composed, law)
        self.assertTrue(bridge["affine"])          # affine in the accumulator...
        closed = parameter_closed_form(bridge, initial=1)
        self.assertEqual(closed["status"], NO_SOLUTION_IN_SPACE)  # ...but not in n
        self.assertEqual(closed["counterexample"]["kind"],
                         "non_affine_length_dependence")


class IterationLawTests(unittest.TestCase):
    def setUp(self):
        self.T = induced_operation(SIGNATURE, MORPHISM, WITNESS)
        self.theorem = iteration_law(self.T)

    def test_every_n_at_once(self):
        self.assertEqual(self.theorem["status"], PROVED)
        self.assertEqual(sp.sympify(self.theorem["parameter"]),
                         sp.Symbol("sym_c") * sp.Symbol("sym_n"))
        self.assertEqual(self.theorem["iterate"]["parameter_names"], [INDEX])

    def test_nothing_is_enumerated_per_n(self):
        self.assertEqual(self.theorem["searched_per_n_after_connection"], 0)
        # the only enumeration is the one 2-fold law, which existed already
        self.assertEqual(self.theorem["stages"]["composition_law"]["searched"], 5)

    def test_the_square_in_n_arrives_by_substitution_not_by_fitting(self):
        n, c, a0, a1 = sp.symbols("sym_n sym_c sym_a0 sym_a1")
        body = [ring_expression(part, {}) for part in self.theorem["iterate"]["body"]]
        self.assertEqual(sp.expand(body[0] - (a0 + n * c)), 0)
        self.assertEqual(sp.expand(body[1] - (a1 + 2 * a0 * c * n + c ** 2 * n ** 2)), 0)
        # the parameter that was proved is degree one in n; the square is what
        # substituting it into the already-proved body produces
        self.assertEqual(sp.Poly(sp.sympify(self.theorem["parameter"]), n).degree(), 1)
        self.assertEqual(sp.Poly(body[1], n).degree(), 2)

    def test_the_stages_each_carry_their_own_verdict(self):
        stages = self.theorem["stages"]
        self.assertTrue(stages["quantification"]["quantified"])
        self.assertTrue(stages["base_case"]["proved"])
        self.assertTrue(stages["bridge"]["affine"])
        self.assertTrue(stages["induction_step"]["proved"])
        self.assertEqual(stages["induction_step"]["residuals"], ["0", "0"])
        self.assertEqual(stages["parameter_induction"]["scope"], "all_finite_words")

    def test_regression_only_the_closed_form_matches_actual_composites(self):
        n = sp.Symbol("sym_n")
        closed = [ring_expression(part, {}) for part in self.theorem["iterate"]["body"]]
        chain = self.T
        for power in range(2, 6):
            chain = compose_operations(self.T, chain)
            binding = {name: slot(name) for name in self.T["coordinate_names"]}
            binding.update({p: slot("c") for p in chain["parameter_names"]})
            actual = [sp.expand(ring_expression(fill(part, binding), {}))
                      for part in chain["body"]]
            for got, want in zip(actual, closed):
                self.assertEqual(sp.expand(got - want.subs(n, power)), 0,
                                 f"disagreed at n={power}")

    def test_a_family_whose_identity_is_not_at_zero_stops_at_the_base_case(self):
        stopped = iteration_law(SCALING)
        self.assertEqual(stopped["status"], OPEN_OBLIGATIONS)
        self.assertFalse(stopped["stages"]["base_case"]["proved"])
        self.assertNotIn("parameter_induction", stopped["stages"])

    def test_a_multiplicative_group_law_stops_at_the_induction_not_before(self):
        # T_c(a) = a + c + a c has T_0 = id and a law affine in the accumulator,
        # so it passes every earlier stage; s_n = (1+c)^n - 1 is where it stops.
        theorem = iteration_law(GROUP, depth=2)
        self.assertTrue(theorem["stages"]["composition_law"]["proved"])
        self.assertTrue(theorem["stages"]["base_case"]["proved"])
        self.assertTrue(theorem["stages"]["bridge"]["affine"])
        self.assertTrue(theorem["stages"]["induction_step"]["proved"])
        self.assertEqual(theorem["status"], NO_SOLUTION_IN_SPACE)
        self.assertEqual(theorem["stages"]["parameter_induction"]["status"],
                         NO_SOLUTION_IN_SPACE)

    def test_a_parameter_free_family_is_refused(self):
        self.assertEqual(iteration_law(one_coordinate(A0))["status"], NOT_APPLICABLE)


class IntertwiningLemmaTests(unittest.TestCase):
    def setUp(self):
        self.T = induced_operation(SIGNATURE, MORPHISM, WITNESS)

    def test_the_premise_carries_to_every_power_by_a_rule_not_a_search(self):
        lemma = intertwined_power(SIGNATURE, MORPHISM, self.T)
        self.assertEqual(lemma["status"], PROVED)
        self.assertTrue(all(p["proved"] for p in lemma["premise"]))
        self.assertEqual([p["residual"] for p in lemma["premise"]], ["0", "0"])
        self.assertIn("no search", lemma["grammar"]["space"])
        self.assertTrue(all(entry["proved"] for entry in lemma["powers"]))

    def test_a_morphism_that_does_not_intertwine_is_refused(self):
        wrong = one_coordinate(A0)
        wrong = dict(wrong, coordinate_names=["a0", "a1"],
                     body=[A0, slot("a1")],
                     domain={"abstraction_map": SIGNATURE["alpha"]})
        lemma = intertwined_power(SIGNATURE, MORPHISM, wrong)
        self.assertEqual(lemma["status"], CANDIDATE_REFUTED)
        self.assertEqual(lemma["powers"], [])


class RecoveryTests(unittest.TestCase):
    def test_a_recovery_map_is_searched_in_the_existing_grammar_and_proved(self):
        found = recovery_map(SIGNATURE)
        self.assertEqual(found["status"], PROVED)
        self.assertEqual(found["expression"], "sym_a0")
        self.assertEqual(found["state"], "u")
        self.assertTrue(found["proof"]["proved"])

    def test_an_abstraction_that_loses_the_state_reports_no_recovery(self):
        squared = abstract_signature([mul(U, U)], coordinate_names=["a0"],
                                     parameter_names=["c"])
        found = recovery_map(squared, depth=2)
        self.assertEqual(found["status"], NO_SOLUTION_IN_SPACE)
        self.assertIsNone(found["map"])

    def test_the_theorem_transfers_only_when_recovery_is_proved(self):
        T = induced_operation(SIGNATURE, MORPHISM, WITNESS)
        theorem = iteration_law(T)
        full = transfer(theorem, recovery_map(SIGNATURE))
        self.assertTrue(full["transfers"])
        self.assertEqual(full["scope"], "the original state")

        squared = abstract_signature([mul(U, U)], coordinate_names=["a0"],
                                     parameter_names=["c"])
        partial = transfer(theorem, recovery_map(squared, depth=2))
        self.assertFalse(partial["transfers"])
        self.assertEqual(partial["scope"], "the abstract coordinates only")


if __name__ == "__main__":
    unittest.main()
