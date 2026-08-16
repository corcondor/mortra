"""非LLM記号エージェント協調の最小反証実験を固定JSONへ出力する。"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from worker.backend.geometry_proof_hypergraph import (  # noqa: E402
    Atom,
    Theorem,
    euclidean_relation_theorems,
)
from worker.backend.symbolic_sheaf_coordination import (  # noqa: E402
    AgentProposal,
    ExactSheafCoordinator,
    LocalCertificate,
    PredicateSignature,
    RuleClosureAdapter,
    TypedVocabulary,
    allocate_consensus_budget,
    render_atom,
    synthesize_problem_from_coordination,
)


def atom(name: str, *arguments: str) -> Atom:
    return Atom(name, tuple(arguments))


def geometry_task():
    bank = {item.name: item for item in euclidean_relation_theorems()}
    agents = (
        RuleClosureAdapter(
            "relation-transport",
            [bank["perpendicular-transport-over-parallel"]],
            imports={"perp", "para"},
            exports={"perp"},
        ),
        RuleClosureAdapter(
            "incidence-closure",
            [bank["common-perpendicular-implies-parallel"]],
            imports={"perp"},
            exports={"para"},
        ),
    )
    labels = tuple("ABCDEFGH")
    vocabulary = TypedVocabulary(
        signatures={
            "perp": PredicateSignature("perp", ("Point",) * 4),
            "para": PredicateSignature("para", ("Point",) * 4),
        },
        entity_sorts={label: "Point" for label in labels},
    )
    return (
        "euclidean-relations",
        vocabulary,
        agents,
        (
            atom("perp", "A", "B", "C", "D"),
            atom("para", "C", "D", "E", "F"),
            atom("perp", "G", "H", "E", "F"),
        ),
        atom("para", "A", "B", "G", "H"),
    )


def arithmetic_task():
    agents = (
        RuleClosureAdapter(
            "gcd-projection",
            [
                Theorem(
                    "gcd-divides-left",
                    (atom("gcd", "?A", "?B", "?D"),),
                    atom("divides", "?D", "?A"),
                ),
                Theorem(
                    "gcd-divides-right",
                    (atom("gcd", "?A", "?B", "?D"),),
                    atom("divides", "?D", "?B"),
                ),
            ],
            imports={"gcd"},
            exports={"divides"},
        ),
        RuleClosureAdapter(
            "additive-divisibility",
            [Theorem(
                "common-divisor-closed-under-sum",
                (
                    atom("divides", "?D", "?A"),
                    atom("divides", "?D", "?B"),
                    atom("sum", "?A", "?B", "?S"),
                ),
                atom("divides", "?D", "?S"),
            )],
            imports={"divides", "sum"},
            exports={"divides"},
        ),
    )
    vocabulary = TypedVocabulary(
        signatures={
            "gcd": PredicateSignature("gcd", ("Natural",) * 3),
            "divides": PredicateSignature("divides", ("Natural",) * 2),
            "sum": PredicateSignature("sum", ("Natural",) * 3),
        },
        entity_sorts={value: "Natural" for value in ("6", "30", "42", "72")},
    )
    return (
        "integer-relations",
        vocabulary,
        agents,
        (atom("gcd", "30", "42", "6"), atom("sum", "30", "42", "72")),
        atom("divides", "6", "72"),
    )


def set_task():
    agents = (
        RuleClosureAdapter(
            "order-closure",
            [Theorem(
                "subset-transitivity",
                (atom("subset", "?A", "?B"), atom("subset", "?B", "?C")),
                atom("subset_span", "?A", "?C"),
            )],
            imports={"subset"},
            exports={"subset_span"},
        ),
        RuleClosureAdapter(
            "disjointness-transport",
            [Theorem(
                "disjointness-restriction",
                (atom("subset_span", "?A", "?C"), atom("disjoint", "?C", "?D")),
                atom("disjoint", "?A", "?D"),
            )],
            imports={"subset_span", "disjoint"},
            exports={"disjoint"},
        ),
    )
    vocabulary = TypedVocabulary(
        signatures={
            "subset": PredicateSignature("subset", ("Set", "Set")),
            "subset_span": PredicateSignature("subset_span", ("Set", "Set")),
            "disjoint": PredicateSignature("disjoint", ("Set", "Set")),
        },
        entity_sorts={label: "Set" for label in "ABCD"},
    )
    return (
        "set-relations",
        vocabulary,
        agents,
        (atom("subset", "A", "B"), atom("subset", "B", "C"), atom("disjoint", "C", "D")),
        atom("disjoint", "A", "D"),
    )


class InvalidAgent:
    def __init__(self, goal_predicate: str, visible_predicates: set[str]) -> None:
        self.agent_id = "invalid-certificate-control"
        self.imports = frozenset(visible_predicates)
        self.exports = frozenset({goal_predicate})

    def propose(self, facts, goal, *, round_index):
        return AgentProposal((LocalCertificate(
            agent_id=self.agent_id,
            rule_name="unsupported-assertion",
            conclusion=goal,
            premises=(),
            native_payload={"round": round_index},
        ),))

    def verify(self, certificate, facts):
        return False


def naive_blackboard_accepts_goal(invalid_agent, givens, goal) -> bool:
    proposal = invalid_agent.propose(frozenset(givens), goal, round_index=1)
    return any(item.conclusion.canonical() == goal.canonical() for item in proposal.certificates)


def run_task(task):
    name, vocabulary, agents, givens, goal = task
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
    invalid = InvalidAgent(goal.predicate, set(vocabulary.signatures))
    fault_tolerant = ExactSheafCoordinator(vocabulary, [invalid, *agents]).solve(givens, goal)
    invalid_only = ExactSheafCoordinator(vocabulary, [invalid]).solve(givens, goal)
    generated = synthesize_problem_from_coordination(coordinated)
    coordinated_keys = {
        (
            item.agent_id,
            item.rule_name,
            item.conclusion.canonical(),
            tuple(premise.canonical() for premise in item.premises),
        )
        for item in coordinated.certificates
    }
    native_keys = {
        (
            item.agent_id,
            item.rule_name,
            item.conclusion.canonical(),
            tuple(premise.canonical() for premise in item.premises),
        )
        for result in independent
        for item in result.certificates
    }
    dropout = {
        removed.agent_id: ExactSheafCoordinator(
            vocabulary,
            [agent for agent in agents if agent.agent_id != removed.agent_id],
        ).solve(givens, goal).solved
        for removed in agents
    }
    return {
        "task": name,
        "goal": render_atom(goal),
        "independent_solved": any(item.solved for item in independent),
        "independent_agent_results": {
            agent.agent_id: result.solved
            for agent, result in zip(agents, independent)
        },
        "coordinated_solved": coordinated.solved,
        "coordinated_replayed": coordinated.replayed,
        "native_certificates": len(native_keys),
        "native_certificates_preserved": len(native_keys & coordinated_keys),
        "capability_preserved": native_keys <= coordinated_keys,
        "coordination_rounds": len(coordinated.rounds),
        "proof_agents": sorted({item.agent_id for item in coordinated.proof_slice()}),
        "proof_rules": [item.rule_name for item in coordinated.proof_slice()],
        "dropout_solved": dropout,
        "fault_tolerant_solved": fault_tolerant.solved and fault_tolerant.replayed,
        "invalid_certificates_rejected": len(fault_tolerant.rejected),
        "invalid_only_solved": invalid_only.solved,
        "naive_blackboard_false_positive": naive_blackboard_accepts_goal(invalid, givens, goal),
        "generated_problem": None if generated is None else {
            "formal_statement": generated.formal_statement,
            "participating_agents": list(generated.participating_agents),
            "proof_depth": generated.proof_depth,
            "proof_steps": len(generated.proof),
        },
        "trace": [asdict(item) for item in coordinated.rounds],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "symbolic-sheaf-coordination-pilot-2026-08-15.json",
    )
    args = parser.parse_args()
    tasks = [geometry_task(), arithmetic_task(), set_task()]
    results = [run_task(task) for task in tasks]
    admm = allocate_consensus_budget({
        "newclid-view": {"construct": 0.8, "eliminate": 0.1, "formalize": 0.1},
        "gclc-view": {"construct": 0.1, "eliminate": 0.8, "formalize": 0.1},
        "euclean-view": {"construct": 0.1, "eliminate": 0.1, "formalize": 0.8},
    })
    report = {
        "experiment": "symbolic-sheaf-coordination-pilot-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "uses_llm": False,
        "external_benchmark": False,
        "claim_scope": (
            "機構検証のみ。GCLC/Newclid/TongGeometry/Eucleanの実エンジン統合や"
            "IMO-AG-30の正答率改善を示す結果ではない。"
        ),
        "tasks": results,
        "summary": {
            "task_count": len(results),
            "independent_solved": sum(item["independent_solved"] for item in results),
            "coordinated_solved": sum(item["coordinated_solved"] for item in results),
            "replayed": sum(item["coordinated_replayed"] for item in results),
            "capability_preserved": sum(item["capability_preserved"] for item in results),
            "generated_formal_problems": sum(item["generated_problem"] is not None for item in results),
            "fault_controls_rejected": sum(not item["invalid_only_solved"] for item in results),
            "naive_blackboard_false_positives": sum(item["naive_blackboard_false_positive"] for item in results),
        },
        "admm_budget_consensus": {
            "consensus": admm.consensus,
            "iterations": admm.iterations,
            "primal_residual": admm.primal_residual,
            "dual_residual": admm.dual_residual,
            "truth_decision": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
