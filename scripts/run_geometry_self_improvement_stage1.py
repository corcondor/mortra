"""The state after the first stage, evaluated on the same final tasks.

The main run compares the starting state with the state after both stages. This
adds the middle point: the library after the first stage only, on the same final
tasks, with the starting policy. It replays the first stage from the saved task
file, so the library it evaluates is the one the first stage actually produced.

    python scripts/run_geometry_self_improvement_stage1.py --run reports/geometry-self-improvement
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from math_os_prototype import geometry_acquired_library as acqlib
from math_os_prototype import geometry_self_improvement as loop


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--applications", type=int, default=40)
    arguments = parser.parse_args()
    run = Path(arguments.run)
    tasks = json.loads((run/"tasks.json").read_text())
    train, final = tasks["train"], tasks["final"]
    started = time.perf_counter()

    library = acqlib.AcquiredLibrary()
    policy = dict(loop.START_POLICY)
    stage_one = loop.learn_stage(train[:len(train)//2], library=library, policy=policy,
                                 applications=arguments.applications)
    middle = loop.evaluate(final, library=library, policy=policy, applications=arguments.applications,
                           note="after stage 1: stage-1 library, starting policy")
    record = {"replayed_stage_1": {k: stage_one[k] for k in ("solved", "tasks", "failures")},
              "library_after_stage_1": library.state(),
              "final_after_stage_1": middle["summary"],
              "rows": middle["rows"], "seconds": time.perf_counter()-started}
    (run/"after-stage-1.json").write_text(json.dumps(record, indent=1, default=str)+"\n", encoding="utf-8")
    print(json.dumps({"replayed_stage_1": record["replayed_stage_1"],
                      "acquired": record["library_after_stage_1"]["acquired"],
                      "final_after_stage_1": record["final_after_stage_1"]}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
