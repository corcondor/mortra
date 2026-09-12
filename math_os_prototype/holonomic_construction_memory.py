"""Return terms of proved relations to the existing composition vocabulary."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from math_os_prototype.holonomic_joint_action_control import verify_prior
from math_os_prototype.holonomic_online_library import OnlineLibrary
from math_os_prototype.holonomic_route_discovery import key

SCHEMA = "mortra.proof-derived-construction-memory.v1"


def build_memory(records, source_library, excluded_programs, provenance):
    verify_prior(records)
    if source_library is not None:
        OnlineLibrary(source_library)
    excluded = {key(p) for p in excluded_programs}
    terms = {}
    for record in records:
        certificate = record["certificate"]
        for term in certificate["terms"]:
            program = record["features"][term["feature"]]["program"]
            encoded = key(program)
            if encoded in excluded:
                continue
            entry = terms.setdefault(encoded, {"program": deepcopy(program), "premises": []})
            premise = {"certificate": certificate["sha256"], "feature": term["feature"]}
            if premise not in entry["premises"]:
                entry["premises"].append(premise)
    result = {"schema": SCHEMA, "records": deepcopy(records),
              "source_library": deepcopy(source_library), "excluded_programs": deepcopy(excluded_programs),
              "provenance": deepcopy(provenance), "constructions": [terms[k] for k in sorted(terms)],
              "scope": "terms in replayed formal identities; not new primitive axioms or novelty"}
    result["sha256"] = sha256(key(result).encode()).hexdigest()
    return result


def replay_memory(memory):
    expected = build_memory(memory["records"], memory["source_library"],
                            memory["excluded_programs"], memory["provenance"])
    if memory != expected:
        raise ValueError("construction memory provenance or terms failed replay")
    return memory


def load_memory(path):
    from math_os_prototype.shared_json import read
    return replay_memory(read(path))


def initial_certificates(memory):
    if memory is None or memory["source_library"] is None:
        return []
    return memory["source_library"]["source_ground_library"]["certificates"]


def extend_seeds(seeds, memory):
    result, seen = deepcopy(seeds), {key(p) for p in seeds}
    if memory:
        for entry in memory["constructions"]:
            if key(entry["program"]) not in seen:
                result.append(deepcopy(entry["program"]))
                seen.add(key(entry["program"]))
    return result
