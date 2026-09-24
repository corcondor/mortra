import copy
from pathlib import Path

import pytest

from scripts import evaluate_future_refinement_game_duel as duel


class StepGame:
    def __init__(self, goal):
        self.goal = goal

    def get_initial_state(self):
        return 0

    def step(self, state, action):
        return state + 1

    def is_goal(self, state):
        return state == self.goal


@pytest.mark.parametrize("goal,horizon,expected", [(0,5,50),(1,5,50),(5,5,50),(6,5,0)])
def test_random_one_boolean_per_trial(goal, horizon, expected):
    result = duel.random_trials(StepGame(goal), 50, horizon, 99)
    assert result["successes"] == expected
    assert 0 <= result["successes"] <= result["trials"] == 50
    assert result["successes"] == sum(row["success"] for row in result["records"])


def test_safe_legacy_loader_and_definition_roundtrip():
    report = duel.ROOT / "reports/self_game_design/run.log"
    before = report.read_bytes() if report.exists() else None
    design = duel.legacy_design()
    game = design.MicroGame(seed=17)
    game.generate_random()
    other = duel.from_definition(game.to_dict(), design)
    assert other.to_dict() == game.to_dict()
    s = game.get_initial_state()
    for a in (0,1,2,3,4)*10:
        assert other.step(s,a) == game.step(s,a)
        s = game.step(s,a)
    assert (report.read_bytes() if report.exists() else None) == before


def train(condition):
    model = duel.old.HistoryModel(2) if condition == "OLD" else duel.FutureRefinementCore((0,1))
    handles = []
    for obs in ([0,2,3,4], [1,2,3,5]):
        model.begin(obs[0])
        handles.append(model.current)
        for step, (a,o) in enumerate(zip((0,0,1),obs[1:]),1):
            if condition == "OLD":
                model.observe(a,o,step)
            else:
                model.observe(a,o)
            handles.append(model.current)
    return model, handles


@pytest.mark.parametrize("condition", ["OLD","NEW"])
def test_frozen_encoder_matches_all_training_histories_without_learning(condition):
    model, handles = train(condition)
    before = copy.deepcopy((model.raw, model.rules, model.mapping, model.model))
    actual = []
    for obs in ([0,2,3,4], [1,2,3,5]):
        encoder = duel.FrozenEncoder(model,condition)
        actual.append(encoder.begin(obs[0]))
        for a,o in zip((0,0,1),obs[1:]):
            actual.append(encoder.advance(a,o))
    expected = [model.encode(h) if condition == "OLD" else model.encode_known_history_node(h) for h in handles]
    assert actual == expected
    assert (model.raw,model.rules,model.mapping,model.model) == before
    assert duel.FrozenEncoder(model,condition).begin(999999) is None


def test_new_adapter_preserves_observed_support_and_omits_unknown_actions():
    model,_ = train("NEW")
    K,rows,labels = duel.planner_model(model,"NEW")
    assert {key:frozenset(row) for key,row in rows.items()} == model.quotient_support()
    assert all(sum(row.values()) == 1 for row in rows.values())
    assert all(sum(row.values()) == 1 for row in K)
    assert len(rows) < len(labels)*2
    assert not any(hasattr(model,n) for n in ("q","goal","discount","reward"))


def test_old_adapter_is_exactly_existing_reasoner_input():
    model,_ = train("OLD")
    K,rows,labels = duel.planner_model(model,"OLD")
    assert K is model.model["K"]
    assert rows is model.model["rows"]
    assert labels == list(model.labels)


def test_external_oracle_replays_shortest_witness():
    design = duel.legacy_design()
    game = design.MicroGame(width=5,height=5)
    game.start_pos,game.goal_pos = (1,1),(3,1)
    game.walls = {(x,y) for x in range(5) for y in range(5) if x in (0,4) or y in (0,4)}
    result = duel.exact_solvability(game)
    assert result["solvable"] and len(result["shortest_actions"]) == 2
    state = game.get_initial_state()
    for action in result["shortest_actions"]:
        state = game.step(state,action)
    assert game.is_goal(state)
    game.walls.add((3,1))
    assert not duel.exact_solvability(game)["solvable"]


def test_source_freeze():
    duel.verify_sources()


def test_same_readout_goal_count_serialization_and_recorded_plot(tmp_path):
    import json
    design = duel.legacy_design()
    game = design.MicroGame(width=5,height=5)
    game.start_pos,game.goal_pos = (1,1),(3,1)
    game.walls = {(x,y) for x in range(5) for y in range(5) if x in (0,4) or y in (0,4)}
    results = {}
    for condition in ("OLD","NEW"):
        model = duel.old.HistoryModel(5) if condition == "OLD" else duel.FutureRefinementCore(tuple(range(5)))
        model.begin(1)
        for step, obs in enumerate((2,3),1):
            if condition == "OLD": model.observe(3,obs,step)
            else: model.observe(3,obs)
        results[condition] = duel.play(game,model,condition,
                                      lambda x,eval_mode=False:x, lambda g,s,t:s[0],
                                      [3],17,{"trials":2,"horizon":2})
        assert results[condition]["successes"] == 2
        assert results[condition]["trials"][0]["actions"] == [3,3]
        json.dumps(results[condition])
    duel.render_result(design,game,results,tmp_path/"first_trial.png",17)
    assert (tmp_path/"first_trial.png").stat().st_size > 1000
