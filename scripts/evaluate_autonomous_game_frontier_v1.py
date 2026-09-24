"""Entry point for the registered frozen-core game experiment (no legacy imports)."""
import os
from pathlib import Path
import sys

for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(name, "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.game_frontier_v1.runner import main

if __name__ == "__main__":
    main()
