"""Synthesising drawing programs over a fixed geometric core, and reusing what they share.

The geometric core is read from the source and recorded, so a run can show it did
not move. What varies is the input, the program the search builds, the library it
has acquired, and the search order.

    a requirement  ->  the search builds a program  ->  the interpreter runs it
    ->  exact checks  ->  the existing dot renderer  ->  SVG and PNG

and then the same program is run again with the inputs moved, the depth raised
and the resolution changed, without a line of source changing.

    python scripts/run_drawing_synthesis.py --output reports/drawing-synthesis
"""
from __future__ import annotations

import argparse
from collections import Counter
from fractions import Fraction
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from math_os_prototype import geometry_acquired_library as acqlib
from math_os_prototype import geometry_drawing_program as dp
from math_os_prototype import geometry_ink as ink
from math_os_prototype import geometry_relational_library as lib
from math_os_prototype import geometry_self_posing as posing
from math_os_prototype.representation_progress import digest


def say(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def fraction_point(x, y):
    return (Fraction(x), Fraction(y))


def quadratic(t, a, b, c):
    """A point of the quadratic through a, b, c — used only to write the requirements."""
    return tuple((1-t)**2*a[i]+2*t*(1-t)*b[i]+t**2*c[i] for i in (0, 1))


# ---------------------------------------------------------------------------
# The requirements
# ---------------------------------------------------------------------------

def requirements():
    a, b, c = fraction_point(0, 0), fraction_point(4, 6), fraction_point(8, 0)
    inputs = {"p0": a, "p1": b, "p2": c}
    three = [quadratic(Fraction(1, 2), a, b, c), quadratic(Fraction(1, 4), a, b, c),
             quadratic(Fraction(3, 4), a, b, c)]
    seven = three+[quadratic(Fraction(k, 8), a, b, c) for k in (1, 3, 5, 7)]
    square = {"p0": fraction_point(0, 0), "p1": fraction_point(8, 0), "p2": fraction_point(8, 8)}
    return [
        {"name": "three points of a curve", "inputs": inputs,
         "must_contain": three, "depth": 3,
         "note": "a weak specification: several programs meet it, and the search is free to "
                 "return the cheapest"},
        {"name": "seven points of a curve", "inputs": inputs,
         "must_contain": seven, "depth": 3,
         "note": "the same three points and four more; the extra points are what pins the rule"},
        {"name": "a curve on a different triangle", "inputs": square,
         "must_contain": [quadratic(Fraction(k, 8), square["p0"], square["p1"], square["p2"])
                          for k in (1, 2, 3, 4, 5, 6, 7)], "depth": 3,
         "note": "unseen: the same shape of requirement on inputs the search has not had"},
    ]


# ---------------------------------------------------------------------------
# Offering a synthesised body to the existing acquisition path
# ---------------------------------------------------------------------------

def acquire_body(library, program, inputs, *, samples=16):
    """Certify what the body guarantees, with the library's own exact procedure.

    The relations that hold of the emitted point are enumerated the way the poser
    enumerates them, and each is decided over the rational function field by
    `certify_entry`. Only what certifies is kept.
    """
    steps = [{"out": statement["let"], "prim": statement["op"], "args": list(statement["args"])}
             for statement in program["body"] if "let" in statement]
    stored = {"params": list(program["params"]), "steps": steps, "result": program["emit"][0]}
    if library.holds(stored):
        return {"registered": False, "reason": "an identical program is already indexed"}
    coordinates = {name: dp.exact(value) for name, value in inputs.items()}
    for step in steps:
        xy, reason = dp.apply_operator(step["prim"], step["args"], coordinates,
                                       dp.operators(), Counter())
        if xy is None:
            return {"registered": False, "reason": f"the body refused: {reason}"}
        coordinates[step["out"]] = dp.exact(xy)
    hidden = program["emit"][0]
    statistics = Counter()
    relations = posing.holding_relations(__import__("random").Random(7), coordinates, hidden,
                                         list(program["params"]), samples=samples, stats=statistics)
    certificates, declared = {}, []
    for predicate, arguments in relations[:12]:
        pattern = (predicate, tuple("v" if name == hidden else name for name in arguments))
        if "v" not in pattern[1]:
            continue
        certificate = lib.certify_entry(pattern[0], pattern[1], stored)
        if certificate is not None:
            certificates[pattern] = certificate
            declared.append([pattern[0], list(pattern[1])])
    if not certificates:
        return {"registered": False, "reason": "nothing it guarantees certified"}
    index = library.register(stored, certificates,
                             source={"from": "a synthesised drawing program",
                                     "body": steps, "generation": 1, "parents": [], "calls": []})
    return {"registered": True, "index": index, "steps": len(steps), "declared": declared,
            "relations_considered": len(relations)}


# ---------------------------------------------------------------------------
# One requirement
# ---------------------------------------------------------------------------

def synthesise(requirement, library, *, levels, node_budget, macros=()):
    table = dp.operators(library, macros)
    began = time.perf_counter()
    counter = Counter()
    result = dp.synthesise_rule(requirement["must_contain"], requirement["inputs"],
                                table=table, levels=levels, node_budget=node_budget,
                                counter=counter, depth=requirement["depth"])
    seconds = time.perf_counter()-began
    record = {"requirement": requirement["name"], "solved": result["solved"], "seconds": seconds,
              "counter": result.get("counter", dict(counter)),
              "operators_available": len(table),
              "acquired_operators_available": sum(1 for entry in table.values()
                                                  if entry["kind"] == "acquired"),
              "macros_available": sum(1 for entry in table.values() if entry["kind"] == "macro")}
    if not result["solved"]:
        record.update(stopped_at=result.get("stopped_at"), reason=result.get("reason"),
                      attempts=result.get("attempts"))
        return record, None
    program = result["program"]
    record["program"] = program
    record["covered_by"] = result.get("covered_by")
    record["uses_acquired_operations"] = sorted({statement["op"] for statement in program["body"]
                                                 if "let" in statement
                                                 and statement["op"].startswith("op:")})
    record["uses_macros"] = sorted({statement["op"] for statement in program["body"]
                                    if "let" in statement and statement["op"].startswith("macro:")})
    record["check"] = dp.check(program, requirement["inputs"], requirement["depth"],
                              {"must_contain": requirement["must_contain"]}, table=table)
    return record, program


# ---------------------------------------------------------------------------
# Drawing, and the interventions
# ---------------------------------------------------------------------------

def draw(name, points, output, *, paper, radius, pixels_per_unit, lattice=None, spacing=None):
    """Put the emitted points on paper with the renderer that already exists."""
    marks = [((0, index), dp.exact(point)) for index, point in enumerate(points)]
    svg = ink.write_svg(output/f"{name}.svg", marks, radius, paper, pixels_per_unit=pixels_per_unit)
    png = ink.write_png(output/f"{name}.png", marks, radius, paper, pixels_per_unit=pixels_per_unit)
    check = ink.check_svg_is_one_radius_black_circles(output/f"{name}.svg")
    return {"image": name, "dots": len(marks), "svg": svg["path"], "png": png["path"],
            "svg_check": check, "radius": float(radius)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--levels", type=int, default=2)
    parser.add_argument("--node-budget", type=int, default=3500)
    parser.add_argument("--pixels-per-unit", type=int, default=120)
    arguments = parser.parse_args()
    output = Path(arguments.output)
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    core = dp.geometric_core()
    report = {"environment": {
        "sha": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True).stdout.strip(),
        "python": sys.version.split()[0], "platform": platform.platform()},
        "geometric_core": {"primitives": sorted(core["primitives"]),
                           "predicates": core["predicates"],
                           "digest": digest([core])},
        "execution_language": {
            "added": ["let x = op(args)", "emit x", "call rule(args) at one lower depth",
                      "keep x where an existing relation holds"],
            "not_added": "no predicate, no primitive, no theorem; recursion is bounded by a depth "
                         "the caller gives and every call lowers, so nothing here is a claim about "
                         "unbounded repetition",
            "counted": "let, call and keep each count in the cost of a search that uses them"},
        "search": {"point_level": "a bounded bottom-up enumeration over the operators, cheapest "
                                  "arity first, with a node budget",
                   "why_not_the_existing_search": "the point-level hole is an equality — a "
                                                  "construction whose output is this point — and an "
                                                  "equality goal matches no primitive's guarantee, "
                                                  "so the contract-directed search offers no "
                                                  "candidate at all; measured below",
                   "structural": "the recursion arguments are chosen by trying the tuples the "
                                 "body's own names allow and keeping those that produce the "
                                 "targets still missing",
                   "levels": arguments.levels, "node_budget": arguments.node_budget}}
    say(f"core: {len(core['primitives'])} primitives, {len(core['predicates'])} predicates")

    base = lib.acquire_index(max_depth=2, stats=Counter())
    tasks = requirements()

    # -- condition A: no acquired operation ---------------------------------
    say("condition A: the enumerated core only")
    library_a = acqlib.AcquiredLibrary(base)
    report["A"] = []
    programs = {}
    for requirement in tasks:
        record, program = synthesise(requirement, library_a, levels=arguments.levels,
                                     node_budget=arguments.node_budget)
        say(f"   {requirement['name']}: solved={record['solved']} "
            f"nodes={record['counter'].get('nodes')} seconds={record['seconds']:.1f}")
        report["A"].append(record)
        if program is not None:
            programs[requirement["name"]] = (program, requirement)

    # -- the pictures, and the interventions --------------------------------
    say("drawing and intervening")
    paper = (Fraction(-2), Fraction(-2), Fraction(10), Fraction(7))
    radius = Fraction(1, 16)
    images, interventions = [], []
    chosen = programs.get("seven points of a curve") or next(iter(programs.values()), None)
    if chosen is not None:
        program, requirement = chosen
        for depth in (2, 3, 5):
            points, counter = dp.run(program, requirement["inputs"], depth)
            images.append({**draw(f"depth-{depth}", points, output, paper=paper, radius=radius,
                                  pixels_per_unit=arguments.pixels_per_unit),
                           "intervention": f"the same program at depth {depth}",
                           "primitive_applications": counter["primitive_applications"]})
            say(f"   depth {depth}: {len(points)} points")
        moved = {"p0": fraction_point(-1, 1), "p1": fraction_point(3, 9), "p2": fraction_point(9, -1)}
        points, counter = dp.run(program, moved, 5)
        images.append({**draw("inputs-moved", points, output, paper=paper, radius=radius,
                              pixels_per_unit=arguments.pixels_per_unit),
                       "intervention": "the same program, the input points moved",
                       "primitive_applications": counter["primitive_applications"]})
        wide = dp.run(program, requirement["inputs"], 5)[0]
        images.append({**draw("resolution-doubled", wide, output, paper=paper, radius=radius,
                              pixels_per_unit=arguments.pixels_per_unit*2),
                       "intervention": "the same points at twice the resolution, the same radius "
                                       "in paper units"})
        interventions = [
            {"intervention": "depth", "checked": "the number of emitted points follows the "
                                                 "recursion and the program is unchanged",
             "points_by_depth": {str(d): len(dp.run(program, requirement["inputs"], d)[0])
                                 for d in (1, 2, 3, 4, 5, 6)}},
            {"intervention": "inputs moved", "checked": "the program still runs and still emits "
                                                        "the same number of points",
             "points": len(points),
             "same_count_as_before": len(points) == len(dp.run(program, requirement["inputs"], 5)[0])},
        ]
        report["chosen_program"] = {"requirement": requirement["name"], "program": program}
    report["images"] = images
    report["interventions"] = interventions

    # -- acquisition, then condition B --------------------------------------
    say("acquisition from the development programs")
    library_b = acqlib.AcquiredLibrary(base)
    acquisition, acquisition_seconds = [], 0.0
    for name in ("three points of a curve", "seven points of a curve"):
        if name not in programs:
            continue
        program, requirement = programs[name]
        began = time.perf_counter()
        acquisition.append({"from": name,
                            **acquire_body(library_b, program, requirement["inputs"])})
        acquisition_seconds += time.perf_counter()-began
        say(f"   {name}: {acquisition[-1].get('reason') or 'kept as ' + str(acquisition[-1].get('index'))}")
    report["acquisition"] = {"records": acquisition, "seconds": acquisition_seconds,
                             "library": library_b.state()}

    # what the solved programs are made of, kept so a later search reaches it sooner
    macros = []
    for name in ("three points of a curve", "seven points of a curve"):
        if name not in programs:
            continue
        macro = dp.macro_from(programs[name][0])
        if macro is not None and all(macro["name"] != held["name"] for held in macros):
            macros.append(macro)
    report["macros"] = {"kept": [{k: m[k] for k in ("name", "params", "steps", "result",
                                                    "primitive_steps", "note")} for m in macros],
                        "digest": dp.macro_digest(macros) if macros else None,
                        "what_they_are_not": "not certified operations; they carry no guarantee and "
                                             "are not offered to the relational retrieval"}
    say(f"macros kept: {[m['name'] for m in macros]}")

    say("condition B: the same, with what was acquired and what was kept as macros")
    report["B"] = []
    for requirement in tasks:
        record, _ = synthesise(requirement, library_b, levels=arguments.levels,
                               node_budget=arguments.node_budget, macros=macros)
        say(f"   {requirement['name']}: solved={record['solved']} "
            f"nodes={record['counter'].get('nodes')} seconds={record['seconds']:.1f} "
            f"macros={record.get('uses_macros')} acquired={record.get('uses_acquired_operations')}")
        report["B"].append(record)

    def summarise(rows, label):
        return {"condition": label,
                "solved": sum(1 for row in rows if row["solved"]),
                "requirements": len(rows),
                "nodes": sum(row["counter"].get("nodes", 0) for row in rows),
                "primitive_applications": sum(row["counter"].get("primitive_applications", 0)
                                              for row in rows),
                "call_candidates": sum(row["counter"].get("call_candidates", 0) for row in rows),
                "bodies_tried": sum(row["counter"].get("bodies_tried", 0) for row in rows),
                "seconds": sum(row["seconds"] for row in rows),
                "requirements_using_an_acquired_operation":
                    sum(1 for row in rows if row.get("uses_acquired_operations")),
                "requirements_using_a_macro":
                    sum(1 for row in rows if row.get("uses_macros"))}

    report["comparison"] = {"A": summarise(report["A"], "A: enumerated core only"),
                            "B": summarise(report["B"], "B: with the acquired operations"),
                            "acquisition_seconds_charged_to_B": acquisition_seconds,
                            "protocol": "the requirements and the budget were fixed before either "
                                        "condition ran; nothing was acquired from the unseen "
                                        "requirement"}
    report["total_seconds"] = time.perf_counter()-started
    (output/"result.json").write_text(json.dumps(report, indent=1, default=str)+"\n",
                                      encoding="utf-8")
    print(json.dumps({"comparison": report["comparison"],
                      "A": [{k: row.get(k) for k in ("requirement", "solved", "seconds")}
                            for row in report["A"]],
                      "B": [{k: row.get(k) for k in ("requirement", "solved", "seconds",
                                                     "uses_macros", "uses_acquired_operations")}
                            for row in report["B"]],
                      "macros": [m["name"] for m in report["macros"]["kept"]],
                      "acquisition": acquisition}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
