"""Two masters of a glyph, what survives between them, and the motion lerp cannot make.

The thread this answers says three things a type engineer runs into, and each of
them is a statement about this fragment:

    "linear interpolation is all there is"        -> lerp is `midpoint` with a
                                                     parameter, and that is the
                                                     whole motion
    "de Casteljau is repeated lerp"               -> which is why the search in
                                                     reports/drawing-round
                                                     returned the subdivision
                                                     rule from seven points
    "a point cannot be moved along an arc"        -> no rotation is rational, so
                                                     no composition of the seven
                                                     primitives is one either

What this run adds is the part a sampler cannot give: whether a relation the
designer depends on survives *every* interpolation, decided over QQ[t] rather
than checked at a few sliders.

    python scripts/run_glyph_interpolation.py --output reports/glyph
"""
from __future__ import annotations

import argparse
from collections import Counter
from fractions import Fraction as F
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import sympy as sp

from math_os_prototype import geometry_drawing_program as dp
from math_os_prototype import geometry_glyph as glyph
from math_os_prototype import geometry_ink as ink
from math_os_prototype import geometry_quadratic as qf


def say(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


# ---------------------------------------------------------------------------
# Two masters of one glyph
# ---------------------------------------------------------------------------

def masters():
    """A stem with a bowl, light and bold, the same points in the same order.

    The names are the outline's, and both masters carry them: that sameness of
    topology is what makes interpolation possible at all, and it is assumed here
    rather than checked, because it is a property of how the masters were drawn.
    """
    light = {
        "a": (F(1), F(0)), "b": (F(2), F(0)),          # stem foot, outer then inner
        "c": (F(2), F(6)), "d": (F(1), F(6)),          # stem head
        "e": (F(5), F(3)), "f": (F(4), F(3)),          # bowl extreme, outer then inner
        "g": (F(2), F(6)), "h": (F(2), F(0)),          # where the bowl meets the stem
        "k": (F(5), F(6)), "m": (F(5), F(0)),          # the bowl's off-curve handles
        # three points a designer keeps in line, and two lengths kept equal --
        # in both masters. What happens between them is the question.
        "u": (F(7), F(0)), "v": (F(8), F(0)), "w": (F(10), F(0)),
        "x": (F(10), F(3)), "y": (F(9), F(3)),
    }
    bold = {
        "a": (F(1), F(0)), "b": (F(3), F(0)),
        "c": (F(3), F(6)), "d": (F(1), F(6)),
        "e": (F(6), F(3)), "f": (F(4), F(3)),
        "g": (F(3), F(6)), "h": (F(3), F(0)),
        "k": (F(6), F(6)), "m": (F(6), F(0)),
        "u": (F(7), F(0)), "v": (F(7), F(1)), "w": (F(7), F(2)),
        "x": (F(10), F(7)), "y": (F(11), F(7)),
    }
    return light, bold


def relations_a_designer_depends_on():
    """Named because a designer would name them, not because they are true."""
    return [
        ("coll", ("a", "d", "b")),        # a relation a designer might assume and be wrong about
        ("coll", ("b", "c", "h")),        # is the inner stem edge straight?
        ("para", ("a", "d", "b", "c")),   # do the two stem edges stay parallel?
        ("perp", ("a", "b", "a", "d")),   # does the foot stay square to the stem?
        ("cong", ("a", "b", "d", "c")),   # does the stem keep one width top and bottom?
        ("cong", ("a", "d", "b", "c")),   # do the two edges keep the same height?
        ("coll", ("g", "k", "c")),        # does the bowl's handle stay in line with the head?
        ("cong", ("g", "k", "h", "m")),   # do the two handles stay the same length?
        ("coll", ("u", "v", "w")),        # three points in line in BOTH masters
        ("cong", ("u", "v", "x", "y")),   # two lengths equal in BOTH masters
    ]


# ---------------------------------------------------------------------------
# Drawing an outline: de Casteljau, which is the program the search returned
# ---------------------------------------------------------------------------

SUBDIVISION = {
    "name": "r", "params": ["p0", "p1", "p2"],
    "body": [{"let": "v1", "op": "midpoint", "args": ["p0", "p1"]},
             {"let": "v2", "op": "midpoint", "args": ["p1", "p2"]},
             {"let": "v3", "op": "midpoint", "args": ["v1", "v2"]}],
    "emit": ["v3"],
    "calls": [{"rule": "r", "args": ["p0", "v1", "v3"]},
              {"rule": "r", "args": ["p2", "v2", "v3"]}]}


def outline(points, segments, depth):
    """The glyph as emitted points: straight runs by halving, curved runs by subdivision."""
    drawn = []
    for segment in segments:
        if len(segment) == 2:
            first, last = (points[name] for name in segment)
            drawn.extend(glyph.straight_motion(first, last, 2**depth))
        else:
            inputs = dict(zip(("p0", "p1", "p2"), (points[name] for name in segment),
                              strict=True))
            emitted, _ = dp.run(SUBDIVISION, inputs, depth)
            drawn.extend([points[segment[0]]]+[tuple(p) for p in emitted]+[points[segment[2]]])
    return drawn


SEGMENTS = [("a", "b"), ("b", "m", "e"), ("e", "k", "c"), ("c", "d"), ("d", "a")]


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------

PAPER = (F(-1), F(-2), F(36), F(8))
RADIUS = F(1, 24)


def draw(name, runs, output, *, pixels_per_unit=60):
    """Several outlines side by side, each shifted, all in the one convention."""
    marks = []
    for index, points in enumerate(runs):
        shift = F(7*index)
        for number, value in enumerate(points):
            x, y = qf.point(value)
            marks.append(((index, number), (x+shift, y)))
    svg = ink.write_svg(output/f"{name}.svg", marks, RADIUS, PAPER,
                        pixels_per_unit=pixels_per_unit)
    png = ink.write_png(output/f"{name}.png", marks, RADIUS, PAPER,
                        pixels_per_unit=pixels_per_unit)
    return {"image": name, "dots": len(marks), "outlines": len(runs),
            "svg": svg["path"], "png": png["path"],
            "svg_check": ink.check_svg_is_one_radius_black_circles(output/f"{name}.svg")}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--depth", type=int, default=4)
    arguments = parser.parse_args()
    output = Path(arguments.output)
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    light, bold = masters()
    report = {"environment": {
        "sha": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True).stdout.strip(),
        "python": sys.version.split()[0], "platform": platform.platform()},
        "what_this_is": {
            "source": "a thread about variable fonts: linear interpolation is all there is, de "
                      "Casteljau is repeated lerp, and a point cannot be moved along an arc",
            "read_by": "a person, from the text pasted into the conversation. Nothing here "
                       "browsed anything, and no font file was read",
            "masters": "written by the development agent as two point sets with the same names, "
                       "not taken from a real typeface"},
        "lerp_is_this_fragment": {
            "claim": "lerp(a, b, t) = a + t(b-a), and at t = 1/2 it is the fragment's midpoint",
            "dyadic_only": "what the fragment constructs exactly is t = k/2**n, by halving. "
                           "t = 1/3 is not reachable by its primitives"}}

    # -- 1. interpolation is halving -----------------------------------------
    say("interpolation, as the fragment writes it")
    halving = glyph.dyadic_lerp_program(3)
    emitted, _ = dp.run(halving, {"p0": light["a"], "p1": bold["b"]}, 1)
    report["interpolation_as_a_program"] = {
        "program": {k: halving[k] for k in ("name", "params", "body", "emit")},
        "t": str(halving["t"]),
        "from": [str(v) for v in light["a"]], "to": [str(v) for v in bold["b"]],
        "gives": [str(v) for v in emitted[0]],
        "same_as_lerp": [str(v) for v in glyph.lerp(light["a"], bold["b"], halving["t"])],
        "reachable_values": {"1/2": glyph.reachable_by_halving(F(1, 2)),
                             "3/8": glyph.reachable_by_halving(F(3, 8)),
                             "1/3": glyph.reachable_by_halving(F(1, 3))}}
    say(f"   t={halving['t']} by halving gives {[str(v) for v in emitted[0]]}, "
        f"lerp gives {[str(v) for v in glyph.lerp(light['a'], bold['b'], halving['t'])]}")

    # -- 2. what survives every interpolation --------------------------------
    say("deciding master compatibility over QQ[t]")
    report["compatibility"] = glyph.compatibility_report(
        relations_a_designer_depends_on(), light, bold)
    for row in report["compatibility"]["relations"]:
        mark = "preserved" if row["preserved"] else (
            "BREAKS between the masters" if all(row["holds_at_the_masters"].values())
            else "does not hold at the masters either")
        say(f"   {row['predicate']}{tuple(row['arguments'])}: {mark}")

    # -- 3. the outlines, drawn ----------------------------------------------
    say("drawing the masters and what lies between them")
    runs, values = [], [F(0), F(1, 4), F(1, 2), F(3, 4), F(1)]
    for t in values:
        points = glyph.interpolate(light, bold, t)
        runs.append(outline(points, SEGMENTS, arguments.depth))
    report["outlines"] = {"t": [str(v) for v in values],
                          "points_each": [len(r) for r in runs],
                          "image": draw("masters-and-between", runs, output)}
    say(f"   {len(runs)} outlines, {report['outlines']['points_each']} points each")

    # -- 4. the motion interpolation cannot make -----------------------------
    say("the arc a slider cannot travel")
    centre, start = (F(0), F(0)), (F(3), F(0))
    straight = glyph.straight_motion(start, (F(-3), F(0)), 6)
    turned = glyph.arc_motion(centre, start, 6)
    report["arc"] = {
        "what_a_slider_does": {"points": [[str(v) for v in p] for p in straight],
                               "all_on_one_circle_about_the_centre":
                                   glyph.on_one_circle(centre, straight)},
        "what_a_sixtieth_turn_does": {"points": [[str(v) for v in p] for p in turned],
                                      "all_on_one_circle_about_the_centre":
                                          glyph.on_one_circle(centre, turned),
                                      "field": qf.FIELD},
        "why": "under interpolation a point travels the straight segment between its two master "
               "positions, so the only way to make it travel an arc is to place masters along "
               "that arc. A turn moves it along the circle exactly, and leaves the rationals to "
               "do it"}
    say(f"   straight motion stays on the circle: "
        f"{report['arc']['what_a_slider_does']['all_on_one_circle_about_the_centre']}")
    say(f"   the turn stays on the circle:        "
        f"{report['arc']['what_a_sixtieth_turn_does']['all_on_one_circle_about_the_centre']}")
    report["arc"]["image"] = draw("straight-against-arc", [straight, turned], output)

    # -- 5. recognising the glyph by its structure ---------------------------
    say("the structure of the outline, and what it matches")
    corners = ["a", "b", "c", "d"]
    light_signature = glyph.signature(light, names=corners)
    bold_signature = glyph.signature(bold, names=corners)
    middle = glyph.interpolate(light, bold, F(1, 2))
    middle_signature = glyph.signature(middle, names=corners)
    other = dict(light, c=(F(2), F(5)))                 # a different shape, same names
    report["recognition"] = {
        "names_compared": corners,
        "light": [f"{p}{a}" for p, a in light_signature],
        "bold_matches_light": glyph.match(light_signature, bold_signature),
        "the_middle_matches_light": glyph.match(light_signature, middle_signature),
        "a_different_shape_matches_light": glyph.match(light_signature,
                                                       glyph.signature(other, names=corners)),
        "what_this_is_not": "this matches one outline against another by the relations that hold "
                            "of it. It is not classification: nothing here names a letter, reads "
                            "a font file, or sees an image"}
    say(f"   light: {len(light_signature)} relations; bold matches: "
        f"{report['recognition']['bold_matches_light']['same']}; "
        f"the middle matches: {report['recognition']['the_middle_matches_light']['same']}; "
        f"a different shape matches: "
        f"{report['recognition']['a_different_shape_matches_light']['same']}")

    report["not_claimed"] = [
        "no font file was read and no image was seen; the masters are two point sets written here",
        "recognition here is matching one outline's exact relations against another's, not "
        "naming a character",
        "the compatibility verdicts are decided over QQ[t] and are exact; the drawings are "
        "rasterised and are not",
        "the fragment constructs the dyadic interpolation values only",
        "nothing here implements the OpenType proposal the thread mentions"]
    report["total_seconds"] = time.perf_counter()-started
    (output/"result.json").write_text(json.dumps(report, indent=1, default=str)+"\n",
                                      encoding="utf-8")
    print(json.dumps({"compatibility": {k: v for k, v in report["compatibility"].items()
                                        if k != "relations"},
                      "arc": {k: report["arc"][k]["all_on_one_circle_about_the_centre"]
                              for k in ("what_a_slider_does", "what_a_sixtieth_turn_does")},
                      "recognition": {k: report["recognition"][k]["same"]
                                      for k in ("bold_matches_light", "the_middle_matches_light",
                                                "a_different_shape_matches_light")}},
                     indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
