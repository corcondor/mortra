"""Snapshot playback from the frozen AST, plus explicitly scoped online updates."""
import ast
import copy
import hashlib
import inspect
import json
import time

import numpy as np

from experiments.self_design_v2_integration.adapter import load_v2
from experiments.task_agent.pretraining import TaskBlindSelector

ARMS = ("frozen", "record_and_replan", "record_replan_and_explore")


def payload(learner):
    return {"id_to_state": learner.id_to_state, "state_to_id": list(learner.state_to_id.items()),
            "node_visits": list(learner.node_visits.items()), "action_visits": list(learner.action_visits.items()),
            "counts": [[k, list(v.items())] for k, v in learner.counts.items()],
            "dest_map": list(learner.dest_map.items())}


def fingerprint(value):
    # Learner dictionary insertion order is explicitly encoded as ordered lists.
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def restore_learner(module, data):
    learner = module.StructuralLearner(module.NUM_ACTIONS)
    learner.id_to_state = [tuple(s) for s in data["id_to_state"]]
    learner.state_to_id = {tuple(s): i for s, i in data["state_to_id"]}
    learner.node_visits = dict(data["node_visits"])
    learner.action_visits = {tuple(k): v for k, v in data["action_visits"]}
    learner.counts = {tuple(k): dict(v) for k, v in data["counts"]}
    learner.dest_map = {tuple(k): v for k, v in data["dest_map"]}
    assert fingerprint(payload(learner)) == fingerprint(data)
    return learner


def restore_game(module, data):
    game = module.MicroGame(data["width"], data["height"])
    for name, value in data.items():
        if name in ("walls", "hazards"):
            value = {tuple(x) for x in value}
        elif name.endswith("_pos") or name in ("teleport_a", "teleport_b"):
            value = tuple(value) if value is not None else None
        setattr(game, name, value)
    assert fingerprint(game.to_dict()) == fingerprint(data)
    return game


class FrozenPlayback:
    """Execute the unchanged self-play statements, without initial training."""
    def __init__(self, module):
        source = ast.parse(inspect.getsource(module.evaluate_game)).body[0]
        start = next(i for i, s in enumerate(source.body) if isinstance(s, ast.Assign)
                     and ast.unparse(s.targets[0]) == "K")
        end = next(i for i, s in enumerate(source.body) if isinstance(s, ast.Assign)
                   and ast.unparse(s.targets[0]) == "random_result")
        body = copy.deepcopy(source.body[start:end])
        trial_loop = next(s for s in body if isinstance(s, ast.For) and ast.unparse(s.target) == "trial")
        original_trial_dump = ast.dump(trial_loop, include_attributes=False)
        step_loop = next(s for s in trial_loop.body if isinstance(s, ast.For))
        readout_start = next(i for i, s in enumerate(step_loop.body) if isinstance(s, ast.Assign)
                             and ast.unparse(s.targets[0]) == "u")
        fallback_index = next(i for i, s in enumerate(step_loop.body) if isinstance(s, ast.If)
                              and ast.unparse(s.test) == "best_a is None or best_val <= 1e-08")
        readout = copy.deepcopy(step_loop.body[readout_start:fallback_index])
        readout += ast.parse("fallback = best_a is None or best_val <= 1e-8").body
        readout += [copy.deepcopy(step_loop.body[fallback_index])]
        readout += ast.parse("return int(best_a), float(best_val), bool(fallback)").body
        chooser = ast.parse("def original_readout(learner, st, psi, trial): pass").body[0]
        chooser.body = readout
        body.insert(0, ast.parse("trial_records = []").body[0])
        trial_loop.body += ast.parse("trial_records.append({'trial': trial, 'actions': recorded_actions, 'states': recorded_states, 'success': bool(reached)})").body
        body += ast.parse("return {'trials': trial_records, 'successes': mortra_successes, 'psi': psi, 'goal_indices': goal_indices}").body
        function = ast.parse("def snapshot_play(game, learner, self_play_trials=50, max_play_steps=100): pass").body[0]
        function.body = body
        tree = ast.fix_missing_locations(ast.Module(body=[function, chooser], type_ignores=[]))
        namespace = dict(vars(module))
        exec(compile(tree, "<frozen-v2-snapshot-playback>", "exec"), namespace)
        self.play = namespace["snapshot_play"]
        self.choose = namespace["original_readout"]
        self.original_trial_ast_sha = hashlib.sha256(original_trial_dump.encode()).hexdigest()

    def evaluate(self, game, learner, trials=50, max_steps=100):
        original = fingerprint(payload(learner))
        frozen = copy.deepcopy(learner)
        game_hash = fingerprint(game.to_dict())
        started = time.process_time()
        result = self.play(game, frozen, trials, max_steps)
        result["cpu_seconds"] = time.process_time() - started
        assert fingerprint(payload(frozen)) == original == fingerprint(payload(learner))
        assert fingerprint(game.to_dict()) == game_hash
        result["learner_unchanged"] = True
        result["actual_actions"] = sum(len(t["actions"]) for t in result["trials"])
        result["mean_capped_cost"] = float(np.mean([len(t["actions"]) if t["success"] else max_steps for t in result["trials"]]))
        return result


