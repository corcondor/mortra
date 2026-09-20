"""From constructed points to ink on paper: the output connection, not a new geometry.

Nothing here is a new predicate or a new primitive. The fragment's seven
primitives build a lattice of rational points; its existing predicates, composed
with auxiliary points, say which of those points lie in a region; and the rest of
this module is the part that was missing — a common iteration that turns a set of
points into black disks of one radius, and writes them as SVG and PNG.

The drawing convention is fixed and shared by every image:

    a point P becomes the disk { X : |X - P|^2 <= r^2 }, filled black,
    on white paper, with one radius r for all points of all images.

Tone therefore comes from one thing only: how many points are placed where. The
disks of a selection from a lattice of spacing h with r = h/2 are pairwise
non-overlapping (tangent at closest), so the black coverage of a window that
contains whole disks is exactly (number of disks) * pi r^2 / area, and the
largest coverage the convention can reach is pi/4 = 0.7854. A target above that
cannot be asked of it.

What is reused: `geometry_relational_dsl.execute_primitive` for every constructed
point, the predicate polynomials the fragment already assigns to `coll`, `cong`
and `midp`, and Pillow, which the repository already depends on. What is new is
the iteration, the selection rule and the two writers.
"""
from __future__ import annotations

from collections import Counter
from fractions import Fraction
from functools import cmp_to_key
from math import pi
from pathlib import Path

from math_os_prototype import geometry_relational_dsl as rdsl

# ---------------------------------------------------------------------------
# The drawing convention
# ---------------------------------------------------------------------------

BLACK = "#000000"
WHITE = "#ffffff"


def maximum_coverage(radius, spacing):
    """The largest black fraction this convention can reach on a lattice of this spacing."""
    return float(pi*radius*radius/(spacing*spacing))


def coverage_from_fill(fill, radius, spacing):
    """The black fraction a given fraction of inked lattice sites produces."""
    return float(fill)*maximum_coverage(radius, spacing)


def fill_for_coverage(coverage, radius, spacing):
    """The fraction of lattice sites to ink for a target black fraction."""
    ceiling = maximum_coverage(radius, spacing)
    if coverage > ceiling+1e-12:
        raise ValueError(f"coverage {coverage} is above what radius {radius} on spacing {spacing} "
                         f"can reach ({ceiling:.4f})")
    return coverage/ceiling


# ---------------------------------------------------------------------------
# A lattice of rational points, built by the fragment's own primitives
# ---------------------------------------------------------------------------

def dyadic_unit_lattice(depth, stats=None):
    """The dyadic lattice of the unit square, every point a `midpoint` of two others.

    Refinement by halving: the four corners are given, and each round inserts the
    midpoint of every horizontally and vertically adjacent pair and of every cell.
    Each insertion is one call to the fragment's `midpoint` primitive, so the
    lattice is produced by the geometry, not by arithmetic written here.
    """
    stats = stats if stats is not None else Counter()
    coordinates = {"c00": (Fraction(0), Fraction(0)), "c10": (Fraction(1), Fraction(0)),
                   "c01": (Fraction(0), Fraction(1)), "c11": (Fraction(1), Fraction(1))}
    names = {(0, 0): "c00", (1, 0): "c10", (0, 1): "c01", (1, 1): "c11"}
    side = 1
    for level in range(depth):
        finer = {}
        for (i, j), name in names.items():
            finer[(2*i, 2*j)] = name
        for i in range(side+1):
            for j in range(side+1):
                for di, dj in ((1, 0), (0, 1), (1, 1)):
                    a, b = (2*i+di, 2*j+dj)
                    if a > 2*side or b > 2*side or (a, b) in finer:
                        continue
                    if di and dj:
                        left, right = names[(i, j)], names[(i+1, j+1)]
                    elif di:
                        left, right = names[(i, j)], names[(i+1, j)]
                    else:
                        left, right = names[(i, j)], names[(i, j+1)]
                    # the name has to carry the round: an index that exists at one
                    # refinement exists again, doubled, at the next, and reusing the
                    # name would overwrite the earlier point under the earlier index
                    new = f"p{level}_{a}_{b}"
                    xy, reason = rdsl.execute_primitive("midpoint", [left, right], coordinates)
                    if xy is None:
                        raise RuntimeError(f"midpoint refused on the lattice: {reason}")
                    stats["primitive_applications"] += 1
                    stats["midpoint"] += 1
                    coordinates[new] = xy
                    finer[(a, b)] = new
        names = finer
        side *= 2
    return {(i, j): coordinates[name] for (i, j), name in names.items()}, stats


