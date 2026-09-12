"""What to compute next when something has just been acquired.

The loop already had one rule of this kind: a proved relation becomes a
construction and `extend_seeds` puts it back among the seeds. That rule knows
about exactly one type. When an operation or an observable is acquired instead,
there is nothing to carry it forward, so the acquisition is displayed and then
lost.

This is that rule generalised. An acquisition declares its type; the table says
what can be computed from that type; the results go into the same candidate
queue under the same budget. Nothing here is specific to any one acquisition:
adding a type means adding a row, not a new pipeline.

What a follow-up is allowed to carry
    Whatever a candidate needs in order to be run, it carries: the body, the
    names its arguments have, the domain it is defined on, and a reference to
    the proof that admitted it. A follow-up that only copied the body would
    produce candidates that cannot say what they are about, and a candidate that
    ignores its parent's expression is not a continuation of anything.

Enumeration, not selection
    The abstraction and morphism candidates are enumerated from the same grammar
    of programs over holes that everything else uses. Which one is worth anything
    is decided downstream by the correspondence proof and the acceptance gate,
    not here.
"""
from __future__ import annotations

from copy import deepcopy
from itertools import permutations

from math_os_prototype.abstraction_correspondence import (
    apply_operation, normal_form, same_domain, slot, slot_expressions)
from math_os_prototype.representation_progress import digest

SCHEMA = "mortra.acquisition-followups.v2"
KINDS = ("construction", "operation", "observable", "abstraction")


# ---- enumerating candidates from the grammar that already exists ----------

def abstraction_candidates(state_names, *, arity=2, depth=1, limit=24):
    """Tuples of programs over the state holes, offered as abstractions.

    Two tuples that normalise to the same expressions are one candidate. The
    grammar reaches the same abstraction by several routes, and offering each
    route separately would prove the same operations again and report one
    abstract object as several.
    """
    pieces = slot_expressions(state_names, depth=depth)
    candidates, seen = [], set()
    for i in range(len(pieces)):
        for j in range(i + 1, len(pieces)):
            candidate = [pieces[i], pieces[j]][:arity]
            name = normal_form(candidate)
            if name in seen:
                continue
            seen.add(name)
            candidates.append({"id": name[:16], "alpha": candidate})
            if len(candidates) >= limit:
                return candidates
    return candidates


def morphism_candidates(state_names, parameter_names, *, limit=12, derivatives=0):
    """Maps of the holes to programs over the holes, offered as operations.

    Permutations of the state and one parameter added to a chosen subset, and --
    when the caller says the objects are differentiable -- the same maps with
    each component differentiated. Every piece is a registered operation of the
    program grammar; nothing is named after what it might turn out to be, and
    the candidate space is not narrowed to the operations one prover happens to
    find cheap.
    """
    candidates, seen = [], set()
    parameter = parameter_names[0] if parameter_names else None
    for depth in range(derivatives + 1):
        for order in permutations(state_names):
            base = {name: slot(target) for name, target in zip(state_names, order)}
            for mask in range(1 << len(state_names)) if parameter else [0]:
                morphism = dict(base)
                for index, name in enumerate(state_names):
                    if parameter and (mask >> index) & 1:
                        morphism[name] = {"op": "add",
                                          "left": deepcopy(morphism[name]),
                                          "right": slot(parameter)}
                for name in state_names:
                    for _ in range(depth):
                        morphism[name] = {"op": "diff",
                                          "child": deepcopy(morphism[name])}
                if parameter:
                    morphism[parameter] = slot(parameter)
                name = normal_form(morphism)
                if name in seen:
                    continue
                seen.add(name)
                candidates.append({"id": name[:16], "morphism": morphism,
                                   "derivative_order": depth})
                if len(candidates) >= limit:
                    return candidates
    return candidates


# ---- the table: acquisition type to follow-up material --------------------

def _bound_coordinates(operation, coordinates):
    """Are all of this operation's arguments bound to concrete programs?"""
    needed = set(operation.get("coordinate_names", [])) | set(
        operation.get("parameter_names", []))
    return needed and needed <= set(coordinates)


def _from_construction(acquisition, context):
    """A proved construction is a program, and programs are seeds already."""
    return {"seeds": [acquisition["program"]], "candidates": []}


