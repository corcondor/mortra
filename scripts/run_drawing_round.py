"""One round of: a directive, a formal requirement, a search, a program, a picture.

Ten requirements of different shape go to the same search. There is no solver
per kind of picture: what differs between them is the input points, the shared
variables, what has to repeat, and which conditions the answer must meet. The
search is `geometry_drawing_program.synthesise_for`, the drawing is
`geometry_ink`, and what one round leaves for the next is
`geometry_drawing_experience`.

The directive is Japanese prose and the formal requirement beside it was written
by a person. That is recorded with every task: nothing here reads natural
language.

    python scripts/run_drawing_round.py --output reports/drawing-round
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

from math_os_prototype import geometry_drawing_experience as experience
from math_os_prototype import geometry_drawing_program as dp
from math_os_prototype import geometry_ink as ink


def say(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def quadratic(t, a, b, c):
    return tuple((1-t)**2*a[i]+2*t*(1-t)*b[i]+t**2*c[i] for i in (0, 1))


# ---------------------------------------------------------------------------
# The ten requirements
# ---------------------------------------------------------------------------

def tasks():
    """Ten requirements of different shape. The formal side of each is human-written."""
    triangle = {"p0": (F(0), F(0)), "p1": (F(4), F(6)), "p2": (F(8), F(0))}
    cell = {"p0": (F(0), F(0)), "p1": (F(2), F(0)), "p2": (F(2), F(2)), "p3": (F(0), F(2))}
    line = {"p0": (F(0), F(0)), "p1": (F(8), F(0)), "p2": (F(2), F(5))}
    disk = {"p0": (F(4), F(4)), "p1": (F(8), F(4)), "p2": (F(0), F(0))}
    made = [
        {"name": "curve-seven",
         "directive": "三点を与える。その三点が定める二次曲線の、八等分点を描け。",
         "assumptions": "入力は三点。曲線は二次で、八等分は媒介変数 t = k/8 の意味。",
         "inputs": triangle, "depth": 3,
         "requirement": {"must_contain": [quadratic(F(k, 8), *triangle.values())
                                          for k in (1, 2, 3, 4, 5, 6, 7)], "depth": 3},
         "scoring": {"must_contain": "all", "max_points": 15, "max_extra": 8}},
        {"name": "curve-three",
         "directive": "同じ三点で、中央と四分の一と四分の三の点だけを要求する。",
         "assumptions": "弱い仕様。これを満たす構成は複数ある。",
         "inputs": triangle, "depth": 3,
         "requirement": {"must_contain": [quadratic(F(k, 4), *triangle.values())
                                          for k in (1, 2, 3)], "depth": 3},
         "scoring": {"must_contain": "all", "max_points": 15, "max_extra": 12}},
        {"name": "lattice-row",
         "directive": "単位胞の四隅を与える。その胞を横に繰り返し、一直線上に相異なる格子点を六つ以上描け。",
         "assumptions": "入力は正方形の四隅。繰り返しは一方向、有限回。与えた点は答えに数えない。",
         "inputs": cell, "depth": 4,
         "requirement": {"must_contain": [(F(4), F(0)), (F(6), F(0)), (F(8), F(0))],
                         "all_satisfy": [{"predicate": "coll", "points": ["p0", "p1", "z"]}],
                         "distinct_count": 6, "exclude_inputs": True, "depth": 4},
         "scoring": {"must_contain": "all", "max_points": 30, "min_distinct": 6,
                     "no_input_points": True, "all_satisfy": "every point"}},
        {"name": "lattice-two-directions",
         "directive": "同じ胞を縦と横の二方向に繰り返し、格子の一部として相異なる点を八つ以上描け。",
         "assumptions": "二方向。各方向の繰り返しは有限回。与えた点は答えに数えない。",
         "inputs": cell, "depth": 4,
         "requirement": {"must_contain": [(F(2*i), F(2*j)) for i in (0, 1, 2) for j in (0, 1, 2)
                                          if (2*i, 2*j) not in ((0, 0), (2, 0), (2, 2), (0, 2))],
                         "distinct_count": 8, "exclude_inputs": True, "depth": 4},
         "scoring": {"must_contain": "all", "max_points": 40, "min_distinct": 8,
                     "no_input_points": True}},
        {"name": "orbit-quarter-turn",
         "directive": "正方形とその外の一点を与える。正方形の中心まわりに四回対称な軌道を描け。",
         "assumptions": "四回対称は、与えられた正方形の中心と辺が決める。",
         "inputs": dict(cell, q=(F(4), F(1))), "depth": 3,
         "requirement": {"must_contain": [(F(0), F(3)), (F(-2), F(1)), (F(2), F(-1))],
                         "distinct_count": 4, "exclude_inputs": True, "depth": 3},
         "scoring": {"must_contain": "all", "max_points": 20, "min_distinct": 4,
                     "no_input_points": True}},
        {"name": "midpoint-chain",
         "directive": "二点を与える。両者の間を半分ずつ詰めていく点列を描け。",
         "assumptions": "入力は二点。点列は有限で、深さで決まる。",
         "inputs": {"p0": (F(0), F(0)), "p1": (F(16), F(0))}, "depth": 5,
         "requirement": {"must_contain": [(F(8), F(0)), (F(4), F(0)), (F(2), F(0))], "depth": 5},
         "scoring": {"must_contain": "all", "max_points": 40, "max_extra": 37}},
        {"name": "all-on-a-line",
         "directive": "三点を与える。最初の二点が決める直線の上に、与えた点とは別の点を五つ以上描け。",
         "assumptions": "関係だけの仕様。どの点を描くかは指定しない。与えた点をそのまま出すのは答えにしない。",
         "inputs": line, "depth": 3,
         "requirement": {"all_satisfy": [{"predicate": "coll", "points": ["p0", "p1", "z"]}],
                         "distinct_count": 5, "exclude_inputs": True, "depth": 3},
         "scoring": {"all_satisfy": "every point", "max_points": 30, "min_distinct": 5,
                     "no_input_points": True}},
        {"name": "inside-a-disk",
         "directive": "中心と半径を決める二点、そして外の一点を与える。その円盤の中に、与えた点とは別の点を五つ以上置け。",
         "assumptions": "円盤は中心 p0、半径 |p0 p1|。領域だけの仕様。与えた点をそのまま出すのは答えにしない。",
         "inputs": disk, "depth": 3,
         "requirement": {"all_inside": [{"centre": "p0", "through": "p1"}],
                         "distinct_count": 5, "exclude_inputs": True, "depth": 3},
         "scoring": {"all_inside": "every point", "max_points": 30, "min_distinct": 5,
                     "no_input_points": True}},
        {"name": "curve-inside-a-disk",
         "directive": "曲線の点を描き、そのすべてを指定の円盤の中に収めよ。",
         "assumptions": "曲線の三点と円盤の二点を同時に与える。二種類の条件の組み合わせ。",
         "inputs": {"p0": (F(2), F(2)), "p1": (F(4), F(6)), "p2": (F(6), F(2)),
                    "p3": (F(4), F(4)), "p4": (F(8), F(4))}, "depth": 3,
         "requirement": {"must_contain": [(F(4), F(3)), (F(3), F(F(7, 2)))],
                         "all_inside": [{"centre": "p3", "through": "p4"}],
                         "distinct_count": 3, "exclude_inputs": True, "depth": 3},
         "scoring": {"must_contain": "all", "all_inside": "every point", "max_points": 20,
                     "min_distinct": 3, "no_input_points": True}},
        {"name": "count-eight",
         "directive": "三点を与える。ちょうど七つの点を描け。",
         "assumptions": "個数だけの仕様に、直線上という関係を添える。",
         "inputs": line, "depth": 3,
         "requirement": {"distinct_count": 7,
                         "all_satisfy": [{"predicate": "coll", "points": ["p0", "p1", "z"]}],
                         "exclude_inputs": True, "depth": 3},
         "scoring": {"min_distinct": 7, "all_satisfy": "every point", "no_input_points": True}},
    ]
    return made


# ---------------------------------------------------------------------------
# Scoring, fixed before the search runs
# ---------------------------------------------------------------------------

def score(task, program, verification, points):
    """The conditions fixed in the task, decided after the fact but never chosen after it."""
    rules = task["scoring"]
    lines = []
    if "max_points" in rules:
        lines.append({"condition": f"at most {rules['max_points']} points drawn",
                      "passed": len(points) <= rules["max_points"], "produced": len(points)})
    if "min_points" in rules:
        lines.append({"condition": f"at least {rules['min_points']} points drawn",
                      "passed": len(points) >= rules["min_points"], "produced": len(points)})
    if "min_distinct" in rules:
        distinct = len({dp.exact(point) for point in points})
        lines.append({"condition": f"at least {rules['min_distinct']} distinct points drawn",
                      "passed": distinct >= rules["min_distinct"], "produced": distinct})
    if rules.get("no_input_points"):
        given = {dp.exact(value) for value in task["inputs"].values()}
        drawn = {dp.exact(point) for point in points}
        lines.append({"condition": "none of the drawn points is a given point",
                      "passed": not (drawn & given), "produced": len(drawn & given)})
    if "max_extra" in rules:
        wanted = len(task["requirement"].get("must_contain", ()))
        lines.append({"condition": f"at most {rules['max_extra']} points beyond the ones asked for",
                      "passed": len(points)-wanted <= rules["max_extra"],
                      "produced": len(points)-wanted})
    lines.append({"condition": "every stated condition of the requirement holds",
                  "passed": verification["passed"],
                  "produced": f"{verification.get('progress')}/{verification.get('of')}"})
    return {"passed": all(line["passed"] for line in lines), "lines": lines}


# ---------------------------------------------------------------------------
# Drawing, including the states on the way
# ---------------------------------------------------------------------------

PAPER = (F(-4), F(-4), F(12), F(8))
RADIUS = F(1, 12)


def draw(name, points, output, *, pixels_per_unit=80):
    marks = [((0, index), dp.exact(point)) for index, point in enumerate(points)]
    svg = ink.write_svg(output/f"{name}.svg", marks, RADIUS, PAPER,
                        pixels_per_unit=pixels_per_unit)
    png = ink.write_png(output/f"{name}.png", marks, RADIUS, PAPER,
                        pixels_per_unit=pixels_per_unit)
    return {"image": name, "dots": len(marks), "svg": svg["path"], "png": png["path"],
            "svg_check": ink.check_svg_is_one_radius_black_circles(output/f"{name}.svg")}


def states(program, inputs, depth, table, rules):
    """The run at each depth: a picture of the way there, and each one re-runnable."""
    rows = []
    for step in range(1, depth+1):
        points, counter = dp.run(program, inputs, step, table=table, rules=rules)
        rows.append({"depth": step, "points": [[str(v) for v in p] for p in points],
                     "primitive_applications": counter["primitive_applications"],
                     "rerun": {"program": program, "inputs": {k: [str(v) for v in value]
                                                              for k, value in inputs.items()},
                               "depth": step}})
    return rows


# ---------------------------------------------------------------------------
# One task
# ---------------------------------------------------------------------------

def attempt(task, *, record, update, output, levels, node_budget, draw_images=True):
    table = dp.operators(None, experience.macros_of(record) if update else ())
    rules = experience.rules_of(record) if update else {}
    order = experience.operator_order(record) if update else {}
    counter = Counter()
    began = time.perf_counter()
    result = dp.synthesise_for(task["requirement"], task["inputs"], table=table, rules=rules,
                               levels=levels, node_budget=node_budget, counter=counter,
                               order=order)
    seconds = time.perf_counter()-began
    row = {"task": task["name"], "directive": task["directive"],
           "assumptions": task["assumptions"],
           "formal_requirement": task["requirement"],
           "formal_requirement_written_by": "a person, beside the directive; no natural language "
                                            "was read by the system",
           "inputs": {k: [str(v) for v in value] for k, value in task["inputs"].items()},
           "scoring_fixed_in_advance": task["scoring"],
           "solved": result["solved"], "seconds": seconds,
           "costs": result.get("counter", dict(counter)),
           "experience_offered": {"macros": len(table)-len(dp.FAMILIES), "rules": len(rules),
                                  "order": bool(order)}}
    if not result["solved"]:
        row.update(stopped_at=result.get("stopped_at"), reason=result.get("reason"),
                   attempts=result.get("attempts"))
        experience.remember(record, task=task["name"], program=None, macro=None,
                            costs=row["costs"], solved=False, reason=row["reason"])
        return row, None
    program = result["program"]
    depth = task["requirement"].get("depth", 3)
    all_rules = dict(rules, **{program["name"]: program})
    points, _ = dp.run(program, task["inputs"], depth, table=table, rules=all_rules)
    row.update(program=program, closed_by=result.get("closed_by"),
               chosen_operators=sorted({s["op"] for s in program["body"] if "let" in s}),
               shared_variables=sorted({a for c in program.get("calls", ()) for a in c["args"]}),
               calls=program.get("calls", []),
               verification=result["verification"],
               score=score(task, program, result["verification"], points),
               used_macros=sorted({s["op"] for s in program["body"]
                                   if "let" in s and s["op"].startswith("macro:")}),
               used_rules=sorted({c["rule"] for c in program.get("calls", ())
                                  if c["rule"].startswith("rule:")}),
               states=states(program, task["inputs"], depth, table, all_rules))
    if draw_images:
        images = [draw(f"{task['name']}-final", points, output)]
        for state in row["states"][:-1]:
            partial, _ = dp.run(program, task["inputs"], state["depth"], table=table,
                                rules=all_rules)
            images.append(draw(f"{task['name']}-depth{state['depth']}", partial, output))
        row["images"] = images
    experience.note_use(record, macros=row["used_macros"], rules=row["used_rules"])
    experience.remember(record, task=task["name"], program=program,
                        macro=dp.macro_from(program), costs=row["costs"], solved=True)
    return row, program


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--levels", type=int, default=2)
    parser.add_argument("--node-budget", type=int, default=2500)
    parser.add_argument("--experience", default=None,
                        help="where the record of earlier rounds lives")
    parser.add_argument("--update", action="store_true",
                        help="let the search read what earlier rounds left")
    arguments = parser.parse_args()
    output = Path(arguments.output)
    output.mkdir(parents=True, exist_ok=True)
    store = Path(arguments.experience) if arguments.experience else output/"experience.json"
    record = experience.load(store)
    started = time.perf_counter()

    report = {"environment": {
        "sha": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True).stdout.strip(),
        "python": sys.version.split()[0], "platform": platform.platform()},
        "geometric_core": {k: sorted(v) if isinstance(v, dict) else v
                           for k, v in dp.geometric_core().items()},
        "protocol": {
            "directive": "Japanese prose, written by a person",
            "formal_requirement": "written by a person beside it; nothing reads natural language",
            "search": "geometry_drawing_program.synthesise_for, one search for every task",
            "no_solver_per_picture": "the tasks differ in inputs, shared variables, what repeats "
                                     "and which conditions must hold, not in code",
            "experience_read": bool(arguments.update),
            "experience_store": str(store)},
        "experience_before": experience.summary(record),
        "rows": []}
    say(f"experience before: {json.dumps(report['experience_before'])[:160]}")

    for task in tasks():
        row, _ = attempt(task, record=record, update=arguments.update, output=output,
                         levels=arguments.levels, node_budget=arguments.node_budget)
        report["rows"].append(row)
        mark = "solved" if row["solved"] else f"stopped at {row.get('stopped_at')}"
        extra = ""
        if row["solved"]:
            extra = (f" score={row['score']['passed']} nodes={row['costs'].get('nodes')}"
                     f" macros={row['used_macros']} rules={row['used_rules']}")
        say(f"   {task['name']:24s} {mark}{extra}")

    report["experience_after"] = experience.summary(record)
    report["experience_path"] = experience.save(record, store)
    report["summary"] = {
        "tasks": len(report["rows"]),
        "solved": sum(1 for r in report["rows"] if r["solved"]),
        "scored": sum(1 for r in report["rows"] if r.get("score", {}).get("passed")),
        "nodes": sum(r["costs"].get("nodes", 0) for r in report["rows"]),
        "programs_checked": sum(r["costs"].get("programs_checked", 0) for r in report["rows"]),
        "primitive_applications": sum(r["costs"].get("primitive_applications", 0)
                                      for r in report["rows"]),
        "seconds": sum(r["seconds"] for r in report["rows"]),
        "tasks_using_a_macro": sum(1 for r in report["rows"] if r.get("used_macros")),
        "tasks_using_a_stored_rule": sum(1 for r in report["rows"] if r.get("used_rules")),
        "distinct_programs": len({experience.program_key(r["program"])
                                  for r in report["rows"] if r.get("program")})}
    report["total_seconds"] = time.perf_counter()-started
    (output/"result.json").write_text(json.dumps(report, indent=1, default=str)+"\n",
                                      encoding="utf-8")
    print(json.dumps({"summary": report["summary"],
                      "experience_before": report["experience_before"],
                      "experience_after": report["experience_after"],
                      "rows": [{k: r.get(k) for k in ("task", "solved", "stopped_at", "reason")}
                               for r in report["rows"]]}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
