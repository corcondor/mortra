"""Handwritten correctness fixtures; never included in discovery statistics."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from math_os_prototype.abstraction_correspondence import (
    OutsideRingFragment, abstract_inputs, abstract_signature, abstract_seeds,
    apply_operation, classify_on_image, compose_operations, composition_law,
    conserved_quantities, correspondence, descends, express, fill,
    induced_component, induced_images, induced_operation, induced_operations,
    is_identity_operation, next_round_seeds, preserves_abstraction, prove_identity,
    query_survives, record_image_condition, ring_expression, ring_program,
    same_domain, slot, solve_component, uses_parameters, well_defined,
    DERIVATION_LAW, NOT_APPLICABLE, NO_SOLUTION_IN_SPACE, PROVED,
    differential_expression, derive, monomial_basis)


def hyper(a, b=()):
    return {"op": "hyper", "a": list(a), "b": list(b)}


def add(left, right):
    return {"op": "add", "left": left, "right": right}


def mul(left, right):
    return {"op": "mul", "left": left, "right": right}


def negate(child):
    return {"op": "scale", "child": child, "factor": "-1"}


U, V, C = slot("u"), slot("v"), slot("c")
ALPHA = [add(U, V), mul(U, V)]
SIGNATURE = abstract_signature(ALPHA, coordinate_names=["s", "p"],
                               parameter_names=["c"])
MORPHISMS = {"stay": {"u": U, "v": V, "c": C},
             "translate": {"u": add(U, C), "v": add(V, C), "c": C},
             "swap": {"u": V, "v": U, "c": C},
             "left_only": {"u": add(U, C), "v": V, "c": C}}
QUERIES = [("difference_squared", mul(add(U, negate(V)), add(U, negate(V)))),
           ("difference", add(U, negate(V)))]
WITNESSES = [{"u": hyper(["1/2"]), "v": hyper([1]), "c": hyper(["1/3"])},
             {"u": hyper([2]), "v": hyper(["1/5"]), "c": hyper([3])},
             {"u": hyper(["2/3"]), "v": hyper([1, 1], [2]), "c": hyper(["1/7"])}]

# A second abstraction, kept because its coordinates are deliberately dependent:
# p2 is s2 squared, so the image satisfies a relation and a quantity can be
# preserved there without varying.
REDUNDANT = [U, mul(U, U)]
REDUNDANT_SIGNATURE = abstract_signature(REDUNDANT, coordinate_names=["a0", "a1"],
                                         parameter_names=["c"])


class SlotTests(unittest.TestCase):
    def test_a_hole_is_replaced_by_what_is_bound_to_it(self):
        self.assertEqual(fill(U, WITNESSES[0]), WITNESSES[0]["u"])
        self.assertEqual(fill(add(U, V), WITNESSES[0]),
                         add(WITNESSES[0]["u"], WITNESSES[0]["v"]))

    def test_an_unbound_hole_is_refused(self):
        with self.assertRaises(ValueError):
            fill(add(U, slot("missing")), WITNESSES[0])


class SignatureTests(unittest.TestCase):
    def test_the_abstract_side_names_coordinates_and_parameters_only(self):
        self.assertEqual(SIGNATURE["names"], ["s", "p", "c"])
        self.assertNotIn("u", SIGNATURE["names"])
        self.assertNotIn("v", SIGNATURE["names"])

    def test_inputs_come_back_in_the_order_the_names_are_declared(self):
        programs = abstract_inputs(SIGNATURE, WITNESSES[0])
        self.assertEqual(len(programs), 3)
        self.assertEqual(programs[0], add(WITNESSES[0]["u"], WITNESSES[0]["v"]))
        self.assertEqual(programs[1], mul(WITNESSES[0]["u"], WITNESSES[0]["v"]))
        self.assertEqual(programs[2], WITNESSES[0]["c"])

    def test_one_name_per_component_is_required(self):
        with self.assertRaises(ValueError):
            abstract_signature(ALPHA, coordinate_names=["s"])
        with self.assertRaises(ValueError):
            abstract_signature(ALPHA, coordinate_names=["s", "c"],
                               parameter_names=["c"])


class RingProgramTests(unittest.TestCase):
    def test_an_expression_becomes_a_program_and_reads_back_the_same(self):
        import sympy as sp
        for text in ("sym_s**2 - 4*sym_p", "sym_a0**2 - sym_a1", "3*sym_c/2",
                     "sym_s*sym_p + 1"):
            program = ring_program(text)
            self.assertEqual(sp.expand(ring_expression(program, {}) - sp.sympify(text)),
                             0, text)

    def test_something_outside_the_fragment_is_refused(self):
        with self.assertRaises(OutsideRingFragment):
            ring_program("sym_s**(-1)")


class ConditionTwoTests(unittest.TestCase):
    def test_a_rearrangement_that_leaves_alpha_alone_is_found_not_named(self):
        preserving = [name for name, morphism in MORPHISMS.items()
                      if all(preserves_abstraction(SIGNATURE, morphism, b)
                             for b in WITNESSES)]
        self.assertEqual(sorted(preserving), ["stay", "swap"])

    def test_an_asymmetric_operation_fails_condition_two(self):
        verdict = descends(SIGNATURE, MORPHISMS["left_only"],
                           {"swap": MORPHISMS["swap"]}, WITNESSES[0])
        self.assertFalse(verdict["descends"])
        self.assertEqual([f["component"] for f in verdict["failures"]], [1])

    def test_a_symmetric_operation_passes_condition_two(self):
        for name in ("translate", "swap", "stay"):
            verdict = descends(SIGNATURE, MORPHISMS[name],
                               {"swap": MORPHISMS["swap"]}, WITNESSES[0])
            self.assertTrue(verdict["descends"], name)


class InducedTests(unittest.TestCase):
    def test_an_induced_component_is_found_and_proved(self):
        found = induced_component(SIGNATURE, MORPHISMS["translate"], 0, WITNESSES[0],
                                  degree_x=0)
        self.assertEqual(found["status"], PROVED)
        self.assertEqual(found["route"], "coefficient comparison")
        self.assertTrue(found["proof"]["proved"])
        self.assertEqual(found["grammar"]["names"], ["s", "p", "c"])

    def test_the_series_route_still_runs_when_the_span_has_no_solution(self):
        # Degree one cannot express p + c*s + c*c, so the complete solve reports
        # only about that span and the older route is still reached and proves it.
        found = induced_component(SIGNATURE, MORPHISMS["translate"], 1, WITNESSES[0],
                                  degree_x=0, span_degree=1)
        self.assertEqual(found["status"], PROVED)
        self.assertEqual(found["route"], "relation search")
        self.assertEqual(found["attempts"][0]["status"], NO_SOLUTION_IN_SPACE)
        self.assertNotIn("proof_attempt", found["certificate"])
        self.assertIn("Q[[x]] at zero; analytic germs only", found["premises"])

    def test_an_operation_that_fixes_a_component_is_admitted_by_projection(self):
        # The identity is not an empty relation; it is the rearrangement that
        # does nothing on the abstract side, and it has an induced operation.
        for component in (0, 1):
            found = induced_component(SIGNATURE, MORPHISMS["stay"], component,
                                      WITNESSES[0], degree_x=0)
            self.assertTrue(found["found"], component)
            self.assertEqual(found["route"], "projection")
            self.assertEqual(found["template"], slot(SIGNATURE["names"][component]))

    def test_a_component_only_uses_the_declared_abstract_names(self):
        operation = induced_operation(SIGNATURE, MORPHISMS["translate"], WITNESSES[0],
                                      degree_x=0)
        for component in operation["body"]:
            symbols = ring_expression(component, {}).free_symbols
            self.assertTrue({str(s) for s in symbols}
                            <= {"sym_s", "sym_p", "sym_c"}, symbols)

    def test_the_search_is_reproved_for_every_replacement(self):
        verdict = well_defined(SIGNATURE, MORPHISMS["translate"], 0, WITNESSES,
                               checks=3, degree_x=0)
        self.assertTrue(verdict["well_defined"])
        self.assertEqual(verdict["checked"], 3)
        self.assertTrue(verdict["same_template_every_time"])


class QueryTests(unittest.TestCase):
    def test_a_question_that_depends_only_on_alpha_survives(self):
        verdict = query_survives(SIGNATURE, QUERIES[0][1], WITNESSES, checks=3,
                                 degree_x=0)
        self.assertTrue(verdict["survives"])

    def test_a_question_that_needs_the_order_is_dropped(self):
        verdict = query_survives(SIGNATURE, QUERIES[1][1], WITNESSES, checks=3,
                                 degree_x=0)
        self.assertFalse(verdict["survives"])


class CorrespondenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = correspondence(
            SIGNATURE, MORPHISMS, WITNESSES, queries=QUERIES, degree_x=0,
            abstract_domain="unordered pair via sum and product",
            source_type="pair of holonomic programs", checks=3)

    def test_only_operations_that_descend_are_supported(self):
        self.assertEqual(sorted(induced_operations(self.record)),
                         ["stay", "swap", "translate"])
        self.assertEqual([u["morphism"] for u in self.record["unsupported_morphisms"]],
                         ["left_only"])

    def test_the_refusal_names_condition_two_and_the_failing_component(self):
        refused = self.record["unsupported_morphisms"][0]
        self.assertIn("condition (2)", refused["reason"])
        self.assertEqual([f["component"] for f in refused["condition_two"]["failures"]],
                         [1])

    def test_the_record_carries_what_it_supports_and_what_it_dropped(self):
        for field in ("source_type", "abstract_type", "abstraction_map", "signature",
                      "supported_morphisms", "unsupported_morphisms",
                      "supported_queries", "dropped_queries", "domain_conditions",
                      "image_conditions", "alpha_preserving_rearrangements", "sha256"):
            self.assertIn(field, self.record)
        self.assertEqual([q["query"] for q in self.record["supported_queries"]],
                         ["difference_squared"])
        self.assertEqual([q["query"] for q in self.record["dropped_queries"]],
                         ["difference"])

    def test_every_supported_operation_carries_its_arguments_and_its_proof(self):
        for entry in self.record["supported_morphisms"]:
            self.assertEqual(entry["coordinate_names"], ["s", "p"])
            self.assertEqual(entry["parameter_names"], ["c"])
            self.assertIn("domain", entry)
            self.assertTrue(all(p["proved"] for p in entry["identity_proofs"]))
            self.assertEqual(sorted(entry["argument_correspondence"]["coordinates"]),
                             ["p", "s"])

    def test_the_record_states_the_law_its_proof_rests_on(self):
        conditions = self.record["domain_conditions"]
        self.assertIn("independent symbols", conditions["universality"])
        self.assertIn("commutative ring", conditions["law"])
        self.assertEqual(conditions["available_names"], ["s", "p", "c"])
        self.assertIn("never admits anything", self.record["admission_rule"])

    def test_no_rearrangement_admits_an_operation_on_its_own(self):
        for entry in self.record["supported_morphisms"]:
            self.assertEqual(entry["admitted_by"],
                             "identity proved for independent inputs")

    def test_the_next_round_gets_objects_and_the_operations_that_work_on_them(self):
        seeds = next_round_seeds(self.record, WITNESSES[0])
        origins = {s["origin"] for s in seeds}
        self.assertEqual(origins, {"abstract_coordinate", "induced_operation"})
        offered = {s.get("morphism") for s in seeds if s["origin"] == "induced_operation"}
        self.assertEqual(offered, {"stay", "swap", "translate"})

    def test_a_refused_operation_reaches_no_later_round(self):
        images = induced_images(self.record, WITNESSES[0])
        self.assertNotIn("left_only", {i["morphism"] for i in images})

    def test_the_abstract_coordinates_are_programs(self):
        seeds = abstract_seeds(self.record, WITNESSES[0])
        self.assertEqual(len(seeds), 2)
        self.assertEqual(seeds[0], add(WITNESSES[0]["u"], WITNESSES[0]["v"]))


class SymbolicProofTests(unittest.TestCase):
    """A rearrangement finding no counterexample must never admit anything."""

    def test_the_square_is_proved_for_independent_inputs(self):
        scaled = {"op": "scale", "child": C, "factor": "2"}
        first = prove_identity(add(add(U, C), add(V, C)), add(add(U, V), scaled))
        second = prove_identity(mul(add(U, C), add(V, C)),
                                add(add(mul(U, V), mul(C, add(U, V))), mul(C, C)))
        self.assertTrue(first["proved"])
        self.assertTrue(second["proved"])

    def test_an_asymmetric_square_leaves_a_residual(self):
        verdict = prove_identity(mul(add(U, C), V),
                                 add(mul(U, V), mul(C, add(U, V))))
        self.assertFalse(verdict["proved"])
        self.assertNotEqual(verdict["residual"], "0")

    def test_an_operation_with_no_registered_law_is_refused_not_translated(self):
        # `pullback` is executable and certifiable as a series, and no axiom here
        # says what it does to an arbitrary element, so it stays outside rather
        # than being quietly translated.
        outcome = prove_identity({"op": "pullback", "child": U,
                                  "numerator": [0, 1], "denominator": [1, 0]}, U)
        self.assertTrue(outcome["outside_fragment"])
        self.assertIn("outside", outcome["reason"])
        with self.assertRaises(OutsideRingFragment):
            ring_expression({"op": "pullback", "child": U,
                             "numerator": [0, 1], "denominator": [1, 0]}, {})

    def test_differentiation_is_decided_by_its_law_not_refused(self):
        # `diff` is registered and has a universal law, so it is judged rather
        # than declined, and judged false here with a residual.
        outcome = prove_identity({"op": "diff", "child": U}, U)
        self.assertFalse(outcome["outside_fragment"])
        self.assertFalse(outcome["proved"])
        self.assertEqual(outcome["law"], DERIVATION_LAW)
        self.assertNotEqual(outcome["residual"], "0")

    def test_a_certified_relation_that_is_not_an_identity_is_not_admitted(self):
        # `express` decides with the same identity the acceptance rests on, so a
        # candidate that only fits these operands is dropped where it is found.
        found = express(SIGNATURE, add(U, negate(V)), WITNESSES[0], degree_x=0)
        self.assertFalse(found["found"])
        self.assertIsNone(found["template"])


class CallableOperationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.operation = induced_operation(SIGNATURE, MORPHISMS["translate"],
                                          WITNESSES[0], degree_x=0)
        cls.identity = induced_operation(SIGNATURE, MORPHISMS["stay"],
                                         WITNESSES[0], degree_x=0)

    def test_the_operation_is_recovered_and_proved(self):
        self.assertTrue(self.operation["proved"])
        self.assertEqual(len(self.operation["body"]), 2)
        self.assertEqual(self.operation["domain"]["coordinate_names"], ["s", "p"])

    def test_it_can_be_applied_to_any_input(self):
        applied = apply_operation(self.operation,
                                  {"s": slot("S"), "p": slot("P"), "c": slot("K")})
        self.assertEqual(len(applied), 2)
        for component in applied:
            self.assertIsNotNone(ring_expression(component, {}))

    def test_an_operation_that_moves_nothing_says_so(self):
        self.assertTrue(is_identity_operation(self.identity))
        self.assertFalse(is_identity_operation(self.operation))
        self.assertEqual(uses_parameters(self.identity), [])
        self.assertEqual(uses_parameters(self.operation), ["c"])

    def test_self_composition_gets_independent_parameters(self):
        composed = compose_operations(self.operation, self.operation)
        self.assertEqual(composed["parameter_names"], ["c", "c_2"])
        self.assertEqual(composed["rename"], {"c": "c_2"})

    def test_a_composite_states_the_stronger_of_its_premises(self):
        from math_os_prototype.abstraction_correspondence import RING_LAW
        signature = abstract_signature([add(U, V)], coordinate_names=["a0"])
        derivative = solve_component(
            signature,
            fill(add(U, V), {"u": {"op": "diff", "child": U},
                             "v": {"op": "diff", "child": V}}),
            degree=1, derivatives=1)
        differentiating = {"body": [derivative["template"]],
                           "coordinate_names": ["a0"], "parameter_names": [],
                           "domain": {"abstraction_map": [add(U, V)]},
                           "law": DERIVATION_LAW, "proved": True, "proofs": []}
        plain = dict(differentiating, body=[slot("a0")], law=RING_LAW)
        self.assertEqual(compose_operations(plain, differentiating)["law"],
                         DERIVATION_LAW)
        self.assertEqual(compose_operations(plain, plain)["law"], RING_LAW)

    def test_composition_correctness_is_inherited_not_reproved(self):
        composed = compose_operations(self.operation, self.operation)
        self.assertTrue(composed["proved"])
        self.assertEqual(composed["proofs"], [])
        self.assertIn("inherited", composed["inherited_proofs"]["rule"])
        self.assertTrue(all(p["proved"] for p in composed["inherited_proofs"]["outer"]))

    def test_the_composition_law_is_searched_and_proved_separately(self):
        composed = compose_operations(self.operation, self.operation)
        law = composition_law(self.operation, composed)
        self.assertTrue(law["proved"])
        self.assertEqual(law["parameter"], "sym_c + sym_c_2")
        self.assertFalse(law["parameter_free_base"])
        self.assertTrue(all(p["proved"] for p in law["proofs"]))

    def test_a_law_over_a_body_that_ignores_its_parameter_says_nothing(self):
        composed = compose_operations(self.identity, self.identity)
        law = composition_law(self.identity, composed)
        self.assertTrue(law["proved"])
        self.assertTrue(law["parameter_free_base"])
        self.assertIn("says nothing", law["reason"])

    def test_a_conserved_quantity_is_solved_for_not_supplied(self):
        import sympy as sp
        self.assertEqual(conserved_quantities(self.operation, degree=1)["found"], [])
        found = conserved_quantities(self.operation, degree=2,
                                     signature=SIGNATURE)
        self.assertEqual(len(found["found"]), 1)
        s, p = sp.Symbol("sym_s"), sp.Symbol("sym_p")
        self.assertEqual(sp.expand(sp.sympify(found["found"][0]) - (s**2 - 4*p)), 0)
        self.assertEqual(found["quantities"][0]["class"], "observable")
        self.assertTrue(found["quantities"][0]["invariance"]["proved"])

    def test_an_operation_that_moves_nothing_yields_no_quantities(self):
        found = conserved_quantities(self.identity, degree=2, signature=SIGNATURE)
        self.assertEqual(found["found"], [])
        self.assertIn("moves nothing", found["reason"])


class ImageTests(unittest.TestCase):
    """Redundant coordinates are allowed; what they satisfy has to be recorded."""

    @classmethod
    def setUpClass(cls):
        cls.morphism = {"u": add(U, C), "v": V, "c": C}
        cls.operation = induced_operation(REDUNDANT_SIGNATURE, cls.morphism,
                                          WITNESSES[0], degree_x=0)

    def test_a_dependent_abstraction_still_induces_an_operation(self):
        import sympy as sp
        self.assertTrue(self.operation["proved"])
        a0, a1, c = (sp.Symbol("sym_a0"), sp.Symbol("sym_a1"), sp.Symbol("sym_c"))
        body = [ring_expression(part, {}) for part in self.operation["body"]]
        self.assertEqual(sp.expand(body[0] - (a0 + c)), 0)
        self.assertEqual(sp.expand(body[1] - (a1 + 2*a0*c + c**2)), 0)

    def test_a_quantity_that_vanishes_on_the_image_is_a_domain_relation(self):
        verdict = classify_on_image("sym_a0**2 - sym_a1", REDUNDANT_SIGNATURE)
        self.assertEqual(verdict["class"], "domain_relation")
        self.assertEqual(verdict["on_image"], "0")

    def test_a_quantity_that_varies_on_the_image_is_an_observable(self):
        verdict = classify_on_image("sym_s**2 - 4*sym_p", SIGNATURE)
        self.assertEqual(verdict["class"], "observable")

    def test_a_quantity_with_no_free_symbols_on_the_image_is_a_constant(self):
        verdict = classify_on_image("sym_a0*sym_a1 - sym_a0*sym_a1 + 5",
                                    REDUNDANT_SIGNATURE)
        self.assertEqual(verdict["class"], "constant")
        self.assertEqual(verdict["on_image"], "5")

    def test_the_preserved_quantity_here_is_a_relation_not_new_structure(self):
        found = conserved_quantities(self.operation, degree=2,
                                     signature=REDUNDANT_SIGNATURE)
        self.assertEqual(found["found"], [])
        self.assertEqual([q["class"] for q in found["quantities"]],
                         ["domain_relation"])
        self.assertEqual(found["quantities"][0]["expression"], "sym_a0**2 - sym_a1")

    def test_a_domain_relation_is_kept_with_the_abstract_object(self):
        record = correspondence(
            REDUNDANT_SIGNATURE, {"shift": self.morphism}, WITNESSES, degree_x=0,
            abstract_domain="dependent pair", source_type="pair", checks=1)
        found = conserved_quantities(record["supported_morphisms"][0], degree=2,
                                     signature=REDUNDANT_SIGNATURE)
        self.assertTrue(record_image_condition(record, found["quantities"][0]))
        self.assertFalse(record_image_condition(record, found["quantities"][0]))
        self.assertEqual([c["expression"] for c in record["image_conditions"]],
                         ["sym_a0**2 - sym_a1"])
        self.assertEqual(
            record["supported_morphisms"][0]["domain"]["image_conditions"],
            record["image_conditions"])


class IndependenceTests(unittest.TestCase):
    """Raising the degree always produces more solutions; most are the old ones."""

    @classmethod
    def setUpClass(cls):
        cls.signature = abstract_signature([U, V], coordinate_names=["a0", "a1"],
                                           parameter_names=["c"])
        cls.operation = induced_operation(
            cls.signature, {"u": add(U, C), "v": add(V, C), "c": C},
            WITNESSES[0], degree_x=0)

    def test_a_power_of_a_conserved_quantity_is_not_counted_again(self):
        found = conserved_quantities(self.operation, degree=2,
                                     signature=self.signature)
        self.assertEqual(len(found["found"]), 1)
        self.assertEqual(len(found["generated"]), 1)
        self.assertIn("**2", found["generated"][0]["expression"])
        self.assertIn("already found", found["generated"][0]["reason"])

    def test_the_generator_itself_is_kept(self):
        import sympy as sp
        found = conserved_quantities(self.operation, degree=2,
                                     signature=self.signature)
        a0, a1 = sp.Symbol("sym_a0"), sp.Symbol("sym_a1")
        self.assertEqual(sp.expand(sp.sympify(found["found"][0]) - (a1 - a0)), 0)


class DomainTests(unittest.TestCase):
    """Two abstractions can spell their coordinates the same and mean different
    things, and an operation only composes with one on its own object."""

    def test_operations_on_different_abstractions_do_not_compose(self):
        first = abstract_signature([U, V], coordinate_names=["a0", "a1"],
                                   parameter_names=["c"])
        second = abstract_signature([U, mul(U, U)], coordinate_names=["a0", "a1"],
                                    parameter_names=["c"])
        left = induced_operation(first, {"u": add(U, C), "v": add(V, C), "c": C},
                                 WITNESSES[0], degree_x=0)
        right = induced_operation(second, {"u": add(U, C), "v": V, "c": C},
                                  WITNESSES[0], degree_x=0)
        self.assertEqual(left["coordinate_names"], right["coordinate_names"])
        self.assertFalse(same_domain(left, right))
        self.assertTrue(same_domain(left, left))
        with self.assertRaises(ValueError):
            compose_operations(left, right)


class DifferentialFragmentTests(unittest.TestCase):
    """A registered operation with a universal law, connected to the prover."""

    def test_the_derivation_is_additive_and_obeys_leibniz(self):
        import sympy as sp
        u, v = differential_expression(U, {}), differential_expression(V, {})
        du, dv = derive(u), derive(v)
        self.assertEqual(sp.expand(derive(u + v) - (du + dv)), 0)
        self.assertEqual(sp.expand(derive(u * v) - (du * v + u * dv)), 0)
        self.assertEqual(derive(sp.Integer(5)), 0)

    def test_a_derivative_expression_reads_back_as_a_program(self):
        import sympy as sp
        wanted = derive(differential_expression(mul(U, V), {}))
        program = ring_program(wanted)
        self.assertEqual(sp.expand(differential_expression(program, {}) - wanted), 0)

    def test_the_span_can_contain_derivatives_of_the_coordinates(self):
        generators, monomials = monomial_basis(["a0"], degree=1, derivatives=1)
        self.assertEqual([str(g) for g in generators], ["sym_a0", "sym_a0__d1"])
        self.assertIn("sym_a0__d1", [str(m) for m in monomials])

    def test_a_differentiating_operation_gets_a_universal_induced_operation(self):
        # alpha(U,V) = U+V, f = (D U, D V). h(a) = D(a) is solved for, not given.
        signature = abstract_signature([add(U, V)], coordinate_names=["a0"])
        morphism = {"u": {"op": "diff", "child": U}, "v": {"op": "diff", "child": V}}
        found = solve_component(signature, fill(add(U, V), morphism),
                                degree=1, derivatives=1)
        self.assertEqual(found["status"], PROVED)
        self.assertEqual(found["template"], {"op": "diff", "child": slot("a0")})
        self.assertEqual(found["proof"]["law"], DERIVATION_LAW)
        self.assertEqual(found["proof"]["residual"], "0")

    def test_without_derivatives_in_the_span_the_answer_is_about_that_span(self):
        signature = abstract_signature([add(U, V)], coordinate_names=["a0"])
        morphism = {"u": {"op": "diff", "child": U}, "v": {"op": "diff", "child": V}}
        found = solve_component(signature, fill(add(U, V), morphism),
                                degree=2, derivatives=0)
        self.assertEqual(found["status"], NO_SOLUTION_IN_SPACE)
        self.assertEqual(found["grammar"]["derivatives"], 0)
        self.assertIn("span", found["reason"])


class CompleteSolveTests(unittest.TestCase):
    """The polynomial route is a complete solve in a declared span, nothing more."""

    MORPHISM = {"u": add(U, C), "v": V, "c": C}

    def signature(self):
        return abstract_signature(REDUNDANT, coordinate_names=["a0", "a1"],
                                  parameter_names=["c"])

    def test_the_answer_does_not_depend_on_which_witness_was_bound(self):
        signature = self.signature()
        left = fill(REDUNDANT[1], self.MORPHISM)
        first = solve_component(signature, left, degree=2)
        second = express(signature, left, WITNESSES[0], degree_x=0)
        third = express(signature, left, WITNESSES[1], degree_x=0)
        self.assertEqual(first["status"], PROVED)
        self.assertEqual(second["status"], third["status"])
        self.assertEqual(second["template"], third["template"])
        self.assertEqual(second["template"], first["template"])

    def test_no_solution_is_scoped_to_the_declared_span(self):
        found = solve_component(self.signature(),
                                fill(REDUNDANT[1], self.MORPHISM), degree=1)
        self.assertEqual(found["status"], NO_SOLUTION_IN_SPACE)
        self.assertEqual(found["grammar"]["degree"], 1)
        self.assertIn("rational form or another representation is untouched",
                      found["reason"])

    def test_an_abstraction_outside_the_fragment_is_not_applicable(self):
        signature = abstract_signature(
            [{"op": "pullback", "child": U, "numerator": [0, 1],
              "denominator": [1, 0]}], coordinate_names=["a0"])
        found = solve_component(signature, U, degree=1)
        self.assertEqual(found["status"], NOT_APPLICABLE)
        self.assertIsNone(found["template"])


class UnregisteredOperationTests(unittest.TestCase):
    """What the grammar does not have, this layer must not pretend to have."""

    def test_the_program_grammar_has_no_division(self):
        from math_os_prototype.holonomic_route_discovery import validate
        for shape in ({"op": "div", "left": U, "right": V},
                      {"op": "reciprocal", "child": U}):
            with self.assertRaises(ValueError):
                validate(shape)

    def test_a_reciprocal_cannot_be_written_in_either_fragment(self):
        import sympy as sp
        with self.assertRaises(OutsideRingFragment):
            ring_program(sp.Integer(1) / sp.Symbol("sym_a0"))


if __name__ == "__main__":
    unittest.main()
