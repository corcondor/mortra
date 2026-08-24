from __future__ import annotations

import unittest

from worker.backend.geometry_proof_hypergraph import Atom, Theorem
from worker.backend.hageo_mmt_certificate_bridge import (
    HageoMMTExchange,
    _shared_argument_sorts,
    _shared_symbol_uri,
    coordinate_hageo_certificates,
    goal_conditioned_proof_basis,
)


class HageoMMTCertificateBridgeTests(unittest.TestCase):
    def test_shared_geometry_symbols_use_openmath_or_private_cd_uris(self) -> None:
        self.assertEqual(
            _shared_symbol_uri("perp"),
            "https://mortra.dev/cd/private_mortra_geometry#perpendicular_lines_by_points",
        )
        self.assertEqual(
            _shared_symbol_uri("rconst"),
            "https://mortra.dev/mmt/geometry/euclidean-relation?rconst",
        )

    def test_shared_signature_distinguishes_points_from_constants(self) -> None:
        self.assertEqual(
            _shared_argument_sorts("rconst", 5),
            ("Point2", "Point2", "Point2", "Point2", "Real"),
        )
        self.assertEqual(
            _shared_argument_sorts("aconst", 5),
            ("Point2", "Point2", "Point2", "Point2", "Angle"),
        )
        self.assertEqual(_shared_argument_sorts("perp", 4), ("Point2",) * 4)
        self.assertEqual(_shared_argument_sorts("unknown_relation", 3), ("Opaque",) * 3)

    def test_shared_signature_rejects_known_relation_arity_drift(self) -> None:
        with self.assertRaisesRegex(ValueError, "unexpected rconst arity"):
            _shared_argument_sorts("rconst", 4)

    def test_public_proof_basis_keeps_goal_required_fact(self) -> None:
        facts = (
            *(Atom(f"noise_{index}", ("a", "b")) for index in range(50)),
            Atom("source", ("a", "b")),
        )
        basis = goal_conditioned_proof_basis(
            facts,
            (Atom("target", ("a", "b")),),
            (
                Theorem(
                    "source-target",
                    (Atom("source", ("?A", "?B")),),
                    Atom("target", ("?A", "?B")),
                ),
            ),
            max_facts=8,
        )

        self.assertIn(Atom("source", ("a", "b")), basis)

    def test_two_native_theories_exchange_replayed_certificates(self) -> None:
        facts = (Atom("source", ("a", "b")),)
        theorems = (
            Theorem(
                "newclid:0",
                (Atom("source", ("?A", "?B")),),
                Atom("middle", ("?A", "?B")),
            ),
            Theorem(
                "universal-transitivity",
                (Atom("middle", ("?A", "?B")),),
                Atom("target", ("?A", "?B")),
            ),
        )

        result = coordinate_hageo_certificates(
            facts,
            (Atom("target", ("a", "b")),),
            theorems,
        )

        self.assertTrue(result.solved)
        self.assertTrue(result.replayed)
        self.assertEqual(result.certificates, 2)
        self.assertIn(Atom("middle", ("a", "b")), result.derived_facts)
        self.assertIn(Atom("target", ("a", "b")), result.derived_facts)
        self.assertEqual(result.open_demands, ())
        self.assertTrue(result.made_goal_progress)
        self.assertGreaterEqual(len(result.closed_demands), 1)
        self.assertEqual(len(result.certificate_sha256), 64)

    def test_missing_premise_is_returned_as_typed_open_demand(self) -> None:
        result = coordinate_hageo_certificates(
            (),
            (Atom("target", ("a", "b")),),
            (
                Theorem(
                    "newclid:0",
                    (Atom("source", ("?A", "?B")),),
                    Atom("target", ("?A", "?B")),
                ),
            ),
        )

        self.assertFalse(result.solved)
        self.assertEqual(result.open_demands, (Atom("source", ("a", "b")),))
        self.assertFalse(result.made_goal_progress)

    def test_irrelevant_derived_fact_is_not_reported_as_goal_progress(self) -> None:
        result = coordinate_hageo_certificates(
            (Atom("middle", ("a", "c")),),
            (Atom("target", ("a", "b")),),
            (
                Theorem(
                    "newclid:source-target",
                    (Atom("source", ("?A", "?B")),),
                    Atom("target", ("?A", "?B")),
                ),
                Theorem(
                    "universal-middle-source",
                    (Atom("middle", ("?A", "?B")),),
                    Atom("source", ("?A", "?B")),
                ),
            ),
        )

        self.assertIn(Atom("source", ("a", "c")), result.derived_facts)
        self.assertEqual(result.open_demands, (Atom("source", ("a", "b")),))
        self.assertFalse(result.made_goal_progress)

    def test_removed_but_unproved_demand_is_not_goal_progress(self) -> None:
        result = HageoMMTExchange(
            input_fact_count=0,
            selected_fact_count=0,
            accepted_facts=(),
            derived_facts=(),
            certificates=0,
            certificate_sha256="",
            goals=(),
            obligations=(),
            initial_open_demands=(Atom("perp", ("a", "b", "c", "d")),),
            open_demands=(Atom("para", ("a", "b", "c", "d")),),
        )

        self.assertEqual(result.closed_demands, ())
        self.assertEqual(len(result.introduced_demands), 1)
        self.assertFalse(result.made_goal_progress)

    def test_large_fact_state_keeps_theorem_matched_proof_basis(self) -> None:
        facts = (
            *(Atom(f"aaa_{index:03d}", ("a", "b")) for index in range(300)),
            Atom("source", ("a", "b")),
        )
        result = coordinate_hageo_certificates(
            facts,
            (Atom("target", ("a", "b")),),
            (
                Theorem(
                    "newclid:source-target",
                    (Atom("source", ("?A", "?B")),),
                    Atom("target", ("?A", "?B")),
                ),
            ),
            max_facts=32,
        )

        self.assertTrue(result.solved)
        self.assertIn(Atom("source", ("a", "b")), result.accepted_facts)
        self.assertNotIn(Atom("aaa_299", ("a", "b")), result.accepted_facts)
        self.assertEqual(result.selection_strategy, "goal-conditioned-proof-basis")

    def test_native_open_frontier_is_preserved_and_closed_by_exact_exchange(self) -> None:
        demand = Atom("middle", ("a", "b"))
        result = coordinate_hageo_certificates(
            (Atom("source", ("a", "b")),),
            (Atom("target", ("a", "b")),),
            (
                Theorem(
                    "newclid:source-middle",
                    (Atom("source", ("?A", "?B")),),
                    Atom("middle", ("?A", "?B")),
                ),
                Theorem(
                    "universal-middle-target",
                    (Atom("middle", ("?A", "?B")),),
                    Atom("target", ("?A", "?B")),
                ),
            ),
            initial_open_demands=(demand,),
        )

        self.assertEqual(result.initial_open_demands, (demand,))
        self.assertEqual(result.open_demands, ())
        self.assertEqual(result.closed_demands, (demand,))
        self.assertIn(demand, result.proof_state_facts)
        self.assertTrue(result.made_goal_progress)

    def test_variadic_native_relations_are_exchanged_as_arity_overloads(self) -> None:
        result = coordinate_hageo_certificates(
            (Atom("coll", ("a", "b", "c", "d")),),
            (Atom("target", ("a", "b")),),
            (
                Theorem(
                    "newclid:coll4-coll3",
                    (Atom("coll", ("?A", "?B", "?C", "?D")),),
                    Atom("coll", ("?A", "?B", "?C")),
                ),
                Theorem(
                    "newclid:coll3-target",
                    (Atom("coll", ("?A", "?B", "?C")),),
                    Atom("target", ("?A", "?B")),
                ),
            ),
        )

        self.assertTrue(result.solved)
        self.assertTrue(result.replayed)
        self.assertIn(Atom("coll", ("a", "b", "c")), result.derived_facts)


if __name__ == "__main__":
    unittest.main()
