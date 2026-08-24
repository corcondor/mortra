from __future__ import annotations

import unittest

from worker.backend.geometry_proof_hypergraph import Atom, Theorem
from worker.backend.mmt_exact_coordination import (
    MMTAtom,
    MMTExactCoordinator,
    MMTSymbolAssignment,
    MMTTheoryView,
)
from worker.backend.symbolic_sheaf_coordination import RuleClosureAdapter


BASE = "https://mortra.dev/mmt/geometry/euclidean-relation"


class MMTExactCoordinationTests(unittest.TestCase):
    def test_distinct_native_predicates_compose_through_shared_symbols(self) -> None:
        first = RuleClosureAdapter(
            "newclid",
            (
                Theorem(
                    "source_to_intermediate",
                    (Atom("source_native", ("?a", "?b", "?c", "?d")),),
                    Atom("intermediate_native", ("?a", "?b", "?c", "?d")),
                ),
            ),
            imports=("source_native", "intermediate_native"),
            exports=("intermediate_native",),
        )
        second = RuleClosureAdapter(
            "gclc",
            (
                Theorem(
                    "intermediate_to_target",
                    (Atom("intermediate_alias", ("?a", "?b", "?c", "?d")),),
                    Atom("target_relation", ("?a", "?c")),
                ),
            ),
            imports=("intermediate_alias", "target_relation"),
            exports=("target_relation",),
        )
        views = (
            MMTTheoryView(
                "newclid",
                "https://newclid.org/theory",
                BASE,
                (
                    MMTSymbolAssignment("source_native", f"{BASE}?source"),
                    MMTSymbolAssignment("intermediate_native", f"{BASE}?intermediate"),
                ),
            ),
            MMTTheoryView(
                "gclc",
                "https://gclc.org/theory",
                BASE,
                (
                    MMTSymbolAssignment("intermediate_alias", f"{BASE}?intermediate"),
                    MMTSymbolAssignment("target_relation", f"{BASE}?target"),
                ),
            ),
        )
        given = MMTAtom(f"{BASE}?source", ("a", "b", "c", "d"))
        goal = MMTAtom(f"{BASE}?target", ("a", "c"))
        result = MMTExactCoordinator((first, second), views).solve((given,), goal)
        self.assertTrue(result.solved)
        self.assertTrue(result.replayed)
        self.assertEqual([item.source_agent_id for item in result.certificates], ["newclid", "gclc"])

    def test_argument_permutation_round_trips(self) -> None:
        view = MMTTheoryView(
            "agent",
            "https://agent.invalid/theory",
            BASE,
            (MMTSymbolAssignment("native", f"{BASE}?shared", (2, 0, 1)),),
        )
        native = Atom("native", ("a", "b", "c"))
        shared = view.push(native)
        self.assertEqual(shared, MMTAtom(f"{BASE}?shared", ("c", "a", "b")))
        self.assertEqual(view.pull(shared), native)

    def test_shared_symbol_rejects_incompatible_theory_view_signatures(self) -> None:
        agents = (
            RuleClosureAdapter("first", (), imports=(), exports=()),
            RuleClosureAdapter("second", (), imports=(), exports=()),
        )
        views = (
            MMTTheoryView(
                "first",
                "https://first.invalid",
                BASE,
                (MMTSymbolAssignment(
                    "native_point_relation",
                    f"{BASE}?shared",
                    argument_sorts=("Point", "Point"),
                ),),
            ),
            MMTTheoryView(
                "second",
                "https://second.invalid",
                BASE,
                (MMTSymbolAssignment(
                    "native_line_relation",
                    f"{BASE}?shared",
                    argument_sorts=("Line", "Line"),
                ),),
            ),
        )

        with self.assertRaisesRegex(ValueError, "incompatible shared symbol signature"):
            MMTExactCoordinator(agents, views)

    def test_argument_permutation_also_permutates_the_shared_signature(self) -> None:
        assignment = MMTSymbolAssignment(
            "incidence",
            f"{BASE}?incidence",
            (2, 0, 1),
            ("Point", "Line", "Plane"),
        )

        self.assertEqual(
            assignment.shared_argument_sorts,
            ("Plane", "Point", "Line"),
        )

    def test_typed_view_rejects_wrong_native_arity(self) -> None:
        view = MMTTheoryView(
            "agent",
            "https://agent.invalid/theory",
            BASE,
            (MMTSymbolAssignment(
                "coll",
                f"{BASE}?collinear",
                argument_sorts=("Point", "Point", "Point"),
            ),),
        )

        self.assertIsNone(view.push(Atom("coll", ("a", "b"))))

    def test_native_predicate_arity_overloads_round_trip(self) -> None:
        view = MMTTheoryView(
            "agent",
            "https://agent.invalid/theory",
            BASE,
            (
                MMTSymbolAssignment(
                    "coll",
                    f"{BASE}?coll/arity-3",
                    argument_sorts=("Point2",) * 3,
                ),
                MMTSymbolAssignment(
                    "coll",
                    f"{BASE}?coll/arity-4",
                    argument_sorts=("Point2",) * 4,
                ),
            ),
        )

        coll3 = Atom("coll", ("a", "b", "c"))
        coll4 = Atom("coll", ("a", "b", "c", "d"))
        self.assertEqual(view.pull(view.push(coll3)), coll3)
        self.assertEqual(view.pull(view.push(coll4)), coll4)

    def test_typed_coordinator_rejects_point_scalar_confusion(self) -> None:
        agent = RuleClosureAdapter("agent", (), imports=(), exports=())
        view = MMTTheoryView(
            "agent",
            "https://agent.invalid/theory",
            BASE,
            (
                MMTSymbolAssignment(
                    "coll",
                    f"{BASE}?coll",
                    argument_sorts=("Point2",) * 3,
                ),
            ),
        )
        coordinator = MMTExactCoordinator((agent,), (view,))
        invalid = MMTAtom(f"{BASE}?coll", ("a", "1/2", "c"))
        valid = MMTAtom(f"{BASE}?coll", ("a", "b", "c"))

        result = coordinator.solve((invalid, valid), valid)

        self.assertIn(valid, result.accepted_facts)
        self.assertNotIn(invalid, result.accepted_facts)

    def test_typed_coordinator_rejects_wrong_angle_literal(self) -> None:
        agent = RuleClosureAdapter("agent", (), imports=(), exports=())
        view = MMTTheoryView(
            "agent",
            "https://agent.invalid/theory",
            BASE,
            (
                MMTSymbolAssignment(
                    "aconst",
                    f"{BASE}?aconst",
                    argument_sorts=("Point2", "Point2", "Point2", "Point2", "Angle"),
                ),
            ),
        )
        coordinator = MMTExactCoordinator((agent,), (view,))
        invalid_goal = MMTAtom(f"{BASE}?aconst", ("a", "b", "c", "d", "e"))

        with self.assertRaisesRegex(ValueError, "goal arity"):
            coordinator.solve((), invalid_goal)


if __name__ == "__main__":
    unittest.main()
