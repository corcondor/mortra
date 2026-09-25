"""Audit fixed final worlds only; no new world generation or model changes."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from experiments.game_frontier_v11_holdout.audit import main

if __name__ == "__main__":
    main()
