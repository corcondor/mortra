# Codex handoff: MORTRA forward integration

Canonical branch:

`research/mortra-forward-integration-20260929`

Base before this forward integration:

`7999f8e41f712b25b83902731badfabf06e007f9`

Do **not** create a second MORTRA implementation. Check out this branch and run the existing code.

## CPU / real-Mario validation

The branch contains `.github/workflows/mortra-pre-codex-validation.yml`. It compiles all changed Python, runs the regression suite, compiles the pinned Mario AI Framework plus `MortraBridge.java`, starts the real game under Xvfb, runs persistent learning, checkpoints, starts a second game process, resumes the same MORTRA state, and runs a fresh spectral audit.

## CUDA validation

On Colab T4/L4/A100:

```bash
git checkout research/mortra-forward-integration-20260929
bash scripts/mortra_t4_validate.sh
```

The script requires a real CUDA-enabled PyTorch runtime. It does not silently fall back to CPU. It checks CPU/CUDA parity for RGB evidence and FFT, tests those kernels on actual Mario RGB batches, then runs a short real-Mario continual-learning smoke with `--device cuda`.

## Main runtime

```bash
xvfb-run -a -s '-screen 0 1280x1024x24' \
python -m experiments.mario_continual.run \
  --game-dir experiments/mario_continual/game \
  --build-dir experiments/mario_continual/build \
  --bridge-source experiments/mario_continual/java/MortraBridge.java \
  --level levels/notch/lvl-1.txt \
  --output mortra-mario-run \
  --device auto \
  --checkpoint-every 100
```

The normal stopping objective is the Mario engine's `WIN`. Numeric limits are infrastructure escape hatches, not the learning objective.

## Transport

Normal deterministic observation: screen capture -> SHA-256 -> short IPC packet -> O(1) hash lookup.

When pixels are actually needed: same-state `SNAPN` -> persistent shared mmap -> NumPy contiguous batch -> CUDA statistics/FFT if enabled.

There is no PNG transport in the current runtime.

## Important semantic boundaries

- Same/different/unresolved evidence stays three-valued.
- Unresolved evidence is never treated as a confirmed new state.
- Learned tools are revoked only by confirmed counterevidence.
- `forward/yaw` is not a hard-coded identification rule.
- ProductPlanner / VirtualFrontier remain the existing MORTRA core.
- CUDA accelerates dense perception kernels; Java game and graph reasoning stay on CPU.
