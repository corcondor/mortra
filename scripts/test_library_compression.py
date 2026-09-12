"""Handwritten correctness fixtures; never included in discovery statistics."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from math_os_prototype.holonomic_route_discovery import key, validate
from math_os_prototype.library_compression import (
    audit_bound, candidates, canonical_literals, cost, expand, generalise,
    holes, learn, learn_library, match_sites, matches_bias, rewrite,
    search_bias, select_sites, structure_size, upper_bound, utility,
    verify_semantics, definition_id, definition_table, is_call, library_term,
    subterms, match_term, instantiate_term, bound_precondition,
    prefix_bytes)


def hyper(a, b=()):
    return {"op": "hyper", "a": list(a), "b": list(b)}


def mul(left, right):
    return {"op": "mul", "left": left, "right": right}


def add(left, right):
    return {"op": "add", "left": left, "right": right}


def diff(child):
    return {"op": "diff", "child": child}


def entry(name, program):
    return {"id": name, "program": program, "proved": True}


# A corpus where one shape recurs with a different companion each time, so the
# recurring part is worth naming and the companion has to become an argument.
CORPUS = [
    entry("c0", mul(hyper(["1/2"]), hyper(["1/2", 1], [1]))),
    entry("c1", mul(hyper([1]), hyper(["1/2", 1], [1]))),
    entry("c2", mul(hyper(["3/2"]), hyper(["1/2", 1], [1]))),
    entry("c3", mul(diff(hyper(["1/2"])), hyper(["1/2", 1], [1]))),
    entry("c4", add(hyper([1]), hyper(["3/2"]))),
]


class CostTests(unittest.TestCase):
    def test_the_cost_is_the_declared_description_cost(self):
        from math_os_prototype.representation_progress import description_bits
        for row in CORPUS:
            self.assertEqual(cost(row["program"]), description_bits(row["program"]))

    def test_renaming_nothing_and_hiding_nothing_is_the_point(self):
        # The rewritten program carries the arguments in full, and the body is
        # paid for once as the definition, so neither can be hidden.
        template, _ = generalise(CORPUS[0]["program"], CORPUS[1]["program"])
        verdict = utility(CORPUS, template)
        self.assertGreater(verdict["definition_bits"], 0)
        touched = [row for row in verdict["rewritten"] if row["sites"]]
        self.assertTrue(touched)
        for row in touched:
            self.assertIn("arguments", str(row["program"]))


class GeneraliseTests(unittest.TestCase):
    def test_a_numeric_disagreement_becomes_a_value_hole(self):
        template, samples = generalise(hyper(["1/2"]), hyper([1]))
        self.assertEqual(holes(template), ["p0"])
        self.assertEqual(samples["p0"], ["1/2", "1"])

    def test_a_structural_disagreement_becomes_a_program_hole(self):
        template, samples = generalise(CORPUS[0]["program"], CORPUS[3]["program"])
        self.assertEqual(holes(template), ["f0"])
        self.assertEqual(template["op"], "mul")
        self.assertEqual(samples["f0"], [hyper(["1/2"]), diff(hyper(["1/2"]))])

    def test_a_bare_hole_is_refused(self):
        with self.assertRaises(ValueError):
            generalise(hyper(["1/2"]), diff(hyper(["1/2"])))

    def test_identical_subterms_abstract_nothing(self):
        with self.assertRaises(ValueError):
            generalise(hyper(["1/2"]), hyper(["1/2"]))

    def test_the_structure_that_survives_is_what_is_named(self):
        template, _ = generalise(CORPUS[0]["program"], CORPUS[3]["program"])
        self.assertGreater(structure_size(template), 0)


class SiteTests(unittest.TestCase):
    def test_a_program_argument_is_a_well_formed_program(self):
        template, _ = generalise(CORPUS[0]["program"], CORPUS[3]["program"])
        for row in CORPUS:
            for site in match_sites(template, row["program"]):
                for name, value in site["binding"].items():
                    if name.startswith("f"):
                        validate(value)

    def test_nested_sites_are_not_both_taken(self):
        template, _ = generalise(hyper(["1/2"]), hyper([1]))
        program = mul(hyper(["1/2"]), mul(hyper([1]), hyper(["3/2"])))
        sites = match_sites(template, program)
        chosen = select_sites(sites)
        self.assertLessEqual(len(chosen), len(sites))
        paths = [tuple(s["path"]) for s in chosen]
        for outer in paths:
            for inner in paths:
                if outer == inner:
                    continue
                self.assertNotEqual(inner[:len(outer)], outer)


class RewriteTests(unittest.TestCase):
    def test_expanding_the_rewrite_returns_the_original(self):
        # Up to how a rational literal happens to be typed: `instantiate` writes
        # one back as a string, and `rational` reads both the same way.
        template, _ = generalise(CORPUS[0]["program"], CORPUS[3]["program"])
        touched = 0
        for row in CORPUS:
            sites = select_sites(match_sites(template, row["program"]))
            if not sites:
                continue
            touched += 1
            replaced = rewrite(row["program"], 0, template, sites)
            self.assertEqual(key(canonical_literals(expand(replaced, definition_table({0: template})))),
                             key(canonical_literals(row["program"])))
        self.assertGreater(touched, 1)

    def test_the_rewritten_programs_are_the_same_series(self):
        library = learn_library(CORPUS, rounds=1, pairs=600)
        if not library["library"]:
            self.skipTest("nothing compressed on this fixture")
        verdict = verify_semantics(library, CORPUS, sample=3)
        self.assertTrue(verdict["checked"])
        self.assertEqual(verdict["failures"], [])
        self.assertIn("definitional", verdict["route_note"])

    def test_a_rewritten_program_is_not_in_the_executable_grammar(self):
        template, _ = generalise(CORPUS[0]["program"], CORPUS[3]["program"])
        sites = select_sites(match_sites(template, CORPUS[0]["program"]))
        replaced = rewrite(CORPUS[0]["program"], 0, template, sites)
        with self.assertRaises(ValueError):
            validate(replaced)


class ObjectiveTests(unittest.TestCase):
    def test_the_utility_is_before_minus_after_minus_definition(self):
        template, _ = generalise(CORPUS[0]["program"], CORPUS[3]["program"])
        verdict = utility(CORPUS, template)
        self.assertEqual(
            verdict["utility_bits"],
            verdict["corpus_bits_before"] - verdict["corpus_bits_after"]
            - verdict["definition_bits"])
        self.assertEqual(verdict["corpus_bits_before"],
                         sum(cost(row["program"]) for row in CORPUS))

    def test_a_pattern_that_occurs_once_does_not_pay_for_itself(self):
        template, _ = generalise(hyper(["1/2", 1], [1]), hyper(["1/2", 1], [2]))
        verdict = utility([CORPUS[0]], template)
        self.assertLess(verdict["utility_bits"], 0)

    def test_a_site_that_cannot_be_expanded_back_earns_nothing(self):
        # The invariant the whole figure rests on: every program the objective
        # counted as shortened must expand to exactly what was there.
        template, _ = generalise(CORPUS[0]["program"], CORPUS[3]["program"])
        verdict = utility(CORPUS, template)
        original = {row["id"]: row["program"] for row in CORPUS}
        counted = 0
        for row in verdict["rewritten"]:
            if not row["sites"]:
                self.assertEqual(row["before_bits"], row["after_bits"])
                continue
            counted += row["sites"]
            restored = expand(row["program"], definition_table({0: template}))
            self.assertEqual(key(canonical_literals(restored)),
                             key(canonical_literals(original[row["id"]])))
        self.assertEqual(counted, verdict["sites_used"])
        for failure in verdict["failures"]:
            row = next(r for r in verdict["rewritten"] if r["id"] == failure["id"])
            self.assertEqual(row["sites"], 0)
            self.assertEqual(row["before_bits"], row["after_bits"])

    def test_overlapping_sites_are_not_counted_twice(self):
        template, _ = generalise(hyper(["1/2"]), hyper([1]))
        verdict = utility(CORPUS, template)
        for row in verdict["rewritten"]:
            paths = [tuple(p) for p in row.get("site_paths", [])]
            self.assertEqual(len(paths), len(set(paths)))


class BoundTests(unittest.TestCase):
    def test_the_bound_is_never_below_the_utility(self):
        for first, second in ((0, 1), (0, 3), (1, 2)):
            template, _ = generalise(CORPUS[first]["program"], CORPUS[second]["program"])
            audit = audit_bound(CORPUS, template)
            self.assertTrue(audit["bound_holds"])
            self.assertGreaterEqual(audit["slack_bits"], 0)

    def test_filling_a_hole_never_adds_match_locations(self):
        template, _ = generalise(CORPUS[0]["program"], CORPUS[3]["program"])
        audit = audit_bound(CORPUS, template)
        self.assertTrue(audit["monotonicity_checks"])
        self.assertTrue(audit["monotone"])

    def test_the_bound_sums_what_the_pattern_currently_covers(self):
        template, _ = generalise(hyper(["1/2"]), hyper([1]))
        bound = upper_bound(CORPUS, template)
        total = 0
        for row in CORPUS:
            for site in select_sites(match_sites(template, row["program"])):
                total += cost(site["subterm"])
        self.assertEqual(bound["bound_bits"], total)


class SearchTests(unittest.TestCase):
    def test_the_search_reports_no_bound_violations(self):
        found = learn(CORPUS, pairs=400, keep=4)
        self.assertEqual(found["bound_violations"], [])
        self.assertGreater(found["offered"], 0)

    def test_a_corpus_with_nothing_in_common_compresses_by_zero(self):
        alone = [entry("a0", hyper(["1/2"])), entry("a1", hyper([1]))]
        library = learn_library(alone, rounds=2, pairs=200)
        self.assertLessEqual(library["net_compression_bits"], 0)
        self.assertEqual(library["library"], [])

    def test_each_round_is_measured_on_what_the_last_one_left(self):
        library = learn_library(CORPUS, rounds=2, pairs=600)
        if len(library["rounds"]) > 1 and library["library"]:
            self.assertEqual(library["rounds"][1]["corpus_bits"],
                             library["rounds"][0]["corpus_bits"]
                             - library["library"][0]["utility_bits"]
                             - library["library"][0]["definition_bits"])

    def test_the_net_figure_comes_from_the_rewritten_corpus(self):
        library = learn_library(CORPUS, rounds=2, pairs=600)
        self.assertEqual(
            library["net_compression_bits"],
            library["corpus_bits_before"] - library["corpus_bits_after"]
            - library["definition_bits"])
        self.assertEqual(library["corpus_bits_after"],
                         sum(cost(row["program"])
                             for row in library["rewritten_corpus"]))


class BiasTests(unittest.TestCase):
    def test_an_abstraction_reweights_candidates_and_adds_no_rule(self):
        library = learn_library(CORPUS, rounds=1, pairs=600)
        bias = search_bias(library)
        self.assertIn("candidate ordering only", bias["effect"])
        self.assertIn("no abstraction is added", bias["not_done"])
        if bias["entries"]:
            hits = matches_bias(bias, CORPUS[0]["program"])
            self.assertTrue(hits)
            self.assertGreater(hits[0]["weight_multiplier"], 1)

    def test_a_program_the_library_does_not_cover_is_not_reweighted(self):
        library = learn_library(CORPUS, rounds=1, pairs=600)
        bias = search_bias(library)
        self.assertEqual(matches_bias(bias, {"op": "poly", "coefficients": [7]}), [])


class DefinitionIdentityTests(unittest.TestCase):
    """A call must not resolve against a body that is not the one it names."""

    def setUp(self):
        self.template, _ = generalise(CORPUS[0]["program"], CORPUS[3]["program"])
        self.other, _ = generalise(hyper(["1/2"]), hyper([1]))
        sites = select_sites(match_sites(self.template, CORPUS[0]["program"]))
        self.call = rewrite(CORPUS[0]["program"], 0, self.template, sites)

    def test_a_tampered_table_is_refused_rather_than_applied(self):
        table = definition_table({0: self.template})
        table["definitions"]["0"] = self.other
        with self.assertRaises(ValueError):
            expand(self.call, table)

    def test_a_definition_of_the_wrong_shape_is_refused_at_the_call(self):
        # Same seal, honestly built, but a body that takes different arguments.
        with self.assertRaises(ValueError):
            expand(self.call, definition_table({0: self.other}))

    def test_a_name_the_table_does_not_have_leaves_the_call_standing(self):
        standing = expand(self.call, definition_table({7: self.template}))
        self.assertTrue(is_call(standing))

    def test_the_identity_of_a_definition_is_its_content(self):
        self.assertEqual(definition_id(self.template), definition_id(self.template))
        self.assertNotEqual(definition_id(self.template), definition_id(self.other))


class NestedDefinitionTests(unittest.TestCase):
    """A later definition has to be able to talk about an earlier one."""

    def test_a_call_is_a_term_the_library_may_be_built_around(self):
        template, _ = generalise(CORPUS[0]["program"], CORPUS[3]["program"])
        sites = select_sites(match_sites(template, CORPUS[0]["program"]))
        call = rewrite(CORPUS[0]["program"], 0, template, sites)
        self.assertTrue(is_call(call))
        self.assertTrue(library_term(call))
        self.assertIn(call, [node for _, node in subterms(call)])

    def test_a_template_can_contain_a_call(self):
        template, _ = generalise(CORPUS[0]["program"], CORPUS[3]["program"])
        first = rewrite(CORPUS[0]["program"], 0, template,
                        select_sites(match_sites(template, CORPUS[0]["program"])))
        second = rewrite(CORPUS[1]["program"], 0, template,
                         select_sites(match_sites(template, CORPUS[1]["program"])))
        outer, _ = generalise(add(first, hyper([1])), add(second, hyper(["3/2"])))
        # The call survives as fixed structure, and what differed inside its
        # argument became an argument of the new definition.
        self.assertEqual(outer["op"], "add")
        self.assertTrue(is_call(outer["left"]))
        self.assertEqual(outer["left"]["abstraction"], 0)
        self.assertEqual(sorted(holes(outer)), ["p0", "p1"])

    def test_a_call_cannot_be_abstracted_into_an_argument(self):
        template, _ = generalise(CORPUS[0]["program"], CORPUS[3]["program"])
        call = rewrite(CORPUS[0]["program"], 0, template,
                       select_sites(match_sites(template, CORPUS[0]["program"])))
        with self.assertRaises(ValueError):
            generalise(add(call, hyper([1])), add(hyper(["3/2"]), hyper([1])))


class NestedArgumentTests(unittest.TestCase):
    """A call may be an argument of a call, and must leave at the boundary."""

    BODY = {"left": {"op": "poly", "coefficients": ["0", "1"]}, "op": "mul",
            "right": {"op": "diff", "child": {"series_parameter": "f0"}}}

    def table(self):
        return definition_table({1: self.BODY})

    def inner(self):
        return {"op": "use", "abstraction": 1, "arguments": {"f0": hyper([1])}}

    def outer(self):
        return {"op": "use", "abstraction": 1, "arguments": {"f0": self.inner()}}

    def test_the_old_matcher_refuses_a_call_as_an_argument(self):
        from math_os_prototype.holonomic_parametric_learning import match
        self.assertFalse(match({"series_parameter": "f9"}, self.inner(), {}))

    def test_the_library_matcher_binds_a_call_to_a_program_hole(self):
        binding = {}
        self.assertTrue(match_term({"series_parameter": "f9"}, self.inner(), binding))
        self.assertTrue(is_call(binding["f9"]))

    def test_a_template_of_a_call_matches_a_nested_call(self):
        binding = {}
        template = {"op": "use", "abstraction": 1,
                    "arguments": {"f0": {"series_parameter": "f9"}}}
        self.assertTrue(match_term(template, self.outer(), binding))
        self.assertTrue(is_call(binding["f9"]))

    def test_instantiating_keeps_the_call_and_expanding_drives_it_out(self):
        term = instantiate_term({"series_parameter": "f9"}, {"f9": self.inner()})
        self.assertTrue(is_call(term))
        expanded = expand(self.outer(), self.table())
        validate(expanded)
        self.assertFalse(is_call(expanded))

    def test_every_position_of_a_nested_call_is_a_library_term(self):
        paths = [path for path, _ in subterms(self.outer())]
        self.assertIn((), paths)
        self.assertIn(("arguments", "f0"), paths)
        self.assertIn(("arguments", "f0", "arguments", "f0"), paths)


class BoundPreconditionTests(unittest.TestCase):
    """The bound is a guarantee only where a stated corpus property holds."""

    def test_the_precondition_holds_on_a_corpus_of_small_programs(self):
        verdict = bound_precondition(CORPUS)
        self.assertTrue(verdict["holds"])
        self.assertEqual(verdict["programs_over_the_limit"], [])
        self.assertLess(verdict["largest_program_bytes"], verdict["limit_bytes"])

    def test_a_program_past_the_limit_is_named_rather_than_ignored(self):
        big = {"op": "poly", "coefficients": [str(i) for i in range(4000)]}
        verdict = bound_precondition(CORPUS + [entry("big", big)])
        self.assertFalse(verdict["holds"])
        self.assertEqual([row["id"] for row in verdict["programs_over_the_limit"]],
                         ["big"])

    def test_the_prefix_is_what_the_derivation_says_it_is(self):
        self.assertEqual(prefix_bytes(1), 1)
        self.assertEqual(prefix_bytes(127), 1)
        self.assertEqual(prefix_bytes(128), 2)
        self.assertEqual(prefix_bytes((1 << 14) - 1), 2)
        self.assertEqual(prefix_bytes(1 << 14), 3)

    def test_the_search_reports_the_precondition_and_its_own_scope(self):
        found = learn(CORPUS, pairs=200, keep=2)
        self.assertTrue(found["bound_precondition"]["holds"])
        self.assertIn("never produced", found["pruning_scope"])


if __name__ == "__main__":
    unittest.main()
