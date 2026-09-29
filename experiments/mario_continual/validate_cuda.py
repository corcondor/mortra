"""Exercise CUDA with live Mario pixels, without changing the player policy."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

import numpy as np

from experiments.accelerator import device_info, fft2_batch, z_score_rgb_batches
from experiments.mario_continual.port import MarioRGBPort


def check_kernels(a, b):
    """Numerical regression, not a CPU/GPU speed or policy comparison."""
    cpu = z_score_rgb_batches(a, b, device="cpu")
    gpu = z_score_rgb_batches(a, b, device="cuda")
    np.testing.assert_allclose(gpu, cpu, rtol=2e-5, atol=2e-6)
    gray = a.astype(np.float32).mean(axis=-1)
    cm, cp = fft2_batch(gray, device="cpu")
    gm, gp = fft2_batch(gray, device="cuda")
    # Phase is undefined at zero amplitude. Compare the complex spectra instead.
    expected = cm * np.exp(1j * cp)
    actual = gm * np.exp(1j * gp)
    scale = max(1.0, float(np.max(np.abs(expected))))
    np.testing.assert_allclose(actual / scale, expected / scale,
                               rtol=2e-5, atol=2e-6)
    return dict(z_cpu=cpu, z_cuda=gpu,
                fft_max_normalized_error=float(np.max(np.abs(actual-expected))/scale))


def main():
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--game-dir", type=Path, default=root / "game")
    parser.add_argument("--build-dir", type=Path, default=root / "build")
    parser.add_argument("--level", default="levels/notch/lvl-1.txt")
    args = parser.parse_args()
    info = device_info("cuda")  # Explicitly fails without a working CUDA device.
    import torch
    args.output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    torch.cuda.reset_peak_memory_stats()
    rng = np.random.default_rng(20260929)
    a = rng.integers(0, 256, size=(32, 32, 32, 3), dtype=np.uint8)
    b = rng.integers(0, 256, size=a.shape, dtype=np.uint8)
    numerical = check_kernels(a, b)
    port = MarioRGBPort(args.game_dir, args.build_dir, root / "java/MortraBridge.java",
                        args.level, args.output / "real_game")
    try:
        _, packet = port.start()
        frame = packet["frame"]
        pixels, packets = port.repeated_observation(64)
        assert all(p["frame"] == frame for p in packets)
        live = check_kernels(pixels[:32], pixels[32:])
        transport = port.metrics()
        assert transport["primitive_actions"] == 0
        digest = hashlib.sha256(pixels.tobytes()).hexdigest()
    finally:
        port.close()
    torch.cuda.synchronize()
    result = dict(status="CUDA_AND_LIVE_RGB_VALIDATED", accelerator=info,
                  commit=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                  torch_version=torch.__version__, numpy_version=np.__version__,
                  numerical=numerical, live_rgb=live, transport=transport,
                  live_batch_sha256=digest, live_batch_shape=list(pixels.shape),
                  peak_cuda_bytes=torch.cuda.max_memory_allocated(),
                  wall_seconds=time.monotonic()-started,
                  note="Kernel/transport validation only; no claim of Mario improvement.")
    (args.output / "result.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf8")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
