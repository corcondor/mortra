"""Verify immutable historical inputs; never run a revised player."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(__file__).parent
SEEDS = list(range(79020000, 79020008))
RUN = 36273640831
COMMIT = "5f8b36744a29327928c87d6db888f2f045dbea79"
FILES = ["game.json", "learner.json", "metrics.json", "audit.json", "training.jsonl.gz", "actions.jsonl.gz"]
FROZEN = ["scripts/evaluate_autonomous_game_design_loop.py"] + [
    f"experiments/task_agent/{name}.py" for name in
    ("pretraining", "virtual_frontier", "core", "exploration", "online", "online_eval")
] + ["experiments/self_design_v2_integration/adapter.py"]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def source_check():
    result = {}
    for name in FROZEN:
        expected = subprocess.check_output(["git", "show", f"{COMMIT}:{name}"], cwd=ROOT)
        actual = (ROOT / name).read_bytes()
        assert actual.replace(b"\r\n", b"\n") == expected.replace(b"\r\n", b"\n"), name
        result[name] = {"actual_sha256": sha(actual), "git_blob_sha256": sha(expected), "equal_normalized_lf": True}
    return result


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected:
            redirected.remove_header("Authorization")
        return redirected


def download(artifact, path):
    if path.exists():
        assert sha(path.read_bytes()) == artifact["digest"].split(":")[1]
        return
    token = os.environ.get("GH_TOKEN") or subprocess.check_output(["gh", "auth", "token"], text=True).strip()
    req = urllib.request.Request(artifact["archive_download_url"], headers={
        "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "MORTRA-input-audit"})
    with urllib.request.build_opener(SafeRedirect()).open(req) as response:
        data = response.read()
    assert sha(data) == artifact["digest"].split(":")[1], "Original artifact digest mismatch"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    attached = PACKAGE / "reference/mortra_v2_followup_audit.zip"
    assert sha(attached.read_bytes()) == "9c100dacb9015747966068743fc3fa018cb097212b8170931b50b222779d32b2"
    with zipfile.ZipFile(attached) as bundle:
        for name in bundle.namelist():
            if not name.endswith("/"):
                assert (PACKAGE / "reference" / name).read_bytes() == bundle.read(name), name
    write(args.output / "source_audit.json", source_check())
    artifacts = json.loads(subprocess.check_output(["git", "show",
        "724220d29f02b79633b0ba43adf57242ad922cb9:reports/self_design_v2_integration_36273640831/artifacts.json"], cwd=ROOT))["artifacts"]
    registry = {}
    for seed in SEEDS:
        artifact = next(a for a in artifacts if a["name"] == f"v2-full-{seed}-virtual_frontier-{RUN}")
        assert artifact["workflow_run"]["head_sha"] == COMMIT
        archive = args.output / "original_artifacts" / f"{artifact['id']}.zip"
        download(artifact, archive)
        base = f"v2_full_{seed}_virtual_frontier/targeted/evaluations/evaluation_000/"
        hashes = {}
        with zipfile.ZipFile(archive) as z:
            for name in FILES:
                data = z.read(base + name)
                path = args.output / "inputs" / str(seed) / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                hashes[name] = sha(data)
            snapshot = json.loads(z.read(f"v2_full_{seed}_virtual_frontier/source_snapshot.json"))
            assert snapshot["head"] == COMMIT
        registry[str(seed)] = {"artifact_id": artifact["id"], "artifact_sha256": sha(archive.read_bytes()), "files": hashes}
        print(f"verified original input {seed}", flush=True)
    ref = PACKAGE / "reference/mortra_v2_followup_audit"
    audit_path = args.output / "stage0_reference_output.txt"
    audit = subprocess.run([sys.executable, str(ref / "audit_saved_failure.py"),
        str(args.output / "original_artifacts/10917048485.zip"), str(audit_path)], capture_output=True, text=True)
    (args.output / "stage0_stdout.log").write_text(audit.stdout, encoding="utf-8")
    (args.output / "stage0_stderr.log").write_text(audit.stderr, encoding="utf-8")
    assert audit.returncode == 0, audit.stderr
    actual = json.loads(audit.stdout)
    expected = json.loads((ref / "failure_audit.json").read_text(encoding="utf-8"))
    # The supplied script appends a literal backslash-n to its file output.
    # Preserve that file unchanged and parse its valid JSON stdout instead.
    differences = {k: {"expected": expected.get(k), "actual": actual.get(k)}
                   for k in expected.keys() | actual.keys() if expected.get(k) != actual.get(k)}
    write(args.output / "stage0_comparison.json", {"differences": differences,
        "exact_values_equal": not differences, "parsed_stdout": True,
        "raw_output_trailing_bytes_hex": audit_path.read_bytes()[-8:].hex()})
    assert not differences, differences
    write(args.output / "stage0_result.json", actual)
    write(args.output / "input_registry.json", registry)
    print("Stage 0: all supplied audit values exactly matched", flush=True)


if __name__ == "__main__":
    main()
