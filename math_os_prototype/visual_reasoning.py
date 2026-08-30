"""Reusable typed morphisms for step-by-step mathematical figures.

The solver owns the mathematics.  This module only turns verified semantic
states into frames and checks that consecutive frames form a typed chain.
It contains no benchmark ids or expected answers.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from math import atan2, cos, degrees, isfinite, pi, sin, sqrt
from typing import Any, Callable, Iterable, Sequence


Point = tuple[float, float]


@dataclass(frozen=True)
class VisualMorphism:
    morphism_id: str
    label_ja: str
    input_type: str
    output_type: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


PIVOT_ROTATION_TO_ORBIT = VisualMorphism(
    "motion.pivot_rotation.to_orbit.v1",
    "支点回転を点の軌跡へ移す",
    "PolygonWithContactRule",
    "PiecewiseCircularOrbit",
)
ORBIT_TO_DISK_UNION = VisualMorphism(
    "sweep.vertex_orbit.to_disk_union.v1",
    "頂点軌跡を円板合併へ移す",
    "PiecewiseCircularOrbit",
    "RadialStarBody",
)
INCREMENTAL_INTERSECTION = VisualMorphism(
    "set.radial_intersection.incremental.v1",
    "新しい領域との共通部分を取る",
    "RadialStarBody",
    "RadialStarBody",
)
ENVELOPE_STABILIZATION = VisualMorphism(
    "order.radial_envelope.stabilization.v1",
    "包含を証明して境界の更新を止める",
    "RadialStarBody",
    "RadialStarBody",
)
BOUNDARY_ARRANGEMENT = VisualMorphism(
    "arrangement.circle_arc.switch.v1",
    "境界を担当する円弧と切替点を求める",
    "RadialStarBody",
    "PiecewiseRadialBoundary",
)
RADIAL_AREA_INTEGRATION = VisualMorphism(
    "measure.radial_partition.integrate.v1",
    "区分的な動径を面積へ積分する",
    "PiecewiseRadialBoundary",
    "ExactArea",
)
FUNCTION_TO_GRAPH = VisualMorphism(
    "analysis.function.to_graph.v1",
    "関数式をグラフへ移す",
    "ExactFunction",
    "FunctionPlot",
)
DERIVATIVE_TO_VARIATION = VisualMorphism(
    "analysis.derivative.to_variation.v1",
    "導関数の符号を増減表へ移す",
    "DifferentialSignState",
    "VariationTable",
)
PROCESS_TO_STATE_GRAPH = VisualMorphism(
    "process.transition.to_state_graph.v1",
    "遷移規則を状態図へ移す",
    "FiniteProcess",
    "StateGraph",
)
VERIFIED_SCENE_UPDATE = VisualMorphism(
    "visual.verified_scene.update.v1",
    "検証済み状態を図面へ反映する",
    "VerifiedVisualState",
    "VerifiedVisualState",
)


_PLANE_SHAPE_KINDS = {"polyline", "circle", "point", "arc", "vector", "label"}
_TONES = {"primary", "secondary", "muted", "accent"}


def _point(x: float, y: float, scale: float = 1.0) -> dict[str, float]:
    return {"x": round(scale * x, 10), "y": round(scale * y, 10)}


def plane_scene_diagram(
    *,
    title: str,
    caption: str,
    viewport: dict[str, float],
    shapes: Sequence[dict[str, Any]],
    axes: bool = False,
) -> dict[str, Any]:
    """Build a validated plane scene from solver-owned semantic objects."""

    required = ("xMin", "xMax", "yMin", "yMax")
    if any(key not in viewport for key in required):
        raise ValueError("a plane viewport needs xMin, xMax, yMin, and yMax")
    values = {key: float(viewport[key]) for key in required}
    if not values["xMin"] < values["xMax"] or not values["yMin"] < values["yMax"]:
        raise ValueError("a plane viewport must have positive width and height")
    records = [deepcopy(shape) for shape in shapes]
    if any(shape.get("kind") not in _PLANE_SHAPE_KINDS for shape in records):
        raise ValueError("a plane scene contains an unsupported shape")
    shape_ids = [str(shape.get("id")) for shape in records if shape.get("id")]
    if len(shape_ids) != len(set(shape_ids)):
        raise ValueError("plane shape ids must be unique")
    return {
        "version": 1,
        "kind": "plane",
        "title": title,
        "caption": caption,
        "viewport": values,
        "axes": bool(axes),
        "shapes": records,
    }


def _shape_extent_points(shape: dict[str, Any]) -> list[Point]:
    kind = shape.get("kind")
    if kind == "polyline":
        return [
            (float(point["x"]), float(point["y"]))
            for point in shape.get("points") or []
            if "x" in point and "y" in point
        ]
    if kind in {"point", "label"}:
        point = shape.get("point") or {}
        return [(float(point["x"]), float(point["y"]))] if "x" in point and "y" in point else []
    if kind == "vector":
        return [
            (float(point["x"]), float(point["y"]))
            for point in (shape.get("from") or {}, shape.get("to") or {})
            if "x" in point and "y" in point
        ]
    if kind in {"circle", "arc"}:
        center = shape.get("center") or {}
        if "x" not in center or "y" not in center or "radius" not in shape:
            return []
        cx, cy, radius = float(center["x"]), float(center["y"]), abs(float(shape["radius"]))
        return [(cx - radius, cy - radius), (cx + radius, cy + radius)]
    return []


def _focused_viewport(
    shapes: Sequence[dict[str, Any]],
    shape_ids: Sequence[str],
    margin: float,
) -> dict[str, float]:
    wanted = set(shape_ids)
    points = [
        point
        for shape in shapes
        if str(shape.get("id") or "") in wanted
        for point in _shape_extent_points(shape)
    ]
    if not points:
        raise ValueError("focus actions must name at least one visible shape")
    x_values = [point[0] for point in points]
    y_values = [point[1] for point in points]
    width = max(x_values) - min(x_values)
    height = max(y_values) - min(y_values)
    padding = max(float(margin), 0.08 * max(width, height, 1.0))
    return {
        "xMin": min(x_values) - padding,
        "xMax": max(x_values) + padding,
        "yMin": min(y_values) - padding,
        "yMax": max(y_values) + padding,
    }


def apply_plane_scene_actions(
    diagram: dict[str, Any],
    actions: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """Apply a small, reusable visual instruction set to a verified scene.

    The instructions alter presentation only.  Every added shape still has to
    come from the domain solver; this function never infers an unlabeled fact.
    """

    if diagram.get("kind") != "plane":
        raise ValueError("plane scene actions require a plane diagram")
    current = deepcopy(diagram)
    shapes = list(current.get("shapes") or [])
    for action in actions:
        operation = str(action.get("op") or "")
        if operation == "add":
            shape = deepcopy(action.get("shape") or {})
            if shape.get("kind") not in _PLANE_SHAPE_KINDS:
                raise ValueError("add actions require a supported shape")
            shape_id = str(shape.get("id") or "")
            if shape_id and any(str(existing.get("id") or "") == shape_id for existing in shapes):
                raise ValueError(f"shape id {shape_id} already exists")
            shapes.append(shape)
        elif operation == "replace":
            shape_id = str(action.get("shape_id") or "")
            replacement = deepcopy(action.get("shape") or {})
            matches = [index for index, shape in enumerate(shapes) if str(shape.get("id") or "") == shape_id]
            if len(matches) != 1 or replacement.get("kind") not in _PLANE_SHAPE_KINDS:
                raise ValueError("replace actions require one existing id and a supported shape")
            replacement.setdefault("id", shape_id)
            shapes[matches[0]] = replacement
        elif operation == "remove":
            shape_ids = {str(value) for value in action.get("shape_ids") or []}
            if not shape_ids:
                raise ValueError("remove actions require shape ids")
            shapes = [shape for shape in shapes if str(shape.get("id") or "") not in shape_ids]
        elif operation == "highlight":
            shape_ids = {str(value) for value in action.get("shape_ids") or []}
            tone = str(action.get("tone") or "accent")
            if not shape_ids or tone not in _TONES:
                raise ValueError("highlight actions require shape ids and a valid tone")
            found = False
            for shape in shapes:
                if str(shape.get("id") or "") in shape_ids:
                    shape["tone"] = tone
                    found = True
            if not found:
                raise ValueError("highlight actions must name a visible shape")
        elif operation == "focus":
            if isinstance(action.get("viewport"), dict):
                current["viewport"] = plane_scene_diagram(
                    title=str(current.get("title") or ""),
                    caption=str(current.get("caption") or ""),
                    viewport=action["viewport"],
                    shapes=shapes,
                    axes=bool(current.get("axes")),
                )["viewport"]
            else:
                current["viewport"] = _focused_viewport(
                    shapes,
                    [str(value) for value in action.get("shape_ids") or []],
                    float(action.get("margin", 0.2)),
                )
        elif operation == "caption":
            if "title" in action:
                current["title"] = str(action["title"])
            if "caption" in action:
                current["caption"] = str(action["caption"])
        elif operation == "axes":
            current["axes"] = bool(action.get("visible"))
        else:
            raise ValueError(f"unsupported plane scene action: {operation}")
    current["shapes"] = shapes
    return plane_scene_diagram(
        title=str(current.get("title") or ""),
        caption=str(current.get("caption") or ""),
        viewport=current.get("viewport") or {},
        shapes=shapes,
        axes=bool(current.get("axes")),
    )


def compile_plane_scene_timeline(
    initial_diagram: dict[str, Any],
    stages: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Compile proof-owned drawing actions into immutable UI/PDF frames."""

    if not stages:
        raise ValueError("a visual timeline needs at least one stage")
    current = plane_scene_diagram(
        title=str(initial_diagram.get("title") or ""),
        caption=str(initial_diagram.get("caption") or ""),
        viewport=initial_diagram.get("viewport") or {},
        shapes=initial_diagram.get("shapes") or [],
        axes=bool(initial_diagram.get("axes")),
    )
    frames: list[dict[str, Any]] = []
    for stage in stages:
        current = apply_plane_scene_actions(current, stage.get("actions") or [])
        frames.append(deepcopy(current))
    return frames


