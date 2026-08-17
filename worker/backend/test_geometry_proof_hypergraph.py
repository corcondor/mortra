from __future__ import annotations

import unittest

from geometry_proof_hypergraph import (
    Atom,
    BidirectionalHypergraphProver,
    Theorem,
    euclidean_relation_theorems,
    synthesize_backward_obligations,
)
from geometry_natural_formalizer import GeometryFormalization, TypedPredicate, prove_formalization


class GeometryProofHypergraphTest(unittest.TestCase):
    def test_backward_obligation_instantiates_missing_typed_premise(self) -> None:
        theorem = Theorem(
            "cyclic-from-angle",
            (
                Atom(
                    "eqangle",
                    ("?P", "?A", "?P", "?B", "?Q", "?A", "?Q", "?B"),
                ),
                Atom("ncoll", ("?P", "?Q", "?A")),
            ),
            Atom("cyclic", ("?A", "?B", "?P", "?Q")),
        )
        obligations = synthesize_backward_obligations(
            (Atom("ncoll", ("P", "Q", "A")),),
            Atom("cyclic", ("A", "B", "P", "Q")),
            (theorem,),
        )
        self.assertTrue(obligations)
        best = obligations[0]
        self.assertEqual(best.theorem, "cyclic-from-angle")
        self.assertEqual(best.unbound_variables, ())
        self.assertEqual(len(best.matched_premises), 1)
        self.assertEqual(best.open_premises[0].predicate, "eqangle")

    def test_backward_obligation_keeps_existential_point_as_typed_hole(self) -> None:
        theorem = Theorem(
            "common-perpendicular",
            (
                Atom("perp", ("?A", "?B", "?X", "?Y")),
                Atom("perp", ("?C", "?D", "?X", "?Y")),
            ),
            Atom("para", ("?A", "?B", "?C", "?D")),
        )
        obligations = synthesize_backward_obligations(
            (), Atom("para", ("A", "B", "C", "D")), (theorem,)
        )
        self.assertTrue(obligations)
        self.assertEqual(obligations[0].unbound_variables, ("?X", "?Y"))
        self.assertEqual(len(obligations[0].open_premises), 2)

    def test_multistep_perpendicular_transport_is_label_independent(self) -> None:
        prover = BidirectionalHypergraphProver(euclidean_relation_theorems())
        for labels in (("A", "B", "C", "D", "E", "F", "G", "H"), ("P", "Q", "R", "S", "T", "U", "V", "W")):
            a, b, c, d, e, f, g, h = labels
            facts = [
                Atom("perp", (a, b, c, d)),
                Atom("para", (c, d, e, f)),
                Atom("para", (e, f, g, h)),
                Atom("cong", (a, c, b, d)),  # irrelevant; must not enter the proof slice
            ]
            goal = Atom("perp", (a, b, g, h))
            proof = prover.prove(facts, goal)
            self.assertIsNotNone(proof)
            self.assertEqual(proof.goal, goal.canonical())
            self.assertEqual(proof.rounds, 2)
            self.assertNotIn("segment-congruence-transitivity", [step.theorem for step in proof.steps])

    def test_congruence_chain_uses_one_schema_for_arbitrary_depth(self) -> None:
        prover = BidirectionalHypergraphProver(euclidean_relation_theorems())
        facts = [
            Atom("cong", ("A", "B", "C", "D")),
            Atom("cong", ("C", "D", "E", "F")),
            Atom("cong", ("E", "F", "G", "H")),
        ]
        proof = prover.prove(facts, Atom("cong", ("A", "B", "G", "H")))
        self.assertIsNotNone(proof)
        self.assertGreaterEqual(proof.rounds, 2)
        self.assertEqual(proof.steps[-1].atom, Atom("cong", ("A", "B", "G", "H")).canonical())

    def test_line_relation_unification_is_invariant_to_lexical_line_order(self) -> None:
        prover = BidirectionalHypergraphProver(euclidean_relation_theorems())
        facts = [
            Atom("perp", ("Z", "Y", "A", "B")),
            Atom("para", ("A", "B", "M", "N")),
            Atom("para", ("M", "N", "C", "D")),
        ]
        proof = prover.prove(facts, Atom("perp", ("Z", "Y", "C", "D")))
        self.assertIsNotNone(proof)
        assert proof is not None
        self.assertEqual(proof.rounds, 2)

    def test_formalizer_bridge_returns_replayable_proof_dag(self) -> None:
        result = GeometryFormalization(
            status="parsed",
            normalized_text="",
            points=list("ABCDEFGH"),
            predicates=[
                TypedPredicate("perp", ("A", "B", "C", "D"), "given"),
                TypedPredicate("para", ("C", "D", "E", "F"), "given"),
                TypedPredicate("para", ("E", "F", "G", "H"), "given"),
            ],
            goal=TypedPredicate("perp", ("A", "B", "G", "H"), "goal"),
            goals=[TypedPredicate("perp", ("A", "B", "G", "H"), "goal")],
            triangles=[],
            unresolved_relations=[],
            coordinates={},
            diagram_residual=None,
            restarts=0,
            formal_problem=None,
            discourse_objects=[],
        )
        proof = prove_formalization(result)
        self.assertIsNotNone(proof)
        self.assertEqual(proof["goal"], "perp(A,B,G,H)")
        self.assertEqual(proof["steps"][-1]["depth"], 2)


if __name__ == "__main__":
    unittest.main()
