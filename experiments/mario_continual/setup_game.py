"""Fetch and compile the pinned Mario AI research framework plus MORTRA bridge."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

GAME_COMMIT = "b0f01f224f868cdedf6a4b1f75ecc4c7a1f53545"
REPOSITORY = "https://github.com/amidos2006/Mario-AI-Framework.git"
ROOT = Path(__file__).resolve().parent
BRIDGE = ROOT / "java" / "MortraBridge.java"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--game-dir", type=Path, default=ROOT / "game")
    parser.add_argument("--build-dir", type=Path, default=ROOT / "build")
    args = parser.parse_args()
    game = args.game_dir.resolve()
    build = args.build_dir.resolve()

    if not game.exists():
        subprocess.run(["git", "clone", "--no-checkout", REPOSITORY, str(game)], check=True)
        subprocess.run(["git", "-C", str(game), "checkout", "--detach", GAME_COMMIT], check=True)
    head = subprocess.check_output(["git", "-C", str(game), "rev-parse", "HEAD"], text=True).strip()
    if head != GAME_COMMIT:
        raise RuntimeError(f"wrong Mario framework checkout: {head}")
    dirty = subprocess.check_output(
        ["git", "-C", str(game), "status", "--porcelain", "--untracked-files=no"], text=True).strip()
    if dirty:
        raise RuntimeError("tracked Mario framework source is modified")

    sources = sorted((game / "src").rglob("*.java"))
    if not sources:
        raise RuntimeError("Mario framework Java source missing")
    build.mkdir(parents=True, exist_ok=True)
    argfile = ROOT / "javac_args.txt"
    argfile.write_text(
        "\n".join('"' + str(path).replace("\\\\", "/") + '"' for path in sources + [BRIDGE]) + "\n",
        encoding="utf8")
    result = subprocess.run(
        ["javac", "-encoding", "UTF-8", "-d", str(build), "@" + str(argfile)],
        text=True, capture_output=True)
    (ROOT / "javac.log").write_text(result.stdout + result.stderr, encoding="utf8")
    if result.returncode:
        raise RuntimeError("javac failed; see javac.log")

    receipt = {
        "status": "REAL_FRAMEWORK_COMPILED",
        "repository": REPOSITORY,
        "commit": head,
        "game_dir": str(game),
        "build_dir": str(build),
        "bridge_sha256": hashlib.sha256(BRIDGE.read_bytes()).hexdigest(),
        "java_files": len(sources),
    }
    (ROOT / "setup_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf8")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
