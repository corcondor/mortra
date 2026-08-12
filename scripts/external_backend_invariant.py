"""Reject accidentally reintroduced external mathematical-AI runtimes."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = (
    ROOT / "app" / "api",
    ROOT / "lib",
    ROOT / "worker" / "src",
    ROOT / "worker" / "backend",
    ROOT / "supabase" / "functions",
    ROOT / ".github" / "workflows",
)
FORBIDDEN = (
    "api.deepseek.com",
    "deepseek_api_key",
    "deepseek-chat",
    "deepseek-reasoner",
    "alphageometry2",
    "mathos_ag2_dir",
    "ddar",
)
TEXT_SUFFIXES = {".ts", ".tsx", ".js", ".mjs", ".py", ".yml", ".yaml", ".json"}
REFERENCE_ONLY = {
    Path("worker/backend/geometry_natural_formalizer.py"),
}


violations: list[str] = []
for directory in SCAN_ROOTS:
    if not directory.exists():
        continue
    for path in directory.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if path.relative_to(ROOT) in REFERENCE_ONLY:
            continue
        source = path.read_text(encoding="utf-8", errors="replace").lower()
        for token in FORBIDDEN:
            if token in source:
                violations.append(f"{path.relative_to(ROOT)}: contains {token}")

if violations:
    print("Removed external backend invariant failed:")
    for violation in violations:
        print(f"- {violation}")
    sys.exit(1)

print("External backend invariant: clean")
