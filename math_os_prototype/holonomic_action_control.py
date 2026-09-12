"""Outcome-trained selection among compositions of the existing series grammar.

Syntax-only observation is the default. Optional state observation also checks
past syntax and existing construction budgets, never future proof results. The
series prover remains solely responsible for mathematical acceptance.
"""
from collections import Counter
from hashlib import sha256
import json

from math_os_prototype.holonomic_search_pool import draw_composition
from math_os_prototype.holonomic_route_discovery import rational, key
from math_os_prototype.research_action_policy import (
    FEATURE_NAMES, ResearchActionPolicy, structural_action_features,
)

OPERATORS = ("hyper", "poly", "diff", "mul", "pullback", "scale", "add")
FEATURES = (*FEATURE_NAMES, "input_depth", "input_nodes",
            *(f"root.{op}" for op in OPERATORS), *(f"count.{op}" for op in OPERATORS))
STATE_FEATURES = (*FEATURES, "depth_budget_fraction", "node_budget_fraction",
                  "order_budget_fraction", "known_syntax_fraction")


def nodes(p):
    return 1+sum(nodes(v) for v in p.values() if isinstance(v, dict))


def depth(p):
    return 1+max([depth(v) for v in p.values() if isinstance(v, dict)]+[0])


def order_bound(p):
    if p["op"] == "ode":
        return len(p["operator"])-1
    if p["op"] == "hyper":
        return len(p["b"])+1
    if p["op"] == "poly":
        return 1
    if p["op"] == "mul":
        return order_bound(p["left"])*order_bound(p["right"])
    if p["op"] == "add":
        return order_bound(p["left"])+order_bound(p["right"])
    return order_bound(p["child"])


def feature_names(observation="syntax"):
    if observation not in {"syntax", "state"}:
        raise ValueError("unknown action observation")
    return STATE_FEATURES if observation == "state" else FEATURES


def selection_state(known, max_depth, max_order):
    return {"known": frozenset(known), "max_depth": max_depth, "max_nodes": 32,
            "max_order": max_order}


def preconditions(program, state):
    return _preconditions_for_key(program, state, key(program))


def _preconditions_for_key(program, state, encoded):
    costs = {"depth": depth(program), "nodes": nodes(program), "order": order_bound(program)}
    reasons = [f"{name}_budget" for name, cost in costs.items() if cost > state[f"max_{name}"]]
    if encoded in state["known"]:
        reasons.append("known_syntax")
    return {"costs": costs, "reasons": reasons, "admissible": not reasons}


def parameter_domain(parameters):
    payload = json.dumps(sorted({str(rational(p)) for p in parameters}), separators=(",", ":"))
    return "series_parameter_grid:" + sha256(payload.encode()).hexdigest()


def search_domain(policy):
    if policy.get("ode_sources_sha256"):
        return "ode_source_corpus:" + policy["ode_sources_sha256"]
    if not policy.get("source_proposal_every"):
        return parameter_domain(policy["parameters"])
    payload = {"height": policy["source_height"], "max_order": policy["max_order"]}
    return "enumerated_series_sources:" + sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def input_features(program):
    counts = Counter()
    stack, depth = [(program, 1)], 0
    while stack:
        term, level = stack.pop()
        counts[term["op"]] += 1
        depth = max(depth, level)
        stack.extend((v, level+1) for v in term.values() if isinstance(v, dict))
    nodes = sum(counts.values())
    base = structural_action_features(len(OPERATORS), {}, program, {})
    return (*base, depth/(1+depth), nodes/(1+nodes),
            *(float(program["op"] == op) for op in OPERATORS),
            *(counts[op]/(1+counts[op]) for op in OPERATORS))


def make_policy(environment, observation="syntax", reward_target="new_verified_relation"):
    return ResearchActionPolicy(environment, feature_names=feature_names(observation), reward_target=reward_target)