def regular_polygon_vertices(
    order: int,
    *,
    radius: float = 1.0,
    phase: float = 0.0,
) -> list[Point]:
    if order < 3 or radius <= 0:
        raise ValueError("a regular polygon needs order >= 3 and positive radius")
    return [
        (
            radius * cos(phase + 2.0 * pi * index / order),
            radius * sin(phase + 2.0 * pi * index / order),
        )
        for index in range(order)
    ]


def regular_polygon_disk_radius(order: int, circumradius: float = 1.0) -> float:
    if order < 3 or circumradius <= 0:
        raise ValueError("disk-union sweep needs order >= 3 and positive radius")
    if order % 2 == 0:
        return 2.0 * circumradius
    return 2.0 * circumradius * cos(pi / (2.0 * order))


def regular_polygon_disk_family(
    order: int,
    *,
    circumradius: float = 1.0,
) -> dict[str, Any]:
    vertices = regular_polygon_vertices(order, radius=circumradius)
    return {
        "id": f"regular-{order}",
        "label": f"F_{order}",
        "order": order,
        "centers": vertices,
        "disk_radius": regular_polygon_disk_radius(order, circumradius),
        "skeleton": vertices,
    }


def _reflect_across_line(point: Point, line_start: Point, line_end: Point) -> Point:
    vx, vy = line_end[0] - line_start[0], line_end[1] - line_start[1]
    norm_squared = vx * vx + vy * vy
    if norm_squared <= 0:
        raise ValueError("reflection line must have distinct endpoints")
    wx, wy = point[0] - line_start[0], point[1] - line_start[1]
    projection = (wx * vx + wy * vy) / norm_squared
    foot = (line_start[0] + projection * vx, line_start[1] + projection * vy)
    return (2.0 * foot[0] - point[0], 2.0 * foot[1] - point[1])


