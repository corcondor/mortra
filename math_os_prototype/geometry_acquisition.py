"""Turning a solved construction into an operation the solver can use again.

The path is the one the repository already has:

    the solver's solution is a nested construction term;
    `geometry_contracts.dag` converts it to the program shape the edit calculus
    speaks; the task's goal atoms become the operation's declared guarantees;
    `geometry_relational_edit.define` refuses the operation unless every
    declared guarantee is certified exactly over QQ(inputs) — not at the
    instance that produced it — and unless the body is non-vacuous;
    `AcquiredLibrary.register` makes the certified operation retrievable by the
    same path the enumerated programs use.

Nothing here writes a solution. It reads one the solver found, and either
certifies the general statement behind it or records why it could not.
"""
from __future__ import annotations

from math_os_prototype import geometry_contracts as gc
from math_os_prototype import geometry_relational_dsl as rdsl
from math_os_prototype import geometry_relational_edit as edit
from math_os_prototype import geometry_relational_library as lib
from math_os_prototype import geometry_semantic_dsl as dsl

SLOTS = ("p0", "p1", "p2")


def body_from_solution(solution, goals):
    """The solution term as a program over at most three slots, or a reason it cannot be one."""
    term = solution.get("term")
    if not isinstance(term, dict) or term.get("op") == "var":
        return None, "the solution is an input point"
    try:
        steps, output = gc.dag(term, fragment=dsl.FRAGMENT)
        parameters = list(gc.parameters(term, fragment=dsl.FRAGMENT))
    except (ValueError, KeyError) as error:
        return None, f"term conversion refused: {error}"
    if not steps:
        return None, "the solution has no construction step"
    mentioned = [a for goal in goals for a in goal["points"] if a != "u"]
    names = list(dict.fromkeys(parameters+mentioned))
    if len(names) > len(SLOTS):
        return None, f"{len(names)} distinct points at the interface, more than the retrieval slots"
    renaming = {name: SLOTS[index] for index, name in enumerate(names)}
    body = {"params": [renaming[name] for name in names],
            "steps": [{"out": step["output"], "prim": step["family"],
                       "args": [renaming.get(a, a) for a in step["inputs"]]} for step in steps],
            "result": output}
    return (body, renaming), None


def declared_guarantees(goals, renaming):
    """The task's goals written over the operation's slots and its result."""
    posts = []
    for goal in goals:
        arguments = tuple("v" if a == "u" else renaming[a] for a in goal["points"])
        posts.append((goal["predicate"], arguments))
    return posts


def surviving_guarantees(body, declared):
    """Split the declared guarantees into those true for every configuration and those that are not.

    Each one is decided by the same exact procedure the library uses,
    `certify_entry`, over the rational function field of the inputs. A relation
    that held only at the configuration the task was posed at is not a guarantee
    of the operation, and is reported instead of being kept.
    """
    try:
        primitive = edit.unfold(body, {})
    except edit.EditRefused:
        return [], [[p, list(a)] for p, a in declared]
    kept, instance_only = [], []
    for predicate, arguments in declared:
        try:
            certificate = lib.certify_entry(predicate, tuple(arguments), primitive)
        except (lib.CertificationBudgetExceeded, ZeroDivisionError, ValueError, KeyError):
            certificate = None
        if certificate is None:
            instance_only.append([predicate, list(arguments)])
        else:
            kept.append((predicate, tuple(arguments)))
    return kept, instance_only


def acquire(solution, task, *, table=None):
    """Certify the solved construction as a general operation, or say why not.

    The guarantees are certified over the rational function field by
    `edit.define`; a relation that held only at this configuration is refused
    there, and the refusal is returned as the reason.
    """
    converted, reason = body_from_solution(solution, task["goals"])
    if converted is None:
        return {"acquired": False, "reason": reason}
    body, renaming = converted
    declared = declared_guarantees(task["goals"], renaming)
    posts, instance_only = surviving_guarantees(body, declared)
    if not posts:
        return {"acquired": False, "reason": "every declared guarantee held only at this configuration",
                "body": body, "declared": [[p, list(a)] for p, a in declared]}
    try:
        definition = edit.define(body, posts, table or {})
    except edit.EditRefused as refusal:
        return {"acquired": False, "reason": f"definition refused: {refusal}", "body": body,
                "declared": [[p, list(a)] for p, a in posts]}
    except lib.CertificationBudgetExceeded:
        return {"acquired": False, "reason": "certification budget exceeded", "body": body}
    except (ZeroDivisionError, ValueError, KeyError) as error:
        return {"acquired": False, "reason": f"certification refused: {type(error).__name__}: {error}",
                "body": body}
    patterns = {}
    for predicate, arguments in posts:
        pattern = rdsl.canonical_atom(predicate, arguments)
        key = _certificate_key(definition, predicate, arguments)
        certificate = definition["certificates"].get(key)
        if certificate is not None:
            patterns[pattern] = certificate
    if not patterns:
        return {"acquired": False, "reason": "no guarantee survived certification", "body": body}
    return {"acquired": True, "definition": definition, "body": body, "patterns": patterns,
            "renaming": renaming, "primitive_steps": definition["primitive_steps"],
            "declared": [[p, list(a)] for p, a in posts],
            "instance_only": instance_only}


def _certificate_key(definition, predicate, arguments):
    from math_os_prototype.representation_progress import digest
    return digest([predicate, list(arguments)])


def register(library, acquisition, *, source):
    """Put a certified operation into the library, unless an identical program is already there."""
    program = edit.unfold(acquisition["body"], {})
    program = {"params": list(acquisition["body"]["params"]), "steps": program["steps"],
               "result": program["result"]}
    if library.holds(program):
        return {"registered": False, "reason": "an identical program is already indexed"}
    index = library.register(program, acquisition["patterns"], source=source)
    return {"registered": True, "index": index, "steps": len(program["steps"]),
            "patterns": [[p[0], list(p[1])] for p in acquisition["patterns"]]}


def used_acquired_operation(solution, library):
    """Which acquired operations appear inside a solution, by comparing primitive expansions.

    A solution that merely rebuilt the same steps by itself counts as a use of
    the operation's content; a solution that shares no such block is a new
    composition. Both are reported, so the two can be told apart afterwards.
    """
    term = solution.get("term")
    if not isinstance(term, dict) or term.get("op") == "var":
        return []
    try:
        steps, _ = gc.dag(term, fragment=dsl.FRAGMENT)
    except (ValueError, KeyError):
        return []
    families = [step["family"] for step in steps]
    used = []
    for index, entry in library.acquired.items():
        program = library.programs[index]
        wanted = [step["prim"] for step in program["steps"]]
        if _subsequence(wanted, families):
            used.append({"index": index, "families": wanted, "source": entry["source"]})
    return used


def _subsequence(needle, haystack):
    if not needle:
        return False
    position = 0
    for item in haystack:
        if item == needle[position]:
            position += 1
            if position == len(needle):
                return True
    return False
