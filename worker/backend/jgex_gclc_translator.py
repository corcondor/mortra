"""Translate a typed JGEX construction graph into executable GCLC source.

The translation is structural: it dispatches only on construction and goal
predicates.  It never inspects a problem name, benchmark index, or known answer.
GCLC drawing coordinates merely choose a non-degenerate sketch; its provers
treat the constructed points symbolically.
"""

from __future__ import annotations

import hashlib
import random
import re
from dataclasses import dataclass

from newclid.jgex.constructions import ALL_JGEX_CONSTRUCTIONS
from newclid.jgex.definition import JGEXDefinition
from newclid.jgex.formulation import JGEXFormulation

from worker.backend.jgex_legacy_normalizer import normalize_legacy_formulation


LINE_LOCI = frozenset(
    {
        "on_line",
        "on_pline",
        "on_tline",
        "on_bline",
        "angle_bisector",
    }
)
CIRCLE_LOCI = frozenset({"on_circle", "on_dia"})
DIRECT_CONSTRUCTIONS = frozenset(
    {
        "triangle",
        "r_triangle",
        "midpoint",
        "foot",
        "orthocenter",
        "circle",
        "incenter",
        "incenter2",
        "mirror",
        "reflect",
    }
)
SUPPORTED_GOALS = frozenset({"coll", "para", "perp", "cong"})


@dataclass(frozen=True)
class GCLCTranslation:
    source: str
    construction_vocabulary: tuple[str, ...]
    goal_channel: str
    goal_points: tuple[str, ...]
    source_sha256: str


def canonical_typed_goal_key(
    channel: str,
    points: tuple[str, ...],
) -> tuple[str, tuple[str, ...]]:
    """Canonicalize only mathematically valid relation symmetries."""

    normalized = tuple(_identifier(point).lower() for point in points)
    if channel == "coll" and len(normalized) == 3:
        return channel, tuple(sorted(normalized))
    if channel in {"para", "perp", "cong"} and len(normalized) == 4:
        left = tuple(sorted(normalized[:2]))
        right = tuple(sorted(normalized[2:]))
        first, second = sorted((left, right))
        return channel, (*first, *second)
    return channel, normalized


def _identifier(value: str) -> str:
    result = re.sub(r"[^A-Za-z0-9_]", "_", value)
    if not result or result[0].isdigit():
        result = f"p_{result}"
    return result


class _Emitter:
    def __init__(self, *, sketch_seed: int = 0) -> None:
        self.lines: list[str] = []
        self.points: set[str] = set()
        self.objects: set[str] = set()
        self._counter = 0
        self.sketch_seed = sketch_seed
        self._random = random.Random(0x4D4F5254 + sketch_seed)
        self._drawing_coordinates: set[tuple[int, int]] = set()

    def fresh(self, prefix: str) -> str:
        while True:
            value = f"mortra_{prefix}_{self._counter}"
            self._counter += 1
            if value not in self.points and value not in self.objects:
                return value

    def emit(self, command: str) -> None:
        self.lines.append(command)

    def free_point(self, point: str) -> None:
        point = _identifier(point)
        if point in self.points:
            return
        while True:
            x = self._random.randint(10, 110)
            y = self._random.randint(10, 90)
            if (x, y) not in self._drawing_coordinates:
                self._drawing_coordinates.add((x, y))
                break
        self.emit(f"point {point} {x} {y}")
        self.points.add(point)

    def object_name(self, prefix: str) -> str:
        result = self.fresh(prefix)
        self.objects.add(result)
        return result

    def line(self, left: str, right: str, prefix: str = "line") -> str:
        name = self.object_name(prefix)
        self.emit(f"line {name} {_identifier(left)} {_identifier(right)}")
        return name

    def perpendicular(self, point: str, reference: str) -> str:
        name = self.object_name("perp")
        self.emit(f"perp {name} {_identifier(point)} {reference}")
        return name

    def parallel(self, point: str, reference: str) -> str:
        name = self.object_name("para")
        self.emit(f"parallel {name} {_identifier(point)} {reference}")
        return name

    def bisector(self, left: str, vertex: str, right: str) -> str:
        name = self.object_name("bis")
        self.emit(
            f"bis {name} {_identifier(left)} {_identifier(vertex)} {_identifier(right)}"
        )
        return name

    def perpendicular_bisector(self, left: str, right: str) -> str:
        name = self.object_name("med")
        self.emit(f"med {name} {_identifier(left)} {_identifier(right)}")
        return name

    def circle(self, center: str, radius_point: str) -> str:
        name = self.object_name("circle")
        self.emit(f"circle {name} {_identifier(center)} {_identifier(radius_point)}")
        return name

    def arbitrary_point_on_line(self, point: str, line: str) -> None:
        point = _identifier(point)
        probe = self.fresh("probe")
        self.free_point(probe)
        transversal = self.perpendicular(probe, line)
        self.emit(f"intersec {point} {line} {transversal}")
        self.points.add(point)

    def arbitrary_point_on_circle(
        self,
        point: str,
        center: str,
        radius_point: str,
    ) -> None:
        point = _identifier(point)
        self.emit(
            f"oncircle {point} {_identifier(center)} {_identifier(radius_point)}"
        )
        self.points.add(point)


