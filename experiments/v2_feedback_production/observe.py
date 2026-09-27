"""Read-only execution observer; never supplies a policy action or edit."""
from collections import Counter, defaultdict
import copy
import sys
import time

from experiments.v2_online_feedback.adapter import ARMS, FeedbackPlayer, fingerprint, payload
from experiments.v2_online_feedback.prepare import write
from experiments.v2_online_feedback.run import rows_write


class EvaluationCapture:
    def __init__(self, module, adapter, game, directory, arm):
        self.module, self.adapter, self.game, self.directory, self.arm = module, adapter, game, directory, arm
        self.phase = "initial"
        self.actions, self.training, self.players = [], [], []
        self.learner = None
        self.pending = None
        self.record_calls = Counter()
        self.cpu = time.process_time()
        self.wall = time.perf_counter()
        self.phase_cpu = self.cpu
        self.times = {}
        self.game_hash = fingerprint(game.to_dict())

    def profile(self, frame, event, result):
        code, m = frame.f_code, self.module
        if code is m.StructuralLearner.__init__.__code__ and event == "return":
            assert self.learner is None, "More than one learner in candidate evaluation"
            self.learner = frame.f_locals["self"]
            assert not self.learner.counts and not self.learner.id_to_state
        if code is self.adapter.feedback.__func__.__code__:
            if event == "call":
                assert self.phase == "initial" and len(self.training) == 2500
                assert frame.f_locals["learner"] is self.learner
                self.initial = copy.deepcopy(payload(self.learner))
                self.times["initial_cpu_seconds"] = time.process_time() - self.phase_cpu
                self.phase_cpu = time.process_time()
                self.phase = "additional"
            elif event == "return":
                assert len(self.players) == 1 and self.players[0].steps == 5000
                self.final = copy.deepcopy(payload(self.learner))
                self.final_hash = fingerprint(self.final)
                self.phase = "frozen"
                self.times["additional_cpu_seconds"] = time.process_time() - self.phase_cpu
                self.phase_cpu = time.process_time()
        if code is FeedbackPlayer.__init__.__code__ and event == "return":
            player = frame.f_locals["self"]
            assert player.learner is self.learner and player.arm == self.arm
            self.players.append(player)
        if code is m.MicroGame.is_goal.__code__ and event == "call":
            assert self.phase != "initial", "Task queried during task-blind initial training"
        if code is m.MicroGame.step.__code__ and event == "return":
            caller = frame.f_back
            phase, trial = self.phase, None
            if phase == "frozen":
                if caller.f_code is m.evaluate_random_player.__code__:
                    phase, trial = "random", caller.f_locals["trial"]
                elif "psi_aux" in caller.f_locals:
                    phase, trial = "auxiliary", 0
                else:
                    phase, trial = "mortra", caller.f_locals["trial"]
            elif phase == "additional":
                trial = self.players[0].trial
            row = {"phase": phase, "trial": trial, "state": frame.f_locals["state"],
                   "action": int(frame.f_locals["action"]), "next_state": result}
            self.actions.append(row)
            if phase in ("initial", "additional"):
                assert self.pending is None or (self.arm == ARMS[0] and phase == "additional")
                self.pending = row
        if code is m.StructuralLearner.record_transition.__code__ and event == "call":
            assert self.phase in ("initial", "additional"), "Evaluation experience leakage"
            assert not (self.phase == "additional" and self.arm == ARMS[0])
            assert frame.f_locals["self"] is self.learner and self.pending is not None
            u, a, v = (frame.f_locals[k] for k in ("u", "a", "v"))
            assert (self.learner.id_to_state[u], a, self.learner.id_to_state[v]) == (
                self.pending["state"], self.pending["action"], self.pending["next_state"])
            self.record_calls[self.phase] += 1
            if self.phase == "initial":
                self.training.append(dict(self.pending))
            self.pending = None
        if code is m.StructuralLearner.build_k_support.__code__ and event == "call" and self.phase == "frozen":
            assert frame.f_locals["self"] is self.learner
            assert fingerprint(payload(self.learner)) == self.final_hash

    def finish(self, metrics):
        self.times["frozen_cpu_seconds"] = time.process_time() - self.phase_cpu
        self.times["evaluation_cpu_seconds"] = time.process_time() - self.cpu
        self.times["evaluation_wall_seconds"] = time.perf_counter() - self.wall
        assert fingerprint(payload(self.learner)) == self.final_hash
        assert fingerprint(self.game.to_dict()) == self.game_hash
        assert self.record_calls["initial"] == 2500
        assert self.record_calls["additional"] == (0 if self.arm == ARMS[0] else 5000)
        assert sum(self.learner.action_visits.values()) == (2500 if self.arm == ARMS[0] else 7500)
        phase_counts = Counter(row["phase"] for row in self.actions)
        assert phase_counts["initial"] == 2500 and phase_counts["additional"] == 5000
        player = self.players[0]
        actual_extra = [r for r in self.actions if r["phase"] == "additional"]
        assert [(r["state"], r["action"], r["next_state"]) for r in actual_extra] == [
            (r["state"], r["action"], r["next_state"]) for r in player.actions]
        groups = defaultdict(list)
        for row in self.actions:
            groups[(row["phase"], row["trial"])].append(row)
        replay_cpu = time.process_time()
        for (phase, trial), rows in groups.items():
            state = self.game.get_initial_state()
            for row in rows:
                assert row["state"] == state, (phase, trial)
                state = self.game.step(state, row["action"])
                assert state == row["next_state"]
        trial_records = {}
        for phase, success_key in (("mortra", "successes"), ("random", "random_successes")):
            records = []
            for trial in range(50):
                rows = groups.get((phase, trial), [])
                states = [self.game.get_initial_state()] + [r["next_state"] for r in rows]
                records.append({"trial": trial, "actions": [r["action"] for r in rows],
                                "states": states, "success": bool(self.game.is_goal(states[-1]))})
            assert sum(t["success"] for t in records) == metrics[success_key]
            assert records[0]["actions"] == metrics[f"{phase}_replay"]["actions"]
            trial_records[phase] = records
        replay_cpu = time.process_time() - replay_cpu
        if self.arm == ARMS[0]:
            assert fingerprint(self.initial) == self.final_hash
        rows_write(self.directory / "all_actions.jsonl.gz", self.actions)
        rows_write(self.directory / "initial_training.jsonl.gz", self.training)
        write(self.directory / "frozen_trials.json", trial_records)
        write(self.directory / "field_events.json", player.fields)
        write(self.directory / "training_rollouts.json", player.rollouts)
        cost = sum(len(t["actions"]) if t["success"] else 100 for t in trial_records["mortra"]) / 50
        audit = {"arm": self.arm, "phase_actions": dict(phase_counts), "total_environment_actions": len(self.actions),
                 "verification_replay_actions": len(self.actions), "verification_cpu_seconds": replay_cpu,
                 "same_learner_before_after_feedback_and_frozen": True, "fresh_learner": True,
                 "frozen_model_unchanged": True, "record_calls": dict(self.record_calls),
                 "no_random_or_evaluation_learning": True, "no_reset_edges": True,
                 "game_unchanged_during_evaluation": True, "all_actions_replayed": True,
                 "mean_capped_cost": cost, "successes": metrics["successes"],
                 "random_successes": metrics["random_successes"], "metrics": metrics, **self.times}
        write(self.directory / "execution_audit.json", audit)
        return audit


