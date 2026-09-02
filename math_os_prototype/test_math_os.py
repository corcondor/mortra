import json
import unittest
from unittest.mock import patch

import sympy as sp

from math_os_prototype.arithmetic_nl import detect_arithmetic_nl_problem
from math_os_prototype.case_frame_parser import parse_case_frames
from math_os_prototype.category_semantics import compile_typed_semantic_graph, run_verifier_gate
from math_os_prototype.container_geometry import detect_container_problem, solve_container_problem
from math_os_prototype.domain_registry import DomainRegistry, run_domain_benchmark
from math_os_prototype.formal_language import compile_formal_ir
from math_os_prototype.geometry_dsl import parse_geometry_dsl, run_geometry_dsl
from math_os_prototype.geometry_nl import convert_geometry_nl
from math_os_prototype.generalization_benchmark import (
    generate_generalization_cases,
    generate_same_structure_pairs,
    run_generalization_benchmark,
)
from math_os_prototype.latex_frontend import parse_latex_problem, split_tex_text_math
from math_os_prototype.lift_lifter import run_lift_lifter_experiment
from math_os_prototype.math_os import ProblemCompiler, TinyRouter, ToolExecutor, run_pipeline
from math_os_prototype.math_search import run_math_search
from math_os_prototype.public_benchmark import answers_match
from math_os_prototype.quantity_reasoner import solve_quantity_reasoning_problem
from math_os_prototype.reasoning_pipeline import run_reasoning_pipeline
from math_os_prototype.retriever import HybridRetriever, QueryBuilder
from math_os_prototype.solution_step_parser import SolutionStepParser
from math_os_prototype.step_verifier import StepVerifier
from math_os_prototype.structural_parser import analyze_structure
from math_os_prototype.symbolic_query import compile_symbolic_query, execute_symbolic_query
from math_os_prototype.theory_atlas import canonical_graph_signature, compare_lift_structures
from math_os_prototype.tool_adapters import ToolRegistry, wolfram_code_for_geometry
from math_os_prototype.typed_definition_kernel import LEXICON, compile_typed_definition_ir
from math_os_prototype.web_app import extract_answer_from_pipeline_data, solve_request_payload
from math_os_prototype.web_solution_fetcher import extract_stackexchange_question_id


