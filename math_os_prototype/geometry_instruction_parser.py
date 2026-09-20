"""Instruction parser and formal task specification generator from recognized geometric text.

Bridges recognized character strings from the geometric reader to formal point
construction tasks in MORTRA's relational DSL.
"""
from __future__ import annotations

from typing import Any, Mapping


# Grammar of geometric commands accepted by MORTRA
COMMAND_GRAMMAR = {
    "PERP": {
        "description": "Construct perpendicular foot from external point onto a line",
        "required_points": ["a", "b", "c"],
        "goals": [
            {"predicate": "coll", "points": ["u", "a", "b"]},
            {"predicate": "perp", "points": ["c", "u", "a", "b"]},
        ],
    },
    "MIDP": {
        "description": "Construct midpoint between two external points",
        "required_points": ["a", "b"],
        "goals": [
            {"predicate": "coll", "points": ["u", "a", "b"]},
            {"predicate": "cong", "points": ["u", "a", "u", "b"]},
        ],
    },
    "COLL": {
        "description": "Construct collinear point at equal distance (mirror)",
        "required_points": ["a", "b"],
        "goals": [
            {"predicate": "coll", "points": ["u", "a", "b"]},
            {"predicate": "cong", "points": ["u", "a", "a", "b"]},
        ],
    },
}


def parse_geometric_instruction(
    command_str: str,
    external_points: Mapping[str, Sequence[float | int]],
) -> dict[str, Any]:
    """Convert a recognized command string and external coordinates into a relational task.

    Parameters
    ----------
    command_str : str
        The recognized string from the geometric bitmap reader.
    external_points : Mapping[str, Sequence[float | int]]
        Explicitly provided external point coordinates that are NOT read from the image.

    Returns
    -------
    dict[str, Any]
        If valid: {"valid": True, "command": cmd, "task": task_dict, "notes": ...}
        If invalid: {"valid": False, "reason": ..., "task": None}
    """
    clean_cmd = command_str.strip().upper()

    if clean_cmd not in COMMAND_GRAMMAR:
        return {
            "valid": False,
            "command": clean_cmd,
            "reason": f"Unknown or unsupported geometric command: '{clean_cmd}'. Allowed commands: {list(COMMAND_GRAMMAR.keys())}",
            "task": None,
        }

    schema = COMMAND_GRAMMAR[clean_cmd]
    req_points = schema["required_points"]

    missing = [p for p in req_points if p not in external_points]
    if missing:
        return {
            "valid": False,
            "command": clean_cmd,
            "reason": f"Missing required external points for command '{clean_cmd}': {missing}. Required: {req_points}",
            "task": None,
        }

    # Extract required points
    points_dict = {p: list(external_points[p]) for p in req_points}

    task = {
        "points": points_dict,
        "goals": schema["goals"],
    }

    return {
        "valid": True,
        "command": clean_cmd,
        "description": schema["description"],
        "task": task,
        "external_inputs": points_dict,
    }
