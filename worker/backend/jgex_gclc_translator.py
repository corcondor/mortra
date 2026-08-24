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
        "on_aline",
    }
)
CIRCLE_LOCI = frozenset({"on_circle", "on_circum", "on_dia", "eqangle3"})
DIRECT_CONSTRUCTIONS = frozenset(
    {
        "free",
        "triangle",
        "iso_triangle",
        "quadrangle",
        "r_triangle",
        "midpoint",
        "centroid",
        "foot",
        "orthocenter",
        "circle",
        "circumcenter",
        "incenter",
        "incenter2",
        "excenter",
        "mirror",
        "reflect",
        "cc_tangent",
    }
)
SUPPORTED_GOALS = frozenset(
    {"coll", "para", "perp", "cong", "cyclic", "eqangle"}
)


@dataclass(frozen=True)
class GCLCTranslation:
    source: str
    construction_vocabulary: tuple[str, ...]
    goal_channel: str
    goal_points: tuple[str, ...]
    source_sha256: str
    local_lemma_certificates: tuple[str, ...] = ()
    original_clause_count: int = 0
    translated_clause_count: int = 0


def canonical_typed_goal_key(
    channel: str,
    points: tuple[str, ...],
) -> tuple[str, tuple[str, ...]]:
    """Canonicalize only mathematically valid relation symmetries."""

    normalized = tuple(_identifier(point).lower() for point in points)
    if channel == "coll" and len(normalized) == 3:
        return channel, tuple(sorted(normalized))
    if channel == "cyclic" and len(normalized) >= 4:
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

    def translate(
        self,
        vector_start: str,
        vector_end: str,
        source: str,
        prefix: str = "translate",
    ) -> str:
        output = self.fresh(prefix)
        self.emit(
            f"translate {output} {_identifier(vector_start)} "
            f"{_identifier(vector_end)} {_identifier(source)}"
        )
        self.points.add(output)
        return output

    def quarter_turn(
        self,
        center: str,
        source: str,
        prefix: str = "quarter_turn",
    ) -> str:
        axis = self.line(center, source, f"{prefix}_axis")
        perpendicular = self.perpendicular(center, axis)
        radius = self.circle(center, source)
        output = self.fresh(prefix)
        opposite = self.fresh(f"{prefix}_opposite")
        self.emit(f"intersec2 {output} {opposite} {radius} {perpendicular}")
        self.points.update((output, opposite))
        return output

    def line_intersection(self, first: str, second: str, prefix: str) -> str:
        output = self.fresh(prefix)
        self.emit(f"intersec {output} {first} {second}")
        self.points.add(output)
        return output

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
        self.emit(f"oncircle {point} {_identifier(center)} {_identifier(radius_point)}")
        self.points.add(point)


def _construction_args(construction) -> tuple[str, ...]:
    return tuple(_identifier(str(value)) for value in construction.args)


def slice_formulation_to_goal_cone(
    formulation: JGEXFormulation,
) -> JGEXFormulation:
    """Keep only construction ancestors and closed constraints of the goal.

    A proof from this weaker hypothesis set is valid for the original problem.
    The slice is structural and depends only on point production/consumption,
    never on a problem name or expected theorem result.
    """

    needed = {
        _identifier(str(argument))
        for goal in formulation.goals
        for argument in goal.args
        if str(argument) and str(argument)[0].isalpha()
    }
    selected: set[int] = set()
    clauses = formulation.setup_clauses
    for index in range(len(clauses) - 1, -1, -1):
        clause = clauses[index]
        outputs = {_identifier(str(point)) for point in clause.points}
        if outputs and outputs.intersection(needed):
            selected.add(index)
            for construction in clause.constructions:
                needed.update(
                    _identifier(str(argument))
                    for argument in construction.args
                    if str(argument) and str(argument)[0].isalpha()
                )
    for index, clause in enumerate(clauses):
        if clause.points:
            continue
        arguments = {
            _identifier(str(argument))
            for construction in clause.constructions
            for argument in construction.args
            if str(argument) and str(argument)[0].isalpha()
        }
        if arguments and arguments.issubset(needed):
            selected.add(index)
    return JGEXFormulation(
        name=formulation.name,
        setup_clauses=tuple(
            clause for index, clause in enumerate(clauses) if index in selected
        ),
        auxiliary_clauses=(),
        goals=formulation.goals,
    )


