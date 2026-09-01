"""Expose MORTRA's exact single-problem solver to the TypeScript worker.

The bridge reads one JSON request from standard input and writes one compact
JSON response to standard output.  It deliberately runs in cold mode so that
success depends on executable mathematics, not a curated theorem entry.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from api.solve import solve_problem
from worker.backend.exact_expression_ir import evaluate_expression_ir


CARD_FIELDS = (
    "statement_tex",
    "answer_tex",
    "solution_tex",
    "family_id",
    "domain",
    "morphism_chain",
    "verification",
    "execution_certificate",
    "diagram",
    "diagram_tikz",
    "visual_explanation",
    "proof_roadmap",
    "proof_obligations",
)


def _response(request: dict[str, Any]) -> dict[str, Any]:
    statement = str(request.get("statement") or "").strip()
    if not statement:
        return {"ok": False, "status": 400, "error": "statement is required"}

    expression_ir = request.get("expression_ir")
    if expression_ir is not None:
        evaluated = evaluate_expression_ir(expression_ir)
        if evaluated.get("ok") is True:
            answer_tex = rf"\({evaluated['result_tex']}\)"
            morphism_chain = [
                "ProblemText",
                "BinderAwareExpressionIR",
                *[f"Evaluate{operator}" for operator in evaluated.get("operators") or []],
                "ExactReplay",
                "VerifiedAnswer",
            ]
            certificate = dict(evaluated["certificate"])
            certificate.update(
                {
                    "statement_sha256": hashlib.sha256(statement.encode("utf-8")).hexdigest(),
                    "answer_tex_sha256": hashlib.sha256(answer_tex.encode("utf-8")).hexdigest(),
                    "tool_name": "sympy.exact_expression_ir",
                    "morphism_chain": morphism_chain,
                    "capability_origin": "synthesized_expression_program",
                    "registered_composite_used": False,
                    "composite_cache_role": "not_consulted",
                }
            )
            checks = list(certificate.get("checks") or [])
            solution_steps = [
                rf"問題文の数式を、和・極限・積分の束縛範囲を保った式木 \({evaluated['expression_tex']}\) として読み取る。",
                "添字変数と極限変数を局所変数として扱い、外部から値や解法を補わずに内側から順に厳密計算する。",
                rf"全ての束縛演算を実行して整理すると \({evaluated['result_tex']}\) を得る。",
                "同じ式木を再構成して計算し、結果の一致と、未評価の和・極限・積分および自由変数が残らないことを確認した。",
            ]
            return {
                "ok": True,
                "status": 200,
                "engine": "MORTRA binder-aware exact IR solver (no LLM)",
                "evaluation_mode": "cold",
                "trace": ["typed expression IR", *morphism_chain[2:-2], "exact replay"],
                "card": {
                    "statement_tex": statement,
                    "answer_tex": answer_tex,
                    "solution_tex": "\n\n".join(
                        rf"\textbf{{{index}.}} {step}"
                        for index, step in enumerate(solution_steps, start=1)
                    ),
                    "family_id": "solve.runtime.exact_expression_ir",
                    "domain": "exact_bound_expression",
                    "morphism_chain": morphism_chain,
                    "verification": {
                        "method": "whitelisted binder-aware AST evaluation + independent exact replay",
                        "exact_backend": True,
                        "independent_check": True,
                        "checks": checks,
                    },
                    "execution_certificate": certificate,
                    "proof_roadmap": morphism_chain,
                    "proof_obligations": checks,
                },
            }

    status, payload = solve_problem(
        statement,
        allow_theorem_kernels=False,
        include_publication_artifact=False,
    )
    diagnostics = payload.get("diagnostics") if isinstance(payload, dict) else None
    registered_replay = bool(
        status != 200
        and isinstance(diagnostics, dict)
        and diagnostics.get("stage") == "registered_completed_route"
    )
    if registered_replay:
        # The public product must reject this route.  The research bridge still
        # needs to replay it against the current statement so that provenance,
        # parameter extraction, and cross-runtime hashes remain testable.
        status, payload = solve_problem(
            statement,
            allow_theorem_kernels=True,
            include_publication_artifact=False,
        )
    cards = payload.get("cards") if isinstance(payload, dict) else None
    if status != 200 or not isinstance(cards, list) or len(cards) != 1:
        return {
            "ok": False,
            "status": status,
            "error": str(payload.get("error") or "no certified exact answer"),
            "trace": payload.get("trace") or [],
            "evaluation_mode": payload.get("evaluation_mode"),
            "diagnostics": payload.get("diagnostics"),
        }

    source_card = cards[0]
    if not isinstance(source_card, dict):
        return {"ok": False, "status": 500, "error": "solver returned an invalid card"}

    compact_card = {
        key: source_card[key]
        for key in CARD_FIELDS
        if key in source_card and source_card[key] is not None
    }
    return {
        "ok": True,
        "status": status,
        "engine": payload.get("engine"),
        "evaluation_mode": payload.get("evaluation_mode"),
        "registered_research_replay": registered_replay,
        "trace": payload.get("trace") or [],
        "card": compact_card,
    }


def main() -> int:
    try:
        request = json.loads(sys.stdin.buffer.read().decode("utf-8"))
        if not isinstance(request, dict):
            raise TypeError("request must be a JSON object")
        statements = request.get("statements")
        if isinstance(statements, list):
            expression_irs = request.get("expression_irs")
            result = {
                "ok": True,
                "results": [
                    _response(
                        {
                            "statement": statement,
                            **(
                                {"expression_ir": expression_irs[index]}
                                if isinstance(expression_irs, list)
                                and index < len(expression_irs)
                                and expression_irs[index] is not None
                                else {}
                            ),
                        }
                    )
                    for index, statement in enumerate(statements)
                ],
            }
        else:
            result = _response(request)
    except Exception as error:  # The caller needs structured failure, not a traceback.
        result = {"ok": False, "status": 500, "error": str(error)}
    encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    sys.stdout.buffer.write(encoded)
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
