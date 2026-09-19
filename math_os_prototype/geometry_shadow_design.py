"""Asking for a shadow and getting a construction back.

The forward direction is settled: a point light, a segment occluder and a
receiving line give an interval, and `geometry_ink` decides membership exactly.
This module runs it backwards — a wanted shadow is handed to the search the
repository already has, and what comes back is a construction program over the
input points.

Two things are written here and nothing else. The first is one general rule that
turns a wanted shadow into relations the fragment can already state: an end of
the shadow on the receiving line is where the boundary ray through the
corresponding end of the occluder meets that line, so

    X is an end of the shadow  <->  coll(L, P, X) and P on the placement line
                                    and P strictly between L and X

with P the unknown. That is the same geometry as the forward direction, stated
as a goal instead of as a test, and it is the only translation: every task uses
it.

The second is the connection the search was missing. `RelationalSynthesis`
solves for one unknown point; a wanted shadow names two, and they are not
independent of each other — they share the light, the placement line and, in the
later tasks, each other. `solve_system` hands the unknowns to the existing
search one at a time, in an order the task gives, with every point solved so far
added to the inputs of the next, and composes the terms that come back into a
single program. No search is written here: `geometry_self_improvement.solve` does
the searching, and this decides what to ask it and how to keep the answers tied
together.
"""
from __future__ import annotations

from collections import Counter
from fractions import Fraction
import time

from math_os_prototype import geometry_acquisition as acq
from math_os_prototype import geometry_ink as ink
from math_os_prototype import geometry_relational_dsl as rdsl
from math_os_prototype import geometry_self_improvement as loop

# ---------------------------------------------------------------------------
# The forward direction, from the drawing side
# ---------------------------------------------------------------------------

def shadow_end(light, occluder_end, receiving, coordinates=None):
    """Where the boundary ray through one end of the occluder meets the receiving line."""
    names = dict(coordinates or {})
    names.update({"__l": light, "__p": occluder_end, "__w1": receiving[0], "__w2": receiving[1]})
    meeting, reason = rdsl.execute_primitive("intersection_ll", ["__l", "__p", "__w1", "__w2"],
                                             names)
    return meeting, reason


def shadow_interval(light, occluder, receiving):
    """The two ends the shadow of a segment has on a receiving line."""
    first, reason = shadow_end(light, occluder[0], receiving)
    if first is None:
        return None, reason
    second, reason = shadow_end(light, occluder[1], receiving)
    if second is None:
        return None, reason
    return (first, second), None


# ---------------------------------------------------------------------------
# The one translation: a wanted shadow becomes relations
# ---------------------------------------------------------------------------

def boundary_relation(light, placement, target, unknown):
    """The relations an unknown occluder end must satisfy for the shadow to reach `target`.

    `coll(k1, k2, P)` puts it on the line it may be placed on, `coll(L, T, P)`
    puts it on the ray that carries the wanted end, and the order — the occluder
    between the light and the screen — is an inequality, which this fragment
    cannot state and which is therefore returned separately, to be decided on the
    instance rather than certified.
    """
    k1, k2 = placement
    return {"goals": [{"predicate": "coll", "points": [k1, k2, unknown]},
                      {"predicate": "coll", "points": [light, target, unknown]}],
            "ordering": ("strictly_between", unknown, light, target)}


def requirement_relations(requirement):
    """Every unknown of a requirement, with its goals, in the order it must be solved."""
    unknowns = []
    for wanted in requirement["wanted"]:
        if wanted["kind"] == "occluder_end":
            relation = boundary_relation(requirement["light"], requirement["placement"],
                                         wanted["target"], wanted["name"])
        elif wanted["kind"] == "light":
            # the light is the point both boundary rays pass through: each ray is
            # named by an end of the occluder and the end of the shadow it carries
            relation = {"goals": [{"predicate": "coll", "points": [pair[0], pair[1], wanted["name"]]}
                                  for pair in wanted["rays"]],
                        "ordering": None}
        elif wanted["kind"] == "relation":
            relation = {"goals": list(wanted["goals"]), "ordering": wanted.get("ordering")}
        else:
            raise ValueError(f"unknown kind of wanted point: {wanted['kind']}")
        unknowns.append({"name": wanted["name"], **relation})
    return unknowns


