"""Re-evaluate saved G0-G10 worlds; never generate or select worlds."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from experiments.game_frontier_v11_generation_holdout.audit import main

if __name__ == "__main__":
    main()