def environment_fingerprint(policy):
    fields = ("operators", "max_depth", "max_order", "pullback_degree", "compound_operands",
              "certificate_seconds", "online_learning", "source_hashes")
    payload = {field: policy[field] for field in fields}
    if policy.get("ode_sources_sha256"):
        payload["ode_sources_sha256"] = policy["ode_sources_sha256"]
    payload["features"] = feature_names(policy.get("action_observation", "syntax"))
    if policy.get("action_frontier_every", 0):
        payload["action_frontier_every"] = policy["action_frontier_every"]
    if policy.get("action_frontier_window", "oldest") != "oldest":
        payload["action_frontier_window"] = policy["action_frontier_window"]
    if policy.get("definition_screen", False):
        payload["definition_screen"] = True
    if policy.get("construction_memory_file_sha256"):
        payload["construction_memory_file_sha256"] = policy["construction_memory_file_sha256"]
    if policy.get("systematic_proposal_every", 0):
        payload["systematic_proposal_every"] = policy["systematic_proposal_every"]
    if policy.get("parameter_proof_backend", "coefficient_ratio") != "coefficient_ratio":
        payload["parameter_proof_backend"] = policy["parameter_proof_backend"]
    if policy.get("parameter_template_strategy", "paired") != "paired":
        payload["parameter_template_strategy"] = policy["parameter_template_strategy"]
    if policy.get("action_reward", "new_verified_relation") != "new_verified_relation":
        payload["action_reward"] = policy["action_reward"]
        payload["progress_probe_items"] = policy["progress_probe_items"]
    if policy.get("learned_proposal_every", 0):
        payload["learned_proposal_every"] = policy["learned_proposal_every"]
    if policy.get("source_proposal_every", 0):
        payload["source_proposal_every"] = policy["source_proposal_every"]
        payload["source_height"] = policy["source_height"]
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def select_composition(pool, rng, policy, width, *, uniform=False, state=None, frontier=None,
                       frontier_window="oldest", systematic=None, learned=None, library=None, source=None, **options):
    if frontier_window not in {"oldest", "sampled"}:
        raise ValueError("unknown frontier window")
    if frontier_window == "sampled" and frontier is None:
        raise ValueError("sampled window requires a retained frontier")
    if frontier is not None and (state is None or policy is None):
        raise ValueError("retained frontier requires state-aware action selection")
    if systematic is not None and frontier is None:
        raise ValueError("systematic proposals require retained fair service")
    if source is not None and (policy is None or frontier is None or width < 2 + int(learned is not None)):
        raise ValueError("source proposals require retained selection and room for each proposal source")
    if policy is None:
        p, parents = draw_composition(pool, rng, **options)
        return p, parents, None
    if width < 1:
        raise ValueError("action choice width must be positive")
    offered = []
    source_receipt = None
    if source is not None:
        proposal, source_receipt = source.offer()
        if proposal is not None:
            offered.append(proposal)
    learned_receipt = None
    if learned is not None:
        if library is None or frontier is None or policy is None or width < 2:
            raise ValueError("learned proposals require a library, retained frontier, and width >= 2")
        proposal, learned_receipt = learned.offer(pool, library)
        if proposal is not None:
            offered.append(proposal)
    systematic_receipt = None
    if systematic is not None:
        proposal, systematic_receipt = systematic.offer(pool)
        if proposal is not None:
            offered.append(proposal)
    for _ in range(width-len(offered)):
        if source is not None and not pool.entries:
            break
        p, parents = draw_composition(pool, rng, **options)
        offered.append({"program": p, "parents": parents})
    frontier_receipt = None
    candidates = offered
    candidate_keys = {}
    if frontier is not None:
        frontier_receipt = {"before_sha256": frontier.digest(), "offered": offered}
        frontier_receipt.update(frontier.prepare(
            [{"key": key(p["program"]), "payload": p} for p in offered],
            lambda encoded, item: _preconditions_for_key(item["program"], state, encoded)["reasons"],
            readonly_keyed=True))
        window = frontier.window(width, rng=rng if frontier_window == "sampled" else None)
        candidate_keys = {entry["id"]: entry["key"] for entry in window}
        candidates = [{**entry["payload"], "frontier_id": entry["id"]}
                      for entry in window]
        frontier_receipt["reserved"] = frontier.reserved
    alternatives = []
    for candidate in candidates:
        p, parents = candidate["program"], candidate["parents"]
        features = list(input_features(p))
        alternative = {**candidate, "features": features}
        if state is not None:
            check = (_preconditions_for_key(p, state, candidate_keys[candidate["frontier_id"]])
                     if frontier is not None else preconditions(p, state))
            alternative["preconditions"] = check
            features.extend(min(1.0, check["costs"][name]/state[f"max_{name}"])
                            for name in ("depth", "nodes", "order"))
            features.append(len(state["known"])/(1+len(state["known"])))
        alternatives.append(alternative)
    scores = policy.scores([a["features"] for a in alternatives])
    eligible = [i for i, a in enumerate(alternatives)
                if a.get("preconditions", {}).get("admissible", True)]
    maximum = max((scores[i] for i in eligible), default=0)
    tied = [i for i in eligible if abs(scores[i]-maximum) < 1e-12]
    if frontier is not None and frontier.reserved and eligible:
        selected = eligible[0]
    else:
        selected = (rng.choice(eligible) if uniform else rng.choice(tied)) if eligible else None
    decision = {"alternatives": alternatives, "scores": scores, "selected": selected,
                "policy_before_sha256": policy.digest(), "outcomes_available_at_selection": False}
    if systematic_receipt is not None:
        decision["systematic"] = systematic_receipt
    if learned_receipt is not None:
        decision["learned_proposals"] = learned_receipt
    if source_receipt is not None:
        decision["source_proposals"] = source_receipt
    if frontier is not None:
        frontier.commit(None if selected is None else alternatives[selected]["frontier_id"])
        frontier_receipt.update(after_sha256=frontier.digest(), pending_count=len(frontier.pending))
        decision["frontier"] = frontier_receipt
    if state is not None:
        decision["state"] = {k: v for k, v in state.items() if k != "known"}
        decision["state"].update(known_syntax_count=len(state["known"]),
            known_syntax_sha256=sha256(json.dumps(sorted(state["known"])).encode()).hexdigest())
    if selected is None:
        return None, [], decision
    chosen = alternatives[selected]
    return chosen["program"], chosen["parents"], decision


def record_outcome(policy, decision, *, status, certificate_hash, source_domain, pair_id, learn):
    # A timeout is failure to obtain evidence within this budget, not a refutation.
    fresh = status == "exact_formal_series_equality"
    skipped = decision["selected"] is None
    if skipped and status != "no_admissible_alternative":
        raise ValueError("unselected action cannot have an execution outcome")
    evidence = {"executed": not skipped, "status": status, "verified_new_relation_count": int(fresh),
                "certificate_hashes": [certificate_hash] if fresh else [],
                "timeout_is_mathematical_refutation": False}
    censored = status == "certificate_budget"
    evidence["proof_not_attempted_due_to_budget"] = censored
    before = policy.digest()
    updated = policy.observe(features=decision["alternatives"][decision["selected"]]["features"],
                             reward=float(fresh), source_domain=source_domain, pair_id=pair_id,
                             evidence=evidence) if learn and not censored and not skipped else False
    return {"reward": None if censored or skipped else float(fresh), "evidence": evidence, "source_domain": source_domain,
            "pair_id": pair_id, "updated": updated,
            "policy_before_sha256": before, "policy_after_sha256": policy.digest()}
