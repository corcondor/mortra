"""When two routes ask for the same computation, run it once.

The loop now reaches the same program by two roads: the ordinary route builds it
out of seeds, and the library route writes it as a call and expands it. Those are
two descriptions of one term, and the expensive part -- building the feature
closure, computing a common annihilator, certifying -- does not care which road
the term arrived by.

What has to agree before one job may stand for another
    Not the expression alone. A result is only reusable when the *same operation*
    was asked of the *same terms* under the *same premises*, with the *same*
    prover and the *same* definitions. A definition table that changed means a
    call expands to something else; a prover version that changed means the
    certificate means something else. All of that is in the key, so a job from a
    stale configuration cannot be handed back.

What this is not
    A stored result is handed to the first asker as it is and copied for every
    later one, so a caller must treat what it gets back as read-only.

    It is not an equality test. Two terms share a job only when their canonical
    forms already agree -- definitional expansion and the normalisation the
    repository already performs. Nothing here decides that two different terms
    denote the same function.

What already existed
    `holonomic_route_discovery._annihilator` and `._coefficients` are
    `lru_cache`d on the program key, so a repeated annihilator is already free.
    Measured on a repeated relation pipeline, that alone takes 0.213 s down to
    0.020 s. What it does not remove is the rest: the feature closure, the
    guesser, the remainder checks and the certificate wrapping all run again.
    This store sits above them and is keyed by the job, not by the program.
"""
from __future__ import annotations

import time
from copy import deepcopy

from math_os_prototype.representation_progress import digest

SCHEMA = "mortra.job-sharing.v1"


def job_key(*, operation, terms, premises, versions):
    """What two jobs must agree on before one may stand for the other."""
    return digest({"schema": SCHEMA, "operation": operation,
                   "terms": list(terms), "premises": dict(premises),
                   "versions": dict(versions)})


class JobStore:
    """Results of completed jobs, with the representations that asked for them."""

    def __init__(self, versions, *, enabled=True):
        self.versions = dict(versions)
        self.enabled = enabled
        self.entries = {}
        self.log = []
        self.phase_seconds = {}
        self.phase_calls = {}

    # ---- phase accounting, kept apart from description length --------------

    def charge(self, phase, seconds):
        """Record what a phase cost. Bits of description are not seconds."""
        self.phase_seconds[phase] = self.phase_seconds.get(phase, 0.0) + seconds
        self.phase_calls[phase] = self.phase_calls.get(phase, 0) + 1

    def timed(self, phase, work):
        started = time.perf_counter()
        try:
            return work()
        finally:
            self.charge(phase, time.perf_counter() - started)

    # ---- the store --------------------------------------------------------

    def run(self, *, operation, terms, premises, work, representation=None,
            phase=None):
        """The result of this job, computed once however many ask for it."""
        if not self.enabled:
            # Off means off: no key is built and nothing is stored, so a loop
            # that gets no reuse out of this pays nothing for it either.
            started = time.perf_counter()
            result = work()
            self.charge(phase or operation, time.perf_counter() - started)
            return result, False
        key = job_key(operation=operation, terms=terms, premises=premises,
                      versions=self.versions)
        entry = self.entries.get(key)
        if entry is not None:
            entry["hits"] += 1
            if representation is not None and representation not in entry["asked_by"]:
                entry["asked_by"].append(representation)
            self.log.append({"job": key[:16], "operation": operation,
                             "shared": True, "representation": representation,
                             "saved_seconds": entry["seconds"]})
            self.charge((phase or operation) + ":shared", 0.0)
            return deepcopy(entry["result"]), True
        started = time.perf_counter()
        result = work()
        seconds = time.perf_counter() - started
        self.charge(phase or operation, seconds)
        if True:
            # The first asker gets the object it computed; a later one gets a
            # copy. Copying on the way in as well would charge every job for a
            # deep copy of a result nobody ever asks for twice, which is a real
            # cost and not a saving.
            self.entries[key] = {"operation": operation, "terms": list(terms),
                                 "premises": dict(premises), "seconds": seconds,
                                 "hits": 0, "result": result,
                                 "asked_by": [representation] if representation
                                             else []}
        self.log.append({"job": key[:16], "operation": operation, "shared": False,
                         "representation": representation, "seconds": seconds})
        return result, False

    # ---- what happened ----------------------------------------------------

    def shared(self):
        """Jobs a second asker got for nothing, and who the askers were."""
        return [{"job": key[:16], "operation": entry["operation"],
                 "hits": entry["hits"], "seconds_each": round(entry["seconds"], 4),
                 "seconds_saved": round(entry["hits"] * entry["seconds"], 4),
                 "asked_by": entry["asked_by"]}
                for key, entry in self.entries.items() if entry["hits"]]

    def cross_route(self):
        """Jobs asked for by more than one kind of representation.

        This is the one that answers the question: did writing a term as a call
        and writing it out in full end up on the same computation.
        """
        found = []
        for entry in self.shared():
            kinds = {asker.split(":")[0] for asker in entry["asked_by"] if asker}
            if len(kinds) > 1:
                found.append(dict(entry, representations=sorted(kinds)))
        return found

    def report(self):
        shared = self.shared()
        return {"schema": SCHEMA, "enabled": self.enabled,
                "versions": dict(self.versions),
                "jobs": len(self.entries), "reuses": sum(e["hits"] for e in shared),
                "seconds_saved": round(sum(e["seconds_saved"] for e in shared), 4),
                "seconds_by_phase": {k: round(v, 4)
                                     for k, v in sorted(self.phase_seconds.items())},
                "calls_by_phase": dict(sorted(self.phase_calls.items())),
                "shared": shared, "cross_route": self.cross_route(),
                "scope": ("identity is canonical form after definitional expansion "
                          "and the normalisation already performed; no equality "
                          "decision is made here")}