@dataclass(frozen=True)
class ExternalHomothetyMacro:
    tangent_clause_index: int
    intersection_clause_index: int
    output: str
    hidden_tangent_points: tuple[str, str, str, str]
    center_a: str
    radius_a: str
    center_b: str
    radius_b: str

    @property
    def certificate(self) -> str:
        return (
            "external_common_tangents_intersect_at_external_homothety_center:"
            f"{self.center_a},{self.radius_a},{self.center_b},{self.radius_b}"
            f"->{self.output}"
        )


def external_homothety_macros(
    formulation: JGEXFormulation,
) -> tuple[ExternalHomothetyMacro, ...]:
    """Find a typed cc_tangent -> line intersection composition.

    This is a graph rewrite, not a text pattern: all four tangent outputs must
    be consumed exactly once by the two-line intersection and nowhere else.
    """

    uses: dict[str, list[int]] = {}
    for clause_index, clause in enumerate(formulation.setup_clauses):
        for construction in clause.constructions:
            for argument in _construction_args(construction):
                uses.setdefault(argument, []).append(clause_index)
    goal_points = {
        _identifier(str(argument))
        for goal in formulation.goals
        for argument in goal.args
    }
    macros: list[ExternalHomothetyMacro] = []
    for clause_index, clause in enumerate(formulation.setup_clauses):
        constructions = tuple(clause.constructions)
        if len(constructions) != 1 or constructions[0].name != "cc_tangent":
            continue
        args = _construction_args(constructions[0])
        first, second, third, fourth, center_a, radius_a, center_b, radius_b = args
        tangent_points = (first, second, third, fourth)
        if goal_points.intersection(tangent_points):
            continue
        for consumer_index in range(clause_index + 1, len(formulation.setup_clauses)):
            consumer = formulation.setup_clauses[consumer_index]
            line_constructions = tuple(
                item for item in consumer.constructions if item.name == "on_line"
            )
            if len(line_constructions) != 2 or len(consumer.constructions) != 2:
                continue
            line_args = tuple(_construction_args(item) for item in line_constructions)
            if line_args[0][0] != line_args[1][0]:
                continue
            endpoint_pairs = {
                frozenset(line_args[0][1:3]),
                frozenset(line_args[1][1:3]),
            }
            expected_pairs = {
                frozenset((first, second)),
                frozenset((third, fourth)),
            }
            if endpoint_pairs != expected_pairs:
                continue
            if any(
                uses.get(point, []) != [clause_index, consumer_index]
                for point in tangent_points
            ):
                continue
            macros.append(
                ExternalHomothetyMacro(
                    tangent_clause_index=clause_index,
                    intersection_clause_index=consumer_index,
                    output=line_args[0][0],
                    hidden_tangent_points=tangent_points,
                    center_a=center_a,
                    radius_a=radius_a,
                    center_b=center_b,
                    radius_b=radius_b,
                )
            )
            break
    return tuple(macros)


def _emit_external_homothety_center(
    emitter: _Emitter,
    macro: ExternalHomothetyMacro,
) -> None:
    copied_radius_b = emitter.translate(
        macro.center_b,
        macro.radius_b,
        macro.center_a,
        "homothety_radius_copy",
    )
    radius_axis = emitter.line(
        macro.center_a,
        macro.radius_a,
        "homothety_radius_axis",
    )
    radius_b_circle = emitter.circle(macro.center_a, copied_radius_b)
    aligned_radius_b = emitter.fresh("homothety_aligned_radius")
    opposite_radius_b = emitter.fresh("homothety_opposite_radius")
    emitter.emit(
        f"intersec2 {aligned_radius_b} {opposite_radius_b} "
        f"{radius_b_circle} {radius_axis}"
    )
    emitter.points.update((aligned_radius_b, opposite_radius_b))
    radius_difference = emitter.translate(
        aligned_radius_b,
        macro.radius_a,
        macro.center_a,
        "homothety_radius_difference",
    )
    centers_axis = emitter.line(
        macro.center_a,
        macro.center_b,
        "homothety_centers",
    )
    homothety_bridge = emitter.line(
        radius_difference,
        macro.center_b,
        "homothety_bridge",
    )
    through_radius_a = emitter.parallel(macro.radius_a, homothety_bridge)
    emitter.emit(
        f"intersec {_identifier(macro.output)} {through_radius_a} {centers_axis}"
    )
    emitter.points.add(_identifier(macro.output))


