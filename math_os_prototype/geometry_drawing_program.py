"""Drawing programs as data: an execution language over the fixed geometric core.

The geometry does not change here. The seven primitives, the ten predicates and
their exact meanings are taken from the modules that define them and are checked
to be what they were. What changes is that the *assembly* — which construction to
apply, what to share, what to repeat, which points to keep — stops being Python
and becomes a value the search can build, run, check and rewrite.

The language, and it is deliberately small:

    let   x = op(args...)        a construction step: a primitive of the fragment,
                                 or an operation the library has acquired
    emit  x                      keep a point for the drawing
    call  rule(args...)          a bounded recursive call, one depth lower
    keep  x where relation       keep a point only when an existing relation holds

`let`, `emit`, `call` and `keep` are additions to the execution language, not to
the geometry: none of them is a new predicate, a new primitive or a new theorem,
and each of them is counted in the cost of a search that uses it. Recursion is
bounded by a depth that the caller supplies and that every call lowers, so every
program terminates and nothing here proves anything about unbounded repetition.

What a program is:

    {"name": ..., "params": [...], "body": [statements], "emit": [names],
     "calls": [{"rule": name, "args": [names]}]}

The body is evaluated once per call, the emitted names are collected, and each
call re-enters with the depth lowered. Running a program with a larger depth
gives more points from the same program; running it with different inputs gives a
different figure from the same program. Nothing is stored expanded: what is kept
is the rule, and points are produced when it is run.
"""
from __future__ import annotations

from collections import Counter
from fractions import Fraction
from itertools import combinations, permutations

from math_os_prototype import geometry_ink as ink
from math_os_prototype import geometry_relational_dsl as rdsl
from math_os_prototype.representation_progress import digest

FAMILIES = tuple(sorted(rdsl.primitive_contracts()))
ARITY = {family: len(rdsl.primitive_contracts()[family]["params"]) for family in FAMILIES}


def exact(point):
    """A point as a pair of Fractions.

    The primitives hand back exact rationals of their own type, which compare
    equal to a Fraction but need not hash like one. Every place that puts a point
    into a set or a dictionary key goes through here, or a point is silently not
    found where it is.
    """
    return (Fraction(point[0]), Fraction(point[1]))


class ProgramRefused(RuntimeError):
    """The program does not type, or a step of it is inapplicable where it was run."""


# ---------------------------------------------------------------------------
# What the geometric core is, so that a run can show it did not move
# ---------------------------------------------------------------------------

def geometric_core():
    """The primitives and predicates as the source defines them, for the record."""
    contracts = rdsl.primitive_contracts()
    return {"primitives": {family: {"params": list(contracts[family]["params"]),
                                    "post": [[p["atom"], list(p["args"])] for p in contracts[family]["post"]],
                                    "pre": [[p["atom"], list(p["args"])] for p in contracts[family]["pre"]]}
                           for family in FAMILIES},
            "predicates": dict(sorted(rdsl.PREDICATE_ARITIES.items()))}


# ---------------------------------------------------------------------------
# Operators: the fragment's primitives, and whatever the library has acquired
# ---------------------------------------------------------------------------

def operators(library=None, macros=None):
    """Everything a `let` may apply, with its arity.

    Three kinds, and the difference matters. A primitive is the fragment itself.
    An acquired operation is one the library certified: it carries guarantees that
    hold for every configuration. A macro is neither — it is a body that earlier
    searches found useful, kept so that a later search reaches the same point in
    one step instead of several. A macro guarantees nothing, and is never offered
    to the relational retrieval; it only shortens this enumeration, and is
    reported apart from what was certified.
    """
    table = {family: {"kind": "primitive", "arity": ARITY[family]} for family in FAMILIES}
    if library is not None:
        for index in sorted(getattr(library, "acquired", {})):
            program = library.programs[index]
            table[f"op:{index}"] = {"kind": "acquired", "arity": len(program["params"]),
                                    "program": program,
                                    "primitive_steps": len(program["steps"])}
    for macro in macros or ():
        table[macro["name"]] = {"kind": "macro", "arity": len(macro["params"]),
                                "program": macro, "primitive_steps": len(macro["steps"])}
    return table


def apply_operator(name, arguments, coordinates, table, counter):
    """One step, whether it is a primitive or an acquired operation."""
    entry = table.get(name)
    if entry is None:
        raise ProgramRefused(f"no such operator: {name}")
    if len(arguments) != entry["arity"]:
        raise ProgramRefused(f"{name} takes {entry['arity']} arguments, given {len(arguments)}")
    if entry["kind"] == "primitive":
        counter["primitive_applications"] += 1
        return rdsl.execute_primitive(name, list(arguments), coordinates, counter)
    counter[f"{entry['kind']}_calls"] += 1
    program = entry["program"]
    local = dict(zip(program["params"], arguments, strict=True))
    values = dict(coordinates)
    for index, step in enumerate(program["steps"]):
        names = [local[a] for a in step["args"]]
        counter["primitive_applications"] += 1
        xy, reason = rdsl.execute_primitive(step["prim"], names, values, counter)
        if xy is None:
            return None, f"{name}: {reason}"
        fresh = f"__{name}_{index}_{len(values)}"
        values[fresh] = xy
        local[step["out"]] = fresh
    return values[local[program["result"]]], None


