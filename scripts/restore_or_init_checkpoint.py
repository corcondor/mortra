"""Checkpoint restoration and initialization script for MORTRA CI workflow.

Explicitly distinguishes between:
- 'initial': Fixed baseline state (clean policy and empty acquired library).
- 'continuous': Restores from a specified checkpoint path. If missing or invalid,
  fails with an explicit error instead of silently falling back.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from math_os_prototype import geometry_recognition_policy as rec_policy


def main():
    parser = argparse.ArgumentParser(description="Restore or initialize MORTRA learning checkpoint.")
    parser.add_argument(
        "--mode",
        choices=["initial", "continuous"],
        default="initial",
        help="Execution mode: 'initial' for clean baseline, 'continuous' for checkpoint restore.",
    )
    parser.add_argument(
        "--checkpoint",
        type=str,
        default="",
        help="Path to checkpoint directory or archive (required when mode is 'continuous').",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="reports/checkpoint_manifest.json",
        help="Path to output manifest JSON.",
    )

    args = parser.parse_args()

    reports_dir = repo_root / "reports"
    policy_dir = reports_dir / "recognition-policy"
    library_dir = reports_dir / "acquired-library"

    policy_dir.mkdir(parents=True, exist_ok=True)
    library_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "mode": args.mode,
        "checkpoint_input": args.checkpoint,
        "restored": False,
        "policy_file": str(policy_dir / "recognition_policy.json"),
        "library_file": str(library_dir / "library_state.json"),
    }

    if args.mode == "initial":
        print("[MORTRA Checkpoint] Initializing clean baseline state (fixed initial state)...")
        # Initialize default recognition policy
        rec_policy.save_recognition_policy(
            rec_policy.DEFAULT_POLICY,
            policy_dir / "recognition_policy.json",
        )
        # Initialize empty library state
        empty_library = {
            "enumerated": 0,
            "acquired": 0,
            "definitions": {},
            "generations": [],
            "patterns": 0,
            "acquired_operations": [],
            "programs": [],
        }
        with (library_dir / "library_state.json").open("w", encoding="utf-8") as f:
            json.dump(empty_library, f, indent=2)

        manifest["status"] = "initialized_clean_baseline"
        manifest["restored"] = True

    elif args.mode == "continuous":
        print(f"[MORTRA Checkpoint] Continuous execution mode requested. Restoring checkpoint from: '{args.checkpoint}'...")
        if not args.checkpoint:
            print("[ERROR] Checkpoint path must be provided in 'continuous' mode!", file=sys.stderr)
            sys.exit(1)

        cp_path = Path(args.checkpoint)
        if not cp_path.is_absolute():
            cp_path = repo_root / cp_path

        if not cp_path.exists():
            print(f"[ERROR] Specified checkpoint does NOT exist: {cp_path}", file=sys.stderr)
            print("[ERROR] Cannot silently fall back to initial state in continuous mode. Aborting.", file=sys.stderr)
            sys.exit(1)

        # Look for policy and library in checkpoint path (directory or files)
        if cp_path.is_dir():
            src_policy = cp_path / "recognition_policy.json"
            if not src_policy.exists():
                src_policy = cp_path / "recognition-policy" / "recognition_policy.json"

            src_library = cp_path / "library_state.json"
            if not src_library.exists():
                src_library = cp_path / "acquired-library" / "library_state.json"

            if not src_policy.exists() and not src_library.exists():
                print(f"[ERROR] Checkpoint directory {cp_path} contains neither recognition_policy.json nor library_state.json!", file=sys.stderr)
                sys.exit(1)

            if src_policy.exists():
                with src_policy.open("r", encoding="utf-8") as f:
                    pol_data = json.load(f)
                with (policy_dir / "recognition_policy.json").open("w", encoding="utf-8") as f:
                    json.dump(pol_data, f, indent=2)
                print(f"  Restored recognition policy from: {src_policy}")

            if src_library.exists():
                with src_library.open("r", encoding="utf-8") as f:
                    lib_data = json.load(f)
                with (library_dir / "library_state.json").open("w", encoding="utf-8") as f:
                    json.dump(lib_data, f, indent=2)
                print(f"  Restored library state from: {src_library}")

        else:
            print(f"[ERROR] Checkpoint path must be a directory: {cp_path}", file=sys.stderr)
            sys.exit(1)

        manifest["status"] = "restored_from_checkpoint"
        manifest["restored"] = True
        manifest["source_path"] = str(cp_path)

    out_manifest = repo_root / args.output
    out_manifest.parent.mkdir(parents=True, exist_ok=True)
    with out_manifest.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"[MORTRA Checkpoint] Checkpoint status saved to: {out_manifest}")


if __name__ == "__main__":
    main()
