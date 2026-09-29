#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== MORTRA T4/L4/A100 validation =="
python - <<'PY'
import json
from experiments.accelerator import device_info
info=device_info("cuda")
print(json.dumps(info,indent=2))
assert info["resolved"]=="cuda" and info["cuda_available"], info
PY

if command -v apt-get >/dev/null 2>&1; then
  if ! command -v Xvfb >/dev/null 2>&1; then
    sudo apt-get update -qq
    sudo apt-get install -y xvfb xauth
  fi
fi

python - <<'PY'
import importlib.util
missing=[name for name in ("numpy","PIL","scipy","psutil","torch")
         if importlib.util.find_spec(name) is None]
if missing:
    raise SystemExit("Missing Python packages: "+", ".join(missing))
PY

python -m experiments.mario_continual.setup_game

OUT="${1:-$ROOT/t4-validation}"
rm -rf "$OUT"

xvfb-run -a -s '-screen 0 1280x1024x24' \
  python -m experiments.mario_continual.validate_gpu \
    --game-dir experiments/mario_continual/game \
    --build-dir experiments/mario_continual/build \
    --bridge-source experiments/mario_continual/java/MortraBridge.java \
    --level levels/notch/lvl-1.txt \
    --output "$OUT/gpu"

xvfb-run -a -s '-screen 0 1280x1024x24' \
  python -m experiments.mario_continual.run \
    --game-dir experiments/mario_continual/game \
    --build-dir experiments/mario_continual/build \
    --bridge-source experiments/mario_continual/java/MortraBridge.java \
    --level levels/notch/lvl-1.txt \
    --output "$OUT/mario" \
    --device cuda \
    --checkpoint-every 4 \
    --max-decisions 24

python - <<'PY' "$OUT"
import json, pathlib, sys
root=pathlib.Path(sys.argv[1])
gpu=json.loads((root/"gpu"/"GPU_VALIDATION.json").read_text())
status=json.loads((root/"mario"/"status.json").read_text())
assert gpu["status"]=="CUDA_VALIDATION_PASS", gpu
assert status["accelerator"]["resolved"]=="cuda", status
assert status["decisions"]==24, status
assert status["primitive_actions"]>=24, status
assert status["predictive_states"]>=1, status
assert status["observation_classes"]>=1, status
receipt={
  "status":"T4_OR_CUDA_REAL_MARIO_VALIDATION_PASS",
  "gpu":gpu["device"],
  "mario":status,
}
(root/"T4_VALIDATION_COMPLETE.json").write_text(json.dumps(receipt,indent=2)+"\n")
print(json.dumps(receipt,indent=2))
PY