def _rotate_about(point: Point, pivot: Point, angle: float) -> Point:
    x, y = point[0] - pivot[0], point[1] - pivot[1]
    return (
        pivot[0] + cos(angle) * x - sin(angle) * y,
        pivot[1] + sin(angle) * x + cos(angle) * y,
    )


def pivot_rotation_diagram(
    vertices: Sequence[Point],
    *,
    shared_edge: tuple[int, int] = (0, 1),
    pivot_index: int = 1,
    total_angle: float,
    frame_fractions: Sequence[float] = (0.0, 0.5, 1.0),
    scale: float = 1.0,
    title: str,
    caption: str,
) -> dict[str, Any]:
    """Draw a rolling frame sequence from a polygon and a contact edge.

    The moving polygon is obtained by reflecting the fixed polygon across the
    shared edge, then rotating it about the selected contact vertex.  Nothing
    in this construction assumes a particular polygon order.
    """

    if len(vertices) < 3:
        raise ValueError("pivot rotation needs at least three vertices")
    if not frame_fractions or any(not 0.0 <= value <= 1.0 for value in frame_fractions):
        raise ValueError("frame fractions must lie in [0, 1]")
    a, b = shared_edge
    if not all(0 <= index < len(vertices) for index in (a, b, pivot_index)):
        raise ValueError("shared edge and pivot indices must name polygon vertices")

    initial = [
        _reflect_across_line(vertex, vertices[a], vertices[b]) for vertex in vertices
    ]
    pivot = vertices[pivot_index]
    tones = ("muted", "primary", "accent")
    shapes: list[dict[str, Any]] = [
        {
            "kind": "polyline",
            "points": [_point(x, y, scale) for x, y in vertices],
            "closed": True,
            "tone": "secondary",
        }
    ]
    all_points = list(vertices)
    for index, fraction in enumerate(frame_fractions):
        frame = [_rotate_about(point, pivot, total_angle * fraction) for point in initial]
        all_points.extend(frame)
        shapes.append(
            {
                "kind": "polyline",
                "points": [_point(x, y, scale) for x, y in frame],
                "closed": True,
                "tone": tones[min(index, len(tones) - 1)],
                "dashed": index < len(frame_fractions) - 1,
            }
        )
    shapes.append(
        {
            "kind": "point",
            "point": _point(pivot[0], pivot[1], scale),
            "label": "支点",
            "tone": "accent",
        }
    )
    orbit_point = max(
        initial,
        key=lambda point: (point[0] - pivot[0]) ** 2 + (point[1] - pivot[1]) ** 2,
    )
    orbit_radius = sqrt(
        (orbit_point[0] - pivot[0]) ** 2 + (orbit_point[1] - pivot[1]) ** 2
    )
    start_angle = degrees(atan2(orbit_point[1] - pivot[1], orbit_point[0] - pivot[0]))
    shapes.append(
        {
            "kind": "arc",
            "center": _point(pivot[0], pivot[1], scale),
            "radius": round(orbit_radius * scale, 10),
            "startAngle": round(start_angle, 8),
            "endAngle": round(start_angle + degrees(total_angle), 8),
            "arrowEnd": True,
            "tone": "accent",
        }
    )
    middle_angle = start_angle + degrees(total_angle) / 2.0
    label_radius = orbit_radius + 0.18
    shapes.append(
        {
            "kind": "label",
            "point": _point(
                pivot[0] + label_radius * cos(middle_angle * pi / 180.0),
                pivot[1] + label_radius * sin(middle_angle * pi / 180.0),
                scale,
            ),
            "text": f"{degrees(total_angle):g}°",
            "tone": "accent",
        }
    )
    x_values = [point[0] * scale for point in all_points]
    y_values = [point[1] * scale for point in all_points]
    margin = 0.45 * scale
    return {
        "version": 1,
        "kind": "plane",
        "title": title,
        "caption": caption,
        "viewport": {
            "xMin": min(x_values) - margin,
            "xMax": max(x_values) + margin,
            "yMin": min(y_values) - margin,
            "yMax": max(y_values) + margin,
        },
        "axes": False,
        "shapes": shapes,
    }


