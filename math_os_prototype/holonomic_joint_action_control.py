"""Choose relation-search jobs using only inputs and past certified outcomes."""

from copy import deepcopy
from hashlib import sha256
import random
import sympy as sp

from math_os_prototype.holonomic_action_control import FEATURES, input_features
from math_os_prototype.holonomic_joint_relations import relation_program, replay_relation, uninterpreted_expression
from math_os_prototype.holonomic_joint_screening import rational_multiple_key, opaque_polynomial
from math_os_prototype.holonomic_route_discovery import X, key
from math_os_prototype.certified_polynomial_ideal import PolynomialIdeal, verify_witness
from math_os_prototype.research_action_policy import ResearchActionPolicy

FEATURE_NAMES = (*FEATURES, "group_size", "degree_x", "derivatives", "product_degree")


def action_features(request):
    vectors = [input_features(row["program"]) for row in request["rows"]]
    if not vectors:
        raise ValueError("empty relation-search group")
    mean = tuple(sum(v[i] for v in vectors)/len(vectors) for i in range(len(FEATURES)))
    counts = (len(vectors), request["plan"]["degree_x"], request["plan"]["derivatives"], request["product_degree"])
    vector = (*mean, *(c/(1+c) for c in counts))
    if "strategy" in request:
        expected = "refine_then_prove" if request["plan"].get("sparse_relations", False) else "direct_proof"
        if request["strategy"] != expected:
            raise ValueError("strategy does not match executable plan")
        return (*vector, float(expected == "refine_then_prove"))
    return vector


def canonical_relation(features, terms):
    return rational_multiple_key(uninterpreted_expression(relation_program(features, terms)))


def verify_prior(records):
    known = {}
    for record in records:
        cert, features = record["certificate"], record["features"]
        if not replay_relation(cert, features):
            raise ValueError("prior relation failed exact replay")
        canonical = canonical_relation(features, cert["terms"])
        if canonical == "zero" or canonical != record["canonical"]:
            raise ValueError("invalid prior relation key")
        known[canonical] = record
    return known


def cross_context_consequence(features, terms, verified_prior):
    """Use shared opaque function atoms, not group-local origin numbers.

    The caller supplies only replayed roots (verify_prior or add_root). Witnesses
    certify the polynomial implication; the roots certify its mathematical use.
    """
    def expression(fs, ts):
        return opaque_polynomial(uninterpreted_expression(relation_program(fs, ts)))
    records = list(verified_prior.values())
    equations = [expression(r["features"], r["certificate"]["terms"]) for r in records]
    target = expression(features, terms)
    variables = sorted(set().union(*(p.free_symbols for p in [*equations, target]))-{X}, key=str)
    variables = variables or [sp.Symbol("unused_function")]
    witness = PolynomialIdeal(equations, variables).witness(target)
    if witness is None:
        return None
    if not verify_witness(witness, equations, target, variables):
        raise ValueError("cross-context implication failed exact replay")
    used = [i for i, multiplier in enumerate(witness["multipliers"]) if multiplier]
    witness["equations"] = [witness["equations"][i] for i in used]
    witness["multipliers"] = [witness["multipliers"][i] for i in used]
    if not verify_witness(witness, [equations[i] for i in used], target, variables):
        raise ValueError("reduced premise set failed exact replay")
    return {"status": "prior_polynomial_consequence", "witness": witness,
            "variables": list(map(str, variables)),
            "premises": [records[i]["certificate"]["sha256"] for i in used],
            "scope": "polynomial consequence of replayed identities, not a new relation"}


