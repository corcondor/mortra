"""Load and enforce membership of the frozen HAGeo benchmark split."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


def load_frozen_problem_names(path: Path) -> tuple[str, ...]:
    """Return a duplicate-free frozen problem list from JSON or plain text."""

    path = path.resolve()
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        raw_names = payload.get("problem_names")
        if raw_names is None:
            sets = payload.get("sets", {})
            raw_names = sets.get("frozen_problem_names")
        if not isinstance(raw_names, list):
            raise ValueError(f"frozen split has no problem_names list: {path}")
        names = tuple(map(str, raw_names))
        declared_total = payload.get("summary", {}).get("total")
        if declared_total is not None and int(declared_total) != len(names):
            raise ValueError(
                f"frozen split total mismatch: declared={declared_total}, "
                f"observed={len(names)}"
            )
    else:
        names = tuple(
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
    if not names:
        raise ValueError(f"frozen split is empty: {path}")
    if len(set(names)) != len(names):
        raise ValueError(f"frozen split contains duplicate problem names: {path}")
    return names


def require_frozen_membership(
    names: Iterable[str],
    frozen_names: Iterable[str],
    *,
    label: str,
) -> None:
    outside = sorted(set(map(str, names)) - set(map(str, frozen_names)))
    if outside:
        raise ValueError(
            f"{label} contains problems outside the frozen split: "
            + ", ".join(outside)
        )


__all__ = ["load_frozen_problem_names", "require_frozen_membership"]