def _construction_args(construction) -> tuple[str, ...]:
    return tuple(_identifier(str(value)) for value in construction.args)


def _line_locus(emitter: _Emitter, name: str, args: tuple[str, ...]) -> str:
    point = args[0]
    if name == "on_line":
        return emitter.line(args[1], args[2], "on_line")
    if name == "on_pline":
        reference = emitter.line(args[2], args[3], "pline_ref")
        return emitter.parallel(args[1], reference)
    if name == "on_tline":
        reference = emitter.line(args[2], args[3], "tline_ref")
        return emitter.perpendicular(args[1], reference)
    if name == "on_bline":
        return emitter.perpendicular_bisector(args[1], args[2])
    if name == "angle_bisector":
        return emitter.bisector(args[1], args[2], args[3])
    raise ValueError(f"unsupported line locus: {name} for {point}")


def _circle_locus(
    emitter: _Emitter,
    name: str,
    args: tuple[str, ...],
) -> tuple[str, str, str]:
    if name == "on_circle":
        circle = emitter.circle(args[1], args[2])
        return circle, args[1], args[2]
    if name == "on_dia":
        midpoint = emitter.fresh("dia_mid")
        emitter.emit(f"midpoint {midpoint} {args[1]} {args[2]}")
        emitter.points.add(midpoint)
        circle = emitter.circle(midpoint, args[1])
        return circle, midpoint, args[1]
    raise ValueError(f"unsupported circle locus: {name}")


def _emit_locus_clause(emitter: _Emitter, constructions: tuple) -> None:
    outputs = {_construction_args(item)[0] for item in constructions}
    if len(outputs) != 1:
        raise ValueError("a locus clause must have one output point")
    output = outputs.pop()
    line_loci = [item for item in constructions if item.name in LINE_LOCI]
    circle_loci = [item for item in constructions if item.name in CIRCLE_LOCI]
    unsupported = [
        item.name
        for item in constructions
        if item.name not in LINE_LOCI and item.name not in CIRCLE_LOCI
    ]
    if unsupported:
        raise ValueError("unsupported compound loci: " + ", ".join(unsupported))

    lines = [
        _line_locus(emitter, item.name, _construction_args(item))
        for item in line_loci
    ]
    circles = [
        _circle_locus(emitter, item.name, _construction_args(item))
        for item in circle_loci
    ]
    if len(lines) >= 2:
        emitter.emit(f"intersec {output} {lines[0]} {lines[1]}")
        emitter.points.add(output)
        return
    if len(lines) == 1 and len(circles) == 1:
        other = emitter.fresh("other_root")
        emitter.emit(f"intersec2 {output} {other} {circles[0][0]} {lines[0]}")
        emitter.points.update((output, other))
        return
    if len(circles) >= 2:
        other = emitter.fresh("other_root")
        emitter.emit(
            f"intersec2 {output} {other} {circles[0][0]} {circles[1][0]}"
        )
        emitter.points.update((output, other))
        return
    if len(lines) == 1:
        emitter.arbitrary_point_on_line(output, lines[0])
        return
    if len(circles) == 1:
        _, center, radius_point = circles[0]
        emitter.arbitrary_point_on_circle(output, center, radius_point)
        return
    raise ValueError("empty locus clause")


