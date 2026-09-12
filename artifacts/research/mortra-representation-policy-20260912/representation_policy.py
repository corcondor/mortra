"""Which representation to reach for next, without inventing an exchange rate.

The components a representation is measured on are not commensurable. Bits of
description, nodes not expanded, calls not made and seconds of wall clock have
no common unit, and any weighting that turns them into one number is a choice
about what matters smuggled in as arithmetic. So the order used here is a Pareto
order:

    a beats b only when it is at least as good on EVERY component that both were
    measured on, and strictly better on at least one.

Everything not beaten by anything is the first front, and is what gets offered
first. What the first front leaves out goes to the second, and so on -- so a
representation that loses on description bits but removes ninety-nine
hundredths of a search is in the first front, because nothing beats it on both.
It is never dropped for the bits alone.

Two things sit outside the order, on purpose:

    admissibility  a representation whose certificate does not admit it for a
                   task is not ranked low for that task, it is not offered. This
                   is a gate, not a component.
    dormancy       a representation unused for a long time is moved after the
                   others WITHIN its front. It is not removed and its front is
                   not changed, because going unused is not evidence that it is
                   worse.
"""
from __future__ import annotations

SCHEMA = "mortra.representation-policy.v1"

#: every component is oriented so that larger is better
OBJECTIVES = (
    "description_gain_bits",
    "state_dimension_ratio",
    "primitive_calls_eliminated",
    "search_nodes_eliminated",
    "search_candidates_eliminated",
    "depth_reduction_ratio",
    "wall_time_saved",
    "reuse_successes",
    "cheap_acquisition",            # the negated acquisition cost
)


def _latest(entry):
    return entry["measurements"][-1] if entry.get("measurements") else None


def objective_vector(entry):
    """The components, oriented larger-is-better, `None` where unmeasured.

    `None` is not zero. A component neither run can report is skipped in the
    comparison rather than counted as a tie at zero, which would let an
    unmeasured representation dominate a measured one.
    """
    measurement = _latest(entry)
    if measurement is None:
        return {name: None for name in OBJECTIVES}
    state = measurement["state_dimension_reduction"]
    primitive = measurement["primitive_elimination"]
    search = measurement["search_reduction"]
    depth = measurement["sequential_depth_reduction"]
    clock = measurement["measured_wall_time"]
    acquisition = entry.get("acquisition_cost") or {}
    cost = acquisition.get("acquisition_primitive_calls")

    def difference(before, after):
        return None if None in (before, after) else before - after

    return {
        "description_gain_bits": measurement["description_gain_bits"],
        "state_dimension_ratio": state["ratio"],
        "primitive_calls_eliminated": difference(primitive["before"],
                                                 primitive["after"]),
        "search_nodes_eliminated": difference(search["nodes_before"],
                                              search["nodes_after"]),
        "search_candidates_eliminated": difference(search["candidates_before"],
                                                   search["candidates_after"]),
        "depth_reduction_ratio": depth["ratio"],
        "wall_time_saved": clock["saved"],
        "reuse_successes": entry["reuse"]["successes"],
        "cheap_acquisition": None if cost is None else -cost,
    }


def dominates(left, right):
    """Pareto domination over the components BOTH were measured on."""
    comparable = [name for name in OBJECTIVES
                  if left.get(name) is not None and right.get(name) is not None]
    if not comparable:
        return False
    better = False
    for name in comparable:
        if left[name] < right[name]:
            return False
        if left[name] > right[name]:
            better = True
    return better


def fronts(entries):
    """Non-dominated sorting: front 1, then what front 1 hid, and so on."""
    remaining = list(entries)
    vectors = {id(entry): objective_vector(entry) for entry in remaining}
    layers = []
    while remaining:
        layer = [entry for entry in remaining
                 if not any(dominates(vectors[id(other)], vectors[id(entry)])
                            for other in remaining if other is not entry)]
        if not layer:                      # a cycle cannot happen, but do not spin
            layer = list(remaining)
        layers.append(layer)
        remaining = [entry for entry in remaining if entry not in layer]
    return layers


def select(entries, *, task=None, limit=None):
    """The offer order: admissible only, by front, dormant last within a front.

    Returns the chosen entries together with the reasoning, so a later reader can
    see which front an entry came from and what, if anything, beat it.
    """
    considered = list(entries)
    gated, refused = [], []
    for entry in considered:
        verdict = certificate_for(entry, task) if task else None
        if task and not (verdict and verdict.get("admissible")):
            refused.append({"id": entry["id"],
                            "observable": entry["representation"].get("observable"),
                            "reason": ("no certificate for this task" if verdict is None
                                       else "refused by " + ", ".join(
                                           verdict.get("refused_by", []))),
                            "counterexample": _first_counterexample(verdict)})
            continue
        gated.append(entry)

    ordered, layers = [], fronts(gated)
    for index, layer in enumerate(layers, start=1):
        active = [e for e in layer if e["status"] == "active"]
        dormant = [e for e in layer if e["status"] != "active"]
        for entry in active + dormant:
            ordered.append({"id": entry["id"], "front": index,
                            "status": entry["status"],
                            "observable": entry["representation"].get("observable"),
                            "dimension": entry["representation"].get("dimension"),
                            "objectives": objective_vector(entry),
                            "entry": entry})
    chosen = ordered[:limit] if limit else ordered
    return {"schema": SCHEMA, "task": task,
            "selected": chosen, "front_sizes": [len(layer) for layer in layers],
            "not_admissible": refused,
            "order": ("Pareto fronts; within a front, active before dormant. No "
                      "component is weighted against another and there is no "
                      "total"),
            "gate": ("a representation without an admitting certificate for this "
                     "task is not offered at all, rather than ranked low")}


def certificate_for(entry, task):
    for certificate in reversed(entry.get("certificates", [])):
        if certificate.get("task") == task:
            return certificate
    return None


def _first_counterexample(verdict):
    if not verdict:
        return None
    for check in verdict.get("checks", []):
        if check.get("counterexample"):
            return {"check": check["name"],
                    "observation": check["counterexample"]["observation"],
                    "value_a": check["counterexample"]["value_a"],
                    "value_b": check["counterexample"]["value_b"]}
    return None


def explain(entries, task=None):
    """A readable account of why the order is what it is."""
    result = select(entries, task=task)
    lines = [f"task: {task or '(none)'}",
             f"offered {len(result['selected'])}, "
             f"not admissible {len(result['not_admissible'])}, "
             f"front sizes {result['front_sizes']}"]
    for row in result["selected"]:
        measured = {k: v for k, v in row["objectives"].items() if v is not None}
        lines.append(f"  front {row['front']} [{row['status']}] "
                     f"{row['observable']} dim {row['dimension']}: {measured}")
    for row in result["not_admissible"]:
        lines.append(f"  refused {row['observable']}: {row['reason']}")
    return "\n".join(lines)