class FeedbackPlayer:
    def __init__(self, module, playback, game, learner, arm):
        assert arm in ARMS
        self.module, self.playback, self.game, self.learner, self.arm = module, playback, game, learner, arm
        assert type(learner) is module.StructuralLearner
        self.selector = TaskBlindSelector("virtual_frontier") if arm == ARMS[2] else None
        self.game_hash = fingerprint(game.to_dict())
        self.state = game.get_initial_state()
        if game.is_goal(self.state):
            raise ValueError("Initial state already accepting: fixed positive action budget cannot use zero-action rollouts")
        self.trial = self.rollout_steps = self.steps = 0
        self.resets = self.fallback_calls = self.selector_calls = self.successes = 0
        self.field_recomputations = 0
        self.first_goal_observation = None
        self.actions, self.rollouts, self.fields = [], [], []
        self.known_goals = {u for u, s in enumerate(learner.id_to_state) if game.is_goal(s)}
        self.first_known_goal = 0 if self.known_goals else None
        self.cpu_seconds = self.wall_seconds = 0.0
        self.field_cpu = self.selector_cpu = 0.0
        self.recompute("initial")

    def recompute(self, reason):
        start = time.process_time()
        kernel = self.learner.build_k_support()
        self.psi = np.zeros(len(self.learner.id_to_state))
        iterations, residual, converged = 0, 0.0, True
        if self.known_goals:
            self.psi, iterations, residual, converged = self.module.solve_fixed_field(kernel, sorted(self.known_goals), q=0.90)
        elapsed = time.process_time() - start
        self.field_cpu += elapsed
        self.field_recomputations += 1
        self.fields.append({"step": self.steps, "reason": reason, "known_goal_ids": sorted(self.known_goals),
                            "states": len(self.psi), "iterations": iterations, "residual": residual,
                            "converged": converged, "cpu_seconds": elapsed})

    def step(self):
        learner = self.learner
        if self.rollout_steps == 100 or self.game.is_goal(self.state):
            self.state = self.game.get_initial_state()
            self.trial += 1
            self.rollout_steps = 0
            self.resets += 1
        before_states = len(learner.id_to_state)
        if self.arm != ARMS[0]:
            learner.get_or_add_id(self.state)
            if len(learner.id_to_state) != before_states:
                self.recompute("observed current state")
        action, best_value, fallback = self.playback.choose(learner, self.state, self.psi, self.trial)
        telemetry = None
        if fallback:
            self.fallback_calls += 1
            if self.selector is not None:
                start = time.process_time()
                decision, telemetry = self.selector.choose(learner, self.state)
                self.selector_cpu += time.process_time() - start
                action = int(decision.action)
                self.selector_calls += 1
                assert telemetry["source_min"] in (None, 1.0) and telemetry["source_max"] in (None, 1.0)
        next_state = self.game.step(self.state, action)
        reached = bool(self.game.is_goal(next_state))
        self.steps += 1
        self.rollout_steps += 1
        if reached and self.first_goal_observation is None:
            self.first_goal_observation = self.steps
        self.actions.append({"step": self.steps, "trial": self.trial, "rollout_step": self.rollout_steps,
            "state": self.state, "action": action, "next_state": next_state, "success": reached,
            "fallback": fallback, "selector_called": bool(fallback and self.selector is not None),
            "best_value": best_value, "telemetry": telemetry})
        if self.arm != ARMS[0]:
            u = learner.get_or_add_id(self.state)
            old_n = len(learner.id_to_state)
            old_dest = learner.dest_map.get((u, action))
            v = learner.get_or_add_id(next_state)
            learner.record_transition(u, action, v)
            new_goal = reached and v not in self.known_goals
            if new_goal:
                self.known_goals.add(v)
                if self.first_known_goal is None:
                    self.first_known_goal = self.steps
            if old_n != len(learner.id_to_state) or old_dest != learner.dest_map[(u, action)] or new_goal:
                self.recompute("observed structure/goal change")
        self.state = next_state
        if reached or self.rollout_steps == 100:
            self.successes += int(reached)
            self.rollouts.append({"trial": self.trial, "end_step": self.steps, "actions": self.rollout_steps,
                                  "success": reached, "termination": "success" if reached else "100_actions"})

    def advance_to(self, budget):
        start_cpu, start_wall = time.process_time(), time.perf_counter()
        while self.steps < budget:
            self.step()
        self.cpu_seconds += time.process_time() - start_cpu
        self.wall_seconds += time.perf_counter() - start_wall
        assert self.steps == budget
        assert fingerprint(self.game.to_dict()) == self.game_hash

    def stats(self):
        return {"additional_actions": self.steps, "resets": self.resets,
                "completed_rollouts": len(self.rollouts), "training_successes": self.successes,
                "current_rollout_actions": self.rollout_steps, "known_states": len(self.learner.id_to_state),
                "known_pairs": len(self.learner.counts), "known_goals": len(self.known_goals),
                "recorded_transition_count": sum(sum(v.values()) for v in self.learner.counts.values()),
                "first_goal_observation_step": self.first_goal_observation,
                "first_known_goal_step": self.first_known_goal, "fallback_calls": self.fallback_calls,
                "selector_calls": self.selector_calls, "field_recomputations": self.field_recomputations,
                "online_cpu_seconds": self.cpu_seconds, "online_wall_seconds": self.wall_seconds,
                "field_cpu_seconds": self.field_cpu, "selector_cpu_seconds": self.selector_cpu}
