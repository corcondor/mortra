"""A straight-stroke alphabet, and the two readers that are compared against it.

The fragment is exact over the rationals and a circular arc is not rational, so
the alphabet here is written with straight strokes only -- a stencil alphabet,
where B and S and O are polygons rather than curves. That is a restriction and it
is the honest one to take: nothing here approximates a curve and then calls the
approximation exact.

Every letter is six units tall, starts at x = 0, and is drawn as a list of
polylines on integer grid points. The definitions are the drawing side; the
reading side is `geometry_reading`, which never sees them -- it sees a bitmap.

One rule constrains the shapes, and it is a typographic one rather than a
concession to the reader: no two junctions of a letter stand closer than two
units. A feature that is not as long as the stroke is thick cannot be resolved
from ink by anything, and a stencil alphabet that asks for it is badly drawn.

Two styles are given. `ROMAN` is the one the reference descriptions are built
from. `NARROW` is the same twenty-six letters with different proportions: bars
sit at different heights, bowls are cut differently, widths differ. No reference
is ever built from `NARROW`, so it measures whether a description made of
relations transfers to a drawing it was not taken from -- which a description
made of coordinates does not.
"""
from __future__ import annotations

from fractions import Fraction

from math_os_prototype import geometry_raster as raster
from math_os_prototype import geometry_reading as reading

# ---------------------------------------------------------------------------
# The letters
# ---------------------------------------------------------------------------

ROMAN = {
    "A": [[[0, 0], [2, 6], [4, 0]], [[1, 3], [3, 3]]],
    "B": [[[0, 0], [0, 6], [3, 6], [4, 4], [3, 3], [0, 3]], [[3, 3], [4, 2], [3, 0], [0, 0]]],
    "C": [[[4, 5], [2, 6], [0, 4], [0, 2], [2, 0], [4, 1]]],
    "D": [[[0, 0], [0, 6], [2, 6], [4, 4], [4, 2], [2, 0], [0, 0]]],
    "E": [[[4, 6], [0, 6], [0, 0], [4, 0]], [[0, 3], [3, 3]]],
    "F": [[[4, 6], [0, 6], [0, 0]], [[0, 3], [3, 3]]],
    "G": [[[4, 5], [2, 6], [0, 4], [0, 2], [2, 0], [4, 1], [4, 3], [2, 3]]],
    "H": [[[0, 0], [0, 6]], [[4, 0], [4, 6]], [[0, 3], [4, 3]]],
    "I": [[[0, 6], [4, 6]], [[2, 6], [2, 0]], [[0, 0], [4, 0]]],
    "J": [[[0, 6], [4, 6]], [[3, 6], [3, 1], [1, 0], [0, 1]]],
    "K": [[[0, 0], [0, 6]], [[4, 6], [0, 3], [4, 0]]],
    "L": [[[0, 6], [0, 0], [4, 0]]],
    "M": [[[0, 0], [0, 6], [2, 3], [4, 6], [4, 0]]],
    "N": [[[0, 0], [0, 6], [4, 0], [4, 6]]],
    "O": [[[0, 2], [0, 4], [2, 6], [4, 4], [4, 2], [2, 0], [0, 2]]],
    "P": [[[0, 0], [0, 6], [3, 6], [4, 5], [3, 3], [0, 3]]],
    "Q": [[[0, 2], [0, 4], [2, 6], [4, 4], [4, 2], [2, 0], [0, 2]], [[2, 2], [4, 0]]],
    "R": [[[0, 0], [0, 6], [3, 6], [4, 5], [3, 3], [0, 3]], [[1, 3], [4, 0]]],
    "S": [[[4, 5], [2, 6], [0, 5], [2, 3], [4, 2], [2, 0], [0, 1]]],
    "T": [[[0, 6], [4, 6]], [[2, 6], [2, 0]]],
    "U": [[[0, 6], [0, 2], [2, 0], [4, 2], [4, 6]]],
    "V": [[[0, 6], [2, 0], [4, 6]]],
    "W": [[[0, 6], [1, 0], [2, 4], [3, 0], [4, 6]]],
    "X": [[[0, 0], [4, 6]], [[0, 6], [4, 0]]],
    "Y": [[[0, 6], [2, 3], [4, 6]], [[2, 3], [2, 0]]],
    "Z": [[[0, 6], [4, 6], [0, 0], [4, 0]]],
}