class JointActionController:
    def __init__(self, requests, environment, mode="learn", seed=0, *, max_revisits=0):
        if mode not in {"learn", "uniform"}:
            raise ValueError("unknown joint action mode")
        if type(max_revisits) is not int or max_revisits < 0:
            raise ValueError("max_revisits must be a nonnegative integer")
        self.requests = deepcopy(requests)
        self.source_domain = "joint_series:" + sha256(key(self.requests).encode()).hexdigest()
        self.pending = list(range(len(requests)))
        self.max_revisits, self.revisits = max_revisits, 0
        self.origins = list(range(len(requests)))
        self.deferred = {}
        self.active_features, self.active_known = None, None
        self.mode, self.rng = mode, random.Random(seed)
        strategy_flags = {"strategy" in r for r in requests}
        if len(strategy_flags) > 1:
            raise ValueError("mixed strategy feature schemas")
        names = (*FEATURE_NAMES, "refinement_enabled") if strategy_flags == {True} else FEATURE_NAMES
        if max_revisits:
            names = (*names, "previous_timeout", "known_relations", "new_relations_since_timeout")
        for request in requests:
            action_features(request)
        self.policy = ResearchActionPolicy(environment, feature_names=names,
                                           reward_target="new_verified_relation")
        self.known, self.active = {}, None

    def features(self, index):
        vector = action_features(self.requests[index])
        if not self.max_revisits:
            return vector
        revisit = self.requests[index].get("revisit")
        previous = set(revisit["known_at_timeout"]) if revisit else set(self.known)
        counts = (len(self.known), len(set(self.known) - previous))
        return (*vector, float(revisit is not None), *(c/(1+c) for c in counts))

    def choose(self):
        if self.active is not None or not self.pending:
            raise ValueError("no selectable joint action")
        features = [self.features(i) for i in self.pending]
        scores = self.policy.scores(features)
        position = (self.rng.randrange(len(self.pending)) if self.mode == "uniform"
                    else max(range(len(scores)), key=lambda i: scores[i]))
        index = self.pending.pop(position)
        decision = {"index": index, "alternatives": [
            {"index": i, "features": list(f), "score": s}
            for i, f, s in zip(sorted([*self.pending, index]), features, scores)],
            "policy_before": self.policy.digest(), "known_before": sorted(self.known),
            "outcomes_available": False}
        self.active = index
        self.active_features = features[position]
        self.active_known = set(self.known)
        request = deepcopy(self.requests[index])
        request["prior_relations"] = list(deepcopy(self.known).values())
        return decision, request

    def finish(self, result, completed, *, termination=None):
        if self.active is None:
            raise ValueError("no executed joint action")
        index = self.active
        if completed and result.get("status") != "completed":
            raise ValueError("incomplete result cannot supply reward")
        if completed and termination not in (None, "completed"):
            raise ValueError("completed result conflicts with termination")
        self.active = None
        new = []
        if completed:
            for record in result["learned_relations"]:
                # Exact replay takes place in the bounded worker and independent audit.
                # The controller receives receipts, never numerical fit candidates.
                if record["canonical"] not in self.known:
                    self.known[record["canonical"]] = deepcopy(record)
                    if record["multi_origin"]:
                        new.append(record["certificate"]["sha256"])
        evidence = {"executed": True, "verified_new_relation_count": len(new),
                    "certificate_hashes": new, "completed": completed}
        reward = float(bool(new)) if completed else None
        updated = False
        if completed and self.mode == "learn":
            updated = self.policy.observe(features=self.active_features, reward=reward,
                source_domain=self.source_domain,
                pair_id=str(index), evidence=evidence)
        feedback = {"index": index, "reward": reward, "updated": updated, "evidence": evidence,
                    "policy_after": self.policy.digest(), "known_after": sorted(self.known)}
        if self.max_revisits:
            if not completed and termination == "timeout":
                self.deferred[self.origins[index]] = {
                    "previous_index": index, "known_at_timeout": sorted(self.active_known),
                }
            scheduled = []
            for origin, failure in list(self.deferred.items()):
                if self.revisits >= self.max_revisits:
                    break
                added = sorted(set(self.known) - set(failure["known_at_timeout"]))
                if not added:
                    continue
                receipt = {**failure, "origin": origin, "new_known_relations": added,
                           "reason": "new_verified_knowledge_after_timeout"}
                proposal = deepcopy(self.requests[origin])
                proposal["revisit"] = receipt
                next_index = len(self.requests)
                self.requests.append(proposal)
                self.origins.append(origin)
                self.pending.append(next_index)
                scheduled.append({"index": next_index, **receipt})
                self.revisits += 1
                del self.deferred[origin]
            feedback.update(termination=termination, revisits_scheduled=scheduled,
                            deferred_origins=sorted(self.deferred), revisits_used=self.revisits)
        self.active_features, self.active_known = None, None
        return feedback
