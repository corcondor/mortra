"""Sequential raw-image execution with the unchanged lazy sweep backend.

Only execution/storage changes: reference equality on saved trajectory prefixes,
then full-data optimized fitting. No change to any learning or planning rule.
"""
from __future__ import annotations

import os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
from datetime import datetime, timezone
import argparse
import csv
import gc
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import evaluate_integrated_predictive_world_model as run
from scripts import integrated_predictive_ci as ci
from scripts import integrated_predictive_evaluation as ev
from scripts import integrated_predictive_visual_evaluation as visual
from mortra_predictive_perception.adapters import ResponseSymbolizer
from mortra_predictive_perception.optimized import SweepResponseSymbolizer, HistoryColumns, ValidColumns
from mortra_predictive_perception.symbol_world import SymbolWorld

BACKEND = "optimized_exact_equivalent"
PREFIX_LENGTHS = (16, 32)
EXPECTED_SEEDS = (201, 302, 403, 504, 605)


def initialize(output, source):
    original = run.read(source/"config.json")
    cases = [c for c in original["cases"] if c["domain"] == "raw_visual"]
    assert tuple(c["spec"]["seed"] for c in cases) == EXPECTED_SEEDS
    # MicroGame remains on its own already-running immutable commit.
    ci.initialize(output)
    hashes = run.read(source/"shared_dataset_hashes.json")
    selected = [r for r in hashes if r["case"]["domain"] == "raw_visual"]
    assert [r["case"] for r in selected] == cases
    for record in selected:
        origin = source/"datasets"/record["case"]["id"]
        for filename, key in (("train.npz", "train"), ("heldout.npz", "heldout")):
            assert run.sha(origin/filename) == record[key]["sha256"]
        assert run.sha(origin/"hidden_evaluator_only.json") == record["hidden_evaluator_only_sha256"]
        shutil.copytree(origin, output/"datasets"/record["case"]["id"])
    config = {**original, "cases":cases, "workers":1,
              "backend":BACKEND, "full_reference_fit":False,
              "reference_validation_prefix_lengths":list(PREFIX_LENGTHS),
              "prefixes_only_validate_backend_not_train_final_model":True,
              "raw_data_source_run":35975264733,
              "microgame_source_unchanged":"afca2779d549e505cf148e47182940991af2f8cd",
              "parallel_environments":1,
              "environment_memory_release":"isolated child process exits before next environment starts",
              "feature_matrix_storage":"lazy HistoryColumns and ValidColumns; never dense N x F",
              "allocation_policy":"full dense reference is not attempted; resource exhaustion is reported separately",
              "timeouts":None,
              "external_interruption":"RUN NOT COMPLETED, not task failure"}
    run.save(output/"config.json",config,exclusive=True)
    run.save(output/"shared_dataset_hashes.json",selected,exclusive=True)
    run.save(output/"rng_seeds.json",[r for r in run.read(source/"rng_seeds.json")
                                      if r["case"] in {c["id"] for c in cases}],exclusive=True)
    frozen = run.read(output/"source_sha.json")
    extra = ["scripts/evaluate_integrated_predictive_world_model.py",
             "scripts/integrated_predictive_evaluation.py",
             "scripts/integrated_predictive_visual_evaluation.py",
             "scripts/integrated_predictive_ci.py",
             "scripts/evaluate_raw_visual_sequential.py"]
    for relative in extra:
        frozen[relative] = run.sha(ROOT/relative)
        destination = output/"frozen_source"/relative
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/relative,destination)
    run.save(output/"source_sha.json",frozen)
    run.save(output/"raw_execution_sha.json",{p:frozen[p] for p in extra},exclusive=True)
    run.log(output,event="raw_inputs_frozen",cases=len(cases),backend=BACKEND,
            prefix_lengths=list(PREFIX_LENGTHS),full_training_steps=[c["spec"]["steps"] for c in cases])


def load_case(case, output):
    folder = output/"datasets"/case["id"]
    manifest = run.read(folder/"manifest.json")
    train = run.load_episodes(folder/"train.npz",manifest["train"]["sha256"])
    heldout = run.load_episodes(folder/"heldout.npz",manifest["heldout"]["sha256"])
    return folder, manifest, train, heldout


