"""Execution-only checks, separate from formal image trajectories."""
import json
from pathlib import Path
import types

import numpy as np
import pytest

from scripts import evaluate_raw_visual_sequential as raw
from mortra_predictive_perception.optimized import HistoryColumns, ValidColumns


@pytest.mark.parametrize("target",["absolute","delta"])
def test_prefix_gate_checks_exact_tree_bic_and_symbols(target):
    data = [(np.array([[0.,1.],[1.,0.],[0.,1.],[2.,0.]]),[0,1,0]),
            (np.array([[2.,1.],[0.,0.]]),[1])]
    result = raw.assert_backend_equivalence(data,(0,1),target)
    for field in ("selected_feature_equal","threshold_equal","BIC_equal","all_symbol_assignments_equal"):
        assert result[field] is True
    assert len(result["assignments"]) == 2


def test_mismatch_blocks_gate(monkeypatch):
    original = raw.SweepResponseSymbolizer.export_tree
    def different(self):
        result = original(self)
        result["unexpected_difference"] = True
        return result
    monkeypatch.setattr(raw.SweepResponseSymbolizer,"export_tree",different)
    with pytest.raises(AssertionError,match="tree/threshold"):
        raw.assert_backend_equivalence([(np.array([[0.],[1.],[0.]]),[0,0])],(0,),"delta")


@pytest.mark.parametrize("target",["absolute","delta"])
def test_full_fit_never_calls_dense_reference(tmp_path,monkeypatch,target):
    def forbidden(*args,**kwargs):
        raise AssertionError("Dense reference training arrays must not run here")
    monkeypatch.setattr(raw.ResponseSymbolizer,"_build_training_arrays",forbidden)
    data = [(np.array([[0.,0.],[1.,1.],[0.,0.],[1.,1.]]),[0,1,0])]
    model,world,_,_,costs = raw.fit_optimized(data,data,(0,1),target,tmp_path)
    assert isinstance(model._feature_matrix,HistoryColumns)
    assert isinstance(model._feature_valid,ValidColumns)
    assert model.report.n_transitions == 3
    assert model.report.max_observed_history == 3
    assert costs["reference"]["cpu_seconds"] == 0
    backend = raw.run.read(tmp_path/f"{target}_backend.json")
    assert backend["backend"] == "optimized_exact_equivalent"
    assert backend["full_N_by_F_array_materialized"] is False
    assert backend["logical_shape"] == [3, 2+3*(2+2)]
    assert world.connection_audit()["training_transitions_checked"] == 3


def test_missing_global_gate_refuses_environment(tmp_path):
    raw.run.save(tmp_path/"source_sha.json",{})
    with pytest.raises(FileNotFoundError):
        raw.verify_gate(tmp_path)


def test_child_exit_releases_arrays_and_is_not_task_failure(tmp_path,monkeypatch):
    case = {"id":"development_raw","domain":"raw_visual"}
    monkeypatch.setattr(raw,"verify_gate",lambda _:None)
    calls = []
    def interrupted(command,**kwargs):
        calls.append((command,kwargs))
        assert "timeout" not in kwargs
        return types.SimpleNamespace(returncode=137)
    monkeypatch.setattr(raw.subprocess,"run",interrupted)
    raw.run_isolated(case,tmp_path)
    assert len(calls) == 1
    result = raw.run.read(tmp_path/"cases/development_raw/result.json")
    assert result["status"] == "RUN NOT COMPLETED"
    assert result["conditions"] == {}
    release = raw.run.read(tmp_path/"cases/development_raw/process_release.json")
    assert release["all_child_process_arrays_released_by_process_exit"]
    assert release["returncode"] == 137


def test_all_global_checks_required(tmp_path):
    raw.run.save(tmp_path/"source_sha.json",{})
    raw.run.save(tmp_path/"config.json",{"cases":[{"id":"development_raw"}]})
    raw.run.save(tmp_path/"prefix_gate.json",{
        "status":"PASS","source_sha256":{},"required_cases":[]})
    with pytest.raises(AssertionError):
        raw.verify_gate(tmp_path)
