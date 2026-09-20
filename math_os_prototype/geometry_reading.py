"""Reading a glyph out of a raster image, with the fragment deciding the geometry.

The measurement layer is `geometry_raster`: it turns black cells into a thinned
skeleton and that skeleton into a graph of chains. Nothing there is a claim. This
module is where the claims start, and it does three things.

**It constructs the corners rather than measuring them.** Thinning rounds a
corner: the pixels on either side of one do not lie on the strokes that lead into
it, and the rounded pixel that sits at the apex is in the wrong place. So the
corner is not read off the image at all. Each straight part of a chain is taken
from two pixels well inside it, and the corner is where the two lines meet --
which is the fragment's own `intersection_ll`. A junction where three strokes
come together is the same construction, and a stroke's free end is its line
carried out to where the ink stops.

**It snaps once, and says so.** The constructed corners are exact rationals but
they are exact rationals derived from a measurement, so they are rounded onto a
coarse lattice in a frame fixed by the ink's own bounding box. That rounding is
the last inexact act. Everything after it is decided.

**It describes a glyph by relations, not by coordinates.** The description is the
multiset of relations of the fragment that hold of the recovered strokes: which
strokes are parallel, which are perpendicular, which are equal in length, which
corners are collinear, which corners stand on the baseline, the cap line or the
mid line. Each one is decided by `atom_holds`, exactly, over the rationals. Two
glyphs match when their descriptions agree, and because relations do not mention
coordinates the description survives a change of proportion that coordinates do
not -- which is the whole reason for doing it this way, and is measured rather
than asserted in `scripts/run_alphabet_reading.py`.
"""
from __future__ import annotations

from collections import Counter
from fractions import Fraction

from math_os_prototype import geometry_ink as ink
from math_os_prototype import geometry_raster as raster
from math_os_prototype import geometry_relational_dsl as rdsl

# ---------------------------------------------------------------------------
# The frame: a few auxiliary points, so that "horizontal" is a relation
# ---------------------------------------------------------------------------

# A glyph is normalised into a box six units tall whose left edge is x = 0 and
# whose baseline is y = 0. These points are what the fragment's predicates are
# applied against; they carry no information of their own.
FRAME = {
    "__o": (Fraction(0), Fraction(0)),
    "__ex": (Fraction(1), Fraction(0)),
    "__ey": (Fraction(0), Fraction(1)),
    "__diag": (Fraction(1), Fraction(1)),
    "__anti": (Fraction(1), Fraction(-1)),
    "__cap0": (Fraction(0), Fraction(6)),
    "__cap1": (Fraction(1), Fraction(6)),
    "__mid0": (Fraction(0), Fraction(3)),
    "__mid1": (Fraction(1), Fraction(3)),
}

DIRECTIONS = (("across", "__o", "__ex"), ("upright", "__o", "__ey"),
              ("rising", "__o", "__diag"), ("falling", "__o", "__anti"))

LINES = (("baseline", "__o", "__ex"), ("capline", "__cap0", "__cap1"),
         ("midline", "__mid0", "__mid1"), ("leftedge", "__o", "__ey"))

HEIGHT = Fraction(6)


class Glyph:
    """Corners and straight strokes in the normalised box, plus the hole count."""

    __slots__ = ("vertices", "edges", "holes", "notes")

    def __init__(self, vertices, edges, holes, notes=None):
        self.vertices = [tuple(v) for v in vertices]
        self.edges = [tuple(sorted(e)) for e in edges]
        self.holes = int(holes)
        self.notes = dict(notes or {})

    def degrees(self):
        count = Counter()
        for a, b in self.edges:
            count[a] += 1
            count[b] += 1
        return [count.get(i, 0) for i in range(len(self.vertices))]

    def coordinates(self, prefix="v"):
        named = {f"{prefix}{i}": xy for i, xy in enumerate(self.vertices)}
        named.update(FRAME)
        return named

    def summary(self):
        return {"vertices": len(self.vertices), "edges": len(self.edges),
                "holes": self.holes, "degrees": sorted(self.degrees()),
                "points": [[str(x), str(y)] for x, y in self.vertices],
                "strokes": [list(e) for e in self.edges]}


