import gzip
import json
import shutil

import pytest

from experiments.task_agent.pretraining_reproduction import (
    SEEDS, exact_compare, read, table, unpack,
)


@pytest.fixture(scope="module")
def bundle(tmp_path_factory):
    result, checked = unpack(tmp_path_factory.mktemp("archive") / "unpacked")
    assert len(checked) == 218
    return result


def all_rows(bundle):
    return [row for seed in SEEDS for row in read(bundle / "results" / str(seed) / "episodes.json")]


def test_reference_keys_are_exact_unique_864(bundle):
    assert len(table(all_rows(bundle))) == 864


def test_duplicate_and_missing_cannot_cancel(bundle):
    rows = all_rows(bundle)
    rows[-1] = rows[0]
    with pytest.raises(AssertionError):
        table(rows)


def test_wrong_seed_detected(bundle):
    rows = all_rows(bundle)
    rows[0]["seed"] += 100
    with pytest.raises(AssertionError):
        table(rows)


def test_all_original_snapshots_and_traces_match_themselves(bundle, tmp_path):
    result = exact_compare(bundle, bundle, tmp_path)
    assert result["passed"]
    assert result["snapshots"] == 72
    assert result["trace_rows"] == {"training_trace.jsonl.gz": 49152, "evaluation_trace.jsonl.gz": 65489}


def test_no_rounding_away_trace_difference(bundle, tmp_path):
    import math
    copy = tmp_path / "copy"
    shutil.copytree(bundle / "results", copy / "results")
    path = copy / "results" / str(SEEDS[0]) / "training_trace.jsonl.gz"
    with gzip.open(path, "rt") as stream:
        rows = [json.loads(line) for line in stream]
    rows[0]["field_residual"] = math.nextafter(float(rows[0]["field_residual"]), math.inf)
    with gzip.open(path, "wt") as stream:
        for row in rows:
            stream.write(json.dumps(row) + "\n")
    result = exact_compare(bundle, copy, tmp_path / "audit")
    assert not result["passed"]
    assert result["difference_counts"] == {"trace": 1}