class LoopObserver:
    def __init__(self, module, adapter):
        self.module, self.adapter = module, adapter
        self.active = None
        self.metrics, self.audits, self.critique_calls, self.acceptance_calls = [], [], [], []
        self.delegate = module.evaluate_game
        assert self.delegate.__self__ is adapter
        self.arm = getattr(adapter, "arm", ARMS[2])

    def evaluate(self, game, *args, **kwargs):
        index = len(self.metrics)
        directory = self.adapter.output / f"evaluation_{index:03d}"
        self.active = EvaluationCapture(self.module, self.adapter, game, directory, self.arm)
        capture = self.active
        try:
            result = self.delegate(game, *args, **kwargs)
        except BaseException as error:
            self.active = None
            directory.mkdir(parents=True, exist_ok=True)
            rows_write(directory / "interrupted_actions.jsonl.gz", capture.actions)
            write(directory / "interrupted.json", {"status": "RUN_NOT_COMPLETED", "error": repr(error)})
            raise
        finally:
            self.active = None
        self.audits.append(capture.finish(result))
        self.metrics.append(result)
        print(f"evaluation {index}: {result['successes']}/50; feedback=5000; audit=PASS", flush=True)
        return result

    def metric_index(self, value):
        matches = [i for i, m in enumerate(self.metrics) if m is value]
        assert len(matches) == 1, "Critique/acceptance did not receive the original evaluation result"
        return matches[0]

    def profile(self, frame, event, result):
        if self.active is not None:
            self.active.profile(frame, event, result)
        if event == "return" and frame.f_code is self.module.critique_game.__code__:
            self.critique_calls.append({"evaluation": self.metric_index(frame.f_locals["metrics"]), "critique": result})
        if event == "return" and frame.f_code is self.module.decide_acceptance.__code__:
            self.acceptance_calls.append({"current_evaluation": self.metric_index(frame.f_locals["m_curr"]),
                "candidate_evaluation": self.metric_index(frame.f_locals["m_cand"]),
                "current_critique": frame.f_locals["curr_critique"], "accepted": result[0], "reason": result[1]})

    def install(self):
        self.module.evaluate_game = self.evaluate

    def run(self, game, iterations, seed, mode):
        prior = sys.getprofile()
        try:
            sys.setprofile(self.profile)
            result = self.module.run_self_design_loop(game, num_iterations=iterations, is_control=mode == "random", seed=seed)
        finally:
            sys.setprofile(prior)
        assert len(self.metrics) == iterations + 1
        assert len(self.critique_calls) == iterations + 1 and len(self.acceptance_calls) == iterations
        for i, row in enumerate(result[1]):
            assert row.get("candidate_metrics", row["metrics"]) is self.metrics[i]
            if i:
                assert self.acceptance_calls[i - 1]["candidate_evaluation"] == i
                assert self.acceptance_calls[i - 1]["accepted"] == row["accepted"]
        return result

    def standalone(self, game):
        prior = sys.getprofile()
        try:
            sys.setprofile(self.profile)
            return self.evaluate(game)
        finally:
            sys.setprofile(prior)