# ---------------------------------------------------------------------------
# Measurement: what the ink itself says about its size
# ---------------------------------------------------------------------------

def measure(bitmap):
    """The ink's thickness and the box it occupies, in cell coordinates.

    The ink is cleaned first, by the most conservative rule there is: a cell with
    at most one black neighbour goes and a gap with at least seven fills. Ragged
    ink otherwise grows spurs under thinning, and a stroke two cells wide is not
    harmed. The thickness is then the black area divided by the length of its
    skeleton, which is the mean width of a stroke; the radius is half of it. The glyph's own box
    is the ink's box pulled in by that radius, because a stroke of radius r
    reaches r beyond the line it was drawn from. Both are estimates and both are
    used only to place the snapping lattice.
    """
    pieces = raster.components(raster.Bitmap(bitmap.width, bitmap.height,
                                             raster.despeckle(bitmap.black)))
    if not pieces:
        raise ValueError("the image has no ink")
    body = pieces[0]
    skeleton = raster.thin(body)
    thickness = Fraction(len(body), max(1, len(skeleton)))
    radius = thickness/2
    imin = min(c[0] for c in body)
    imax = max(c[0] for c in body)
    jmin = min(c[1] for c in body)
    jmax = max(c[1] for c in body)
    return {"body": body, "skeleton": skeleton, "thickness": thickness, "radius": radius,
            "box": (Fraction(imin)+radius, Fraction(jmin)+radius,
                    Fraction(imax+1)-radius, Fraction(jmax+1)-radius),
            "pieces": len(pieces)}


# ---------------------------------------------------------------------------
# Construction: where two fitted lines meet
# ---------------------------------------------------------------------------

def _meet(line_a, line_b):
    """The fragment's `intersection_ll` on two lines given by pairs of points."""
    coordinates = {"__p": line_a[0], "__q": line_a[1], "__r": line_b[0], "__s": line_b[1]}
    xy, reason = rdsl.execute_primitive("intersection_ll", ["__p", "__q", "__r", "__s"],
                                        coordinates)
    if xy is None:
        return None, reason
    return (Fraction(xy[0]), Fraction(xy[1])), None


def _as_point(cell):
    return (Fraction(2*cell[0]+1, 2), Fraction(2*cell[1]+1, 2))


def _carry(line, towards, distance):
    """The point on the line, past `towards`, a given distance further out.

    A thinned stroke stops short of where the ink does, by about the radius of
    the pen. This carries the fitted line out by that much so that a free end
    lands where the stroke ends rather than where the thinning stopped.
    """
    (ax, ay), (bx, by) = line
    dx, dy = bx-ax, by-ay
    squared = dx*dx+dy*dy
    if squared == 0:
        return towards
    # the exact unit vector is irrational; the step is taken on the squared
    # length, which is a rational approximation and is part of the measurement
    length = Fraction(_isqrt_fraction(squared))
    if length == 0:
        return towards
    return (towards[0]+dx*distance/length, towards[1]+dy*distance/length)


def _isqrt_fraction(value, *, digits=10**6):
    """A rational close to the square root of a rational: measurement, not geometry.

    The fragment has no square root, and it does not need one: this appears only
    in carrying a free end out to where the ink stops, which is a step of the
    measurement and is rounded away by the snap.
    """
    return Fraction(_integer_sqrt(int(value*digits*digits)), digits)


