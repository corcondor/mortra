"""Exact input/output summaries of already certified rational construction DAGs.

Under P, triangular uniqueness and the retained rational witness give
exists(private).C <=> Q. This is witness elimination, not general QE.
"""
from copy import deepcopy
import time
import sympy as sp
from math_os_prototype import geometry_contracts as gc
from math_os_prototype.representation_progress import digest


def infer_interface(steps, selected_outputs, final_outputs):
    selected = set(selected_outputs)
    produced = [s["output"] for s in steps]
    if len(set(produced)) != len(produced) or not selected <= set(produced):
        raise ValueError("invalid single-assignment sub-DAG")
    all_outputs, available = set(produced), set()
    for step in steps:
        if any(p in all_outputs and p not in available for p in step["inputs"]):
            raise ValueError("construction DAG is not topological")
        available.add(step["output"])
    if not set(final_outputs) <= all_outputs:
        raise ValueError("undeclared final output")
    inputs = list(dict.fromkeys(p for s in steps if s["output"] in selected
                                for p in s["inputs"] if p not in selected))
    boundary = {p for s in steps if s["output"] not in selected for p in s["inputs"] if p in selected}
    public = (set(final_outputs) & selected) | boundary
    return {"external_inputs": inputs,
            "final_outputs": [p for p in produced if p in selected and p in final_outputs],
            "boundary_outputs": [p for p in produced if p in boundary],
            "public_outputs": [p for p in produced if p in public],
            "private_locals": [p for p in produced if p in selected-public]}


def source_interfaces(contract, corpus):
    """Project the actual source sub-DAG's outside references onto H's locals."""
    proofs = {c["source_proof"]: c["program"] for c in corpus}
    boundaries, evidence = set(), []
    for source in contract.get("source_proof_traces", []):
        whole, final = gc.dag(proofs[source["source_proof"]])
        by_term = {digest(s["term"]): s["output"] for s in whole}
        for match in source["matches"]:
            def substitute(node):
                if node["op"] == "var":
                    return deepcopy(match["binding"][node["name"]])
                return {"op": node["op"], "args": [substitute(a) for a in node["args"]]}
            mapping = {s["output"]: by_term[digest(substitute(s["term"]))] for s in contract["composition"]}
            interface = infer_interface(whole, mapping.values(), [final, mapping[contract["output"]]])
            boundaries.update(n for n, actual in mapping.items() if actual in interface["boundary_outputs"])
            evidence.append({"source_proof": source["source_proof"], "match_path": match["path"],
                             "local_mapping": mapping, "interface": interface})
    return sorted(boundaries), evidence


def effect_signature(polynomials, symbols, outputs):
    """A conservative shape signature, not a test that a goal is reachable."""
    values = [gc.parse(e, symbols) if isinstance(e, str) else e for e in polynomials]
    return {"output_type": "Point", "coefficient_field": "QQ",
            "linear_output": all(sp.Poly(v, *outputs).total_degree() <= 1 for v in values),
            "affine_all_coordinates": all(sp.Poly(v, *symbols.values()).total_degree() <= 1 for v in values)}


def compile_summary(contract, boundary_outputs=()):
    started = time.perf_counter()
    valid, replay_cost = gc.replay_contract(contract)
    if not valid or contract["representation_scopes"] != gc.SCOPE:
        raise ValueError("summary requires the exact declared contract")
    steps = contract["composition"]
    outputs = [s["output"] for s in steps]
    if not set(boundary_outputs) <= set(outputs):
        raise ValueError("unknown boundary output")
    # An outside read is modeled as an external consumer, so classification is
    # the same for a source sub-DAG and for a public interface request.
    external = [{"output": f"consumer{i}", "inputs": [p]} for i, p in enumerate(boundary_outputs)]
    occupied = set(outputs) | {p for s in steps for p in s["inputs"]}
    while any(s["output"] in occupied for s in external):
        external = [{**s, "output": "external_"+s["output"]} for s in external]
    interface = infer_interface([*steps, *external], outputs, [contract["output"]])
    names = [p["name"] for p in contract["typed_parameters"]]
    symbols = {n+a: sp.Symbol(n+a, real=True) for n in names for a in ("x", "y")}
    allowed = set(contract["applicability"]["input_nonzero_polynomials"])
    equations, witness, denominators, checks = {}, {}, set(), 0
    for output in interface["public_outputs"]:
        coords = [sp.Symbol(output+a, real=True) for a in ("x", "y")]
        values = [gc.parse(e, symbols) for e in contract["witness"][output]]
        polys = []
        for coordinate, value in zip(coords, values):
            numerator, denominator = sp.cancel(value).as_numer_denom()
            required = set(gc.factors(denominator))
            if not required <= allowed:
                raise ValueError("summary denominator outside certificate P")
            denominators.update(required)
            poly = sp.expand(denominator*coordinate-numerator)
            checks += 1
            if not gc.exact_zero(poly.subs(coordinate, value)):
                raise ValueError("summary witness identity failed")
            polys.append(str(poly))
        equations[output] = polys
        witness[output] = list(map(str, values))
    all_symbols = {**symbols, **{p+a: sp.Symbol(p+a, real=True) for p in interface["public_outputs"] for a in ("x", "y")}}
    summary = {"version": 1, "contract_id": contract["id"], "scope": gc.SCOPE,
        "interface": interface, "P": deepcopy(contract["applicability"]),
        "R": {"exists_points": interface["private_locals"], "body_contract_id": contract["id"]},
        "Q": equations, "public_witness": witness,
        "certificate": {"method": "triangular_uniqueness_plus_denominator_clearing",
            "equivalence_under_P": True, "required_denominators": sorted(denominators),
            "identity_checks": checks, "all_real_inputs_under_P": True},
        "effect_signature": effect_signature([e for rows in equations.values() for e in rows], all_symbols,
            [all_symbols[p+a] for p in interface["public_outputs"] for a in ("x", "y")])}
    summary["id"] = "summary."+digest(summary)[:20]
    return summary, {"seconds": time.perf_counter()-started, "summary_identity_calls": checks,
                     "contract_replay": replay_cost}


def replay_summary(contract, summary):
    rebuilt, cost = compile_summary(contract, summary["interface"]["boundary_outputs"])
    return rebuilt == summary, cost
