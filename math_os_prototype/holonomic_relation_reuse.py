"""Replay ground series equalities inside new, domain-checked compositions.

Rules come only from saved exact certificates. They do not bind parameters or
claim a confluent/complete normal form. Every replacement strictly decreases a
term order, and its source equalities and occurrence path remain replayable.
"""
from collections import defaultdict, deque
from copy import deepcopy
from hashlib import sha256
import json

from math_os_prototype.holonomic_route_discovery import key, replay_certificate, validate

SCHEMA = "mortra.holonomic-ground-library.v1"
TRACE_SCHEMA = "mortra.holonomic-context-rewrite.v1"


def digest(value):
    return sha256(key(value).encode()).hexdigest()


def term_order(p):
    encoded = key(p)
    return (1 + sum(term_order(v)[0] for v in p.values() if isinstance(v, dict)),
            len(encoded), encoded)


def _compile(certificates):
    adjacency, programs = defaultdict(list), {}
    for cert in certificates:
        left, right = key(cert["left"]), key(cert["right"])
        programs[left], programs[right] = cert["left"], cert["right"]
        adjacency[left].append((right, cert["sha256"], "forward"))
        adjacency[right].append((left, cert["sha256"], "reverse"))
    rules, visited = [], set()
    for first in sorted(programs):
        if first in visited:
            continue
        component, queue = {first}, deque([first])
        while queue:
            for neighbor, _, _ in adjacency[queue.popleft()]:
                if neighbor not in component:
                    component.add(neighbor)
                    queue.append(neighbor)
        visited.update(component)
        representative = min(component, key=lambda p: term_order(programs[p]))
        for start in sorted(component - {representative}):
            queue, paths = deque([start]), {start: []}
            while representative not in paths:
                node = queue.popleft()
                for neighbor, certificate, direction in sorted(adjacency[node]):
                    if neighbor not in paths:
                        paths[neighbor] = paths[node] + [{"certificate": certificate, "direction": direction}]
                        queue.append(neighbor)
            rule = {"left": programs[start], "right": programs[representative],
                    "certificate_chain": paths[representative]}
            rule["id"] = digest(rule)
            rules.append(rule)
    return sorted(rules, key=lambda r: key(r["left"]))


def build_library(certificates, provenance):
    certificates = deepcopy(certificates)
    for cert in certificates:
        from math_os_prototype.holonomic_definition_screening import replay_definition_certificate
        replay = (replay_definition_certificate if cert.get("status") == "definition_only_equality"
                  else replay_certificate)
        if not replay(cert):
            raise ValueError("library contains an invalid exact certificate")
    result = {"schema": SCHEMA, "certificates": certificates, "rules": _compile(certificates),
              "provenance": deepcopy(provenance), "parameter_generalization": False,
              "scope": "Q[[x]] at zero; ground matches in validated series contexts",
              "confluence_or_completeness_claimed": False}
    result["sha256"] = digest(result)
    return result


def occurrences(p, path=()):
    if isinstance(p, dict):
        yield path, p
        children = ((field, p[field]) for field in sorted(p))
    elif isinstance(p, list):
        children = enumerate(p)
    else:
        return
    for field, value in children:
        if isinstance(value, (dict, list)):
            yield from occurrences(value, path + (field,))


def replace_at(p, path, replacement):
    if not path:
        return deepcopy(replacement)
    # deepcopy preserves aliases: detach every edge on the selected path so
    # a shared subtree elsewhere cannot be rewritten without its own step.
    result = deepcopy(p)
    result[path[0]] = replace_at(p[path[0]], path[1:], replacement)
    return result


class RelationLibrary:
    def __init__(self, library):
        expected = build_library(library["certificates"], library["provenance"])
        if expected != library:
            raise ValueError("library rules, scope, or digest failed replay")
        self.sha256 = expected["sha256"]
        self._rules = {key(r["left"]): r for r in expected["rules"]}
        self._ids = {r["id"]: r for r in expected["rules"]}

    @classmethod
    def load(cls, path):
        from math_os_prototype.shared_json import read
        return cls(read(path))

    def reduce(self, program, max_steps=1024):
        validate(program)
        current, steps = deepcopy(program), []
        if max_steps < 0:
            raise ValueError("negative rewrite budget")
        exhausted = False
        while True:
            match = next(((path, self._rules[key(sub)]) for path, sub in occurrences(current)
                          if key(sub) in self._rules), None)
            if match is None:
                break
            if len(steps) >= max_steps:
                exhausted = True
                break
            path, rule = match
            after = replace_at(current, path, rule["right"])
            validate(after)
            if not term_order(after) < term_order(current):
                raise ValueError("rewrite did not decrease the declared term order")
            steps.append({"path": list(path), "rule": rule["id"],
                          "before": digest(current), "after": digest(after)})
            current = after
        trace = {"schema": TRACE_SCHEMA, "library": self.sha256, "input": deepcopy(program),
                 "output": current, "steps": steps, "budget_exhausted": exhausted,
                 "scope": "exact equality in Q[[x]]; no special-value claim"}
        return current, trace

    def replay(self, trace):
        try:
            if (set(trace) != {"schema", "library", "input", "output", "steps", "budget_exhausted", "scope"}
                    or trace["schema"] != TRACE_SCHEMA or trace["library"] != self.sha256
                    or trace["scope"] != "exact equality in Q[[x]]; no special-value claim"
                    or not isinstance(trace["budget_exhausted"], bool)):
                return False
            validate(trace["input"])
            current = deepcopy(trace["input"])
            for step in trace["steps"]:
                if set(step) != {"path", "rule", "before", "after"}:
                    return False
                rule, sub = self._ids[step["rule"]], current
                for field in step["path"]:
                    sub = sub[field]
                if sub != rule["left"] or digest(current) != step["before"]:
                    return False
                after = replace_at(current, step["path"], rule["right"])
                validate(after)
                if digest(after) != step["after"] or not term_order(after) < term_order(current):
                    return False
                current = after
            if current != trace["output"]:
                return False
            applicable = any(key(sub) in self._rules for _, sub in occurrences(current))
            return applicable == trace["budget_exhausted"]
        except (ValueError, KeyError, TypeError, IndexError):
            return False