def _transfer_direct_similarity(
    emitter: _Emitter,
    *,
    target_origin: str,
    target_unit: str,
    source_origin: str,
    source_unit: str,
    source_point: str,
) -> str:
    """Map one point through the direct similarity source_unit -> target_unit.

    The source vector is decomposed into its parallel and perpendicular
    components.  Parallel constructions transfer the two directed scalar
    coefficients to the target basis, so no measured angle or fitted numeric
    constant enters the proof graph.
    """

    source_axis = emitter.line(source_origin, source_unit, "similarity_source")
    projection = emitter.fresh("similarity_projection")
    emitter.emit(f"foot {projection} {source_point} {source_axis}")
    emitter.points.add(projection)

    source_perp_unit = emitter.quarter_turn(
        source_origin,
        source_unit,
        "similarity_source_perp",
    )
    source_perp_component = emitter.translate(
        projection,
        source_point,
        source_origin,
        "similarity_source_component",
    )
    target_unit_at_source = emitter.translate(
        target_origin,
        target_unit,
        source_origin,
        "similarity_target_unit",
    )
    target_perp_at_source = emitter.quarter_turn(
        source_origin,
        target_unit_at_source,
        "similarity_target_perp",
    )

    def transfer_scalar(
        source_basis: str,
        scaled_source: str,
        target_basis: str,
        prefix: str,
    ) -> str:
        bridge = emitter.line(source_basis, target_basis, f"{prefix}_bridge")
        transferred = emitter.parallel(scaled_source, bridge)
        target_axis = emitter.line(source_origin, target_basis, f"{prefix}_axis")
        return emitter.line_intersection(transferred, target_axis, prefix)

    target_parallel_component = transfer_scalar(
        source_unit,
        projection,
        target_unit_at_source,
        "similarity_parallel_component",
    )
    target_perp_component = transfer_scalar(
        source_perp_unit,
        source_perp_component,
        target_perp_at_source,
        "similarity_perp_component",
    )
    parallel_at_target = emitter.translate(
        source_origin,
        target_parallel_component,
        target_origin,
        "similarity_parallel_at_target",
    )
    perpendicular_at_target = emitter.translate(
        source_origin,
        target_perp_component,
        target_origin,
        "similarity_perp_at_target",
    )
    return emitter.translate(
        target_origin,
        perpendicular_at_target,
        parallel_at_target,
        "similarity_image",
    )


def _angle_line(
    emitter: _Emitter,
    *,
    target_origin: str,
    target_unit: str,
    source_point: str,
    source_origin: str,
    source_unit: str,
) -> str:
    image = _transfer_direct_similarity(
        emitter,
        target_origin=target_origin,
        target_unit=target_unit,
        source_origin=source_origin,
        source_unit=source_unit,
        source_point=source_point,
    )
    return emitter.line(target_origin, image, "angle_line")


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
    if name == "on_aline":
        return _angle_line(
            emitter,
            target_origin=args[1],
            target_unit=args[2],
            source_point=args[3],
            source_origin=args[4],
            source_unit=args[5],
        )
    raise ValueError(f"unsupported line locus: {name} for {point}")


