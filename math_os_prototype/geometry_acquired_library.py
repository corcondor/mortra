"""The solver's library, extended with operations acquired while solving.

`RelationalSynthesis` reaches a library through four members only:
`candidates(patterns)`, `certified(index, pattern)`, `programs[index]` and
`costs["exact_certifications"]`. `ContractIndex` provides them for the
task-independent enumeration and has no way to take a new program. This class
provides the same four members over the enumerated programs plus the ones
acquired at runtime, so an operation certified by `geometry_relational_edit`
becomes reachable by the same retrieval path, with no change to the solver.

An acquired entry answers `certified` from the certificate `define` produced,
which is the same exact decision procedure the enumerated entries use, run once
at definition time instead of once per retrieval.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy

from math_os_prototype import geometry_relational_dsl as rdsl
from math_os_prototype import geometry_relational_library as lib
from math_os_prototype.representation_progress import digest

SLOTS = ("p0", "p1", "p2")


class AcquiredLibrary:
    """Enumerated programs and acquired operations behind one retrieval interface."""

    def __init__(self, base=None):
        self.base = base
        self.programs = [deepcopy(p) for p in base.programs] if base is not None else []
        self.membership = {k: set(v) for k, v in base.membership.items()} if base is not None else {}
        self.ordered = {k: list(v) for k, v in base.ordered.items()} if base is not None else {}
        self.costs = Counter(dict(base.costs)) if base is not None else Counter()
        self.certificates = {}
        self.acquired = {}
        # the definitions behind the acquired programs, kept so that a later
        # acquisition can be built out of them rather than beside them
        self.definitions = {}
        self.enumerated_count = len(self.programs)

    # -- the solver's interface --------------------------------------------
    def candidates(self, patterns):
        patterns = list(patterns)
        if any(pattern not in self.membership for pattern in patterns):
            return []
        first = min(patterns, key=lambda pattern: len(self.membership[pattern]))
        return [index for index in self.ordered[first]
                if all(index in self.membership[pattern] for pattern in patterns)]

    def certified(self, index, pattern):
        entry = self.acquired.get(index)
        if entry is not None:
            certificate = entry["certificates"].get(pattern)
            if certificate is not None:
                self.costs["acquired_certificates_reused"] += 1
            return certificate
        key = (index, pattern)
        if key not in self.certificates:
            self.costs["exact_certifications"] += 1
            self.certificates[key] = lib.certify_entry(pattern[0], pattern[1], self.programs[index])
            if self.certificates[key] is None:
                self.costs["float_candidates_refused_exactly"] += 1
        return self.certificates[key]

    # -- registration -------------------------------------------------------
    def register(self, program, certificates, *, source):
        """Add one acquired operation. `certificates` maps a canonical pattern to its certificate."""
        if not certificates:
            raise ValueError("an acquired operation must carry at least one certified pattern")
        index = len(self.programs)
        self.programs.append(deepcopy(program))
        self.acquired[index] = {"certificates": dict(certificates), "source": dict(source),
                                "steps": len(program["steps"])}
        for pattern in certificates:
            self.membership.setdefault(pattern, set()).add(index)
            self.ordered[pattern] = sorted(self.membership[pattern],
                                           key=lambda i: (len(self.programs[i]["steps"]), i))
        self.costs["acquired_operations"] += 1
        return index

    def holds(self, program):
        """Whether an identical program is already indexed, by its canonical expansion."""
        key = _program_key(program)
        return any(_program_key(existing) == key for existing in self.programs)

    def state(self):
        return {"enumerated": self.enumerated_count, "acquired": len(self.acquired),
                "definitions": len(self.definitions),
                "generations": sorted({entry["source"].get("generation", 1)
                                       for entry in self.acquired.values()}),
                "patterns": len(self.membership),
                "digest": digest([self.programs,
                                  sorted([[k[0], list(k[1]), sorted(v)] for k, v in self.membership.items()])]),
                "acquired_operations": [
                    {"index": index, "steps": entry["steps"],
                     "patterns": [[p[0], list(p[1])] for p in entry["certificates"]],
                     "source": entry["source"]}
                    for index, entry in sorted(self.acquired.items())]}


def _program_key(program):
    names = {p: p for p in program["params"]}
    rendered = []
    for step in program["steps"]:
        names[step["out"]] = f"#{len(rendered)}"
        rendered.append([step["prim"], [names[a] for a in step["args"]]])
    return digest([rendered, names[program["result"]]])
