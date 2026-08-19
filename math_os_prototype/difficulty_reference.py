"""Versioned, self-checking reference statements for difficulty diagnostics.

Difficulty scores are not permitted to gate delivery until human ratings show
that the score predicts the human decision with sufficient accuracy.  This
module only fixes the input side of that future calibration experiment.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable

try:
    from math_os_prototype.latex_frontend import (
        extract_document_body,
        strip_comments,
    )
except ImportError:  # pragma: no cover - direct script execution
    from latex_frontend import extract_document_body, strip_comments


ROOT = Path(__file__).resolve().parent
FIXED_REFERENCE_PATH = ROOT / "problem_synthesis" / "local_hard_corpus.json"
REFERENCE_VERSION = "local-hard-corpus-v1-2026-07-31"
EXPECTED_REFERENCE_COUNT = 176
# Filled from the normalized problem statements in local_hard_corpus.json.
EXPECTED_REFERENCE_SHA256 = (
    "87cf951e8617ffa716669be8e4ab20d045519cbfa57d95b409a7476cb4c00878"
)

FORBIDDEN_DOCUMENT_MARKERS = (
    r"\documentclass",
    r"\usepackage",
    r"\begin{document}",
    r"\end{document}",
)

HUMAN_AUC = 0.086
MINIMUM_GATING_AUC = 0.7
DIFFICULTY_GATING_ENABLED = HUMAN_AUC >= MINIMUM_GATING_AUC


def extract_problem_statement(source: str) -> str:
    """Extract only the problem body and reject leaked document scaffolding."""

    body = extract_document_body(strip_comments(str(source))).strip()
    if not body:
        raise ValueError("empty problem statement")
    leaked = [marker for marker in FORBIDDEN_DOCUMENT_MARKERS if marker in body]
    if leaked:
        raise ValueError(
            "LaTeX document scaffolding leaked into the problem statement: "
            + ", ".join(leaked)
        )
    return body


def canonical_reference_statement(source: str) -> str:
    statement = extract_problem_statement(source)
    statement = unicodedata.normalize("NFKC", statement)
    return re.sub(r"\s+", " ", statement).strip()


def reference_digest(rows: Iterable[dict[str, Any]]) -> str:
    canonical = [
        canonical_reference_statement(str(row.get("statement") or ""))
        for row in rows
    ]
    payload = "\n".join(canonical).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def normalize_reference_rows(
    rows: Iterable[dict[str, Any]],
) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for index, row in enumerate(rows):
        statement = extract_problem_statement(str(row.get("statement") or ""))
        normalized.append(
            {
                "source": str(row.get("source") or "unknown"),
                "id": str(row.get("id") or index),
                "statement": statement,
                "solution": str(row.get("solution") or ""),
            }
        )
    return normalized


def load_fixed_reference(
    path: Path = FIXED_REFERENCE_PATH,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = normalize_reference_rows(payload.get("problems", []))
    digest = reference_digest(rows)
    if len(rows) != EXPECTED_REFERENCE_COUNT:
        raise RuntimeError(
            f"{REFERENCE_VERSION}: expected {EXPECTED_REFERENCE_COUNT} statements, "
            f"found {len(rows)}; bump the reference version intentionally"
        )
    if EXPECTED_REFERENCE_SHA256 and digest != EXPECTED_REFERENCE_SHA256:
        raise RuntimeError(
            f"{REFERENCE_VERSION}: reference digest changed from "
            f"{EXPECTED_REFERENCE_SHA256} to {digest}; bump the reference "
            "version intentionally"
        )
    metadata = {
        "version": REFERENCE_VERSION,
        "count": len(rows),
        "sha256": digest,
        "extraction": (
            "strip TeX comments; extract document body; reject documentclass, "
            "usepackage, and document environment leakage; normalize NFKC and "
            "whitespace only for the digest"
        ),
        "human_auc": HUMAN_AUC,
        "minimum_gating_auc": MINIMUM_GATING_AUC,
        "gating_enabled": DIFFICULTY_GATING_ENABLED,
    }
    return rows, metadata
