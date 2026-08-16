"""既存の証明成果物からBoolean RTM支持監査を生成する。"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from worker.backend.wu_rtm_support import audit_wu_rtm_support  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--problem", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = json.loads(args.input.read_text(encoding="utf-8"))
    proof = source["results"][args.problem]["proof"]
    audit = audit_wu_rtm_support(proof)
    report = {
        "experiment": "wu-rtm-boolean-support-projection",
        "generated_at": datetime.now(UTC).isoformat(),
        "uses_llm": False,
        "uses_problem_specific_solver_logic": False,
        "source_artifact": args.input.name,
        "problem": args.problem,
        "theoretical_basis": [
            "https://www.mdpi.com/2227-7390/14/13/2442",
            "https://arxiv.org/abs/2604.14912",
        ],
        "hypothesis": (
            "The Boolean support projection of Wu's RTM exposes proof obligations "
            "whose original-hypothesis footprint is strictly smaller than the full system."
        ),
        "audit": asdict(audit),
        "claim_scope": (
            "Support sets are certified upper bounds propagated through replayed exact "
            "pseudo-division identities; they are not minimal polynomial RTM rows."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = {
        "hypotheses": audit.hypothesis_count,
        "derived_polynomials": audit.derived_polynomial_count,
        "goal_support_width": audit.goal_support_width,
        "strict_local_obligations": audit.strict_local_obligation_count,
        "obligation_count": len(audit.local_obligations),
        "components": audit.hypothesis_components,
        "density": audit.support_matrix_density,
        "all_references_resolved": audit.all_references_resolved,
        "all_certificates_replayed": audit.all_certificates_replayed,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
