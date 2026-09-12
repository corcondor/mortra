"""Infer parameter patterns from saved equalities; prove by coefficient induction.

The default uses coefficient ratios. Optional ODE proofs and parameter-ray
hypotheses expand that scope without accepting finite-prefix coincidences.
"""
from copy import deepcopy
from itertools import combinations
import json
import re

import sympy as sp

from math_os_prototype.holonomic_route_discovery import key, rational, validate
from math_os_prototype.holonomic_relation_reuse import (
    RelationLibrary, digest, occurrences, replace_at, term_order,
)

SCHEMA = "mortra.holonomic-parametric-library.v1"
CERT_SCHEMA = "mortra.coefficient-ratio-identity.v1"
TRACE_SCHEMA = "mortra.parametric-context-rewrite.v1"
N = sp.Symbol("n", integer=True, nonnegative=True)
FUNCTION_STRATEGIES = {"abstract_functions", "abstract_subexpressions"}
DEFINITION_LEARNING_STRATEGIES = FUNCTION_STRATEGIES | {"typed_union"}


def validate_learning_mode(proof_backend, template_strategy):
    if proof_backend not in {"coefficient_ratio", "uniform_ode", "formal_function", "typed_dispatch"}:
        raise ValueError("unknown parameter proof backend")
    if template_strategy not in {"paired", "paired_and_rays"} | DEFINITION_LEARNING_STRATEGIES:
        raise ValueError("unknown parameter hypothesis strategy")
    if (proof_backend == "typed_dispatch") != (template_strategy == "typed_union"):
        raise ValueError("typed union requires typed proof dispatch")
    if (proof_backend == "formal_function") != (template_strategy in FUNCTION_STRATEGIES):
        raise ValueError("function abstraction requires the arbitrary-function verifier")


def parameter(p):
    if (not isinstance(p, dict) or set(p) not in ({"parameter"}, {"parameter", "multiplier"})
            or not re.fullmatch(r"p\d+", str(p["parameter"]))):
        return False
    try:
        return rational(p.get("multiplier", 1)) > 0
    except (ValueError, TypeError):
        return False


def series_parameter(p):
    return (isinstance(p, dict) and set(p) == {"series_parameter"}
            and isinstance(p["series_parameter"], str)
            and re.fullmatch(r"f\d+", p["series_parameter"]) is not None)


def abstract_functions(relation):
    """Replace observed opaque atoms, not operations or numeric constants."""
    variables, samples = {}, {}

    def walk(value):
        if isinstance(value, dict) and value.get("op") in {"hyper", "ode"}:
            encoded = key(value)
            if encoded not in variables:
                name = f"f{len(variables)}"
                variables[encoded], samples[name] = name, [deepcopy(value)]
            return {"series_parameter": variables[encoded]}
        if isinstance(value, dict):
            return {k: walk(v) for k, v in sorted(value.items())}
        if isinstance(value, list):
            return [walk(v) for v in value]
        return value

    for value in relation.values():
        validate(value)
    template = walk(relation)
    if not variables:
        raise ValueError("no opaque function to abstract")
    return template, samples


def abstract_subexpressions(relation):
    """Enumerate bounded shared-subterm cuts; no inferred identity is assumed."""
    for side in relation.values():
        validate(side)
    trees = [{key(sub): sub for _, sub in occurrences(relation[side])}
             for side in ("left", "right")]
    common = sorted(set(trees[0]) & set(trees[1]), key=lambda s: (-len(s), s))
    # Opaque leaves are abstracted in every candidate, irrespective of the cut.
    common = [s for s in common if trees[0][s]["op"] not in {"hyper", "ode"}][:16]
    cuts = [(), *[(s,) for s in common], *combinations(common, 2)]
    if len(common) > 2:
        cuts.append(tuple(common))
    seen = set()
    for cut in cuts:
        selected, variables, samples = set(cut), {}, {}

        def walk(value):
            if isinstance(value, dict) and "op" in value:
                encoded = key(value)
                if encoded in selected or value["op"] in {"hyper", "ode"}:
                    if encoded not in variables:
                        name = f"f{len(variables)}"
                        variables[encoded], samples[name] = name, [deepcopy(value)]
                    return {"series_parameter": variables[encoded]}
            if isinstance(value, dict):
                return {k: walk(v) for k, v in sorted(value.items())}
            if isinstance(value, list):
                return [walk(v) for v in value]
            return value

        template = walk(relation)
        encoded = key(template)
        if not samples or encoded in seen:
            continue
        seen.add(encoded)
        if instantiate(template, {k: v[0] for k, v in samples.items()}) != relation:
            raise ValueError("subexpression abstraction does not reconstruct its source")
        yield template, samples