def translate(point_name, origin_name, target_name, coordinates, stats=None):
    """P + (T - O), as the fragment writes it: mirror(O, midpoint(P, T)).

    Two existing primitives and no new one. `midpoint(P,T)` is the centre of P and
    T, and mirroring the origin in that centre lands on P + T - O.
    """
    stats = stats if stats is not None else Counter()
    centre, reason = rdsl.execute_primitive("midpoint", [point_name, target_name], coordinates)
    if centre is None:
        return None, reason
    stats["primitive_applications"] += 1
    stats["midpoint"] += 1
    helper = f"__mid_{len(coordinates)}"
    coordinates[helper] = centre
    moved, reason = rdsl.execute_primitive("mirror", [origin_name, helper], coordinates)
    del coordinates[helper]
    if moved is None:
        return None, reason
    stats["primitive_applications"] += 1
    stats["mirror"] += 1
    return moved, None


def paper_lattice(width_cells, height_cells, depth, stats=None):
    """A lattice over a `width_cells` x `height_cells` sheet, spacing 1/2**depth.

    The unit cell is built once by halving, and the whole sheet is covered by
    translating it, so every point of the sheet is the output of `midpoint` and
    `mirror` applied to points the sheet already had.
    """
    stats = stats if stats is not None else Counter()
    cell, _ = dyadic_unit_lattice(depth, stats)
    side = 2**depth
    coordinates = {"origin": (Fraction(0), Fraction(0))}
    points = {}
    for (i, j), xy in cell.items():
        coordinates[f"u{i}_{j}"] = xy
    for a in range(width_cells):
        for b in range(height_cells):
            target = f"t{a}_{b}"
            coordinates[target] = (Fraction(a), Fraction(b))
            for (i, j), xy in cell.items():
                index = (a*side+i, b*side+j)
                if index in points:
                    continue
                if a == 0 and b == 0:
                    points[index] = xy
                    continue
                moved, reason = translate(f"u{i}_{j}", "origin", target, coordinates, stats)
                if moved is None:
                    raise RuntimeError(f"translation refused on the lattice: {reason}")
                points[index] = moved
    stats["lattice_points"] = len(points)
    return points, stats


# ---------------------------------------------------------------------------
# Regions, as compositions of predicates the fragment already has
# ---------------------------------------------------------------------------

def _squared_distance(p, q):
    return (p[0]-q[0])**2+(p[1]-q[1])**2


def in_closed_disk(point, centre, through):
    """The decision, which is a comparison of exact rationals and nothing more.

    The relation being decided is `exists U V: midp(P,U,V) and cong(O,U,O,A) and
    cong(O,V,O,A)`: P is the midpoint of two points of the circle about O through
    A. Writing U = P + v and V = P - v, the two `cong` atoms force v to be
    perpendicular to P - O with |v|^2 = |OA|^2 - |P-O|^2, and such a v exists over
    the reals exactly when |P-O| <= |OA|. That is the comparison below.

    It is a comparison, and this docstring used to claim more. The witnesses are
    built, and the three atoms actually decided, by
    `geometry_sign.witness_in_closed_disk`, which also reports the field the
    witness needed: often QQ, and often a quadratic extension, because the
    perpendicular offset is rational only when |OA|^2 - |P-O|^2 over |P-O|^2 is a
    square. This function is what the per-pixel loops call; that one is what a
    certificate comes from.
    """
    return _squared_distance(point, centre) <= _squared_distance(centre, through)


def certified_in_closed_disk(point, centre, through):
    """The same relation with its witnesses built and its atoms decided."""
    from math_os_prototype import geometry_sign

    return geometry_sign.witness_in_closed_disk(point, centre, through)


