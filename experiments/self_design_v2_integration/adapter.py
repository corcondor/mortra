"""Only replace the training select_action call; observe everything else."""
import ast
from collections import defaultdict
import gzip
import importlib.util
import inspect
import json
from pathlib import Path
import sys
import time

from experiments.task_agent.pretraining import TaskBlindSelector, METHODS
from .verify import ROOT, write


def load_v2():
    source = ROOT / "scripts/evaluate_autonomous_game_design_loop.py"
    spec = importlib.util.spec_from_file_location("self_design_v2_frozen", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def json_default(value):
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(type(value).__name__)


def make_evaluator(module, choose):
    tree = ast.parse(inspect.getsource(module.evaluate_game))
    replaced = 0
    class Replace(ast.NodeTransformer):
        def visit_Call(self, node):
            nonlocal replaced
            if (isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "learner" and node.func.attr == "select_action"):
                assert ast.unparse(node) == "learner.select_action(curr_u)"
                replaced += 1
                return ast.copy_location(ast.Call(func=ast.Name(id="_training_action", ctx=ast.Load()),
                    args=[ast.Name(id=name, ctx=ast.Load()) for name in ("learner", "curr_state", "curr_u")], keywords=[]), node)
            return self.generic_visit(node)
    tree = Replace().visit(tree)
    assert replaced == 1, "Only the single training action selector may change"
    ast.fix_missing_locations(tree)
    namespace = dict(vars(module))
    namespace["_training_action"] = choose
    exec(compile(tree, "<single-training-selector-adapter>", "exec"), namespace)
    return namespace["evaluate_game"], ast.dump(tree, include_attributes=False)


class EvaluationRecorder:
    def __init__(self, module, method, directory, explore_steps):
        self.module, self.method, self.directory = module, method, directory
        self.budget = explore_steps
        self.selector = None if method == "structural" else TaskBlindSelector(method)
        self.pending = None
        self.learner = None
        self.actions = []
        self.training = []
        self.factor_started = {}
        self.solve_started = None
        self.virtual_solve_cpu = 0.0
        self.goal_during_training = 0
        self.oracle_calls = 0
        self.cpu_start = time.process_time()
        self.training_cpu = None

    def choose(self, learner, state, u):
        required = ("num_actions", "state_to_id", "id_to_state", "node_visits", "action_visits",
                    "counts", "dest_map", "get_or_add_id", "record_transition")
        missing = [name for name in required if not hasattr(learner, name)]
        if missing:
            raise TypeError(f"Missing V2 learner interface: {missing}")
        assert type(learner) is self.module.StructuralLearner
        self.learner = learner
        if self.method == "structural":
            action, telemetry = learner.select_action(u), {}
        else:
            decision, telemetry = self.selector.choose(learner, state)
            action = int(decision.action)
        assert 0 <= action < learner.num_actions
        self.pending = {"step": len(self.training) + 1, "state": state, "u": u,
                        "action": action, "telemetry": telemetry}
        return action

    def profile(self, frame, event, result):
        code = frame.f_code
        if event == "call" and "oracle" in code.co_name.lower():
            self.oracle_calls += 1
            raise RuntimeError(f"Forbidden oracle call: {code.co_filename}:{code.co_firstlineno}")
        if event == "call" and code is self.module.MicroGame.is_goal.__code__ and len(self.training) < self.budget:
            self.goal_during_training += 1
            raise RuntimeError("Goal queried during task-blind training")
        if event == "call" and code is self.module.StructuralLearner.build_k_support.__code__:
            self.training_cpu = time.process_time() - self.cpu_start
        if event == "return" and code.co_name == "build_frontier_fields":
            assert code.co_filename.replace("\\", "/").endswith("task_agent/virtual_frontier.py")
            assert (result.sources[len(result.states):] == 1.0).all()
            assert frame.f_globals["Q"] == 0.90
        if event == "return" and code is self.module.StructuralLearner.record_transition.__code__:
            learner = frame.f_locals["self"]
            assert self.pending is not None
            u, a, v = (frame.f_locals[k] for k in ("u", "a", "v"))
            assert (u, a) == (self.pending["u"], self.pending["action"])
            self.pending.update(next_state=learner.id_to_state[v], v=v,
                                known_states=len(learner.id_to_state), known_pairs=len(learner.counts))
            self.training.append(self.pending)
            self.pending = None
        if event == "return" and code is self.module.MicroGame.step.__code__:
            caller = frame.f_back
            if self.pending is not None:
                phase, trial = "training", None
            elif caller.f_code is self.module.evaluate_random_player.__code__:
                phase, trial = "random", caller.f_locals["trial"]
            elif "psi_aux" in caller.f_locals:
                phase, trial = "auxiliary", 0
            else:
                phase, trial = "mortra", caller.f_locals.get("trial")
            self.actions.append({"phase": phase, "trial": trial, "state": frame.f_locals["state"],
                                 "action": frame.f_locals["action"], "next_state": result})
        if code.co_name == "splu" and "scipy" in code.co_filename:
            if event == "call":
                self.factor_started[id(frame)] = time.process_time()
            elif event == "return":
                self.virtual_solve_cpu += time.process_time() - self.factor_started.pop(id(frame))
        if event in ("c_call", "c_return") and getattr(result, "__name__", "") == "solve" and type(getattr(result, "__self__", None)).__name__ == "SuperLU":
            if event == "c_call":
                self.solve_started = time.process_time()
            elif self.solve_started is not None:
                self.virtual_solve_cpu += time.process_time() - self.solve_started
                self.solve_started = None

    def save(self, game, metrics):
        assert len(self.training) == self.budget
        learner = self.learner
        assert sum(learner.action_visits.values()) == self.budget
        groups = defaultdict(list)
        for item in self.actions:
            groups[(item["phase"], item["trial"])].append(item)
        for (phase, trial), rows in groups.items():
            state = game.get_initial_state()
            for row in rows:
                assert tuple(row["state"]) == state
                state = game.step(state, row["action"])
                assert state == tuple(row["next_state"])
            if phase in ("mortra", "random") and trial == 0:
                replay = metrics[f"{phase}_replay"]
                assert [r["action"] for r in rows] == replay["actions"]
                assert game.is_goal(state) == replay["reached_goal"]
        for phase, key in (("mortra", "successes"), ("random", "random_successes")):
            successes = sum(game.is_goal(rows[-1]["next_state"]) for (p, _), rows in groups.items() if p == phase)
            if game.is_goal(game.get_initial_state()):
                successes = metrics["trials"]
            assert successes == metrics[key], (phase, successes, metrics[key])
        for name, rows in (("training.jsonl.gz", self.training), ("actions.jsonl.gz", self.actions)):
            with gzip.open(self.directory / name, "xt", encoding="utf-8") as stream:
                for row in rows:
                    stream.write(json.dumps(row, default=json_default, allow_nan=False) + "\n")
        write(self.directory / "learner.json", {
            "id_to_state": learner.id_to_state, "state_to_id": list(learner.state_to_id.items()),
            "node_visits": list(learner.node_visits.items()), "action_visits": list(learner.action_visits.items()),
            "counts": [[k, list(v.items())] for k, v in learner.counts.items()], "dest_map": list(learner.dest_map.items())})
        return {"training_steps": len(self.training), "known_states": len(learner.id_to_state),
                "known_state_action_pairs": len(learner.counts), "training_cpu_seconds": self.training_cpu,
                "virtual_factorization_and_solve_cpu_seconds": self.virtual_solve_cpu,
                "oracle_calls": self.oracle_calls, "goal_queries_during_training": self.goal_during_training,
                "replay_all_recorded_actions_verified": True,
                "trials_recorded": {phase: sum(p == phase for p, _ in groups) for phase in ("mortra", "random")}}


class Integration:
    def __init__(self, module, method, directory):
        assert method in METHODS
        self.module, self.method, self.directory = module, method, Path(directory)
        self.original_evaluate = module.evaluate_game
        self.recorder = None
        self.evaluations = []
        self.evaluator, self.adapter_ast = make_evaluator(module, self.choose)

    def choose(self, learner, state, u):
        return self.recorder.choose(learner, state, u)

    def evaluate(self, game, explore_steps=2500, self_play_trials=50, max_play_steps=100):
        directory = self.directory / f"evaluation_{len(self.evaluations):03d}"
        directory.mkdir(parents=True, exist_ok=False)
        write(directory / "game.json", game.to_dict())
        recorder = EvaluationRecorder(self.module, self.method, directory, explore_steps)
        self.recorder = recorder
        prior = sys.getprofile()
        cpu, wall = time.process_time(), time.perf_counter()
        try:
            sys.setprofile(recorder.profile)
            metrics = self.evaluator(game, explore_steps, self_play_trials, max_play_steps)
        finally:
            sys.setprofile(prior)
        cpu, wall = time.process_time() - cpu, time.perf_counter() - wall
        audit = recorder.save(game, metrics)
        audit.update(total_evaluation_cpu_seconds=cpu, evaluation_wall_seconds=wall)
        write(directory / "metrics.json", metrics)
        write(directory / "audit.json", audit)
        self.evaluations.append(audit)
        return metrics

    def install(self):
        self.module.evaluate_game = self.evaluate

    def restore(self):
        self.module.evaluate_game = self.original_evaluate