def assert_backend_equivalence(episodes, actions, target):
    models, cost = [], {}
    for name, cls in (("reference",ResponseSymbolizer),(BACKEND,SweepResponseSymbolizer)):
        wall, cpu = time.perf_counter(),time.process_time()
        model = cls(actions,target)
        for observations,controls in episodes:
            model.add_episode(observations,controls)
        model.fit()
        if name == BACKEND:
            assert isinstance(model._feature_matrix,HistoryColumns)
            assert isinstance(model._feature_valid,ValidColumns)
        cost[name] = {"wall_seconds":time.perf_counter()-wall,"cpu_seconds":time.process_time()-cpu}
        models.append(model)
    reference, optimized = models
    assert reference.report == optimized.report, "Prefix selected features/BIC differ"
    assert reference.export_tree() == optimized.export_tree(), "Prefix tree/threshold/routing differ"
    assignments = ev.new_symbols(reference,episodes)
    assert assignments == ev.new_symbols(optimized,episodes), "Prefix symbol assignments differ"
    for a,b in zip(reference._leaves(reference.tree),optimized._leaves(optimized.tree),strict=True):
        np.testing.assert_array_equal(a.row_indices,b.row_indices)
        assert a.action_means.keys() == b.action_means.keys()
        for action in a.action_means:
            np.testing.assert_array_equal(a.action_means[action],b.action_means[action])
    result = {"selected_feature_equal":True,"threshold_equal":True,"BIC_equal":True,
              "all_symbol_assignments_equal":True,"missing_routing_equal":True,
              "leaf_means_equal":True,"tree":reference.export_tree(),"assignments":assignments,
              "costs":cost,"optimized_work":optimized.work,
              "scope":"exact equality on this validation prefix, not a full-data reference execution"}
    del models,reference,optimized,model
    gc.collect()
    return result


def gate_one(case, output):
    run.frozen_check(output)
    folder = output/"gates"/case["id"]
    folder.mkdir(parents=True,exist_ok=False)
    wall,cpu = time.perf_counter(),time.process_time()
    record = {"case":case,"status":"RUNNING","checks":[]}
    try:
        _,manifest,train,_ = load_case(case,output)
        assert len(train) == 1
        obs,controls = train[0]
        record["training_dataset_sha256"] = manifest["train"]["sha256"]
        for length in PREFIX_LENGTHS:
            assert length <= len(controls)
            prefix = [(obs[:length+1],controls[:length])]
            for target in ("absolute","delta"):
                run.log(output,event="prefix_check_started",case=case["id"],target=target,length=length)
                match = assert_backend_equivalence(prefix,tuple(range(case["spec"]["actions"])),target)
                run.save(folder/f"prefix_{length}_{target}.json",match,exclusive=True)
                record["checks"].append({"length":length,"target":target,"status":"PASS",
                                         "cpu_seconds":sum(c["cpu_seconds"] for c in match["costs"].values())})
        record["status"] = "PASS"
    except MemoryError:
        record.update(status="RESOURCE UNAVAILABLE - NOT COMPLETED",exception=traceback.format_exc())
    except Exception:
        record.update(status="EQUIVALENCE GATE FAILED - DO NOT RUN RAW VISUAL",exception=traceback.format_exc())
    finally:
        run.frozen_check(output)
        record.update(cpu_seconds=time.process_time()-cpu,wall_seconds=time.perf_counter()-wall,resources=run.resources())
        run.save(folder/"result.json",record,exclusive=True)
        run.log(output,event="prefix_case_finished",case=case["id"],status=record["status"])
    return record["status"] == "PASS"