def _circle_locus(
    emitter: _Emitter,
    name: str,
    args: tuple[str, ...],
) -> tuple[str, str, str]:
    if name == "on_circle":
        circle = emitter.circle(args[1], args[2])
        return circle, args[1], args[2]
    if name == "on_circum":
        center = emitter.fresh("circum_center")
        first_bisector = emitter.perpendicular_bisector(args[1], args[2])
        second_bisector = emitter.perpendicular_bisector(args[1], args[3])
        emitter.emit(f"intersec {center} {first_bisector} {second_bisector}")
        emitter.points.add(center)
        circle = emitter.circle(center, args[1])
        return circle, center, args[1]
    if name == "on_dia":
        midpoint = emitter.fresh("dia_mid")
        emitter.emit(f"midpoint {midpoint} {args[1]} {args[2]}")
        emitter.points.add(midpoint)
        circle = emitter.circle(midpoint, args[1])
        return circle, midpoint, args[1]
    if name == "eqangle3":
        tangent = _angle_line(
            emitter,
            target_origin=args[1],
            target_unit=args[2],
            source_point=args[4],
            source_origin=args[3],
            source_unit=args[5],
        )
        radius_at_first = emitter.perpendicular(args[1], tangent)
        chord_bisector = emitter.perpendicular_bisector(args[1], args[2])
        center = emitter.line_intersection(
            radius_at_first,
            chord_bisector,
            "eqangle_center",
        )
        circle = emitter.circle(center, args[1])
        return circle, center, args[1]
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
        _line_locus(emitter, item.name, _construction_args(item)) for item in line_loci
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
        first_circle, first_center, first_radius_point = circles[0]
        second_circle, second_center, second_radius_point = circles[1]
        if first_radius_point == second_radius_point:
            # GCLC can draw a circle-circle intersection, but its Wu and
            # Groebner provers reject p_intercc.  When the two circles share a
            # known point A, their other intersection is the reflection of A
            # in the line joining their centers.  This exact reduction uses
            # only prover-supported line, foot, and point-ratio commands.
            centers_axis = emitter.line(
                first_center,
                second_center,
                "common_chord_centers",
            )
            projection = emitter.fresh("common_chord_foot")
            emitter.emit(
                f"foot {projection} {first_radius_point} {centers_axis}"
            )
            emitter.points.add(projection)
            emitter.emit(f"towards {output} {first_radius_point} {projection} 2")
            emitter.points.add(output)
            return
        other = emitter.fresh("other_root")
        emitter.emit(f"intersec2 {output} {other} {first_circle} {second_circle}")
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
    if name == "free":
        emitter.free_point(args[0])
        return
    if name in {"triangle", "quadrangle"}:
        for point in args:
            emitter.free_point(point)
        return
    if name == "iso_triangle":
        apex, left, right = args
        emitter.free_point(left)
        emitter.free_point(right)
        symmetry_axis = emitter.perpendicular_bisector(left, right)
        emitter.arbitrary_point_on_line(apex, symmetry_axis)
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
    if name == "centroid":
        midpoint_a, midpoint_b, midpoint_c, center, a, b, c = args
        emitter.emit(f"midpoint {midpoint_a} {b} {c}")
        emitter.emit(f"midpoint {midpoint_b} {c} {a}")
        emitter.emit(f"midpoint {midpoint_c} {a} {b}")
        emitter.points.update((midpoint_a, midpoint_b, midpoint_c))
        median_a = emitter.line(a, midpoint_a, "median")
        median_b = emitter.line(b, midpoint_b, "median")
        emitter.emit(f"intersec {center} {median_a} {median_b}")
        emitter.points.add(center)
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
    if name in {"circle", "circumcenter"}:
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
    if name == "excenter":
        center, a, b, c = args
        internal_at_a = emitter.bisector(b, a, c)
        internal_at_c = emitter.bisector(b, c, a)
        external_at_c = emitter.perpendicular(c, internal_at_c)
        emitter.emit(f"intersec {center} {internal_at_a} {external_at_c}")
        emitter.points.add(center)
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
    if name == "cc_tangent":
        first, second, third, fourth, center_a, radius_a, center_b, radius_b = args

        copied_radius_b = emitter.translate(
            center_b,
            radius_b,
            center_a,
            "tangent_radius_copy",
        )
        radius_axis = emitter.line(center_a, radius_a, "tangent_radius_axis")
        radius_b_circle = emitter.circle(center_a, copied_radius_b)
        aligned_radius_b = emitter.fresh("tangent_aligned_radius")
        opposite_radius_b = emitter.fresh("tangent_opposite_radius")
        emitter.emit(
            f"intersec2 {aligned_radius_b} {opposite_radius_b} "
            f"{radius_b_circle} {radius_axis}"
        )
        emitter.points.update((aligned_radius_b, opposite_radius_b))

        # The two collinear radius copies encode the external and internal
        # homothety branches.  Geometry search must retain both: the external
        # center is at infinity when the radii are equal, while the internal
        # center remains finite.  Sketch attempts alternate the branch without
        # inspecting a problem identifier or expected result.
        homothety_radius = (
            aligned_radius_b if emitter.sketch_seed % 2 == 0 else opposite_radius_b
        )
        radius_difference = emitter.translate(
            homothety_radius,
            radius_a,
            center_a,
            "tangent_radius_difference",
        )
        centers_axis = emitter.line(center_a, center_b, "tangent_centers")
        homothety_bridge = emitter.line(
            radius_difference,
            center_b,
            "tangent_homothety_bridge",
        )
        through_radius_a = emitter.parallel(radius_a, homothety_bridge)
        homothety_center = emitter.line_intersection(
            through_radius_a,
            centers_axis,
            "tangent_homothety_center",
        )

        first_circle = emitter.circle(center_a, radius_a)

        # Obtain the contact chord as the polar of the homothety center.
        # A complete quadrilateral uses only line-circle and line-line
        # intersections, both supported by GCLC's algebraic provers.
        first_secant = emitter.line(
            homothety_center,
            center_a,
            "tangent_first_secant",
        )
        first_secant_a = emitter.fresh("tangent_first_secant_point")
        first_secant_b = emitter.fresh("tangent_first_secant_point")
        emitter.emit(
            f"intersec2 {first_secant_a} {first_secant_b} {first_circle} {first_secant}"
        )
        emitter.points.update((first_secant_a, first_secant_b))

        second_secant = emitter.line(
            homothety_center,
            radius_a,
            "tangent_second_secant",
        )
        second_secant_a = emitter.fresh("tangent_second_secant_point")
        second_secant_b = emitter.fresh("tangent_second_secant_point")
        emitter.emit(
            f"intersec2 {second_secant_a} {second_secant_b} "
            f"{first_circle} {second_secant}"
        )
        emitter.points.update((second_secant_a, second_secant_b))

        first_diagonal_a = emitter.line(
            first_secant_a,
            second_secant_a,
            "tangent_diagonal",
        )
        first_diagonal_b = emitter.line(
            first_secant_b,
            second_secant_b,
            "tangent_diagonal",
        )
        first_polar_point = emitter.line_intersection(
            first_diagonal_a,
            first_diagonal_b,
            "tangent_polar_point",
        )
        second_diagonal_a = emitter.line(
            first_secant_a,
            second_secant_b,
            "tangent_diagonal",
        )
        second_diagonal_b = emitter.line(
            first_secant_b,
            second_secant_a,
            "tangent_diagonal",
        )
        second_polar_point = emitter.line_intersection(
            second_diagonal_a,
            second_diagonal_b,
            "tangent_polar_point",
        )
        contact_chord = emitter.line(
            first_polar_point,
            second_polar_point,
            "tangent_contact_chord",
        )
        emitter.emit(f"intersec2 {first} {third} {first_circle} {contact_chord}")
        emitter.points.update((first, third))

        first_tangent = emitter.line(homothety_center, first, "tangent_line")
        third_tangent = emitter.line(homothety_center, third, "tangent_line")
        emitter.emit(f"foot {second} {center_b} {first_tangent}")
        emitter.emit(f"foot {fourth} {center_b} {third_tangent}")
        emitter.points.update((second, fourth))
        return
    raise ValueError(f"unsupported direct construction: {name}")


