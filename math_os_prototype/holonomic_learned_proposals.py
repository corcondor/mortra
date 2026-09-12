"""Offer compound terms mined from already certified parameter identities.

No conclusion is supplied to the prover. Rule-derived candidates and their
descendants must be excluded from description-progress training probes.
Each new template uses a frozen, bounded set of observed positive parameters.
"""
from copy import deepcopy

from math_os_prototype.holonomic_parametric_learning import instantiate, names
from math_os_prototype.holonomic_online_library import OnlineLibrary
from math_os_prototype.holonomic_relation_reuse import digest
from math_os_prototype.holonomic_route_discovery import rational, validate
from math_os_prototype.research_indexed_agenda import ResearchIndexedAgenda


def compound_size(term):
    if not isinstance(term, dict) or "op" not in term:
        return 0
    return 1 + sum(compound_size(v) for v in term.values())


def observed_parameters(pool, limit=32):
    values = {}
    for entry in pool.entries:
        stack = [entry["program"]]
        while stack:
            term = stack.pop()
            if term["op"] == "hyper":
                for value in term["a"] + term["b"]:
                    q = rational(value)
                    if q > 0 and (str(q) in values or len(values) < limit):
                        values.setdefault(str(q), entry["id"])
            stack.extend(v for v in term.values() if isinstance(v, dict) and "op" in v)
    return [{"value": q, "parent": parent} for q, parent in values.items()]


class LearnedSeriesProposals:
    def __init__(self, every):
        if type(every) is not int or every < 1:
            raise ValueError("positive learned-proposal interval required")
        self.every, self.round = every, 0
        self.agenda = ResearchIndexedAgenda()
        self.templates, self.seen = [], set()

    def sync(self, pool, library):
        # Library construction already replays all guards and exact certificates.
        if not isinstance(library, OnlineLibrary):
            raise ValueError("learned proposals require a replayed online library")
        values = None
        for rule in library.parametric.rules:
            for side in ("left", "right"):
                term = rule["template"][side]
                variables = sorted(names(term))
                identifier = digest(term)
                if (identifier in self.seen or compound_size(term) < 2
                        or not variables):
                    continue
                function_mode = all(v.startswith("f") for v in variables)
                if function_mode:
                    current_values = [{"value": deepcopy(e["program"]), "parent": e["id"]}
                                      for e in pool.entries[:32]]
                elif values is None:
                    values = observed_parameters(pool)
                    current_values = values
                else:
                    current_values = values
                if not current_values:
                    continue
                self.seen.add(identifier)
                self.agenda.admit(identifier, len(current_values)**len(variables))
                self.templates.append({"template": deepcopy(term), "template_sha256": identifier,
                    "library_sha256": library.sha256, "rule": rule["id"], "side": side,
                    "parameters": variables, "values": deepcopy(current_values)})
                if function_mode:
                    self.templates[-1]["binding_kind"] = "arbitrary_formal_series"

    def offer(self, pool, library):
        self.sync(pool, library)
        index = self.round
        self.round += 1
        before = self.agenda.digest()
        item = self.agenda.pop() if index % self.every == 0 else None
        receipt = {"round": index, "before_sha256": before,
                   "after_sha256": self.agenda.digest(), "item": item}
        if item is None:
            return None, receipt
        source = self.templates[item["stream_id"]]
        offset, binding, parents = item["offset"], {}, []
        for name in source["parameters"]:
            offset, j = divmod(offset, len(source["values"]))
            value = source["values"][j]
            binding[name] = value["value"]
            if value["parent"] not in parents:
                parents.append(value["parent"])
        program = instantiate(source["template"], binding)
        validate(program)
        return {"program": program, "parents": parents,
                "proposal_origin": ("learned_function_template" if source.get("binding_kind") == "arbitrary_formal_series"
                                    else "learned_parameter_template"),
                "learned_construction": {k: deepcopy(source[k]) for k in
                    ("template_sha256", "library_sha256", "rule", "side")} | {"binding": binding}}, receipt

    def snapshot(self):
        return {"schema": "mortra.learned-series-proposals.v1", "every": self.every,
                "round": self.round, "agenda": self.agenda.snapshot(),
                "templates": deepcopy(self.templates), "parameter_limit": 32,
                "known_rule_instances_are_not_new_theorems": True}