def _from_operation(acquisition, context):
    """An acquired operation can be run, composed, and asked what it fixes."""
    operation = acquisition["operation"]
    # An operation is a template. Applying it to holes gives another template,
    # which is not a program the generator can take. It only becomes a seed once
    # the coordinates are bound to the concrete objects the abstraction came
    # from, so without those bindings it contributes no seed at all.
    coordinates = acquisition.get("coordinates") or {}
    seeds = []
    if _bound_coordinates(operation, coordinates):
        seeds.extend(apply_operation(operation, coordinates))
    candidates = [{"kind": "conservation", "operation": deepcopy(operation),
                   "signature": deepcopy(acquisition.get("signature")),
                   "coordinates": deepcopy(coordinates),
                   "abstraction": acquisition.get("abstraction"),
                   "parent": acquisition["id"]}]
    # Composition includes this operation with itself. Two copies of a
    # one-parameter family at independent parameters is the case worth asking
    # about, and refusing it because the two factors are the same object would
    # rule out exactly that question.
    #
    # Two bounds are declared rather than left implicit. Only operations on the
    # same abstract object are composed, because agreeing on the spelling of the
    # coordinates is not agreeing on what they denote. And a composite does not
    # itself offer further compositions: stacking them only adds parameters, and
    # once a composition law is proved the composite is already a member of the
    # family it came from.
    if acquisition.get("composed_of") is None:
        for other in context.get("known_operations", []) + [acquisition]:
            if other.get("composed_of") is not None:
                continue
            if not same_domain(operation, other["operation"]):
                continue
            candidates.append({"kind": "composition",
                               "outer": deepcopy(operation),
                               "inner": deepcopy(other["operation"]),
                               "signature": deepcopy(acquisition.get("signature")),
                               "coordinates": deepcopy(coordinates),
                               "abstraction": acquisition.get("abstraction"),
                               "parent": acquisition["id"], "with": other["id"],
                               "self_composition": other["id"] == acquisition["id"]})
    return {"seeds": seeds, "candidates": candidates,
            "bounds": ["compositions are offered only between operations on the same "
                       "abstract object, and only from operations that are not "
                       "themselves composites"]}


def _from_observable(acquisition, context):
    """An observable is a program, and it is a question about other operations.

    What it is not is a reason to run the search that produced it again. Asking
    the same operation for its conserved quantities a second time returns the
    same answer by construction, so that edge is not in the table.
    """
    program = acquisition.get("program")
    coordinates = acquisition.get("coordinates") or {}
    seeds = []
    if program is not None and coordinates:
        try:
            seeds.append(apply_operation({"body": [program]}, coordinates)[0])
        except ValueError:
            seeds = []
    candidates = []
    for other in context.get("known_operations", []):
        if other["id"] == acquisition.get("from_operation"):
            continue
        if acquisition.get("abstraction") != other.get("abstraction"):
            continue
        candidates.append({"kind": "invariance",
                           "observable": deepcopy(program),
                           "expression": acquisition.get("expression"),
                           "operation": deepcopy(other["operation"]),
                           "signature": deepcopy(acquisition.get("signature")),
                           "abstraction": acquisition.get("abstraction"),
                           "parent": acquisition["id"], "against": other["id"]})
    return {"seeds": seeds, "candidates": candidates,
            "bounds": ["an observable is only asked about operations on the abstract "
                       "object it was found on"]}


def _from_abstraction(acquisition, context):
    """An accepted abstraction hands over the operations it proved.

    The whole operation record travels, not just its body: the argument names,
    the domain, and the proofs that admitted it are what let the next stage say
    why it is allowed to run this.
    """
    record = acquisition["record"]
    candidates = []
    for entry in record.get("supported_morphisms", []):
        operation = {field: deepcopy(entry[field]) for field in
                     ("body", "coordinate_names", "parameter_names", "domain",
                      "proofs", "proved", "routes", "law", "sha256")
                     if field in entry}
        operation["provenance"] = {"abstraction": acquisition["id"],
                                   "morphism": entry["morphism"],
                                   "admitted_by": entry.get("admitted_by")}
        candidates.append({"kind": "operation_acquired", "parent": acquisition["id"],
                           "morphism": entry["morphism"],
                           "morphism_program": deepcopy(entry.get("morphism_program")),
                           "argument_correspondence":
                               deepcopy(entry.get("argument_correspondence")),
                           "abstraction": acquisition["id"],
                           "signature": deepcopy(record.get("signature")),
                           "coordinates": deepcopy(acquisition.get("coordinates", {})),
                           "operation": operation})
    return {"seeds": [], "candidates": candidates}


TABLE = {"construction": _from_construction,
         "operation": _from_operation,
         "observable": _from_observable,
         "abstraction": _from_abstraction}


def follow_ups(acquisition, context):
    """Type-compatible continuations for one acquisition."""
    kind = acquisition.get("kind")
    if kind not in TABLE:
        return {"seeds": [], "candidates": [], "bounds": [],
                "reason": f"no follow-up is defined for an acquisition of kind {kind!r}"}
    produced = TABLE[kind](acquisition, context)
    return {"seeds": produced["seeds"], "candidates": produced["candidates"],
            "bounds": produced.get("bounds", []),
            "reason": f"follow-ups for kind {kind!r}"}
