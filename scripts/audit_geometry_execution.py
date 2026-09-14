"""Summarize existing traces only; does not acquire definitions or solve tasks."""
from pathlib import Path
import argparse
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from math_os_prototype.geometry_execution_audit import aggregate_geometry_events
from worker.backend.typed_geometry_stalk import DEFAULT_POINT_FAMILIES


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    log = args.run/"events.jsonl"
    summary = aggregate_geometry_events(log)
    sha = hashlib.sha256()
    with log.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b""):
            sha.update(chunk)
    summary["source_event_sha256"] = sha.hexdigest()
    summary["analysis_only_not_new_math_execution"] = True
    declarations = {f.name: {"kind": "primitive", "arity": f.input_arity,
        "symmetry": f.symmetry} for f in DEFAULT_POINT_FAMILIES}
    library = args.run/"library-provenance.json"
    if library.exists():
        definitions = json.loads(library.read_text(encoding="utf-8"))["definitions"]
    else:
        definitions = []
        for file in sorted(args.run.glob("*-archive.json")):
            definitions.extend(json.loads(file.read_text(encoding="utf-8")))
    for h in definitions:
        cert = h["exact_certificate"]
        declarations[h["id"]] = {"kind": "acquired", "arity": len(h["parameters"]),
            "body": h["body"], "parents": h["parents"], "generation": h["generation"],
            "effect_predicates": sorted({p["predicate"] for p in cert["guaranteed_relation"]}),
            "certificate": cert}
    summary["declarations"] = declarations
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output/"audit.json").write_text(json.dumps(summary, indent=2)+"\n", encoding="utf-8")
    text = ["# Geometry execution inventory", "", "This is an aggregation of saved events, not a new solve.",
        "Counts are event occurrences. A success is an executed construction with primitive replay, not a solved task.",
        "Failed predicate requests cannot be reconstructed when the original trace omitted them.", ""]
    for group, families in sorted(summary["families"].items()):
        text.extend(["## "+group, "", "| Operation | Kind | Proposed | Selected | Successful | Refused |", "|---|---|---:|---:|---:|---:|"])
        for name, declaration in declarations.items():
            row = families.get(name, {})
            refused = sum(v for k, v in row.items() if k.startswith("refused:"))
            text.append(f"| {name} | {declaration['kind']} | {row.get('proposed_in_pages', 0)} | {row.get('selected', 0)} | {row.get('successful_execution', 0)} | {refused} |")
        text.extend(["", "Consumed premises in successful constructions:",
            "```json", json.dumps(summary["consumed_premises_in_successful_calls"].get(group, {}), indent=2), "```", ""])
    (args.output/"inventory.md").write_text("\n".join(text).rstrip()+"\n", encoding="utf-8")
    print(json.dumps({"registered_operations": len(declarations), "groups": list(summary["families"]),
        "predicate_coverage": summary["predicate_request_coverage"], "output": str(args.output)}))


if __name__ == "__main__":
    main()
