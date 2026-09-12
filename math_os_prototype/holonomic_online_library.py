"""Compose existing ground and guarded-parameter proofs without adding identities."""
from copy import deepcopy

from math_os_prototype.holonomic_parametric_learning import FUNCTION_STRATEGIES, ParametricLibrary
from math_os_prototype.holonomic_relation_reuse import RelationLibrary
from math_os_prototype.holonomic_route_discovery import validate

SCHEMA = "mortra.online-context-rewrite.v1"
SCOPE = "exact equality in Q[[x]]; ground and positive-parameter rules; no special-value claim"


class OnlineLibrary:
    def __init__(self, data):
        self.parametric = ParametricLibrary(data)
        self.ground = RelationLibrary(data["source_ground_library"])
        self.sha256 = data["sha256"]
        self.rules = self.parametric.rules
        self.scope = ("exact equality in Q[[x]]; ground and arbitrary-function rules; no special-value claim"
                      if data.get("template_strategy") in FUNCTION_STRATEGIES else SCOPE)
        if data.get("template_strategy") == "typed_union":
            self.scope = "exact equality in Q[[x]]; ground, arbitrary-function and guarded numeric rules; no special-value claim"

    def next_step(self, program):
        for kind, library in (("parametric", self.parametric), ("ground", self.ground)):
            after, trace = library.reduce(program, max_steps=1)
            if trace["steps"]:
                return after, {"kind": kind, "rule": trace["steps"][0]["rule"], "trace": trace}
        return None

    def reduce(self, program, max_steps=1024):
        validate(program)
        if max_steps < 0:
            raise ValueError("negative rewrite budget")
        current, steps = deepcopy(program), []
        while True:
            found = self.next_step(current)
            if found is None or len(steps) >= max_steps:
                break
            current, step = found
            steps.append(step)
        return current, {"schema": SCHEMA, "library": self.sha256, "input": deepcopy(program),
                         "output": current, "steps": steps, "budget_exhausted": found is not None,
                         "scope": self.scope}

    def replay(self, trace):
        try:
            if (set(trace) != {"schema", "library", "input", "output", "steps", "budget_exhausted", "scope"}
                    or trace["schema"] != SCHEMA or trace["library"] != self.sha256
                    or trace["scope"] != self.scope or not isinstance(trace["budget_exhausted"], bool)):
                return False
            validate(trace["input"])
            current = trace["input"]
            for step in trace["steps"]:
                if set(step) != {"kind", "rule", "trace"}:
                    return False
                library = {"parametric": self.parametric, "ground": self.ground}[step["kind"]]
                inner = step["trace"]
                if (inner["input"] != current or len(inner["steps"]) != 1
                        or inner["steps"][0]["rule"] != step["rule"] or not library.replay(inner)):
                    return False
                current = inner["output"]
            return current == trace["output"] and (self.next_step(current) is not None) == trace["budget_exhausted"]
        except (ValueError, KeyError, TypeError, IndexError):
            return False
