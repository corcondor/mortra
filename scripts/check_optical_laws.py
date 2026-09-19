"""Which laws of geometrical optics the fragment can state, and which of those it can prove.

Nothing is added to the fragment here. Each law is written as an atom over points
the seven primitives construct, and then handed to the same exact decision
procedure the library uses, `certify_entry`, which decides whether the atom's
polynomial is the zero element of the rational function field of the free
inputs — that is, whether the law holds for every configuration, not just the one
drawn.

    python scripts/check_optical_laws.py --output reports/optical-laws
"""
from __future__ import annotations

import argparse
from collections import Counter
from fractions import Fraction
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from math_os_prototype import geometry_relational_dsl as rdsl
from math_os_prototype import geometry_relational_library as lib


def program(params, steps, result):
    return {"params": list(params), "steps": [dict(s) for s in steps], "result": result}


def run(program_, values):
    """Execute a program at concrete rational coordinates, for the drawn instance."""
    coordinates = {name: (Fraction(x), Fraction(y)) for name, (x, y) in values.items()}
    local = dict(zip(program_["params"], program_["params"], strict=True))
    for step in program_["steps"]:
        xy, reason = rdsl.execute_primitive(step["prim"], [local[a] for a in step["args"]], coordinates)
        if xy is None:
            return None, reason
        coordinates[step["out"]] = xy
        local[step["out"]] = step["out"]
    return coordinates, None


