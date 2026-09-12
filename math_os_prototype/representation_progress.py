"""Source-neutral, declared-code description cost and bounded progress reward.

This measures certified semantic descriptions supplied by an adapter, not
Kolmogorov complexity, source-text reconstruction, novelty, or human difficulty.
The adapter must certify equivalence and independently replay every receipt.
"""
import hashlib
import json

TARGET = "certified_description_progress"
SCHEMA = "mortra.certified-description-progress.v1"


def encoding(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def digest(value):
    return hashlib.sha256(encoding(value)).hexdigest()


def description_bits(value):
    payload = encoding(value)
    # Length-prefixed canonical JSON; a base-128 unsigned length is self-delimiting.
    length_bytes = max(1, (len(payload).bit_length()+6)//7)
    return 8*(length_bytes+len(payload))


def reward_from_costs(costs):
    fields = {"before_data_bits", "after_data_bits", "before_definition_bits", "after_definition_bits"}
    if set(costs) != fields or any(type(v) is not int or v < 0 for v in costs.values()):
        raise ValueError("description costs must be nonnegative exact integer bit counts")
    before = costs["before_data_bits"]+costs["before_definition_bits"]
    after = costs["after_data_bits"]+costs["after_definition_bits"]
    return max(0, before-after)/max(1, before)


def receipt(before_definitions, after_definitions, items):
    ids = [r["id"] for r in items]
    if not items or len(ids) != len(set(ids)):
        raise ValueError("a probe must contain distinct identified items")
    costs = {"before_data_bits": description_bits([r["before"] for r in items]),
             "after_data_bits": description_bits([r["after"] for r in items]),
             "before_definition_bits": description_bits(before_definitions),
             "after_definition_bits": description_bits(after_definitions)}
    result = {"schema": SCHEMA, "encoding": "length-prefixed canonical ASCII JSON",
              "before_definitions": before_definitions, "after_definitions": after_definitions,
              "items": items, "costs": costs, "reward": reward_from_costs(costs),
              "definition_cost_included": True,
              "scope": "equivalent program descriptions; proof-storage and runtime costs not included"}
    result["sha256"] = digest(result)
    return result


def validate_evidence(evidence, reward):
    if evidence.get("status") == "no_new_parameter_representation":
        if reward != 0 or evidence.get("receipt_sha256") is not None:
            raise ValueError("unchanged representations cannot earn progress reward")
        return
    if evidence.get("status") != "completed_description_probe":
        raise ValueError("uncompleted probes cannot update the policy")
    h = evidence.get("receipt_sha256")
    if (not isinstance(h, str) or len(h) != 64 or any(c not in "0123456789abcdef" for c in h)
            or type(evidence.get("probe_items")) is not int or evidence["probe_items"] < 1):
        raise ValueError("progress reward needs a completed probe receipt")
    if reward != reward_from_costs(evidence.get("costs", {})):
        raise ValueError("progress reward does not match description costs")
