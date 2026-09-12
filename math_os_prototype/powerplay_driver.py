"""The loop that carries controller changes, its history, and its own cost.

One round proposes a task and a set of certified equalities. The equalities are
turned into a controller by rebuilding the library from certificates, so an
unproved rule cannot enter: `build_library` re-verifies every certificate and
`RelationLibrary` refuses a library that does not replay. Passing the gate is
never a substitute for that check, and the two are kept apart on purpose.

Accounting covers the whole round, not only the accepted part: proposing,
rebuilding the controller, and verifying acceptance are all charged, and a
rejected round is charged too. Otherwise a proposer that floods the gate with
hopeless candidates would look free.

The stored state is what a proposer is given. `context` returns the current
controller, the stored tasks, the accepted history and the construction memory,
so a proposer that ignores past acquisitions has to ignore them deliberately;
it cannot fail to receive them.
"""
from __future__ import annotations

from copy import deepcopy

from math_os_prototype.bounded_competence import (
    CRITERIA,
    acceptance,
    library_digest,
    replay_acceptance,
    task_digest,
)
from math_os_prototype.holonomic_construction_memory import replay_memory
from math_os_prototype.holonomic_relation_reuse import RelationLibrary, build_library
from math_os_prototype.representation_progress import digest

SCHEMA = "mortra.powerplay-driver.v1"
SCOPE = ("certified controller growth on a declared evaluation set; "
         "charges proposal, rebuild and verification, including rejected rounds")


class CountingLibrary:
    """A controller that records how much reduction was spent through it.

    The gate is allowed to be expensive; it is not allowed to be expensive
    without saying so.
    """

    def __init__(self, library):
        self._library = library
        self.sha256 = library_digest(library)
        self.reductions = 0
        self.steps = 0

    def reduce(self, program, max_steps=1024):
        output, trace = self._library.reduce(program, max_steps=max_steps)
        self.reductions += 1
        self.steps += len(trace["steps"])
        return output, trace

    def replay(self, trace):
        return self._library.replay(trace)


def controller_from(certificates, provenance):
    """Build a controller from certificates only.

    Rules never arrive as data. They are derived from equalities that
    `build_library` re-verifies, which is where mathematical correctness is
    decided.
    """
    return RelationLibrary(build_library(list(certificates), dict(provenance)))