def gates(output):
    config = run.read(output/"config.json")
    status = "PASS"
    for case in config["cases"]:
        command = [sys.executable,"-u",str(Path(__file__).resolve()),"gate-one","--output",str(output),"--case",case["id"]]
        result = subprocess.run(command,check=False)  # No mathematical timeout.
        if result.returncode:
            status = "PREFIX EQUIVALENCE NOT ESTABLISHED - RAW VISUAL NOT STARTED"
            break
    gate = {"status":status,"required_cases":[c["id"] for c in config["cases"]],
            "prefix_lengths":list(PREFIX_LENGTHS),"targets":["absolute","delta"],
            "source_sha256":run.read(output/"source_sha.json"),
            "datasets":{r["case"]["id"]:r["train"]["sha256"] for r in run.read(output/"shared_dataset_hashes.json")}}
    run.save(output/"prefix_gate.json",gate,exclusive=True)
    if status != "PASS":
        raise RuntimeError(status)


def verify_gate(output):
    run.frozen_check(output)
    gate = run.read(output/"prefix_gate.json")
    assert gate["status"] == "PASS", "Raw evaluation requires all prefix checks"
    assert gate["source_sha256"] == run.read(output/"source_sha.json")
    config = run.read(output/"config.json")
    assert gate["required_cases"] == [c["id"] for c in config["cases"]]
    for case in config["cases"]:
        data = output/"datasets"/case["id"]
        assert run.sha(data/"train.npz") == gate["datasets"][case["id"]]
        result = run.read(output/"gates"/case["id"]/"result.json")
        assert result["status"] == "PASS"
        assert {(r["length"],r["target"]) for r in result["checks"] if r["status"] == "PASS"} == {
            (length,target) for length in PREFIX_LENGTHS for target in ("absolute","delta")}


def fit_optimized(episodes, heldout, actions, target, folder):
    start, wall = time.process_time(),time.perf_counter()
    model = SweepResponseSymbolizer(actions,target)
    for obs,controls in episodes:
        model.add_episode(obs,controls)
    model.fit()
    assert isinstance(model._feature_matrix,HistoryColumns), "Dense N x F features forbidden"
    assert isinstance(model._feature_valid,ValidColumns), "Dense validity matrix forbidden"
    costs = {"sweep":{"cpu_seconds":time.process_time()-start,"wall_seconds":time.perf_counter()-wall},
             "reference":{"cpu_seconds":0.,"status":"FULL DATA NOT RUN; PREFIX GATE SEPARATE"}}
    start = time.process_time()
    train_symbols,test_symbols = ev.new_symbols(model,episodes),ev.new_symbols(model,heldout)
    costs["equivalence_and_encoding_cpu"] = time.process_time()-start
    run.save(folder/f"{target}_tree.json",model.export_tree(),exclusive=True)
    run.save(folder/f"{target}_backend.json",{
        "backend":BACKEND,"full_reference_fit":False,"prefix_gate":"../../prefix_gate.json",
        "feature_storage":"HistoryColumns", "validity_storage":"ValidColumns",
        "logical_shape":list(model._feature_matrix.shape),
        "full_N_by_F_array_materialized":False,"all_data_derived_features_and_thresholds":True,
        "training_transitions":model.report.n_transitions,
        "max_observed_history":model.report.max_observed_history,
        "costs":costs,"work":model.work},exclusive=True)
    world = SymbolWorld(actions)
    start = time.process_time()
    for symbols,(_,controls) in zip(train_symbols,episodes,strict=True):
        world.add_episode(symbols,controls)
    world.freeze()
    costs["world_and_quotient_cpu"] = time.process_time()-start
    run.save(folder/f"{target}_connection_audit.json",world.connection_audit(),exclusive=True)
    assert not {"q","discount","goal","reward","max_history_depth"} & vars(model).keys()
    assert not {"q","discount","goal","reward","max_history_depth"} & vars(world).keys()
    return model,world,train_symbols,test_symbols,costs