# the same letters, drawn differently: bars moved, bowls recut, widths changed.
# No description is ever built from these; they are only ever read.
NARROW = {
    "A": [[[0, 0], [3, 6], [6, 0]], [[1, 2], [5, 2]]],
    "B": [[[0, 0], [0, 6], [2, 6], [3, 5], [2, 4], [0, 4]], [[2, 4], [3, 2], [2, 0], [0, 0]]],
    "C": [[[3, 5], [1, 6], [0, 5], [0, 1], [1, 0], [3, 1]]],
    "D": [[[0, 0], [0, 6], [1, 6], [3, 5], [3, 1], [1, 0], [0, 0]]],
    "E": [[[3, 6], [0, 6], [0, 0], [3, 0]], [[0, 2], [2, 2]]],
    "F": [[[3, 6], [0, 6], [0, 0]], [[0, 2], [2, 2]]],
    "G": [[[3, 5], [1, 6], [0, 5], [0, 1], [1, 0], [3, 1], [3, 2], [2, 2]]],
    "H": [[[0, 0], [0, 6]], [[3, 0], [3, 6]], [[0, 2], [3, 2]]],
    "I": [[[0, 6], [3, 6]], [[1, 6], [1, 0]], [[0, 0], [3, 0]]],
    "J": [[[0, 6], [3, 6]], [[2, 6], [2, 2], [1, 0], [0, 2]]],
    "K": [[[0, 0], [0, 6]], [[3, 6], [0, 2], [3, 0]]],
    "L": [[[0, 6], [0, 0], [3, 0]]],
    "M": [[[0, 0], [0, 6], [3, 1], [6, 6], [6, 0]]],
    "N": [[[0, 0], [0, 6], [3, 0], [3, 6]]],
    "O": [[[0, 1], [0, 5], [1, 6], [3, 5], [3, 1], [1, 0], [0, 1]]],
    "P": [[[0, 0], [0, 6], [2, 6], [3, 4], [0, 4]]],
    "Q": [[[0, 1], [0, 5], [1, 6], [3, 5], [3, 2], [1, 0], [0, 1]], [[1, 2], [3, 0]]],
    "R": [[[0, 0], [0, 6], [2, 6], [3, 4], [0, 4]], [[1, 4], [3, 0]]],
    "S": [[[3, 5], [1, 6], [0, 4], [2, 3], [3, 1], [1, 0], [0, 2]]],
    "T": [[[0, 6], [6, 6]], [[3, 6], [3, 0]]],
    "U": [[[0, 6], [0, 1], [1, 0], [2, 1], [2, 6]]],
    "V": [[[0, 6], [1, 0], [2, 6]]],
    "W": [[[0, 6], [1, 0], [3, 3], [5, 0], [6, 6]]],
    "X": [[[0, 0], [2, 6]], [[0, 6], [2, 0]]],
    "Y": [[[0, 6], [3, 2], [6, 6]], [[3, 2], [3, 0]]],
    "Z": [[[0, 6], [3, 6], [0, 0], [3, 0]]],
}


# ---------------------------------------------------------------------------
# Drawing a letter
# ---------------------------------------------------------------------------

def draw(strokes, *, height=36, radius=Fraction(3, 2), margin=None, at=None, pen="round"):
    """Render a letter's definition into a bitmap, and nothing else.

    `height` is the glyph's own height in pixels; the pen has radius `radius`, so
    the ink reaches that far past the strokes and the image is padded to hold it.
    `at` places the glyph's origin explicitly, for the translation tests, and
    `pen` chooses a round nib or a square one -- the square nib mitres the
    corners and squares the ends, which is a different drawing of the same
    letter and not one the reader was built against.
    """
    radius = Fraction(radius)
    scale = Fraction(height, 6)
    margin = Fraction(margin if margin is not None else radius+2)
    xs = [p[0] for chain in strokes for p in chain]
    ys = [p[1] for chain in strokes for p in chain]
    origin = at if at is not None else (margin, margin)
    origin = (Fraction(origin[0]), Fraction(origin[1]))
    placed = [[[origin[0]+scale*(p[0]-min(xs)), origin[1]+scale*(p[1]-min(ys))] for p in chain]
              for chain in strokes]
    width = int(origin[0]+scale*(max(xs)-min(xs))+radius+margin)+1
    tall = int(origin[1]+scale*(max(ys)-min(ys))+radius+margin)+1
    nib = raster.render_square if pen == "square" else raster.render
    return nib(raster.polyline_segments(placed), radius, width, tall)


# ---------------------------------------------------------------------------
# The reader under test, and the reader it is compared against
# ---------------------------------------------------------------------------

def constructed(style="ROMAN"):
    """The same letters with every corner named by the construction that made it.

    The tables above are coordinates, which is fine as data and poor as a claim.
    `geometry_letter_construction` starts from three points -- (0,0), (1,0) and
    (0,1) -- and produces every lattice point of the box as the output of
    `mirror` or `midpoint`, in eighty-two steps that replay from those three
    alone. This returns that construction together with the letters rewritten
    over its names, and the test suite checks that replaying it reproduces the
    tables exactly.
    """
    from math_os_prototype import geometry_letter_construction

    return geometry_letter_construction.constructed(ROMAN if style == "ROMAN" else NARROW)


def library(definitions=None, **options):
    """The description of every letter, built from the definitions alone."""
    return reading.library_from(definitions or ROMAN, **options)


def read_by_relations(bitmap, shelf, **options):
    """The reader of this work: recover a glyph, describe it, take the best match."""
    return reading.read(bitmap, shelf, **options)


def coordinate_template(glyph):
    """A letter as the set of its recovered corners and strokes: coordinates, no relations.

    This is the control. It uses exactly the same recovery, the same
    normalisation and the same snap as the reader under test, and then compares
    what the reader deliberately does not compare: where the corners are.
    """
    points = {("point", str(x), str(y)) for x, y in glyph.vertices}
    strokes = {("stroke", str(glyph.vertices[a][0]), str(glyph.vertices[a][1]),
                str(glyph.vertices[b][0]), str(glyph.vertices[b][1]))
               for a, b in glyph.edges}
    return points | strokes


def template_library(definitions=None, *, grid=1):
    definitions = definitions or ROMAN
    return {letter: coordinate_template(reading.arrangement(strokes, grid=grid))
            for letter, strokes in definitions.items()}


def read_by_coordinates(bitmap, shelf, *, grid=1):
    """The control reader: nearest by corners and strokes, with no predicate decided."""
    glyph = reading.recover(bitmap, grid=grid)
    mine = coordinate_template(glyph)
    scored = []
    for letter, other in shelf.items():
        union = len(mine | other)
        scored.append((Fraction(len(mine & other), union) if union else Fraction(0), letter))
    scored.sort(key=lambda pair: (-pair[0], pair[1]))
    best = scored[0]
    runner = scored[1] if len(scored) > 1 else (Fraction(0), None)
    return {"letter": best[1], "score": best[0], "runner_up": runner[1],
            "runner_up_score": runner[0], "margin": best[0]-runner[0], "glyph": glyph}
