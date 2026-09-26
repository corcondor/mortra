"""Read-only exact source and stored-result gates."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
V2 = "156abc04d3ae77f1ac42d151f5d60830585f6ae7"
TASK = "dd845c64b3ecfd82a17012b7ca4dabe315597e23"
FILES = ("game_initial.json", "game_final.json", "evolution_history.json", "self_play_metrics.json")


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def source_audit():
    references = {"scripts/evaluate_autonomous_game_design_loop.py": V2,
                  "tests/test_self_game_design_v2.py": V2,
                  "requirements-game-tests.txt": V2, "requirements-game-experiments.txt": V2}
    references.update({p.relative_to(ROOT).as_posix(): TASK
                       for p in (ROOT / "experiments/task_agent").glob("*.py")})
    rows = []
    for name, commit in sorted(references.items()):
        original = subprocess.check_output(["git", "show", f"{commit}:{name}"], cwd=ROOT)
        current = (ROOT / name).read_bytes()
        rows.append({"file": name, "commit": commit, "sha256": hashlib.sha256(current).hexdigest(),
                     "reference_sha256": hashlib.sha256(original).hexdigest(),
                     "identical_lf": current.replace(b"\r\n", b"\n") == original.replace(b"\r\n", b"\n")})
    return rows


def differences(a, b, path=""):
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            if key not in a or key not in b:
                yield {"path": path + "/" + key, "reference": a.get(key), "actual": b.get(key), "kind": "key"}
            else:
                yield from differences(a[key], b[key], path + "/" + key)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            yield {"path": path, "reference": len(a), "actual": len(b), "kind": "length"}
        for i, (x, y) in enumerate(zip(a, b)):
            yield from differences(x, y, f"{path}/{i}")
    elif a != b or type(a) is not type(b):
        yield {"path": path, "reference": a, "actual": b,
               "kind": "float" if type(a) is float and type(b) is float else "value"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--actual", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    sources = source_audit()
    all_diffs = []
    file_results = {}
    reference = ROOT / "reports/self_game_design_v2"
    for name in FILES:
        saved = subprocess.check_output(["git", "show", f"{V2}:reports/self_game_design_v2/{name}"], cwd=ROOT)
        assert saved.replace(b"\r\n", b"\n") == (reference / name).read_bytes().replace(b"\r\n", b"\n"), name
        a, b = json.loads(saved), json.loads((args.actual / name).read_text(encoding="utf-8"))
        diff = list(differences(a, b, name))
        all_diffs.extend(diff)
        file_results[name] = {"exact_json_match": not diff, "differences": len(diff)}
    structural_diffs = [d for d in all_diffs if d["kind"] != "float"]
    summary = {"gate_passed": not all_diffs and all(s["identical_lf"] for s in sources),
               "files": file_results, "difference_count": len(all_diffs),
               "float_only": bool(all_diffs) and not structural_diffs,
               "non_float_difference_count": len(structural_diffs),
               "comparison": "every JSON value, including both final games, all accept/reject/critique sequences, candidate metrics and trial-0 replays",
               "python": sys.version, "platform": platform.platform(),
               "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()}
    write(args.output / "sources.json", sources)
    write(args.output / "differences.json", all_diffs)
    write(args.output / "summary.json", summary)
    print(json.dumps(summary, indent=2))
    if not summary["gate_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