def on_closed_segment(point, a, b):
    """`coll(A,P,B)` and the disk on AB as diameter: the decision, comparison and all.

    Collinearity alone admits the whole line; intersecting it with the disk whose
    centre is midpoint(A,B) and whose radius is |AB|/2 cuts it down to the
    segment. The first part is an atom of the fragment and is decided as one; the
    second is the comparison above, and `geometry_sign.certify_on_closed_segment`
    is where it acquires a witness.
    """
    cross = (b[0]-a[0])*(point[1]-a[1])-(b[1]-a[1])*(point[0]-a[0])
    if cross != 0:
        return False
    centre = ((a[0]+b[0])/2, (a[1]+b[1])/2)
    return _squared_distance(point, centre) <= _squared_distance(centre, a)


def strictly_between(point, a, b):
    """On the segment and equal to neither end: the segment relation with `diff` added."""
    if point == a or point == b:
        return False
    return on_closed_segment(point, a, b)


def occluded(x, light, occluder_a, occluder_b, coordinates=None, stats=None):
    """Whether some point of the segment occluder lies strictly between the light and X.

    The relation is
        exists P: P on segment(A,B) and P strictly between L and X,
    every part of which is a composition of `coll`, `cong` and `diff` with
    auxiliary points. The execution below replaces the existential by the one
    candidate it can have: for a straight-line light and a segment occluder, the
    points of line(L,X) that could occlude are the points of line(A,B) on it, and
    two distinct lines meet in at most one point, which the fragment's own
    `intersection_ll` produces. The assumptions that make the two agree are that
    L is not on line(A,B) and that line(L,X) is not parallel to line(A,B); the
    first is checked by the caller, the second appears as a refusal and is
    reported as "no occlusion" because a ray parallel to the occluder meets it
    nowhere.
    """
    stats = stats if stats is not None else Counter()
    coordinates = dict(coordinates or {})
    coordinates.update({"__l": light, "__x": x, "__a": occluder_a, "__b": occluder_b})
    if x == light:
        return False, "the evaluation point is the light"
    meeting, reason = rdsl.execute_primitive("intersection_ll", ["__l", "__x", "__a", "__b"],
                                             coordinates)
    stats["primitive_applications"] += 1
    stats["intersection_ll"] += 1
    if meeting is None:
        # two lines that do not meet are parallel OR the same line, and the second
        # case is not "no occlusion": the occluder lies along the ray, and whether
        # it blocks it is an interval question decided below. `intersection_ll`
        # refuses both alike, so they have to be told apart here
        if _collinear(light, x, occluder_a) and _collinear(light, x, occluder_b):
            stats["the_occluder_lies_along_the_ray"] += 1
            return _along_the_ray(light, x, occluder_a, occluder_b)
        stats["parallel_or_degenerate"] += 1
        return False, reason
    if not on_closed_segment(meeting, occluder_a, occluder_b):
        stats["meets_the_line_but_not_the_segment"] += 1
        return False, "the ray meets the line of the occluder outside its segment"
    if not strictly_between(meeting, light, x):
        stats["behind_the_light_or_beyond_the_point"] += 1
        return False, "the occluding point is not between the light and the point"
    stats["occluded"] += 1
    return True, None


# ---------------------------------------------------------------------------
# Choosing which lattice sites take ink
# ---------------------------------------------------------------------------

def _collinear(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]) == 0


def _along_the_ray(light, x, a, b):
    """The occluder lies on the ray's own line: does its span meet the open ray?

    Everything is collinear, so each point has a parameter along L -> X, and the
    question is whether the interval of the occluder meets the open interval
    (0, 1). That is four comparisons of exact rationals and no construction at
    all, which is why `intersection_ll` cannot answer it: there is no single
    meeting point to construct.
    """
    dx, dy = Fraction(x[0])-Fraction(light[0]), Fraction(x[1])-Fraction(light[1])
    span = dx*dx+dy*dy
    if span == 0:
        return False, "the evaluation point is the light"

    def parameter(point):
        return ((Fraction(point[0])-Fraction(light[0]))*dx
                + (Fraction(point[1])-Fraction(light[1]))*dy)/span
    low, high = sorted((parameter(a), parameter(b)))
    lower, upper = max(low, Fraction(0)), min(high, Fraction(1))
    if lower < upper or (lower == upper and 0 < lower < 1):
        return True, None
    return False, "the occluder lies along the ray but its span misses the open segment"