class Driver:
    def __init__(self, provenance, budget, criterion="final_output",
                 certificates=(), tasks=(), history=(), memory=None, spent=None):
        if type(budget) is not int or budget < 1:
            raise ValueError("a budget must be a positive exact integer")
        if criterion not in CRITERIA:
            raise ValueError(f"the reach criterion must be one of {CRITERIA}")
        self.provenance = dict(provenance)
        self.budget = budget
        self.criterion = criterion
        self.certificates = [deepcopy(c) for c in certificates]
        self.tasks = [deepcopy(t) for t in tasks]
        self.history = [deepcopy(h) for h in history]
        self.memory = deepcopy(memory) if memory is not None else None
        if self.memory is not None:
            replay_memory(self.memory)
        self.spent = dict(spent or {"rounds": 0, "accepted": 0,
                                    "proposal_reductions": 0, "gate_reductions": 0,
                                    "gate_steps": 0})

    # ---- what a proposer is allowed to read -------------------------------

    @property
    def controller(self):
        return controller_from(self.certificates, self.provenance)

    def constructions(self):
        """Programs that appeared in replayed identities, from build_memory."""
        return deepcopy(self.memory["constructions"]) if self.memory else []

    def context(self):
        """Everything acquired so far, handed to the proposer by construction."""
        return {"controller": self.controller,
                "tasks": deepcopy(self.tasks),
                "certificates": deepcopy(self.certificates),
                "constructions": self.constructions(),
                "accepted_history": [h for h in self.history if h["accepted"]],
                "budget": self.budget,
                "criterion": self.criterion,
                "spent": dict(self.spent)}

    def adopt_memory(self, memory):
        """Attach construction memory after replaying its provenance."""
        self.memory = deepcopy(replay_memory(memory))
        return self.constructions()

    # ---- one round --------------------------------------------------------

    def attempt(self, new_task, new_certificates, *, proposal_reductions=0):
        """Propose (task, modification), charge the round, keep it only if admitted."""
        before_raw = self.controller
        after_raw = controller_from(self.certificates + list(new_certificates),
                                    self.provenance)
        before = CountingLibrary(before_raw)
        after = CountingLibrary(after_raw)
        evidence = acceptance(before, after, new_task, self.tasks,
                              self.budget, self.criterion)

        charged = {"proposal_reductions": int(proposal_reductions),
                   "gate_reductions": before.reductions + after.reductions,
                   "gate_steps": before.steps + after.steps}
        record = {"schema": SCHEMA, "round": len(self.history),
                  "accepted": evidence["accepted"],
                  "new_task_id": new_task["id"],
                  "new_certificate_count": len(list(new_certificates)),
                  "controller_before": evidence["before_controller"],
                  "controller_after": evidence["after_controller"],
                  "judge": evidence["judge"],
                  "charged": charged,
                  "acceptance": evidence,
                  "scope": SCOPE}
        record["sha256"] = digest(record)

        self.spent["rounds"] += 1
        for field, value in charged.items():
            self.spent[field] += value
        if evidence["accepted"]:
            # Replayed against the raw controllers, so the count wrapper cannot
            # be what made the verdict come out right.
            replay_acceptance(evidence, before_raw, after_raw, new_task, self.tasks)
            self.certificates.extend(deepcopy(c) for c in new_certificates)
            self.tasks.append(deepcopy(new_task))
            self.spent["accepted"] += 1
        self.history.append(record)
        return record

    def run(self, proposer, *, rounds, candidates_per_round=1):
        """Give each candidate its own round; stop at the round budget.

        The proposer is called with the accumulated context every round, so a
        later proposal can use what an earlier round acquired. Running the loop
        is not by itself evidence that it did.
        """
        if type(rounds) is not int or rounds < 1:
            raise ValueError("a round budget must be a positive exact integer")
        produced = []
        for _ in range(rounds):
            taken = 0
            for candidate in proposer(self.context()):
                task, certificates = candidate["task"], candidate["certificates"]
                produced.append(self.attempt(
                    task, certificates,
                    proposal_reductions=candidate.get("proposal_reductions", 0)))
                taken += 1
                if taken >= candidates_per_round:
                    break
            if taken == 0:
                break
        return produced

    # ---- persistence ------------------------------------------------------

    def state(self):
        payload = {"schema": SCHEMA, "provenance": deepcopy(self.provenance),
                   "budget": self.budget, "criterion": self.criterion,
                   "certificates": deepcopy(self.certificates),
                   "tasks": deepcopy(self.tasks),
                   "history": deepcopy(self.history),
                   "memory": deepcopy(self.memory),
                   "spent": dict(self.spent),
                   "judge": task_digest(self.tasks, self.budget, self.criterion)
                            if self.tasks else None,
                   "controller": library_digest(self.controller),
                   "scope": SCOPE}
        payload["sha256"] = digest(payload)
        return payload

    @classmethod
    def restore(cls, payload):
        """Rebuild from stored state, refusing a state that does not replay."""
        if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
            raise ValueError("driver state must declare its schema")
        stored = dict(payload)
        if stored.pop("sha256", None) != digest(stored):
            raise ValueError("driver state digest does not match its contents")
        driver = cls(payload["provenance"], payload["budget"], payload["criterion"],
                     payload["certificates"], payload["tasks"], payload["history"],
                     payload["memory"], payload["spent"])
        if library_digest(driver.controller) != payload["controller"]:
            raise ValueError("stored certificates do not rebuild the stored controller")
        return driver
