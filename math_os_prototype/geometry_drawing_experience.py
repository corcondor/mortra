"""What a drawing search leaves behind for the next one.

Saving a picture is not learning, and neither is saving a log. What a later
search can actually consult is this: the bodies and the whole rules earlier
searches built, and the order in which the operators are worth trying. Those
three things are what this file keeps, and they are the only things the search
reads back.

    macros   a body, with its parameters, kept so a later search reaches the
             same point in one step instead of several. It carries no geometric
             guarantee — see `geometry_drawing_program.operators`.
    rules    a whole drawing program, recursion and shared variables included,
             kept so a later search may call it rather than rebuild it. This is
             what a macro cannot hold: a macro is a straight-line body, so the
             iteration structure is exactly what it loses.
    order    how often each operator has appeared in something that worked,
             which is what the bottom-up enumeration sorts by. With no
             experience the order is the alphabetical one it always had.

Nothing here is a geometric claim. It is the memory of a search.
"""
from __future__ import annotations

import json
from pathlib import Path

from math_os_prototype.representation_progress import digest

VERSION = 1


def empty():
    return {"version": VERSION, "macros": [], "rules": [], "operator_uses": {},
            "solved": [], "refused": []}


def load(path):
    path = Path(path)
    if not path.exists():
        return empty()
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("version") != VERSION:
        raise ValueError(f"experience at {path} is version {record.get('version')}, not {VERSION}")
    return record


def save(record, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=1, default=str)+"\n", encoding="utf-8")
    return str(path)


def program_key(program):
    """A name for a whole program that does not depend on how it was written."""
    return digest([program["params"],
                   [[s.get("op") or s.get("keep"), s.get("args") or s.get("where")]
                    for s in program["body"]],
                   program["emit"],
                   [[c["rule"], c["args"]] for c in program.get("calls", ())]])


def remember(record, *, task, program, macro, costs, solved, reason=None):
    """Fold one attempt into the record. Failures are kept too, with their reason."""
    if not solved:
        record["refused"].append({"task": task, "reason": reason, "costs": costs})
        return record
    key = program_key(program)
    record["solved"].append({"task": task, "program": key, "costs": costs})
    if macro is not None and all(held["name"] != macro["name"] for held in record["macros"]):
        record["macros"].append({**macro, "from": task, "uses": 0})
    rules = {held["key"]: held for held in record["rules"]}
    if key not in rules:
        stored = f"rule:{key[:12]}"
        # a stored rule keeps its own name in its own calls. Left as the generic
        # name the search gave it, a self-call would resolve to whatever program
        # is being built when it is reused, and take the wrong arity with it.
        calls = [dict(call, rule=stored if call["rule"] == program["name"] else call["rule"])
                 for call in program.get("calls", ())]
        record["rules"].append({"key": key, "name": stored, "from": task,
                                "params": list(program["params"]),
                                "body": [dict(s) for s in program["body"]],
                                "emit": list(program["emit"]),
                                "calls": calls,
                                "recursive": bool(program.get("calls")), "uses": 0})
    for statement in program["body"]:
        if "let" in statement:
            record["operator_uses"][statement["op"]] = \
                record["operator_uses"].get(statement["op"], 0)+1
    return record


def note_use(record, *, macros=(), rules=()):
    """Mark what a later search actually reached for, so the order follows real use."""
    for held in record["macros"]:
        if held["name"] in macros:
            held["uses"] += 1
    for held in record["rules"]:
        if held["name"] in rules:
            held["uses"] += 1
    return record


def macros_of(record):
    return [{k: held[k] for k in ("name", "params", "steps", "result", "primitive_steps",
                                  "guarantees", "note")}
            for held in record["macros"]]


def rules_of(record):
    """The stored programs, in the shape `run` wants, keyed by the name a call would use."""
    return {held["name"]: {"name": held["name"], "params": list(held["params"]),
                           "body": [dict(s) for s in held["body"]],
                           "emit": list(held["emit"]),
                           "calls": [dict(c) for c in held["calls"]]}
            for held in record["rules"]}


def operator_order(record):
    """How often each operator has been part of something that worked."""
    return dict(record["operator_uses"])


def summary(record):
    return {"macros": len(record["macros"]), "rules": len(record["rules"]),
            "recursive_rules": sum(1 for r in record["rules"] if r["recursive"]),
            "solved": len(record["solved"]), "refused": len(record["refused"]),
            "operator_uses": dict(sorted(record["operator_uses"].items(),
                                         key=lambda item: (-item[1], item[0]))),
            "description_length": len(json.dumps({"macros": record["macros"],
                                                  "rules": record["rules"]}, default=str))}