def bayer(order):
    """An ordered-dither threshold matrix: deterministic, no randomness anywhere."""
    matrix = [[0]]
    size = 1
    while size < order:
        matrix = [[4*v for v in row]+[4*v+2 for v in row] for row in matrix] + \
                 [[4*v+3 for v in row]+[4*v+1 for v in row] for row in matrix]
        size *= 2
    return matrix


BAYER8 = bayer(8)


def select(points, level, *, order=8, matrix=None):
    """Ink a lattice site when its dither threshold falls under the wanted level.

    `level` is a function of the point's coordinates returning the fraction of
    sites to ink there, between 0 and 1. The rule is a plain iteration over the
    lattice indices: it is the selection procedure, deliberately separate from
    the rule that built the lattice.
    """
    matrix = matrix or BAYER8
    cells = order*order
    chosen = []
    for (i, j), xy in sorted(points.items()):
        wanted = level(xy)
        threshold = (matrix[i % order][j % order]+Fraction(1, 2))/cells
        if wanted > threshold:
            chosen.append(((i, j), xy))
    return chosen


# ---------------------------------------------------------------------------
# Measuring what was drawn
# ---------------------------------------------------------------------------

def pairwise_separation_ok(points, radius):
    """Whether no two disks overlap, checked on a grid of buckets rather than all pairs."""
    diameter = 2*radius
    buckets = {}
    for _, xy in points:
        key = (int(xy[0]/diameter), int(xy[1]/diameter))
        buckets.setdefault(key, []).append(xy)
    for (bx, by), members in buckets.items():
        neighbours = [p for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                      for p in buckets.get((bx+dx, by+dy), ())]
        for point in members:
            for other in neighbours:
                if other is point or other == point:
                    continue
                if _squared_distance(point, other) < diameter*diameter:
                    return False, (point, other)
    return True, None


def coverage(points, radius, window, *, samples=400):
    """The black fraction of a window, by counting covered sample cells.

    An approximation, and reported as one: the window is split into `samples` by
    `samples` cells and a cell counts as black when its centre lies in some disk.
    The resolution is part of the record.
    """
    x0, y0, x1, y1 = (Fraction(v) for v in window)
    width, height = x1-x0, y1-y0
    inside = [xy for _, xy in points
              if x0-radius <= xy[0] <= x1+radius and y0-radius <= xy[1] <= y1+radius]
    buckets = {}
    diameter = 2*radius
    for xy in inside:
        buckets.setdefault((int(xy[0]/diameter), int(xy[1]/diameter)), []).append(xy)
    covered = 0
    radius_squared = radius*radius
    for a in range(samples):
        cx = x0+width*(2*a+1)/(2*samples)
        for b in range(samples):
            cy = y0+height*(2*b+1)/(2*samples)
            key = (int(cx/diameter), int(cy/diameter))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    hit = False
                    for xy in buckets.get((key[0]+dx, key[1]+dy), ()):
                        if (cx-xy[0])**2+(cy-xy[1])**2 <= radius_squared:
                            hit = True
                            break
                    if hit:
                        covered += 1
                        break
                else:
                    continue
                break
    return {"black_coverage": covered/(samples*samples), "method": "sample-cell centres",
            "resolution": f"{samples}x{samples} cells over the window",
            "window": [float(v) for v in (x0, y0, x1, y1)],
            "disks_considered": len(inside)}


def analytic_coverage(points, radius, window):
    """The black fraction from the disk count, exact while no disk crosses the window edge."""
    x0, y0, x1, y1 = (Fraction(v) for v in window)
    whole = [xy for _, xy in points
             if x0+radius <= xy[0] <= x1-radius and y0+radius <= xy[1] <= y1-radius]
    touching = [xy for _, xy in points
                if (x0-radius <= xy[0] <= x1+radius and y0-radius <= xy[1] <= y1+radius)
                and not (x0+radius <= xy[0] <= x1-radius and y0+radius <= xy[1] <= y1-radius)]
    area = float((x1-x0)*(y1-y0))
    return {"black_coverage_from_whole_disks": len(whole)*float(pi)*float(radius)**2/area,
            "disks_wholly_inside": len(whole), "disks_crossing_the_edge": len(touching),
            "exact_while": "no disk crosses the window edge, and disks do not overlap"}


