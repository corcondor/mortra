"""Conservative, structural reuse of certified fold representations.

Task names are display labels, not contracts. Fingerprints bind the executable
fold adapter; they are version checks, not proofs about arbitrary Python code.
Legacy certificates without this contract are not reusable by this path.
"""
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
import inspect
from pathlib import Path

import sympy as sp

from math_os_prototype import fold_observable_system as F
from math_os_prototype import rigid_fold_problem_discovery as folds
from math_os_prototype.representation_progress import digest


def _function_key(function):
    if function is None:
        return None
    try:
        source = inspect.getsource(function)
        captures = [repr(cell.cell_contents) for cell in (function.__closure__ or ())]
        return {"source": sha256(source.encode()).hexdigest(),
                "module": function.__module__, "captures": captures,
                "defaults": repr(function.__defaults__)}
    except (OSError, TypeError, AttributeError):
        return {"unsupported_callable": repr(function)}


def task_key(task):
    """The mathematical and executable contract, independent of the task name."""
    return {
        "action_system": {
            "alphabet": list(task.alphabet), "step": _function_key(task.step),
            "generators": [asdict(g) for g in folds.FOLD_GENERATORS],
            "kinematics_sha256": sha256(Path(folds.__file__).read_bytes()).hexdigest(),
            "adapter_sha256": sha256(Path(inspect.getfile(task.step)).read_bytes()).hexdigest(),
            "coordinates": list(F.VARIABLE_NAMES)},
        "coefficient_field": task.coefficient_field,
        "domain": {"coordinates": "integer doubled centre and reachable frame",
                   "state_arity": len(task.seed_state)},
        "required_observables": [str(sp.expand(sp.sympify(q))) for q in
                                 (task.observable_expression, *task.required_observables)
                                 if q is not None],
        "legality": {"always": task.legal_always,
                     "predicate": None if task.legal_always else _function_key(task.legal_step)},
        "goal": _function_key(task.goal_from_state),
        "counted": task.counted, "length_means": task.length_means,
    }


def coverage(certificate, task, premise):
    universal = (all(c["kind"] in ("proof", "structural") and c["holds"]
                     for c in certificate["checks"])
                 and bool(premise and premise.get("exact")
                          and premise.get("frames_closed")))
    return {"kind": "all_finite_words" if universal else "bounded_from_seed",
            "maximum_length": None if universal else certificate["depth"],
            "seed": [str(v) for v in task.seed_state],
            "frames": (premise or {}).get("verified_frames", []),
            "centre_domain": "Z^3", "coefficient_field": task.coefficient_field}


def representation_key(record):
    return digest({key: record[key] for key in ("basis", "action_matrices")})


def ensure_scope(certificate, task, length):
    """Never extend finite congruence checks to untested depths or starts."""
    if length < 0:
        raise ValueError("length must be nonnegative")
    scope = certificate.get("coverage")
    if scope is None:
        # Existing callers can still use old certificates, conservatively.
        if any(c.get("kind") == "no counterexample within depth"
               for c in certificate.get("checks", [])) and length > certificate["depth"]:
            raise ValueError("length exceeds the bounded certificate scope")
        return
    if scope["kind"] == "bounded_from_seed":
        if length > scope["maximum_length"] or scope["seed"] != [str(v) for v in task.seed_state]:
            raise ValueError("length or initial state exceeds the bounded certificate scope")
    else:
        frame = [list(task.seed_state[3 + 3*i:6 + 3*i]) for i in range(3)]
        if frame not in scope["frames"] or any(sp.sympify(v).is_Integer is not True
                                               for v in task.seed_state[:12]):
            raise ValueError("initial state is outside the certified integer frame domain")


def compatible_certificate(representation, certificate, task, lengths=()):
    """Use the stored proof; derive only a readout in its already certified space."""
    from math_os_prototype import representation_certificate as C
    old = certificate.get("reuse_key")
    new = task_key(task)
    if not certificate.get("admissible") or not old or not certificate.get("coverage"):
        return None
    if certificate.get("representation_key") != representation_key(representation):
        return None
    for key in ("action_system", "coefficient_field", "domain", "legality", "goal",
                "counted", "length_means"):
        if old.get(key) != new[key]:
            return None
    if task.observable_expression is None or task.coefficient_field != "QQ":
        return None
    if not representation.get("identity_residuals_all_zero"):
        return None
    if not representation.get("step_premise", {}).get("exact"):
        return None
    try:
        if sp.expand(task.value(F.VARIABLES) - task.observable_expression) != 0:
            return None
        for length in lengths or (0,):
            ensure_scope(certificate, task, length)
        closure = F.closure_from_record(representation)
        readouts = [C.span_membership(closure, q) for q in
                    (task.observable_expression, *task.required_observables)]
        if not all(row and row["member"] for row in readouts):
            return None
    except (ValueError, TypeError, KeyError, IndexError):
        return None
    result = deepcopy(certificate)
    result.update(task=task.name, reuse_key=new, readout=readouts[0]["coefficients"],
                  required_readouts=readouts[1:],
                  start_observation=[str(v) for v in C.compiled_observation(closure)(task.seed_state)])
    for check in result["checks"]:
        if check["name"] == "observable":
            check["coefficients"] = readouts[0]["coefficients"]
            check["required_expression"] = str(task.observable_expression)
        if check["name"] == "start":
            check["observation"] = result["start_observation"]
    result["reused_certificate"] = {"source_task": certificate["task"],
                                    "source_key": digest(old),
                                    "new_key": digest(new),
                                    "scope": deepcopy(certificate["coverage"]),
                                    "readout_check": "exact polynomial span membership"}
    return result
