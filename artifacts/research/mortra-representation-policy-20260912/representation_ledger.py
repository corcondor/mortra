"""What every learned representation has cost and earned, kept over time.

One entry per representation, never overwritten by a summary. The nine things
the ledger keeps for each are kept as nine things:

    description_gain_bits          MDL / library learning
    state_dimension_reduction      model reduction
    primitive_elimination          calls the representation removed outright
    search_reduction               candidates and nodes not expanded
    sequential_depth_reduction     applications of the same core, in sequence
    measured_wall_time             what it actually took, both sides
    acquisition_cost               what it cost to get, once
    reuse_count                    how often it has since been used, and where
    certificate_scope              what has been proved, and to what range

They are not combined. There is no total, no weighted sum and no score field,
because the selection policy is a Pareto frontier and a scalar would throw away
exactly the trade-offs the frontier is there to keep -- a representation that
loses on bits and removes ninety-nine hundredths of a search is not worse.

Savings are attributed to four different causes and never pooled:

    mathematical_reduction    a route that is cheaper because of mathematics
                              already available without learning anything
    memoisation_reduction     recomputation avoided by a cache
    generic_search_reduction  what a standard search improvement gives, with no
                              learned representation involved
    representation_reduction  what THIS representation adds on top of all three

The last one is the only number that belongs to the representation. The ladder
is measured as marginal steps, each rung an actual run, so the four add up to
the total rather than being apportioned.

Nothing is deleted. A representation that has not been used for a while becomes
dormant, which lowers its position in the selection order and nothing else; its
measurements, its certificate and its provenance stay.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from math_os_prototype.representation_progress import digest

SCHEMA = "mortra.representation-ledger.v1"

#: the nine, by name, so a reader can check none has quietly gone missing
COMPONENTS = ("description_gain_bits", "state_dimension_reduction",
              "primitive_elimination", "search_reduction",
              "sequential_depth_reduction", "measured_wall_time",
              "acquisition_cost", "reuse_count", "certificate_scope")

ATTRIBUTION = ("mathematical_reduction", "memoisation_reduction",
               "generic_search_reduction", "representation_reduction")

DELETION_POLICY = ("never deleted. Going unused lowers the selection order and "
                   "nothing else; the entry, its measurements, its certificates "
                   "and its provenance are kept.")


def _certificate_scope(certificate):
    """What has been proved about this representation, and to what range.

    Kept as the ninth component in its own right: an admission that rests on a
    depth-bounded search is not the same asset as one that rests on a proof, and
    flattening them would lose exactly the distinction the certificate exists to
    make.
    """
    if not certificate:
        return None
    return {"task": certificate.get("task"),
            "verdict": certificate.get("verdict"),
            "admissible": certificate.get("admissible"),
            "refused_by": certificate.get("refused_by"),
            "checks": [{"name": check.get("name"), "kind": check.get("kind"),
                        "holds": check.get("holds"),
                        "scope": check.get("scope"),
                        "depth": check.get("depth"),
                        "compared": check.get("words_compared")}
                       for check in certificate.get("checks", [])],
            "sense": ("a check of kind `proof` holds for every state; one of "
                      "kind `no counterexample within depth` holds only as far "
                      "as it was searched, and says how far")}


def components_of(evaluation):
    """Pull the nine out of one evaluation record, each on its own."""
    compression = evaluation["description_compression"]
    state = evaluation["state_reduction"]
    primitive = evaluation["primitive_reduction"]
    search = evaluation["search_reduction"]
    depth = evaluation["execution_depth"]
    cost = evaluation["real_cost"]
    raw, reduced = state["raw_state_dimension"], state["representation_dimension"]
    return {
        "task": evaluation["name"],
        "description_gain_bits": compression["net_description_gain_bits"],
        "state_dimension_reduction": {
            "before": raw, "after": reduced,
            "difference": (raw - reduced) if None not in (raw, reduced) else None,
            "ratio": (raw / reduced) if reduced else None},
        "primitive_elimination": {
            "before": primitive["primitive_calls_before"],
            "after": primitive["primitive_calls_after"],
            "eliminated": primitive["eliminated_by_representation"],
            "derivative_calls_before": primitive["derivative_calls_before"],
            "derivative_calls_after": primitive["derivative_calls_after"],
            "derivative_request_calls_before":
                primitive["derivative_request_calls_before"],
            "derivative_request_calls_after":
                primitive["derivative_request_calls_after"]},
        "search_reduction": {
            "candidates_before": search["candidates_generated_before"],
            "candidates_after": search["candidates_generated_after"],
            "nodes_before": search["search_nodes_before"],
            "nodes_after": search["search_nodes_after"],
            "rejected_before": search["rejected_candidates_before"],
            "rejected_after": search["rejected_candidates_after"],
            "units": search.get("units")},
        "sequential_depth_reduction": {
            "before": depth["sequential_depth_before"],
            "after": depth["sequential_depth_after"],
            "ratio": depth["depth_reduction_ratio"],
            "not_a_success_condition": depth["not_a_success_condition"]},
        "measured_wall_time": {
            "before": cost["wall_time_before"], "after": cost["wall_time_after"],
            "saved": (None if None in (cost["wall_time_before"],
                                       cost["wall_time_after"])
                      else round(cost["wall_time_before"]
                                 - cost["wall_time_after"], 6))},
        "attribution": evaluation.get("attribution"),
        "break_evens": evaluation["cumulative"]["break_evens"],
        "provenance": evaluation.get("provenance"),
        "certificate_scope": _certificate_scope(evaluation.get("certificate")),
    }


class Ledger:
    """The store. Append-only in spirit: entries are updated, never dropped."""

    def __init__(self, path=None, entries=None, cycle=0):
        self.path = Path(path) if path else None
        self.entries = {k: deepcopy(v) for k, v in (entries or {}).items()}
        self.cycle = int(cycle)

    # -- identity -----------------------------------------------------------

    @staticmethod
    def identify(representation):
        return digest(representation)[:24]

    # -- writing ------------------------------------------------------------

    def observe(self, representation, evaluation, *, certificate=None,
                acquisition=None):
        """Record one measurement of one representation. Adds, never replaces."""
        key = self.identify(representation)
        entry = self.entries.setdefault(key, {
            "id": key, "kind": representation.get("kind"),
            "representation": deepcopy(representation),
            "first_seen_cycle": self.cycle,
            "acquisition_cost": deepcopy(acquisition or {}),
            "measurements": [], "certificates": [],
            "reuse": {"count": 0, "successes": 0, "failures": 0,
                      "heldout_successes": 0, "tasks": [],
                      "last_used_cycle": None},
            "status": "active", "dormant_since": None,
            "deleted": False, "deletion_policy": DELETION_POLICY})
        if acquisition and not entry["acquisition_cost"]:
            entry["acquisition_cost"] = deepcopy(acquisition)
        entry["measurements"].append(components_of(evaluation))
        if certificate is not None:
            entry["certificates"].append(deepcopy(certificate))
        reuse = entry["reuse"]
        report = evaluation.get("reuse", {})
        reuse["count"] += 1
        reuse["successes"] += report.get("successful_reuses", 0)
        reuse["heldout_successes"] += report.get("heldout_successes", 0)
        reuse["failures"] += report.get("failed_reuses", 0)
        reuse["last_used_cycle"] = self.cycle
        if evaluation["name"] not in reuse["tasks"]:
            reuse["tasks"].append(evaluation["name"])
        entry["status"] = "active"
        entry["dormant_since"] = None
        return entry

    def note_certificate(self, representation, certificate):
        """A refusal is worth keeping too: it says where this must not be used."""
        key = self.identify(representation)
        entry = self.entries.setdefault(key, {
            "id": key, "kind": representation.get("kind"),
            "representation": deepcopy(representation),
            "first_seen_cycle": self.cycle, "acquisition_cost": {},
            "measurements": [], "certificates": [],
            "reuse": {"count": 0, "successes": 0, "failures": 0,
                      "heldout_successes": 0, "tasks": [],
                      "last_used_cycle": None},
            "status": "active", "dormant_since": None,
            "deleted": False, "deletion_policy": DELETION_POLICY})
        entry["certificates"].append(deepcopy(certificate))
        return entry

    # -- ageing, which is not deletion --------------------------------------

    def advance(self, *, idle_cycles=8):
        """Move the clock on and mark the long-unused dormant.

        Dormant changes the selection order and nothing else. There is no path
        in this class that removes an entry.
        """
        self.cycle += 1
        for entry in self.entries.values():
            last = entry["reuse"]["last_used_cycle"]
            idle = self.cycle - (last if last is not None
                                 else entry["first_seen_cycle"])
            if idle >= idle_cycles and entry["status"] == "active":
                entry["status"] = "dormant"
                entry["dormant_since"] = self.cycle
                entry["dormancy_note"] = (
                    f"unused for {idle} cycles; lowered in the selection order, "
                    "kept in full")
        return self.cycle

    # -- reading ------------------------------------------------------------

    def active(self):
        return [e for e in self.entries.values() if e["status"] == "active"]

    def all_entries(self):
        return list(self.entries.values())

    def admissible_for(self, task_name):
        """Only those whose certificate for this task admits them."""
        out = []
        for entry in self.entries.values():
            for certificate in reversed(entry["certificates"]):
                if certificate.get("task") == task_name:
                    if certificate.get("admissible"):
                        out.append(entry)
                    break
        return out

    # -- persistence --------------------------------------------------------

    def state(self):
        payload = {"schema": SCHEMA, "cycle": self.cycle,
                   "components": list(COMPONENTS),
                   "attribution": list(ATTRIBUTION),
                   "deletion_policy": DELETION_POLICY,
                   "entries": deepcopy(self.entries)}
        payload["sha256"] = digest(payload)
        return payload

    @classmethod
    def restore(cls, payload, path=None):
        stored = dict(payload)
        if stored.pop("sha256", None) != digest(stored):
            raise ValueError("ledger digest does not match")
        return cls(path=path, entries=payload["entries"], cycle=payload["cycle"])

    def save(self, path=None):
        target = Path(path or self.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.state(), indent=1, sort_keys=True),
                          encoding="utf-8")
        return target

    @classmethod
    def load(cls, path):
        target = Path(path)
        if not target.exists():
            return cls(path=target)
        return cls.restore(json.loads(target.read_text(encoding="utf-8")),
                           path=target)
