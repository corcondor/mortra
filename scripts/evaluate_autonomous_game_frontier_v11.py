"""Run only the explicitly requested, preregistered Frontier v1.1 stage."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from experiments.game_frontier_v11.runner import main

if __name__ == "__main__":
    main()
