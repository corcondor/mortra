"""Short-lived Newclid parser process for the known-root circle cohort."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from newclid.jgex.formulation import (  # noqa: E402
    JGEXFormulation,
    jgex_formulation_from_txt_file,
)

from scripts.benchmark_hageo_known_root_circle_cohort import (  # noqa: E402
    extract_known_root_circle_cohort,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    dataset = args.dataset.resolve()
    formulations = jgex_formulation_from_txt_file(dataset)
    cohort = extract_known_root_circle_cohort(formulations)
    sources = {
        str(entry["problem"]): str(
            JGEXFormulation(
                name=formulations[str(entry["problem"])].name,
                setup_clauses=formulations[str(entry["problem"])].setup_clauses,
                auxiliary_clauses=(),
                goals=formulations[str(entry["problem"])].goals,
            )
        ).strip()
        for entry in cohort
    }
    payload = {
        "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        "cohort": cohort,
        "sources": sources,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
