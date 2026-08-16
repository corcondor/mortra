from __future__ import annotations

import unittest

import numpy as np

from worker.backend.geometry_proof_hypergraph import Atom, Theorem
from worker.backend.symbolic_sheaf_coordination import (
    ExactSheafCoordinator,
    PredicateSignature,
    RuleClosureAdapter,
    TypedVocabulary,
)
from worker.backend.symbolic_sheaf_learning import (
    BudgetedSheafCoordinator,
    LinearSymbolicSheafADMM,
    ProofFlowLearner,
)


def atom(name: str, *arguments: str) -> Atom:
    return Atom(name, tuple(arguments))


def fixture():
    first = RuleClosureAdapter(
        "first",
        [Theorem("lift", (atom("seed", "?X"),), atom("bridge", "?X"))],
        imports={"seed"},
        exports={"bridge"},
    )
    second = RuleClosureAdapter(
        "second",
        [Theorem("finish", (atom("bridge", "?X"),), atom("goal", "?X"))],
        imports={"bridge"},
        exports={"goal"},
    )
    vocabulary = TypedVocabulary(
        signatures={
            name: PredicateSignature(name, ("Object",))
            for name in ("seed", "bridge", "goal")
        },
        entity_sorts={"A": "Object", "B": "Object"},
    )
    return vocabulary, (first, second), (atom("seed", "A"), atom("seed", "B")), atom("goal", "A")


class SymbolicSheafLearningTest(unittest.TestCase):
    def test_admm_reduces_typed_edge_disagreement(self) -> None:
        vocabulary, agents, _givens, _goal = fixture()
        result = LinearSymbolicSheafADMM(
            agents,
            vocabulary.signatures,
            iterations=40,
        ).solve({"first": {"bridge": 1.0}, "second": {"bridge": 0.0}})
        self.assertTrue(result.trace)
        self.assertLess(result.trace[-1].sheaf_residual, 1.0)
        self.assertLess(result.trace[-1].primal_residual, 1e-8)
        self.assertLess(result.trace[-1].dual_residual, 1e-8)
        self.assertTrue(np.isfinite(result.z).all())

    def test_budgeted_coordination_replays_exact_certificates(self) -> None:
        vocabulary, agents, givens, goal = fixture()
        result = BudgetedSheafCoordinator(vocabulary, agents).solve(
            givens,
            goal,
            transfer_budget=1,
        )
        self.assertTrue(result.solved)
        self.assertTrue(result.replayed)
        self.assertEqual([item.rule_name for item in result.proof_slice()], ["lift", "finish"])

    def test_local_agents_exchange_only_over_restriction_edges(self) -> None:
        vocabulary, agents, givens, goal = fixture()
        result = BudgetedSheafCoordinator(
            vocabulary,
            agents,
            local_views=True,
        ).solve(givens, goal, transfer_budget=1)
        self.assertTrue(result.solved and result.replayed)
        self.assertEqual(result.peer_messages_total, 1)

    def test_learning_uses_structure_not_rule_name_or_entity_label(self) -> None:
        vocabulary, agents, givens, goal = fixture()
        strict = ExactSheafCoordinator(vocabulary, agents).solve(givens, goal, stop_on_goal=False)
        learner = ProofFlowLearner()
        learner.fit_episode(strict, agents)

        renamed_first = RuleClosureAdapter(
            "first",
            [Theorem("completely-renamed", (atom("seed", "?X"),), atom("bridge", "?X"))],
            imports={"seed"},
            exports={"bridge"},
        )
        renamed_second = RuleClosureAdapter(
            "second",
            [Theorem("another-name", (atom("bridge", "?X"),), atom("goal", "?X"))],
            imports={"bridge"},
            exports={"goal"},
        )
        renamed = (renamed_first, renamed_second)
        result = BudgetedSheafCoordinator(
            vocabulary,
            renamed,
            learner=learner,
        ).solve((atom("seed", "B"),), atom("goal", "B"), transfer_budget=1)
        self.assertTrue(result.solved and result.replayed)
        self.assertGreater(learner.rule_weight(result.proof_slice()[0]), 0.5)

    def test_nonshared_predicates_are_not_forced_to_full_consensus(self) -> None:
        vocabulary, agents, _givens, _goal = fixture()
        result = LinearSymbolicSheafADMM(agents, vocabulary.signatures).solve({
            "first": {"seed": 1.0},
            "second": {"goal": 1.0},
        })
        self.assertFalse(any(edge.predicate in {"seed", "goal"} for edge in result.edges))


if __name__ == "__main__":
    unittest.main()