def numeric(v):
    try:
        return rational(v)
    except (ValueError, TypeError):
        return None


def anti_unify(first, second):
    """Least general shared tree, with repeated numeric pairs sharing a variable."""
    variables, samples = {}, {}

    def walk(a, b):
        qa, qb = numeric(a), numeric(b)
        if qa is not None and qb is not None:
            if qa == qb:
                return str(qa)
            pair = str(qa), str(qb)
            if pair not in variables:
                name = f"p{len(variables)}"
                variables[pair], samples[name] = name, list(pair)
            return {"parameter": variables[pair]}
        if isinstance(a, dict) and isinstance(b, dict) and set(a) == set(b):
            return {k: walk(a[k], b[k]) for k in sorted(a)}
        if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
            return [walk(x, y) for x, y in zip(a, b)]
        if type(a) is type(b) and a == b:
            return a
        raise ValueError("incompatible expression trees")

    template = walk(first, second)
    if not variables:
        raise ValueError("no variable was inferred")
    return template, samples


def names(value):
    if series_parameter(value):
        return {value["series_parameter"]}
    if parameter(value):
        return {value["parameter"]}
    if isinstance(value, dict):
        return set().union(*(names(v) for v in value.values()))
    if isinstance(value, list):
        return set().union(*(names(v) for v in value))
    return set()


def instantiate(template, binding):
    if series_parameter(template):
        result = deepcopy(binding[template["series_parameter"]])
        validate(result)
        return result
    if parameter(template):
        return str(rational(template.get("multiplier", 1))*rational(binding[template["parameter"]]))
    if isinstance(template, dict):
        return {k: instantiate(v, binding) for k, v in template.items()}
    if isinstance(template, list):
        return [instantiate(v, binding) for v in template]
    return template


def symbolic(value, symbols):
    return (rational(value.get("multiplier", 1))*symbols[value["parameter"]]
            if parameter(value) else rational(value))


def parameter_ray(relation):
    """Hypothesize common rescaling of every positive hypergeometric slot.

    No theorem is assumed: every proposed ray still needs a uniform proof.
    Maps, derivatives, sums and scalar normalizations are left unchanged.
    """
    anchor = None

    def walk(value):
        nonlocal anchor
        if isinstance(value, dict) and value.get("op") == "hyper":
            out = deepcopy(value)
            for field in ("a", "b"):
                out[field] = []
                for v in value[field]:
                    q = rational(v)
                    if q <= 0:
                        raise ValueError("ray requires positive hypergeometric slots")
                    if anchor is None:
                        anchor = q
                    scalar = {"parameter": "p0"}
                    if q != anchor:
                        scalar["multiplier"] = str(q/anchor)
                    out[field].append(scalar)
            return out
        if isinstance(value, dict):
            return {k: walk(v) for k, v in sorted(value.items())}
        if isinstance(value, list):
            return [walk(v) for v in value]
        return value

    template = walk(relation)
    if anchor is None:
        raise ValueError("ray has no hypergeometric slots")
    if instantiate(template, {"p0": str(anchor)}) != relation:
        # Ground programs accept integer scalars as well as rational strings.
        def normalize(value):
            q = numeric(value)
            if q is not None:
                return str(q)
            if isinstance(value, dict):
                return {k: normalize(v) for k, v in value.items()}
            if isinstance(value, list):
                return [normalize(v) for v in value]
            return value
        if normalize(instantiate(template, {"p0": str(anchor)})) != normalize(relation):
            raise ValueError("ray does not reconstruct source")
    return template, {"p0": [str(anchor)]}