def finite_disk_union_radial_radius(family: dict[str, Any], theta: float) -> float:
    """Return the outer intersection of a ray with a star-shaped disk union."""

    disk_radius = float(family["disk_radius"])
    candidates: list[float] = []
    ux, uy = cos(theta), sin(theta)
    for raw_center in family["centers"]:
        cx, cy = float(raw_center[0]), float(raw_center[1])
        projection = cx * ux + cy * uy
        transverse = cx * uy - cy * ux
        discriminant = disk_radius * disk_radius - transverse * transverse
        if discriminant >= -1e-12:
            candidates.append(projection + sqrt(max(0.0, discriminant)))
    if not candidates:
        raise ValueError("the requested ray misses every disk")
    return max(candidates)


def sample_radial_intersection(
    families: Sequence[dict[str, Any]],
    *,
    samples: int = 180,
) -> list[Point]:
    if not families or samples < 12:
        raise ValueError("radial intersection needs families and at least 12 samples")
    boundary: list[Point] = []
    for index in range(samples + 1):
        theta = 2.0 * pi * index / samples
        radius = min(finite_disk_union_radial_radius(family, theta) for family in families)
        boundary.append((radius * cos(theta), radius * sin(theta)))
    return boundary


def radial_intersection_diagram(
    families: Sequence[dict[str, Any]],
    *,
    current_family_index: int,
    scale: float,
    title: str,
    caption: str,
    samples: int = 180,
) -> dict[str, Any]:
    """Draw an incremental intersection of arbitrary finite disk unions."""

    if not 0 <= current_family_index < len(families):
        raise ValueError("current family index is outside the family sequence")
    active = list(families[: current_family_index + 1])
    current = active[-1]
    common_boundary = sample_radial_intersection(active, samples=samples)
    current_boundary = sample_radial_intersection([current], samples=samples)
    skeleton = list(current.get("skeleton") or [])
    max_radius = max(
        sqrt(x * x + y * y)
        for x, y in [*common_boundary, *current_boundary, *skeleton]
    )
    shapes: list[dict[str, Any]] = [
        {
            "kind": "circle",
            "center": _point(0.0, 0.0, scale),
            "radius": scale,
            "tone": "muted",
            "dashed": True,
        },
        {
            "kind": "polyline",
            "points": [_point(x, y, scale) for x, y in common_boundary],
            "closed": True,
            "tone": "primary",
            "fill": True,
        },
        {
            "kind": "polyline",
            "points": [_point(x, y, scale) for x, y in current_boundary],
            "closed": True,
            "tone": "accent",
            "dashed": len(active) > 1,
        },
    ]
    if skeleton:
        shapes.append(
            {
                "kind": "polyline",
                "points": [_point(x, y, scale) for x, y in skeleton],
                "closed": True,
                "tone": "secondary",
            }
        )
        shapes.extend(
            {
                "kind": "point",
                "point": _point(x, y, scale),
                "label": f"P_{index + 1}",
                "tone": "secondary",
            }
            for index, (x, y) in enumerate(skeleton)
        )
    extent = (max_radius + 0.35) * scale
    return {
        "version": 1,
        "kind": "plane",
        "title": title,
        "caption": caption,
        "viewport": {"xMin": -extent, "xMax": extent, "yMin": -extent, "yMax": extent},
        "axes": False,
        "shapes": shapes,
    }


