"""Preserve downloaded results and render readable trace diagrams, no policy run."""
import argparse
import gzip
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments.v2_online_feedback.prepare import sha, write
from experiments.v2_online_feedback.adapter import ARMS


def render(root, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    output.mkdir()
    for seed in range(79020000, 79020008):
        world = root / str(seed)
        game = json.loads((world / "game.json").read_text())
        fig, axes = plt.subplots(1, 3, figsize=(12, 5.4))
        for axis, arm, title in zip(axes, ARMS, ("A: frozen", "B: record + replan", "C: exploration + record + replan")):
            with gzip.open(world / arm / "checkpoint_5000/evaluation_trials.jsonl.gz", "rt") as stream:
                trial = json.loads(next(stream))
            for x, y in game["walls"]:
                axis.add_patch(Rectangle((x-.5,y-.5),1,1,color="#444b53"))
            for x, y in game["hazards"]:
                axis.scatter(x,y,marker="x",c="#c63853",s=50)
            for key, label in (("key_pos","K"),("door_pos","D"),("switch_pos","S"),("gate_pos","G"),("block_pos","B"),("teleport_a","P"),("teleport_b","P")):
                if game[key] is not None:
                    axis.text(*game[key],label,ha="center",va="center",color="#986a13",fontsize=9)
            states = trial["states"]
            axis.plot([s[0] for s in states],[s[1] for s in states],color="#218574",lw=2)
            axis.scatter(*game["start_pos"],marker="s",s=55,color="#357aad",label="start")
            axis.scatter(*game["goal_pos"],marker="*",s=125,color="#e0a420",label="goal")
            axis.scatter(states[-1][0],states[-1][1],s=20,color="#111111",label="end")
            axis.set(xlim=(-.5,game["width"]-.5),ylim=(game["height"]-.5,-.5),aspect="equal")
            axis.set_xticks([]); axis.set_yticks([])
            axis.set_title(f"{title}\ntrial 0: {len(trial['actions'])} actions, success={trial['success']}",fontsize=9,pad=10)
        axes[0].legend(fontsize=7,loc="lower left")
        fig.suptitle(f"Run 36281122365 | seed {seed} | frozen evaluation after +5000 actions",fontsize=11,y=.98)
        fig.text(.5,.91,"Position projection of saved state/action traces; not captured gameplay frames",ha="center",fontsize=9)
        fig.tight_layout(rect=(0,0,1,.84))
        fig.savefig(output/f"trial0_{seed}.png",dpi=140)
        plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence",type=Path,required=True)
    args = parser.parse_args()
    out = Path(__file__).parent
    evidence = args.evidence / "actions_36281122365"
    for seed in range(79020000,79020008):
        shutil.copytree(evidence/"worlds"/f"feedback-{seed}-36281122365"/f"feedback_{seed}",out/"worlds"/str(seed))
    shutil.copytree(evidence/"summary",out/"frozen_summary")
    gates = evidence/"gates"
    shutil.copytree(gates/"reports/reproduction_gate",out/"gates/reproduction_gate")
    registered = gates/"reports/registered_inputs"
    shutil.copytree(registered/"inputs",out/"registered_inputs")
    for name in ("input_registry.json","source_audit.json","stage0_comparison.json","stage0_result.json","stage0_reference_output.txt","stage0_stdout.log","stage0_stderr.log"):
        shutil.copy2(registered/name,out/"gates"/name)
    shutil.copy2(gates/"feedback-tests.xml",out/"gates/feedback-tests.xml")
    shutil.copytree(args.evidence/"bundle_crosscheck_attempt2",out/"bundle_crosscheck")
    shutil.copy2(args.evidence/"loop-wiring-tests.xml",out/"gates/loop-wiring-tests.xml")
    for name in ("development-tests-1.xml","all-tests-2.xml","development-tests-3.xml"):
        shutil.copy2(args.evidence/name,out/"gates"/name)
    render(out/"worlds",out/"display")
    run = json.loads(subprocess.check_output(["gh","run","view","36281122365","--repo","corcondor/mortra","--json","databaseId,status,conclusion,headSha,url,jobs,createdAt,updatedAt"],text=True))
    assert run["conclusion"] == "success" and run["headSha"] == "78ef2c84b0bbee80396810a919eb4aae7082d031"
    write(out/"github_run.json",run)
    artifacts = json.loads(subprocess.check_output(["gh","api","repos/corcondor/mortra/actions/runs/36281122365/artifacts?per_page=100"],text=True))
    write(out/"artifacts.json",artifacts)
    originals = json.loads((out/"gates/stage0_reference_output.txt").read_text())
    assert originals == json.loads((out/"gates/stage0_result.json").read_text())
    write(out/"documentation_correction.json",{
        "correction":"The frozen protocol/comment incorrectly anticipated a literal backslash-n in the supplied audit output. The actual supplied script writes valid JSON with a real newline. The unchanged raw file parses and equals the stdout result. No algorithm, data or comparison changed.",
        "valid_original_json_verified":True,
        "postprocess_setup":"Crosscheck attempt 1 assumed an artifact without the preserved feedback_<seed> directory; attempt 2 uses the actual artifact layout. No policy rerun."})
    headline = json.loads((out/"frozen_summary/headline.json").read_text())
    write(out/"resource_totals.json",{
        "worker_cpu_seconds_sum":sum(r["total_cpu_seconds"] for r in headline["resources"]),
        "worker_wall_seconds_sum_not_elapsed":sum(r["total_wall_seconds"] for r in headline["resources"]),
        "peak_worker_memory_bytes":max(r["peak_process_memory_bytes"] for r in headline["resources"]),
        "additional_training_actions":120000,"frozen_evaluation_trials":3600,
        "frozen_evaluation_actions":105600,
        "source_commit":"78ef2c84b0bbee80396810a919eb4aae7082d031"})
    write(out/"preserved_file_hashes.json",{p.relative_to(out).as_posix():sha(p.read_bytes()) for p in out.rglob("*") if p.is_file()})
    print(json.dumps({"archived_to":str(out),"status":headline["status"]}))


if __name__=="__main__":
    main()
