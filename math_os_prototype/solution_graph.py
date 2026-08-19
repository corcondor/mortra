"""Solution graph construction for retrieval- and tool-driven solving."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SolutionNode:
    id: str
    kind: str
    label: str
    payload: dict[str, Any] = field(default_factory=dict)
    children: list["SolutionNode"] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "label": self.label,
            "payload": self.payload,
            "children": [child.to_dict() for child in self.children],
        }


@dataclass
class SolutionGraph:
    fingerprint: str
    status: str
    root: SolutionNode
    answer: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "fingerprint": self.fingerprint,
            "status": self.status,
            "answer": self.answer,
            "root": self.root.to_dict(),
        }


def build_solution_graph(
    problem: str,
    structural_ir: dict[str, Any],
    retrieval: dict[str, Any],
    math_search: dict[str, Any],
    web_solutions: dict[str, Any] | None = None,
) -> SolutionGraph:
    fingerprint = fingerprint_structure(structural_ir)
    root = SolutionNode(
        id="root",
        kind="problem",
        label="problem",
        payload={"text": problem, "fingerprint": fingerprint},
    )
    root.children.append(
        SolutionNode(
            id="structure",
            kind="structure",
            label="MathState",
            payload={
                "variables": structural_ir.get("variables", []),
                "relations": structural_ir.get("relations", []),
                "operations": structural_ir.get("operations", []),
                "tool_affordances": structural_ir.get("tool_affordances", []),
            },
        )
    )

    retrieval_node = SolutionNode(id="retrieval", kind="retrieval", label="retrieval candidates")
    for index, hit in enumerate(retrieval.get("hits", [])[:5], start=1):
        retrieval_node.children.append(
            SolutionNode(
                id=f"retrieval-{index}",
                kind="retrieval_hit",
                label=str(hit.get("title") or hit.get("url") or "hit"),
                payload=hit,
            )
        )
    root.children.append(retrieval_node)

    search_node = SolutionNode(id="search", kind="search", label="experiment tree")
    for index, action in enumerate(math_search.get("actions", [])[:16], start=1):
        result = action.get("result") if isinstance(action.get("result"), dict) else {}
        search_node.children.append(
            SolutionNode(
                id=f"action-{index}",
                kind="action",
                label=str(action.get("name")),
                payload={
                    "input_summary": action.get("input_summary"),
                    "verifier": action.get("verifier"),
                    "command": action.get("command"),
                    "status": action.get("status"),
                    "result_status": result.get("status"),
                    "result": result,
                },
            )
        )
    root.children.append(search_node)

    if web_solutions:
        web_node = SolutionNode(
            id="web-solutions",
            kind="web_solutions",
            label="web solution step trees",
            payload={"summary": web_solutions.get("summary", {}), "enabled": web_solutions.get("enabled", False)},
        )
        for index, item in enumerate(web_solutions.get("verified", [])[:6], start=1):
            web_node.children.append(
                SolutionNode(
                    id=f"web-verified-{index}",
                    kind="verified_web_solution",
                    label=str(item.get("source_url") or item.get("answer_id") or "web answer"),
                    payload=item,
                )
            )
        root.children.append(web_node)

    answer = math_search.get("answer")
    web_verified = bool(web_solutions and web_solutions.get("summary", {}).get("verified_or_sanity_checked", 0))
    status = "verified_candidate" if answer else "web_supported_candidate_tree" if web_verified else "candidate_tree"
    return SolutionGraph(fingerprint=fingerprint, status=status, root=root, answer=answer)


def fingerprint_structure(structural_ir: dict[str, Any]) -> str:
    payload = {
        "variables": structural_ir.get("variables", []),
        "relations": structural_ir.get("relations", []),
        "operations": structural_ir.get("operations", []),
        "quantities": structural_ir.get("quantities", []),
        "entities": structural_ir.get("entities", []),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def append_solution_graph(graph: SolutionGraph, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(graph.to_dict(), ensure_ascii=False) + "\n")