def function_plot_diagram(
    curves: Sequence[tuple[str, Callable[[float], float], str]],
    *,
    x_min: float,
    x_max: float,
    title: str,
    caption: str,
    marked_points: Sequence[tuple[float, float, str]] = (),
    samples: int = 161,
) -> dict[str, Any]:
    """Compile exact functions into a serializable plot scene.

    The callable is only sampled at the rendering boundary.  Mathematical
    claims such as roots, extrema, or monotonicity must be supplied as verified
    marked points or a separate variation table; the samples are never used as
    a proof.
    """

    if not curves or not x_min < x_max or samples < 24:
        raise ValueError("a function plot needs curves, a domain, and samples")
    sampled_curves: list[tuple[list[Point], str]] = []
    y_values: list[float] = []
    for _, function, tone in curves:
        points: list[Point] = []
        for index in range(samples):
            x_value = x_min + (x_max - x_min) * index / (samples - 1)
            try:
                y_value = float(function(x_value))
            except (ArithmeticError, TypeError, ValueError, OverflowError):
                continue
            if isfinite(y_value):
                points.append((x_value, y_value))
                y_values.append(y_value)
        if len(points) >= 2:
            sampled_curves.append((points, tone))
    if not sampled_curves:
        raise ValueError("none of the supplied functions produced a visible curve")
    ordered = sorted(y_values)
    lower = ordered[max(0, int(len(ordered) * 0.03) - 1)]
    upper = ordered[min(len(ordered) - 1, int(len(ordered) * 0.97))]
    margin = max(0.5, (upper - lower) * 0.14)
    y_min, y_max = lower - margin, upper + margin
    shapes: list[dict[str, Any]] = []
    for points, tone in sampled_curves:
        clipped = [(x, min(y_max, max(y_min, y))) for x, y in points]
        shapes.append(
            {
                "kind": "polyline",
                "points": [_point(x, y) for x, y in clipped],
                "tone": tone,
            }
        )
    for x_value, y_value, label in marked_points:
        shapes.append(
            {
                "kind": "point",
                "point": _point(x_value, y_value),
                "label": label,
                "tone": "accent",
            }
        )
    return {
        "version": 1,
        "kind": "plane",
        "title": title,
        "caption": caption,
        "viewport": {"xMin": x_min, "xMax": x_max, "yMin": y_min, "yMax": y_max},
        "axes": True,
        "shapes": shapes,
    }


