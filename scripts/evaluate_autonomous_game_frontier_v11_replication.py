"""New registered seeds only, unchanged v1.1 evolution, then holdout audit."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from experiments.game_frontier_v11_replication.run import main

if __name__ == "__main__":
    main()
