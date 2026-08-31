"""Audit CADTestBench programs against MORTRA's finite engineering language.

This is a structural coverage audit, not a CADTestBench correctness score.  It
parses method calls without executing submitted programs and records exactly which
CadQuery operations have a direct MORTRA compilation route.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
import json
from pathlib import Path
import subprocess
from typing import Iterable


BASIS_METHODS: dict[str, str] = {
    "translate": "transform",
    "rotate": "transform",
    "transformed": "transform",
    "moved": "transform",
    "center": "transform",
    "array": "transform",
    "pushPoints": "transform",
    "scale": "transform",
    "mirror": "transform",
    "extrude": "sweep",
    "sweep": "sweep",
    "revolve": "sweep",
    "loft": "sweep",
    "twistExtrude": "sweep",
    "fillet": "sweep",
    "shell": "sweep",
    "offset2D": "sweep",
    "union": "combine",
    "cut": "combine",
    "intersect": "combine",
    "fuse": "combine",
    "add": "combine",
    "combine": "combine",
    "hole": "combine",
    "cutBlind": "combine",
    "cutThruAll": "combine",
    "faces": "select",
    "edges": "select",
    "vertices": "select",
    "solids": "select",
    "workplane": "slice",
}

# These calls describe finite input cells or coordinate frames rather than new
# morphisms.  Every entry has a compilation into the current data-only grammar.
RUNTIME_DATA_METHODS = {
    "Workplane",
    "Plane",
    "Location",
    "Sketch",
    "circle",
    "rect",
    "polygon",
    "polyline",
    "lineTo",
    "moveTo",
    "close",
    "box",
    "cylinder",
    "makeBox",
    "wire",
    "face",
    "placeSketch",
    "reset",
    "push",
    "threePointArc",
    "radiusArc",
}

# Generic input-curve gaps.  Adding these would extend data, not the eight-op
# morphism basis, but the declarative runtime does not execute them yet.
FINITE_DATA_GAPS = {
    "tangentArcPoint",
    "arc",
    "ellipse",
    "spline",
}

# Feature operations whose decomposition into the eight operations is not yet in
# the public executor.  They must remain visible rather than being over-claimed.
RUNTIME_OPERATION_GAPS = {
    "chamfer",
    "split",
    "interpPlate",
    "text",
}

NON_CONSTRUCTION_METHODS = {
    "export",
    "val",
    "vals",
    "size",
    "BoundingBox",
    "Volume",
    "Area",
    "Center",
    "CenterOfBoundBox",
    "centerOfMass",
    "isInside",
    "facesIntersectedByLine",
    "findSolid",
    "normalAt",
    "norm",
    "dot",
    "sqrt",
    "sin",
    "cos",
    "tan",
    "asin",
    "acos",
    "atan2",
    "radians",
    "degrees",
    "linspace",
    "append",
    "newObject",
    "Shape",
    "Vector",
    "X",
    "Y",
}


def call_methods(tree: ast.AST) -> Iterable[tuple[str, bool]]:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute):
            yield node.func.attr, True
        elif isinstance(node.func, ast.Name):
            yield node.func.id, False


def classify(method: str, *, is_attribute: bool = True) -> tuple[str, str | None]:
    if method in BASIS_METHODS:
        return "runtime_basis", BASIS_METHODS[method]
    if method in RUNTIME_DATA_METHODS:
        return "runtime_data", None
    if method in FINITE_DATA_GAPS:
        return "finite_data_gap", None
    if method in RUNTIME_OPERATION_GAPS:
        return "runtime_operation_gap", None
    if method in NON_CONSTRUCTION_METHODS:
        return "non_construction", None
    # Bare calls are Python helpers, assertions, or locally defined assembly
    # functions. CADQuery's construction API is method/constructor based and its
    # allowed constructors are listed explicitly above.
    if not is_attribute:
        return "non_construction", None
    return "unclassified", None


def git_metadata(root: Path) -> dict[str, str | None]:
    """Record a reproducible source identity without publishing a local path."""

    def read(*arguments: str) -> str | None:
        try:
            result = subprocess.run(
                ["git", "-C", str(root), *arguments],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return result.stdout.strip() or None

    return {
        "dataset": root.name,
        "repository": read("remote", "get-url", "origin"),
        "revision": read("rev-parse", "HEAD"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cadtestbench", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    files = sorted(args.cadtestbench.glob("baselines/**/gpt_generated.py"))
    methods: Counter[tuple[str, str]] = Counter()
    file_classes: dict[str, Counter[str]] = {}
    parse_errors: list[dict[str, str]] = []
    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError as exc:
            parse_errors.append({"path": str(path), "error": str(exc)})
            continue
        local = Counter(call_methods(tree))
        classes = Counter()
        for (method, is_attribute), count in local.items():
            category, _ = classify(method, is_attribute=is_attribute)
            classes[category] += count
            methods[(category, method)] += count
        file_classes[str(path)] = classes

    category_counts: Counter[str] = Counter()
    basis_counts: Counter[str] = Counter()
    category_methods: dict[str, Counter[str]] = defaultdict(Counter)
    for (category, method), count in methods.items():
        _, basis = classify(method, is_attribute=category != "non_construction")
        category_counts[category] += count
        category_methods[category][method] += count
        if basis:
            basis_counts[basis] += count

    construction_categories = {
        "runtime_basis",
        "runtime_data",
        "finite_data_gap",
        "runtime_operation_gap",
        "unclassified",
    }
    construction_calls = sum(
        count
        for category, count in category_counts.items()
        if category in construction_categories
    )
    covered_calls = category_counts["runtime_basis"] + category_counts["runtime_data"]
    files_with_only_covered_construction = 0
    for classes in file_classes.values():
        if not any(
            classes[category]
            for category in ("finite_data_gap", "runtime_operation_gap", "unclassified")
        ):
            files_with_only_covered_construction += 1

    report = {
        "audit": "cadtestbench-operator-coverage-v2",
        "scope": "AST method-call coverage only; programs were not scored for CAD correctness",
        "source": git_metadata(args.cadtestbench.resolve()),
        "program_files": len(files),
        "parsed_files": len(file_classes),
        "parse_errors": parse_errors,
        "method_calls": sum(methods.values()),
        "construction_calls": construction_calls,
        "runtime_covered_construction_calls": covered_calls,
        "runtime_covered_construction_call_ratio": (
            covered_calls / construction_calls if construction_calls else 0.0
        ),
        "files_with_only_runtime_covered_construction": files_with_only_covered_construction,
        "files_with_only_runtime_covered_construction_ratio": (
            files_with_only_covered_construction / len(file_classes)
            if file_classes
            else 0.0
        ),
        "category_counts": dict(sorted(category_counts.items())),
        "basis_operation_counts": dict(sorted(basis_counts.items())),
        "methods_by_category": {
            category: [
                {"method": method, "count": count}
                for method, count in counter.most_common()
            ]
            for category, counter in sorted(category_methods.items())
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "program_files",
        "parsed_files",
        "construction_calls",
        "runtime_covered_construction_calls",
        "runtime_covered_construction_call_ratio",
        "files_with_only_runtime_covered_construction",
        "files_with_only_runtime_covered_construction_ratio",
    )}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
