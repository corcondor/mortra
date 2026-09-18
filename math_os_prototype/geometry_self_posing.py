"""Posing geometry tasks from constructions that were actually carried out.

A task is not invented as a sentence. It is produced in the order the request
asks for:

    1. a non-degenerate input configuration is sampled;
    2. primitive operations are composed into a construction and executed
       exactly at rational coordinates;
    3. relations that hold of the constructed point are decided exactly, with
       the prerequisites that `atom_holds` already requires;
    4. the intermediate points and the construction are hidden, and only the
       input configuration and the goal relations are published;
    5. the solver is handed the published part alone.

Everything that decides whether a posed task is usable is a function that
already exists: `rdsl.execute_primitive` runs the construction,
`rdsl.atom_holds` decides a relation strictly, `rdsl._generic_polynomial`
detects a relation that holds for every configuration, and
`cohort.rational_solutions` decides whether the published goals leave finitely
many candidates. A task is refused unless a rational non-input solution exists,
no input point already satisfies the goals, and the goals are not identically
true.
"""
from __future__ import annotations

from collections import Counter
from itertools import combinations
import random

import sympy as sp

from math_os_prototype import geometry_relational_cohort as cohort
from math_os_prototype import geometry_relational_dsl as rdsl
from math_os_prototype.representation_progress import digest

GOAL_PREDICATES = ("coll", "perp", "para", "cong", "cyclic", "midp", "eqangle")
INPUT_NAMES = ("a", "b", "c", "d", "e", "f")
FAMILIES = tuple(rdsl.primitive_contracts())


def sample_points(rng, count=4):
    """A configuration with no repeated point and no collinear triple.

    More points make a harder task family: a goal that mentions four or more of
    them cannot be retrieved from the library at all, because retrieval binds at
    most three fixed names, so the search has to compose the construction itself.
    """
    names = INPUT_NAMES[:count]
    for _ in range(10000):
        points = {n: [rng.randint(-9, 9), rng.randint(-9, 9)] for n in names}
        values = list(points.values())
        if len({tuple(p) for p in values}) != len(values):
            continue
        if any((b[0]-a[0])*(c[1]-a[1]) == (b[1]-a[1])*(c[0]-a[0]) for a, b, c in combinations(values, 3)):
            continue
        return points
    raise ValueError("point sampler exhausted its rejection bound")


def build_construction(rng, points, depth, *, attempts=60):
    """Compose `depth` primitive steps, executing each one exactly; returns steps and coordinates."""
    coordinates = {n: tuple(sp.Integer(v) for v in xy) for n, xy in points.items()}
    available = list(points)
    steps = []
    for index in range(depth):
        for _ in range(attempts):
            family = rng.choice(FAMILIES)
            arity = len(rdsl.primitive_contracts()[family]["params"])
            if len(available) < arity:
                continue
            arguments = [rng.choice(available) for _ in range(arity)]
            if len(set(arguments)) < arity:
                continue
            if rdsl.binding_returns_input(family, arguments):
                continue
            xy, reason = rdsl.execute_primitive(family, arguments, coordinates)
            if xy is None or any(xy == coordinates[n] for n in coordinates):
                continue
            name = f"h{index}"
            coordinates[name] = xy
            available.append(name)
            steps.append({"out": name, "prim": family, "args": list(arguments)})
            break
        else:
            return None, None
    return steps, coordinates


def _argument_tuples(rng, predicate, names, hidden, *, samples):
    """Argument tuples for a predicate that mention the hidden point, sampled within a bound."""
    arity = rdsl.PREDICATE_ARITIES[predicate]
    pool = list(names)
    seen = set()
    for _ in range(samples):
        arguments = [rng.choice(pool+[hidden]) for _ in range(arity)]
        if hidden not in arguments:
            arguments[rng.randrange(arity)] = hidden
        key = rdsl.canonical_atom(predicate, tuple(arguments))
        if key in seen:
            continue
        seen.add(key)
        yield tuple(arguments)


