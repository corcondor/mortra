"""Smoke runner for the integrated Task Agent.

This file intentionally imports MORTRA's canonical learner/engine rather than
embedding copies. Large experiment configuration should live beside this script.
"""
from experiments.game_frontier_v1.frozen import StructuralLearner
from experiments.game_frontier_v11.world import Engine
from experiments.task_agent import (
    ExactState, SequenceTask, ProductPlanner,
    FrozenStructuralPolicy, TaskConditionedPolicy, OnlineTaskAgent,
)


def build_agent(engine, policy="task_conditioned"):
    learner = StructuralLearner(engine.num_actions)
    planner = ProductPlanner(q=.90)
    if policy == "structural":
        exploration = FrozenStructuralPolicy()
    elif policy == "task_conditioned":
        exploration = TaskConditionedPolicy(planner)
    else:
        raise ValueError(policy)
    return OnlineTaskAgent(learner, exploration, planner=planner)
