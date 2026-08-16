from __future__ import annotations

import unittest

from worker.backend.geometry_proof_hypergraph import (
    Atom,
    Theorem,
    euclidean_relation_theorems,
)
from worker.backend.symbolic_sheaf_coordination import (
    AgentProposal,
    ExactSheafCoordinator,
    LocalCertificate,
    PredicateSignature,
    RuleClosureAdapter,
    TypedVocabulary,
    allocate_consensus_budget,
    synthesize_problem_from_coordination,
)


def atom(name: str, *arguments: str) -> Atom:
    return Atom(name, tuple(arguments))


def geometry_fixture(labels: tuple[str, ...] = tuple("ABCDEFGH")):
    a, b, c, d, e, f, g, h = labels
    theorem_bank = {item.name: item for item in euclidean_relation_theorems()}
    transport = RuleClosureAdapter(
        "transport-agent",
        [theorem_bank["perpendicular-transport-over-parallel"]],
        imports={"perp", "para"},
        exports={"perp"},
    )
    incidence = RuleClosureAdapter(
        "incidence-agent",
        [theorem_bank["common-perpendicular-implies-parallel"]],
        imports={"perp"},
        exports={"para"},
    )
    vocabulary = TypedVocabulary(
        signatures={
            "perp": PredicateSignature("perp", ("Point",) * 4),
            "para": PredicateSignature("para", ("Point",) * 4),
        },
        entity_sorts={label: "Point" for label in labels},
    )
    givens = (
        atom("perp", a, b, c, d),
        atom("para", c, d, e, f),
        atom("perp", g, h, e, f),
    )
    goal = atom("para", a, b, g, h)
    return vocabulary, (transport, incidence), givens, goal


def arithmetic_fixture():
    gcd_left = Theorem(
        "gcd-divides-left",
        (atom("gcd", "?A", "?B", "?D"),),
        atom("divides", "?D", "?A"),
    )
    gcd_right = Theorem(
        "gcd-divides-right",
        (atom("gcd", "?A", "?B", "?D"),),
        atom("divides", "?D", "?B"),
    )
    sum_closed = Theorem(
        "common-divisor-closed-under-sum",
        (
            atom("divides", "?D", "?A"),
            atom("divides", "?D", "?B"),
            atom("sum", "?A", "?B", "?S"),
        ),
        atom("divides", "?D", "?S"),
    )
    projection = RuleClosureAdapter(
        "gcd-projection-agent",
        [gcd_left, gcd_right],
        imports={"gcd"},
        exports={"divides"},
    )
    closure = RuleClosureAdapter(
        "additive-closure-agent",
        [sum_closed],
        imports={"divides", "sum"},
        exports={"divides"},
    )
    vocabulary = TypedVocabulary(
        signatures={
            "gcd": PredicateSignature("gcd", ("Natural",) * 3),
            "divides": PredicateSignature("divides", ("Natural",) * 2),
            "sum": PredicateSignature("sum", ("Natural",) * 3),
        },
        entity_sorts={value: "Natural" for value in ("6", "30", "42", "72")},
    )
    givens = (atom("gcd", "30", "42", "6"), atom("sum", "30", "42", "72"))
    goal = atom("divides", "6", "72")
    return vocabulary, (projection, closure), givens, goal


class InvalidGoalAgent:
    agent_id = "invalid-agent"
    imports = frozenset({"perp", "para"})
    exports = frozenset({"para"})

    def propose(self, facts, goal, *, round_index):
        return AgentProposal((LocalCertificate(
            agent_id=self.agent_id,
            rule_name="invented-rule",
            conclusion=goal,
            premises=(),
            native_payload={"round": round_index},
        ),))

    def verify(self, certificate, facts):
        return False


