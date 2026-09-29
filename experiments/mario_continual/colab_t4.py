"""T4 deployment of the existing player; no alternate policy or comparison arms."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
BASE = "c8bcb8cc4490271d599b0fc7beb61e665510253a"


def command(args):
    subprocess.run([str(x) for x in args], cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "learn"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[key] = "1"
    os.environ["PYTHONUNBUFFERED"] = "1"
    os.environ["MORTRA_DEVICE"] = "cuda"
    from experiments.accelerator import device_info
    info = device_info("cuda")
    if "T4" not in info["device_name"]:
        raise RuntimeError(f"T4 required for this notebook: {info}")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    # Do not allow two cells/processes to write the same persistent memory.
    with (output / "runner.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        receipt = output / "T4_VALIDATED.json"
        sources = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                   for folder in ("mario_continual", "continual_tools", "task_agent",
                                  "noisy_rgb_discovery", "noisy_rgb_version_space")
                   for p in sorted((ROOT / "experiments" / folder).glob("*.py"))}
        for relative in ("experiments/accelerator.py",
                         "experiments/mario_continual/java/MortraBridge.java"):
            sources[relative] = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        xvfb = ["xvfb-run", "-a", "-s", "-screen 0 1280x1024x24", sys.executable]
        if args.mode == "prepare":
            if receipt.exists():
                saved = json.loads(receipt.read_text())
                if saved["commit"] == head and saved["sources"] == sources:
                    print("T4_VALIDATION_ALREADY_COMPLETE", flush=True)
                    return
                raise RuntimeError("Existing validation is for different code; use a new output folder")
            command([sys.executable, "-m", "pytest", "-q", "tests/test_accelerator.py",
                     "tests/test_mario_cuda_validation.py", "tests/test_mario_continual.py",
                     "--junitxml=" + str(output / "cuda-tests.xml")])
            command([sys.executable, "-m", "experiments.mario_continual.setup_game"])
            validation = output / ("validation_" + str(time.time_ns()))
            command(xvfb + ["-m", "experiments.mario_continual.validate_cuda",
                            "--output", validation])
            result = json.loads((validation / "result.json").read_text())
            if result["status"] != "CUDA_AND_LIVE_RGB_VALIDATED":
                raise RuntimeError("CUDA validation did not complete")
            receipt.write_text(json.dumps(dict(
                status="T4_VALIDATED", base=BASE, commit=head, sources=sources,
                accelerator=info, validation=str(validation),
                python=sys.version, versions={name: importlib.metadata.version(name)
                    for name in ("numpy", "scipy", "torch", "pillow", "pytest")}), indent=2)+"\n")
            print("T4_VALIDATED", info["device_name"], flush=True)
            return
        saved = json.loads(receipt.read_text())
        if saved["commit"] != head or saved["sources"] != sources:
            raise RuntimeError("Code differs from the T4-validated source")
        learning = output / "learning"
        resume = (learning / "checkpoint.pkl").is_file()
        print(json.dumps(dict(event="LAUNCHING", device=info, resume=resume,
                              output=str(learning), commit=head)), flush=True)
        command(xvfb + ["-u", "-m", "experiments.mario_continual.run",
                        "--device", "cuda", "--output", learning,
                        "--checkpoint-every", "100"] + (["--resume"] if resume else []))


if __name__ == "__main__":
    main()