def holding_relations(rng, coordinates, hidden, input_names, *, samples=24, stats=None):
    """Relations that hold exactly of the constructed point and are not true of every configuration."""
    found = []
    for predicate in GOAL_PREDICATES:
        # an eight-place relation has far more argument tuples than the others and each
        # test is far more expensive, so it is sampled less, not skipped
        budget = max(4, samples//4) if rdsl.PREDICATE_ARITIES[predicate] > 4 else samples
        for arguments in _argument_tuples(rng, predicate, input_names, hidden, samples=budget):
            if stats is not None:
                stats["relation_tests"] += 1
            try:
                if rdsl._generic_polynomial(predicate, arguments) == 0:
                    if stats is not None:
                        stats["identically_true"] += 1
                    continue
                if rdsl.atom_holds(predicate, arguments, coordinates):
                    found.append((predicate, arguments))
            except (ValueError, KeyError, ZeroDivisionError):
                if stats is not None:
                    stats["relation_test_refused"] += 1
    return found


def structure_signature(steps, goals):
    """What makes two tasks the same problem: the construction shape and the goal shape.

    Point names and coordinates are deliberately not part of it, so that a task
    that only renames or moves the configuration has the same signature.
    """
    families = [step["prim"] for step in steps]
    roles = []
    for predicate, arguments in goals:
        pattern, index = [], {}
        for argument in arguments:
            if argument == "u":
                pattern.append("u")
            else:
                pattern.append(index.setdefault(argument, f"x{len(index)}"))
        roles.append(rdsl.canonical_atom(predicate, tuple(pattern)))
    return digest([families, sorted(roles)])


def finite_candidates(goals, points, stats=None):
    """Candidates for the unknown, or None when no pair of the goals pins it down to finitely many.

    `cohort.rational_solutions` solves two equations. When more conditions are
    asked at once, a pair that already leaves finitely many candidates is enough:
    the conjunction of all of them can only leave fewer. The returned candidates
    are then the ones that satisfy every goal.
    """
    for first in range(len(goals)):
        for second in range(first+1, len(goals)):
            try:
                solutions = cohort.rational_solutions([goals[first], goals[second]], points)
            except (ValueError, KeyError, ZeroDivisionError, sp.PolynomialError):
                if stats is not None:
                    stats["solution_set_refused"] += 1
                continue
            if solutions is None:
                continue
            coordinates = {n: tuple(sp.Integer(v) for v in xy) for n, xy in points.items()}
            surviving = []
            for candidate in solutions:
                local = dict(coordinates, u=tuple(candidate))
                if all(rdsl.atom_holds(g["predicate"], tuple(g["points"]), local) for g in goals):
                    surviving.append(tuple(candidate))
            return surviving
    return None


def one_step_reachable(task, *, stats=None):
    """Whether a single primitive applied to the input points already satisfies every goal.

    This is the cheapest statement of 'no composition is needed': every family is
    applied to every tuple of input points, exactly, and the goals are decided on
    the result. A task that passes it is a one-step task however it was posed.
    """
    points = task["points"]
    coordinates = {n: tuple(sp.Integer(v) for v in xy) for n, xy in points.items()}
    names = list(points)
    for family in FAMILIES:
        parameters = rdsl.primitive_contracts()[family]["params"]
        for arguments in _tuples(names, len(parameters)):
            if rdsl.binding_returns_input(family, list(arguments)):
                continue
            xy, _ = rdsl.execute_primitive(family, list(arguments), coordinates)
            if stats is not None:
                stats["one_step_executions"] += 1
            if xy is None or xy in set(coordinates.values()):
                continue
            local = dict(coordinates, __probe=xy)
            if all(rdsl.atom_holds(goal["predicate"],
                                   tuple("__probe" if a == "u" else a for a in goal["points"]), local)
                   for goal in task["goals"]):
                return True
    return False


def _tuples(names, arity):
    from itertools import permutations
    return permutations(names, arity) if arity <= len(names) else ()


def pose(rng, *, depth=2, goal_count=2, samples=24, stats=None, points=None, require_multistep=False):
    """One posed task, or None when the attempt is refused.

    The returned record separates what the solver may see (`task`) from what it
    may not (`hidden`): the construction, the intermediate points and the
    constructed solution.
    """
    stats = stats if stats is not None else Counter()
    points = points or sample_points(rng)
    steps, coordinates = build_construction(rng, points, depth)
    if steps is None:
        stats["construction_failed"] += 1
        return None
    hidden = steps[-1]["out"]
    relations = holding_relations(rng, coordinates, hidden, list(points), samples=samples, stats=stats)
    if len(relations) < goal_count:
        stats["too_few_relations"] += 1
        return None
    rng.shuffle(relations)
    for chosen in combinations(relations[:7], goal_count):
        goals = [{"predicate": p, "points": [("u" if a == hidden else a) for a in args]} for p, args in chosen]
        keys = {rdsl.canonical_atom(g["predicate"], tuple(g["points"])) for g in goals}
        if len(keys) != goal_count:
            stats["duplicate_atoms"] += 1
            continue
        if any(all(rdsl.atom_holds(g["predicate"], tuple(name if a == "u" else a for a in g["points"]), coordinates)
                   for g in goals) for name in points):
            stats["input_point_satisfies_goal"] += 1
            continue
        solutions = finite_candidates(goals, points, stats)
        if solutions is None:
            stats["not_finite"] += 1
            continue
        constructed = tuple(sp.Rational(v) for v in coordinates[hidden])
        if constructed not in {tuple(s) for s in solutions}:
            stats["constructed_point_not_recovered"] += 1
            continue
        posed = {"points": points, "goals": goals}
        # whether a single primitive from the inputs already meets every goal: a
        # structural statement about the task, not about any solver's budget
        one_step = one_step_reachable(posed, stats=stats)
        if one_step:
            stats["one_step_reachable"] += 1
            if require_multistep:
                continue
        else:
            stats["needs_composition"] += 1
        stats["posed"] += 1
        return {"task": posed, "one_step_reachable": one_step,
                "hidden": {"steps": steps, "solution": [str(v) for v in constructed],
                           "depth": depth, "families": [s["prim"] for s in steps],
                           "candidate_count": len(solutions)},
                "signature": structure_signature(steps, [(g["predicate"], tuple(g["points"])) for g in goals])}
    stats["no_usable_goal_pair"] += 1
    return None


def pose_many(seed, count, *, depth=2, goal_count=2, attempts=4000, samples=24, exclude=(),
              require_multistep=False):
    """A batch of posed tasks with distinct structures, and why the refused attempts were refused."""
    rng = random.Random(seed)
    stats, posed, signatures = Counter(), [], set(exclude)
    for _ in range(attempts):
        if len(posed) == count:
            break
        record = pose(rng, depth=depth, goal_count=goal_count, samples=samples, stats=stats,
                      require_multistep=require_multistep)
        if record is None:
            continue
        if record["signature"] in signatures:
            stats["duplicate_structure"] += 1
            continue
        signatures.add(record["signature"])
        posed.append(record)
    return {"seed": seed, "requested": count, "posed": posed, "rejections": dict(stats),
            "signatures": sorted(signatures-set(exclude))}


def rename_and_move(record, rng):
    """The same construction shape at a different configuration, for the memorisation probe."""
    mapping = dict(zip(INPUT_NAMES, rng.sample(INPUT_NAMES, len(INPUT_NAMES)), strict=True))
    for _ in range(200):
        points = sample_points(rng)
        renamed_points = {mapping[name]: points[name] for name in points}
        steps = [{"out": step["out"], "prim": step["prim"],
                  "args": [mapping.get(a, a) for a in step["args"]]} for step in record["hidden"]["steps"]]
        coordinates = {n: tuple(sp.Integer(v) for v in xy) for n, xy in renamed_points.items()}
        try:
            for step in steps:
                xy, reason = rdsl.execute_primitive(step["prim"], step["args"], coordinates)
                if xy is None:
                    raise ValueError(reason)
                coordinates[step["out"]] = xy
        except ValueError:
            continue
        hidden = steps[-1]["out"]
        goals = [{"predicate": g["predicate"],
                  "points": [("u" if a == "u" else mapping[a]) for a in g["points"]]}
                 for g in record["task"]["goals"]]
        if not all(rdsl.atom_holds(g["predicate"], tuple(hidden if a == "u" else a for a in g["points"]),
                                   coordinates) for g in goals):
            continue
        if any(all(rdsl.atom_holds(g["predicate"], tuple(name if a == "u" else a for a in g["points"]),
                                   coordinates) for g in goals) for name in renamed_points):
            continue
        solutions = finite_candidates(goals, renamed_points)
        if not solutions:
            continue
        return {"task": {"points": renamed_points, "goals": goals},
                "hidden": {"steps": steps, "solution": [str(v) for v in coordinates[hidden]],
                           "depth": record["hidden"]["depth"],
                           "families": [s["prim"] for s in steps], "candidate_count": len(solutions)},
                "signature": record["signature"], "probe": "renamed_and_moved"}
    return None


# ---------------------------------------------------------------------------
# A ladder: a task whose construction extends another task's construction
# ---------------------------------------------------------------------------

def choose_goals(rng, coordinates, hidden, points, *, goal_count, samples=24, stats=None,
                 prefer=("cyclic", "cong", "eqangle", "perp"), minimum_distinct_points=0):
    """Goal relations for one hidden point, or None when no usable set is found.

    Relations that hold for every configuration are discarded, a set that an input
    point already satisfies is discarded, and the set must leave finitely many
    candidates with the constructed point among them. Sets that mention a circle
    or an angle condition are tried first, because those were the weak ones.
    """
    stats = stats if stats is not None else Counter()
    relations = holding_relations(rng, coordinates, hidden, list(points), samples=samples, stats=stats)
    if len(relations) < goal_count:
        stats["too_few_relations"] += 1
        return None
    rng.shuffle(relations)
    interesting = [r for r in relations if r[0] in prefer]
    ordered = interesting+[r for r in relations if r not in interesting]
    for chosen in combinations(ordered[:7], goal_count):
        if len({p for p, _ in chosen}) < 2:
            stats["single_predicate_goal"] += 1
            continue
        goals = [{"predicate": p, "points": [("u" if a == hidden else a) for a in args]} for p, args in chosen]
        mentioned = {a for g in goals for a in g["points"] if a != "u"}
        if len(mentioned) < minimum_distinct_points:
            stats["too_few_distinct_points"] += 1
            continue
        if len({rdsl.canonical_atom(g["predicate"], tuple(g["points"])) for g in goals}) != goal_count:
            stats["duplicate_atoms"] += 1
            continue
        if any(all(rdsl.atom_holds(g["predicate"], tuple(name if a == "u" else a for a in g["points"]),
                                   coordinates) for g in goals) for name in points):
            stats["input_point_satisfies_goal"] += 1
            continue
        solutions = finite_candidates(goals, points, stats)
        if solutions is None:
            stats["not_finite"] += 1
            continue
        constructed = tuple(sp.Rational(v) for v in coordinates[hidden])
        if constructed not in {tuple(s) for s in solutions}:
            stats["constructed_point_not_recovered"] += 1
            continue
        return {"goals": goals, "candidates": len(solutions), "solution": [str(v) for v in constructed]}
    stats["no_usable_goal_set"] += 1
    return None


def extend_construction(rng, coordinates, steps, extra, *, attempts=80):
    """Continue a construction, each new step consuming the point the previous one made.

    That is what makes the earlier part necessary: the extension cannot be
    rebuilt without the point the base construction produced.
    """
    coordinates = dict(coordinates)
    steps = [dict(step) for step in steps]
    available = [name for name in coordinates]
    for index in range(extra):
        previous = steps[-1]["out"]
        for _ in range(attempts):
            family = rng.choice(FAMILIES)
            parameters = rdsl.primitive_contracts()[family]["params"]
            if len(available) < len(parameters):
                continue
            arguments = [previous]+[rng.choice(available) for _ in range(len(parameters)-1)]
            rng.shuffle(arguments)
            if len(set(arguments)) < len(parameters) or previous not in arguments:
                continue
            if rdsl.binding_returns_input(family, arguments):
                continue
            xy, _ = rdsl.execute_primitive(family, arguments, coordinates)
            if xy is None or any(xy == value for value in coordinates.values()):
                continue
            name = f"k{index}"
            coordinates[name] = xy
            available.append(name)
            steps.append({"out": name, "prim": family, "args": list(arguments)})
            break
        else:
            return None, None
    return steps, coordinates


def pose_ladder(rng, *, base_depth=2, extra_steps=1, goal_count=3, samples=24, stats=None,
                input_points=4, minimum_distinct_points=0):
    """Two tasks from one construction: the base, and the base extended.

    The extended construction contains the base construction as a prefix and uses
    the point it produced, so an operation acquired from the base is exactly the
    block the extended task needs. Both are published the same way: the input
    configuration and the goal relations, with everything else hidden.
    """
    stats = stats if stats is not None else Counter()
    points = sample_points(rng, input_points)
    steps, coordinates = build_construction(rng, points, base_depth)
    if steps is None:
        stats["construction_failed"] += 1
        return None
    base = choose_goals(rng, coordinates, steps[-1]["out"], points, goal_count=goal_count,
                        samples=samples, stats=stats, minimum_distinct_points=minimum_distinct_points)
    if base is None:
        return None
    extended_steps, extended_coordinates = extend_construction(rng, coordinates, steps, extra_steps)
    if extended_steps is None:
        stats["extension_failed"] += 1
        return None
    top = choose_goals(rng, extended_coordinates, extended_steps[-1]["out"], points,
                       goal_count=goal_count, samples=samples, stats=stats,
                       minimum_distinct_points=minimum_distinct_points)
    if top is None:
        return None
    stats["ladders"] += 1
    ladder = digest([[s["prim"] for s in extended_steps], sorted(
        rdsl.canonical_atom(g["predicate"], tuple(g["points"])) for g in top["goals"])])
    def record(goal_record, construction, level):
        task = {"points": points, "goals": goal_record["goals"]}
        return {"task": task, "level": level, "ladder": ladder,
                "hidden": {"steps": construction, "solution": goal_record["solution"],
                           "depth": len(construction),
                           "families": [s["prim"] for s in construction],
                           "candidate_count": goal_record["candidates"]},
                "signature": structure_signature(construction,
                                                 [(g["predicate"], tuple(g["points"]))
                                                  for g in goal_record["goals"]])}
    return {"base": record(base, steps, "base"), "top": record(top, extended_steps, "top")}


def pose_ladders(seed, count, *, base_depth=2, extra_steps=1, goal_count=3, attempts=3000, samples=24,
                 input_points=4, minimum_distinct_points=0):
    """A batch of ladders with distinct extended structures."""
    rng = random.Random(seed)
    stats, ladders, seen = Counter(), [], set()
    for _ in range(attempts):
        if len(ladders) == count:
            break
        record = pose_ladder(rng, base_depth=base_depth, extra_steps=extra_steps,
                             goal_count=goal_count, samples=samples, stats=stats,
                             input_points=input_points,
                             minimum_distinct_points=minimum_distinct_points)
        if record is None:
            continue
        if record["top"]["signature"] in seen or record["base"]["signature"] in seen:
            stats["duplicate_structure"] += 1
            continue
        seen.add(record["top"]["signature"])
        seen.add(record["base"]["signature"])
        ladders.append(record)
    return {"seed": seed, "ladders": ladders, "rejections": dict(stats)}


# ---------------------------------------------------------------------------
# Reading a posed task
# ---------------------------------------------------------------------------

JAPANESE = {
    "coll": "{0}, {1}, {2} は同一直線上にある",
    "perp": "直線{0}{1} と 直線{2}{3} は直交する",
    "para": "直線{0}{1} と 直線{2}{3} は平行である",
    "cong": "線分{0}{1} と 線分{2}{3} の長さが等しい",
    "cyclic": "{0}, {1}, {2}, {3} は同一円周上にある",
    "midp": "{0} は 線分{1}{2} の中点である",
    "eqangle": "角({0}{1}, {2}{3}) と 角({4}{5}, {6}{7}) が等しい",
}

ENGLISH = {
    "coll": "{0}, {1} and {2} are collinear",
    "perp": "line {0}{1} is perpendicular to line {2}{3}",
    "para": "line {0}{1} is parallel to line {2}{3}",
    "cong": "segment {0}{1} has the length of segment {2}{3}",
    "cyclic": "{0}, {1}, {2} and {3} lie on one circle",
    "midp": "{0} is the midpoint of {1}{2}",
    "eqangle": "the angle between {0}{1} and {2}{3} equals the angle between {4}{5} and {6}{7}",
}


def render(task, *, language="japanese"):
    """The posed task as a sentence. Nothing of the construction appears in it."""
    table = JAPANESE if language == "japanese" else ENGLISH
    points = "、".join(f"{name}({x}, {y})" for name, (x, y) in task["points"].items()) \
        if language == "japanese" else ", ".join(f"{name}({x}, {y})" for name, (x, y) in task["points"].items())
    conditions = [table[goal["predicate"]].format(*goal["points"]) for goal in task["goals"]]
    if language == "japanese":
        return (f"点 {points} が与えられている。"
                f"次をすべて満たす点 u を作図せよ：" + "、かつ".join(conditions) + "。")
    return (f"Given {points}, construct a point u such that "
            + ", and ".join(conditions) + ".")
