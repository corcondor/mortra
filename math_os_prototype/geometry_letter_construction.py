"""The letters, built by the fragment from three points, instead of typed in.

Until now the alphabet was a table of coordinates someone wrote down. That is
fine as data and poor as a claim: a fragment that draws letters ought to be able
to make the points it draws them from. So this module starts with three points
and nothing else --

    o = (0,0),  ex = (1,0),  ey = (0,1)

-- and produces every corner of every letter as the output of a primitive, by a
program that is recorded step by step and can be replayed from the three seeds
alone. Nothing is rounded and nothing is assumed: each step goes through
`execute_primitive`, so each one passes the same applicability checks any other
construction in this repository does.

Two moves are enough.

**Along an axis, `mirror`.** The reflection of a point in another is
`mirror(a,b) = 2b - a`, so from `o` and `ex` the whole integer ray follows:
`(2,0) = mirror(o, ex)`, `(3,0) = mirror(ex, (2,0))`, and so on. The same on the
other axis from `ey`.

**Off the axes, `midpoint` then `mirror`.** The point `(m,n)` is the sum of
`(m,0)` and `(0,n)`, and a sum is a reflection of the origin in a midpoint:
`mirror(o, midpoint((m,0), (0,n)))`. Two primitives, no arithmetic.

Why three seeds and not two: the plane fragment's primitives all commute with a
reflection, so from two points nothing ever leaves the line through them --
`stays_on_the_line` checks it. That is the same obstruction `geometry_space`
meets one dimension up, where three points never leave their plane.
"""
from __future__ import annotations

from fractions import Fraction

from math_os_prototype import geometry_relational_dsl as rdsl

SEEDS = {"o": (Fraction(0), Fraction(0)),
         "ex": (Fraction(1), Fraction(0)),
         "ey": (Fraction(0), Fraction(1))}


def _step(program, coordinates, name, family, arguments):
    value, reason = rdsl.execute_primitive(family, list(arguments), coordinates)
    if value is None:
        raise RuntimeError(f"{family}{tuple(arguments)} was refused: {reason}")
    coordinates[name] = tuple(Fraction(str(v)) for v in value)
    program.append({"let": name, "op": family, "args": list(arguments)})
    return name


def build_lattice(width, height):
    """Every integer point of the box, as the output of a primitive. Nothing typed.

    Returns the map from a lattice index to the name of the point that holds it,
    the program that builds them, and the coordinates the program produced.
    """
    coordinates = dict(SEEDS)
    program = []
    names = {(0, 0): "o", (1, 0): "ex", (0, 1): "ey"}
    for k in range(2, width+1):
        names[(k, 0)] = _step(program, coordinates, f"x{k}", "mirror",
                              [names[(k-2, 0)], names[(k-1, 0)]])
    for k in range(2, height+1):
        names[(0, k)] = _step(program, coordinates, f"y{k}", "mirror",
                              [names[(0, k-2)], names[(0, k-1)]])
    for m in range(1, width+1):
        for n in range(1, height+1):
            centre = _step(program, coordinates, f"c{m}_{n}", "midpoint",
                           [names[(m, 0)], names[(0, n)]])
            names[(m, n)] = _step(program, coordinates, f"p{m}_{n}", "mirror",
                                  ["o", centre])
    return names, program, coordinates


def replay(program, seeds=None):
    """Run the program from the seeds alone, and return what it produced."""
    coordinates = dict(seeds or SEEDS)
    for step in program:
        value, reason = rdsl.execute_primitive(step["op"], list(step["args"]), coordinates)
        if value is None:
            raise RuntimeError(f"{step['op']} was refused on replay: {reason}")
        coordinates[step["let"]] = tuple(Fraction(str(v)) for v in value)
    return coordinates


def stays_on_the_line(*, rounds=3, limit=600):
    """From two points, does anything ever leave their line? It does not.

    Every primitive of the fragment commutes with the reflection in the line
    through the two given points, and that reflection fixes both, so it fixes
    whatever is built. This is the check that the seed set has to be three.
    """
    coordinates = {"a": (Fraction(0), Fraction(0)), "b": (Fraction(1), Fraction(0))}
    tried = 0
    for _ in range(rounds):
        fresh = {}
        keys = list(coordinates)
        for family, contract in sorted(rdsl.primitive_contracts().items()):
            arity = len(contract["params"])
            from itertools import product
            for choice in product(keys, repeat=arity):
                if tried >= limit:
                    break
                tried += 1
                value, _ = execute = rdsl.execute_primitive(family, list(choice), coordinates)
                if value is None:
                    continue
                point = tuple(Fraction(str(v)) for v in value)
                if point not in set(coordinates.values()) and point not in set(fresh.values()):
                    fresh[f"n{len(coordinates)+len(fresh)}"] = point
        coordinates.update(fresh)
    off = [name for name, (x, y) in coordinates.items() if y != 0]
    return {"left_the_line": bool(off), "points_built": len(coordinates),
            "constructions_tried": tried, "off_the_line": off,
            "why": "the reflection in the line fixes both given points and commutes with every "
                   "primitive, so it fixes everything built from them"}


# ---------------------------------------------------------------------------
# The letters, over constructed names
# ---------------------------------------------------------------------------

def as_names(letters, names):
    """A letter table of coordinates rewritten as a table of constructed names."""
    out = {}
    for letter, strokes in letters.items():
        out[letter] = [[names[(int(p[0]), int(p[1]))] for p in chain] for chain in strokes]
    return out


def as_coordinates(named, coordinates):
    """And back again: the coordinates the program produced, for the drawing side."""
    return {letter: [[list(coordinates[name]) for name in chain] for chain in strokes]
            for letter, strokes in named.items()}


def constructed(letters, *, width=6, height=6):
    """The whole round trip: build the lattice, name the letters, replay, compare.

    The comparison is the point. The letters that come back are the letters that
    went in, and every coordinate in them is now the output of `mirror` or
    `midpoint` applied to the three seeds, with a program that produced it.
    """
    names, program, built = build_lattice(width, height)
    named = as_names(letters, names)
    produced = replay(program)
    rebuilt = as_coordinates(named, produced)
    same = all(
        [[list(map(Fraction, p)) for p in chain] for chain in letters[letter]] ==
        [[list(map(Fraction, p)) for p in chain] for chain in rebuilt[letter]]
        for letter in letters)
    return {"names": names, "program": program, "coordinates": produced,
            "letters_by_name": named, "letters": rebuilt, "agrees_with_the_table": same,
            "steps": len(program), "seeds": {k: [str(v) for v in xy] for k, xy in SEEDS.items()},
            "points": len(produced)}