# ---------------------------------------------------------------------------
# The interpreter: fixed, and the only thing that turns a program into points
# ---------------------------------------------------------------------------

def validate(program, table):
    """Types, arities and scope, before anything is executed."""
    seen = set(program["params"])
    for statement in program["body"]:
        if "let" in statement:
            entry = table.get(statement["op"])
            if entry is None:
                raise ProgramRefused(f"no such operator: {statement['op']}")
            if len(statement["args"]) != entry["arity"]:
                raise ProgramRefused(f"{statement['op']} arity")
            for argument in statement["args"]:
                if argument not in seen:
                    raise ProgramRefused(f"{argument} is not in scope")
            seen.add(statement["let"])
        elif "keep" in statement:
            if statement["keep"] not in seen:
                raise ProgramRefused(f"{statement['keep']} is not in scope")
        else:
            raise ProgramRefused(f"unknown statement: {sorted(statement)}")
    for name in program["emit"]:
        if name not in seen:
            raise ProgramRefused(f"emitted name {name} is not in scope")
    for call in program.get("calls", ()):
        for argument in call["args"]:
            if argument not in seen:
                raise ProgramRefused(f"call argument {argument} is not in scope")
    return sorted(seen)


def run(program, inputs, depth, *, table=None, library=None, counter=None, rules=None,
        node_budget=200000):
    """Evaluate a program at concrete points and collect what it emits.

    `inputs` maps the program's parameters to rational points. `depth` bounds the
    recursion and every call lowers it, so the run always ends. The points come
    out in the order they were emitted; nothing is stored expanded.
    """
    table = table if table is not None else operators(library)
    counter = counter if counter is not None else Counter()
    rules = rules if rules is not None else {program["name"]: program}
    emitted = []
    _run(program, dict(inputs), depth, table, counter, rules, emitted, node_budget)
    return emitted, counter


def _run(program, inputs, depth, table, counter, rules, emitted, node_budget):
    if depth <= 0:
        return
    if counter["statements"] > node_budget:
        raise ProgramRefused("the run passed its statement budget")
    counter["calls"] += 1
    coordinates = {name: exact(value) for name, value in inputs.items()}
    dropped = set()
    for statement in program["body"]:
        counter["statements"] += 1
        if "let" in statement:
            xy, reason = apply_operator(statement["op"], statement["args"], coordinates, table,
                                        counter)
            if xy is None:
                counter["refused_steps"] += 1
                raise ProgramRefused(f"{statement['op']} refused: {reason}")
            coordinates[statement["let"]] = exact(xy)
        else:
            predicate, arguments = statement["where"]
            counter["relation_tests"] += 1
            holds = rdsl.atom_holds(predicate, tuple(arguments), coordinates)
            if not holds:
                dropped.add(statement["keep"])
    for name in program["emit"]:
        if name not in dropped:
            emitted.append(coordinates[name])
    for call in program.get("calls", ()):
        target = rules.get(call["rule"])
        if target is None:
            raise ProgramRefused(f"no such rule: {call['rule']}")
        bindings = dict(zip(target["params"],
                            [coordinates[a] for a in call["args"]], strict=True))
        _run(target, bindings, depth-1, table, counter, rules, emitted, node_budget)


# ---------------------------------------------------------------------------
# Filling a point-level hole: a bounded bottom-up enumeration over the operators
# ---------------------------------------------------------------------------