class MathOsPrototypeTest(unittest.TestCase):
    def test_arithmetic_nl_compiles_reusable_syntax(self):
        problem = (
            "Janet's ducks lay 16 eggs per day. She eats three for breakfast every morning "
            "and bakes muffins for her friends every day with four. She sells the remainder "
            "at the farmers' market daily for $2 per fresh duck egg."
        )
        parsed = detect_arithmetic_nl_problem(problem)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.intent, "remainder_sale")
        self.assertEqual(parsed.expression, "(16-3-4)*2")

    def test_full_pipeline_solves_arithmetic_nl_without_specialized_adapter(self):
        result = solve_request_payload(
            {
                "problem": "What is the positive difference between $120\\%$ of 30 and $130\\%$ of 20?",
                "full_pipeline": True,
            }
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["answer"], "10")
        self.assertEqual(result["data"]["parser"]["intent"], "arithmetic_nl_percent_difference")

    def test_full_pipeline_solves_public_word_problem_syntax(self):
        result = solve_request_payload(
            {
                "problem": (
                    "John drives for 3 hours at a speed of 60 mph and then turns around. "
                    "He tries to get home in 4 hours but spends the first 2 hours in standstill traffic. "
                    "He spends the next half-hour driving at a speed of 30mph, before being able to drive "
                    "the remaining time of the 4 hours going at 80 mph. How far is he from home?"
                ),
                "full_pipeline": True,
            }
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["answer"], "45")

    def test_state_event_backend_preserves_loss_and_gain_signs(self):
        problem = (
            "A waiter had 12 customers. While 15 customers left he got 14 new customers. "
            "How many customers does he still have?"
        )
        for _ in range(3):
            result = solve_request_payload({"problem": problem, "full_pipeline": True})
            self.assertTrue(result["ok"])
            self.assertEqual(result["answer"], "11")

    def test_arithmetic_nl_handles_math_benchmark_syntax(self):
        asymptote = solve_request_payload(
            {
                "problem": r"How many vertical asymptotes does the graph of $y=\frac{2}{x^2+x-6}$ have?",
                "full_pipeline": True,
            }
        )
        dice = solve_request_payload(
            {
                "problem": r"$n$ fair 6-sided dice are simultaneously rolled. The probability that exactly two of them show a number other than 1 is $\frac{25}{216}$. Find $n$.",
                "full_pipeline": True,
            }
        )
        self.assertEqual(asymptote["answer"], "2")
        self.assertEqual(dice["answer"], "4")

    def test_surface_morphism_adapters_are_opt_in(self):
        text = "What is the 100th term of the arithmetic sequence 6 10 14?"
        self.assertIsNone(detect_arithmetic_nl_problem(text))
        enabled = detect_arithmetic_nl_problem(text, allow_surface_morphisms=True)
        self.assertIsNotNone(enabled)
        self.assertEqual(enabled.intent, "allfield_arithmetic_sequence_nth_term")

        cold = run_reasoning_pipeline(text)
        self.assertNotEqual(cold.parser["intent"], "arithmetic_nl_allfield_arithmetic_sequence_nth_term")
        specialized = run_reasoning_pipeline(text, allow_specialized=True)
        self.assertEqual(specialized.parser["intent"], "arithmetic_nl_allfield_arithmetic_sequence_nth_term")

    def test_semantic_graph_lifts_solution_parts_as_morphisms(self):
        sequence = compile_typed_semantic_graph(
            "What is the 100th term of the arithmetic sequence whose first term is 6 and second term is 10?"
        )
        sequence_morphisms = {item.name for item in sequence.morphisms}
        sequence_queries = {item.target for item in sequence.queries}
        self.assertIn("ArithmeticProgression", sequence_morphisms)
        self.assertIn("NthTerm", sequence_morphisms)
        self.assertIn("NthTerm(seq,100)", sequence_queries)

        geometry = compile_typed_semantic_graph("Find the distance from the origin to the point (3,4).")
        geometry_morphisms = {item.name for item in geometry.morphisms}
        geometry_queries = {item.target for item in geometry.queries}
        self.assertIn("Distance", geometry_morphisms)
        self.assertIn("Distance(O,P)", geometry_queries)

        midpoint = compile_typed_semantic_graph("Find the sum of the coordinates of the midpoint of (2,6) and (8,10).")
        midpoint_morphisms = {item.name for item in midpoint.morphisms}
        midpoint_queries = {item.target for item in midpoint.queries}
        self.assertIn("Midpoint", midpoint_morphisms)
        self.assertIn("CoordinateSum", midpoint_morphisms)
        self.assertIn("CoordinateSum(Midpoint(A,B))", midpoint_queries)

    def test_lift_certificates_define_same_structure(self):
        first = compile_typed_semantic_graph("What is the 100th term of the arithmetic sequence 6 10 14?")
        second = compile_typed_semantic_graph("Find the 50th term of the arithmetic sequence 2 5 8.")
        report = compare_lift_structures(first.lift_certificates, second.lift_certificates)
        self.assertTrue(report["same_structure"])
        self.assertTrue(any("discrete_affine_sequence.nth_term" in item for item in report["shared_signatures"]))

        distance_a = compile_typed_semantic_graph("Find the distance from the origin to the point (3,4).")
        distance_b = compile_typed_semantic_graph("Compute the distance from the origin to the point (5,12).")
        distance_report = compare_lift_structures(distance_a.lift_certificates, distance_b.lift_certificates)
        self.assertTrue(distance_report["same_structure"])
        self.assertTrue(any("inner_product_geometry.distance" in item for item in distance_report["shared_signatures"]))

        sequence_signature = canonical_graph_signature(first.lift_certificates)
        distance_signature = canonical_graph_signature(distance_a.lift_certificates)
        self.assertFalse(set(sequence_signature) & set(distance_signature))

    def test_generalization_benchmark_protocol_covers_required_axes(self):
        cases = generate_generalization_cases(seeds=1)
        pairs = generate_same_structure_pairs(cases)
        family_count = len({case.family_id for case in cases})
        self.assertGreaterEqual(family_count, 25)
        self.assertEqual(len(cases), family_count * 3)
        self.assertEqual(len(pairs), family_count * 2)
        self.assertEqual({case.transform for case in cases}, {"base", "surface", "numeric"})
        self.assertIn("held_out", {case.split for case in cases})

        result = run_generalization_benchmark(seeds=1, modes=["certified_lift_backend"])
        self.assertEqual(result["generated"]["case_count"], family_count * 3)
        self.assertEqual(result["generated"]["same_structure_pair_count"], family_count * 2)
        certified = result["modes"]["certified_lift_backend"]
        self.assertEqual(certified["lift_family_match_rate"], 1.0)
        self.assertEqual(certified["lift_certificate_pair_match_rate"], 1.0)

    def test_lift_lifter_learns_certificates_not_answers(self):
        result = run_lift_lifter_experiment(seeds=5)
        summary = result["seven_axis_summary"]
        self.assertEqual(summary["1_family_id"], 1.0)
        self.assertEqual(summary["2_morphism_chain"], 1.0)
        self.assertEqual(summary["3_constraint_skeleton"], 1.0)
        self.assertEqual(summary["4_query_signature"], 1.0)
        self.assertEqual(summary["5_backend_execution_success"], 1.0)
        self.assertEqual(summary["6_surface_numeric_same_structure"], 1.0)
        self.assertEqual(summary["7_negative_structure_not_confused"], 1.0)

    def test_case_frame_arithmetic_handles_public_word_problem_relations(self):
        breakeven = solve_request_payload(
            {
                "problem": (
                    "Carlos is planting a lemon tree. The tree will cost $90 to plant. "
                    "Each year it will grow 7 lemons, which he can sell for $1.5 each. "
                    "It costs $3 a year to water and feed the tree. How many years will it take "
                    "before he starts earning money on the lemon tree?"
                ),
                "full_pipeline": True,
            }
        )
        speed = solve_request_payload(
            {
                "problem": (
                    "Marissa is hiking a 12-mile trail. She took 1 hour to walk the first 4 miles, "
                    "then another hour to walk the next two miles. If she wants her average speed "
                    "to be 4 miles per hour, what speed (in miles per hour) does she need to walk "
                    "the remaining distance?"
                ),
                "full_pipeline": True,
            }
        )
        self.assertEqual(breakeven["answer"], "13")
        self.assertEqual(speed["answer"], "6")
        self.assertTrue(breakeven["data"]["parser"]["intent"].startswith("arithmetic_nl_case_frame_"))
        self.assertTrue(speed["data"]["parser"]["intent"].startswith("arithmetic_nl_case_frame_"))

    def test_arithmetic_nl_generic_state_updates(self):
        state = solve_request_payload(
            {
                "problem": "Paige had 11 songs on her mp3 player. If she deleted 9 old songs from it and then added 8 new songs, how many songs does she have on her mp3 player?",
                "full_pipeline": True,
            }
        )
        remaining_time = solve_request_payload(
            {
                "problem": "A painter needed to paint 12 rooms in a building. Each room takes 7 hours to paint. If he already painted 5 rooms, how much longer will he take to paint the rest?",
                "full_pipeline": True,
            }
        )
        self.assertEqual(state["answer"], "10")
        self.assertEqual(remaining_time["answer"], "49")

    def test_arithmetic_nl_tracks_target_objects(self):
        cookies = solve_request_payload(
            {
                "problem": "Paco had 9 sweet cookies and 6 salty cookies. He ate 36 sweet cookies and 3 salty cookies. How many salty cookies did Paco have left?",
                "full_pipeline": True,
            }
        )
        coops = solve_request_payload(
            {
                "problem": "Ben counted a total of 9 chicken coops and Daniel said that there are 60 chickens in one coop. How many chickens do they have in total?",
                "full_pipeline": True,
            }
        )
        self.assertEqual(cookies["answer"], "3")
        self.assertEqual(coops["answer"], "540")

    def test_quantity_reasoner_handles_complement_counts_and_pronouns(self):
        recycled = solve_request_payload(
            {
                "problem": "Megan earned 8 points for each bag of cans she recycled. If she had 14 bags, but didn't recycle 5 of them, how many points would she have earned?",
                "full_pipeline": True,
            }
        )
        books = solve_request_payload(
            {
                "problem": "Tom had 5 books. If he sold 4 of them and used the money he earned to buy 38 new books, how many books would Tom have?",
                "full_pipeline": True,
            }
        )
        tips = solve_request_payload(
            {
                "problem": "At lunch a waiter had 7 customers and 5 of them didn't leave a tip. If he got $3 each from the ones who did tip, how much money did he earn?",
                "full_pipeline": True,
            }
        )
        self.assertEqual(recycled["answer"], "72")
        self.assertEqual(books["answer"], "39")
        self.assertEqual(tips["answer"], "6")

    def test_quantity_reasoner_distinguishes_containers_from_products(self):
        folders = solve_request_payload(
            {
                "problem": "Nancy had 80 files on her computer. She deleted 31 of them and put the rest into folders with 7 files in each one. How many folders did Nancy end up with?",
                "full_pipeline": True,
            }
        )
        quarters = solve_request_payload(
            {
                "problem": "Jason had 49 quarters in his bank. His dad gave him 25 more quarters. How many quarters does he have now?",
                "full_pipeline": True,
            }
        )
        self.assertEqual(folders["answer"], "7")
        self.assertEqual(quarters["answer"], "74")

    def test_quantity_reasoner_builds_structural_equation_candidates(self):
        gain_loss = solve_request_payload(
            {
                "problem": "Dave had 21 apps on his phone. He added 89 new apps. After deleting some he had 24 left. How many more apps did he add than he deleted?",
                "full_pipeline": True,
            }
        )
        category_diff = solve_request_payload(
            {
                "problem": "In a school there are 362 boys and 257 girls. 403 more girls joined the school. How many more girls than boys does the school have?",
                "full_pipeline": True,
            }
        )
        per_unit_diff = solve_request_payload(
            {
                "problem": "They have 14 chairs for each set of table. If they have 9 sets of tables How many more chairs than tables do they have?",
                "full_pipeline": True,
            }
        )
        self.assertEqual(gain_loss["answer"], "3")
        self.assertEqual(category_diff["answer"], "298")
        self.assertEqual(per_unit_diff["answer"], "117")

    def test_quantity_reasoner_handles_time_cost_and_partitions(self):
        time_diff = solve_request_payload(
            {
                "problem": "Julia played tag with 9 kids on monday, 7 kids on tuesday and 96 kids on wednesday. How many more kids did she play with on monday than on tuesday?",
                "full_pipeline": True,
            }
        )
        breakfast = solve_request_payload(
            {
                "problem": "Ron and Chanarong had breakfast at a cafe. Muffins cost $2 each, and fruit cups cost $2 each. Ron had 1 muffin and 2 fruit cups. Chanarong had 1 muffin and 2 fruit cups. How much did their breakfast cost?",
                "full_pipeline": True,
            }
        )
        groups = solve_request_payload(
            {
                "problem": "There are 56 students in the class. The teacher wants to split them into two groups. The first group has 24 students. How many more students will there be in the second group?",
                "full_pipeline": True,
            }
        )
        self.assertEqual(time_diff["answer"], "2")
        self.assertEqual(breakfast["answer"], "12")
        self.assertEqual(groups["answer"], "8")

    def test_quantity_reasoner_handles_partitions_capacity_and_initial_gain(self):
        split = solve_request_payload(
            {
                "problem": "At a company picnic 23 managers and 7 employees decided to start a game of volleyball. If they split into 6 teams how many people would be on each team?",
                "full_pipeline": True,
            }
        )
        buses = solve_request_payload(
            {
                "problem": "The school has 67 classrooms. There are 66 students in each classroom. If there are 6 seats on each school bus How many buses are needed?",
                "full_pipeline": True,
            }
        )
        initial = solve_request_payload(
            {
                "problem": "Tera had some mango. Becky gave him 7 more. Now Tera has 31 mango. How many mango did Tera have initially?",
                "full_pipeline": True,
            }
        )
        self.assertEqual(split["answer"], "5")
        self.assertEqual(buses["answer"], "737")
        self.assertEqual(initial["answer"], "24")

    def test_quantity_reasoner_handles_complement_partition_and_local_unit_labels(self):
        complement = solve_request_payload(
            {
                "problem": "John earned 8 dollars for each lawn he mowed. If he had 15 lawns to mow, but forgot to mow 7 of them, how much money did he actually earn?",
                "full_pipeline": True,
            }
        )
        remaining = solve_request_payload(
            {
                "problem": "Tiffany baked 8 brownies, but needed 17 total for her party. If she used 8 cups of flour on each one, how much cups of flour does she still need?",
                "full_pipeline": True,
            }
        )
        label_rate = solve_request_payload(
            {
                "problem": "The shop makes $115 off each jersey and $25 off each t-shirt. How much more does a jersey cost than a t-shirt?",
                "full_pipeline": True,
            }
        )
        self.assertEqual(complement["answer"], "64")
        self.assertEqual(remaining["answer"], "72")
        self.assertEqual(label_rate["answer"], "90")

    def test_quantity_reasoner_emits_logic_level_semantics(self):
        result = solve_quantity_reasoning_problem(
            "The school has 67 classrooms. There are 66 students in each classroom. "
            "If there are 6 seats on each school bus How many buses are needed?"
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.answer_exact, "737")
        self.assertEqual(result.semantic_model["output_sort"]["base"], "Count")
        self.assertEqual(result.semantic_model["output_sort"]["obj"], "bus")
        self.assertIn("(typed answer (Count bus))", result.semantic_model["obligations"])
        self.assertIn("(Rate student classroom)", result.semantic_model["best_sequent"])
        self.assertIn("(Rate seat bus)", result.semantic_model["best_sequent"])
        payload = solve_request_payload(
            {
                "problem": "The school has 67 classrooms. There are 66 students in each classroom. If there are 6 seats on each school bus How many buses are needed?",
                "full_pipeline": True,
            }
        )
        semantic_model = payload["data"]["parser"]["givens"]["arithmetic_problem"]["metadata"]["semantic_model"]
        self.assertEqual(semantic_model["output_sort"]["obj"], "bus")

    def test_quantity_reasoner_handles_generic_state_rate_and_selection(self):
        per_day = solve_request_payload(
            {
                "problem": "The ring toss game made the same amount of money each day. In total in 5 days they earned 165 dollars. How much did they make per day?",
                "full_pipeline": True,
            }
        )
        target_sum = solve_request_payload(
            {
                "problem": "Allan brought 3 balloons and 20 balls while Jake brought 5 balloons and 59 balls to the park. How many balloons did Allan and Jake have in the park?",
                "full_pipeline": True,
            }
        )
        earlier = solve_request_payload(
            {
                "problem": "After finding some bottle caps at the park Danny has 32 bottle caps. If he had 25 bottle caps earlier How many bottle caps did he find?",
                "full_pipeline": True,
            }
        )
        self.assertEqual(per_day["answer"], "33")
        self.assertEqual(target_sum["answer"], "8")
        self.assertEqual(earlier["answer"], "7")

    def test_quantity_reasoner_composes_a_typed_rate_chain(self):
        result = solve_quantity_reasoning_problem(
            "A classroom has a whiteboard shared by 4 teachers. "
            "Each teacher has 2 lessons per day. The whiteboard is cleaned "
            "3 times per lesson. How many times is it cleaned in a day?"
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.answer_exact, "24")
        self.assertEqual(result.semantic_model["best_candidate_kind"], "typed_rate_chain")
        self.assertIn("(Rate lesson teacher)", result.semantic_model["best_sequent"])
        self.assertIn("(Rate time lesson)", result.semantic_model["best_sequent"])

    def test_dependency_graph_rejects_an_omitted_connected_mixture_premise(self):
        problem = (
            "I have 10 liters of orange drink that are two-thirds water and add it "
            "to 15 liters of pineapple drink that is three-fifths water. "
            "I spill one liter of the orange drink. How much water is in the mixture?"
        )
        with patch.dict("os.environ", {"MATHOS_REQUIRE_DEPENDENCY_COVERAGE": "0"}):
            baseline = solve_quantity_reasoning_problem(problem)
        self.assertIsNotNone(baseline)
        self.assertTrue(baseline.semantic_model["execution_certificate"])
        candidate = baseline.candidates[0]
        self.assertTrue(candidate["logic"]["connected_unconsumed_premise_ids"])
        with patch.dict("os.environ", {"MATHOS_REQUIRE_DEPENDENCY_COVERAGE": "1"}):
            self.assertIsNone(solve_quantity_reasoning_problem(problem))

    def test_dependency_graph_keeps_a_disconnected_distractor_outside_the_proof(self):
        problem = (
            "Rebecca wants to split eggs into 3 groups. Rebecca has 4 marbles and "
            "15 eggs. How many eggs will each group have?"
        )
        with patch.dict("os.environ", {"MATHOS_REQUIRE_DEPENDENCY_COVERAGE": "1"}):
            result = solve_quantity_reasoning_problem(problem)
        self.assertIsNotNone(result)
        self.assertEqual(result.answer_exact, "5")
        self.assertEqual(
            result.semantic_model["execution_certificate"]["evidence_ids"],
            [2, 0],
        )

    def test_dependency_graph_discharges_bounds_identity_and_common_base(self):
        cases = [
            (
                "There were 12 people on the bus. At the next stop 4 more people got on the bus. "
                "Each bus can not have more than 36 people. How many people are there on the bus now?",
                "16",
            ),
            (
                "Will had 59 pieces of clothing to wash. He put 32 of them in one load, "
                "but split the rest into 9 equal loads. How many pieces could go in each small load?",
                "3",
            ),
            (
                "Juice Box A is 4 dollars. Juice Box B is 5 dollars more than Juice Box A. "
                "Juice Box C is 7 dollars more than Juice Box A. How much more is C than B?",
                "2",
            ),
        ]
        with patch.dict("os.environ", {"MATHOS_REQUIRE_DEPENDENCY_COVERAGE": "1"}):
            for problem, expected in cases:
                with self.subTest(problem=problem):
                    result = solve_quantity_reasoning_problem(problem)
                    self.assertIsNotNone(result)
                    self.assertEqual(result.answer_exact, expected)

    def test_quantity_reasoner_merges_parallel_rate_branches_before_observation(self):
        per_basket = solve_quantity_reasoning_problem(
            "There are 65 baskets of peaches. Each basket has 7 red peaches and 3 green peaches. "
            "How many peaches are in each basket?"
        )
        total = solve_quantity_reasoning_problem(
            "There are 11 baskets of peaches. Each basket has 10 red peaches and 18 green peaches. "
            "How many peaches are in the baskets altogether?"
        )
        self.assertEqual(per_basket.answer_exact, "10")
        self.assertEqual(total.answer_exact, "308")
        self.assertIn("parallel_rate_merge", per_basket.candidates[0]["checks"])

    def test_quantity_reasoner_rejects_partial_rate_program_without_query_certificate(self):
        result = solve_quantity_reasoning_problem(
            "Judy teaches 5 dance classes every weekday and 8 classes on Saturday. "
            "Each class has 15 students and she charges $15 per student. "
            "How much money does she make in one week?"
        )
        self.assertIsNone(result)

    def test_quantity_reasoner_composes_affine_relations_without_name_or_number_templates(self):
        first = solve_quantity_reasoning_problem(
            "Amy made 20 more friends than Lily. Lily made 50 friends. "
            "How many friends do Lily and Amy have together?"
        )
        changed = solve_quantity_reasoning_problem(
            "Nora made 7 more friends than Mei. Mei made 12 friends. "
            "How many friends do Mei and Nora have together?"
        )
        self.assertEqual(first.answer_exact, "120")
        self.assertEqual(changed.answer_exact, "31")
        self.assertEqual(first.semantic_model["best_candidate_kind"], "affine_entity_relation")

    def test_quantity_reasoner_composes_fractional_allocation_and_conservation(self):
        first = solve_quantity_reasoning_problem(
            "Two girls each got 1/6 of the 24 liters of water. Then a boy got 6 liters. "
            "How many liters were left?"
        )
        changed = solve_quantity_reasoning_problem(
            "Three teams each received 1/8 of the 40 boxes. Then a club took 5 boxes. "
            "How many boxes were left?"
        )
        self.assertEqual(first.answer_exact, "10")
        self.assertEqual(changed.answer_exact, "20")
        self.assertEqual(first.semantic_model["best_candidate_kind"], "fractional_each_allocation")

    def test_quantity_reasoner_does_not_treat_dimensions_or_percent_as_counts(self):
        result = solve_quantity_reasoning_problem(
            "Lumber prices rose 50%. There are ten 2 x 4 x 10 boards costing $10 each "
            "and five 4 x 4 x 10 boards costing $16 each. How much profit is made?"
        )
        self.assertIsNone(result)

    def test_quantity_reasoner_handles_unit_price_and_group_inversion(self):
        unit_price = solve_request_payload(
            {
                "problem": "The shop made $51 from selling 3 t-shirt. What is the cost of each t-shirt?",
                "full_pipeline": True,
            }
        )
        boys = solve_request_payload(
            {
                "problem": "Haley has 10 marbles and she gave 5 marbles to each boy. How many boys did she give the marbles to?",
                "full_pipeline": True,
            }
        )
        groups = solve_request_payload(
            {
                "problem": "Rebecca wants to split eggs into 3 groups. Rebecca has 4 marbles and 15 eggs. How many eggs will each group have?",
                "full_pipeline": True,
            }
        )
        self.assertEqual(unit_price["answer"], "17")
        self.assertEqual(boys["answer"], "2")
        self.assertEqual(groups["answer"], "5")

    def test_quantity_reasoner_handles_remaining_goal_forms(self):
        pictures = solve_request_payload(
            {
                "problem": "Nancy took 49 pictures at the zoo and 8 at the museum. If she later deleted 38 of the pictures, how many pictures did she still have?",
                "full_pipeline": True,
            }
        )
        cakes = solve_request_payload(
            {
                "problem": "Baker made 155 cakes. If his friend bought 140 cakes from him How many cakes would baker still have?",
                "full_pipeline": True,
            }
        )
        needed = solve_request_payload(
            {
                "problem": "She needs 125 rocks to complete the border. She has 64 rocks. How many more rocks does she need?",
                "full_pipeline": True,
            }
        )
        self.assertEqual(pictures["answer"], "19")
        self.assertEqual(cakes["answer"], "15")
        self.assertEqual(needed["answer"], "61")

    def test_typed_definition_kernel_covers_core_vocabulary(self):
        surfaces = {surface for entry in LEXICON for surface in entry.surfaces}
        for word in (
            "点",
            "直線",
            "曲線",
            "円",
            "三角形",
            "正三角形",
            "重心",
            "接線",
            "交点",
            "軌跡",
            "領域",
            "面積",
            "最大値",
            "整数",
            "素数",
            "確率",
            "期待値",
            "すべて",
            "存在する",
            "満たす",
            "求めよ",
            "示せ",
            "かつ",
            "ならば",
        ):
            self.assertIn(word, surfaces)

    def test_japanese_case_frame_parser_reads_particles_as_slots(self):
        ir = parse_case_frames(r"任意の整数 n に対して、n^2 が偶数ならば n も偶数であることを示せ。")
        relations = [frame.relation for frame in ir.frames]
        self.assertIn("Forall", relations)
        self.assertIn("Prove", relations)

        locus = parse_case_frames(r"点 P が曲線 C 上にあるとき、P の軌跡を求めよ。")
        logic = [frame.logic for frame in locus.frames]
        self.assertIn("(On \"点 P\" \"曲線 C\")", logic)
        self.assertTrue(any(item.startswith("(Query") for item in logic))

    def test_typed_definition_ir_exposes_case_frames(self):
        ir = compile_typed_definition_ir(r"実数 x が x^2-5*x+6=0 を満たすとき、x を求めよ。")
        self.assertIsNotNone(ir.case_frames)
        self.assertIn("Satisfies", [frame["relation"] for frame in ir.case_frames["frames"]])

    def test_typed_declarations_infer_function_application(self):
        ir = compile_typed_definition_ir(
            r"関数 $f(x),g(x)$ が $\int_0^1 f(x)g(x)dx=1$ を満たすとき一組求めよ。"
        )
        declarations = {item["name"]: item["type"] for item in ir.declarations}
        self.assertEqual(declarations["f"], "Function(Real, Real)")
        self.assertEqual(declarations["g"], "Function(Real, Real)")
        self.assertEqual(declarations["x"], "Real")

    def test_typed_declarations_infer_complex_sequence_from_definition(self):
        text = r"$n$を正の整数とする。複素数平面上の点 $z_n=n+i$ を考える。"
        ir = compile_typed_definition_ir(text)
        declarations = {item["name"]: item["type"] for item in ir.declarations}
        self.assertEqual(declarations["n"], "Integer")
        self.assertEqual(declarations["z_n"], "Sequence(Complex)")

        graph = compile_typed_semantic_graph(text, typed_definition_ir=ir.to_dict())
        objects = {item.name: item.sort for item in graph.objects}
        self.assertEqual(objects["z_n"], "Sequence(Complex)")
        self.assertTrue(any(item.name == "Complex" for item in graph.sorts))

    def test_proof_representation_changes_compile_as_typed_morphisms(self):
        text = (
            r"$x=y-a/3$ とおく。$g'(y)$ の符号から単調増加を示す。"
            r"判別式を調べ、共役な根を得る。係数比較により条件を求める。"
        )
        graph = compile_typed_semantic_graph(text)
        names = {item.name for item in graph.morphisms}
        self.assertTrue(
            {
                "PolynomialTranslation",
                "Differentiation",
                "MonotonicityTest",
                "Discriminant",
                "ComplexConjugation",
                "CoefficientComparison",
            }
            <= names
        )

    def test_typed_definition_kernel_generalizes_regular_polygon(self):
        ir = compile_typed_definition_ir(
            r"$\text{曲線 }$y=x^3−2x"
            r"$\text{ 上の3点を頂点とする正三角形の重心の軌跡が囲む部分の面積を求めよ }$"
        )
        self.assertEqual(ir.status, "type_checked")
        self.assertIn("RegularPolygon", [entry["canonical"] for entry in ir.definitions_used])
        self.assertIn({"name": "P", "type": "Fin(3) -> Point2"}, ir.declarations)
        self.assertEqual(ir.query["kind"], "compute")
        self.assertIn("Area(BoundedRegion(Locus", ir.query["expression"])
        self.assertIn("real_closed_fields", [item["theory"] for item in ir.backend_obligations])

    def test_typed_definition_kernel_does_not_promote_japanese_particles_to_logic(self):
        maximum = compile_typed_definition_ir(
            "正十二面体から3点を取るとき、三角形の面積の最大値を求めよ。"
        )
        sine = compile_typed_definition_ir(r"$\sin x=0$ を満たす実数を求めよ。")
        assertion = compile_typed_definition_ir("nは整数である。")

        maximum_names = {entry["canonical"] for entry in maximum.definitions_used}
        sine_names = {entry["canonical"] for entry in sine.definitions_used}
        assertion_names = {entry["canonical"] for entry in assertion.definitions_used}
        self.assertNotIn("Decide", maximum_names)
        self.assertEqual(maximum.query["target"], "maximum")
        self.assertNotIn("Member", sine_names)
        self.assertNotIn("Exists", assertion_names)

    def test_typed_definition_kernel_has_first_class_measure_and_limit_queries(self):
        limit_ir = compile_typed_definition_ir(r"$\lim_{n\to\infty} a_n$ を求めよ。")
        volume_ir = compile_typed_definition_ir("立体Kの体積を求めよ。")
        correlation_ir = compile_typed_definition_ir("確率変数X,Yの相関係数を求めよ。")

        self.assertEqual(limit_ir.query["expression"], "Limit(target)")
        self.assertEqual(volume_ir.query["expression"], "Volume(target_region)")
        self.assertEqual(correlation_ir.query["expression"], "Correlation(X,Y)")

    def test_typed_definition_kernel_types_finite_english_query_forms(self):
        cases = (
            ("How many integer solutions are there?", "count", "Integer"),
            ("What percentage of the students enrolled?", "measure", "Real"),
            (r"Evaluate $i^5+i^{-25}+i^{45}$.", "compute_or_characterize", "Real"),
            ("Which of the following vectors are possible?", "select", "Set"),
            ('Enter "odd", "even", or "neither".', "classify", "Fin"),
            ("What was the original price?", "compute_or_characterize", "Real"),
        )
        for text, kind, target_type in cases:
            with self.subTest(text=text):
                ir = compile_typed_definition_ir(text)
                self.assertEqual(ir.status, "type_checked")
                self.assertEqual(ir.query["kind"], kind)
                self.assertEqual(ir.query["target_type"], target_type)
                self.assertTrue(ir.query["target"])

    def test_mixed_prose_preserves_currency_and_percentages(self):
        text = (
            "Choose between jewelry worth $5,000 or gadgets worth $8,000. "
            "The markets rise 2.5% and 1.2%. How much profit is possible?"
        )
        ir = compile_typed_definition_ir(text)
        self.assertIn("2.5%", ir.normalized_text)
        self.assertIn("How much profit", ir.normalized_text)
        self.assertEqual(ir.query["kind"], "measure")
        self.assertEqual(ir.status, "type_checked")

    def test_typed_operators_execute_without_problem_family_templates(self):
        cases = (
            (r"Compute $23^{-1}\pmod{101}$.", "22", "ModularInverse"),
            (
                "During a survey the following counts were recorded: "
                "12 red, 18 blue, 24 green. What is their mean?",
                "18",
                "FiniteMean",
            ),
            (
                "A shop bought 2 dozen rolls which cost $7 per dozen, "
                "and 3 dozen cakes for $11 per dozen. How much was the total cost?",
                "47",
                "UnitRateSum",
            ),
        )
        for text, expected, operator in cases:
            with self.subTest(text=text):
                result = detect_arithmetic_nl_problem(text)
                self.assertIsNotNone(result)
                self.assertEqual(result.answer_exact, expected)
                self.assertEqual(result.metadata["operator"], operator)

    def test_symbolic_query_root_sum_allows_domain_adjectives(self):
        result = run_reasoning_pipeline(
            r"Find the sum of all complex roots of $\frac{1}{x-2}+\frac{1}{x-7}=1$."
        )
        answer = extract_answer_from_pipeline_data(json.loads(result.to_json()))
        self.assertEqual(answer, "11")

    def test_new_backend_contracts_generalize_to_changed_parameters(self):
        cases = (
            (
                "When rolling a certain unfair 4-sided die, the probability of a distinguished face F "
                "is greater than 1/4, the probability of the opposite face is less than 1/4, and the "
                "probability of each of the other faces is 1/4. Opposite faces sum to 5. When two such "
                "dice are rolled, the probability of obtaining a sum of 5 is 17/72. If P(F)=m/n in "
                "relatively prime integers, find m+n.",
                "4",
            ),
            (
                r"Let $M_n$ be tridiagonal with $m_{i,i}=5$ and "
                r"$m_{i+1,i}=m_{i,i+1}=2$; all other entries are zero. "
                r"Let $D_n$ be its determinant. Find $\sum_{n=1}^{\infty}\frac{1}{3D_n+1}$.",
                "1/12",
            ),
            (
                r"In triangle $\triangle XYZ$, $XY=XZ$ and $XH$ is an altitude. "
                r"Point $P$ is a point on $XZ$ and $XY\parallel HP$. "
                r"The area of $\triangle XYZ$ is 80. What is the area of $XYHP$?",
                "60",
            ),
            (
                "A car moves at uniform speed towards a tower. The angle of elevation changes "
                "from 30 degrees to 45 degrees in 6 minutes. How much more time is required?",
                "3 + 3*sqrt(3)",
            ),
        )
        for text, expected in cases:
            with self.subTest(text=text):
                result = run_reasoning_pipeline(text)
                answer = extract_answer_from_pipeline_data(json.loads(result.to_json()))
                self.assertTrue(answers_match(answer, expected), (answer, expected))

    def test_asymptote_coordinate_backend_uses_constructed_points(self):
        text = r"""
        [asy]
        pair A=(0,0); pair B=(4,0); pair C=(1,3);
        [/asy]
        What is the area of $\triangle ABC$?
        """
        result = run_reasoning_pipeline(text)
        answer = extract_answer_from_pipeline_data(json.loads(result.to_json()))
        self.assertEqual(answer, "6")

    def test_correlation_is_compiled_through_centered_inner_product(self):
        ir = compile_typed_definition_ir(
            "確率変数X,Yの共分散と相関係数を求めよ。"
        )
        names = {item["canonical"] for item in ir.definitions_used}
        self.assertTrue(
            {
                "Center",
                "Covariance",
                "InnerProduct",
                "Norm",
                "NormalizedInnerProduct",
                "Correlation",
            }
            <= names
        )

    def test_inner_product_structures_receive_specific_lift_certificates(self):
        examples = {
            (
                "行列A,Bのフロベニウス内積を求めよ。",
                "linear_algebra.frobenius_pairing",
            ),
            (
                "実内積空間でベクトルvの部分空間Sへの直交射影を求めよ。",
                "linear_algebra.orthogonal_projection",
            ),
            (
                "正定値行列Qによる二次形式の最小値を求めよ。",
                "optimization.positive_definite_quadratic",
            ),
            (
                "正規化内積のnから無限大における極限を求めよ。",
                "real_analysis.normalized_inner_product_limit",
            ),
            (
                "弱定常過程Xの相関関数を求めよ。",
                "probability.autocorrelation_function",
            ),
        }
        for text, expected in examples:
            typed = compile_typed_definition_ir(text)
            graph = compile_typed_semantic_graph(
                text,
                typed_definition_ir=typed.to_dict(),
            )
            ids = {
                item.family_id
                for item in graph.lift_certificates
                if item.admissible
            }
            self.assertIn(expected, ids)

    def test_category_semantic_graph_lifts_quantity_observables(self):
        text = "Jake brought 6 balloons. Jake then bought 3 more balloons. How many balloons did Jake bring?"
        graph = compile_typed_semantic_graph(text)
        self.assertEqual(graph.status, "type_checked")
        self.assertIn("Observable", [sort.name for sort in graph.sorts])
        self.assertIn("Count[balloon]", [sort.name for sort in graph.sorts])
        self.assertTrue(any(morphism.kind == "observable" for morphism in graph.morphisms))
        self.assertTrue(any(query.sort == "Count[balloon]" for query in graph.queries))
        gate = run_verifier_gate(graph, answer="9")
        self.assertEqual(gate.status, "accepted")
        self.assertIn("morphism_sorts_resolved", gate.checks)

    def test_pure_tex_math_does_not_create_spurious_quantity_observables(self):
        graph = compile_typed_semantic_graph(
            r"$\displaystyle\lim_{n\to\infty}\frac{1}{n}=0$ を示せ。"
        )
        morphism_names = {morphism.name for morphism in graph.morphisms}

        self.assertNotIn("observe_dollar", morphism_names)
        self.assertNotIn("observe_frac", morphism_names)
        self.assertNotIn("observe_n", morphism_names)
        self.assertFalse(any(name.startswith("observe_") for name in morphism_names))

        japanese_tex = compile_typed_semantic_graph(
            r"1から$n$までのカードが1枚ずつあり、2枚を引くときの相関係数を求めよ。"
        )
        japanese_names = {morphism.name for morphism in japanese_tex.morphisms}
        self.assertNotIn("observe_n", japanese_names)
        self.assertNotIn("observe_quantity", japanese_names)

    def test_category_semantic_graph_lifts_geometry_as_objects_and_morphisms(self):
        text = r"$\text{曲線 }$y=x^3−2x$\text{ 上の3点を頂点とする正三角形の重心の軌跡が囲む部分の面積を求めよ }$"
        typed = compile_typed_definition_ir(text)
        formal = compile_formal_ir(text)
        graph = compile_typed_semantic_graph(
            text,
            typed_definition_ir=typed.to_dict(),
            formal_ir=formal.to_dict(),
        )
        morphism_names = {morphism.name for morphism in graph.morphisms}
        self.assertIn("RegularPolygon", morphism_names)
        self.assertIn("Centroid", morphism_names)
        self.assertIn("Area", morphism_names)
        self.assertTrue(any(query.kind == "compute" for query in graph.queries))
        self.assertTrue(any("Centroid" in constraint.expression for constraint in graph.constraints))
        certificate_ids = {item.family_id for item in graph.lift_certificates if item.admissible}
        self.assertIn("measure_geometry.locus_area", certificate_ids)

    def test_category_semantic_graph_certifies_abstract_limit_and_prime_queries(self):
        limit_text = r"$\lim_{n\to\infty} a_n$ を求めよ。"
        limit_typed = compile_typed_definition_ir(limit_text)
        limit_graph = compile_typed_semantic_graph(
            limit_text,
            typed_definition_ir=limit_typed.to_dict(),
        )
        prime_text = "素数p,qについて条件を満たす組をすべて求めよ。"
        prime_typed = compile_typed_definition_ir(prime_text)
        prime_graph = compile_typed_semantic_graph(
            prime_text,
            typed_definition_ir=prime_typed.to_dict(),
        )

        limit_ids = {item.family_id for item in limit_graph.lift_certificates if item.admissible}
        prime_ids = {item.family_id for item in prime_graph.lift_certificates if item.admissible}
        self.assertIn("real_analysis.limit_observable", limit_ids)
        self.assertIn("elementary_number_theory.prime_constraint_query", prime_ids)

    def test_full_pipeline_exposes_typed_definition_ir(self):
        result = solve_request_payload(
            {
                "problem": r"素数 p に対して p>1 を示せ。",
                "full_pipeline": True,
            }
        )
        self.assertTrue(result["ok"])
        typed_ir = result["data"]["typed_definition_ir"]
        self.assertIn("Prime", [entry["canonical"] for entry in typed_ir["definitions_used"]])
        self.assertIn("Prove", [entry["canonical"] for entry in typed_ir["definitions_used"]])
        self.assertIn("TypedKernel:", result["reply"])
        self.assertIn("semantic_graph", result["data"])
        self.assertIn("constraint_ir", result["data"])
        self.assertIn("verifier_gate", result["data"])
        self.assertIn("SemanticGraph:", result["reply"])
        self.assertIn("VerifierGate:", result["reply"])

    def test_rejected_verifier_gate_blocks_answer_extraction(self):
        data = {
            "verifier_gate": {"status": "rejected", "rejection": "bad semantic sort"},
            "tool_execution": {
                "tool_calls": [
                    {
                        "name": "mock.solver",
                        "status": "executed",
                        "result": {"answer_exact": "999"},
                    }
                ]
            },
        }
        self.assertIsNone(extract_answer_from_pipeline_data(data))

    def test_domain_registry_classifies_broad_domains(self):
        registry = DomainRegistry()
        self.assertEqual(registry.analyze("素数 p に対して a^p ≡ a mod p を示せ。").domain, "number_theory")
        self.assertEqual(registry.analyze("グラフ G の頂点彩色数を求めよ。").domain, "graph_theory")
        self.assertEqual(registry.analyze("サイコロを2回振るとき和が7になる確率を求めよ。").domain, "probability")

    def test_domain_registry_normalizes_japanese_query_vocabulary(self):
        registry = DomainRegistry()
        region = registry.analyze("点Pが動くとき円の通過領域を求めよ。")
        locus = registry.analyze("点Hの軌跡を求めよ。")
        proof = registry.analyze("素数pについて合同式を示せ。")

        self.assertEqual(region.operation, "passing_region")
        self.assertEqual(locus.operation, "locus")
        self.assertEqual(proof.domain, "number_theory")
        self.assertNotEqual(proof.domain, "inequalities")

    def test_domain_benchmark_accuracy(self):
        result = run_domain_benchmark()
        self.assertGreaterEqual(result["accuracy"], 0.9)
        self.assertEqual(result["total"], 18)

    def test_full_pipeline_includes_domain_ir_for_unregistered_problem(self):
        result = run_reasoning_pipeline("サイコロを2回振るとき和が7になる確率を求めよ。")
        self.assertEqual(result.domain_ir["domain"], "probability")
        self.assertEqual(result.parser["domain"], "probability")
        self.assertIn("probability_domain_plan", [item["name"] for item in result.strategies])
        self.assertEqual(result.verification["status"], "partial")
        self.assertTrue(result.parser["cold_mode"])
        self.assertIn("structural_ir", result.to_json())

    def test_cold_mode_does_not_use_specialized_benchmark_adapter(self):
        text = r"$m$週間と$n!$秒が等しくなる非負整数の組($m,n$)をすべて求めよ."
        result = solve_request_payload({"problem": text, "full_pipeline": True})
        self.assertTrue(result["ok"])
        self.assertTrue(result["data"]["parser"]["cold_mode"])
        self.assertNotEqual(
            result["data"]["tool_execution"]["tool_calls"][0]["name"] if result["data"]["tool_execution"]["tool_calls"] else "",
            "number_theory.factorial_weeks",
        )

    def test_structural_parser_and_math_search_emit_generic_experiments(self):
        structure = analyze_structure("正の整数 n について n^2 = 9 を満たすものをすべて求めよ。")
        search = run_math_search(structure, external_tools=False)
        action_names = [action["name"] for action in search.actions]
        self.assertIn("generic_wolfram_experiment", action_names)
        self.assertIn("integer_model_search", structure.tool_affordances)
        self.assertEqual(search.answer, "['3']")

    def test_full_pipeline_returns_solution_graph_from_generic_search(self):
        result = solve_request_payload({"problem": "正の整数 n について n^2 = 9 を満たすものをすべて求めよ。", "full_pipeline": True})
        self.assertTrue(result["ok"])
        self.assertEqual(result["answer"], "['3']")
        self.assertEqual(result["data"]["solution_graph"]["status"], "verified_candidate")
        self.assertIn("formal_ir", result["data"])

    def test_generic_math_search_evaluates_expression_under_constraints(self):
        result = solve_request_payload(
            {
                "problem": r"実数 $x,y$ が $x+y=5$ かつ $xy=6$ を満たすとき、$x^2+y^2$ を求めよ。",
                "full_pipeline": True,
            }
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["answer"], "13")
        action_names = [action["name"] for action in result["data"]["math_search"]["actions"]]
        self.assertIn("generic_sympy_value_from_constraints", action_names)

    def test_generic_counterexample_respects_assumptions(self):
        result = solve_request_payload({"problem": "x>0 のとき x^2 < x を示せ。", "full_pipeline": True})
        self.assertTrue(result["ok"])
        self.assertEqual(result["answer"], "{'x': 1}")

    def test_generic_quadratic_existence_range(self):
        result = solve_request_payload(
            {
                "problem": r"実数 $x$ が $x^2-a*x+1=0$ を満たすような実数 $a$ の範囲を求めよ。",
                "full_pipeline": True,
            }
        )
        self.assertTrue(result["ok"])
        self.assertIn("a <= -2", result["answer"])
        self.assertIn("2 <= a", result["answer"])

    def test_generic_tex_limit_integral_and_factor(self):
        limit_result = solve_request_payload(
            {"problem": r"$\lim_{x\to0} \frac{\sin x}{x}$ を求めよ。", "full_pipeline": True}
        )
        integral_result = solve_request_payload(
            {"problem": r"$\int_0^1 x^2 dx$ を求めよ。", "full_pipeline": True}
        )
        factor_result = solve_request_payload(
            {"problem": r"$x^2+2x+1$ を因数分解せよ。", "full_pipeline": True}
        )
        self.assertEqual(limit_result["answer"], "1")
        self.assertEqual(integral_result["answer"], "1/3")
        self.assertEqual(factor_result["answer"], "(x + 1)**2")

    def test_generic_limit_rejects_an_unelaborated_sequence_target(self):
        result = solve_request_payload(
            {
                "problem": (
                    r"1から$n$までのカードから2枚を引く。相加平均と相乗平均を"
                    r"$X_n,Y_n$ とし、その相関係数を $\rho_n$ とする。"
                    r"$\lim_{n\to\infty}\rho_n$ を求めよ。"
                ),
                "full_pipeline": True,
                "allow_theorem_kernels": False,
            }
        )

        self.assertIsNone(result["answer"])
        limit_action = next(
            action
            for action in result["data"]["math_search"]["actions"]
            if action["name"] == "generic_sympy_limit"
        )
        self.assertEqual(limit_action["result"]["status"], "not_applicable")
        self.assertNotEqual(limit_action["result"].get("answer_exact"), "を求めよ。")

    def test_factorization_proof_clause_is_not_an_imperative_factor_query(self):
        problem = r"""
        $f(x)-1=2^{p-1}(x-1)\{P(x)\}^2$ と因数分解できることを示せ。
        さらに $|P'(\alpha)|$ を $p$ のみで表せ。
        """
        self.assertIsNone(compile_symbolic_query(problem))

    def test_defined_expression_with_unbound_coefficients_is_rejected(self):
        problem = r"""
        $S=g(S)$ とし、
        $g(S)=C_0+C_1/S+C_2/S^2+C_3/S^3+C_4/S^4$
        の定数項 $C_0$ の値を求めよ。
        """
        compiled = compile_symbolic_query(problem)
        self.assertIsNotNone(compiled)
        with self.assertRaisesRegex(ValueError, "unbound symbols"):
            execute_symbolic_query(compiled.to_dict())

    def test_prime_triangle_goal_is_retained_as_typed_constraints(self):
        compiled = compile_typed_definition_ir(
            "三辺が全て素数である三角形の外接円半径は無理数であることを示せ。"
        )
        definitions = {entry["canonical"] for entry in compiled.definitions_used}
        formulas = {entry["formula"] for entry in compiled.predicates}
        self.assertTrue({"EdgeLength", "Circumradius", "Irrational", "Prime"} <= definitions)
        self.assertIn("forall i:Fin(3), Prime(EdgeLength(P,i))", formulas)
        self.assertEqual(compiled.query["expression"], "Irrational(Circumradius(P))")
        self.assertNotIn("(query prove goal)", compiled.logic)

    def test_integer_geometry_search_enumerates_the_typed_shape(self):
        compiled = compile_typed_definition_ir(
            "三辺の長さが素数で、外接円半径と内接円半径の積も素数となる整数三角形を全て求めよ。"
        )
        formulas = {entry["formula"] for entry in compiled.predicates}
        self.assertIn("forall i:Fin(3), Prime(EdgeLength(P,i))", formulas)
        self.assertIn("Prime(Circumradius(P) * Inradius(P))", formulas)
        self.assertEqual(compiled.query["kind"], "enumerate")
        self.assertEqual(compiled.query["target"], "P")

    def test_generic_linear_system_derivative_and_dice_probability(self):
        system_result = solve_request_payload(
            {"problem": r"連立方程式 $x+y=5$, $x-y=1$ を解け。", "full_pipeline": True}
        )
        derivative_result = solve_request_payload(
            {"problem": r"$x^3+2x$ を $x$ で微分せよ。", "full_pipeline": True}
        )
        probability_result = solve_request_payload(
            {"problem": "サイコロを2回振るとき和が7になる確率を求めよ。", "full_pipeline": True}
        )
        self.assertIn("'x': '3'", system_result["answer"])
        self.assertIn("'y': '2'", system_result["answer"])
        self.assertEqual(derivative_result["answer"], "3*x**2 + 2")
        self.assertEqual(probability_result["answer"], "1/6")

    def test_generic_matrix_combinatorics_optimization_complex_and_remainder(self):
        determinant_result = solve_request_payload(
            {"problem": "行列 [[1,2],[3,4]] の行列式を求めよ。", "full_pipeline": True}
        )
        combination_result = solve_request_payload(
            {"problem": "5人から2人を選ぶ方法は何通りか。", "full_pipeline": True}
        )
        minimum_result = solve_request_payload(
            {"problem": r"実数 $x$ に対して $x^2-4*x+5$ の最小値を求めよ。", "full_pipeline": True}
        )
        complex_result = solve_request_payload(
            {"problem": r"複素数 $z=3+4i$ の絶対値を求めよ。", "full_pipeline": True}
        )
        remainder_result = solve_request_payload(
            {"problem": r"$2^10$ を $7$ で割った余りを求めよ。", "full_pipeline": True}
        )
        trig_result = solve_request_payload(
            {"problem": r"$\sin x=0$ を解け。", "full_pipeline": True}
        )
        self.assertEqual(determinant_result["answer"], "-2")
        self.assertEqual(combination_result["answer"], "10")
        self.assertEqual(minimum_result["answer"], "1")
        self.assertEqual(complex_result["answer"], "5")
        self.assertEqual(remainder_result["answer"], "2")
        self.assertEqual(trig_result["answer"], "['0', 'pi']")

    def test_long_japanese_logic_and_formal_ir(self):
        value_result = solve_request_payload(
            {
                "problem": "実数 x,y は、和が 5 で積が 6 である。さらに x<y とする。このとき x^2+y^2 の値を求めよ。",
                "full_pipeline": True,
            }
        )
        chain_result = solve_request_payload(
            {"problem": r"実数 x が $0<x<1$ を満たすとき、$x^2<x$ を示せ。", "full_pipeline": True}
        )
        condition_result = solve_request_payload(
            {
                "problem": r"実数 a について、すべての実数 x に対して $x^2+a*x+1>0$ が成り立つための a の必要十分条件を求めよ。",
                "full_pipeline": True,
            }
        )
        region_result = solve_request_payload(
            {
                "problem": r"t を実数全体にわたって動かす。各 t に対して曲線 C_t: $y=t*x-t^2$ を考える。このとき、少なくとも一つの t に対して点 (x,y) が C_t 上にあるような点全体の領域を求めよ。",
                "full_pipeline": True,
            }
        )
        predicate_formal = compile_formal_ir("正の整数 n について、n^2 が偶数ならば n も偶数であることを示せ。")
        predicate_result = solve_request_payload(
            {"problem": "正の整数 n について、n^2 が偶数ならば n も偶数であることを示せ。", "full_pipeline": True}
        )
        self.assertEqual(value_result["answer"], "13")
        self.assertEqual(chain_result["answer"], "proved")
        self.assertEqual(condition_result["answer"], "(-2 < a) & (a < 2)")
        self.assertEqual(region_result["answer"], "y <= x**2/4")
        self.assertEqual(predicate_result["answer"], "proved")
        self.assertIn("(exists ((t Real))", region_result["data"]["formal_ir"]["goal"])
        self.assertIn("(implies (even (^ n 2)) (even n))", predicate_formal.goal)
        action_names = [action["name"] for action in predicate_result["data"]["math_search"]["actions"]]
        self.assertIn("generic_modular_parity_proof", action_names)

    def test_formal_ir_value_problem(self):
        formal = compile_formal_ir(r"実数 $x,y$ が $x+y=5$ かつ $xy=6$ を満たすとき、$x^2+y^2$ を求めよ。")
        self.assertEqual(formal.status, "type_checked")
        self.assertIn("(declare x Real)", formal.sexpr)
        self.assertIn("(meta a Real)", formal.sexpr)
        self.assertIn("(= a (+ (^ x 2) (^ y 2)))", formal.sexpr)

    def test_formal_ir_all_solutions_problem(self):
        formal = compile_formal_ir(r"方程式 $x^2-5*x+6=0$ を満たす実数 $x$ をすべて求めよ。")
        self.assertEqual(formal.status, "type_checked")
        self.assertIn("(meta S (Set Real))", formal.sexpr)
        self.assertIn("(iff (member x S)", formal.sexpr)

    def test_formal_ir_existence_range_problem(self):
        formal = compile_formal_ir(r"実数 $x$ が $x^2-a*x+1=0$ を満たすような実数 $a$ の範囲を求めよ。")
        self.assertEqual(formal.status, "type_checked")
        self.assertIn("(meta S (Set Real))", formal.sexpr)
        self.assertIn("(exists ((x Real))", formal.sexpr)

    def test_formal_ir_does_not_evaluate_large_factorial(self):
        formal = compile_formal_ir(r"$2025!-1$は素数か。")
        self.assertIn("(factorial 2025)", formal.sexpr)

    def test_tex_input_scanner_splits_math_modes(self):
        text, spans = split_tex_text_math(r"価格は \$5。式は $x^2+1$ と \(y=\frac{1}{x+1}\)。")
        self.assertEqual(len(spans), 2)
        self.assertIn(r"\$5", text)
        self.assertIn("x**2+1", text)
        self.assertIn("y=((1)/(x+1))", text)

    def test_latex_frontend_uses_scanner_for_display_math(self):
        parsed = parse_latex_problem(r"求めよ \[ \frac{x^2-1}{x-1} \] ただし $x\ne1$.")
        self.assertIn("((x**2-1)/(x-1))", parsed.normalized_text)
        self.assertIn("x!=1", parsed.normalized_text)
        self.assertEqual(len(parsed.math_segments), 2)

    def test_bare_latex_spacing_command_does_not_split_a_fraction(self):
        parsed = parse_latex_problem(
            r"\frac{\int_{0}^{1} f(x)g(x)\,dx}"
            r"{\sqrt{\int_{0}^{1} f(x)^2\,dx}\sqrt{\int_{0}^{1} g(x)^2\,dx}}"
            r"=\cos\frac{\pi}{6} を満たす関数を一組求めよ。"
        )

        self.assertEqual(len(parsed.math_segments), 1)
        self.assertIn("integral _0**(1) f*(x)*g*(x) dx", parsed.math_segments[0])
        self.assertIn("=cos((pi)/(6))", parsed.math_segments[0])

    def test_latex_text_macro_style_problem_solves(self):
        problem = (
            r"$\text{実数 }x,y\text{ が }x+y=5\text{ かつ }xy=6"
            r"\text{ を満たすとき、}x^2+y^2\text{ を求めよ。}$"
        )
        parsed = parse_latex_problem(problem)
        self.assertIn("実数 x,y", parsed.normalized_text)
        self.assertIn("x**2+y**2", parsed.normalized_text)
        result = solve_request_payload({"problem": problem, "full_pipeline": True})
        self.assertEqual(result["answer"], "13")

    def test_equilateral_triangle_centroid_locus_area_compiles_to_constraints(self):
        problem = (
            r"$\text{曲線 }$y=x^3−2x"
            r"$\text{ 上の3点を頂点とする正三角形の重心の軌跡が囲む部分の面積を求めよ }$"
        )
        result = solve_request_payload({"problem": problem, "full_pipeline": True})
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["parser"]["intent"], "latex_to_equilateral_triangle_centroid_locus_area")
        self.assertIsNone(result["answer"])
        self.assertEqual(result["data"]["math_search"]["answer"], None)
        self.assertNotIn("sympy.envelope", [call["name"] for call in result["data"]["tool_execution"]["tool_calls"]])
        tool_call = result["data"]["tool_execution"]["tool_calls"][0]
        self.assertEqual(tool_call["name"], "geometry.constraint_ir")
        self.assertEqual(tool_call["result"]["status"], "formalized")
        self.assertTrue(tool_call["result"]["no_memorized_answer"])
        self.assertIn("PointOnCurve", [constraint["type"] for constraint in tool_call["result"]["constraints"]])
        self.assertIn("Equilateral", [constraint["type"] for constraint in tool_call["result"]["constraints"]])
        self.assertEqual(tool_call["result"]["query"]["type"], "AreaOfBoundedLocus")
        self.assertEqual(result["data"]["formal_ir"]["metas"][0]["name"], "A")
        self.assertIn("geometry_constraint_compilation", [strategy["name"] for strategy in result["data"]["strategies"]])

    def test_equilateral_triangle_centroid_locus_coeff_change_uses_same_ir(self):
        problem = (
            r"$\text{曲線 }$y=x^3−3x"
            r"$\text{ 上の3点を頂点とする正三角形の重心の軌跡が囲む部分の面積を求めよ }$"
        )
        result = solve_request_payload({"problem": problem, "full_pipeline": True})
        self.assertTrue(result["ok"])
        self.assertIsNone(result["answer"])
        tool_call = result["data"]["tool_execution"]["tool_calls"][0]
        self.assertEqual(tool_call["name"], "geometry.constraint_ir")
        self.assertEqual(tool_call["result"]["status"], "formalized")
        self.assertEqual(tool_call["result"]["objects"][0]["equation"], "y = x**3-3*x")
        self.assertEqual(tool_call["result"]["query"]["type"], "AreaOfBoundedLocus")

    def test_web_solution_url_parser(self):
        url = "https://math.stackexchange.com/questions/1234567/example-title"
        self.assertEqual(extract_stackexchange_question_id(url), 1234567)

    def test_solution_step_parser_and_verifier(self):
        text = "Assume x is real. We have x^2 + 2*x + 1 = (x+1)^2. Therefore the expressions are equal."
        parsed = SolutionStepParser().parse_answer(text, source_url="memory://test", answer_id=1)
        self.assertTrue(parsed.steps)
        verified = StepVerifier(external_tools=False).verify_solution(parsed)
        self.assertGreaterEqual(verified.total_steps, 1)
        self.assertGreaterEqual(verified.verified_steps, 1)

    def test_query_builder_for_container_problem(self):
        text = r"平面上に一辺$\sqrt3$の正方形を固定する.一辺$\sqrt2+\sqrt6$の正三角形を, この正方形を含むように自由に動かすとき, 正三角形の通過領域の面積を求めよ."
        queries = QueryBuilder().build(text)
        self.assertIn("moving equilateral triangle contains square swept area", queries)

    def test_hybrid_retriever_offline(self):
        text = "曲線 y = t*x - t^2 の包絡線を求めよ。"
        result = HybridRetriever(live_search=False).retrieve(text, {"intent": "geometry_nl_to_dsl_envelope"})
        self.assertTrue(result["hits"])
        self.assertFalse(result["live_search"])

    def test_full_reasoning_pipeline_container_problem(self):
        text = r"平面上に一辺$\sqrt3$の正方形を固定する.一辺$\sqrt2+\sqrt6$の正三角形を, この正方形を含むように自由に動かすとき, 正三角形の通過領域の面積を求めよ."
        result = run_reasoning_pipeline(text)
        self.assertEqual(result.parser["intent"], "latex_to_container_square_in_equilateral_triangle_sweep")
        self.assertTrue(result.memory_retrieval["hits"])
        self.assertEqual(result.verification["status"], "verified")
        self.assertIn("Answer:", result.explanation)

    def test_web_app_rejects_empty_problem(self):
        result = solve_request_payload({"problem": ""})
        self.assertFalse(result["ok"])
        self.assertIn("問題文", result["error"])

    def test_web_app_replies_to_problem(self):
        text = r"平面上に一辺$\sqrt3$の正方形を固定する.一辺$\sqrt2+\sqrt6$の正三角形を, この正方形を含むように自由に動かすとき, 正三角形の通過領域の面積を求めよ."
        result = solve_request_payload({"problem": text, "full_pipeline": True})
        self.assertTrue(result["ok"])
        self.assertEqual(result["mode"], "full_pipeline")
        self.assertIn("Answer:", result["reply"])
        self.assertIn("data", result)

    def test_web_app_extracts_non_geometry_answers(self):
        algebra = solve_request_payload({"problem": "solve x^2 - 5*x + 6 = 0 for x", "full_pipeline": True})
        calculus = solve_request_payload({"problem": "derivative x^3 + 2*x with respect to x", "full_pipeline": True})
        convex = solve_request_payload(
            {
                "problem": "Minkowski sum [(0,0),(1,0),(1,1),(0,1)] + [(0,0),(2,0),(0,1)]",
                "full_pipeline": True,
            }
        )
        self.assertEqual(algebra["answer"], "['2', '3']")
        self.assertEqual(calculus["answer"], "3*x**2 + 2")
        self.assertIn("[3, 1]", convex["answer"])

    def test_polynomial_remainder_problem(self):
        ir = run_pipeline(r"$x^30$を$(x-1)^2$で割った余りを求めよ。")
        self.assertEqual(ir.intent, "latex_to_polynomial_remainder")
        self.assertEqual(ir.tool_calls[0].result["remainder"], "30*x - 29")
        result = solve_request_payload({"problem": r"$x^30$を$(x-1)^2$で割った余りを求めよ。", "full_pipeline": True})
        self.assertEqual(result["answer"], "30*x - 29")

    def test_japanese_polynomial_equation_pipeline(self):
        result = solve_request_payload({"problem": r"$x^3-6*x^2+11*x-6=0$ を解け。", "full_pipeline": True})
        self.assertTrue(result["ok"])
        self.assertEqual(result["answer"], "['1', '2', '3']")

    def test_number_theory_factorial_weeks_adapter(self):
        result = solve_request_payload(
            {
                "problem": r"$m$週間と$n!$秒が等しくなる非負整数の組($m,n$)をすべて求めよ.",
                "full_pipeline": True,
                "allow_specialized": True,
            }
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["answer"], "n >= 10, m = n!/604800")
        self.assertEqual(result["data"]["tool_execution"]["tool_calls"][0]["name"], "number_theory.factorial_weeks")

    def test_coordinate_geometry_circle_overlap_limit_adapter(self):
        text = (
            r"半径$n$の2円の中心間距離が $n+\frac12,\sqrt{n(n+1)}$のときの共通部分の面積を "
            r"$S_n,T_n$ とする. $\lim_{n\to\infty}(S_n-T_n)$ を求めよ."
        )
        result = solve_request_payload({"problem": text, "full_pipeline": True, "allow_specialized": True})
        self.assertTrue(result["ok"])
        self.assertEqual(result["answer"], "-sqrt(3)/8")
        self.assertEqual(result["data"]["tool_execution"]["tool_calls"][0]["name"], "geometry.circle_overlap_limit")

    def test_probability_two_card_correlation_adapter(self):
        text = (
            r"1から$n$までの自然数が書かれたカードが1枚ずつあり，2枚を同時に引いたカードの値の"
            r"相加平均，相乗平均を $X_n,Y_n$ とする．また，$X_n,Y_n$ の相関係数を $\rho_n$ とする．"
            r"$\lim_{n\to\infty}\rho_n$ を求めよ．"
        )
        result = solve_request_payload({"problem": text, "full_pipeline": True, "allow_specialized": True})
        self.assertTrue(result["ok"])
        self.assertEqual(result["answer"], "8*sqrt(6)/(5*sqrt(17))")
        self.assertEqual(result["data"]["tool_execution"]["tool_calls"][0]["name"], "probability.two_card_correlation_limit")

    def test_probability_k_card_angle_adapter(self):
        text = (
            r"1から$n$までの自然数が書かれたカードが1枚ずつあり，$k(<n)$枚を同時に引き，"
            r"その相加平均，相乗平均を$X_{n,k},Y_{n,k}$とし，$X_{n,k}$と$Y_{n,k}$の相関係数を"
            r"$\cos\theta_{n,k}$とする. $\lim_{k\to\infty}\lim_{n\to\infty}\theta_{n,k}$ を求めよ."
        )
        result = solve_request_payload({"problem": text, "full_pipeline": True, "allow_specialized": True})
        self.assertTrue(result["ok"])
        self.assertEqual(result["answer"], "pi/6")
        self.assertEqual(result["data"]["tool_execution"]["tool_calls"][0]["name"], "probability.k_card_angle_limit")

    def test_inequality_counterexample_adapter(self):
        result = solve_request_payload(
            {"problem": "x>0 のとき x^2 < x を示せ.", "full_pipeline": True, "allow_specialized": True}
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["answer"], "{'x': 1}")
        self.assertEqual(result["data"]["tool_execution"]["tool_calls"][0]["name"], "inequality.counterexample_search")

    def test_container_geometry_detects_square_triangle_problem(self):
        text = r"平面上に一辺$\sqrt3$の正方形を固定する.一辺$\sqrt2+\sqrt6$の正三角形を, この正方形を含むように自由に動かすとき, 正三角形の通過領域の面積を求めよ."
        problem = detect_container_problem(text)
        self.assertIsNotNone(problem)
        self.assertEqual(problem.fixed_side, "sqrt(3)")
        self.assertEqual(problem.moving_side, "sqrt(2)+sqrt(6)")

    def test_container_geometry_solves_square_triangle_problem(self):
        text = r"平面上に一辺$\sqrt3$の正方形を固定する.一辺$\sqrt2+\sqrt6$の正三角形を, この正方形を含むように自由に動かすとき, 正三角形の通過領域の面積を求めよ."
        problem = detect_container_problem(text)
        result = solve_container_problem(problem)
        self.assertEqual(result["status"], "solved")
        self.assertIn("2*pi*(2*sqrt(3) + 5)", result["answer_exact"])

    def test_math_os_solves_container_problem(self):
        text = r"平面上に一辺$\sqrt3$の正方形を固定する.一辺$\sqrt2+\sqrt6$の正三角形を, この正方形を含むように自由に動かすとき, 正三角形の通過領域の面積を求めよ."
        ir = run_pipeline(text)
        self.assertEqual(ir.intent, "latex_to_container_square_in_equilateral_triangle_sweep")
        self.assertEqual(ir.tool_calls[0].result["status"], "solved")

    def test_latex_frontend_normalizes_region_problem(self):
        latex = r"""
        \begin{problem}
        $t\in\mathbb{R}$ とする。曲線 \( y = tx - t^2 \) の通過領域を求めよ。
        \end{problem}
        """
        parsed = parse_latex_problem(latex)
        self.assertIn("t in R", parsed.normalized_text)
        self.assertIn("y = t*x - t**2", parsed.normalized_text)

    def test_math_os_runs_latex_region_problem(self):
        latex = r"\begin{problem}$t\in\mathbb{R}$ とする。曲線 \( y = tx - t^2 \) の通過領域を求めよ。\end{problem}"
        ir = run_pipeline(latex)
        self.assertEqual(ir.intent, "latex_to_geometry_nl_to_dsl_region")
        self.assertEqual(ir.tool_calls[0].result["result"]["closed_form"]["inequality"], "y <= x**2/4")

    def test_tool_registry_reports_sympy(self):
        status = ToolRegistry().status()
        self.assertTrue(status["sympy"]["available"])
        self.assertIn("available", status["wolfram"])
        self.assertIn("available", status["z3"])
        self.assertIn("available", status["shapely"])
        self.assertIn("available", status["lean"])

    def test_wolfram_code_for_region(self):
        problem = parse_geometry_dsl("task region; family y = t*x - t^2; param t in R")
        code = wolfram_code_for_geometry(problem)
        self.assertIn("Reduce[Exists[t", code)
        self.assertIn("y == t*x - t^2", code)

    def test_geometry_nl_region_conversion(self):
        conversion = convert_geometry_nl("tを実数として、曲線 y = t*x - t^2 の通過領域を求めよ。")
        self.assertIsNotNone(conversion)
        self.assertEqual(conversion.dsl, "task region; family y = t*x-t**2; param t in R")

    def test_geometry_nl_envelope_conversion(self):
        conversion = convert_geometry_nl("曲線 y = t*x - t^2 の包絡線を求めよ。")
        self.assertIsNotNone(conversion)
        self.assertEqual(conversion.task, "envelope")
        self.assertEqual(conversion.equations["y"], "t*x-t**2")

    def test_geometry_nl_locus_coordinate_pair(self):
        conversion = convert_geometry_nl("(x,y)=(t+1,2t) で表される点の軌跡を求めよ。")
        self.assertIsNotNone(conversion)
        self.assertEqual(conversion.dsl, "task locus; x = t+1; y = 2*t; param t in R")

    def test_math_os_runs_natural_language_region(self):
        ir = run_pipeline("tを実数として、曲線 y = t*x - t^2 の通過領域を求めよ。")
        self.assertEqual(ir.intent, "geometry_nl_to_dsl_region")
        self.assertEqual(ir.tool_calls[0].result["result"]["closed_form"]["inequality"], "y <= x**2/4")
        self.assertEqual(ir.tool_calls[0].result["tool_results"][0]["tool"], "sympy")

    def test_geometry_dsl_envelope_execution(self):
        result = run_geometry_dsl("task envelope; family y = t*x - t^2; param t")
        self.assertEqual(result["problem"]["task"], "envelope")
        self.assertEqual(result["result"]["envelope_relation"], "-x**2 + 4*y")

    def test_geometry_dsl_region_unbounded_quadratic(self):
        result = run_geometry_dsl("task region; family y = t*x - t^2; param t in R")
        closed_form = result["result"]["closed_form"]
        self.assertEqual(closed_form["type"], "quadratic_range")
        self.assertEqual(closed_form["inequality"], "y <= x**2/4")

    def test_geometry_dsl_locus_execution(self):
        result = run_geometry_dsl("task locus; x = t + 1; y = 2*t; param t")
        self.assertEqual(result["result"]["locus_relation"], "2*x - y - 2")

    def test_geometry_dsl_parser_interval(self):
        problem = parse_geometry_dsl("task region; family y = t*x - t^2; param t in [0,2]")
        self.assertEqual(problem.domain.kind, "interval")
        self.assertEqual(problem.domain.lower, "0")
        self.assertEqual(problem.domain.upper, "2")

    def test_math_os_detects_geometry_dsl(self):
        ir = run_pipeline("task region; family y = t*x - t^2; param t in R")
        self.assertEqual(ir.intent, "geometry_dsl_region")
        self.assertEqual(ir.tool_calls[0].result["result"]["closed_form"]["inequality"], "y <= x**2/4")

    def test_envelope_execution(self):
        ir = run_pipeline("包絡線 y = t*x - t^2 を求めて。parameter t")
        self.assertEqual(ir.route, "geometry_symbolic")
        result = ir.tool_calls[0].result
        self.assertIsNotNone(result)
        if "result" in result:
            result = result["result"]
        self.assertEqual(result["envelope_relation"], "-x**2 + 4*y")

    def test_minkowski_sum_execution(self):
        ir = run_pipeline(
            "Minkowski sum [(0,0),(1,0),(1,1),(0,1)] + [(0,0),(2,0),(0,1)]"
        )
        self.assertEqual(ir.route, "convex_geometry")
        self.assertEqual(ir.tool_calls[0].result["vertices"], [[0, 0], [3, 0], [3, 1], [1, 2], [0, 2]])

    def test_formal_proof_is_planned(self):
        ir = run_pipeline("Leanで n + 0 = n を証明したい")
        self.assertEqual(ir.route, "formal_proof")
        self.assertFalse(ir.tool_calls[0].executable)
        self.assertIn("import Mathlib", ir.givens["lean_stub"])

    def test_router_can_train_from_seed_examples(self):
        router = TinyRouter()
        decision = router.route("diagram parser")
        self.assertIn(decision.label, set(router.route("diagram parser").scores))

    def test_compiler_without_execution(self):
        compiler = ProblemCompiler()
        ir = compiler.compile("solve x^2 - 5*x + 6 = 0 for x")
        ToolExecutor().execute(ir)
        self.assertEqual(ir.tool_calls[0].result["solutions"], ["2", "3"])

    def test_symbolic_query_ir_preserves_query_operator(self):
        cases = [
            ("Expand $(3x^2+2x)(x^2-5)$.", "expand", "3*x**4 + 2*x**3 - 15*x**2 - 10*x"),
            ("Factor $5x^2-45$.", "factor", "5*(x - 3)*(x + 3)"),
            ("If $(3x+1)(x-2)=7$, find the sum of the possible values of $x$.", "root_sum", "5/3"),
            ("What value of $x$ gives the minimum value of $2x^2-20x+1$?", "argmin", "5"),
            ("Given that $-6$ is a solution to $x^2+bx-42=0$, what is the value of $b$?", "solve", "-1"),
            ("If $r$ and $s$ are the roots of $3x^2-7x+2=0$, find $(r-2)(s-2)$.", "symmetric_root_expression", "0"),
        ]
        for problem, operator, expected in cases:
            with self.subTest(operator=operator):
                ir = run_pipeline(problem)
                self.assertEqual(ir.intent, f"symbolic_query_{operator}")
                self.assertEqual(ir.tool_calls[0].result["query_operator"], operator)
                self.assertEqual(ir.tool_calls[0].result["answer_exact"], expected)

    def test_symbolic_query_executes_closed_term_with_certificate(self):
        ir = run_pipeline(r"Evaluate $i^5+i^{-25}+i^{45}$.")
        self.assertEqual(ir.intent, "symbolic_query_evaluate_expression")
        self.assertEqual(ir.tool_calls[0].result["answer_exact"], "I")
        self.assertEqual(
            ir.givens["symbolic_query"]["lowering_certificate"]["kind"],
            "closed_term_evaluation",
        )

    def test_function_set_observations_lower_definitions_to_cas(self):
        domain = run_pipeline(
            r"What is the smallest real number $x$ in the domain of "
            r"$g(x)=\sqrt{(x-3)^2-(x-8)^2}$?"
        )
        image = run_pipeline(r"Compute the range of the function $h(t)=\sqrt{t^2}$.")
        self.assertEqual(domain.intent, "symbolic_query_function_domain_minimum")
        self.assertEqual(domain.tool_calls[0].result["answer_exact"], "11/2")
        self.assertEqual(image.intent, "symbolic_query_function_range")
        self.assertEqual(image.tool_calls[0].result["answer_exact"], "Interval(0, oo)")

    def test_integer_constraint_aggregate_executes_over_a_finite_set(self):
        ir = run_pipeline(
            r"Find the sum of all integers that satisfy "
            r"$|x|+1>7\text{ and }|x+1|\le7$."
        )
        self.assertEqual(ir.intent, "symbolic_query_integer_solution_sum")
        self.assertEqual(ir.tool_calls[0].result["answer_exact"], "-15")

    def test_linear_constraint_projection_generalizes_by_alpha_renaming(self):
        first = run_pipeline(
            r"Eight pounds of feathers and two ounces of gold together cost $\$932$. "
            r"Fourteen pounds of feathers and three ounces of gold together cost $\$1402$. "
            "What is the cost of five pounds of feathers and five ounces of gold?"
        )
        renamed = run_pipeline(
            "Seven crates of apples and three bags of pears together cost $83. "
            "Two crates of apples and five bags of pears together cost $64. "
            "What is the cost of four crates of apples and one bag of pears?"
        )
        self.assertEqual(first.intent, "linear_constraint_projection")
        self.assertEqual(first.tool_calls[0].result["answer_exact"], "2300")
        self.assertEqual(renamed.intent, "linear_constraint_projection")
        self.assertEqual(renamed.tool_calls[0].result["answer_exact"], "1174/29")

    def test_interval_grader_normalizes_latex_delimiters_and_unbraced_fraction(self):
        self.assertTrue(
            answers_match(
                "Union(Interval.open(-oo, -1/2), Interval.open(-1/2, oo))",
                r"\left(-\infty,-\frac 12\right)\cup \left(-\frac 12,\infty\right)",
            )
        )

    def test_linear_constraint_projection_solves_a_ratio_not_a_known_answer(self):
        ir = run_pipeline(
            "Ten treeks weigh as much as three squigs and one goolee. "
            "Two treeks and one goolee are equal in weight to one squig. "
            "The combined weight of how many treeks equals the weight of one squig?"
        )
        self.assertEqual(ir.intent, "linear_constraint_projection")
        self.assertEqual(ir.tool_calls[0].result["answer_exact"], "3")

    def test_partition_relation_uses_one_law_across_surface_domains(self):
        allocation = run_pipeline(
            "Alberta wants to distribute 320 watches among 19 friends. "
            "How many would each friend obtain?"
        )
        slicing = run_pipeline(
            "Lindsey had some chocolate. He chopped each chocolate into 26 slices. "
            "If total 115 chocolate slices Lindsey made, then how many chocolate Lindsey had?"
        )
        self.assertEqual(allocation.intent, "finite_relation_Partition")
        self.assertEqual(allocation.tool_calls[0].result["answer_exact"], "320/19")
        self.assertEqual(slicing.intent, "finite_relation_Partition")
        self.assertEqual(slicing.tool_calls[0].result["answer_exact"], "115/26")
        self.assertEqual(
            allocation.givens["finite_relation_query"]["lowering_certificate"]["law"],
            slicing.givens["finite_relation_query"]["lowering_certificate"]["law"],
        )

    def test_state_transition_recomputes_after_numeric_perturbation(self):
        loss = run_pipeline(
            "Vernon had 177 mango. Eric took some mango. Now Vernon has 33 mango. "
            "How many did Eric take?"
        )
        gain = run_pipeline(
            "Kasey had 23 car. Nancy gave him some more. Now Kasey has 200 car. "
            "How many did Nancy give him?"
        )
        self.assertEqual(loss.intent, "finite_relation_StateTransition")
        self.assertEqual(loss.tool_calls[0].result["answer_exact"], "144")
        self.assertEqual(gain.tool_calls[0].result["answer_exact"], "177")

    def test_closed_term_evaluator_requires_query_term_dependency(self):
        ir = run_pipeline("Two sides of a triangle are each $8$ units long. What is the greatest possible perimeter?")
        self.assertNotEqual(ir.intent, "symbolic_query_evaluate_expression")

    def test_symbolic_query_solves_constraint_system_then_observes_target(self):
        problem = r"""Determine $x^2+y^2$ if
        \[\begin{aligned}x+y&=3\\x-y&=1\end{aligned}\]"""
        ir = run_pipeline(problem)
        self.assertEqual(ir.intent, "symbolic_query_solve_system_evaluate")
        self.assertEqual(ir.tool_calls[0].result["answer_exact"], "5")
        self.assertEqual(ir.tool_calls[0].result["constraint_count"], 2)

    def test_symbolic_query_executes_composed_function_inverse(self):
        problem = r"Let $f(x)=7x+5$ and $g(x)=x-1$. If $h(x)=f(g(x))$, what is the inverse of $h(x)$?"
        ir = run_pipeline(problem)
        self.assertEqual(ir.intent, "symbolic_query_invert_defined_function")
        self.assertEqual(ir.tool_calls[0].result["answer_exact"], "x/7 + 2/7")

    def test_symbolic_query_executes_piecewise_function(self):
        problem = r"""Let $f(x)=\begin{cases}3x+5 &\text{if }x<-3, \\
        7-4x &\text{if }x\ge -3.\end{cases}$ Find $f(-10)$."""
        ir = run_pipeline(problem)
        self.assertEqual(ir.intent, "symbolic_query_evaluate_defined_expression")
        self.assertEqual(ir.tool_calls[0].result["answer_exact"], "-25")

    def test_symbolic_query_executes_finite_function_inverse_composition(self):
        problem = r"Given $f(1)=2$, $f(4)=3$, and $f(7)=4$, find $f^{-1}(f^{-1}(3))$."
        ir = run_pipeline(problem)
        self.assertEqual(ir.intent, "symbolic_query_evaluate_finite_function_expression")
        self.assertEqual(ir.tool_calls[0].result["answer_exact"], "7")

    def test_symbolic_query_observes_invariant_of_underdetermined_constraint(self):
        problem = r"What is $\frac{a+11b}{a-b}$ if $\frac{4a+3b}{a-2b}=5$?"
        ir = run_pipeline(problem)
        self.assertEqual(ir.intent, "symbolic_query_solve_constraints_evaluate")
        self.assertEqual(ir.tool_calls[0].result["answer_exact"], "2")

    def test_symbolic_query_executes_absolute_value_aggregate(self):
        ir = run_pipeline(r"Find the sum of all values of $x$ such that $|x-1|=7$.")
        self.assertEqual(ir.intent, "symbolic_query_root_sum")
        self.assertEqual(ir.tool_calls[0].result["answer_exact"], "2")

    def test_symbolic_query_selects_ordered_solution_after_solving(self):
        ir = run_pipeline(r"What is the smallest value of $x$ such that $|5x-1|=|3x+2|$?")
        self.assertEqual(ir.intent, "symbolic_query_solve_minimum")
        self.assertEqual(ir.tool_calls[0].result["answer_exact"], "-1/8")

    def test_latex_operator_normalization_preserves_executable_meaning(self):
        division = run_pipeline(r"Solve $(17^6-17^5)\div16=17^x$ for $x$.")
        mixed = run_pipeline(r"Solve for $w$: $\frac{1\frac16}w=\frac{42}3$.")
        custom = run_pipeline(r"If $a\ast b=2a+5b-ab$, find $3\ast10$.")
        self.assertEqual(division.tool_calls[0].result["answer_exact"], "5")
        self.assertEqual(mixed.tool_calls[0].result["answer_exact"], "1/12")
        self.assertEqual(custom.tool_calls[0].result["answer_exact"], "26")

    def test_tuple_equality_lowers_to_component_constraints(self):
        ir = run_pipeline(r"If $(x,y)=(3,9)$, what is $y^2-3xy+8$?")
        self.assertEqual(ir.givens["symbolic_query"]["constraints"], ["x=3", "y=9"])
        self.assertEqual(ir.tool_calls[0].result["answer_exact"], "8")

    def test_nth_root_lowers_to_rational_power(self):
        ir = run_pipeline(r"If $a=8$, find $\left(16\sqrt[3]{a^2}\right)^{\frac13}$.")
        self.assertEqual(ir.tool_calls[0].result["answer_exact"], "4")

    def test_inverse_proportion_uses_multiplicative_invariant(self):
        problem = r"If $j$ and $k$ are inversely proportional and $j=16$ when $k=21$, find $j$ when $k=14$."
        ir = run_pipeline(problem)
        self.assertEqual(ir.intent, "symbolic_query_inverse_proportion")
        self.assertEqual(ir.tool_calls[0].result["answer_exact"], "24")

    def test_root_ratio_lowers_through_vieta_relations(self):
        problem = r"The two roots of $x^2+bx+48=0$ are in the ratio of 3 to 1. Find the largest value of $b$."
        ir = run_pipeline(problem)
        self.assertEqual(ir.intent, "symbolic_query_root_ratio_parameter_extreme")
        self.assertEqual(ir.tool_calls[0].result["answer_exact"], "16")

    def test_factorial_equation_uses_recurrence_normalization(self):
        ir = run_pipeline(r"Find $n$ satisfying $2(n+1)!+6n!=3(n+1)!$.")
        self.assertEqual(ir.tool_calls[0].result["answer_exact"], "5")

    def test_common_root_projection_uses_resultant_and_real_quadratic_zero_set(self):
        problem = (
            r"Let $a,b$ be real and suppose $x^2+ax+b=0$ and $ax^2+bx+1=0$ "
            r"have a root in common. Find all possible values of $a+b$."
        )
        ir = run_pipeline(problem)
        self.assertEqual(ir.intent, "symbolic_query_common_polynomial_root_projection")
        self.assertEqual(ir.tool_calls[0].result["answer_exact"], ["-1", "2"])

    def test_complex_root_moduli_projects_all_complex_roots(self):
        problem = r"Let $z$ be a complex number such that $z^5+z^4+2z^3+z^2+z=0$. Find all possible values of $|z|$."
        ir = run_pipeline(problem)
        self.assertEqual(ir.intent, "symbolic_query_complex_root_moduli")
        self.assertEqual(ir.tool_calls[0].result["answer_exact"], ["0", "1"])

    def test_trigonometric_root_sum_respects_interval_constraints(self):
        problem = r"Find the sum of the solutions to $2\sin^3x-3\sin x=-\frac32\sin 2x$ in $0\le x\le2\pi$."
        ir = run_pipeline(problem)
        self.assertEqual(ir.intent, "symbolic_query_root_sum_on_domain")
        self.assertEqual(ir.tool_calls[0].result["answer_exact"], "5*pi")

    def test_public_benchmark_compares_finite_scalar_sets_and_pi_products(self):
        from math_os_prototype.public_benchmark import answers_match

        self.assertTrue(answers_match("['-1', '2']", "-1,2"))
        self.assertTrue(answers_match("['0', '1']", "0,1"))
        self.assertTrue(answers_match("5*pi", r"5 \pi"))

    def test_solution_count_is_an_observation_not_a_root_list(self):
        complex_distance = run_pipeline(r"For how many real values of $c$ do we have $|3-ci|=7$?")
        polynomial = run_pipeline(r"For how many different values of $x$ does $x^5=x^4+72x^3$?")
        self.assertEqual(complex_distance.intent, "symbolic_query_count_solutions")
        self.assertEqual(complex_distance.tool_calls[0].result["answer_exact"], "2")
        self.assertEqual(polynomial.intent, "symbolic_query_count_solutions")
        self.assertEqual(polynomial.tool_calls[0].result["answer_exact"], "3")

    def test_constraint_system_accepts_nonunique_states_with_unique_observation(self):
        problem = r"""Determine $x^2+y^2$ if
        \[\begin{aligned}x^2&=4\\y^2&=9\end{aligned}\]"""
        ir = run_pipeline(problem)
        self.assertEqual(ir.intent, "symbolic_query_solve_system_evaluate")
        self.assertEqual(ir.tool_calls[0].result["answer_exact"], "13")

    def test_closed_order_projection_is_a_typed_observation(self):
        floor_ir = run_pipeline(r"What is the greatest integer less than or equal to $\frac{3^{100}+2^{100}}{3^{96}+2^{96}}$?")
        ceiling_ir = run_pipeline(r"Find the least integer greater than or equal to $\frac{17}{5}$.")
        self.assertEqual(floor_ir.intent, "symbolic_query_floor_value")
        self.assertEqual(floor_ir.tool_calls[0].result["answer_exact"], "80")
        self.assertEqual(ceiling_ir.tool_calls[0].result["answer_exact"], "4")

    def test_closed_term_projections_are_numeric_morphisms(self):
        nearest = run_pipeline(r"What is the nearest integer to $(5+2\sqrt7)^4$?")
        root = run_pipeline(r"What is the positive square root of the product $10 \times 15 \times 24$?")
        digit = run_pipeline(r"What is the units digit of $1!+3!+5!+7!$?")
        changed = run_pipeline(r"What is the positive square root of the product $6 \times 24$?")
        self.assertEqual(nearest.tool_calls[0].result["answer_exact"], "11218")
        self.assertEqual(root.tool_calls[0].result["answer_exact"], "60")
        self.assertEqual(digit.tool_calls[0].result["answer_exact"], "7")
        self.assertEqual(changed.tool_calls[0].result["answer_exact"], "12")

    def test_vector_query_uses_typed_cross_product_not_scalar_multiplication(self):
        problem = r"""Given $\mathbf{a} = \begin{pmatrix} 2 \\ 1 \\ 0 \end{pmatrix},$
        $\mathbf{b} = \begin{pmatrix} 0 \\ 0 \\ 1 \end{pmatrix},$ and
        $\mathbf{c} = \begin{pmatrix} 1 \\ -2 \\ -3 \end{pmatrix},$ compute
        \[(\mathbf{a} \times \mathbf{b}) \times \mathbf{c} -
        \mathbf{a} \times (\mathbf{b} \times \mathbf{c}).\]"""
        ir = run_pipeline(problem)
        self.assertEqual(ir.intent, "vector_query_evaluate_vector_expression")
        self.assertEqual(ir.tool_calls[0].result["answer_exact"], "Matrix([6, 3, 0])")

    def test_vector_query_intersects_affine_constraints(self):
        problem = r"""A plane is parameterized by
        \[\mathbf{v}=\begin{pmatrix}1\\6\\7\end{pmatrix}
        +t\begin{pmatrix}2\\-1\\-1\end{pmatrix}
        +s\begin{pmatrix}2\\-3\\-5\end{pmatrix},\]
        and a line is parameterized by
        \[\mathbf{w}=\begin{pmatrix}7\\4\\1\end{pmatrix}
        +u\begin{pmatrix}3\\0\\-1\end{pmatrix}.\]
        Find the intersection of the plane and line."""
        ir = run_pipeline(problem)
        self.assertEqual(ir.intent, "vector_query_intersect_affine_subspaces")
        self.assertEqual(ir.tool_calls[0].result["answer_exact"], "Matrix([1, 4, 3])")

    def test_vector_query_selects_direction_equivalence_classes(self):
        problem = r"""A line has slope $\frac{2}{5}$. Which direction vectors are possible?
        (A) $\begin{pmatrix}2\\5\end{pmatrix}$
        (B) $\begin{pmatrix}5\\2\end{pmatrix}$
        (C) $\begin{pmatrix}0\\0\end{pmatrix}$
        (E) $\begin{pmatrix}-5\\-2\end{pmatrix}$
        (G) $\begin{pmatrix}40\\16\end{pmatrix}$"""
        ir = run_pipeline(problem)
        self.assertEqual(ir.intent, "vector_query_select_direction_vectors")
        self.assertEqual(ir.tool_calls[0].result["answer_exact"], "B, E, G")

    def test_vector_query_lifts_executable_constraints_to_semantic_graph(self):
        problem = r"""Given $\mathbf{a} = \begin{pmatrix} 1 \\ 0 \\ 0 \end{pmatrix}$ and
        $\mathbf{b} = \begin{pmatrix} 0 \\ 1 \\ 0 \end{pmatrix}$, compute
        \[\mathbf{a} \times \mathbf{b}.\]"""
        result = solve_request_payload({"problem": problem, "full_pipeline": True})
        self.assertEqual(result["answer"], "Matrix([0, 0, 1])")
        graph = result["data"]["semantic_graph"]
        self.assertTrue(any(item["kind"] == "typed_vector_term" for item in graph["constraints"]))
        self.assertTrue(any(item["name"] == "evaluate_vector_expression" for item in graph["morphisms"]))
        self.assertTrue(any(item["sort"] == "Vector" for item in graph["queries"]))

    def test_symbolic_query_ir_lifts_to_typed_semantic_graph(self):
        result = solve_request_payload(
            {
                "problem": "For what values of $x$ is $x^2-5x-4 \\le 10$? Express the answer in interval notation.",
                "full_pipeline": True,
            }
        )
        self.assertEqual(result["answer"], "Interval(-2, 7)")
        graph = result["data"]["semantic_graph"]
        self.assertTrue(any(item["name"] == "solve_inequality" for item in graph["morphisms"]))
        self.assertTrue(any(item["kind"] == "solve_inequality" and item["sort"] == "Set" for item in graph["queries"]))

    def test_symbolic_query_expands_chained_inequality_as_constraint_intersection(self):
        result = solve_request_payload(
            {
                "problem": "For what real values of $u$ is $-5<u^4+5u^2<24$ satisfied? Express the answer in interval notation.",
                "full_pipeline": True,
            }
        )
        self.assertEqual(result["answer"], "Interval.open(-sqrt(3), sqrt(3))")
        symbolic_ir = result["data"]["parser"]["givens"]["symbolic_query"]
        self.assertEqual(symbolic_ir["constraints"], ["-5<u**4+5*u**2", "u**4+5*u**2<24"])

    def test_symbolic_query_does_not_drop_equation_for_domain_inequalities(self):
        problem = (
            r"$0<2p<q$, $n\geqq2$ and "
            r"$\cos^n\frac{p\pi}{q}+\sin^n\frac{p\pi}{q}="
            r"\cos\frac{np\pi}{q}+\sin\frac{np\pi}{q}$. "
            r"Find all triples $(n,p,q)$."
        )

        compiled = compile_symbolic_query(problem)

        self.assertIsNotNone(compiled)
        self.assertNotEqual(compiled.query_operator, "solve_inequality")

    def test_structural_interval_requires_token_and_explicit_delimiters(self):
        prose = analyze_structure("A shop sells mini cupcakes in boxes, and asks how many remain.")
        self.assertFalse(any(item.kind == "interval" for item in prose.constraints))

        interval = analyze_structure("Find x in [0, 1].")
        constraints = [item.expression for item in interval.constraints if item.kind == "interval"]
        self.assertEqual(constraints, ["x in [0, 1]"])

    def test_quantity_execution_requires_conservation_certificate(self):
        result = solve_quantity_reasoning_problem(
            "Tera had some mango. Becky gave him 7 more. Now Tera has 31 mango. How many mango did Tera have initially?"
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.semantic_model["execution_certificate"]["status"], "proved")
        self.assertEqual(result.semantic_model["execution_certificate"]["law"], "final = initial + gain")

    def test_quantity_semantics_separates_measure_unit_from_measured_object(self):
        result = solve_quantity_reasoning_problem(
            "The recipe calls for 7 cups of sugar and 10 cups of flour. She already put in 4 cups of sugar. How many more cups of sugar are needed?"
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.answer_exact, "3")
        objects = [item["obj"] for item in result.quantities]
        self.assertEqual(objects, ["sugar", "flour", "sugar"])

    def test_generic_equation_solver_cannot_answer_an_unreached_aggregate_query(self):
        result = solve_request_payload(
            {
                "problem": "The roots of $z^6+z^4+z^2+1=0$ are vertices of a convex polygon. Find the sum of the squares of its side lengths.",
                "full_pipeline": True,
            }
        )
        self.assertIsNone(result["answer"])
        operations = result["data"]["structural_ir"]["operations"]
        self.assertTrue(any(item["kind"] == "aggregate" for item in operations))

    def test_latex_frontend_preserves_bare_trigonometric_application(self):
        parsed = parse_latex_problem(r"$\sin\theta,\cos x,\tan t$")
        self.assertEqual(parsed.math_segments, ["sin(theta),cos(x),tan(t)"])

    def test_latex_frontend_preserves_indexed_functions_and_nested_limits(self):
        parsed = parse_latex_problem(
            r"$k(<n)$, $\cos\theta_{n,k}$, "
            r"$\lim_{k\to\infty}\lim_{n\to\infty}\theta_{n,k}$"
        )
        self.assertEqual(
            parsed.math_segments,
            [
                "(k < n)",
                "cos(theta_n_k)",
                "limit_k to infinity limit_n to infinity theta_n_k",
            ],
        )

    def test_typed_analysis_executes_unseen_latex_limit(self):
        ir = run_pipeline(r"次の極限を求めよ。\[\lim_{t\to0}(1+3t)^{1/t}\]")
        self.assertEqual(ir.intent, "typed_analysis_limit")
        self.assertEqual(ir.tool_calls[0].status, "executed")
        self.assertEqual(ir.tool_calls[0].result["answer_exact"], "exp(3)")

    def test_typed_analysis_rejects_partial_multipart_match(self):
        ir = run_pipeline(
            r"(1) \(\lim_{x\to0}\frac{\sin x}{x}\) を求めよ。"
            r"(2) \(\lim_{x\to0}\frac{1-\cos x}{x^2}\) を求めよ。"
        )
        self.assertNotEqual(ir.intent, "typed_analysis_limit")

    def test_typed_analysis_does_not_treat_an_indexed_sequence_as_constant(self):
        ir = run_pipeline(r"数列 \(S_n\) に対し \[\lim_{n\to\infty}S_n\] を求めよ。")
        self.assertEqual(ir.intent, "typed_analysis_limit")
        self.assertEqual(ir.tool_calls[0].status, "failed")
        self.assertIn("dependency was lost", ir.tool_calls[0].error)

    def test_closed_proposition_rejects_unevaluated_integral(self):
        ir = run_pipeline(
            r"\[\int_0^{\pi/2}\{\cos(\cos x+\sin x)+\sin(\cos x+\sin x)\}\,dx<2\]を示せ。"
        )
        self.assertEqual(ir.intent, "typed_analysis_decide_closed_proposition")
        self.assertEqual(ir.tool_calls[0].status, "failed")
        self.assertIn("unevaluated operator", ir.tool_calls[0].error)

    def test_closed_proposition_is_decided_without_problem_specific_answer(self):
        ir = run_pipeline(r"\[2^{\sqrt2}<e\]を示せ。")
        self.assertEqual(ir.intent, "typed_analysis_decide_closed_proposition")
        result = ir.tool_calls[0].result
        self.assertEqual(result["answer_exact"], "True")
        self.assertEqual(result["relation"], "2**(sqrt(2)) < E")
        self.assertEqual(result["proof_certificate"]["kind"], "atanh_log_series_upper_bound")
        self.assertEqual(result["proof_certificate"]["verified_product_bound"], "True")

    def test_geometric_progression_lowers_to_definition_and_elimination(self):
        problem = (
            r"\(\sin t,\cos t,\tan t\) がこの順で等比数列をなすような"
            r"\(\cos t\)を求めよ。"
        )
        ir = run_pipeline(problem)
        self.assertEqual(ir.intent, "progression_geometric_constraint")
        result = ir.tool_calls[0].result
        self.assertEqual(result["elimination_polynomial"], "c**3 + c**2 - 1")
        self.assertEqual(len(result["lowering_certificate"]), 4)
        self.assertAlmostEqual(float(sp.N(sp.sympify(result["answer_exact"]))), 0.7548776662, places=9)

    def test_self_similar_nested_radical_is_lowered_to_iteration(self):
        problem = r"$\sqrt{e^{\pi\sqrt{e^{\pi\sqrt{e^{\pi\cdots}}}}}}$ の値を求めよ。"
        ir = run_pipeline(problem)
        self.assertEqual(ir.intent, "iteration_convergence")
        result = ir.tool_calls[0].result
        self.assertEqual(result["answer_exact"], "oo")
        self.assertEqual(result["rate"], "pi/2")

    def test_iteration_query_abstains_outside_proved_regime(self):
        problem = r"$\sqrt{e^{\frac12\sqrt{e^{\frac12\sqrt{e^{\frac12\cdots}}}}}}$ の値を求めよ。"
        ir = run_pipeline(problem)
        self.assertEqual(ir.intent, "iteration_convergence")
        self.assertEqual(ir.tool_calls[0].status, "failed")

    def test_cubic_centroid_locus_is_derived_by_elimination(self):
        problem = r"曲線 $y=x^3-2x$ 上の3点を頂点とする正三角形の重心の軌跡が囲む部分の面積を求めよ。"
        ir = run_pipeline(problem)
        self.assertEqual(ir.intent, "cubic_equilateral_centroid_locus_area")
        result = ir.tool_calls[0].result
        self.assertEqual(
            sp.simplify(sp.sympify(result["answer_exact"]) - 4 * sp.pi * (2 - sp.sqrt(3)) / 9),
            0,
        )
        self.assertAlmostEqual(result["numeric_lobe_check"], float(sp.N(2 * sp.pi * (2 - sp.sqrt(3)) / 9)), places=9)

    def test_cubic_centroid_locus_is_translation_invariant(self):
        original = run_pipeline(
            r"曲線 $y=x^3-2x$ 上の3点を頂点とする正三角形の重心の軌跡が囲む部分の面積を求めよ。"
        )
        translated = run_pipeline(
            r"曲線 $y=(x-1)^3-2(x-1)+5$ 上の3点を頂点とする正三角形の重心の軌跡が囲む部分の面積を求めよ。"
        )
        self.assertEqual(
            original.tool_calls[0].result["answer_exact"],
            translated.tool_calls[0].result["answer_exact"],
        )

    def test_hilbert_witness_is_synthesized_from_target_correlation(self):
        ir = run_pipeline(
            r"\[\frac{\int_{0}^{1}f(x)g(x)dx}{\sqrt{\int_{0}^{1}f(x)^2dx}"
            r"\sqrt{\int_{0}^{1}g(x)^2dx}}=\cos\frac{\pi}{3}\]を満たす関数を一組求めよ."
        )
        self.assertEqual(ir.intent, "hilbert_normalized_inner_product_witness")
        result = ir.tool_calls[0].result
        self.assertEqual(result["target_correlation"], "1/2")
        self.assertEqual(result["verification"]["normalized_inner_product"], "1/2")

    def test_prime_reciprocal_series_uses_parity_superset(self):
        ir = run_pipeline(r"$\displaystyle \sum_{p:素数}\dfrac{1}{p^2}<\frac12$を示せ.")
        self.assertEqual(ir.intent, "prime_structure_bound_prime_reciprocal_power_series")
        result = ir.tool_calls[0].result
        self.assertEqual(result["answer_exact"], "True")
        self.assertEqual(result["lowering_certificate"]["kind"], "prime_type_parity_partition")
        self.assertLess(sp.Rational(result["rational_upper_bound"]), sp.Rational(1, 2))

    def test_prime_reciprocal_series_abstains_if_bound_is_insufficient(self):
        ir = run_pipeline(r"$\displaystyle \sum_{p:素数}\dfrac{1}{p^2}<\frac25$を示せ.")
        self.assertEqual(ir.intent, "prime_structure_bound_prime_reciprocal_power_series")
        self.assertEqual(ir.tool_calls[0].status, "failed")

    def test_prime_triangle_radius_proof_covers_all_parity_cases(self):
        ir = run_pipeline("三辺が全て素数である三角形の外接円半径は無理数であることを示せ.")
        self.assertEqual(ir.intent, "prime_structure_prove_prime_triangle_circumradius_irrational")
        result = ir.tool_calls[0].result
        self.assertEqual(result["answer_exact"], "True")
        self.assertEqual(len(result["case_certificates"]), 4)


if __name__ == "__main__":
    unittest.main()