class SymbolicSheafCoordinationTest(unittest.TestCase):
    def test_geometry_requires_cross_agent_feedback(self) -> None:
        vocabulary, agents, givens, goal = geometry_fixture()
        independent = [
            ExactSheafCoordinator(vocabulary, [agent]).solve(givens, goal)
            for agent in agents
        ]
        self.assertFalse(any(result.solved for result in independent))

        coordinated = ExactSheafCoordinator(vocabulary, agents).solve(givens, goal)
        self.assertTrue(coordinated.solved)
        self.assertTrue(coordinated.replayed)
        self.assertEqual({item.agent_id for item in coordinated.proof_slice()}, {
            "transport-agent",
            "incidence-agent",
        })

    def test_same_coordinator_operates_on_arithmetic_relations(self) -> None:
        vocabulary, agents, givens, goal = arithmetic_fixture()
        independent = [
            ExactSheafCoordinator(vocabulary, [agent]).solve(givens, goal)
            for agent in agents
        ]
        self.assertFalse(any(result.solved for result in independent))

        coordinated = ExactSheafCoordinator(vocabulary, agents).solve(givens, goal)
        self.assertTrue(coordinated.solved)
        self.assertTrue(coordinated.replayed)
        self.assertEqual(len(coordinated.proof_slice()), 3)

    def test_invalid_agent_cannot_create_a_false_proof(self) -> None:
        vocabulary, agents, givens, goal = geometry_fixture()
        result = ExactSheafCoordinator(vocabulary, [InvalidGoalAgent(), *agents]).solve(givens, goal)
        self.assertTrue(result.solved)
        self.assertTrue(result.replayed)
        self.assertGreaterEqual(len(result.rejected), 1)
        self.assertNotIn("invalid-agent", {item.agent_id for item in result.proof_slice()})

    def test_label_renaming_does_not_change_the_proof_structure(self) -> None:
        first = geometry_fixture(tuple("ABCDEFGH"))
        second = geometry_fixture(tuple("PQRSTUVW"))
        results = [
            ExactSheafCoordinator(vocabulary, agents).solve(givens, goal)
            for vocabulary, agents, givens, goal in (first, second)
        ]
        self.assertTrue(all(result.solved and result.replayed for result in results))
        self.assertEqual(
            [item.rule_name for item in results[0].proof_slice()],
            [item.rule_name for item in results[1].proof_slice()],
        )

    def test_admm_allocates_budget_without_deciding_truth(self) -> None:
        result = allocate_consensus_budget({
            "newclid": {"construct": 0.9, "eliminate": 0.1, "formalize": 0.0},
            "gclc": {"construct": 0.1, "eliminate": 0.8, "formalize": 0.1},
            "euclean": {"construct": 0.0, "eliminate": 0.1, "formalize": 0.9},
        })
        self.assertAlmostEqual(sum(result.consensus.values()), 1.0, places=9)
        self.assertLess(result.primal_residual, 1e-7)
        self.assertLess(result.dual_residual, 1e-7)
        self.assertEqual(set(result.consensus), {"construct", "eliminate", "formalize"})

    def test_verified_proof_dag_can_be_reversed_into_a_problem(self) -> None:
        vocabulary, agents, givens, goal = arithmetic_fixture()
        result = ExactSheafCoordinator(vocabulary, agents).solve(givens, goal)
        candidate = synthesize_problem_from_coordination(result)
        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(candidate.conclusion, goal.canonical())
        self.assertEqual(len(candidate.participating_agents), 2)
        self.assertGreaterEqual(candidate.proof_depth, 2)
        self.assertIn("|- divides(6,72)", candidate.formal_statement)

    def test_cooperation_preserves_each_agents_native_certificates(self) -> None:
        vocabulary, agents, givens, goal = geometry_fixture()
        independent = [
            ExactSheafCoordinator(vocabulary, [agent]).solve(
                givens,
                goal,
                stop_on_goal=False,
            )
            for agent in agents
        ]
        coordinated = ExactSheafCoordinator(vocabulary, agents).solve(
            givens,
            goal,
            stop_on_goal=False,
        )
        native = {
            (item.agent_id, item.rule_name, item.conclusion, item.premises)
            for result in independent
            for item in result.certificates
        }
        shared = {
            (item.agent_id, item.rule_name, item.conclusion, item.premises)
            for item in coordinated.certificates
        }
        self.assertTrue(native)
        self.assertLessEqual(native, shared)


if __name__ == "__main__":
    unittest.main()