def candidate_bodies(targets, inputs, *, table=None, library=None, levels=2, node_budget=6000,
                     counter=None):
    """Which construction over the given points lands on one of the wanted points.

    A plain bottom-up enumeration: everything reachable in one step from the
    inputs, then everything reachable in one step from those, and so on, cheapest
    arity first, stopping at a node budget. It is written once and used for every
    task; an operation the library has acquired takes part in it as an operator
    like any other, which is the only way acquiring can make a search shorter.

    The equality this answers — "a construction whose output is this point" — is
    not something the contract-directed search can be asked for: an equality goal
    matches no primitive's guarantee, so that search offers no candidate at all.
    """
    table = table if table is not None else operators(library)
    counter = counter if counter is not None else Counter()
    wanted = {exact(point): index for index, point in enumerate(targets)}
    coordinates = {name: exact(value) for name, value in inputs.items()}
    terms = {name: {"op": "var", "name": name} for name in inputs}
    for name, point in list(coordinates.items()):
        if point in wanted:
            counter["hits"] += 1
            yield {"term": terms[name], "target": wanted[point], "level": 0}
    frontier = list(coordinates)
    for level in range(1, levels+1):
        names = list(coordinates)
        fresh = []
        for arity in sorted({entry["arity"] for entry in table.values()}):
            for operator, entry in sorted(table.items()):
                if entry["arity"] != arity:
                    continue
                for arguments in permutations(names, arity):
                    if not any(argument in frontier for argument in arguments):
                        continue                       # nothing new in it, already seen
                    if counter["nodes"] >= node_budget:
                        counter["budget_reached"] += 1
                        return
                    counter["nodes"] += 1
                    xy, _ = apply_operator(operator, arguments, coordinates, table, counter)
                    if xy is None:
                        continue
                    xy = exact(xy)
                    term = {"op": operator, "args": [terms[a] for a in arguments]}
                    if xy in wanted:
                        # a wanted point is worth every construction that reaches it, not
                        # only the first: the shortest one need not be the one a recursion
                        # can be built on, and discarding the others by value would hide it
                        counter["hits"] += 1
                        yield {"term": term, "target": wanted[xy], "level": level}
                    if xy in coordinates.values():
                        counter["duplicate_values"] += 1
                        continue
                    name = f"x{level}_{len(coordinates)}"
                    coordinates[name] = xy
                    terms[name] = term
                    fresh.append(name)
        if not fresh:
            break
        frontier = fresh


def term_to_body(term, prefix="v"):
    """A construction term as `let` statements, with the name of its result."""
    statements, counter = [], [0]

    def walk(node):
        if node["op"] == "var":
            return node["name"]
        arguments = [walk(child) for child in node["args"]]
        counter[0] += 1
        name = f"{prefix}{counter[0]}"
        statements.append({"let": name, "op": node["op"], "args": arguments})
        return name
    result = walk(term)
    return statements, result


# ---------------------------------------------------------------------------
# Filling the structural holes: what to recurse on, and with which arguments
# ---------------------------------------------------------------------------

def synthesise_rule(targets, inputs, *, table=None, library=None, name="r", levels=2,
                    node_budget=6000, calls=2, counter=None, depth=3):
    """A recursive drawing rule that produces every wanted point.

    Bodies come from the bottom-up enumeration one at a time, and each is tried as
    soon as it appears: its recursion is closed by running the argument tuples the
    body's own names allow, at the depth the requirement will be run at, and
    keeping a combination that produces every wanted point still missing. The
    search stops at the first body that closes, so the node count it reports is
    what it cost to succeed. What the search chooses is the operators, their
    arguments, which name to emit, and what each call passes — the shared
    variables included.
    """
    table = table if table is not None else operators(library)
    counter = counter if counter is not None else Counter()
    parameters = list(inputs)
    attempts = []
    for candidate in candidate_bodies(targets, inputs, table=table, levels=levels,
                                      node_budget=node_budget, counter=counter):
        counter["bodies_tried"] += 1
        outcome = _close_recursion(candidate, targets, inputs, parameters, name, table, counter,
                                   calls, depth)
        if outcome["solved"]:
            # the cost that matters is what it took to get here, not what a full
            # enumeration would have cost, so the search stops at the first body
            # whose recursion closes
            outcome["counter"] = dict(counter)
            outcome["bodies_tried"] = counter["bodies_tried"]
            outcome["nodes_to_success"] = counter["nodes"]
            return outcome
        attempts.append({"level": candidate["level"], "target": candidate["target"],
                         "reason": outcome.get("reason")})
    if not attempts:
        return {"solved": False, "stopped_at": "the body", "counter": dict(counter),
                "reason": "no construction over the operators reached any wanted point within "
                          "the levels and the node budget allowed"}
    return {"solved": False, "stopped_at": "the recursion", "counter": dict(counter),
            "reason": "no candidate body closed the recursion", "attempts": attempts[:8]}