def _goal_line(
    emitter: _Emitter,
    channel: str,
    points: tuple[str, ...],
) -> str:
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
    if channel == "cyclic" and len(points) == 4:
        first, second, third, fourth = points[:4]
        first_cross = f"{{ signed_area3 {first} {second} {third} }}"
        first_dot = f"{{ pythagoras_difference3 {first} {second} {third} }}"
        second_cross = f"{{ signed_area3 {first} {fourth} {third} }}"
        second_dot = f"{{ pythagoras_difference3 {first} {fourth} {third} }}"
        # Equal (possibly supplementary) directed angles ABC and ADC.
        # This tangent identity avoids a branch-sensitive circumcenter.
        return (
            f"prove {{ equal {{ mult {first_cross} {second_dot} }} "
            f"{{ mult {first_dot} {second_cross} }} }}"
        )
    if channel == "eqangle" and len(points) == 8:
        a, b, c, d, e, f, g, h = points
        translated_d = emitter.translate(c, d, a, "goal_angle_vector")
        translated_h = emitter.translate(g, h, e, "goal_angle_vector")
        first_cross = f"{{ signed_area3 {a} {b} {translated_d} }}"
        first_dot = f"{{ pythagoras_difference3 {a} {b} {translated_d} }}"
        second_cross = f"{{ signed_area3 {e} {f} {translated_h} }}"
        second_dot = f"{{ pythagoras_difference3 {e} {f} {translated_h} }}"
        return (
            f"prove {{ equal {{ mult {first_cross} {second_dot} }} "
            f"{{ mult {first_dot} {second_cross} }} }}"
        )
    raise ValueError(f"unsupported GCLC goal: {channel} {points}")


