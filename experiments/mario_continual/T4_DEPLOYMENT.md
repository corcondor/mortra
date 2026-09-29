# T4 deployment, 2026-09-29

- Player baseline: `c8bcb8cc4490271d599b0fc7beb61e665510253a`.
- Executed source: `e6ac5be605943add20deec0bcf51d3bad5e0e1c7`.
- Notebook: https://colab.research.google.com/drive/1nef9TSlmgByb4DYAA4jTbUgElNb52oYg
- Persistent output: `/content/drive/MyDrive/MORTRA/mario-t4-e6ac5be6`.
- Actual device: Tesla T4, 15,637,086,208 bytes VRAM; PyTorch 2.11.0+cu128,
  CUDA 12.8, NumPy 2.1.3.

## Verified

The local regression suite passed 44 tests, with 4 CUDA tests skipped locally.
The Colab suite passed all 17 selected tests, including the 4 real CUDA cases.
The pinned Mario AI Framework (`b0f01f224f868cdedf6a4b1f75ecc4c7a1f53545`)
and bridge compiled (86 framework Java files). A live batch of 64 RGB images
with shape `[64, 240, 256, 3]` was processed on CUDA. Maximum normalized FFT
error against CPU was `9.589173544100049e-08`; both live-image z-scores were 0.
These are numerical and transport checks, not game-performance measurements.

An observed learning checkpoint recorded 500 decisions / 500 primitive actions,
2 episodes, 303 predictive states and 500 known state-action pairs at
9.611587557 seconds. It recorded 0 learned/reused tools and no first clear.
A later checkpoint recorded 3,000 decisions / 3,000 primitive actions,
12 episodes, 1,663 predictive states and 2,964 known state-action pairs at
65.02480446 seconds, still with 0 learned/reused tools and no first clear.
The Colab launcher PID was 7450. These are startup observations, not a sustained
throughput or speedup claim.

## Implementation

The player, action alphabet, evidence thresholds and planner remain unchanged.
The original CPU centering operation is now shared before both FFT backends:
CUDA float32 reduction order otherwise introduced a different near-zero DC
component. Test tolerances were not relaxed. FFT itself and dense RGB statistics
execute on CUDA when requested; exact-hash recognition, Java and graph reasoning
remain on CPU. A clean hash hit does not require GPU work.

The notebook uses a full OpenJDK 17 installation (not headless-only), Xvfb,
explicit CUDA selection, visible subprocess output, a validation receipt and
a writer lock. Image transfer remains hash plus local `/dev/shm` mmap, not Drive
per-frame files. Memory checkpoints are written to Drive by the original player.

## Reproduce and Resume

Run the notebook cells in order on T4. The source SHA is pinned. The validation
receipt must match that SHA and source hashes before learning starts. The last
cell runs one persistent player until WIN, without comparison arms or an added
decision limit. On a later session, repeat the setup cells and the last cell;
the same output folder restores `learning/checkpoint.pkl` when present.

This starts a separate run of the current player. Older notebooks and their
incompatible checkpoints were not overwritten or silently imported. Original
checkpoint cadence is retained: abrupt runtime loss can discard work since the
latest saved checkpoint. Runtime lifetime is controlled by Colab.