def _close_recursion(candidate, targets, inputs, parameters, name, table, counter, calls, depth):
    """Given a body, find calls whose arguments produce the targets it does not.

    A call is tried at the depth the requirement is going to be run at, because a
    target several levels down is invisible to a shallower trial.
    """
    body, result = term_to_body(candidate["term"])
    program = {"name": name, "params": parameters, "body": body, "emit": [result], "calls": []}
    scope = validate(program, table)
    remaining = {index for index in range(len(targets))} - {candidate["target"]}
    if not remaining:
        return {"solved": True, "program": program,
                "covered_by": {"body": candidate["target"], "calls": {}}}
    # what each possible call would produce, one depth further down
    found_target = candidate["target"]
    produced = {}
    for arguments in permutations(scope, len(parameters)):
        if list(arguments) == parameters:
            continue                                   # the call that never moves
        counter["call_candidates"] += 1
        trial = dict(program, calls=[{"rule": name, "args": list(arguments)}])
        try:
            points, _ = run(trial, inputs, depth, table=table, counter=counter,
                            rules={name: trial})
        except ProgramRefused:
            counter["call_candidates_refused"] += 1
            continue
        produced_points = {exact(p) for p in points}
        hit = {index for index, target in enumerate(targets)
               if exact(target) in produced_points}
        if hit & remaining:
            produced[arguments] = hit & remaining
    # what one call reaches on its own is not what a pair of them reaches: a target
    # can be produced only by a call made inside another call, so the combinations
    # are tried and run, not unioned
    useful = sorted(produced.items(), key=lambda item: (-len(item[1]), item[0]))[:12]
    chosen = None
    for size in range(1, calls+1):
        for combination in combinations([arguments for arguments, _ in useful], size):
            counter["call_combinations"] += 1
            trial = dict(program, calls=[{"rule": name, "args": list(arguments)}
                                         for arguments in combination])
            try:
                points, _ = run(trial, inputs, depth, table=table, counter=counter,
                                rules={name: trial})
            except ProgramRefused:
                continue
            produced_points = {exact(p) for p in points}
            if all(exact(targets[index]) in produced_points for index in remaining):
                chosen = [list(arguments) for arguments in combination]
                break
        if chosen is not None:
            break
    if chosen is None:
        reached = set().union(*(hit for _, hit in useful)) if useful else set()
        return {"solved": False,
                "reason": f"no combination of up to {calls} calls reaches targets "
                          f"{sorted(remaining-reached)}"}
    program = dict(program, calls=[{"rule": name, "args": arguments} for arguments in chosen])
    validate(program, table)
    return {"solved": True, "program": program,
            "covered_by": {"body": found_target,
                           "calls": {str(k): sorted(v) for k, v in produced.items()
                                     if list(k) in chosen},
                           "verified_by": "running the combination at the requirement's depth"}}


# ---------------------------------------------------------------------------
# Checking a program against what was asked
# ---------------------------------------------------------------------------

def check(program, inputs, depth, requirement, *, table=None, library=None):
    """Run it and decide every published condition exactly."""
    table = table if table is not None else operators(library)
    points, counter = run(program, inputs, depth, table=table)
    emitted = {exact(point) for point in points}
    checks = []
    for target in requirement.get("must_contain", ()):
        wanted = exact(target)
        checks.append({"check": f"the emitted set contains {[str(v) for v in wanted]}",
                       "passed": wanted in emitted})
    if "count" in requirement:
        checks.append({"check": f"the emitted set has {requirement['count']} points",
                       "passed": len(points) == requirement["count"],
                       "produced": len(points)})
    for condition in requirement.get("all_satisfy", ()):
        predicate, arguments = condition["predicate"], condition["points"]
        holds = []
        for point in points:
            coordinates = {name: exact(value) for name, value in inputs.items()}
            coordinates["z"] = exact(point)
            holds.append(rdsl.atom_holds(predicate, tuple(arguments), coordinates))
        checks.append({"check": f"every emitted point satisfies {predicate}{tuple(arguments)}",
                       "passed": all(holds), "failures": holds.count(False)})
    for condition in requirement.get("all_inside", ()):
        centre = exact(inputs[condition["centre"]])
        through = exact(inputs[condition["through"]])
        inside = [ink.in_closed_disk(exact(point), centre, through) for point in points]
        checks.append({"check": f"every emitted point lies in the disk about {condition['centre']} "
                                f"through {condition['through']}",
                       "passed": all(inside), "failures": inside.count(False)})
    return {"passed": all(c["passed"] for c in checks), "checks": checks,
            "points": len(points), "distinct_points": len(emitted), "counter": dict(counter)}


# ---------------------------------------------------------------------------
# Keeping what a solved program is made of, so a later search can reach it sooner
# ---------------------------------------------------------------------------

def macro_from(program, *, prefix="macro"):
    """A solved body, kept as one operator. It carries no guarantee and says so."""
    steps = [{"out": statement["let"], "prim": statement["op"], "args": list(statement["args"])}
             for statement in program["body"] if "let" in statement]
    if not steps or any(not step["prim"] in FAMILIES for step in steps):
        return None
    key = digest([[step["prim"], step["args"]] for step in steps]+[program["emit"][0]])
    return {"name": f"{prefix}:{key[:12]}", "params": list(program["params"]), "steps": steps,
            "result": program["emit"][0], "primitive_steps": len(steps),
            "guarantees": None,
            "note": "a search abstraction, not a certified operation: it shortens the enumeration "
                    "and states nothing about every configuration"}


def macro_digest(macros):
    return digest([[m["name"], m["params"], [[s["prim"], s["args"]] for s in m["steps"]],
                    m["result"]] for m in macros])