# ---------------------------------------------------------------------------
# The connection: several unknowns, solved one at a time, kept tied together
# ---------------------------------------------------------------------------

def solve_system(requirement, *, library=None, policy=None, applications=40):
    """Solve for each unknown with the existing search, sharing the inputs and the answers.

    The order is the requirement's own. Each unknown is posed as a task whose
    points are the given ones together with everything solved so far, so a later
    unknown may depend on an earlier one and the dependency is carried rather
    than guessed. Nothing is hidden from the search that a solver would be given:
    the goals are relations, and the answer is checked afterwards.
    """
    policy = dict(policy or loop.START_POLICY)
    # the solver names its unknown "u"; a given point of that name would silently
    # merge with it and turn the goals into different, easier ones
    clashing = sorted({"u"} & set(requirement["points"]))
    if clashing:
        raise ValueError(f"a given point is named {clashing}, which is the name the solver gives "
                         f"its unknown; rename it before posing the requirement")
    points = {name: [str(v) for v in value] for name, value in requirement["points"].items()}
    coordinates = {name: tuple(Fraction(v) for v in value)
                   for name, value in requirement["points"].items()}
    unknowns = requirement_relations(requirement)
    solved, rows, terms = {}, [], {}
    solutions, tasks = {}, {}
    costs = Counter()
    for unknown in unknowns:
        task = {"points": dict(points),
                "goals": [{"predicate": goal["predicate"],
                           "points": ["u" if p == unknown["name"] else p for p in goal["points"]]}
                          for goal in unknown["goals"]]}
        began = time.perf_counter()
        reused_before = 0 if library is None else library.costs.get("acquired_certificates_reused", 0)
        row = loop.solve(task, library=library, policy=policy, applications=applications)
        reused_after = 0 if library is None else library.costs.get("acquired_certificates_reused", 0)
        measurement = loop.measurements(row)
        measurement["seconds"] = time.perf_counter()-began
        used = acq.used_acquired_operation(row["solution"], library) \
            if (row.get("solved") and library is not None) else []
        rows.append({"unknown": unknown["name"], "goals": task["goals"],
                     "measurement": measurement,
                     "via": (row.get("solution") or {}).get("via"),
                     "acquired_certificates_consulted_during_this_search":
                         reused_after-reused_before,
                     "acquired_operations_in_the_answer": [entry["index"] for entry in used]})
        for key, value in row["costs"].items():
            costs[key] += value
        if not row["solved"]:
            return {"solved": False, "stopped_at": unknown["name"],
                    "stop_reason": row["stop_reason"], "rows": rows, "costs": dict(costs)}
        value = row["solution"]["coordinates"] if "coordinates" in row["solution"] else None
        term = row["solution"]["term"]
        replayed, _ = _replay(term, coordinates)
        solved[unknown["name"]] = replayed
        coordinates[unknown["name"]] = replayed
        points[unknown["name"]] = [str(v) for v in replayed]
        terms[unknown["name"]] = term
        solutions[unknown["name"]] = row["solution"]
        tasks[unknown["name"]] = task
        if unknown["ordering"]:
            kind, who, first, second = unknown["ordering"]
            held = ink.strictly_between(coordinates[who], coordinates[first], coordinates[second])
            rows[-1]["ordering"] = {"condition": f"{kind}({who}, {first}, {second})", "holds": held}
            if not held:
                return {"solved": False, "stopped_at": unknown["name"],
                        "stop_reason": "the order condition failed on the instance",
                        "rows": rows, "costs": dict(costs)}
    return {"solved": True, "points": {k: [str(v) for v in value] for k, value in solved.items()},
            "terms": terms, "rows": rows, "costs": dict(costs),
            "solutions": solutions, "tasks": tasks}


