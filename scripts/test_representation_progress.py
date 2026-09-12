"""Reward-accounting and exact-series fixtures; not discovery evidence."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from math_os_prototype.representation_progress import (
    TARGET, description_bits, receipt, reward_from_costs,
)
from math_os_prototype.research_action_policy import ResearchActionPolicy, FEATURE_NAMES
from math_os_prototype.holonomic_representation_progress import RepresentationProgress
from math_os_prototype.holonomic_online_library import OnlineLibrary
from math_os_prototype.holonomic_parametric_learning import learn_templates
from math_os_prototype.holonomic_relation_reuse import build_library, digest
from math_os_prototype.holonomic_route_discovery import certify_equal


FEATURES = [1.0]+[0.0]*(len(FEATURE_NAMES)-1)


class DescriptionRewardTests(unittest.TestCase):
    def test_same_encoding_and_definition_charge(self):
        self.assertEqual(description_bits({"a": 1, "b": 2}), description_bits({"b": 2, "a": 1}))
        items = [{"id": "x", "before": ["long"]*10, "after": ["short"]}]
        small = receipt([], [], items)
        huge = receipt([], ["definition"]*100, items)
        self.assertGreater(small["reward"], 0)
        self.assertEqual(huge["reward"], 0)

    def test_no_reward_for_unchanged_or_larger_descriptions(self):
        self.assertEqual(receipt([], [], [{"id": "x", "before": [1], "after": [1]}])["reward"], 0)
        self.assertEqual(receipt([], [], [{"id": "x", "before": [1], "after": [1, 2]}])["reward"], 0)
        with self.assertRaises(ValueError):
            receipt([], [], [])
        with self.assertRaises(ValueError):
            receipt([], [], [{"id": "x"}, {"id": "x"}])

    def test_continuous_reward_updates_and_replays_policy(self):
        p = ResearchActionPolicy("fixture", reward_target=TARGET)
        costs = dict(before_data_bits=100, after_data_bits=20, before_definition_bits=0, after_definition_bits=30)
        evidence = dict(executed=True, status="completed_description_probe", costs=costs,
                        receipt_sha256="a"*64, probe_items=8)
        before = p.scores([FEATURES])
        p.observe(features=FEATURES, reward=0.5, evidence=evidence, source_domain="fixture", pair_id="case")
        self.assertNotEqual(before, p.scores([FEATURES]))
        restored = ResearchActionPolicy.from_dict(p.to_dict(), environment_fingerprint="fixture")
        self.assertEqual(restored.to_dict(), p.to_dict())
        self.assertFalse(p.observe(features=FEATURES, reward=0.5, evidence=evidence,
                                   source_domain="fixture", pair_id="case"))
        for reward in [1.0, -0.1, float("nan")]:
            with self.assertRaises(ValueError):
                p.observe(features=FEATURES, reward=reward, evidence=evidence, source_domain="fixture", pair_id="bad")

    def test_invalid_or_pending_evidence_cannot_train(self):
        p = ResearchActionPolicy("fixture", reward_target=TARGET)
        for status in ["awaiting_future_description_probe", "insufficient_future_probe_items"]:
            with self.assertRaises(ValueError):
                p.observe(features=FEATURES, reward=0.0, evidence={"executed": True, "status": status},
                          source_domain="fixture", pair_id=status)
        with self.assertRaises(ValueError):
            reward_from_costs(dict(before_data_bits=True, after_data_bits=0, before_definition_bits=0, after_definition_bits=0))


class DelayedSeriesProgressTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def h(a):
            return {"op": "hyper", "a": [a], "b": []}
        source = {"left": {"op": "mul", "left": h("1/5"), "right": h("1/5")}, "right": h("2/5")}
        empty = build_library([], {"source": "unit fixture"})
        ground = build_library([certify_equal(source["left"], source["right"])], {"source": "unit fixture"})
        cls.before = OnlineLibrary(learn_templates(empty)[0])
        cls.after = OnlineLibrary(learn_templates(ground, proof_backend="uniform_ode", template_strategy="paired_and_rays")[0])
        cls.program = {"op": "mul", "left": h("2/7"), "right": h("2/7")}

    def setup_probe(self, size=8, learn=True):
        p = ResearchActionPolicy("fixture", reward_target=TARGET)
        probe = RepresentationProgress(p, source_domain="fixture", seed=1, probe_items=size, learn=learn)
        attempt = {"index": 10, "status": "candidate", "decision": {"selected": 0,
                   "alternatives": [{"features": FEATURES}]}}
        row = {"comparison_status": "exact_formal_series_equality", "proposal_index": 10}
        outcome = probe.record(attempt, row, self.before, self.after)
        return p, probe, outcome

    def rows(self, size):
        for i in range(size):
            program = {"op": "scale", "factor": str(i+1), "child": self.program}
            yield {"id": digest(program), "program": program, "proposal_index": 11+i}

    def test_reward_is_delayed_and_proofs_are_replayed(self):
        policy, probe, outcome = self.setup_probe()
        self.assertEqual(outcome["status"], "awaiting_future_description_probe")
        self.assertFalse(policy.feedback)
        for row in self.rows(7):
            self.assertFalse(probe.advance(row))
        self.assertFalse(policy.feedback)
        event = probe.advance(list(self.rows(8))[-1])[0]
        self.assertGreater(event["feedback"]["reward"], 0)
        self.assertEqual(event["origin_proposal"], 10)
        self.assertEqual(event["observed_after_proposal"], 18)
        self.assertEqual(len(policy.feedback), 1)
        for item in event["receipt"]["items"]:
            self.assertTrue(self.before.parametric.replay(item["before_trace"]))
            self.assertTrue(self.after.parametric.replay(item["after_trace"]))
        _, replay, _ = self.setup_probe()
        for row in self.rows(8):
            replay.advance(row)
        self.assertEqual(probe.snapshot(), replay.snapshot())

    def test_incomplete_probe_is_censored_not_negative(self):
        policy, probe, _ = self.setup_probe()
        probe.advance(next(self.rows(1)))
        state = probe.snapshot()
        self.assertFalse(policy.feedback)
        self.assertEqual(state["pending"][0]["status"], "insufficient_future_probe_items")

    def test_frozen_mode_does_not_update(self):
        policy, probe, _ = self.setup_probe(learn=False)
        before = policy.to_dict()
        for row in self.rows(8):
            probe.advance(row)
        self.assertEqual(before, policy.to_dict())
        self.assertFalse(probe.events[0]["feedback"]["updated"])

    def test_current_and_earlier_items_are_excluded(self):
        _, probe, _ = self.setup_probe()
        row = next(self.rows(1))
        for index in [1, 10]:
            probe.advance({**row, "proposal_index": index})
        self.assertEqual(probe.snapshot()["pending"][0]["items"], [])

    def test_rule_generated_candidates_cannot_supply_their_own_reward(self):
        policy, probe, _ = self.setup_probe()
        for row in self.rows(8):
            assert not probe.advance({**row, "uses_learned_construction": True})
        self.assertFalse(policy.feedback)
        self.assertEqual(probe.snapshot()["pending"][0]["items"], [])

    def test_unchanged_parameter_rules_do_not_start_probe(self):
        policy = ResearchActionPolicy("fixture", reward_target=TARGET)
        probe = RepresentationProgress(policy, source_domain="fixture", seed=1, probe_items=8, learn=True)
        attempt = {"index": 1, "status": "candidate", "decision": {"selected": 0,
                   "alternatives": [{"features": FEATURES}]}}
        out = probe.record(attempt, {"comparison_status": "exact_formal_series_equality"}, self.before, self.before)
        self.assertEqual(out["reward"], 0)
        self.assertFalse(probe.pending)

    def test_numeric_rule_is_not_credited_as_a_definition_acquisition(self):
        policy = ResearchActionPolicy("fixture", reward_target=TARGET)
        probe = RepresentationProgress(policy, source_domain="fixture", seed=1, probe_items=8, learn=True)
        attempt = {"index": 1, "status": "candidate", "decision": {"selected": 0,
                   "alternatives": [{"features": FEATURES}]}}
        out = probe.record(attempt, {"comparison_status": "definition_only_equality"}, self.before, self.after)
        self.assertEqual(out["reward"], 0)
        self.assertFalse(probe.pending)


if __name__ == "__main__":
    unittest.main()