def _emit_direct(emitter: _Emitter, name: str, args: tuple[str, ...]) -> None:
    if name == "triangle":
        for point in args:
            emitter.free_point(point)
        return
    if name == "r_triangle":
        vertex, left, right = args
        emitter.free_point(vertex)
        emitter.free_point(left)
        probe = emitter.fresh("right_probe")
        emitter.free_point(probe)
        base = emitter.line(vertex, left, "right_base")
        altitude = emitter.perpendicular(vertex, base)
        cross_line = emitter.parallel(probe, base)
        emitter.emit(f"intersec {right} {altitude} {cross_line}")
        emitter.points.add(right)
        return
    if name == "midpoint":
        emitter.emit(f"midpoint {args[0]} {args[1]} {args[2]}")
        emitter.points.add(args[0])
        return
    if name == "foot":
        side = emitter.line(args[2], args[3], "foot_side")
        emitter.emit(f"foot {args[0]} {args[1]} {side}")
        emitter.points.add(args[0])
        return
    if name == "orthocenter":
        output, a, b, c = args
        bc = emitter.line(b, c, "orth_side")
        ac = emitter.line(a, c, "orth_side")
        altitude_a = emitter.perpendicular(a, bc)
        altitude_b = emitter.perpendicular(b, ac)
        emitter.emit(f"intersec {output} {altitude_a} {altitude_b}")
        emitter.points.add(output)
        return
    if name == "circle":
        output, a, b, c = args
        bisector_ab = emitter.perpendicular_bisector(a, b)
        bisector_ac = emitter.perpendicular_bisector(a, c)
        emitter.emit(f"intersec {output} {bisector_ab} {bisector_ac}")
        emitter.points.add(output)
        return
    if name in {"incenter", "incenter2"}:
        if name == "incenter":
            center, a, b, c = args
            feet: tuple[str, ...] = ()
        else:
            foot_a, foot_b, foot_c, center, a, b, c = args
            feet = (foot_a, foot_b, foot_c)
        bisector_a = emitter.bisector(b, a, c)
        bisector_b = emitter.bisector(c, b, a)
        emitter.emit(f"intersec {center} {bisector_a} {bisector_b}")
        emitter.points.add(center)
        if feet:
            for foot, left, right in zip(
                feet,
                (b, c, a),
                (c, a, b),
                strict=True,
            ):
                side = emitter.line(left, right, "incenter_side")
                emitter.emit(f"foot {foot} {center} {side}")
                emitter.points.add(foot)
        return
    if name == "mirror":
        output, source, center = args
        emitter.emit(f"towards {output} {source} {center} 2")
        emitter.points.add(output)
        return
    if name == "reflect":
        output, source, left, right = args
        axis = emitter.line(left, right, "reflect_axis")
        projection = emitter.fresh("projection")
        emitter.emit(f"foot {projection} {source} {axis}")
        emitter.points.add(projection)
        emitter.emit(f"towards {output} {source} {projection} 2")
        emitter.points.add(output)
        return
    raise ValueError(f"unsupported direct construction: {name}")


def _goal_line(channel: str, points: tuple[str, ...]) -> str:
    if channel == "coll" and len(points) == 3:
        return f"prove {{ collinear {' '.join(points)} }}"
    if channel == "para" and len(points) == 4:
        return f"prove {{ parallel {' '.join(points)} }}"
    if channel == "perp" and len(points) == 4:
        return f"prove {{ perpendicular {' '.join(points)} }}"
    if channel == "cong" and len(points) == 4:
        return (
            f"prove {{ equal {{ segment {points[0]} {points[1]} }} "
            f"{{ segment {points[2]} {points[3]} }} }}"
        )
    raise ValueError(f"unsupported GCLC goal: {channel} {points}")


def translate_jgex_to_gclc(text: str, *, sketch_seed: int = 0) -> GCLCTranslation:
    definitions = JGEXDefinition.to_dict(list(ALL_JGEX_CONSTRUCTIONS))
    formulation, report = normalize_legacy_formulation(
        JGEXFormulation.from_text(text), definitions
    )
    if report.unresolved_constructions:
        raise ValueError("JGEX normalization left unresolved constructions")
    if len(formulation.goals) != 1:
        raise ValueError("GCLC translation requires exactly one goal")
    goal = formulation.goals[0]
    channel = goal.predicate_type.value
    points = tuple(_identifier(str(point)) for point in goal.args)
    if channel not in SUPPORTED_GOALS:
        raise ValueError(f"unsupported GCLC goal channel: {channel}")

    emitter = _Emitter(sketch_seed=sketch_seed)
    vocabulary: list[str] = []
    for clause in formulation.setup_clauses:
        constructions = tuple(clause.constructions)
        vocabulary.extend(item.name for item in constructions)
        if len(constructions) == 1 and constructions[0].name in DIRECT_CONSTRUCTIONS:
            _emit_direct(
                emitter,
                constructions[0].name,
                _construction_args(constructions[0]),
            )
            continue
        _emit_locus_clause(emitter, constructions)

    emitter.emit(_goal_line(channel, points))
    source = "\n".join(emitter.lines) + "\n"
    return GCLCTranslation(
        source=source,
        construction_vocabulary=tuple(sorted(set(vocabulary))),
        goal_channel=channel,
        goal_points=points,
        source_sha256=hashlib.sha256(source.encode("utf-8")).hexdigest(),
    )