def translate_jgex_to_gclc(
    text: str,
    *,
    sketch_seed: int = 0,
    enable_structural_lemmas: bool = True,
    goal_local: bool = False,
) -> GCLCTranslation:
    definitions = JGEXDefinition.to_dict(list(ALL_JGEX_CONSTRUCTIONS))
    formulation, report = normalize_legacy_formulation(
        JGEXFormulation.from_text(text), definitions
    )
    if report.unresolved_constructions:
        raise ValueError("JGEX normalization left unresolved constructions")
    original_clause_count = len(formulation.setup_clauses)
    if goal_local:
        formulation = slice_formulation_to_goal_cone(formulation)
    if len(formulation.goals) != 1:
        raise ValueError("GCLC translation requires exactly one goal")
    goal = formulation.goals[0]
    channel = goal.predicate_type.value
    points = tuple(_identifier(str(point)) for point in goal.args)
    if channel not in SUPPORTED_GOALS:
        raise ValueError(f"unsupported GCLC goal channel: {channel}")

    emitter = _Emitter(sketch_seed=sketch_seed)
    vocabulary: list[str] = []
    homothety_macros = (
        external_homothety_macros(formulation) if enable_structural_lemmas else ()
    )
    macros_by_start = {item.tangent_clause_index: item for item in homothety_macros}
    skipped_clause_indices = {
        item.intersection_clause_index for item in homothety_macros
    }
    for clause_index, clause in enumerate(formulation.setup_clauses):
        constructions = tuple(clause.constructions)
        vocabulary.extend(item.name for item in constructions)
        if clause_index in macros_by_start:
            _emit_external_homothety_center(emitter, macros_by_start[clause_index])
            continue
        if clause_index in skipped_clause_indices:
            continue
        if len(constructions) == 1 and constructions[0].name in DIRECT_CONSTRUCTIONS:
            _emit_direct(
                emitter,
                constructions[0].name,
                _construction_args(constructions[0]),
            )
            continue
        _emit_locus_clause(emitter, constructions)

    emitter.emit(_goal_line(emitter, channel, points))
    source = "\n".join(emitter.lines) + "\n"
    return GCLCTranslation(
        source=source,
        construction_vocabulary=tuple(sorted(set(vocabulary))),
        goal_channel=channel,
        goal_points=points,
        source_sha256=hashlib.sha256(source.encode("utf-8")).hexdigest(),
        local_lemma_certificates=tuple(item.certificate for item in homothety_macros),
        original_clause_count=original_clause_count,
        translated_clause_count=len(formulation.setup_clauses),
    )