def check(name, statement, program_, atom, arguments, values, results):
    """Decide the atom at the drawn configuration, then try to certify it for all of them."""
    record = {"law": name, "statement": statement, "atom": f"{atom}{tuple(arguments)}",
              "construction": [f"{s['prim']}({','.join(s['args'])}) -> {s['out']}"
                               for s in program_["steps"]]}
    coordinates, reason = run(program_, values)
    if coordinates is None:
        record.update(holds_at_the_drawn_configuration=None, refused=reason)
        results.append(record)
        return record
    record["holds_at_the_drawn_configuration"] = rdsl.atom_holds(atom, tuple(arguments), coordinates)
    began = time.perf_counter()
    counter = Counter()
    try:
        certificate = lib.certify_entry(atom, tuple(arguments), program_, counter)
        if certificate is not None:
            record["verdict"] = "certified for every configuration"
        elif counter["certification_budget_exceeded"]:
            # the decision procedure gave up on the size of the expression. That is an
            # unfinished proof, not a refutation, and is recorded as one
            record["verdict"] = "undecided: the expression passed the certifier's size bound"
        else:
            record["verdict"] = "not certified: the polynomial is not identically zero"
    except lib.CertificationBudgetExceeded as exceeded:
        record["verdict"] = f"undecided: {exceeded}"
    except Exception as failure:                                  # noqa: BLE001 - reported, not hidden
        record["verdict"] = f"undecided: {type(failure).__name__}: {failure}"
    record["certifier_counters"] = dict(counter)
    record["seconds"] = time.perf_counter()-began
    results.append(record)
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()
    output = Path(arguments.output)
    output.mkdir(parents=True, exist_ok=True)
    results = []

    # -- the law of reflection ---------------------------------------------
    # mirror line m1 m2, source i, an observer direction fixed by q;
    # p is where the ray meets the mirror, j is the image of the source
    reflection = program(
        ["m1", "m2", "i", "q"],
        [{"out": "p", "prim": "foot", "args": ["q", "m1", "m2"]},
         {"out": "j", "prim": "reflect", "args": ["i", "m1", "m2"]}],
        "j")
    values = {"m1": (-5, 0), "m2": (5, 0), "i": (0, 3), "q": (2, 4)}
    check("law of reflection",
          "the angle the incoming ray makes with the mirror equals the angle the outgoing ray makes",
          reflection, "eqangle", ["i", "p", "m1", "m2", "m1", "m2", "p", "j"], values, results)
    check("mirror image, perpendicularity",
          "the segment joining a point to its image is perpendicular to the mirror",
          reflection, "perp", ["j", "i", "m1", "m2"], values, results)
    check("mirror image, equal distance",
          "a point and its image are the same distance from any point of the mirror",
          reflection, "cong", ["j", "m1", "i", "m1"], values, results)
    check("mirror image, equal path",
          "the two legs of the reflected path are the legs of the straight path to the image",
          reflection, "cong", ["p", "i", "p", "j"], values, results)

    # -- the focal property of a parabola ----------------------------------
    # directrix d1 d2, focus f, a point q that fixes where on the curve we are:
    # t is the foot on the directrix, the tangent is the perpendicular bisector of f t,
    # and x is the point of the parabola above t
    parabola = program(
        ["d1", "d2", "f", "q"],
        [{"out": "t", "prim": "foot", "args": ["q", "d1", "d2"]},
         {"out": "md", "prim": "midpoint", "args": ["f", "t"]},
         {"out": "c", "prim": "circle", "args": ["f", "t", "q"]},
         {"out": "x", "prim": "intersection_ll", "args": ["q", "t", "md", "c"]}],
        "x")
    parabola_values = {"d1": (-4, 0), "d2": (4, 0), "f": (0, 2), "q": (3, 5)}
    check("parabola, focus and directrix",
          "a point of the parabola is as far from the focus as from the directrix",
          parabola, "cong", ["x", "f", "x", "t"], parabola_values, results)
    check("parabola, focal reflection",
          "the tangent makes equal angles with the axis-parallel ray and with the ray to the focus",
          parabola, "eqangle", ["x", "t", "x", "md", "x", "md", "x", "f"], parabola_values, results)

    # -- the focal property of an ellipse ----------------------------------
    # foci f1 f2; x on the ellipse is built as the meeting of the line f1 p with the
    # perpendicular bisector of p f2, where p runs on the circle about f1
    ellipse = program(
        ["f1", "f2", "p", "z"],
        [{"out": "md", "prim": "midpoint", "args": ["p", "f2"]},
         {"out": "c", "prim": "circle", "args": ["p", "f2", "z"]},
         {"out": "x", "prim": "intersection_ll", "args": ["f1", "p", "md", "c"]}],
        "x")
    ellipse_values = {"f1": (-3, 0), "f2": (3, 0), "p": (2, 6), "z": (1, -2)}
    check("ellipse, focal reflection",
          "the tangent makes equal angles with the rays to the two foci",
          ellipse, "eqangle", ["f1", "x", "x", "md", "x", "md", "x", "f2"], ellipse_values, results)
    check("ellipse, equal legs",
          "the reflected leg has the length of the leg to the mirrored focus",
          ellipse, "cong", ["x", "p", "x", "f2"], ellipse_values, results)

    report = {
        "fragment": {"primitives": sorted(rdsl.primitive_contracts()),
                     "predicates": dict(sorted(rdsl.PREDICATE_ARITIES.items()))},
        "method": "each law is an atom over constructed points; `certify_entry` decides whether its "
                  "polynomial is identically zero over the rational function field of the free inputs, "
                  "which is the same procedure the library uses for its own operations",
        "results": results,
        "not_expressible": [
            "Snell's law as a law: there is no ratio predicate, no constant may appear in an atom, and "
            "the relation grammar has no implication, so a refractive index cannot be written and a law "
            "cannot be assumed as a hypothesis",
            "the two-focus property as a constant sum: cong compares two squared distances and there is "
            "no sum of lengths",
            "the thin-lens equation: no predicate compares ratios or reciprocals of lengths",
            "which side, which direction, which medium: all ten predicates are equalities or "
            "non-vanishing conditions, and certify_entry decides only whether a polynomial is zero, so "
            "an inequality is not merely unwritten but undecidable by this kernel",
        ]}
    (output/"result.json").write_text(json.dumps(report, indent=1, default=str)+"\n", encoding="utf-8")
    for record in results:
        print(f"  {record['law']:34s} drawn={record.get('holds_at_the_drawn_configuration')} "
              f"| {record.get('verdict')} ({record.get('seconds', 0):.1f}s)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
