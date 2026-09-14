"""Independent contract/source/proof replay plus summary and visibility audit."""
from pathlib import Path
import argparse
import json
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.replay_geometry_contracts import replay as replay_contracts
from math_os_prototype.geometry_contraction import replay_summary, source_interfaces
from math_os_prototype.theory_geometry_acquisition import independent_replay


def replay(folder):
    started = time.perf_counter()
    result = replay_contracts(folder)
    def read(name):
        return json.loads((folder/name).read_text(encoding="utf-8"))
    archive, learned, comparisons = read("frozen-library.json"), read("acquisition.json"), read("comparisons.json")
    by_id = {h["id"]: h for h in archive}
    summaries = []
    for h in archive:
        ok, cost = replay_summary(h, h["summary"])
        boundary, sources = source_interfaces(h, learned["corpus"])
        ok = ok and sources == h["interface_sources"] and boundary == sorted(h["summary"]["interface"]["boundary_outputs"])
        summaries.append({"id": h["summary"]["id"], "passed": ok, "cost": cost})
        if not ok:
            result["errors"].append("summary/source interface mismatch: "+h["id"])
    visibility_checks = 0
    for label in ("summarized", "hiding_only", "ablation"):
        for row in comparisons[label]:
            for event in row["events"]:
                if event["event"] != "apply":
                    continue
                action = event["action"]
                if action["family"] not in by_id:
                    continue
                h = by_id[action["family"]]
                interface = h["summary"]["interface"]
                if len(action["outputs"]) != len(interface["public_outputs"]):
                    result["errors"].append("private point exposed by summarized apply")
                if interface["private_locals"]:
                    d = action.get("contraction", {})
                    if (d.get("summary_id") != h["summary"]["id"] or d.get("private_locals") != interface["private_locals"]
                            or set(d.get("local_mapping", {})) != set(interface["public_outputs"])):
                        result["errors"].append("invalid contracted action interface")
                visibility_checks += 1
    regression = [independent_replay(r) for r in read("regression.json")]
    if any(r["checked"] and not r["passed"] for r in regression):
        result["errors"].append("regression false proof")
    result.update(passed=not result["errors"], summaries=summaries, visibility_checks=visibility_checks,
                  regression_replays=regression, total_seconds=time.perf_counter()-started,
                  scientific_gate_passed=read("verification.json")["scientific_gate_passed"])
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-scientific-pass", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("refuse to replace previous replay")
    result = replay(args.run)
    args.output.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] and (not args.require_scientific_pass or result["scientific_gate_passed"]) else 1)