def coefficient_recurrence(p, symbols):
    """Return c(0), R(n) with c(n+1)=R(n)c(n), on the positive guard."""
    op = p.get("op")
    fields = {"hyper": {"op", "a", "b"}, "diff": {"op", "child"},
              "scale": {"op", "child", "factor"},
              "pullback": {"op", "child", "numerator", "denominator"}}
    if op not in fields or set(p) != fields[op]:
        raise ValueError("no supported coefficient recurrence for this operation")
    if op == "hyper":
        a, b = [symbolic(v, symbols) for v in p["a"]], [symbolic(v, symbols) for v in p["b"]]
        if not a or len(a) > 5 or len(b) > 4 or len(a) > len(b)+1:
            raise ValueError("unsupported order")
        if any(v.is_positive is not True for v in a+b):
            raise ValueError("positive hypergeometric parameters are required")
        return sp.S.One, sp.prod(N+v for v in a)/((N+1)*sp.prod(N+v for v in b))
    initial, ratio = coefficient_recurrence(p["child"], symbols)
    if op == "diff":
        return sp.cancel(initial*ratio.subs(N, 0)), sp.cancel((N+2)*ratio.subs(N, N+1)/(N+1))
    if op == "scale":
        factor = symbolic(p["factor"], symbols)
        if factor.is_zero is not False:
            raise ValueError("nonzero scale is not proved")
        return factor*initial, ratio
    num, den = [symbolic(v, symbols) for v in p["numerator"]], [symbolic(v, symbols) for v in p["denominator"]]
    if (len(num) != 2 or num[0] != 0 or num[1].is_zero is not False or not den
            or den[0].is_zero is not False or any(v != 0 for v in den[1:])):
        raise ValueError("only linear substitutions preserve the supported recurrence")
    return initial, sp.cancel(num[1]*ratio/den[0])


def certify_template(template, *, proof_backend="coefficient_ratio"):
    if proof_backend == "typed_dispatch":
        variables = names(template)
        if variables and all(re.fullmatch(r"f\d+", v) for v in variables):
            return certify_template(template, proof_backend="formal_function")
        if variables and all(re.fullmatch(r"p\d+", v) for v in variables):
            return certify_template(template, proof_backend="uniform_ode")
        raise ValueError("no supported proof route for mixed or absent parameter types")
    if proof_backend == "formal_function":
        from math_os_prototype.holonomic_definition_screening import certify_definition_equal
        if set(template) != {"left", "right"}:
            raise ValueError("invalid function template")
        variables = sorted(names(template))
        if not variables or any(not re.fullmatch(r"f\d+", v) for v in variables):
            raise ValueError("formal-function proof requires function-valued parameters only")
        def contains_source(value):
            if isinstance(value, dict):
                return value.get("op") in {"hyper", "ode"} or any(contains_source(v) for v in value.values())
            return isinstance(value, list) and any(contains_source(v) for v in value)
        if contains_source(template):
            raise ValueError("unabstracted source function")
        # These distinct nodes are labels for uninterpreted functions in the
        # definition verifier. No hypergeometric identity or ODE is used here.
        markers = {v: {"op": "hyper", "a": [str(i+1)], "b": []}
                   for i, v in enumerate(variables)}
        ground = instantiate(template, markers)
        for side in ground.values():
            validate(side)
            if any(sub["op"] in {"ode", "hyper"} and sub not in markers.values()
                   for _, sub in occurrences(side)):
                raise ValueError("unabstracted source function")
        proof = certify_definition_equal(ground["left"], ground["right"])
        if proof is None:
            return {"status": "not_a_symbolic_identity"}
        result = {"schema": "mortra.arbitrary-series-identity.v1",
                  "status": "exact_parametric_coefficient_identity", "template": deepcopy(template),
                  "guards": {v: "arbitrary series in Q[[x]]" for v in variables},
                  "proof": proof, "scope": "formal calculus; no new mathematical axiom or special-value claim"}
        return result | {"sha256": digest(result)}
    if proof_backend not in {"coefficient_ratio", "uniform_ode"}:
        raise ValueError("unknown parameter proof backend")
    if proof_backend == "uniform_ode":
        try:
            return certify_template(template)
        except ValueError:
            from math_os_prototype.holonomic_parameter_ode import certify_parameter_ode
            return certify_parameter_ode(template)
    if set(template) != {"left", "right"}:
        raise ValueError("invalid relation template")
    variables = sorted(names(template))
    if not variables:
        raise ValueError("parameter-free relations belong in the ground library")
    symbols = {v: sp.Symbol(v, positive=True) for v in variables}
    initial_l, ratio_l = coefficient_recurrence(template["left"], symbols)
    initial_r, ratio_r = coefficient_recurrence(template["right"], symbols)
    initial_residual, ratio_residual = sp.cancel(initial_l-initial_r), sp.cancel(ratio_l-ratio_r)
    if initial_residual != 0 or ratio_residual != 0:
        return {"status": "not_a_symbolic_identity", "initial_residual": str(initial_residual),
                "ratio_residual": str(ratio_residual)}
    result = {"schema": CERT_SCHEMA, "status": "exact_parametric_coefficient_identity",
              "template": deepcopy(template), "guards": {v: "positive rational" for v in variables},
              "initial": str(sp.cancel(initial_l)), "coefficient_ratio": str(sp.cancel(ratio_l)),
              "proof": "same initial coefficient and same rational recurrence for every integer n >= 0",
              "domain": "positive parameters; all recurrence denominators nonzero for n >= 0",
              "scope": "Q[[x]] at zero; no endpoint or special-value claim", "backend": sp.__version__}
    result["sha256"] = digest(result)
    return result


