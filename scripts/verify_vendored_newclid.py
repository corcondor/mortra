"""Check vendored bytes and the actually imported Newclid distribution."""
from pathlib import Path
import argparse
import hashlib
import importlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from urllib.parse import urlparse
from urllib.request import url2pathname


ROOT = Path(__file__).resolve().parents[1]


def blob_sha1(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def snapshot_check(folder, manifest):
    expected = manifest["files"]
    actual = {p.relative_to(folder).as_posix() for p in folder.rglob("*")
              if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}
    if actual != set(expected):
        raise ValueError(f"snapshot files differ: missing={sorted(set(expected)-actual)}, "
                         f"extra={sorted(actual-set(expected))}")
    for name, entry in expected.items():
        path = folder / name
        if not path.resolve().is_relative_to(folder.resolve()) or path.is_symlink():
            raise ValueError(f"snapshot path escapes vendor directory: {name}")
        data = path.read_bytes()
        if len(data) != entry["bytes"] or blob_sha1(data) != entry["git_blob_sha1"]:
            raise ValueError(f"snapshot content differs: {name}")
    return len(expected)


def local_origin(info, folder):
    url = urlparse(info.get("url", ""))
    return (url.scheme == "file" and not url.netloc
            and Path(url2pathname(url.path)).resolve() == folder.resolve())


def package_check(package, folder, manifest):
    prefix = "src/newclid/"
    expected = {n[len(prefix):] for n in manifest["files"] if n.startswith(prefix)}
    actual = {p.relative_to(package).as_posix() for p in package.rglob("*")
              if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"}
    if actual != expected:
        raise ValueError(f"imported package files differ: missing={sorted(expected-actual)}, "
                         f"extra={sorted(actual-expected)}")
    normalized = []
    for name in sorted(expected):
        original = (folder / prefix / name).read_bytes()
        imported = (package / name).read_bytes()
        if imported != original:
            # Windows upstream installations may have CRLF; report this explicitly.
            if imported.replace(b"\r\n", b"\n") != original.replace(b"\r\n", b"\n"):
                raise ValueError(f"imported package content differs: {name}")
            normalized.append(name)
    return {"checked_files": len(expected), "line_ending_only_differences": normalized}


def audit(root=ROOT, require_local=True):
    folder = root / "vendor/newclid"
    manifest_path = root / "vendor/newclid.upstream.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    count = snapshot_check(folder, manifest)
    module = importlib.import_module("newclid")
    package = Path(module.__file__).resolve().parent
    distribution = importlib.metadata.distribution("newclid")
    info = json.loads(distribution.read_text("direct_url.json") or "{}")
    local = local_origin(info, folder)
    if require_local and not local:
        raise ValueError("Newclid was not installed from this checkout's vendor/newclid")
    expected_package = (folder / "src/newclid" if info.get("dir_info", {}).get("editable")
                        else Path(distribution.locate_file("newclid")))
    if package != expected_package.resolve():
        raise ValueError("Imported Newclid is shadowing the audited distribution")
    if distribution.version != manifest["version"]:
        raise ValueError("Newclid version differs from the pinned snapshot")
    return {"passed": True, "upstream_repository": manifest["repository"],
            "upstream_commit": manifest["commit"], "version": distribution.version,
            "snapshot_files_checked": count, "imported_package": str(package),
            "installed_from_this_checkout": local, "direct_url": info,
            "package": package_check(package, folder, manifest),
            "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "python": sys.version, "executable": sys.executable, "platform": platform.platform(),
            "repository": os.environ.get("GITHUB_REPOSITORY"),
            "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
            "sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
            "dependencies": sorted(f"{d.metadata['Name']}=={d.version}"
                                   for d in importlib.metadata.distributions())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--allow-upstream-install", action="store_true")
    args = parser.parse_args()
    result = audit(require_local=not args.allow_upstream_install)
    content = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    print(content)


if __name__ == "__main__":
    main()