# ---------------------------------------------------------------------------
# The two writers
# ---------------------------------------------------------------------------

def _transform(paper, pixels_per_unit):
    x0, y0, x1, y1 = paper
    width = int(round(float(x1-x0)*pixels_per_unit))
    height = int(round(float(y1-y0)*pixels_per_unit))

    def to_pixels(xy):
        return (float(xy[0]-x0)*pixels_per_unit, float(y1-xy[1])*pixels_per_unit)
    return to_pixels, width, height


def write_svg(path, points, radius, paper, *, pixels_per_unit=300):
    """Black circles of one radius on white. The writer draws what it is given."""
    to_pixels, width, height = _transform(paper, pixels_per_unit)
    radius_px = float(radius)*pixels_per_unit
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
             f'viewBox="0 0 {width} {height}">',
             f'<rect width="{width}" height="{height}" fill="{WHITE}"/>']
    for _, xy in points:
        x, y = to_pixels(xy)
        lines.append(f'<circle cx="{x:.4f}" cy="{y:.4f}" r="{radius_px:.4f}" fill="{BLACK}"/>')
    lines.append("</svg>")
    Path(path).write_text("\n".join(lines)+"\n", encoding="utf-8")
    return {"path": str(path), "width": width, "height": height, "radius_px": radius_px,
            "circles": len(points)}


def write_png(path, points, radius, paper, *, pixels_per_unit=300, supersample=3):
    """The same disks rasterised. The grey at a disk's edge is the sampling, not a tone."""
    from PIL import Image, ImageDraw

    to_pixels, width, height = _transform(paper, pixels_per_unit)
    radius_px = float(radius)*pixels_per_unit
    big = Image.new("L", (width*supersample, height*supersample), 255)
    draw = ImageDraw.Draw(big)
    scaled = radius_px*supersample
    for _, xy in points:
        x, y = to_pixels(xy)
        cx, cy = x*supersample, y*supersample
        draw.ellipse([cx-scaled, cy-scaled, cx+scaled, cy+scaled], fill=0)
    image = big.resize((width, height), Image.BOX)
    image.save(path)
    return {"path": str(path), "width": width, "height": height, "radius_px": radius_px,
            "dots": len(points), "supersample": supersample,
            "note": "the disks are drawn opaque black at a higher resolution and box-averaged "
                    "down, so a pixel on a disk's edge holds the fraction of it that is covered. "
                    "That grey is a rasterisation artefact of the sampling, not a drawn tone; the "
                    "SVG holds the disks themselves"}


def check_svg_is_one_radius_black_circles(path):
    """Every element is a black circle, and every circle has the same radius."""
    import re

    text = Path(path).read_text(encoding="utf-8")
    radii = set(re.findall(r'<circle [^>]*r="([0-9.]+)"', text))
    fills = set(re.findall(r'<circle [^>]*fill="([^"]+)"', text))
    others = re.findall(r"<(?!circle|/?svg|rect)([a-zA-Z]+)", text)
    return {"distinct_radii": sorted(radii), "distinct_fills": sorted(fills),
            "non_circle_elements": sorted(set(others)),
            "one_radius": len(radii) == 1, "all_black": fills <= {BLACK},
            "no_other_marks": not others}


# ---------------------------------------------------------------------------
# The boundary of a shadow, as constructed points
# ---------------------------------------------------------------------------

def window_edges(window):
    """The four sides of a rectangular window, as pairs of corners."""
    x0, y0, x1, y1 = (Fraction(v) for v in window)
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return [(corners[i], corners[(i+1) % 4]) for i in range(4)], corners