def learn_templates(ground, *, proof_backend="coefficient_ratio", template_strategy="paired"):
    validate_learning_mode(proof_backend, template_strategy)
    if template_strategy == "typed_union":
        return learn_typed_templates(ground)
    RelationLibrary(ground)
    candidates, accepted, seen = [], [], set()
    for a, b in (combinations(ground["rules"], 2) if template_strategy not in FUNCTION_STRATEGIES else []):
        row = {"source_rules": [a["id"], b["id"]]}
        try:
            template, samples = anti_unify({k: a[k] for k in ("left", "right")},
                                           {k: b[k] for k in ("left", "right")})
            row.update({"template": template, "support_bindings": samples})
            if any(rational(v) <= 0 for values in samples.values() for v in values):
                raise ValueError("support outside the declared positive parameter domain")
            if key(template) in seen:
                row["status"] = "duplicate_template"
            else:
                seen.add(key(template))
                proof = certify_template(template, proof_backend=proof_backend)
                row["status"] = proof["status"]
                row["certificate"] = proof
                if proof["status"] == "exact_parametric_coefficient_identity":
                    accepted.append({"id": digest(template), "template": template, "certificate": proof,
                                     "source_rules": row["source_rules"], "support_bindings": samples})
        except (ValueError, TypeError, KeyError) as exc:
            row.update({"status": "unsupported", "diagnostic": str(exc)})
        candidates.append(row)
    if template_strategy in {"paired_and_rays", "abstract_functions"}:
        for rule in ground["rules"]:
            row = {"source_rules": [rule["id"]], "generalization":
                   "arbitrary_formal_functions" if template_strategy == "abstract_functions" else "positive_parameter_ray"}
            try:
                abstraction = abstract_functions if template_strategy == "abstract_functions" else parameter_ray
                template, samples = abstraction({k: rule[k] for k in ("left", "right")})
                row.update({"template": template, "support_bindings": samples})
                if key(template) in seen:
                    row["status"] = "duplicate_template"
                else:
                    seen.add(key(template))
                    proof = certify_template(template, proof_backend=proof_backend)
                    row.update({"status": proof["status"], "certificate": proof})
                    if proof["status"] == "exact_parametric_coefficient_identity":
                        accepted.append({"id": digest(template), "template": template, "certificate": proof,
                                         "source_rules": row["source_rules"], "support_bindings": samples})
            except (ValueError, TypeError, KeyError) as exc:
                row.update({"status": "unsupported", "diagnostic": str(exc)})
            candidates.append(row)
    if template_strategy == "abstract_subexpressions":
        for rule in ground["rules"]:
            proved = []
            relation = {k: rule[k] for k in ("left", "right")}
            for template, samples in abstract_subexpressions(relation):
                row = {"source_rules": [rule["id"]], "generalization": "shared_subexpression_cut",
                       "template": template, "support_bindings": samples, "selected": False,
                       "serialized_template_bytes": len(key(template).encode("utf-8"))}
                try:
                    proof = certify_template(template, proof_backend=proof_backend)
                    row.update({"status": proof["status"], "certificate": proof})
                    if proof["status"] == "exact_parametric_coefficient_identity":
                        proved.append(row)
                except (ValueError, TypeError, KeyError) as exc:
                    row.update({"status": "unsupported", "diagnostic": str(exc)})
                candidates.append(row)
            if proved:
                best = min(proved, key=lambda r: (r["serialized_template_bytes"], key(r["template"])))
                encoded = key(best["template"])
                if encoded not in seen:
                    seen.add(encoded)
                    best["selected"] = True
                    accepted.append({"id": digest(best["template"]), "template": best["template"],
                                     "certificate": best["certificate"], "source_rules": best["source_rules"],
                                     "support_bindings": best["support_bindings"]})
    library = {"schema": SCHEMA, "source_ground_library": ground,
               "rules": sorted(accepted, key=lambda r: r["id"]),
               "parameter_generalization": "proved only on positive rational guards",
               "scope": "Q[[x]] at zero; no novelty or special-value claim"}
    if proof_backend != "coefficient_ratio":
        library["proof_backend"] = proof_backend
    if template_strategy != "paired":
        library["template_strategy"] = template_strategy
    if template_strategy in FUNCTION_STRATEGIES:
        library["parameter_generalization"] = "proved for arbitrary function-valued parameters in Q[[x]]"
    if template_strategy == "abstract_subexpressions":
        library["abstraction_search"] = {"max_shared_subterms": 16, "cut_sizes": [0, 1, 2, "all"],
            "selection": "minimum serialized template bytes among certified candidates per ground rule",
            "global_optimality_claimed": False}
    library["sha256"] = digest(library)
    return library, candidates


