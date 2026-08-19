"""Validation for proof-dependency graphs used by generated problems."""
from __future__ import annotations

from collections import Counter, deque
from typing import Any


def certify_proof_graph(graph: Any) -> dict[str, Any]:
    """Return a structural certificate; never infer a graph from a flat chain."""

    if not isinstance(graph, dict):
        return {
            "present": False,
            "valid_dag": False,
            "interaction_verified": False,
            "reason": "proof_graph_missing",
            "node_count": 0,
            "edge_count": 0,
            "merge_count": 0,
        }

    raw_nodes = graph.get("nodes") or []
    raw_edges = graph.get("edges") or []
    nodes = {
        str(node.get("id")): node
        for node in raw_nodes
        if isinstance(node, dict) and node.get("id") is not None
    }
    if len(nodes) != len(raw_nodes):
        return {
            "present": True,
            "valid_dag": False,
            "interaction_verified": False,
            "reason": "duplicate_or_invalid_node",
            "node_count": len(nodes),
            "edge_count": len(raw_edges),
            "merge_count": 0,
        }

    outgoing: dict[str, list[str]] = {node_id: [] for node_id in nodes}
    incoming = Counter({node_id: 0 for node_id in nodes})
    for edge in raw_edges:
        if not isinstance(edge, dict):
            continue
        source = str(edge.get("source"))
        target = str(edge.get("target"))
        if source not in nodes or target not in nodes:
            return {
                "present": True,
                "valid_dag": False,
                "interaction_verified": False,
                "reason": "dangling_edge",
                "node_count": len(nodes),
                "edge_count": len(raw_edges),
                "merge_count": 0,
            }
        outgoing[source].append(target)
        incoming[target] += 1

    queue = deque(node_id for node_id in nodes if incoming[node_id] == 0)
    indegree = incoming.copy()
    visited = 0
    while queue:
        node_id = queue.popleft()
        visited += 1
        for target in outgoing[node_id]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    valid_dag = visited == len(nodes)
    roots = [node_id for node_id in nodes if incoming[node_id] == 0]
    terminals = [
        node_id
        for node_id, node in nodes.items()
        if node.get("kind") in {"query", "conclusion"}
    ]
    merges = [node_id for node_id in nodes if incoming[node_id] >= 2]

    def reaches_terminal(root: str) -> bool:
        seen = {root}
        frontier = [root]
        while frontier:
            current = frontier.pop()
            if current in terminals:
                return True
            for target in outgoing[current]:
                if target not in seen:
                    seen.add(target)
                    frontier.append(target)
        return False

    required_roots = [
        node_id
        for node_id in roots
        if nodes[node_id].get("kind") in {"object", "premise", "constraint"}
    ]
    interaction_verified = bool(
        valid_dag
        and len(required_roots) >= 2
        and terminals
        and merges
        and all(reaches_terminal(root) for root in required_roots)
    )
    reason = "interaction_verified" if interaction_verified else "no_converging_constraints"
    if not valid_dag:
        reason = "cycle_detected"
    elif not terminals:
        reason = "terminal_missing"

    return {
        "present": True,
        "valid_dag": valid_dag,
        "interaction_verified": interaction_verified,
        "reason": reason,
        "node_count": len(nodes),
        "edge_count": len(raw_edges),
        "root_count": len(required_roots),
        "merge_count": len(merges),
        "terminal_count": len(terminals),
    }
