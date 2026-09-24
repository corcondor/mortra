"""Provenance, data packaging and artifact bookkeeping. No research algorithms."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT/"configs/integrated-predictive-source-sha.json"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_new(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("x",encoding="utf-8") as stream:
        json.dump(value,stream,indent=2,allow_nan=False)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(["git",*args],cwd=ROOT,text=True).strip()


def package_inputs():
    # Deliberately omit historical success metrics and hidden-state labels.
    prior = ROOT/"reports/adaptive_refinement_20260923-222106"
    target = ROOT/"data/integrated-predictive-experience-20260924"
    provenance = []
    paths = [prior/f"finite_{i:03d}.json" for i in range(100)]
    paths += [prior/f"partial_{i:03d}.json" for i in range(20)]
    paths += [prior/f"game_{seed}.json" for seed in (201,302,403,504,605)]
    for source in paths:
        obj = read(source)
        payload = {"stream":obj["stream"]}
        if "spec" in obj: payload["spec"] = obj["spec"]
        if "seed" in obj: payload["seed"] = obj["seed"]
        dest = target/source.name
        write_new(dest,payload)
        provenance.append({"original":str(source.relative_to(ROOT)).replace("\\","/"),
                           "original_sha256":digest(source),"input":source.name,"input_sha256":digest(dest)})
    write_new(target/"provenance.json",provenance)
    frozen = ROOT/"reports/integrated_predictive_world_model_20260924-160455"
    write_new(MANIFEST,read(frozen/"source_sha.json"))


def initialize(output):
    output.mkdir(parents=True,exist_ok=False)
    sources = read(MANIFEST)
    inputs = ROOT/"data/integrated-predictive-experience-20260924"
    for record in read(inputs/"provenance.json"):
        assert digest(inputs/record["input"]) == record["input_sha256"], "Packaged experience changed"
    for name,expected in sources.items():
        assert digest(ROOT/name)==expected, f"Frozen algorithm changed: {name}"
        dest = output/"frozen_source"/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/name,dest)
    write_new(output/"source_sha.json",sources)
    write_new(output/"old_source_sha.json",{k:v for k,v in sources.items() if k.startswith("scripts/")})
    write_new(output/"new_source_sha.json",{k:v for k,v in sources.items() if k.startswith("mortra_predictive_perception/")})
    write_new(output/"source_snapshot.json",{
        "experiment_id":output.name,"timestamp":datetime.now(timezone.utc).isoformat(),
        "branch":os.environ.get("GITHUB_REF_NAME") or git("branch","--show-current"),
        "HEAD":git("rev-parse","HEAD"),"git_status_short":git("status","--short"),
        "run_id":os.environ.get("GITHUB_RUN_ID"),"run_attempt":os.environ.get("GITHUB_RUN_ATTEMPT"),
        "algorithm_freeze":"20260924-160455","source_sha256":sources,
        "execution_location":"GitHub Actions" if os.environ.get("GITHUB_ACTIONS") else "local",
        "platform_interruption":"RUN NOT COMPLETED, never a mathematical FAIL"})


def finalize(output):
    config = read(output/"config.json")
    for case in config["cases"]:
        directory = output/"cases"/case["id"]
        if (directory/"result.json").exists(): continue
        write_new(directory/"result.json",{"case":case,"conditions":{},"status":"RUN NOT COMPLETED",
            "reason":"No completed result artifact. See Actions logs and progress.json; not a capability failure."})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode",choices=("package","initialize","finalize"))
    parser.add_argument("--output",type=Path)
    args = parser.parse_args()
    if args.mode=="package": package_inputs()
    elif args.mode=="initialize": initialize(args.output)
    else: finalize(args.output)


if __name__=="__main__": main()