def learn_typed_templates(ground):
    """Combine existing hypothesis spaces without broadening either guard."""
    accepted, candidates, routes = {}, [], []
    for strategy, backend in (("abstract_subexpressions", "formal_function"),
                              ("paired_and_rays", "uniform_ode")):
        branch, attempts = learn_templates(ground, proof_backend=backend, template_strategy=strategy)
        routes.append({"template_strategy": strategy, "proof_backend": backend,
                       "library_sha256": branch["sha256"]})
        candidates.extend({**c, "hypothesis_strategy": strategy, "proof_backend": backend} for c in attempts)
        for rule in branch["rules"]:
            if rule["id"] in accepted and accepted[rule["id"]] != rule:
                raise ValueError("conflicting typed rule provenance")
            accepted[rule["id"]] = rule
    library = {"schema": SCHEMA, "source_ground_library": ground,
               "rules": [accepted[k] for k in sorted(accepted)],
               "proof_backend": "typed_dispatch", "template_strategy": "typed_union",
               "proof_routes": routes,
               "parameter_generalization": "per-rule guards: arbitrary formal series or positive rational parameters",
               "scope": "Q[[x]] at zero; no novelty or special-value claim"}
    library["sha256"] = digest(library)
    return library, candidates


def match(template, program, binding):
    if series_parameter(template):
        try:
            validate(program)
        except (ValueError, TypeError):
            return False
        name = template["series_parameter"]
        if name in binding:
            return binding[name] == program
        binding[name] = deepcopy(program)
        return True
    if parameter(template):
        q = numeric(program)
        if q is None or q <= 0:
            return False
        q /= rational(template.get("multiplier", 1))
        name = template["parameter"]
        if name in binding:
            return binding[name] == str(q)
        binding[name] = str(q)
        return True
    if isinstance(template, dict):
        return (isinstance(program, dict) and set(template) == set(program)
                and all(match(template[k], program[k], binding) for k in sorted(template)))
    if isinstance(template, list):
        return (isinstance(program, list) and len(template) == len(program)
                and all(match(a, b, binding) for a, b in zip(template, program)))
    q = numeric(template)
    return q == numeric(program) if q is not None else template == program


