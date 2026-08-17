from __future__ import annotations

import unittest

from worker.backend.geometry_proof_hypergraph import Atom, Theorem
from worker.backend.symbolic_sheaf_coordination import (
    PredicateSignature,
    RuleClosureAdapter,
    TypedVocabulary,
)
from worker.backend.typed_logic_circuit import (
    compile_typed_proof_circuit,
    schedule_circuit,
)


def atom(name: str, *arguments: str) -> Atom:
    return Atom(name, tuple(arguments)).canonical()


def reachability_case(prefix: str, distractors: int = 8):
    chain = [f"{prefix}_n{i}" for i in range(5)]
    noise = [f"{prefix}_d{i}" for i in range(2 * distractors)]
    entities = chain + noise + [f"{prefix}_isolated"]
    givens = [atom("active", chain[0])]
    givens.extend(atom("edge", left, right) for left, right in zip(chain, chain[1:]))
    for index in range(distractors):
        givens.append(atom("active", noise[2 * index]))
        givens.append(atom("edge", noise[2 * index], noise[2 * index + 1]))
    agent = RuleClosureAdapter(
        "reachability",
        (Theorem(
            "advance",
            (atom("active", "?A"), atom("edge", "?A", "?B")),
            atom("active", "?B"),
        ),),
        imports={"active", "edge"},
        exports={"active"},
    )
    vocabulary = TypedVocabulary(
        signatures={
            "active": PredicateSignature("active", ("Node",)),
            "edge": PredicateSignature("edge", ("Node", "Node")),
        },
        entity_sorts={entity: "Node" for entity in entities},
    )
    return vocabulary, (agent,), tuple(givens), atom("active", chain[-1]), atom("active", entities[-1])


class TypedLogicCircuitTest(unittest.TestCase):
    def test_argument_aware_circuit_solves_long_chain_under_exact_budget(self) -> None:
        vocabulary, agents, givens, goal, _ = reachability_case("heldout", distractors=12)
        circuit = compile_typed_proof_circuit(givens, goal, agents, max_rounds=8)

        result = schedule_circuit(
            circuit,
            vocabulary,
            agents,
            mode="circuit",
            budget_per_round=1,
            max_rounds=4,
        )

        self.assertTrue(circuit.provable)
        self.assertTrue(result.solved)
        self.assertTrue(result.replayed)
        self.assertEqual(result.transmitted, 4)

    def test_predicate_collapse_is_not_a_sound_negative_test(self) -> None:
        vocabulary, agents, givens, _, negative_goal = reachability_case("negative")
        circuit = compile_typed_proof_circuit(givens, negative_goal, agents, max_rounds=8)
        theorems = tuple(theorem for agent in agents for theorem in agent.theorems)

        result = schedule_circuit(
            circuit,
            vocabulary,
            agents,
            mode="circuit",
            budget_per_round=1,
            max_rounds=8,
        )

        self.assertFalse(circuit.provable)
        self.assertTrue(circuit.predicate_abstraction_provable(theorems))
        self.assertFalse(result.solved)
        self.assertEqual(result.transmitted, 0)

    def test_entity_renaming_preserves_circuit_shape_and_result(self) -> None:
        left = reachability_case("alpha", distractors=6)
        right = reachability_case("omega", distractors=6)
        circuits = [
            compile_typed_proof_circuit(case[2], case[3], case[1], max_rounds=8)
            for case in (left, right)
        ]

        self.assertEqual(len(circuits[0].gates), len(circuits[1].gates))
        self.assertEqual(circuits[0].compile_matches, circuits[1].compile_matches)
        self.assertEqual(len(circuits[0].proof_slice()), len(circuits[1].proof_slice()))
        for case, circuit in zip((left, right), circuits):
            result = schedule_circuit(
                circuit,
                case[0],
                case[1],
                mode="circuit",
                budget_per_round=1,
                max_rounds=4,
            )
            self.assertTrue(result.replayed)

    def test_top_one_provenance_does_not_mix_equal_cost_or_branches(self) -> None:
        rules = (
            Theorem("left-a", (atom("seed", "a"),), atom("left", "a")),
            Theorem("left-b", (atom("seed", "b"),), atom("left", "b")),
            Theorem("right-a", (atom("seed", "a"),), atom("right", "a")),
            Theorem("right-b", (atom("seed", "b"),), atom("right", "b")),
            Theorem(
                "finish-a",
                (atom("left", "a"), atom("right", "a")),
                atom("goal", "x"),
            ),
            Theorem(
                "finish-b",
                (atom("left", "b"), atom("right", "b")),
                atom("goal", "x"),
            ),
        )
        agent = RuleClosureAdapter(
            "or-branches",
            rules,
            imports={"seed", "left", "right"},
            exports={"left", "right", "goal"},
        )
        vocabulary = TypedVocabulary(
            signatures={
                name: PredicateSignature(name, ("Node",))
                for name in ("seed", "left", "right", "goal")
            },
            entity_sorts={"a": "Node", "b": "Node", "x": "Node"},
        )
        circuit = compile_typed_proof_circuit(
            (atom("seed", "a"), atom("seed", "b")),
            atom("goal", "x"),
            (agent,),
        )

        _atom_demand, gate_demand = circuit.backward_demands(top_k=1)
        demanded_finish = [
            gate
            for gate in circuit.gates
            if gate.conclusion == atom("goal", "x")
            and gate_demand.get(gate.key, 0.0) > 0.0
        ]
        result = schedule_circuit(
            circuit,
            vocabulary,
            (agent,),
            mode="circuit",
            budget_per_round=1,
            max_rounds=3,
        )

        self.assertEqual(len(demanded_finish), 1)
        self.assertTrue(result.solved)
        self.assertTrue(result.replayed)

        soft_result = schedule_circuit(
            circuit,
            vocabulary,
            (agent,),
            mode="circuit_soft",
            budget_per_round=1,
            max_rounds=3,
        )
        self.assertFalse(soft_result.solved)


if __name__ == "__main__":
    unittest.main()