def _replay(term, coordinates):
    """Evaluate a solution term at the given coordinates, with the fragment's primitives."""
    if term.get("op") == "var":
        return coordinates[term["name"]], None
    values = dict(coordinates)
    arguments = []
    for index, child in enumerate(term["args"]):
        value, reason = _replay(child, coordinates)
        if value is None:
            return None, reason
        name = f"__arg{index}_{len(values)}"
        values[name] = value
        arguments.append(name)
    return rdsl.execute_primitive(term["op"], arguments, values)


def term_steps(term, steps, names, counter):
    """Flatten a solution term into primitive steps over named inputs.

    `names` carries the unknowns already emitted: a later unknown that mentions an
    earlier one must reach that earlier one's step, not a name the program has no
    input for.
    """
    if term.get("op") == "var":
        return names.get(term["name"], term["name"])
    arguments = [term_steps(child, steps, names, counter) for child in term["args"]]
    counter[0] += 1
    out = f"s{counter[0]}"
    steps.append({"out": out, "prim": term["op"], "args": arguments})
    return out


def program_of(requirement, solution):
    """The answer as something that can be run again: inputs, steps, outputs."""
    steps, counter = [], [0]
    outputs, emitted = {}, {}
    for name, term in solution["terms"].items():
        out = term_steps(term, steps, emitted, counter)
        outputs[name] = out
        emitted[name] = out
    return {"params": sorted(requirement["points"]), "steps": steps, "outputs": outputs,
            "primitive_steps": len(steps)}


def run_program(program, points):
    """Execute a synthesised program at concrete coordinates."""
    coordinates = {name: tuple(Fraction(v) for v in value) for name, value in points.items()}
    for step in program["steps"]:
        xy, reason = rdsl.execute_primitive(step["prim"], step["args"], coordinates)
        if xy is None:
            return None, f"{step['prim']} refused: {reason}"
        coordinates[step["out"]] = xy
    return {name: coordinates[out] for name, out in program["outputs"].items()}, None


# ---------------------------------------------------------------------------
# Checking the answer against what was asked
# ---------------------------------------------------------------------------

def check_requirement(requirement, produced):
    """Recompute the shadow the synthesised configuration casts and compare it with the target."""
    coordinates = {name: tuple(Fraction(v) for v in value)
                   for name, value in requirement["points"].items()}
    coordinates.update(produced)
    checks = []
    for test in requirement["verify"]:
        if test["kind"] == "shadow_interval":
            light = coordinates[test["light"]]
            occluder = (coordinates[test["occluder"][0]], coordinates[test["occluder"][1]])
            receiving = (coordinates[test["receiving"][0]], coordinates[test["receiving"][1]])
            wanted = (coordinates[test["target"][0]], coordinates[test["target"][1]])
            interval, reason = shadow_interval(light, occluder, receiving)
            # the primitives hand back exact rationals of their own type; compare the
            # numbers, not the objects
            def exact(pair):
                return tuple(sorted((Fraction(p[0]), Fraction(p[1])) for p in pair))
            passed = interval is not None and exact(interval) == exact(wanted)
            checks.append({"check": "the shadow on the receiving line has the wanted ends",
                           "receiving": test["receiving"], "wanted": [str(v) for v in wanted[0]]
                           + [str(v) for v in wanted[1]],
                           "produced": None if interval is None
                           else [str(v) for v in interval[0]]+[str(v) for v in interval[1]],
                           "passed": passed, "reason": reason})
        elif test["kind"] == "on_line":
            point = coordinates[test["point"]]
            a, b = coordinates[test["line"][0]], coordinates[test["line"][1]]
            passed = rdsl.atom_holds("coll", (test["line"][0], test["line"][1], test["point"]),
                                     coordinates)
            checks.append({"check": f"{test['point']} lies on {test['line']}", "passed": passed})
        elif test["kind"] == "between":
            passed = ink.strictly_between(coordinates[test["point"]], coordinates[test["from"]],
                                          coordinates[test["to"]])
            checks.append({"check": f"{test['point']} is strictly between {test['from']} and "
                                    f"{test['to']}", "passed": passed,
                           "decided": "on the instance: an order condition is not a relation this "
                                      "fragment can certify"})
        else:
            raise ValueError(f"unknown check: {test['kind']}")
    return {"passed": all(c["passed"] for c in checks), "checks": checks}
