# MORTRA on Colab GPU

## Recommended accelerator

Use a **T4 GPU** for the current MORTRA Mario pipeline.  L4/A100 are also
supported and faster if available.  TPU v5e is intentionally not the primary
backend: the current runtime is a Java game process plus dynamic Python graph
reasoning, while only dense perception kernels are accelerator-friendly.

The control semantics do not change with CUDA:

- Java Mario / Xvfb: CPU
- predictive graph / ProductPlanner / VirtualFrontier: CPU
- RGB batch mean/variance and z-score: CUDA when selected
- Fourier transforms used by visual/spectral experiments: CUDA-capable helper

This avoids rewriting MORTRA around a device-specific framework.

## Colab setup

Select **Runtime -> Change runtime type -> T4 GPU** (or L4/A100).

Then:

\`\`\`bash
!nvidia-smi
!python - <<'PY'
import torch
print(torch.__version__)
print("cuda", torch.cuda.is_available())
print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else "NONE")
PY
\`\`\`

Clone/check out the integration branch and install the non-Torch dependencies:

\`\`\`bash
!git clone https://github.com/corcondor/mortra.git
%cd mortra
!git checkout research/mortra-forward-integration-20260929
!sudo apt-get update -qq
!sudo apt-get install -y xvfb xauth
!pip install -q numpy==1.26.4 Pillow==11.3.0 scipy psutil
\`\`\`

Colab normally already provides CUDA-enabled PyTorch.  Verify MORTRA sees it:

\`\`\`bash
!python - <<'PY'
from experiments.accelerator import device_info
print(device_info("cuda"))
PY
\`\`\`

Compile the pinned Mario framework:

\`\`\`bash
!python -m experiments.mario_continual.setup_game
\`\`\`

Run persistent learning with CUDA perception:

\`\`\`bash
!xvfb-run -a -s '-screen 0 1280x1024x24' \
  python -m experiments.mario_continual.run \
    --game-dir experiments/mario_continual/game \
    --build-dir experiments/mario_continual/build \
    --bridge-source experiments/mario_continual/java/MortraBridge.java \
    --level levels/notch/lvl-1.txt \
    --output /content/mortra_mario_run \
    --device cuda \
    --checkpoint-every 100
\`\`\`

For automatic selection, use \`--device auto\`.  It chooses CUDA when a
CUDA-enabled PyTorch runtime is actually available and otherwise preserves the
CPU path.

## TPU v5e

The current branch does not claim TPU support.  Supporting v5e properly would
mean moving the batched numerical path to JAX/XLA and arranging much larger
static batches.  That does not accelerate the Java game, subprocess I/O,
predictive-state graph updates, or branch-heavy online control, so it is not the
right first accelerator for this experiment.
