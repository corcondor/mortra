"""A wanted shadow in, a construction out, and the same construction offered back to the search.

The path this connects:

    a wanted shadow  ->  relations the fragment can state  ->  the existing search
    ->  a construction program  ->  the existing drawing  ->  the existing acquisition
    ->  the next requirement

Nothing about the fragment changes. The search is `geometry_self_improvement.solve`,
the drawing is `geometry_ink`, the acquisition is `geometry_acquisition`. What is
added is the translation of a wanted shadow into goals and the handling of a
requirement that names more than one unknown point, both in
`geometry_shadow_design`.

    python scripts/run_shadow_design.py --output reports/shadow-design
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
from math_os_prototype import geometry_acquisition as acq
from math_os_prototype import geometry_ink as ink
from math_os_prototype import geometry_relational_library as lib
from math_os_prototype import geometry_self_improvement as loop
from math_os_prototype import geometry_shadow_design as design


def say(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def point(x, y):
    return (str(Fraction(x)), str(Fraction(y)))


# ---------------------------------------------------------------------------
# The requirements
# ---------------------------------------------------------------------------

def development_requirement():
    """A light, a line to put the occluder on, a screen, and the shadow wanted on it."""
    return {
        "name": "development: place a segment so its shadow is a wanted interval",
        "light": "l", "placement": ("k1", "k2"),
        "points": {"l": point(0, "3/2"), "k1": point(1, 0), "k2": point(1, 1),
                   "w1": point(3, 0), "w2": point(3, 1),
                   "s": point(3, "3/5"), "t": point(3, "12/5")},
        "wanted": [{"name": "A", "kind": "occluder_end", "target": "s"},
                   {"name": "B", "kind": "occluder_end", "target": "t"}],
        "verify": [{"kind": "shadow_interval", "light": "l", "occluder": ["A", "B"],
                    "receiving": ["w1", "w2"], "target": ["s", "t"]},
                   {"kind": "on_line", "point": "A", "line": ["k1", "k2"]},
                   {"kind": "on_line", "point": "B", "line": ["k1", "k2"]},
                   {"kind": "between", "point": "A", "from": "l", "to": "s"},
                   {"kind": "between", "point": "B", "from": "l", "to": "t"}],
        "unknowns_named": ["A", "B"]}


def slanted_requirement():
    """The line the occluder may sit on is not parallel to the screen."""
    return {
        "name": "the placement line is not parallel to the screen",
        "light": "l", "placement": ("k1", "k2"),
        "points": {"l": point(0, "3/2"), "k1": point(1, 0), "k2": point("6/5", 3),
                   "w1": point(3, 0), "w2": point(3, 1),
                   "s": point(3, "3/5"), "t": point(3, "12/5")},
        "wanted": [{"name": "A", "kind": "occluder_end", "target": "s"},
                   {"name": "B", "kind": "occluder_end", "target": "t"}],
        "verify": [{"kind": "shadow_interval", "light": "l", "occluder": ["A", "B"],
                    "receiving": ["w1", "w2"], "target": ["s", "t"]},
                   {"kind": "on_line", "point": "A", "line": ["k1", "k2"]},
                   {"kind": "on_line", "point": "B", "line": ["k1", "k2"]}],
        "unknowns_named": ["A", "B"]}


def unreachable_requirement():
    """A placement line the boundary rays only meet beyond the screen: no segment on it works.

    The relations are satisfiable — a point of that line does lie on the ray — and
    the search finds one. What fails is the order: the occluder would stand behind
    the screen, and the shadow would not be cast on it at all. It is here as a
    control, to show that the order condition is doing work.
    """
    return {
        "name": "control: the placement line is only met beyond the screen",
        "light": "l", "placement": ("k1", "k2"),
        "points": {"l": point(0, "3/2"), "k1": point(1, 0), "k2": point(2, 1),
                   "w1": point(3, 0), "w2": point(3, 1),
                   "s": point(3, "3/5"), "t": point(3, "12/5")},
        "wanted": [{"name": "A", "kind": "occluder_end", "target": "s"},
                   {"name": "B", "kind": "occluder_end", "target": "t"}],
        "verify": [{"kind": "shadow_interval", "light": "l", "occluder": ["A", "B"],
                    "receiving": ["w1", "w2"], "target": ["s", "t"]}],
        "unknowns_named": ["A", "B"], "expected": "refused by the order condition"}


def find_the_light_requirement():
    """The occluder is given; where must the light be for the shadow to land where it should?"""
    return {
        "name": "the occluder is known and the light is wanted",
        "light": "L", "placement": ("k1", "k2"),
        "points": {"a": point(1, "6/5"), "b": point(1, "9/5"), "k1": point(1, 0), "k2": point(1, 1),
                   "w1": point(3, 0), "w2": point(3, 1),
                   "s": point(3, "3/5"), "t": point(3, "12/5")},
        "wanted": [{"name": "L", "kind": "light", "rays": [("a", "s"), ("b", "t")]}],
        "verify": [{"kind": "shadow_interval", "light": "L", "occluder": ["a", "b"],
                    "receiving": ["w1", "w2"], "target": ["s", "t"]}],
        "unknowns_named": ["L"]}


def indirect_requirement(name, light, near, middle, screen_x, placement_x):
    """The wanted interval is given by its near end and its middle, not by both ends.

    The far end is then a point that has to be constructed as well, and the second
    occluder end depends on it: two steps where the plain form needs one, and five
    distinct given points at the interface, which the enumerated vocabulary — written
    over three — cannot hold.
    """
    return {
        "name": name, "light": "l", "placement": ("k1", "k2"),
        "points": {"l": point(*light), "k1": point(placement_x, 0), "k2": point(placement_x, 1),
                   "w1": point(screen_x, 0), "w2": point(screen_x, 1),
                   "s": point(*near), "m": point(*middle)},
        "wanted": [{"name": "A", "kind": "occluder_end", "target": "s"},
                   {"name": "T", "kind": "relation",
                    "goals": [{"predicate": "midp", "points": ["m", "s", "T"]},
                              {"predicate": "coll", "points": ["w1", "w2", "T"]}]},
                   {"name": "B", "kind": "occluder_end", "target": "T"}],
        "verify": [{"kind": "shadow_interval", "light": "l", "occluder": ["A", "B"],
                    "receiving": ["w1", "w2"], "target": ["s", "T"]},
                   {"kind": "on_line", "point": "A", "line": ["k1", "k2"]},
                   {"kind": "on_line", "point": "B", "line": ["k1", "k2"]}],
        "unknowns_named": ["A", "T", "B"]}


# ---------------------------------------------------------------------------
# Drawing one solved requirement
# ---------------------------------------------------------------------------

def points_on_segment(lattice, a, b):
    return [(index, xy) for index, xy in sorted(lattice.items()) if ink.on_closed_segment(xy, a, b)]


def draw_three(requirement, produced, output, lattice, radius, paper, spacing, *, pixels_per_unit):
    """The wanted shadow, the configuration the search found, and the shadow it casts."""
    coordinates = {name: tuple(Fraction(v) for v in value)
                   for name, value in requirement["points"].items()}
    coordinates.update(produced)
    light = coordinates[requirement["light"]]
    screen = (coordinates["w1"], coordinates["w2"])
    placement = (coordinates[requirement["placement"][0]], coordinates[requirement["placement"][1]])
    target_ends = (coordinates["s"], coordinates[requirement["verify"][0]["target"][1]])
    occluder = (produced["A"], produced["B"])
    sparse = ink.fill_for_coverage(0.05, radius, spacing)
    dense = ink.fill_for_coverage(0.55, radius, spacing)

    def given_lines():
        """The lines the requirement gives, dotted, so that a solid run reads against them."""
        on_k = points_on_segment(lattice, *_clip_line(placement, paper))
        on_w = points_on_segment(lattice, *_clip_line(screen, paper))
        return [(index, xy) for number, (index, xy) in enumerate(on_k+on_w) if number % 4 == 0]

    images = []
    wanted = points_on_segment(lattice, *target_ends)
    images.append(("1-wanted",
                   "what was asked: the two given lines dotted, and solid on the screen the "
                   "interval the shadow has to cover", given_lines()+wanted))
    found = points_on_segment(lattice, *occluder)
    images.append(("2-found",
                   "what the search returned: solid on the placement line, the segment it chose",
                   given_lines()+found))
    statistics = Counter()
    region = ink.select(lattice, lambda xy: dense if ink.occluded(
        xy, light, occluder[0], occluder[1], stats=statistics)[0] else sparse)
    images.append(("3-cast", "the shadow recomputed from the configuration the search returned",
                   region+found))
    records = []
    for name, description, points in images:
        stem = f"{requirement['stem']}-{name}"
        svg = ink.write_svg(output/f"{stem}.svg", points, radius, paper,
                            pixels_per_unit=pixels_per_unit)
        png = ink.write_png(output/f"{stem}.png", points, radius, paper,
                            pixels_per_unit=pixels_per_unit)
        check = ink.check_svg_is_one_radius_black_circles(output/f"{stem}.svg")
        records.append({"image": stem, "description": description, "dots": len(points),
                        "svg": svg["path"], "png": png["path"], "svg_check": check})
    return records


def _clip_line(line, paper):
    """The part of an infinite line that lies in the paper, as a segment."""
    x0, y0, x1, y1 = (Fraction(v) for v in paper)
    (ax, ay), (bx, by) = line
    if ax == bx:
        return ((ax, y0), (ax, y1))
    slope = (by-ay)/(bx-ax)
    return ((x0, ay+slope*(x0-ax)), (x1, ay+slope*(x1-ax)))


# ---------------------------------------------------------------------------
# Offering what was solved back to the acquisition the repository already has
# ---------------------------------------------------------------------------

def acquire_from(result, library, *, note):
    """Hand each solved unknown to the existing gate and record what it kept."""
    records = []
    for name, solution in result["solutions"].items():
        task = result["tasks"][name]
        outcome = acq.acquire(solution, task, definitions=getattr(library, "definitions", None))
        record = {"unknown": name, "acquired": outcome["acquired"]}
        if not outcome["acquired"]:
            record["reason"] = outcome["reason"]
            records.append(record)
            continue
        registration = acq.register(library, outcome, source={"note": note, "unknown": name})
        record.update({"registered": registration.get("registered"),
                       "reason": registration.get("reason"),
                       "index": registration.get("index"),
                       "generation": registration.get("generation"),
                       "parents": registration.get("parents"),
                       "steps": registration.get("steps"),
                       "body": outcome["body"],
                       "declared_and_certified": outcome["declared"],
                       "held_only_at_this_configuration": outcome.get("instance_only"),
                       "lineage_recorded": registration.get("lineage_recorded")})
        records.append(record)
    return records


def evaluation_set():
    """Fixed before the comparison: three of the same shape, one whose unknown is different."""
    return [
        indirect_requirement("evaluation 1: near end and middle, moved",
                             (0, "7/5"), (3, "1/2"), (3, "3/2"), 3, 1),
        indirect_requirement("evaluation 2: near end and middle, moved again",
                             ("1/5", "8/5"), (3, "2/5"), (3, "7/5"), 3, 1),
        indirect_requirement("evaluation 3: a different screen and placement line",
                             (0, "3/2"), ("7/2", "1/2"), ("7/2", "3/2"), "7/2", "3/2"),
        find_the_light_requirement(),
    ]


def condition(name, requirements, library, policy, applications):
    began = time.perf_counter()
    rows, totals = [], Counter()
    for requirement in requirements:
        record, result, produced = attempt(requirement, library=library, policy=policy,
                                           applications=applications)
        consulted = sum(row.get("acquired_certificates_consulted_during_this_search", 0)
                        for row in record["rows"])
        used = sorted({index for row in record["rows"]
                       for index in row.get("acquired_operations_in_the_answer", [])})
        rows.append({"requirement": requirement["name"], "solved": record["solved"],
                     "verified": record.get("verification", {}).get("passed"),
                     "primitive_steps": (record.get("program") or {}).get("primitive_steps"),
                     "acquired_certificates_consulted_during_search": consulted,
                     "acquired_operations_in_the_answer": used,
                     "seconds": record["seconds"], "costs": record["costs"]})
        for key, value in record["costs"].items():
            totals[key] += value
    summary = {"condition": name, "requirements": len(requirements),
               "solved": sum(1 for row in rows if row["solved"]),
               "verified": sum(1 for row in rows if row["verified"]),
               "plan_expansions": totals["plan_expansions"],
               "primitive_applications": totals["applications"],
               "condition_checks": totals["polynomial_checks"],
               "library_queries": totals["library_queries"],
               "exact_certifications": totals["exact_certifications"],
               "acquired_certificates_reused": totals["acquired_certificates_reused"],
               "seconds": time.perf_counter()-began,
               "requirements_that_consulted_an_acquired_operation":
                   sum(1 for row in rows if row["acquired_certificates_consulted_during_search"]),
               "requirements_whose_answer_contains_an_acquired_operation":
                   sum(1 for row in rows if row["acquired_operations_in_the_answer"])}
    return {"summary": summary, "rows": rows}


# ---------------------------------------------------------------------------
# One requirement, end to end
# ---------------------------------------------------------------------------

def attempt(requirement, *, library, policy, applications):
    began = time.perf_counter()
    result = design.solve_system(requirement, library=library, policy=policy,
                                 applications=applications)
    record = {"requirement": requirement["name"], "unknowns": requirement["unknowns_named"],
              "solved": result["solved"], "seconds": time.perf_counter()-began,
              "rows": result["rows"], "costs": result["costs"]}
    if not result["solved"]:
        record.update(stopped_at=result.get("stopped_at"), stop_reason=result.get("stop_reason"))
        return record, None, None
    program = design.program_of(requirement, result)
    produced, reason = design.run_program(program, requirement["points"])
    record["program"] = program
    record["produced"] = {k: [str(v) for v in value] for k, value in produced.items()}
    record["rerun_refused"] = reason
    record["verification"] = design.check_requirement(requirement, produced)
    record["used_acquired_operations"] = []
    return record, result, produced


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--applications", type=int, default=40)
    parser.add_argument("--depth", type=int, default=5)
    parser.add_argument("--pixels-per-unit", type=int, default=300)
    arguments = parser.parse_args()
    output = Path(arguments.output)
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    report = {"environment": {
        "sha": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True).stdout.strip(),
        "python": sys.version.split()[0], "platform": platform.platform()},
        "protocol": {
            "translation": "one rule for every task: an end of the shadow is where the boundary "
                           "ray through an end of the occluder meets the screen, which is coll on "
                           "the placement line and coll on the ray, with the order condition kept "
                           "apart because the fragment cannot state an inequality",
            "search": "geometry_self_improvement.solve, unchanged",
            "drawing": "geometry_ink, unchanged",
            "acquisition": "geometry_acquisition, unchanged"}}

    base = lib.acquire_index(max_depth=2, stats=Counter())
    library = acqlib.AcquiredLibrary(base)
    policy = dict(loop.START_POLICY)
    say(f"vocabulary: {len(base.programs)} enumerated programs")

    # -- 1. where the existing search stops ---------------------------------
    say("locating the stop")
    development = development_requirement()
    collapsed = {"points": development["points"],
                 "goals": [{"predicate": "coll", "points": ["k1", "k2", "u"]},
                           {"predicate": "coll", "points": ["l", "s", "u"]},
                           {"predicate": "coll", "points": ["l", "t", "u"]}]}
    stop = {}
    for label, extra in (("directed search", {}),
                         ("with backward substitution", {"backward_substitution": True})):
        began = time.perf_counter()
        row = loop.solve(collapsed, library=library, policy=dict(policy, **extra),
                         applications=arguments.applications)
        stop[label] = {"solved": row["solved"], "stop_reason": row["stop_reason"],
                       "seconds": time.perf_counter()-began,
                       "costs": {k: v for k, v in row["costs"].items()
                                 if k in ("applications", "plan_expansions", "library_queries",
                                          "max_queue", "polynomial_checks")
                                 or k.startswith("backward_spec")}}
        say(f"   {label}: solved={row['solved']} stop={row['stop_reason']}")
    report["where_it_stopped"] = {
        "what_was_asked": "one unknown point required to carry both ends of the wanted shadow",
        "why_that_is_the_faithful_collapse": "the solver's task format is a set of given points and "
                                             "goals over them and one unknown; a goal set naming two "
                                             "unknown points cannot be written in it at all",
        "runs": stop,
        "connection_added": "solve_system: each unknown is posed to the same search as its own task "
                            "over the given points and everything solved so far, so the unknowns "
                            "share the light and the placement line and a later one may depend on "
                            "an earlier one"}

    # -- 2. the development requirement, end to end -------------------------
    development["stem"] = "dev"
    say("the development requirement")
    record, result, produced = attempt(development, library=library, policy=policy,
                                       applications=arguments.applications)
    say(f"   solved={record['solved']} verification="
        f"{record.get('verification', {}).get('passed')}")
    report["development"] = record
    if not record["solved"]:
        (output/"result.json").write_text(json.dumps(report, indent=1, default=str)+"\n",
                                          encoding="utf-8")
        return 1

    # -- 3. the three pictures ----------------------------------------------
    say("drawing the three pictures")
    spacing = Fraction(1, 2**arguments.depth)
    radius = spacing/2
    paper = (Fraction(0), Fraction(0), Fraction(4), Fraction(3))
    lattice, lattice_statistics = ink.paper_lattice(4, 3, arguments.depth, Counter())
    report["drawing"] = {"lattice_points": len(lattice),
                         "primitive_applications": lattice_statistics["primitive_applications"],
                         "radius": float(radius), "spacing": float(spacing),
                         "images": draw_three(development, produced, output, lattice, radius, paper,
                                              spacing, pixels_per_unit=arguments.pixels_per_unit)}
    for image in report["drawing"]["images"]:
        say(f"   {image['image']}: {image['dots']} dots")

    # -- 4. the other requirements ------------------------------------------
    say("the other requirements")
    variants = [slanted_requirement(), unreachable_requirement(), find_the_light_requirement(),
                indirect_requirement("the interval is given by its near end and its middle",
                                     (0, "3/2"), (3, "3/5"), (3, "3/2"), 3, 1)]
    report["variants"] = []
    for requirement in variants:
        record, _, _ = attempt(requirement, library=library, policy=policy,
                               applications=arguments.applications)
        say(f"   {requirement['name']}: solved={record['solved']} "
            f"verified={record.get('verification', {}).get('passed')} "
            f"{'stopped at '+str(record.get('stopped_at')) if not record['solved'] else ''}")
        report["variants"].append(record)

    # -- 5. offering the solved constructions to the acquisition gate --------
    say("acquisition")
    training = [development_requirement(),
                indirect_requirement("training: near end and middle",
                                     (0, "3/2"), (3, "3/5"), (3, "3/2"), 3, 1)]
    learned = acqlib.AcquiredLibrary(base)
    acquisition, acquisition_seconds = [], 0.0
    for requirement in training:
        began = time.perf_counter()
        _, result, _ = attempt(requirement, library=learned, policy=policy,
                               applications=arguments.applications)
        if result is None:
            continue
        acquisition.append({"from": requirement["name"],
                            "records": acquire_from(result, learned, note=requirement["name"])})
        acquisition_seconds += time.perf_counter()-began
    report["acquisition"] = {"records": acquisition, "library": learned.state(),
                             "seconds": acquisition_seconds,
                             "note": "the cost of acquiring is charged to condition B below"}
    for entry in acquisition:
        for record in entry["records"]:
            say(f"   {entry['from'][:36]} / {record['unknown']}: "
                f"{'kept as ' + str(record.get('index')) if record.get('registered') else record.get('reason')}")

    # -- 6. the comparison ---------------------------------------------------
    say("comparison: without and with the acquired operations")
    evaluation = evaluation_set()
    report["comparison"] = {
        "protocol": "the requirements and the budget are fixed before either condition runs, and "
                    "nothing is acquired from the evaluation requirements themselves",
        "budget_applications": arguments.applications,
        "A": condition("A: enumerated vocabulary only", evaluation,
                       acqlib.AcquiredLibrary(base), policy, arguments.applications),
        "B": condition("B: the same, with what was acquired from the training requirements",
                       evaluation, learned, policy, arguments.applications)}
    report["comparison"]["B"]["summary"]["acquisition_seconds_to_be_added"] = acquisition_seconds
    for key in ("A", "B"):
        summary = report["comparison"][key]["summary"]
        say(f"   {key}: solved {summary['solved']}/{summary['requirements']}, "
            f"plans {summary['plan_expansions']}, applications {summary['primitive_applications']}, "
            f"checks {summary['condition_checks']}, seconds {summary['seconds']:.1f}, "
            f"consulted {summary['requirements_that_consulted_an_acquired_operation']}")

    report["total_seconds"] = time.perf_counter()-started
    (output/"result.json").write_text(json.dumps(report, indent=1, default=str)+"\n",
                                      encoding="utf-8")
    print(json.dumps({"stop": {k: {"solved": v["solved"], "stop_reason": v["stop_reason"]}
                               for k, v in stop.items()},
                      "development": {"solved": report["development"]["solved"],
                                      "program": report["development"].get("program"),
                                      "produced": report["development"].get("produced"),
                                      "verified": report["development"]["verification"]["passed"]},
                      "variants": [{"name": v["requirement"], "solved": v["solved"],
                                    "verified": v.get("verification", {}).get("passed"),
                                    "steps": (v.get("program") or {}).get("primitive_steps"),
                                    "stopped_at": v.get("stopped_at"),
                                    "stop_reason": v.get("stop_reason")}
                                   for v in report["variants"]],
                      "acquisition": [{"from": e["from"],
                                       "records": [{k: rec.get(k) for k in
                                                    ("unknown", "registered", "reason", "index",
                                                     "generation", "steps")}
                                                   for rec in e["records"]]}
                                      for e in report["acquisition"]["records"]],
                      "comparison": {k: report["comparison"][k]["summary"] for k in ("A", "B")}},
                     indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
