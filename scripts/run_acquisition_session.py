"""One start: search, learn from the search, search again with what was learned.

    python scripts/run_acquisition_session.py --config configs/acquisition-hyper.json \
        --output artifacts/research/<name>

Resuming continues from the saved state, keeping the acquired tasks, the learned
library, the candidate queue and the enumeration cursor:

    python scripts/run_acquisition_session.py --resume artifacts/research/<name>

Nothing in here decides anything mathematical. It reads a configuration, runs
`acquisition_session.Session`, writes the state and the report, and prints the
stop reason.
"""
from __future__ import annotations

import argparse
import json
import sys
from hashlib import sha256
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from math_os_prototype.acquisition_report import report
from math_os_prototype.acquisition_session import Session

SOURCE_FILES = (
    "math_os_prototype/acquisition_session.py",
    "math_os_prototype/acquisition_report.py",
    "math_os_prototype/powerplay_driver.py",
    "math_os_prototype/powerplay_proposer.py",
    "math_os_prototype/library_compression.py",
    "math_os_prototype/abstraction_correspondence.py",
    "math_os_prototype/acquisition_followups.py",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path,
                        help="JSON configuration; see configs/acquisition-hyper.json")
    parser.add_argument("--resume", type=Path,
                        help="a directory holding session.json")
    parser.add_argument("--output", type=Path,
                        help="where to write session.json and report.txt")
    parser.add_argument("--quiet", action="store_true")
    arguments = parser.parse_args()

    if bool(arguments.config) == bool(arguments.resume):
        parser.error("give exactly one of --config and --resume")

    if arguments.resume:
        session = Session.load(arguments.resume)
        output = arguments.output or arguments.resume
        session.stop_reason = None
    else:
        config = json.loads(arguments.config.read_text(encoding="utf-8"))
        session = Session(config)
        output = arguments.output or Path("artifacts/research/acquisition-session")

    progress = None if arguments.quiet else (lambda line: print(line, flush=True))
    session.run(progress=progress)
    path = session.save(output)

    state = json.loads(Path(path).read_text(encoding="utf-8"))
    text = report(state)
    (Path(output) / "report.txt").write_text(text, encoding="utf-8")

    root = Path(__file__).resolve().parents[1]
    (Path(output) / "seal.json").write_text(json.dumps({
        "schema": "mortra.acquisition-session.seal.v1",
        "session_sha256": state["sha256"],
        "source_files": {name: sha256((root / name).read_bytes()).hexdigest()
                         for name in SOURCE_FILES},
    }, indent=1), encoding="utf-8")

    print()
    print(f"cycles      : {len(state['cycles'])}")
    print(f"accepted    : {sum(c['accepted_count'] for c in state['cycles'])}")
    print(f"definitions : {len(state['cycles'][-1]['library']) if state['cycles'] else 0}")
    print(f"compression : {sum(c['compression_bits'] for c in state['cycles']):+d} bits "
          "(per cycle, each measured on that cycle's corpus)")
    print(f"stop reason : {state['stop_reason']}")
    print(f"written     : {output}")


if __name__ == "__main__":
    main()
