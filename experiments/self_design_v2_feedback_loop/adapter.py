"""Connect the tested C feedback, without changing the frozen design loop.

No loop experiment is launched by this module. Each evaluate_game invocation
constructs a new V2 learner, including after a game version change.
"""
import ast
import inspect
from pathlib import Path

from experiments.task_agent.pretraining import TaskBlindSelector
from experiments.v2_online_feedback.adapter import ARMS, FeedbackPlayer, FrozenPlayback, fingerprint, payload
from experiments.v2_online_feedback.prepare import write
from experiments.v2_online_feedback.run import rows_write


class FeedbackLoopAdapter:
    def __init__(self, module, output):
        self.module, self.output = module, Path(output)
        self.original = module.evaluate_game
        self.playback = FrozenPlayback(module)
        self.records = []
        self.selector = None
        source = ast.parse(inspect.getsource(self.original))
        replacements = 0
        class ReplaceTrainingSelector(ast.NodeTransformer):
            def visit_Call(self, node):
                nonlocal replacements
                if ast.unparse(node.func) == "learner.select_action":
                    assert ast.unparse(node) == "learner.select_action(curr_u)"
                    replacements += 1
                    return ast.copy_location(ast.parse("_training_action(learner, curr_state)", mode="eval").body, node)
                return self.generic_visit(node)
        source = ReplaceTrainingSelector().visit(source)
        assert replacements == 1
        body = source.body[0].body
        k_index = next(i for i, stmt in enumerate(body) if isinstance(stmt, ast.Assign) and ast.unparse(stmt.targets[0]) == "K")
        body.insert(k_index, ast.parse("_feedback(game, learner)").body[0])
        namespace = dict(vars(module))
        namespace.update(_training_action=self.training_action, _feedback=self.feedback)
        exec(compile(ast.fix_missing_locations(source), "<v2-feedback-loop-adapter>", "exec"), namespace)
        self.evaluator = namespace["evaluate_game"]

    def training_action(self, learner, state):
        assert type(learner) is self.module.StructuralLearner
        decision, telemetry = self.selector.choose(learner, state)
        assert telemetry["source_min"] in (None, 1.0)
        assert telemetry["source_max"] in (None, 1.0)
        return int(decision.action)

    def feedback(self, game, learner):
        directory = self.output / f"evaluation_{len(self.records):03d}"
        directory.mkdir(parents=True, exist_ok=False)
        game_hash = fingerprint(game.to_dict())
        write(directory / "game.json", game.to_dict())
        write(directory / "initial_learner.json", payload(learner))
        player = FeedbackPlayer(self.module, self.playback, game, learner, ARMS[2])
        try:
            player.advance_to(5000)
        except BaseException as error:
            write(directory / "incomplete.json", {"status": "RUN_NOT_COMPLETED", "reason": repr(error)})
            raise
        finally:
            rows_write(directory / "additional_actions.jsonl.gz", player.actions)
            write(directory / "final_learner.json", payload(learner))
            write(directory / "feedback_metrics.json", player.stats())
        assert game_hash == fingerprint(game.to_dict())
        self.records.append({"directory": directory, "game_hash": game_hash, **player.stats()})

    def evaluate(self, game, explore_steps=2500, self_play_trials=50, max_play_steps=100):
        # The frozen evaluator creates a fresh learner on every call.
        self.selector = TaskBlindSelector("virtual_frontier")
        metrics = self.evaluator(game, explore_steps, self_play_trials, max_play_steps)
        metrics["additional_feedback_actions"] = 5000
        metrics["total_learning_actions"] = explore_steps + 5000
        write(self.records[-1]["directory"] / "evaluation_metrics.json", metrics)
        return metrics

    def install(self):
        self.module.evaluate_game = self.evaluate

    def restore(self):
        self.module.evaluate_game = self.original