class ParametricLibrary:
    def __init__(self, library):
        expected, _ = learn_templates(library["source_ground_library"],
                                      proof_backend=library.get("proof_backend", "coefficient_ratio"),
                                      template_strategy=library.get("template_strategy", "paired"))
        if expected != library:
            raise ValueError("parameter library provenance or symbolic proof failed replay")
        self.sha256 = library["sha256"]
        self.rules = deepcopy(expected["rules"])
        self.by_id = {r["id"]: r for r in self.rules}

    def application(self, p):
        for rule in self.rules:
            binding = {}
            if match(rule["template"]["left"], p, binding):
                if set(binding) != names(rule["template"]):
                    continue
                right = instantiate(rule["template"]["right"], binding)
                validate(right)
                if term_order(right) < term_order(p):
                    return rule, binding, right
        return None

    def reduce(self, program, max_steps=1024):
        validate(program)
        if max_steps < 0:
            raise ValueError("negative rewrite budget")
        current, steps, exhausted = deepcopy(program), [], False
        while True:
            found = None
            for path, sub in occurrences(current):
                application = self.application(sub)
                if application:
                    found = path, application
                    break
            if found is None:
                break
            if len(steps) >= max_steps:
                exhausted = True
                break
            path, (rule, binding, right) = found
            after = replace_at(current, path, right)
            validate(after)
            if not term_order(after) < term_order(current):
                raise ValueError("nondecreasing parameter rewrite")
            steps.append({"rule": rule["id"], "binding": binding, "path": list(path),
                          "before": digest(current), "after": digest(after)})
            current = after
        trace = {"schema": TRACE_SCHEMA, "library": self.sha256, "input": deepcopy(program), "output": current,
                 "steps": steps, "budget_exhausted": exhausted, "scope": "exact equality in Q[[x]] only"}
        return current, trace

    def replay(self, trace):
        try:
            if (set(trace) != {"schema", "library", "input", "output", "steps", "budget_exhausted", "scope"}
                    or trace["schema"] != TRACE_SCHEMA or trace["library"] != self.sha256
                    or trace["scope"] != "exact equality in Q[[x]] only"
                    or not isinstance(trace["budget_exhausted"], bool)):
                return False
            validate(trace["input"])
            current = deepcopy(trace["input"])
            for step in trace["steps"]:
                if set(step) != {"rule", "binding", "path", "before", "after"}:
                    return False
                rule, sub = self.by_id[step["rule"]], current
                for field in step["path"]:
                    sub = sub[field]
                binding = {}
                if (not match(rule["template"]["left"], sub, binding) or binding != step["binding"]
                        or set(binding) != names(rule["template"]) or digest(current) != step["before"]):
                    return False
                after = replace_at(current, step["path"], instantiate(rule["template"]["right"], binding))
                validate(after)
                if digest(after) != step["after"] or not term_order(after) < term_order(current):
                    return False
                current = after
            if current != trace["output"]:
                return False
            applicable = any(self.application(sub) for _, sub in occurrences(current))
            return bool(applicable) == trace["budget_exhausted"]
        except (ValueError, KeyError, TypeError, IndexError):
            return False


def load_library(path):
    from math_os_prototype.shared_json import read
    data = read(path)
    if data.get("schema") == SCHEMA:
        return ParametricLibrary(data)
    return RelationLibrary(data)