def evaluate_one(case, output):
    verify_gate(output)
    folder = output/"cases"/case["id"]
    folder.mkdir(parents=True,exist_ok=False)
    wall,cpu = time.perf_counter(),time.process_time()
    result = {"case":case,"conditions":{},"status":"RUNNING","backend":BACKEND}
    def progress(stage):
        run.save(folder/"progress.json",{"stage":stage,"resources":run.resources(),"wall_seconds":time.perf_counter()-wall})
        run.log(output,event="raw_stage",case=case["id"],stage=stage)
    try:
        data,manifest,train,heldout = load_case(case,output)
        config = run.read(output/"config.json")
        result["conditions"] = visual.evaluate(case,train,heldout,data/"hidden_evaluator_only.json",
            config,ROOT,folder,fit_optimized,run.save,progress)
        for condition, value in result["conditions"].items():
            value["backend"] = "unchanged_old" if condition == "OLD" else BACKEND
        result["prefix_validation"] = run.read(output/"gates"/case["id"]/"result.json")
        result["status"] = "COMPLETE"
        for filename,key in (("train.npz","train"),("heldout.npz","heldout")):
            assert run.sha(data/filename) == manifest[key]["sha256"]
    except MemoryError:
        result.update(status="RESOURCE UNAVAILABLE - NOT COMPLETED",exception=traceback.format_exc())
    except Exception:
        result.update(status="EXECUTION ERROR - NOT A CAPABILITY RESULT",exception=traceback.format_exc())
    finally:
        run.frozen_check(output)
        result.update(wall_seconds=time.perf_counter()-wall,cpu_seconds=time.process_time()-cpu,resources=run.resources())
        run.save(folder/"result.json",result,exclusive=True)
        progress(result["status"])
    return result["status"]


def run_isolated(case, output):
    verify_gate(output)
    command = [sys.executable,"-u",str(Path(__file__).resolve()),"evaluate-one","--output",str(output),"--case",case["id"]]
    started = datetime.now(timezone.utc).isoformat()
    run.save(output/f"execution_command_{case['id']}.json",{
        "started":started,"command":command,"backend":BACKEND},exclusive=True)
    run.log(output,event="raw_child_started",case=case["id"],command=command)
    child = subprocess.run(command,check=False)
    path = output/"cases"/case["id"]/"result.json"
    if not path.exists():
        path.parent.mkdir(parents=True,exist_ok=True)
        run.save(path,{"case":case,"conditions":{},"backend":BACKEND,"status":"RUN NOT COMPLETED",
                       "reason":"Child process exited without a result; not a task failure","returncode":child.returncode},exclusive=True)
    run.save(path.parent/"process_release.json",{
        "child_started":started,"child_ended":datetime.now(timezone.utc).isoformat(),
        "returncode":child.returncode,"command":command,
        "all_child_process_arrays_released_by_process_exit":True,
        "parent_resources_after_exit":run.resources()},exclusive=True)
    run.log(output,event="raw_child_exited",case=case["id"],returncode=child.returncode,arrays_released=True)
    if child.returncode and run.read(path)["status"].startswith("EXECUTION ERROR"):
        raise RuntimeError(f"Execution error in {case['id']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode",choices=("initialize","gates","gate-one","case","evaluate-one","summarize"))
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--shared-input",type=Path)
    parser.add_argument("--case")
    args = parser.parse_args()
    output = args.output.resolve()
    if args.mode == "initialize":
        initialize(output,args.shared_input.resolve())
        return
    run.frozen_check(output)
    if args.mode == "gates":
        gates(output)
    elif args.mode == "summarize":
        ci.finalize(output)
        summary = run.summarize(output,run.read(output/"config.json"))
        summary["backend"] = BACKEND
        summary["prefix_validation_cpu_seconds"] = sum(run.read(p)["cpu_seconds"]
            for p in (output/"gates").glob("*/result.json"))
        summary["full_reference_fit"] = False
        summary["algorithm_change"] = False
        run.save(output/"metrics.json",summary)
        for filename in ("world_model_comparison.csv","compute_scaling.csv","complete_system.csv"):
            path = output/filename
            with path.open(encoding="utf-8",newline="") as f:
                rows = list(csv.DictReader(f))
            for row in rows:
                row["backend"] = "unchanged_old" if row["condition"] == "OLD" else BACKEND
            run.write_csv(path,rows)
    else:
        case = next(c for c in run.read(output/"config.json")["cases"] if c["id"] == args.case)
        if args.mode == "gate-one":
            if not gate_one(case,output): sys.exit(1)
        elif args.mode == "evaluate-one":
            status = evaluate_one(case,output)
            if status.startswith("EXECUTION ERROR"): sys.exit(1)
        else:
            run_isolated(case,output)


if __name__ == "__main__":
    main()
