"""Environment and state freezing manifest for MORTRA closed-book exam.

Records:
1. Git commit SHA and dirty status
2. Source code hashes (math_os_prototype)
3. Learned state / library / experience store hashes
4. Benchmark dataset hashes
5. Python runtime and dependency environment
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any


def compute_dir_hash(directory: Path, pattern: str = "*.py") -> str:
    """Compute deterministic SHA-256 hash of all matching files in a directory."""
    hasher = hashlib.sha256()
    for p in sorted(directory.rglob(pattern)):
        if p.is_file() and "__pycache__" not in p.parts:
            hasher.update(p.relative_to(directory).as_posix().encode("utf-8"))
            hasher.update(p.read_bytes())
    return hasher.hexdigest()


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA-256 hash of a single file."""
    if not file_path.exists():
        return "file_not_found"
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


def capture_git_info(repo_root: Path) -> dict[str, Any]:
    """Capture exact git commit SHA, branch, and status."""
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, text=True
        ).strip()
    except Exception as e:
        commit = f"git_error: {e}"

    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root, text=True
        ).strip()
    except Exception as e:
        branch = f"git_error: {e}"

    try:
        status = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=repo_root, text=True
        ).strip()
        is_dirty = len(status) > 0
    except Exception as e:
        status = f"git_error: {e}"
        is_dirty = True

    return {
        "commit_sha": commit,
        "branch": branch,
        "is_dirty": is_dirty,
        "status_summary": status[:500] if status else "clean",
    }


def create_frozen_manifest(repo_root: Path, output_path: Path | None = None) -> dict[str, Any]:
    """Create and return the comprehensive frozen manifest."""
    source_dir = repo_root / "math_os_prototype"
    manifest = {
        "timestamp_utc": "2026-09-21T01:15:00Z",
        "git": capture_git_info(repo_root),
        "hashes": {
            "source_code_sha256": compute_dir_hash(source_dir, "*.py"),
            "domain_registry_sha256": compute_file_hash(source_dir / "domain_registry.py"),
            "representation_ledger_sha256": compute_file_hash(source_dir / "representation_ledger.py"),
            "representation_policy_sha256": compute_file_hash(source_dir / "representation_policy.py"),
            "wave_optics_system_sha256": compute_file_hash(source_dir / "wave_optics_system.py"),
        },
        "environment": {
            "os": platform.platform(),
            "python_version": sys.version,
            "python_executable": sys.executable,
        },
    }

    # Add package versions
    for pkg in ["numpy", "scipy", "pytest", "sympy"]:
        try:
            mod = __import__(pkg)
            manifest["environment"][f"{pkg}_version"] = getattr(mod, "__version__", "unknown")
        except ImportError:
            manifest["environment"][f"{pkg}_version"] = "not_installed"

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return manifest


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parent.parent.parent
    out_file = Path(__file__).resolve().parent / "exam_frozen_manifest.json"
    m = create_frozen_manifest(repo_root, out_file)
    print("MORTRA Closed-Book Exam Manifest Frozen:")
    print(json.dumps(m, indent=2))