def _integer_sqrt(value):
    if value < 0:
        raise ValueError("negative")
    if value == 0:
        return 0
    guess = 1 << ((value.bit_length()+1)//2)
    while True:
        better = (guess+value//guess)//2
        if better >= guess:
            return guess
        guess = better


# ---------------------------------------------------------------------------
# Recovering a glyph from an image
# ---------------------------------------------------------------------------

def recover(bitmap, *, grid=1, tolerance_divisor=12):
    """A raster image in, a glyph of exact rational corners out.

    The steps are: measure the ink; thin it; make a graph of its chains; cut each
    chain at its corners; fit a line to the inside of each straight part; place
    every corner where the relevant lines meet; carry the free ends out to where
    the ink stops; normalise by the ink's box; snap.
    """
    gauge = measure(bitmap)
    body, skeleton, radius = gauge["body"], gauge["skeleton"], gauge["radius"]
    junction = max(1, round(float(radius)))
    nodes, edges = raster.skeleton_graph(skeleton, junction_radius=junction)
    nodes, edges = raster.prune(nodes, edges, max(2, round(float(3*radius/2))))
    nodes, edges = raster.dissolve(nodes, edges)
    if not edges:
        raise ValueError("the ink has no stroke")
    x0, y0, x1, y1 = gauge["box"]
    tolerance = max(Fraction(1), (y1-y0)/tolerance_divisor)
    margin = max(1, round(float(radius)))

    # every straight part of every chain, as a line and the node it starts from
    parts = []
    for a, b, chain in edges:
        pieces = raster.straight_pieces(chain, tolerance, margin)
        lines = [(_as_point(p), _as_point(q)) for p, q, _ in pieces]
        parts.append({"a": a, "b": b, "chain": chain, "lines": lines})

    # a node's place is where the lines that reach it meet
    incident = {index: [] for index in range(len(nodes))}
    for part in parts:
        incident[part["a"]].append((part["lines"][0], part["chain"][0], part))
        incident[part["b"]].append((part["lines"][-1], part["chain"][-1], part))
    placed, constructions = {}, Counter()
    for index, arrivals in incident.items():
        centre = _centroid(nodes[index])
        if len(arrivals) >= 2:
            best, chosen = None, None
            for i in range(len(arrivals)):
                for j in range(i+1, len(arrivals)):
                    meeting, _ = _meet(arrivals[i][0], arrivals[j][0])
                    if meeting is None:
                        continue
                    apart = _transversality(arrivals[i][0], arrivals[j][0])
                    if best is None or apart > best:
                        best, chosen = apart, meeting
            if chosen is not None and _within(chosen, gauge["box"], y1-y0):
                placed[index] = chosen
                constructions["junction_by_intersection"] += 1
                continue
        if arrivals:
            line, last, _ = arrivals[0]
            end = _as_point(last)
            placed[index] = _carry(line, end, radius) if _points_away(line, end) \
                else _carry((line[1], line[0]), end, radius)
            constructions["free_end_carried_out"] += 1
        else:
            placed[index] = centre
            constructions["node_left_at_its_centre"] += 1

    # a corner inside a chain is where its two straight parts meet
    vertices, keys, strokes = [], {}, []

    def site(point):
        snapped = _snap(point, x0, y0, y1, grid)
        if snapped not in keys:
            keys[snapped] = len(vertices)
            vertices.append(snapped)
        return keys[snapped]

    for part in parts:
        chain_points = [placed[part["a"]]]
        for first, second in zip(part["lines"], part["lines"][1:]):
            meeting, _ = _meet(first, second)
            if meeting is None or not _within(meeting, gauge["box"], y1-y0):
                # two nearly parallel pieces meet far outside the glyph; that is
                # not a corner of the letter, it is the fit going slack
                constructions["corner_refused_and_taken_from_the_chain"] += 1
                meeting = _as_point(part["chain"][min(len(chain_points),
                                                      len(part["chain"])-1)])
            else:
                constructions["corner_by_intersection"] += 1
            chain_points.append(meeting)
        chain_points.append(placed[part["b"]])
        indices = [site(p) for p in chain_points]
        for one, two in zip(indices, indices[1:]):
            if one != two:
                strokes.append((one, two))

    holes = raster.holes(body, bitmap.width, bitmap.height)
    vertices, strokes, straightened = straighten(vertices, sorted(set(strokes)))
    constructions["corner_dissolved_as_collinear"] += straightened
    notes = {"thickness": str(gauge["thickness"]), "radius": str(gauge["radius"]),
             "ink_pieces": gauge["pieces"], "grid": grid,
             "tolerance": str(tolerance), "junction_radius": junction,
             "constructions": dict(constructions)}
    return Glyph(vertices, strokes, holes, notes)


def _within(point, box, span):
    """Whether a constructed point is anywhere near the ink it was built from."""
    x0, y0, x1, y1 = box
    slack = span
    return x0-slack <= point[0] <= x1+slack and y0-slack <= point[1] <= y1+slack


def straighten(vertices, edges):
    """Dissolve a corner that is not one, with `coll` deciding whether it is.

    A chain of pixels that runs straight can still be cut in two by the polyline
    step, and the two pieces then meet at a point that is on both of them. The
    fragment can say so: if a corner has exactly two strokes and its two
    neighbours are collinear with it, it is not a corner and the two strokes are
    one. This is the one place where a decision of the fragment changes the
    recovered glyph rather than only describing it.
    """
    vertices = list(vertices)
    edges = [tuple(sorted(e)) for e in edges]
    dissolved = 0
    while True:
        touching = {}
        for a, b in edges:
            touching.setdefault(a, []).append(b)
            touching.setdefault(b, []).append(a)
        victim = None
        for index, neighbours in touching.items():
            if len(neighbours) != 2 or neighbours[0] == neighbours[1]:
                continue
            a, b = neighbours
            names = {"__a": vertices[a], "__m": vertices[index], "__b": vertices[b]}
            if rdsl.atom_holds("coll", ("__a", "__m", "__b"), names):
                victim = (index, a, b)
                break
        if victim is None:
            break
        index, a, b = victim
        edges = [e for e in edges if index not in e]
        edges.append(tuple(sorted((a, b))))
        dissolved += 1
        keep = sorted({v for e in edges for v in e})
        remap = {old: new for new, old in enumerate(keep)}
        vertices = [vertices[old] for old in keep]
        edges = sorted({tuple(sorted((remap[a], remap[b]))) for a, b in edges})
    return vertices, sorted(set(edges)), dissolved


def _centroid(cells):
    total = len(cells)
    return (Fraction(sum(c[0] for c in cells), total)+Fraction(1, 2),
            Fraction(sum(c[1] for c in cells), total)+Fraction(1, 2))


def _transversality(line_a, line_b):
    """How far from parallel two lines are; used only to pick the better pair."""
    (ax, ay), (bx, by) = line_a
    (cx, cy), (dx, dy) = line_b
    u = (bx-ax, by-ay)
    v = (dx-cx, dy-cy)
    cross = u[0]*v[1]-u[1]*v[0]
    scale = (u[0]*u[0]+u[1]*u[1])*(v[0]*v[0]+v[1]*v[1])
    return abs(cross)*abs(cross)/scale if scale else Fraction(0)


def _points_away(line, end):
    """Whether the line's own direction leads out of the stroke at this end."""
    (ax, ay), (bx, by) = line
    return (bx-ax)*(end[0]-ax)+(by-ay)*(end[1]-ay) >= 0


def _snap(point, x0, y0, y1, grid):
    """Normalise by the ink's box, then round onto the lattice. The last estimate."""
    span = y1-y0
    scale = HEIGHT/span if span else Fraction(1)
    x = (point[0]-x0)*scale
    y = (point[1]-y0)*scale
    return (Fraction(round(x*grid), grid), Fraction(round(y*grid), grid))


# ---------------------------------------------------------------------------
# A glyph from a definition, by the fragment's own arrangement
# ---------------------------------------------------------------------------

def arrangement(polylines, *, grid=1):
    """The planar arrangement of a letter's strokes: corners, crossings, touches.

    Where two strokes cross, the crossing is a corner of the drawing, and it is
    produced here by `intersection_ll` and kept when `on_closed_segment` says it
    lies on both. That is the same construction the reader performs on an image,
    run on the definition instead, so that the reference a letter is matched
    against is built the way the reading is.
    """
    segments = [(tuple(Fraction(v) for v in a), tuple(Fraction(v) for v in b))
                for a, b in raster.polyline_segments(polylines)]
    cuts = {index: set() for index in range(len(segments))}
    for i, (a, b) in enumerate(segments):
        cuts[i].update({a, b})
        for j, (c, d) in enumerate(segments):
            if i == j:
                continue
            meeting, _ = _meet((a, b), (c, d))
            if meeting is None:
                continue
            if ink.on_closed_segment(meeting, a, b) and ink.on_closed_segment(meeting, c, d):
                cuts[i].add(meeting)
    vertices, keys, strokes = [], {}, []

    def site(point):
        snapped = (Fraction(round(point[0]*grid), grid), Fraction(round(point[1]*grid), grid))
        if snapped not in keys:
            keys[snapped] = len(vertices)
            vertices.append(snapped)
        return keys[snapped]

    for index, (a, b) in enumerate(segments):
        along = sorted(cuts[index], key=lambda p: ((p[0]-a[0])**2+(p[1]-a[1])**2))
        indices = [site(p) for p in along]
        for one, two in zip(indices, indices[1:]):
            if one != two:
                strokes.append((one, two))
    filled = raster.render(segments, Fraction(1, 4), 64, 64)
    holes = _holes_of_definition(segments)
    return Glyph(vertices, sorted(set(strokes)), holes,
                 {"source": "definition", "rendered_cells": filled.count()})


def _holes_of_definition(segments, *, cells_per_unit=8):
    """How many regions the strokes enclose, counted on a fine grid of the box."""
    xs = [v for a, b in segments for v in (a[0], b[0])]
    ys = [v for a, b in segments for v in (a[1], b[1])]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    width = int((x1-x0)*cells_per_unit)+1
    height = int((y1-y0)*cells_per_unit)+1
    moved = [((a[0]-x0)*cells_per_unit, (a[1]-y0)*cells_per_unit,
              (b[0]-x0)*cells_per_unit, (b[1]-y0)*cells_per_unit) for a, b in segments]
    picture = raster.render([((ax, ay), (bx, by)) for ax, ay, bx, by in moved],
                            Fraction(3, 4), width+2, height+2)
    return raster.holes(picture.black, picture.width, picture.height)


# ---------------------------------------------------------------------------
# The description: relations of the fragment, decided exactly
# ---------------------------------------------------------------------------

def _vertex_descriptors(glyph, *, frame=True):
    """What a corner is, said without coordinates: its degree and where it stands."""
    coordinates = glyph.coordinates()
    degrees = glyph.degrees()
    out = []
    for index in range(len(glyph.vertices)):
        name = f"v{index}"
        standing = tuple(label for label, p, q in LINES
                         if rdsl.atom_holds("coll", (p, q, name), coordinates)) if frame else ()
        out.append((degrees[index], standing))
    return out


def _edge_descriptors(glyph, vertex_descriptors, *, frame=True):
    """What a stroke is: its direction against the frame, and the corners it joins."""
    coordinates = glyph.coordinates()
    out = []
    for a, b in glyph.edges:
        first, second = f"v{a}", f"v{b}"
        heading = tuple(label for label, p, q in DIRECTIONS
                        if rdsl.atom_holds("para", (p, q, first, second),
                                           coordinates)) if frame else ()
        ends = tuple(sorted((vertex_descriptors[a], vertex_descriptors[b])))
        out.append((heading, ends))
    return out


def relations(glyph, *, frame=True):
    """The multiset of relations that hold, each stated about descriptors not names.

    Nothing in here is a coordinate. Two glyphs of different size, position or
    proportion can produce the same multiset, and that is what makes the
    description a description of the letter rather than of the drawing.

    `frame=False` drops every relation that mentions the normalising box, which
    leaves a description built only from relations among the glyph's own
    strokes. Those are invariant under every similarity, rotations included, so
    without the frame no such description can tell a letter from a turned copy
    of itself -- N from Z, M from W. That is a theorem about the predicate set
    rather than a defect of this code, and the ablation measures what it costs.
    """
    coordinates = glyph.coordinates()
    vdesc = _vertex_descriptors(glyph, frame=frame)
    edesc = _edge_descriptors(glyph, vdesc, frame=frame)
    facts = Counter()
    for descriptor in vdesc:
        facts[("corner", descriptor)] += 1
    for descriptor in edesc:
        facts[("stroke", descriptor)] += 1
    for i in range(len(glyph.edges)):
        for j in range(i+1, len(glyph.edges)):
            a, b = glyph.edges[i]
            c, d = glyph.edges[j]
            names = (f"v{a}", f"v{b}", f"v{c}", f"v{d}")
            pair = tuple(sorted((edesc[i], edesc[j])))
            for predicate in ("para", "perp", "cong"):
                if rdsl.atom_holds(predicate, names, coordinates):
                    facts[(predicate, pair)] += 1
    for i in range(len(glyph.vertices)):
        for j in range(i+1, len(glyph.vertices)):
            for k in range(j+1, len(glyph.vertices)):
                names = (f"v{i}", f"v{j}", f"v{k}")
                if rdsl.atom_holds("coll", names, coordinates):
                    facts[("coll", tuple(sorted((vdesc[i], vdesc[j], vdesc[k]))))] += 1
    return facts


def structure(glyph):
    """The part that is counted rather than decided: holes, corners, strokes, degrees."""
    return Counter({("holes", glyph.holes): 1,
                    ("corners", len(glyph.vertices)): 1,
                    ("strokes", len(glyph.edges)): 1,
                    ("degrees", tuple(sorted(glyph.degrees()))): 1})


def description(glyph, *, use_relations=True, use_structure=True, frame=True):
    """Everything the reader compares, with either half able to be switched off."""
    total = Counter()
    if use_relations:
        total.update(relations(glyph, frame=frame))
    if use_structure:
        total.update(structure(glyph))
    return total


def agreement(left, right):
    """How much of two multisets is shared: intersection over union, exactly."""
    shared = sum((left & right).values())
    total = sum((left | right).values())
    return Fraction(shared, total) if total else Fraction(0)


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def read(bitmap, library, *, grid=1, use_relations=True, use_structure=True, frame=True):
    """Name the letter in an image, by the description that agrees with it best.

    `library` maps a letter to the description of its definition. The answer
    comes with the runner-up and the gap between them, because a reader that
    cannot say how sure it is has not said enough.
    """
    glyph = recover(bitmap, grid=grid)
    mine = description(glyph, use_relations=use_relations, use_structure=use_structure,
                       frame=frame)
    scored = sorted(((agreement(mine, other), letter) for letter, other in library.items()),
                    key=lambda pair: (-pair[0], pair[1]))
    best, runner = scored[0], (scored[1] if len(scored) > 1 else (Fraction(0), None))
    return {"letter": best[1], "score": best[0], "runner_up": runner[1],
            "runner_up_score": runner[0], "margin": best[0]-runner[0],
            "glyph": glyph, "ranking": [(letter, str(value)) for value, letter in scored[:5]]}


def library_from(definitions, *, grid=1, use_relations=True, use_structure=True, frame=True):
    """A description for each letter, built from its definition and nothing else."""
    return {letter: description(arrangement(strokes, grid=grid), use_relations=use_relations,
                                use_structure=use_structure, frame=frame)
            for letter, strokes in definitions.items()}
