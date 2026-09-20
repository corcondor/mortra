"""The sign kernel, the letters built from three points, and the fragment in space.

Ordering is what the letters, the figures, the shadows and the solids all need
and the equality fragment does not have. This run is the kernel that supplies
it, and the three things that immediately sit on it.

    python scripts/run_sign_and_space.py --output reports/sign-and-space
"""
from __future__ import annotations

import argparse
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

from math_os_prototype import geometry_alphabet as alphabet
from math_os_prototype import geometry_letter_construction as construction
from math_os_prototype import geometry_raster as raster
from math_os_prototype import geometry_reading as reading
from math_os_prototype import geometry_sign as sign
from math_os_prototype import geometry_space as space


def say(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


# ---------------------------------------------------------------------------
# The kernel
# ---------------------------------------------------------------------------

def the_kernel():
    """How many squares each of a spread of values needs, and what that means."""
    rows = []
    for value in (F(0), F(1), F(2), F(3), F(4), F(5), F(6), F(7), F(1, 2), F(2, 3),
                  F(7, 9), F(23, 5), F(169, 4), F(1000003)):
        report = sign.certify_nonnegative(value)
        rows.append({"value": str(value), "squares": report["how_many"],
                     "identity": report["identity"], "certified": report["certified"],
                     "least_dimension_holding_sqrt": report["how_many"],
                     "two_square_criterion_agrees":
                         sign.two_squares_criterion(value) == (report["how_many"] <= 2)})
    negative = sign.certify_nonnegative(F(-3))
    refused = None
    try:
        sign.sign(sp.sqrt(3))
    except ValueError as trouble:
        refused = str(trouble)
    return {"theorem": "a rational a is non-negative exactly when it is a sum of four rational "
                       "squares -- Lagrange applied to pq after writing a = pq/q^2, which is to "
                       "say the Pythagoras number of QQ is 4, and 4 is sharp because 7 is a sum "
                       "of four and not of three",
            "the_count_is_a_dimension": "the least number of squares is the least d for which "
                                        "sqrt(a) is a distance between two points of QQ^d: one "
                                        "is a rational number, two a rational plane distance, "
                                        "three a rational space distance and not a plane one "
                                        "(sqrt 3, the cube's diagonal), four no distance "
                                        "between rational points of space at all",
            "values": rows,
            "a_negative_value": {"holds": negative["holds"], "certified": negative["certified"]},
            "outside_QQ_it_is_refused": refused,
            "why_it_is_refused": "in QQ(sqrt 3) a sum of squares must be positive under both "
                                 "real embeddings, and 4 sqrt(3) is not, so a true ordering "
                                 "fact there has no certificate of this kind at all"}


def the_relations():
    """The order relations the repository actually uses, each with its witnesses."""
    disk = []
    for point, centre, through, label in (
            ((F(1), F(0)), (F(0), F(0)), (F(2), F(0)), "inside, ratio 3"),
            ((F(3), F(4)), (F(0), F(0)), (F(5), F(0)), "on the circle"),
            ((F(1), F(1)), (F(0), F(0)), (F(2), F(0)), "inside, ratio 1"),
            ((F(9), F(0)), (F(0), F(0)), (F(2), F(0)), "outside")):
        report = sign.witness_in_closed_disk(point, centre, through)
        disk.append({"case": label, "holds": report["holds"],
                     "certified": report.get("certified"),
                     "field": report.get("witness_field"),
                     "U": report.get("U"), "V": report.get("V"),
                     "atoms": report.get("atoms")})
    stroke = sign.certify_within_of_segment((F(5, 2), F(1, 2)), (F(0), F(0)), (F(10), F(0)), F(1))
    missed = sign.certify_within_of_segment((F(5, 2), F(5)), (F(0), F(0)), (F(10), F(0)), F(1))
    shadow = sign.certify_occluded((F(5), F(0)), (F(0), F(0)), (F(2), F(-1)), (F(2), F(1)))
    lit = sign.certify_occluded((F(5), F(5)), (F(0), F(0)), (F(2), F(-1)), (F(2), F(1)))
    return {"soundness_of_the_existential": sign.witness_implies_membership(),
            "in_the_closed_disk": disk,
            "an_inked_cell": {"near": {"holds": stroke["holds"], "certified": stroke["certified"],
                                       "Q": stroke["Q"], "how": stroke["how_Q_was_found"]},
                              "far": {"holds": missed["holds"], "Q": missed["Q"]},
                              "relation": stroke["relation"]},
            "the_foot_is_nearest": sign.certify_the_foot_is_nearest(),
            "in_shadow": {"occluded": {"holds": shadow["holds"], "P": shadow.get("P")},
                          "lit": {"holds": lit["holds"], "P": lit.get("P")},
                          "relation": shadow["relation"]}}


def the_universal_layer():
    """Non-negative for every configuration, certified by squares and not by samples."""
    a, b, c, d, e, f = sp.symbols("a b c d e f", real=True)
    cases = [("Cauchy-Schwarz in the plane", (a**2+b**2)*(c**2+d**2)-(a*c+b*d)**2, [a, b, c, d]),
             ("Lagrange's identity in space",
              (a**2+b**2+c**2)*(d**2+e**2+f**2)-(a*d+b*e+c*f)**2, [a, b, c, d, e, f]),
             ("|PQ|^2 + |QR|^2 >= |PR|^2 / 2",
              (a**2+b**2)+(c**2+d**2)-((a+c)**2+(b+d)**2)/2, [a, b, c, d]),
             ("a^2 + b^2 >= ab", a**2+b**2-a*b, [a, b])]
    out = []
    for name, expression, variables in cases:
        started = time.perf_counter()
        report = sign.sum_of_squares(expression, variables)
        out.append({"statement": name, "certified": report.get("certified", False),
                    "identity": report.get("identity") or report.get("why"),
                    "seconds": round(time.perf_counter()-started, 2)})
    return {"cases": out,
            "means": "a sum of squares with non-negative weights is non-negative wherever it is "
                     "evaluated, so these hold at every configuration and not merely at the "
                     "ones tried. Finding the decomposition is a search; checking it is one "
                     "expansion and one equality"}


# ---------------------------------------------------------------------------
# The letters, from three points
# ---------------------------------------------------------------------------

def the_letters():
    started = time.perf_counter()
    roman = construction.constructed(alphabet.ROMAN)
    narrow = construction.constructed(alphabet.NARROW)
    return {"seeds": roman["seeds"],
            "steps": roman["steps"], "points_built": roman["points"],
            "every_roman_coordinate_is_constructed": roman["agrees_with_the_table"],
            "every_narrow_coordinate_is_constructed": narrow["agrees_with_the_table"],
            "A_by_name": roman["letters_by_name"]["A"],
            "first_steps": roman["program"][:6],
            "from_two_points": construction.stays_on_the_line(rounds=2, limit=400),
            "seconds": round(time.perf_counter()-started, 1),
            "means": "every corner of every letter is the output of `mirror` or `midpoint` "
                     "applied to o, ex and ey, and the program that makes them replays from "
                     "those three alone"}


# ---------------------------------------------------------------------------
# Space
# ---------------------------------------------------------------------------

def the_solids(output):
    rows = []
    for name in ("tetrahedron", "cube", "octahedron", "icosahedron"):
        vertices, faces = space.SOLIDS[name]()
        rational = space.is_rational(vertices)
        regular = space.certify_regular(vertices)
        row = {"solid": name, "vertices": len(vertices), "rational": rational,
               "field": "QQ" if rational else "QQ(sqrt(5))",
               "edges": regular["edges"], "every_edge_congruent": regular["all_congruent"],
               "edge_squared_length": regular["edge_squared_length"]}
        if faces:
            convex = space.certify_convex(vertices, faces)
            row["convex"] = convex["convex"]
            row["faces"] = len(convex["faces"])
            row["a_face_certificate"] = convex["faces"][0]["a_certificate"]
        rows.append(row)
    eye = (10, 3, 1)
    vertices, faces = space.cube()
    seen = space.visible_faces(vertices, faces, eye)
    inside = space.inside_tetrahedron((F(1, 4), F(1, 4), F(1, 4)),
                                      (0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1))
    outside = space.inside_tetrahedron((F(2), F(2), F(2)),
                                       (0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1))
    return {"solids": rows,
            "why_two_of_them_leave_QQ": space.no_rotation_of_order_five(),
            "the_pentagon_says_the_same": space.the_pentagon_argument(),
            "the_triangle_the_plane_cannot_have": space.the_rational_equilateral_triangle(),
            "from_three_points": space.escapes_the_plane(
                [(0, 0, 0), (1, 0, 0), (0, 1, 0)], rounds=2, limit=300),
            "which_faces_an_eye_sees": {"eye": seen["eye"], "visible": seen["visible"],
                                        "of": seen["of"], "relation": seen["relation"]},
            "inside_a_tetrahedron": {"a_point_inside": inside["holds"],
                                     "certified": inside["certified"],
                                     "a_point_outside": outside["holds"],
                                     "relation": inside["relation"]}}


# ---------------------------------------------------------------------------
# What it costs
# ---------------------------------------------------------------------------

def _time(call, repeats):
    started = time.perf_counter()
    for _ in range(repeats):
        call()
    return (time.perf_counter()-started)/repeats


def the_cost():
    """The decision against the certificate, and the reading pipeline end to end."""
    value = F(1234, 567)
    decision = _time(lambda: sign.sign(value), 2000)
    certificate = _time(lambda: sign.certify_nonnegative(value), 200)
    disk = _time(lambda: sign.witness_in_closed_disk((F(1), F(1)), (F(0), F(0)), (F(3), F(0))), 20)
    inked = _time(lambda: sign.certify_within_of_segment((F(5, 2), F(1, 2)), (F(0), F(0)),
                                                         (F(10), F(0)), F(1)), 20)
    rows = []
    shelf = alphabet.library()
    for height, radius in ((36, F(1)), (72, F(5, 2)), (144, F(5))):
        # draw first, and keep the images: subtracting one timed drawing pass
        # from another would measure the difference between two passes
        started = time.perf_counter()
        drawn = {letter: alphabet.draw(strokes, height=height, radius=radius)
                 for letter, strokes in alphabet.ROMAN.items()}
        drawing = time.perf_counter()-started
        cells = sum(bitmap.count() for bitmap in drawn.values())
        started = time.perf_counter()
        right = sum(reading.read(bitmap, shelf)["letter"] == letter
                    for letter, bitmap in drawn.items())
        whole = time.perf_counter()-started
        rows.append({"glyph_height_px": height, "stroke_radius_px": str(radius),
                     "inked_cells_for_the_alphabet": cells,
                     "drawing_seconds_for_26": round(drawing, 2),
                     "reading_seconds_for_26": round(whole, 2),
                     "seconds_per_letter": round(whole/26, 3),
                     "cells_read_per_second": round(cells/whole) if whole else None,
                     "read_correctly": f"{right}/26"})
    magnitudes = []
    for exponent in range(2, 11):
        value = F(10**exponent+3)
        started = time.perf_counter()
        report = sign.certify_nonnegative(value, limit=10**12)
        magnitudes.append({"value": f"10^{exponent}+3", "squares": report.get("how_many"),
                           "seconds": round(time.perf_counter()-started, 4)})
    return {"one_decision_seconds": round(decision, 9),
            "the_search_is_order_root_n": magnitudes,
            "what_that_means": "finding the squares costs about the square root of the numerator "
                               "times the denominator, so the kernel refuses past a stated limit "
                               "rather than grinding. The sign is decided either way; only the "
                               "witness is withheld",
            "one_certificate_seconds": round(certificate, 6),
            "certificate_over_decision": round(certificate/decision) if decision else None,
            "one_disk_witness_seconds": round(disk, 4),
            "one_inked_cell_certificate_seconds": round(inked, 4),
            "why_the_loops_use_the_decision": "a certificate for every cell of a 72px alphabet "
                                              "would be four orders of magnitude more work than "
                                              "drawing it. The certificate is what the claim "
                                              "rests on; the comparison is what the loop runs",
            "reading": rows}


# ---------------------------------------------------------------------------
# A picture of the solids
# ---------------------------------------------------------------------------

def draw_solids(output):
    """An orthographic view of each solid, drawn as strokes on the raster grid."""
    pictures = []
    for name in ("tetrahedron", "cube", "octahedron", "icosahedron"):
        vertices, faces = space.SOLIDS[name]()
        points = [(sp.nsimplify(v[0])+sp.Rational(1, 3)*sp.nsimplify(v[2]),
                   sp.nsimplify(v[1])+sp.Rational(1, 5)*sp.nsimplify(v[2])) for v in vertices]
        lengths = {}
        for i in range(len(vertices)):
            for j in range(i+1, len(vertices)):
                lengths[(i, j)] = sp.nsimplify(space.squared_distance(
                    space.point(vertices[i]), space.point(vertices[j])))
        shortest = min(lengths.values(), key=lambda v: float(v))
        edges = [pair for pair, value in lengths.items() if value == shortest]
        scaled = [(F(str(sp.nsimplify(sp.Rational(round(float(x)*24), 1)))),
                   F(str(sp.nsimplify(sp.Rational(round(float(y)*24), 1))))) for x, y in points]
        low_x = min(p[0] for p in scaled)
        low_y = min(p[1] for p in scaled)
        placed = [(p[0]-low_x+6, p[1]-low_y+6) for p in scaled]
        segments = [(placed[i], placed[j]) for i, j in edges]
        width = int(max(p[0] for p in placed))+8
        height = int(max(p[1] for p in placed))+8
        bitmap = raster.render(segments, F(1), width, height)
        raster.write_png(output/f"solid-{name}.png", bitmap, cell=2)
        pictures.append({"file": f"solid-{name}.png", "edges_drawn": len(edges),
                         "exact": space.is_rational(vertices),
                         "note": "drawn from exact vertices" if space.is_rational(vertices)
                         else "the vertices lie in QQ(sqrt 5); the pixel positions are rounded "
                              "from them, and that rounding is the only inexact step"})
    return pictures


# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()
    output = Path(arguments.output)
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    say("the kernel")
    kernel = the_kernel()
    say("the relations that use it")
    relations = the_relations()
    say("the universal layer")
    universal = the_universal_layer()
    say("the letters, from three points")
    letters = the_letters()
    say("space")
    solids = the_solids(output)
    say("drawing the solids")
    pictures = draw_solids(output)
    say("what it costs")
    cost = the_cost()

    report = {
        "environment": {
            "sha": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                                  text=True).stdout.strip(),
            "python": sys.version.split()[0], "platform": platform.platform()},
        "the_sign_kernel": kernel,
        "the_relations": relations,
        "the_universal_layer": universal,
        "the_letters_from_three_points": letters,
        "space": solids,
        "pictures": pictures,
        "what_it_costs": cost,
        "not_claimed": [
            "the comparison is not gone. `sign` is a comparison, the search that finds the four "
            "squares is full of comparisons, and every per-pixel loop in this repository still "
            "runs the comparison. What the kernel supplies is a witness that turns the answer "
            "into an equation, and checking that witness uses no order at all",
            "Lagrange's theorem makes a certificate exist for every true instance, so the "
            "existence of one proves nothing about the instance. What it buys is that the fact "
            "can be stated in the fragment's language and checked in it",
            "the universal layer certifies non-negativity and never refutes it: a failure to "
            "find a sum of squares is a failure of the search, not a proof that the polynomial "
            "goes negative",
            "the three-dimensional fragment is new code and shares no certifier with the plane "
            "one. Its predicates are written here rather than derived from the plane's",
            "the solids are checked, not classified: this run certifies that three of them have "
            "rational vertices and that the standard coordinates of the fourth do not. The "
            "impossibility for the icosahedron and the dodecahedron is argued from the regular "
            "pentagon and is not machine-checked here",
            "the letters are built by the fragment from three points. Which twenty-six shapes "
            "to build was still a human choice"],
        "total_seconds": round(time.perf_counter()-started, 1),
    }
    (output/"result.json").write_text(json.dumps(report, indent=2, ensure_ascii=False,
                                                 default=str), encoding="utf-8")
    say(f"letters: {letters['steps']} steps from three points, agrees="
        f"{letters['every_roman_coordinate_is_constructed']}")
    say(f"space: nothing left the plane of three seeds "
        f"({solids['from_three_points']['points_built']} points built); the equilateral "
        f"triangle is rational here")
    say(f"cost: a decision {cost['one_decision_seconds']}s, a certificate "
        f"{cost['one_certificate_seconds']}s")
    say(f"wrote {output/'result.json'}")


if __name__ == "__main__":
    main()
