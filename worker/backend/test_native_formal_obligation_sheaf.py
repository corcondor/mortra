from __future__ import annotations

import unittest

import numpy as np

from worker.backend.native_formal_obligation_sheaf import (
    FormalLocalView,
    HeterogeneousSheafADMM,
    LocalCoordinate,
    SharedChannel,
    build_candidate_local_view,
    build_pairwise_restriction_edges,
    capability_preserving_candidate_order,
    coordinate_candidate_scores,
)
from worker.backend.typed_geometry_stalk import schema_quota_score_fill


class NativeFormalObligationSheafTests(unittest.TestCase):
    def test_heterogeneous_views_only_share_typed_overlap(self) -> None:
        goal = SharedChannel("goal", "perp(line_0,line_1)")
        ndg = SharedChannel("ndg", "line_0!=point")
        action = SharedChannel("action", "foot(point_2,line_0)", "Construction")
        views = (
            FormalLocalView(
                "newclid",
                "Newclid predicates",
                (
                    LocalCoordinate("perp(a,b,c,d)", goal),
                    LocalCoordinate("foot(e,a,b)", action),
                ),
                {"perp(a,b,c,d)": 1.0, "foot(e,a,b)": 0.3},
            ),
            FormalLocalView(
                "wu",
                "Wu polynomial ideal",
                (
                    LocalCoordinate("dot(b-a,d-c)=0", goal),
                    LocalCoordinate("norm2(b-a)!=0", ndg),
                ),
                {"dot(b-a,d-c)=0": 0.8, "norm2(b-a)!=0": 0.9},
            ),
            FormalLocalView(
                "tong",
                "TongGeometry actions",
                (LocalCoordinate("construct-foot", action),),
                {"construct-foot": 0.95},
            ),
        )
        edges = build_pairwise_restriction_edges(views)
        self.assertEqual({(edge.left, edge.right) for edge in edges}, {
            ("newclid", "wu"),
            ("newclid", "tong"),
        })
        self.assertEqual(edges[0].left_map.shape[1], 2)
        self.assertEqual(edges[0].right_map.shape[1], 2)
        result = HeterogeneousSheafADMM(views, edges=edges).solve()
        self.assertLessEqual(result.trace[-1].sheaf_residual, result.trace[0].sheaf_residual)
        shared = result.shared_scores(views)
        self.assertIn(goal.key, shared)
        self.assertIn(action.key, shared)
        self.assertNotIn(ndg.key, shared)

    def test_same_text_with_different_sort_does_not_communicate(self) -> None:
        proposition = SharedChannel("candidate", "x", "Proposition")
        construction = SharedChannel("candidate", "x", "Construction")
        views = (
            FormalLocalView(
                "logic",
                "logic",
                (LocalCoordinate("x", proposition),),
                {"x": 1.0},
            ),
            FormalLocalView(
                "constructor",
                "construction",
                (LocalCoordinate("x", construction),),
                {"x": 1.0},
            ),
        )
        self.assertEqual(build_pairwise_restriction_edges(views), ())
        result = HeterogeneousSheafADMM(views).solve()
        self.assertEqual(result.shared_scores(views), {})

    def test_candidate_consensus_uses_partial_local_views(self) -> None:
        views = (
            build_candidate_local_view(
                agent_id="newclid",
                formal_language="Newclid relation closure",
                scores={"good": 1.0, "relation-only": 0.9},
            ),
            build_candidate_local_view(
                agent_id="wu",
                formal_language="Wu polynomial obligations",
                scores={"good": 0.8, "algebra-only": 1.0},
            ),
            build_candidate_local_view(
                agent_id="constructor",
                formal_language="typed construction actions",
                scores={"good": 0.7, "relation-only": 0.1, "algebra-only": 0.1},
            ),
        )
        scores, result = coordinate_candidate_scores(views)
        self.assertGreater(scores["good"], scores["relation-only"])
        self.assertGreater(scores["good"], scores["algebra-only"])
        self.assertGreater(len(result.edges), 0)

    def test_duplicate_shared_coordinate_is_rejected(self) -> None:
        channel = SharedChannel("goal", "coll(p0,p1,p2)")
        view = FormalLocalView(
            "broken",
            "broken",
            (
                LocalCoordinate("first", channel),
                LocalCoordinate("second", channel),
            ),
            {"first": 1.0, "second": 1.0},
        )
        with self.assertRaises(ValueError):
            build_pairwise_restriction_edges((view,))

    def test_positive_local_trust_changes_consensus_without_changing_channels(self) -> None:
        left = build_candidate_local_view(
            agent_id="left",
            formal_language="left language",
            scores={"candidate": 1.0},
        )
        right = build_candidate_local_view(
            agent_id="right",
            formal_language="right language",
            scores={"candidate": 0.0},
        )
        neutral, _ = coordinate_candidate_scores((left, right), iterations=48)
        trusted, result = coordinate_candidate_scores(
            (left, right),
            trust_by_agent={"left": 8.0, "right": 1.0},
            iterations=48,
        )

        self.assertGreater(trusted["candidate"], neutral["candidate"])
        self.assertEqual(len(result.edges), 1)

    def test_unknown_or_nonpositive_trust_is_rejected(self) -> None:
        view = build_candidate_local_view(
            agent_id="agent",
            formal_language="language",
            scores={"candidate": 1.0},
        )
        with self.assertRaises(ValueError):
            HeterogeneousSheafADMM((view,), trust_by_agent={"other": 1.0})
        with self.assertRaises(ValueError):
            HeterogeneousSheafADMM((view,), trust_by_agent={"agent": 0.0})

    def test_channel_block_solve_matches_dense_sheaf_system(self) -> None:
        views = (
            build_candidate_local_view(
                agent_id="left",
                formal_language="left language",
                scores={"a": 0.2, "b": 0.7},
            ),
            build_candidate_local_view(
                agent_id="middle",
                formal_language="middle language",
                scores={"a": 0.8, "b": 0.1},
            ),
            build_candidate_local_view(
                agent_id="right",
                formal_language="right language",
                scores={"a": 0.5},
            ),
        )
        solver = HeterogeneousSheafADMM(views, rho=0.8, gamma=1.3)
        rhs = np.asarray([0.3, 0.9, 0.4, 0.2, 0.7], dtype=float)
        dense = solver.rho * np.eye(solver.dimension) + solver.gamma * (
            solver._delta.T @ solver._delta
        )
        expected = np.linalg.solve(dense, rhs)
        actual = solver._consensus_solve(rhs, None)
        np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-12)

    def test_schema_quota_preserves_multiple_candidates_per_family(self) -> None:
        candidates = [
            (family, index)
            for index in range(6)
            for family in ("a", "b")
        ]
        selected = schema_quota_score_fill(
            candidates,
            category=lambda item: item[0],
            category_order=("a", "b"),
            limit=8,
        )
        self.assertEqual(selected[:8], candidates[:8])

    def test_schema_quota_can_preserve_local_structural_order(self) -> None:
        candidates = [("a", 2), ("b", 2), ("a", 0), ("b", 0), ("a", 1), ("b", 1)]
        selected = schema_quota_score_fill(
            candidates,
            category=lambda item: item[0],
            category_order=("a", "b"),
            limit=4,
            within_category_key=lambda item: item[1],
        )
        self.assertEqual(selected, [("a", 0), ("b", 0), ("a", 1), ("b", 1)])

    def test_schema_quota_can_split_budget_between_coverage_and_score(self) -> None:
        candidates = [("a", 9), ("a", 0), ("b", 0), ("b", 1), ("a", 1), ("b", 2)]
        selected = schema_quota_score_fill(
            candidates,
            category=lambda item: item[0],
            category_order=("a", "b"),
            limit=4,
            within_category_key=lambda item: item[1],
            quota_fraction=0.5,
        )
        self.assertEqual(selected, [("a", 0), ("b", 0), ("a", 9), ("b", 1)])

    def test_capability_preserving_order_keeps_each_agent_frontier(self) -> None:
        views = (
            build_candidate_local_view(
                agent_id="left", formal_language="left", scores={"c": 1.0, "a": 0.2}
            ),
            build_candidate_local_view(
                agent_id="right", formal_language="right", scores={"d": 1.0, "b": 0.2}
            ),
        )
        ordered = capability_preserving_candidate_order(("a", "b", "c", "d"), views)
        self.assertEqual(ordered[:3], ("a", "c", "d"))
        self.assertEqual(set(ordered), {"a", "b", "c", "d"})


if __name__ == "__main__":
    unittest.main()