def shadow_polygon(light, occluder, window):
    """The corners of the CLOSURE of the shadow inside the window, each one constructed.

    Three kinds of corner, and the same routine finds all of them for any light,
    segment and window: where a boundary ray through an end of the occluder
    leaves the window; the corners of the window that are themselves in shadow;
    and, when the occluder crosses the window, where it crosses it and where its
    ends stand inside.

    This is the closure, and that is a different set from the shadow. A point of
    the occluder is not in the shadow — nothing lies strictly between it and the
    light — but it is a limit of points that are, so it belongs to the outline
    that gets drawn. The membership used to place ink is `occluded`, which
    excludes it; this routine is for the outline and its area.
    """
    a, b = occluder
    edges, corners = window_edges(window)
    coordinates = {"__l": light, "__a": a, "__b": b}
    found = []
    for index, end in (("a", a), ("b", b)):
        coordinates["__end"] = end
        for number, (p, q) in enumerate(edges):
            coordinates["__p"], coordinates["__q"] = p, q
            meeting, _ = rdsl.execute_primitive("intersection_ll", ["__l", "__end", "__p", "__q"],
                                                coordinates)
            if meeting is None:
                continue
            if not on_closed_segment(meeting, p, q):
                continue
            if not occluded(meeting, light, a, b)[0]:
                continue
            found.append(meeting)
    for corner in corners:
        if occluded(corner, light, a, b)[0]:
            found.append(corner)
    # when the occluder itself stands inside the window, the shadow begins at it:
    # its ends are corners of the region although no point of it is "beyond" it
    x0, y0, x1, y1 = (Fraction(v) for v in window)
    for end in (a, b):
        if x0 <= end[0] <= x1 and y0 <= end[1] <= y1:
            found.append(end)
    # an occluder that crosses the window shades it from where it crosses: those
    # crossings are corners of the closure although no point of them is in the
    # shadow itself
    coordinates["__a"], coordinates["__b"] = a, b
    for number, (p, q) in enumerate(edges):
        coordinates["__p"], coordinates["__q"] = p, q
        meeting, _ = rdsl.execute_primitive("intersection_ll", ["__a", "__b", "__p", "__q"],
                                            coordinates)
        if meeting is None:
            continue
        if on_closed_segment(meeting, p, q) and on_closed_segment(meeting, a, b):
            found.append(meeting)
    unique = sorted(set(found))
    if len(unique) < 3:
        return []
    cx = Fraction(sum(Fraction(p[0]) for p in unique), len(unique))
    cy = Fraction(sum(Fraction(p[1]) for p in unique), len(unique))
    return _around(unique, (cx, cy))


def _around(points, centre):
    """Sort points by angle about a centre, by signs alone and never by atan2.

    The corners here are exact rationals produced by `intersection_ll`, and the
    area that follows is a shoelace sum, which is order-dependent. Sorting them
    by the angle of a float would let the rounding choose the order of two
    nearly equal angles, and with it the outline and the area. A half-plane test
    and the sign of a cross product decide the same order exactly.
    """
    def half(p):
        dy = Fraction(p[1])-centre[1]
        dx = Fraction(p[0])-centre[0]
        return 0 if (dy > 0 or (dy == 0 and dx >= 0)) else 1

    def turn(p, q):
        return ((Fraction(p[0])-centre[0])*(Fraction(q[1])-centre[1])
                - (Fraction(p[1])-centre[1])*(Fraction(q[0])-centre[0]))

    def compare(p, q):
        if half(p) != half(q):
            return -1 if half(p) < half(q) else 1
        cross = turn(p, q)
        if cross != 0:
            return -1 if cross > 0 else 1
        near = ((Fraction(p[0])-centre[0])**2+(Fraction(p[1])-centre[1])**2
                - (Fraction(q[0])-centre[0])**2-(Fraction(q[1])-centre[1])**2)
        return (near > 0)-(near < 0)
    return sorted(points, key=cmp_to_key(compare))


def polygon_area(vertices):
    """The exact area of a simple polygon given in order, by the shoelace sum."""
    total = Fraction(0)
    for index, (x, y) in enumerate(vertices):
        nx, ny = vertices[(index+1) % len(vertices)]
        total += Fraction(x)*Fraction(ny)-Fraction(nx)*Fraction(y)
    return abs(total)/2
