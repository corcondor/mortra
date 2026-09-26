"""Read-only verification of completed Actions artifacts; never invokes a policy."""
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

from experiments.task_agent.pretraining_reproduction import exact_compare

ROOT = Path(__file__).resolve().parent
EVIDENCE = Path(sys.argv[1]).resolve()
REPRO = EVIDENCE / "reproduction"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(name, value):
    (ROOT / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


with gzip.open(REPRO / "canonical/all_differences.jsonl.gz", "rt") as stream:
    differences = [json.loads(line) for line in stream]
with gzip.open(REPRO / "standalone/all_differences.jsonl.gz", "rt") as stream:
    independent = [json.loads(line) for line in stream]
assert differences == independent
maxima = defaultdict(float)
field_counts, methods = Counter(), Counter()
for row in differences:
    assert row["kind"] == "trace" and row["file"] == "training_trace.jsonl.gz"
    methods[row["actual"]["method"]] += 1
    assert set(row["fields"]) <= {"generic_scores", "field_residual"}
    for field in row["fields"]:
        field_counts[field] += 1
        a, b = row["reference"][field], row["actual"][field]
        pairs = [(a[key], b[key]) for key in a] if isinstance(a, dict) else [(a, b)]
        maxima[field] = max(maxima[field], *(abs(x - y) for x, y in pairs))
between = exact_compare(REPRO / "standalone", REPRO / "canonical", ROOT / "canonical_vs_standalone")
assert between["passed"]
tests = {}
for label, path in {
    "canonical_existing_and_new_harness": EVIDENCE / "canonical-tests.xml",
    "unchanged_bundle_standalone": REPRO / "standalone/results/tests.xml",
    "unchanged_bundle_canonical": REPRO / "canonical/results/tests.xml",
}.items():
    suites = list(ET.parse(path).iter("testsuite"))
    tests[label] = {k: sum(int(s.attrib.get(k, 0)) for s in suites)
                    for k in ("tests", "failures", "errors", "skipped")}
    assert not tests[label]["failures"] and not tests[label]["errors"]
reproductions = {m: load(REPRO / m / "results/reproduction.json") for m in ("standalone", "canonical")}
assert all(r["passed"] and r["snapshots_compared"] == 8 and r["episodes_compared"] == 96
           for r in reproductions.values())
replay = {m: load(REPRO / m / "results/postrun_audit.json") for m in reproductions}
assert all(r["passed"] and r["episodes_replayed"] == 864 for r in replay.values())
artifact = ROOT / "original_actions_artifact.zip"
artifact_sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
assert artifact_sha == "c75f5e2fef4fe35380682289a9e817db70731c6c00cafb1007d2379d82603613"
save("verification.json", {
    "run_id": 36270643269, "run_commit": "dd845c64b3ecfd82a17012b7ca4dabe315597e23",
    "fresh_started": False, "fresh_worlds_evaluated": 0,
    "disposition": "STOPPED_AT_EXACT_NUMERICAL_GATE; NOT A POLICY FAILURE",
    "tests": tests, "rows_per_route": 864, "snapshot_matches_per_route": 72,
    "structural512_matches_per_route": 8, "historical_generic_matches_per_route": 96,
    "all_training_actions_and_observations_equal": True,
    "all_evaluation_actions_and_observations_equal": True,
    "training_steps_per_route": 49152, "evaluation_steps_per_route": 65489,
    "different_trace_rows_per_route": len(differences),
    "different_fields_per_route": dict(field_counts), "max_absolute_difference": dict(maxima),
    "different_rows_by_method": dict(methods),
    "both_routes_have_identical_differences_against_original": True,
    "canonical_vs_standalone_all_values_exact": between["passed"],
    "runtime": load(REPRO / "source_snapshot.json"),
    "original_runtime": {k: load(REPRO / "original/mortra_pretraining_smoke/manifest_before.json")[k]
                         for k in ("python", "numpy", "scipy", "platform")},
    "original_artifact": {"id": 10914934920, "sha256": artifact_sha, "bytes": artifact.stat().st_size},
    "roundoff_cause": "unisolated; package versions match, platform/compiler builds differ; no tolerance or policy changed",
})
for name in ("gate.json", "source_snapshot.json", "attempts.json", "original_integrity.json"):
    save(name, load(REPRO / name))
print(json.dumps(load(ROOT / "verification.json"), indent=2))
