"""Typed MORTRA bridge to the official FormalGeo runtime.

The bridge has three strict boundaries:

1. Newclid-style point predicates are elaborated into FormalGeo point/line
   objects and an ordered, geometrically consistent construction program.
2. FormalGeo is executed in its own GPL process through JSON.
3. Returned AND/OR goals are translated back to typed MORTRA atoms.  A solved
   FormalGeo root is an external certificate candidate, not a native Newclid or
   GCLC certificate; downstream replay is still required.

No benchmark question, numeric answer, or problem-specific theorem is stored
here.  The mapping is defined only by relation signatures and object types.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations, permutations
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Iterable

from worker.backend.geometry_proof_hypergraph import Atom


DEFAULT_FORMALGEO_ROOT = (
    Path.home() / ".cache" / "mortra-research-sources" / "FormalGeo"
)

# FormalGeo's official parser accepts one non-space code point per object
# argument.  Keep point and line namespaces disjoint and reversible.
_POINT_SYMBOLS = tuple("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + tuple(
    "ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ"
)
_LINE_SYMBOLS = tuple("abcdefghijklmnopqrstuvwxyz") + tuple(
    "αβγδεζηθικλμνξοπρστυφχψω"
)


class FormalGeoElaborationError(ValueError):
    """The typed assumptions cannot yet be expressed as a sound construction."""


def _render_atom(atom: Atom) -> str:
    return f"{atom.predicate}({','.join(atom.arguments)})"


def _segment(left: str, right: str) -> tuple[str, str]:
    if left == right:
        raise FormalGeoElaborationError("a line segment requires two distinct points")
    return tuple(sorted((left, right)))


def _segments(atom: Atom) -> tuple[tuple[str, str], ...]:
    name = atom.predicate.lower()
    args = atom.arguments
    if name in {"para", "perp"} and len(args) == 4:
        return (_segment(args[0], args[1]), _segment(args[2], args[3]))
    if name == "eqangle" and len(args) == 8:
        return tuple(_segment(args[index], args[index + 1]) for index in range(0, 8, 2))
    if name == "coll" and len(args) == 3:
        return (_segment(args[0], args[1]),)
    return ()


@dataclass(frozen=True)
class FormalGeoRuntimeConfig:
    root: Path
    python_executable: Path
    gdl_path: Path
    adapter_script: Path
    timeout_seconds: float = 45.0

    @classmethod
    def detect(cls, *, timeout_seconds: float = 45.0) -> "FormalGeoRuntimeConfig":
        root = Path(os.environ.get("MORTRA_FORMALGEO_ROOT", DEFAULT_FORMALGEO_ROOT))
        python_executable = Path(
            os.environ.get(
                "MORTRA_FORMALGEO_PYTHON",
                root / ".venv-mortra" / "Scripts" / "python.exe",
            )
        )
        gdl_path = Path(
            os.environ.get("MORTRA_FORMALGEO_GDL", root / "tests" / "gdl.json")
        )
        adapter_script = Path(__file__).resolve().parents[2] / "scripts" / "run_formalgeo_runtime.py"
        return cls(
            root=root,
            python_executable=python_executable,
            gdl_path=gdl_path,
            adapter_script=adapter_script,
            timeout_seconds=timeout_seconds,
        )

    @property
    def available(self) -> bool:
        return all(
            path.is_file()
            for path in (self.python_executable, self.gdl_path, self.adapter_script)
        )


@dataclass(frozen=True)
class FormalGeoElaboration:
    facts: tuple[Atom, ...]
    goal: Atom
    constructions: tuple[str, ...]
    formal_goal: str
    point_to_object: tuple[tuple[str, str], ...]
    segment_to_object: tuple[tuple[tuple[str, str], str], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "facts": [_render_atom(atom) for atom in self.facts],
            "goal": _render_atom(self.goal),
            "constructions": list(self.constructions),
            "formal_goal": self.formal_goal,
            "point_to_object": dict(self.point_to_object),
            "segment_to_object": [
                {"segment": list(segment), "object": obj}
                for segment, obj in self.segment_to_object
            ],
        }


@dataclass(frozen=True)
class FormalGeoBridgeResult:
    available: bool
    elaborated: bool
    root_solved: bool
    replay_required: bool
    elaboration: FormalGeoElaboration | None
    translated_goals: tuple[dict[str, Any], ...]
    open_branches: tuple[tuple[Atom, ...], ...]
    runtime_trace: dict[str, Any]
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "elaborated": self.elaborated,
            "root_solved": self.root_solved,
            "replay_required": self.replay_required,
            "elaboration": self.elaboration.to_dict() if self.elaboration else None,
            "translated_goals": list(self.translated_goals),
            "open_branches": [
                [_render_atom(atom) for atom in branch] for branch in self.open_branches
            ],
            "runtime_trace": self.runtime_trace,
            "error": self.error,
        }


@dataclass(frozen=True)
class FormalGeoGoalExchange:
    """Goal-conditioned official-runtime proposals for downstream replay."""

    attempted: bool
    selected_facts: tuple[Atom, ...]
    results: tuple[FormalGeoBridgeResult, ...]
    obligation_branches: tuple[tuple[Atom, ...], ...]

    @property
    def official_solved(self) -> bool:
        return any(result.root_solved for result in self.results)

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempted": self.attempted,
            "selected_facts": [_render_atom(atom) for atom in self.selected_facts],
            "official_solved": self.official_solved,
            "accepted_as_mortra_solution": False,
            "acceptance_rule": (
                "FormalGeo output proposes typed obligations; Newclid/GCLC replay "
                "is required before MORTRA counts a solution"
            ),
            "obligation_branches": [
                [_render_atom(atom) for atom in branch]
                for branch in self.obligation_branches
            ],
            "results": [result.to_dict() for result in self.results],
        }


class _ConstructionPlanner:
    def __init__(self, facts: tuple[Atom, ...], goal: Atom):
        points = sorted(
            {
                argument
                for atom in (*facts, goal)
                for argument in atom.arguments
                if not argument.startswith("?")
            }
        )
        segments = sorted({segment for atom in (*facts, goal) for segment in _segments(atom)})
        if len(points) > len(_POINT_SYMBOLS):
            raise FormalGeoElaborationError(
                f"FormalGeo GDL supports at most {len(_POINT_SYMBOLS)} mapped points"
            )
        if len(segments) > len(_LINE_SYMBOLS):
            raise FormalGeoElaborationError(
                f"FormalGeo GDL supports at most {len(_LINE_SYMBOLS)} mapped lines"
            )
        self.point_map = {
            point: _POINT_SYMBOLS[index] for index, point in enumerate(points)
        }
        self.line_map = {
            segment: _LINE_SYMBOLS[index] for index, segment in enumerate(segments)
        }
        self.constructed_points: set[str] = set()
        self.constructed_lines: set[tuple[str, str]] = set()
        self.constructions: list[str] = []

    def point(self, point: str) -> str:
        try:
            return self.point_map[point]
        except KeyError as exc:
            raise FormalGeoElaborationError(f"unknown point: {point}") from exc

    def line(self, segment: tuple[str, str]) -> str:
        try:
            return self.line_map[segment]
        except KeyError as exc:
            raise FormalGeoElaborationError(f"unknown segment: {segment}") from exc

    def free_point(self, point: str) -> None:
        if point in self.constructed_points:
            return
        obj = self.point(point)
        self.constructions.append(f"Point({obj}):FreePoint({obj})")
        self.constructed_points.add(point)

    def constrained_point(self, point: str, constraint: str) -> None:
        if point in self.constructed_points:
            raise FormalGeoElaborationError(
                f"cannot attach a new assumption after point {point!r} was constructed"
            )
        obj = self.point(point)
        self.constructions.append(f"Point({obj}):{constraint}")
        self.constructed_points.add(point)

    def secant_line(self, segment: tuple[str, str]) -> None:
        if segment in self.constructed_lines:
            return
        left, right = segment
        self.free_point(left)
        self.free_point(right)
        line = self.line(segment)
        self.constructions.append(
            f"Line({line}):PointOnLine({self.point(left)},{line})"
            f"&PointOnLine({self.point(right)},{line})"
        )
        self.constructed_lines.add(segment)

    def related_line(
        self,
        segment: tuple[str, str],
        relation: str,
        other_line: str,
    ) -> None:
        if segment in self.constructed_lines:
            raise FormalGeoElaborationError(
                f"cannot attach {relation} after line {segment!r} was constructed"
            )
        left, right = segment
        if left in self.constructed_points and right in self.constructed_points:
            raise FormalGeoElaborationError(
                f"both endpoints of constrained line {segment!r} already exist"
            )
        anchor, moving = (left, right) if left in self.constructed_points else (right, left)
        if anchor not in self.constructed_points:
            self.free_point(anchor)
        line = self.line(segment)
        self.constructions.append(
            f"Line({line}):PointOnLine({self.point(anchor)},{line})"
            f"&{relation}({other_line},{line})"
        )
        self.constructed_lines.add(segment)
        self.constrained_point(moving, f"PointOnLine({self.point(moving)},{line})")

    def relation(self, atom: Atom) -> None:
        name = atom.predicate.lower()
        args = atom.arguments
        if name in {"para", "perp"} and len(args) == 4:
            first, second = _segments(atom)
            formal = "ParallelBetweenLine" if name == "para" else "PerpendicularBetweenLine"
            if first not in self.constructed_lines:
                self.secant_line(first)
            self.related_line(second, formal, self.line(first))
            return
        if name == "coll" and len(args) == 3:
            segment = _segment(args[0], args[1])
            self.secant_line(segment)
            self.constrained_point(
                args[2],
                f"PointOnLine({self.point(args[2])},{self.line(segment)})",
            )
            return
        if name == "cong" and len(args) == 4:
            for point in args[:3]:
                self.free_point(point)
            self.constrained_point(
                args[3],
                "EqualDistancePointToPoint("
                f"{self.point(args[0])},{self.point(args[1])},"
                f"{self.point(args[2])},{self.point(args[3])})",
            )
            return
        if name == "cyclic" and len(args) == 4:
            for point in args[:3]:
                self.free_point(point)
            self.constrained_point(
                args[3],
                "ConcyclicBetweenPoints("
                + ",".join(self.point(point) for point in args)
                + ")",
            )
            return
        if name == "eqangle" and len(args) == 8:
            lines = _segments(atom)
            for segment in lines[:3]:
                self.secant_line(segment)
            target = lines[3]
            if target in self.constructed_lines:
                raise FormalGeoElaborationError("target angle line was already constructed")
            left, right = target
            if left in self.constructed_points and right in self.constructed_points:
                raise FormalGeoElaborationError("target angle endpoints were already constructed")
            anchor, moving = (left, right) if left in self.constructed_points else (right, left)
            self.free_point(anchor)
            target_line = self.line(target)
            relation = "EqualAngle(" + ",".join(
                [*(self.line(segment) for segment in lines[:3]), target_line]
            ) + ")"
            self.constructions.append(
                f"Line({target_line}):PointOnLine({self.point(anchor)},{target_line})"
                f"&{relation}"
            )
            self.constructed_lines.add(target)
            self.constrained_point(moving, f"PointOnLine({self.point(moving)},{target_line})")
            return
        raise FormalGeoElaborationError(f"unsupported typed assumption: {_render_atom(atom)}")

    def ensure_goal_entities(self, goal: Atom) -> None:
        for point in goal.arguments:
            if not point.startswith("?"):
                self.free_point(point)
        for segment in _segments(goal):
            self.secant_line(segment)


def _formal_relation(
    atom: Atom,
    point_map: dict[str, str],
    line_map: dict[tuple[str, str], str],
) -> str:
    name = atom.predicate.lower()
    args = atom.arguments

    def point(value: str) -> str:
        return point_map[value]

    def line(left: str, right: str) -> str:
        return line_map[_segment(left, right)]

    if name == "para" and len(args) == 4:
        return f"ParallelBetweenLine({line(args[0],args[1])},{line(args[2],args[3])})"
    if name == "perp" and len(args) == 4:
        return f"PerpendicularBetweenLine({line(args[0],args[1])},{line(args[2],args[3])})"
    if name == "cong" and len(args) == 4:
        return "EqualDistancePointToPoint(" + ",".join(map(point, args)) + ")"
    if name == "cyclic" and len(args) == 4:
        return "ConcyclicBetweenPoints(" + ",".join(map(point, args)) + ")"
    if name == "eqangle" and len(args) == 8:
        lines = [line(args[index], args[index + 1]) for index in range(0, 8, 2)]
        return "EqualAngle(" + ",".join(lines) + ")"
    if name == "coll" and len(args) == 3:
        return f"PointOnLine({point(args[2])},{line(args[0],args[1])})"
    raise FormalGeoElaborationError(f"unsupported typed goal: {_render_atom(atom)}")


def elaborate_atoms(facts: Iterable[Atom], goal: Atom) -> FormalGeoElaboration:
    normalized_facts = tuple(atom.canonical() for atom in facts)
    normalized_goal = goal.canonical()
    planner = _ConstructionPlanner(normalized_facts, normalized_goal)
    for atom in normalized_facts:
        planner.relation(atom)
    planner.ensure_goal_entities(normalized_goal)
    formal_goal = _formal_relation(normalized_goal, planner.point_map, planner.line_map)
    return FormalGeoElaboration(
        facts=normalized_facts,
        goal=normalized_goal,
        constructions=tuple(planner.constructions),
        formal_goal=formal_goal,
        point_to_object=tuple(sorted(planner.point_map.items())),
        segment_to_object=tuple(sorted(planner.line_map.items())),
    )


def _restore_object(
    value: str,
    point_inverse: dict[str, str],
    line_inverse: dict[str, tuple[str, str]],
) -> str:
    if value in point_inverse:
        return point_inverse[value]
    if value in line_inverse:
        return "@line:" + ":".join(line_inverse[value])
    return value


def _linear_attribution_terms(
    expression: dict[str, Any],
    coefficient: Fraction = Fraction(1),
) -> dict[str, Fraction] | None:
    """Read a linear combination from the serialized FormalGeo SymPy AST."""

    kind = expression.get("kind")
    if kind == "symbol":
        return {str(expression["name"]): coefficient}
    if kind == "integer":
        return {} if int(expression["value"]) == 0 else None
    if kind == "rational":
        value = Fraction(
            int(expression["numerator"]), int(expression["denominator"])
        )
        return {} if value == 0 else None
    if kind == "add":
        result: dict[str, Fraction] = {}
        for argument in expression.get("args", []):
            terms = _linear_attribution_terms(argument, coefficient)
            if terms is None:
                return None
            for symbol, value in terms.items():
                result[symbol] = result.get(symbol, Fraction(0)) + value
        return {symbol: value for symbol, value in result.items() if value}
    if kind == "mul":
        scalar = coefficient
        symbolic: dict[str, Any] | None = None
        for argument in expression.get("args", []):
            argument_kind = argument.get("kind")
            if argument_kind == "integer":
                scalar *= int(argument["value"])
            elif argument_kind == "rational":
                scalar *= Fraction(
                    int(argument["numerator"]), int(argument["denominator"])
                )
            elif symbolic is None:
                symbolic = argument
            else:
                return None
        if symbolic is None:
            return {} if scalar == 0 else None
        return _linear_attribution_terms(symbolic, scalar)
    return None


def _split_attribution_symbol(symbol: str, suffix: str) -> tuple[str, str] | None:
    marker = "." + suffix
    if not symbol.endswith(marker):
        return None
    objects = symbol[: -len(marker)]
    if len(objects) != 2:
        return None
    return objects[0], objects[1]


def _lower_algebraic_equality(
    expression: dict[str, Any],
    point_inverse: dict[str, str],
    line_inverse: dict[str, tuple[str, str]],
) -> Atom | None:
    """Recover typed relations from equality of FormalGeo attributions."""

    terms = _linear_attribution_terms(expression)
    if terms is None or len(terms) != 2:
        return None
    ((left_symbol, left_coefficient), (right_symbol, right_coefficient)) = sorted(
        terms.items()
    )
    if left_coefficient != -right_coefficient:
        return None

    left_points = _split_attribution_symbol(left_symbol, "dpp")
    right_points = _split_attribution_symbol(right_symbol, "dpp")
    if left_points is not None and right_points is not None:
        objects = (*left_points, *right_points)
        if all(item in point_inverse for item in objects):
            return Atom(
                "cong", tuple(point_inverse[item] for item in objects)
            ).canonical()

    left_lines = _split_attribution_symbol(left_symbol, "ma")
    right_lines = _split_attribution_symbol(right_symbol, "ma")
    if left_lines is not None and right_lines is not None:
        objects = (*left_lines, *right_lines)
        if all(item in line_inverse for item in objects):
            arguments = tuple(
                point
                for line_object in objects
                for point in line_inverse[line_object]
            )
            return Atom("eqangle", arguments).canonical()
    return None


def _translate_atom(
    predicate: str,
    instance: Any,
    point_inverse: dict[str, str],
    line_inverse: dict[str, tuple[str, str]],
    algebraic_ast: dict[str, Any] | None = None,
) -> Atom:
    if predicate == "Eq" and algebraic_ast is not None:
        lowered = _lower_algebraic_equality(
            algebraic_ast, point_inverse, line_inverse
        )
        if lowered is not None:
            return lowered
    values = tuple(instance) if isinstance(instance, list) else (str(instance),)
    if predicate == "ParallelBetweenLine" and len(values) == 2:
        return Atom("para", (*line_inverse[values[0]], *line_inverse[values[1]])).canonical()
    if predicate == "PerpendicularBetweenLine" and len(values) == 2:
        return Atom("perp", (*line_inverse[values[0]], *line_inverse[values[1]])).canonical()
    if predicate == "EqualDistancePointToPoint" and len(values) == 4:
        return Atom("cong", tuple(point_inverse[item] for item in values)).canonical()
    if predicate == "ConcyclicBetweenPoints" and len(values) == 4:
        return Atom("cyclic", tuple(point_inverse[item] for item in values)).canonical()
    if predicate == "EqualAngle" and len(values) == 4:
        arguments = tuple(point for item in values for point in line_inverse[item])
        return Atom("eqangle", arguments).canonical()
    if predicate == "PointOnLine" and len(values) == 2 and values[1] in line_inverse:
        return Atom("coll", (*line_inverse[values[1]], point_inverse[values[0]])).canonical()
    return Atom(
        "formalgeo." + predicate.lower(),
        tuple(_restore_object(str(item), point_inverse, line_inverse) for item in values),
    )


def _translate_tree(
    tree: dict[str, Any],
    point_inverse: dict[str, str],
    line_inverse: dict[str, tuple[str, str]],
) -> dict[str, Any]:
    kind = tree["kind"]
    if kind == "atom":
        atom = _translate_atom(
            tree["predicate"],
            tree["instance"],
            point_inverse,
            line_inverse,
            tree.get("algebraic_ast"),
        )
        return {
            **tree,
            "atom": atom,
            "rendered_atom": _render_atom(atom),
        }
    if kind == "not":
        return {
            "kind": "not",
            "child": _translate_tree(tree["child"], point_inverse, line_inverse),
        }
    return {
        "kind": kind,
        "children": [
            _translate_tree(child, point_inverse, line_inverse)
            for child in tree["children"]
        ],
    }


def _open_dnf(tree: dict[str, Any], *, limit: int = 256) -> list[tuple[Atom, ...]]:
    kind = tree["kind"]
    if kind == "atom":
        return [()] if tree.get("status") == 1 else [(tree["atom"],)]
    if kind == "not":
        child = tree["child"]
        if child["kind"] == "atom":
            atom = child["atom"]
            return [(Atom("not." + atom.predicate, atom.arguments),)]
        return [(Atom("formalgeo.negated_tree", (json.dumps(child, default=str),)),)]
    children = tree["children"]
    if kind == "or":
        branches = [branch for child in children for branch in _open_dnf(child, limit=limit)]
        return branches[:limit]
    branches: list[tuple[Atom, ...]] = [()]
    for child in children:
        next_branches: list[tuple[Atom, ...]] = []
        for left in branches:
            for right in _open_dnf(child, limit=limit):
                next_branches.append(tuple(sorted(set((*left, *right)), key=_render_atom)))
                if len(next_branches) >= limit:
                    break
            if len(next_branches) >= limit:
                break
        branches = next_branches
    return branches


def _json_tree(tree: dict[str, Any]) -> dict[str, Any]:
    result = dict(tree)
    result.pop("atom", None)
    if "children" in result:
        result["children"] = [_json_tree(child) for child in result["children"]]
    if "child" in result:
        result["child"] = _json_tree(result["child"])
    return result


def run_formalgeo_bridge(
    facts: Iterable[Atom],
    goal: Atom,
    *,
    theorem_names: Iterable[str] = (),
    max_rounds: int = 4,
    config: FormalGeoRuntimeConfig | None = None,
    seed_offsets: Iterable[int] = (0,),
    elaboration_override: FormalGeoElaboration | None = None,
) -> FormalGeoBridgeResult:
    runtime = config or FormalGeoRuntimeConfig.detect()
    if not runtime.available:
        return FormalGeoBridgeResult(
            available=False,
            elaborated=False,
            root_solved=False,
            replay_required=True,
            elaboration=None,
            translated_goals=(),
            open_branches=(),
            runtime_trace={},
            error="FormalGeo runtime, GDL, or adapter script is unavailable",
        )
    if elaboration_override is None:
        try:
            elaboration = elaborate_atoms(facts, goal)
        except FormalGeoElaborationError as exc:
            return FormalGeoBridgeResult(
                available=True,
                elaborated=False,
                root_solved=False,
                replay_required=True,
                elaboration=None,
                translated_goals=(),
                open_branches=(),
                runtime_trace={},
                error=str(exc),
            )
    else:
        elaboration = elaboration_override

    payload = {
        "mode": "backward_decompose",
        "gdl_path": str(runtime.gdl_path),
        "constructions": [
            {"statement": statement, "random_seed": index + 1}
            for index, statement in enumerate(elaboration.constructions)
        ],
        "goal": elaboration.formal_goal,
        "max_rounds": max_rounds,
        "seed_offsets": list(seed_offsets),
    }
    theorem_name_list = list(theorem_names)
    if theorem_name_list:
        payload["theorem_names"] = theorem_name_list
    runtime_environment = os.environ.copy()
    runtime_environment["PYTHONIOENCODING"] = "utf-8"
    trace: dict[str, Any] | None = None
    timeout_error: str | None = None
    completed: subprocess.CompletedProcess[str] | None = None
    with tempfile.TemporaryDirectory(prefix="mortra-formalgeo-") as directory:
        checkpoint_path = Path(directory) / "checkpoint.json"
        payload["checkpoint_path"] = str(checkpoint_path)
        try:
            completed = subprocess.run(
                [str(runtime.python_executable), str(runtime.adapter_script)],
                input=json.dumps(payload, ensure_ascii=False),
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=runtime.timeout_seconds,
                cwd=runtime.root,
                env=runtime_environment,
                check=False,
            )
        except OSError as exc:
            return FormalGeoBridgeResult(
                available=True,
                elaborated=True,
                root_solved=False,
                replay_required=True,
                elaboration=elaboration,
                translated_goals=(),
                open_branches=(),
                runtime_trace={"timed_out": False, "error_type": type(exc).__name__},
                error=f"{type(exc).__name__}: {exc}",
            )
        except subprocess.TimeoutExpired as exc:
            timeout_error = f"{type(exc).__name__}: {exc}"
            if checkpoint_path.is_file():
                try:
                    trace = json.loads(checkpoint_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    trace = None
            if trace is None:
                return FormalGeoBridgeResult(
                    available=True,
                    elaborated=True,
                    root_solved=False,
                    replay_required=True,
                    elaboration=elaboration,
                    translated_goals=(),
                    open_branches=((goal.canonical(),),),
                    runtime_trace={
                        "timed_out": True,
                        "timeout_seconds": runtime.timeout_seconds,
                        "error_type": type(exc).__name__,
                        "root_obligation_preserved": True,
                    },
                    error=timeout_error,
                )
            trace.update(
                {
                    "timed_out": True,
                    "right_censored": True,
                    "timeout_seconds": runtime.timeout_seconds,
                    "error_type": type(exc).__name__,
                }
            )

    if trace is None and completed is not None:
        try:
            trace = json.loads(completed.stdout)
        except json.JSONDecodeError:
            trace = {
                "ok": False,
                "error": "invalid_runtime_json",
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "returncode": completed.returncode,
            }
    assert trace is not None
    if not trace.get("ok"):
        trace["root_obligation_preserved"] = True
        return FormalGeoBridgeResult(
            available=True,
            elaborated=True,
            root_solved=False,
            replay_required=True,
            elaboration=elaboration,
            translated_goals=(),
            open_branches=((goal.canonical(),),),
            runtime_trace=trace,
            error=(
                trace.get("message")
                or trace.get("error")
                or (completed.stderr if completed is not None else timeout_error)
            ),
        )

    point_inverse = {value: key for key, value in elaboration.point_to_object}
    line_inverse = {value: key for key, value in elaboration.segment_to_object}
    translated: list[dict[str, Any]] = []
    for goal_item in trace.get("goals", []):
        translated_tree = _translate_tree(goal_item["tree"], point_inverse, line_inverse)
        translated.append({**goal_item, "tree": _json_tree(translated_tree)})

    branches: list[tuple[Atom, ...]] = []
    if trace.get("frontier_tree") is not None and not trace.get("root_solved"):
        translated_frontier = _translate_tree(
            trace["frontier_tree"], point_inverse, line_inverse
        )
        branches.extend(_open_dnf(translated_frontier))

    unique_branches = tuple(
        sorted(
            set(branches),
            key=lambda branch: (len(branch), tuple(map(_render_atom, branch))),
        )
    )
    return FormalGeoBridgeResult(
        available=True,
        elaborated=True,
        root_solved=bool(trace.get("root_solved")),
        replay_required=True,
        elaboration=elaboration,
        translated_goals=tuple(translated),
        open_branches=unique_branches,
        runtime_trace=trace,
        error=timeout_error,
    )


_SUPPORTED_TYPED_PREDICATES = frozenset(
    {"coll", "para", "perp", "cong", "cyclic", "eqangle"}
)


def select_goal_conditioned_facts(
    facts: Iterable[Atom],
    goal: Atom,
    *,
    max_facts: int = 4,
) -> tuple[Atom, ...]:
    """Select a bounded connected fact chart without theorem-name templates.

    Selection depends only on typed entity overlap and relation signatures.  It
    does not inspect a problem identifier, expected theorem sequence, or answer.
    """

    if max_facts < 1:
        return ()
    goal = goal.canonical()

    def informative(atom: Atom) -> bool:
        name = atom.predicate.lower()
        args = atom.arguments
        if name == "cong" and len(args) == 4:
            return _segment(args[0], args[1]) != _segment(args[2], args[3])
        if name == "eqangle" and len(args) == 8:
            lines = _segments(atom)
            return not (lines[0] == lines[1] and lines[2] == lines[3])
        return True

    candidates = tuple(
        dict.fromkeys(
            atom.canonical()
            for atom in facts
            if atom.predicate.lower() in _SUPPORTED_TYPED_PREDICATES
            and not any(argument.startswith("?") for argument in atom.arguments)
            and atom.canonical() != goal
            and informative(atom.canonical())
        )
    )
    support = set(goal.arguments)
    selected: list[Atom] = []
    remaining = list(candidates)
    while remaining and len(selected) < max_facts:
        ranked = sorted(
            remaining,
            key=lambda atom: (
                -len(set(atom.arguments) & support),
                -(atom.predicate == goal.predicate),
                -len(set(atom.arguments) - support),
                _render_atom(atom),
            ),
        )
        candidate = ranked[0]
        if not (set(candidate.arguments) & support):
            break
        selected.append(candidate)
        support.update(candidate.arguments)
        remaining.remove(candidate)
    return tuple(selected)


def run_formalgeo_goal_exchange(
    facts: Iterable[Atom],
    goal: Atom,
    *,
    max_facts: int = 4,
    max_elaborations: int = 6,
    max_rounds: int = 2,
    max_chart_facts: int = 4,
    max_plan_checks: int = 256,
    config: FormalGeoRuntimeConfig | None = None,
) -> FormalGeoGoalExchange:
    """Try bounded construction orders and return only typed proof obligations."""

    selected = select_goal_conditioned_facts(facts, goal, max_facts=max_facts)
    if not selected:
        return FormalGeoGoalExchange(False, (), (), ())

    candidate_orders: list[tuple[Atom, ...]] = []
    # Prefer the largest connected chart.  Shorter prefixes remain useful when
    # one relation cannot yet be elaborated by the official construction API.
    plan_checks = 0
    max_length = min(max_chart_facts, len(selected))
    checks_per_length = max(1, max_plan_checks // max_length)
    for length in range(1, max_length + 1):
        length_checks = 0
        found_at_length = False
        for subset in combinations(selected, length):
            for order in permutations(subset):
                plan_checks += 1
                length_checks += 1
                try:
                    elaborate_atoms(order, goal)
                except FormalGeoElaborationError:
                    pass
                else:
                    candidate_orders.append(order)
                    found_at_length = True
                    break
                if length_checks >= checks_per_length:
                    break
            if found_at_length or length_checks >= checks_per_length:
                break
        if plan_checks >= max_plan_checks:
            break
    candidate_orders.sort(key=lambda order: (-len(order), tuple(map(_render_atom, order))))
    candidate_orders = candidate_orders[:max_elaborations]

    results: list[FormalGeoBridgeResult] = []
    branches: list[tuple[Atom, ...]] = []
    for order in candidate_orders:
        result = run_formalgeo_bridge(
            order,
            goal,
            max_rounds=max_rounds,
            config=config,
        )
        results.append(result)
        branches.extend(result.open_branches)
        if result.root_solved or result.open_branches:
            break

    obligation_branches = tuple(
        sorted(
            set(branches),
            key=lambda branch: (len(branch), tuple(map(_render_atom, branch))),
        )
    )
    return FormalGeoGoalExchange(
        attempted=bool(candidate_orders),
        selected_facts=selected,
        results=tuple(results),
        obligation_branches=obligation_branches,
    )


__all__ = [
    "FormalGeoBridgeResult",
    "FormalGeoElaboration",
    "FormalGeoElaborationError",
    "FormalGeoGoalExchange",
    "FormalGeoRuntimeConfig",
    "elaborate_atoms",
    "run_formalgeo_bridge",
    "run_formalgeo_goal_exchange",
    "select_goal_conditioned_facts",
]