def state_transition_diagram(
    states: Sequence[dict[str, Any]],
    transitions: Sequence[dict[str, Any]],
    *,
    title: str,
    caption: str,
) -> dict[str, Any]:
    """Build a reusable state diagram for probability and discrete processes."""

    ids = [str(state.get("id") or "") for state in states]
    if not states or any(not value for value in ids) or len(ids) != len(set(ids)):
        raise ValueError("state ids must be non-empty and unique")
    known = set(ids)
    if any(
        str(edge.get("from")) not in known or str(edge.get("to")) not in known
        for edge in transitions
    ):
        raise ValueError("every transition must connect known states")
    return {
        "version": 1,
        "kind": "state",
        "title": title,
        "caption": caption,
        "states": [dict(state) for state in states],
        "transitions": [dict(edge) for edge in transitions],
    }


def variation_table_diagram(
    columns: Sequence[str],
    rows: Sequence[dict[str, Any]],
    *,
    title: str,
    caption: str,
    variable_label: str = "x",
) -> dict[str, Any]:
    """Build a variation/sign table from already verified interval data."""

    if not columns or not rows:
        raise ValueError("a variation table needs columns and rows")
    if any(len(row.get("cells") or []) != len(columns) for row in rows):
        raise ValueError("every variation row must match the column count")
    return {
        "version": 1,
        "kind": "variation",
        "title": title,
        "caption": caption,
        "variableLabel": variable_label,
        "columns": list(columns),
        "rows": [dict(row) for row in rows],
    }


