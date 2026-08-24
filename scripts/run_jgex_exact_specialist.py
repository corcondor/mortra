"""Isolated CLI for MORTRA's exact JGEX elimination specialist."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from worker.backend.jgex_exact_constraint_bridge import (  # noqa: E402
    lower_jgex_to_exact_obligation,
)
from worker.backend.jgex_exact_solution_writer import (  # noqa: E402
    build_jgex_exact_solution_artifact,
)
from newclid.jgex.formulation import JGEXFormulation  # noqa: E402


def _replace_goal(text: str, goal: str) -> str:
    formulation = JGEXFormulation.from_text(text)
    setup = "; ".join(map(str, formulation.setup_clauses))
    if not setup:
        raise ValueError("goal override requires a nonempty JGEX setup")
    return f"{setup} ? {goal.strip()}"


def _write_payload(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--solution-markdown-output",
        type=Path,
        help=(
            "Optional readable solution path. By default a sibling "
            "<output stem>.solution.md file is written for every completed run."
        ),
    )
    parser.add_argument(
        "--progress-output",
        type=Path,
        help=(
            "Optional checkpoint file kept separate from the final proof. "
            "This remains readable if an external runner stops the process."
        ),
    )
    parser.add_argument(
        "--representation",
        choices=(
            "explicit",
            "relational",
            "local_relational",
            "goal_local_relational",
            "typed_relation_separator",
            "construction_block_dag",
        ),
        default="goal_local_relational",
    )
    parser.add_argument("--max-saturation-rounds", type=int, default=1)
    parser.add_argument("--local-max-steps", type=int)
    parser.add_argument("--local-max-output-terms", type=int, default=64)
    parser.add_argument("--local-max-resultant-degree", type=int, default=1)
    parser.add_argument(
        "--enable-affine-local-lemmas",
        action="store_true",
        help=(
            "Eliminate deterministic clause-local affine coordinates with "
            "replayable substitution certificates before terminal reduction."
        ),
    )
    parser.add_argument("--max-separator-variables", type=int, default=12)
    parser.add_argument("--local-prepass-max-separator-variables", type=int)
    parser.add_argument("--max-pairs-per-clique", type=int, default=4)
    parser.add_argument("--max-basis-size-per-clique", type=int, default=16)
    parser.add_argument("--terminal-max-pairs", type=int, default=64)
    parser.add_argument("--terminal-max-basis-size", type=int, default=32)
    parser.add_argument("--obligation-cost-slack", type=int, default=1)
    parser.add_argument(
        "--native-facts",
        type=Path,
        help="JSON array of typed Yuclid facts for typed_relation_separator.",
    )
    parser.add_argument(
        "--goal",
        help="Optional ground JGEX relation to certify instead of the source goal.",
    )
    parser.add_argument(
        "--guidance-relations",
        type=Path,
        help=(
            "Optional JSON array of open typed obligations used only to rank "
            "construction-block elimination; it does not add assumptions."
        ),
    )
    parser.add_argument(
        "--guidance-branches",
        type=Path,
        help=(
            "Optional JSON array of coherent AND branches. The outer array "
            "is OR; branch atoms are never flattened across alternatives."
        ),
    )
    args = parser.parse_args()
    progress_output = args.progress_output or args.output
    solution_markdown: str | None = None
    try:
        # Newclid's JGEX parser treats a trailing line break after the goal as
        # an additional empty clause.  Keep the mathematical payload intact
        # while removing file-format whitespace at this process boundary.
        source = args.input.read_text(encoding="utf-8").strip()
        if args.representation == "typed_relation_separator":
            from worker.backend.geometry_proof_hypergraph import Atom
            from worker.backend.typed_relation_separator import (
                certify_typed_relation_separator,
            )

            if not args.goal or args.native_facts is None:
                raise ValueError(
                    "typed_relation_separator requires --goal and --native-facts"
                )
            raw_facts = json.loads(args.native_facts.read_text(encoding="utf-8"))
            native_facts = tuple(
                Atom(
                    str(item["predicate"]),
                    tuple(map(str, item["arguments"])),
                )
                for item in raw_facts
            )
            goal_parts = args.goal.split()
            if len(goal_parts) < 2:
                raise ValueError("goal must contain a predicate and arguments")
            certificate = certify_typed_relation_separator(
                source,
                Atom(goal_parts[0], tuple(goal_parts[1:])),
                native_facts,
            )
        elif args.representation == "construction_block_dag":
            from worker.backend.construction_block_proof_dag import (
                certify_construction_block_proof_dag,
            )

            if args.goal:
                source = _replace_goal(source, args.goal)
            guidance_relations: tuple[tuple[str, tuple[str, ...]], ...] = ()
            if args.guidance_relations is not None:
                raw_guidance = json.loads(
                    args.guidance_relations.read_text(encoding="utf-8")
                )
                guidance_relations = tuple(
                    (
                        str(item["predicate"]),
                        tuple(map(str, item["arguments"])),
                    )
                    for item in raw_guidance
                )
            guidance_branches: tuple[
                tuple[tuple[str, tuple[str, ...]], ...], ...
            ] = ()
            if args.guidance_branches is not None:
                raw_branches = json.loads(
                    args.guidance_branches.read_text(encoding="utf-8")
                )
                guidance_branches = tuple(
                    tuple(
                        (
                            str(item["predicate"]),
                            tuple(map(str, item["arguments"])),
                        )
                        for item in branch
                    )
                    for branch in raw_branches
                )
            progress_history: list[dict[str, object]] = []
            partial_local_nodes: list[dict[str, object]] = []
            partial_separator_nodes: list[dict[str, object]] = []
            partial_root: dict[str, object] = {
                "node_id": "root:checkpoint",
                "remaining_polynomials": [],
                "typed_relation_certificates": [],
            }

            def checkpoint(event: dict[str, object]) -> None:
                event = dict(event)
                checkpoint_node = event.pop("checkpoint_node", None)
                stage = str(event.get("stage", ""))
                if isinstance(checkpoint_node, dict):
                    if stage == "local_prepass_step_completed":
                        checkpoint_node = {
                            **checkpoint_node,
                            "node_id": (
                                f"checkpoint:local:{len(partial_local_nodes)}:"
                                f"{checkpoint_node.get('variable', 'unknown')}"
                            ),
                            "typed_relation_certificates": [],
                        }
                        partial_local_nodes.append(checkpoint_node)
                    elif stage == "clique_completed":
                        checkpoint_node = {
                            **checkpoint_node,
                            "node_id": (
                                f"checkpoint:separator:{len(partial_separator_nodes)}:"
                                f"{checkpoint_node.get('variable', 'unknown')}"
                            ),
                            "typed_relation_certificates": [],
                        }
                        partial_separator_nodes.append(checkpoint_node)
                if stage == "terminal_started":
                    partial_root.update(
                        {
                            "remaining_polynomials": list(
                                event.get("remaining_polynomials", [])
                            ),
                            "remaining_variables": list(
                                event.get("remaining_variables", [])
                            ),
                        }
                    )
                progress_history.append(event)
                replayed_nodes = (*partial_local_nodes, *partial_separator_nodes)
                _write_payload(
                    progress_output,
                    {
                        "status": "running",
                        "progress": progress_history[-64:],
                        "partial_certificate": {
                            "local_elimination_nodes": partial_local_nodes,
                            "separator_nodes": partial_separator_nodes,
                            "root": partial_root,
                            "all_local_certificates_replayed": all(
                                node.get("replayed") is True
                                for node in replayed_nodes
                            ),
                            "checkpoint_only": True,
                        },
                    },
                )

            certificate = certify_construction_block_proof_dag(
                source,
                max_separator_variables=args.max_separator_variables,
                local_prepass_max_separator_variables=(
                    args.local_prepass_max_separator_variables
                ),
                max_pairs_per_clique=args.max_pairs_per_clique,
                max_basis_size_per_clique=args.max_basis_size_per_clique,
                terminal_max_pairs=args.terminal_max_pairs,
                terminal_max_basis_size=args.terminal_max_basis_size,
                guidance_relations=guidance_relations,
                guidance_relation_branches=guidance_branches,
                obligation_cost_slack=args.obligation_cost_slack,
                progress_callback=checkpoint,
            )
        else:
            if args.goal:
                source = _replace_goal(source, args.goal)
            progress_history: list[dict[str, object]] = []

            def checkpoint(event: dict[str, object]) -> None:
                progress_history.append(dict(event))
                _write_payload(
                    progress_output,
                    {
                        "status": "running",
                        "latest_stage": event.get("stage"),
                        "progress": progress_history[-64:],
                    },
                )

            certificate = lower_jgex_to_exact_obligation(
                source,
                representation=args.representation,
                max_saturation_rounds=args.max_saturation_rounds,
                local_max_steps=args.local_max_steps,
                local_max_output_terms=args.local_max_output_terms,
                local_max_resultant_degree=args.local_max_resultant_degree,
                enable_affine_local_lemmas=args.enable_affine_local_lemmas,
                progress_callback=checkpoint,
            )
        certificate_payload = asdict(certificate)
        solution = build_jgex_exact_solution_artifact(source, certificate_payload)
        payload = {
            "status": "proved" if certificate.exact_replay else "unproved",
            "certificate": certificate_payload,
            "solution": solution.to_dict(),
        }
        solution_markdown = solution.to_markdown()
    except ValueError as exc:
        payload = {"status": "unsupported", "reason": str(exc)}
    except Exception as exc:
        payload = {
            "status": "execution_error",
            "reason": f"{type(exc).__name__}: {exc}",
        }
    _write_payload(args.output, payload)
    if solution_markdown is not None:
        markdown_output = (
            args.solution_markdown_output
            or args.output.with_suffix(".solution.md")
        )
        _write_text(markdown_output, solution_markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
