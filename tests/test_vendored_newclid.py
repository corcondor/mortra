"""Vendoring integrity tests; these are not autonomous mathematics results."""
from pathlib import Path
import json

import pytest

from scripts.verify_vendored_newclid import (
    ROOT, blob_sha1, local_origin, package_check, snapshot_check,
)


def test_complete_upstream_snapshot():
    manifest = json.loads((ROOT / "vendor/newclid.upstream.json").read_text())
    assert snapshot_check(ROOT / "vendor/newclid", manifest) == len(manifest["files"])
    assert "LICENSE" in manifest["files"] and "NOTICE.md" in manifest["files"]


@pytest.fixture
def snapshot(tmp_path):
    folder = tmp_path / "vendor"
    folder.mkdir()
    data = b"original\n"
    (folder / "LICENSE").write_bytes(data)
    return folder, {"files": {"LICENSE": {"bytes": len(data), "git_blob_sha1": blob_sha1(data)}}}


@pytest.mark.parametrize("change", ["missing", "extra", "modified"])
def test_reject_changed_snapshot(snapshot, change):
    folder, manifest = snapshot
    if change == "missing":
        (folder / "LICENSE").unlink()
    elif change == "extra":
        (folder / "extra.py").write_text("x=1")
    else:
        (folder / "LICENSE").write_text("different")
    with pytest.raises(ValueError, match="snapshot"):
        snapshot_check(folder, manifest)


def test_local_origin_is_checkout_specific(tmp_path):
    assert local_origin({"url": tmp_path.as_uri()}, tmp_path)
    assert not local_origin({"url": (tmp_path / "other").as_uri()}, tmp_path)
    assert not local_origin({"url": "https://github.com/Newclid/Newclid"}, tmp_path)
    assert not local_origin({}, tmp_path)


def test_package_content_not_just_version_or_origin(tmp_path):
    vendor = tmp_path / "vendor"
    source = vendor / "src/newclid"
    source.mkdir(parents=True)
    package = tmp_path / "installed"
    package.mkdir()
    (source / "__init__.py").write_bytes(b"x=1\n")
    (package / "__init__.py").write_bytes(b"x=1\r\n")
    manifest = {"files": {"src/newclid/__init__.py": {}}}
    result = package_check(package, vendor, manifest)
    assert result["line_ending_only_differences"] == ["__init__.py"]
    (package / "__init__.py").write_bytes(b"x=2\n")
    with pytest.raises(ValueError, match="content differs"):
        package_check(package, vendor, manifest)


def test_package_extra_python_is_not_silently_accepted(tmp_path):
    (tmp_path / "extra.py").write_text("x=1")
    with pytest.raises(ValueError, match="files differ"):
        package_check(tmp_path, Path("unused"), {"files": {}})