def progressive_diagram_frames(
    diagram: dict[str, Any],
    count: int,
) -> list[dict[str, Any]]:
    """Reveal one verified diagram incrementally without problem-specific code."""

    if count < 1 or not isinstance(diagram, dict):
        raise ValueError("progressive frames need a diagram and a positive count")
    kind = diagram.get("kind")
    frames: list[dict[str, Any]] = []
    for index in range(count):
        fraction = (index + 1) / count
        frame = dict(diagram)
        if kind == "plane":
            shapes = list(diagram.get("shapes") or [])
            visible = max(1, min(len(shapes), round(len(shapes) * fraction)))
            frame["shapes"] = shapes[:visible]
        elif kind == "state":
            states = list(diagram.get("states") or [])
            visible = max(1, min(len(states), round(len(states) * fraction)))
            visible_states = states[:visible]
            visible_ids = {str(state.get("id")) for state in visible_states}
            frame["states"] = visible_states
            frame["transitions"] = [
                edge
                for edge in diagram.get("transitions") or []
                if str(edge.get("from")) in visible_ids and str(edge.get("to")) in visible_ids
            ]
        elif kind == "variation":
            rows = list(diagram.get("rows") or [])
            visible = max(1, min(len(rows), round(len(rows) * fraction)))
            frame["rows"] = rows[:visible]
        elif kind == "morphism":
            nodes = list(diagram.get("nodes") or [])
            visible = max(2, min(len(nodes), round(len(nodes) * fraction)))
            frame["nodes"] = nodes[:visible]
        elif kind == "calculus":
            variation = diagram.get("variation") or {}
            plot = diagram.get("plot") or {}
            if isinstance(variation, dict) and variation.get("kind") == "variation":
                frame["variation"] = progressive_diagram_frames(variation, count)[index]
            if isinstance(plot, dict) and plot.get("kind") == "plane":
                frame["plot"] = progressive_diagram_frames(plot, count)[index]
        frames.append(frame)
    if frames:
        frames[-1] = dict(diagram)
    return frames


def visual_step(
    *,
    step_id: str,
    title: str,
    explanation_ja: str,
    formula_tex: str,
    morphism: VisualMorphism,
    source_state_id: str,
    target_state_id: str,
    diagram: dict[str, Any],
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not step_id or not title or not explanation_ja:
        raise ValueError("a visual step needs an id, title, and explanation")
    if not isinstance(diagram, dict) or not diagram.get("kind"):
        raise ValueError("a visual step must carry a renderable diagram")
    return {
        "id": step_id,
        "title": title,
        "explanation_ja": explanation_ja,
        "formula_tex": formula_tex,
        "morphism": morphism.to_dict(),
        "source_state": {"id": source_state_id, "type": morphism.input_type},
        "target_state": {"id": target_state_id, "type": morphism.output_type},
        "evidence": dict(evidence or {}),
        "diagram": diagram,
    }


def compose_visual_explanation(
    steps: Iterable[dict[str, Any]],
    *,
    title: str,
) -> dict[str, Any]:
    records = [dict(step) for step in steps]
    if not records:
        raise ValueError("a visual explanation needs at least one step")
    ids = [str(step.get("id") or "") for step in records]
    if len(ids) != len(set(ids)) or any(not step_id for step_id in ids):
        raise ValueError("visual step ids must be non-empty and unique")
    for index, step in enumerate(records):
        if not isinstance(step.get("diagram"), dict):
            raise ValueError(f"visual step {step['id']} has no diagram")
        morphism = step.get("morphism") or {}
        source = step.get("source_state") or {}
        target = step.get("target_state") or {}
        if source.get("type") != morphism.get("input_type"):
            raise ValueError(f"visual step {step['id']} has an invalid input type")
        if target.get("type") != morphism.get("output_type"):
            raise ValueError(f"visual step {step['id']} has an invalid output type")
        if index:
            previous_target = records[index - 1].get("target_state") or {}
            if previous_target.get("id") != source.get("id"):
                raise ValueError(
                    f"visual state chain breaks between {records[index - 1]['id']} and {step['id']}"
                )
            if previous_target.get("type") != source.get("type"):
                raise ValueError(
                    f"visual type chain breaks between {records[index - 1]['id']} and {step['id']}"
                )
    return {
        "version": 1,
        "mode": "stepper",
        "title": title,
        "diagram_required_for_every_step": True,
        "composition_verified": True,
        "morphism_chain": [step["morphism"]["morphism_id"] for step in records],
        "steps": records,
    }
