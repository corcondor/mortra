"""Delayed action credit from subsequently encountered, exactly rewritten series.

Each acquisition is compared with its own frozen predecessor on the next K
recorded candidates. These are training observations, not an untouched test set.
No ground-only rewrite or finite coefficient match counts as a representation.
"""
from copy import deepcopy

from math_os_prototype.representation_progress import TARGET, encoding, receipt


def definitions(library):
    # Certificates and provenance are replayed separately; count executable guarded rules.
    unique = {encoding({"template": r["template"], "guards": r["certificate"]["guards"]}):
              {"template": r["template"], "guards": r["certificate"]["guards"]}
              for r in library.parametric.rules}
    return [unique[k] for k in sorted(unique)]


class RepresentationProgress:
    def __init__(self, controller, *, source_domain, seed, probe_items, learn):
        if controller.reward_target != TARGET or type(probe_items) is not int or probe_items < 1:
            raise ValueError("invalid progress policy or probe budget")
        self.controller, self.source_domain, self.seed = controller, source_domain, seed
        self.probe_items, self.learn = probe_items, learn
        self.pending, self.events = [], []

    def observe(self, attempt, reward, evidence):
        decision = attempt["decision"]
        before = self.controller.digest()
        pair_id = f"seed-{self.seed}:proposal-{attempt['index']}"
        updated = self.controller.observe(
            features=decision["alternatives"][decision["selected"]]["features"],
            reward=reward, source_domain=self.source_domain, pair_id=pair_id,
            evidence=evidence) if self.learn else False
        return {"reward": reward, "evidence": evidence, "source_domain": self.source_domain,
                "pair_id": pair_id, "updated": updated,
                "policy_before_sha256": before, "policy_after_sha256": self.controller.digest()}

    def record(self, attempt, row, before_library, after_library):
        decision = attempt.get("decision")
        if decision is None:
            return None
        status = row.get("comparison_status", attempt["status"]) if row else attempt["status"]
        if decision["selected"] is None or status == "certificate_budget":
            return {"reward": None, "updated": False, "status": "unexecuted_or_censored"}
        changed = (before_library is not None and after_library is not None
                   and definitions(before_library) != definitions(after_library))
        acquired_function_rule = False
        if changed and status == "definition_only_equality":
            old_ids = {r["id"] for r in before_library.parametric.rules}
            # Libraries replay these universal certificates before admission. A
            # definition may improve reuse without becoming a new theorem.
            acquired_function_rule = any(
                r["id"] not in old_ids
                and r["certificate"]["schema"] == "mortra.arbitrary-series-identity.v1"
                for r in after_library.parametric.rules)
        if changed and (status == "exact_formal_series_equality" or acquired_function_rule):
            self.pending.append({"attempt": deepcopy(attempt), "before": before_library,
                                 "after": after_library, "items": []})
            return {"reward": None, "updated": False, "status": "awaiting_future_description_probe",
                    "before_library": before_library.sha256, "after_library": after_library.sha256,
                    "required_items": self.probe_items}
        return self.observe(attempt, 0.0, {"executed": True, "status": "no_new_parameter_representation",
                                           "source_outcome": status, "receipt_sha256": None})

    def advance(self, row):
        if row is None or row.get("uses_learned_construction", False):
            return []
        completed = []
        remaining = []
        for p in self.pending:
            if row["proposal_index"] > p["attempt"]["index"]:
                p["items"].append({"id": row["id"], "program": deepcopy(row["program"]),
                                   "proposal_index": row["proposal_index"]})
            if len(p["items"]) < self.probe_items:
                remaining.append(p)
                continue
            items = []
            for item in p["items"]:
                before, bt = p["before"].parametric.reduce(item["program"])
                after, at = p["after"].parametric.reduce(item["program"])
                if not p["before"].parametric.replay(bt) or not p["after"].parametric.replay(at):
                    raise ValueError("uncertified representation probe rewrite")
                items.append({**item, "before": before, "after": after,
                              "before_trace": bt, "after_trace": at})
            proof = receipt(definitions(p["before"]), definitions(p["after"]), items)
            evidence = {"executed": True, "status": "completed_description_probe",
                        "receipt_sha256": proof["sha256"], "costs": proof["costs"],
                        "probe_items": len(items)}
            event = {"origin_proposal": p["attempt"]["index"],
                     "observed_after_proposal": row["proposal_index"],
                     "before_library": p["before"].sha256, "after_library": p["after"].sha256,
                     "receipt": proof, "feedback": self.observe(p["attempt"], proof["reward"], evidence)}
            self.events.append(event)
            completed.append(event)
        self.pending = remaining
        return completed

    def snapshot(self):
        return {"schema": "mortra.delayed-series-description-progress.v1", "events": deepcopy(self.events),
                "probe_items": self.probe_items,
                "pending": [{"origin_proposal": p["attempt"]["index"],
                             "before_library": p["before"].sha256, "after_library": p["after"].sha256,
                             "items": deepcopy(p["items"]), "status": "insufficient_future_probe_items"}
                            for p in self.pending],
                "probe_is_training_feedback": True, "heldout_source_generalization_established": False}
