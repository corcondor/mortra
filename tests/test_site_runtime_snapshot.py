"""The site refresh retains the previously deployed math runtime unchanged."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = json.loads(
    (ROOT / "reports/self_game_design_v2/production_runtime_snapshot.json").read_text()
)


def test_recovered_modules_match_production_bytes():
    for path, digest in SNAPSHOT["files"].items():
        assert hashlib.sha1((ROOT / path).read_bytes()).hexdigest() == digest, path


def test_api_entrypoint_matches_previous_production():
    data = (ROOT / SNAPSHOT["entrypoint"]).read_bytes()
    # This existing Git-tracked entrypoint is checked out with platform line endings.
    normalized = data.replace(b"\r\n", b"\n")
    assert hashlib.sha1(normalized).hexdigest() == SNAPSHOT["entrypoint_lf_sha1"]
