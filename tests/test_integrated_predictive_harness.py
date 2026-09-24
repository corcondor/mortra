"""Harness checks use synthetic data, never the formal benchmark for tuning."""
import json
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

from scripts import integrated_predictive_evaluation as ev
from scripts import evaluate_integrated_predictive_world_model as run
from scripts import integrated_predictive_visual_evaluation as visual
from mortra_predictive_perception.shared_data import save_episodes


def test_neutral_guarantee_checks_every_successor():
    model = ev.NeutralModel((0,1),{0:"x",1:"goal",2:"bad"},
                            {(0,0):{1:1},(0,1):{1:1,2:1},(2,0):{2:1},(2,1):{2:1}}, {0})
    result = model.solve(frozenset({0}),{1})
    assert result["ranks"][frozenset({0})] == 1
    assert result["policy"][frozenset({0})] == 0
    assert frozenset({2}) not in result["ranks"]
    assert frozenset({ev.UNKNOWN}) not in result["ranks"]
    assert not model.solve(frozenset(),{1})["policy"]


def test_unknown_and_contradiction_are_not_fabricated():
    model = ev.NeutralModel((0,),{0:"x",1:"y"},{(0,0):{1:1}},{0})
    assert model.advance(frozenset({0}),0,"x") == frozenset()
    assert model.advance(frozenset({1}),0,"z") == frozenset({ev.UNKNOWN})
    assert not model.solve(frozenset({1}),{0})["policy"]


def test_operator_external_projection():
    audit = ev.audit_operator([0,0,1],[(0,)]*3,{(0,0):{2:1},(1,0):{2:2}},
                              [0,0,1],{(0,0):{1:Fraction(1)}})
    assert audit["eps_action"] == 0
    assert audit["observations_preserved"]
    bad = ev.audit_operator([0,0,1],[(0,)]*3,{(0,0):{2:1},(1,0):{2:2}},
                            [0,0,1],{(0,0):{0:Fraction(1)}})
    assert bad["eps_action"] == 2


def test_common_metric_denominators_and_ambiguous_pairs():
    q = ev.common_partition([0,0,1,1],[0,1,0,1])
    assert q["predictive_violation"] == 1
    assert q["false_merge"] == .5
    assert q["false_split"] == 1
    ambiguity,indices = ev.ambiguity_diagnostics([[0]]*4,[0,1,0,1],[0,0,1,1])
    assert ambiguity["same_observation_different_future_pairs"] == 4
    assert ambiguity["collision_pairs"] == 2
    assert indices == {0,1,2,3}


def test_frozen_source_manifest_matches():
    manifest = run.ROOT / "configs/integrated-predictive-source-sha.json"
    if not manifest.exists():
        pytest.skip("CI manifest packaging has not run yet")
    for relative, expected in run.read(manifest).items():
        assert run.sha(run.ROOT/relative) == expected


def test_full_finite_adapter_synthetic_only(tmp_path):
    case = {"id":"test_only","domain":"finite","spec":{"n":4,"actions":2,"seed":1234567,"kind":"random","steps":8}}
    config = {"planning_horizon":8,"evaluation_goals":2}
    table,labels = run.old.finite_world(4,2,1234567,"random")
    def episode(acts):
        state = 0
        hidden = [state]
        for a in acts:
            state = int(table[state,a]); hidden.append(state)
        return np.asarray([[labels[s]] for s in hidden],dtype=float),acts,hidden
    train,acts,_ = episode([0,1,0,1,1,0,1,0])
    test,test_acts,hidden = episode([1,0,1,1,0,0,1,0])
    data = tmp_path/"datasets"/case["id"]
    data.mkdir(parents=True)
    a = save_episodes(data/"train.npz",[(train,acts)])
    b = save_episodes(data/"heldout.npz",[(test,test_acts)])
    run.save(data/"manifest.json",{"train":a,"heldout":b})
    run.save(data/"hidden_evaluator_only.json",[hidden])
    run.save(tmp_path/"source_sha.json",{})
    result = run.run_case(case,str(tmp_path),config)
    assert result["status"] == "COMPLETE", result.get("exception")
    for condition,values in result["conditions"].items():
        assert values["operator"]["eps_action"] == 0
        assert values["complete_system"]["successes"] <= values["complete_system"]["trials"]
        if condition != "OLD":
            assert values["memory"]["recursive_full_history_agreement"] == 1
    result = run.summarize(tmp_path,{"cases":[case]})
    assert result["status"] == "COMPLETE"


@pytest.mark.parametrize("domain",["MicroGame","raw_visual"])
def test_visual_old_adapter_saved_frames_only(domain):
    legacy = run.load_legacy_visual(run.ROOT/"scripts/evaluate_visual_state_construction.py")
    frames = [np.zeros(576),np.ones(576),np.zeros(576)]
    episodes = [(frames,(0,1))]
    fitted = visual.train_old(domain,episodes,episodes,legacy)
    assert len(fitted["test_states"][0]) == 3
    assert fitted["states"] > 0


def test_resource_failure_is_not_capability_failure(tmp_path, monkeypatch):
    case = {"id":"memory_test","domain":"finite","spec":{"actions":2}}
    data = tmp_path/"datasets"/case["id"]
    data.mkdir(parents=True)
    episode = [([np.array([0.]),np.array([1.])],[0])]
    train = save_episodes(data/"train.npz",episode)
    heldout = save_episodes(data/"heldout.npz",episode)
    run.save(data/"manifest.json",{"train":train,"heldout":heldout})
    run.save(tmp_path/"source_sha.json",{})
    monkeypatch.setattr(run.psutil,"virtual_memory",lambda:type("Memory",(),{"available":0})())
    result = run.run_case(case,tmp_path,{})
    assert result["status"] == "RESOURCE UNAVAILABLE - NOT RUN"
    assert all(c["status"].startswith("NOT RUN") for c in result["conditions"].values())


@pytest.mark.parametrize("domain",["MicroGame","raw_visual"])
def test_full_visual_evaluator_synthetic_only(tmp_path,domain):
    case = {"domain":domain,"spec":{"seed":1234567},"evaluation_trials":1}
    config = {"planning_horizon":2}
    frames = [np.zeros(576),np.zeros(576),np.zeros(576)]
    episodes = [(frames,(0,1))]
    hidden_path = tmp_path/"hidden.json"
    run.save(hidden_path,[[[0],[1],[0]]])
    result = visual.evaluate(case,episodes,episodes,hidden_path,config,run.ROOT,tmp_path,
                             run.fit_new,run.save,lambda stage:None)
    for condition,row in result.items():
        assert row["status"] == "COMPLETE"
        assert row["complete_system"]["successes"] <= 1
        if condition != "OLD":
            assert row["memory"]["recursive_full_history_agreement"] == 1
    json.dumps(result,allow_nan=False)


@pytest.mark.parametrize("domain",["MicroGame","raw_visual"])
def test_shared_collector_synthetic_only(tmp_path,domain):
    prior = tmp_path/"source.json"
    run.save(prior,{"stream":[[None,0],[0,0],[1,0]]})
    case = {"id":"collector_test","domain":domain,"spec":{"seed":1234567,"actions":5,"steps":2},
            "evaluation_seed":2345678,"evaluation_trials":1,
            "prior":str(prior) if domain=="MicroGame" else None}
    manifest = run.prepare_case(case,tmp_path,{"planning_horizon":2})
    folder = tmp_path/"datasets"/"collector_test"
    data = run.load_episodes(folder/"train.npz",manifest["train"]["sha256"])
    assert len(data[0][1]) == 2
    assert data[0][0][0].size == 576
    assert not data[0][0][0].flags.writeable
