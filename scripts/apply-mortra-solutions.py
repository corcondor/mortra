"""Solve TeX itembox problems and append only verified MORTRA solutions.

The generated block is delimited and therefore idempotent.  The original file
is backed up before the first write; unsupported problems remain in the JSON
report instead of receiving fabricated answers.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from api.solve import solve_problem
from math_os_prototype.creative_tex_corpus import extract_itembox_problems


BEGIN = "% MORTRA-SOLUTIONS-BEGIN"
END = "% MORTRA-SOLUTIONS-END"


@dataclass
class AuditRow:
    ordinal: int
    label: str
    status: str
    answer_tex: str | None = None
    family_id: str | None = None
    error: str | None = None


def _existing_answer_labels(source: str) -> set[str]:
    return set(re.findall(r"\\section\*\{(問題\d+)解答\}", source))


def _escape_heading(value: str) -> str:
    return value.replace("%", r"\%").replace("#", r"\#")


def _display_math(value: str) -> str:
    if value.startswith(r"\(") and value.endswith(r"\)"):
        return r"\[" + value[2:-2] + r"\]"
    return value


def _solution_block(rows: list[tuple[AuditRow, dict]]) -> str:
    parts = [
        BEGIN,
        r"\clearpage",
        r"\fbox{MORTRAによる検証済み解答（追補）}",
        "",
        "この追補には，型付き制約への変換と厳密計算を通過した解答だけを収録する。",
        "未検証の問題には答えを補わない。",
        "",
    ]
    for row, card in rows:
        parts.extend(
            [
                rf"\section*{{{_escape_heading(row.label)}解答（入力順 {row.ordinal}）}}",
                r"\paragraph{答え}",
                _display_math(card["answer_tex"]),
                r"\paragraph{解答}",
                card["solution_tex"],
                r"\paragraph{検証}",
                r"\texttt{" + str(card["verification"]["method"]).replace("_", r"\_") + "}",
                "",
            ]
        )
    parts.append(END)
    return "\n".join(parts)


def apply_solutions(
    source_path: Path,
    report_path: Path,
    *,
    limit: int | None = None,
    candidate_indices: set[int] | None = None,
) -> dict:
    source = source_path.read_text(encoding="utf-8")
    existing_answers = _existing_answer_labels(source)
    clean_source = re.sub(
        rf"\n?{re.escape(BEGIN)}.*?{re.escape(END)}\n?",
        "\n",
        source,
        flags=re.DOTALL,
    )
    problems = extract_itembox_problems(clean_source)
    if limit is not None:
        problems = problems[:limit]

    rows: list[AuditRow] = []
    solved_rows: list[tuple[AuditRow, dict]] = []
    for block in problems:
        if block.label in existing_answers:
            rows.append(
                AuditRow(
                    ordinal=block.ordinal,
                    label=block.label,
                    status="already_answered",
                )
            )
            continue
        if candidate_indices is not None and block.ordinal not in candidate_indices:
            rows.append(
                AuditRow(
                    ordinal=block.ordinal,
                    label=block.label,
                    status="unresolved",
                    error="全件ベンチで問題全体の検証が完了していない",
                )
            )
            continue
        status, result = solve_problem(block.statement_tex)
        cards = result.get("cards") or []
        if status == 200 and cards:
            card = cards[0]
            row = AuditRow(
                ordinal=block.ordinal,
                label=block.label,
                status="verified",
                answer_tex=card.get("answer_tex"),
                family_id=card.get("family_id"),
            )
            solved_rows.append((row, card))
        else:
            row = AuditRow(
                ordinal=block.ordinal,
                label=block.label,
                status="unresolved",
                error=result.get("error") or f"HTTP {status}",
            )
        rows.append(row)

    block_text = _solution_block(solved_rows)
    if r"\end{document}" not in clean_source:
        raise ValueError("\\end{document} が見つかりません")
    output = clean_source.replace(r"\end{document}", block_text + "\n\n" + r"\end{document}", 1)

    backup = source_path.with_name(f"{source_path.stem}.before-mortra-{date.today():%Y%m%d}{source_path.suffix}")
    if not backup.exists():
        shutil.copy2(source_path, backup)
    source_path.write_text(output, encoding="utf-8", newline="\n")

    report = {
        "source": str(source_path),
        "backup": str(backup),
        "total": len(rows),
        "verified": sum(row.status == "verified" for row in rows),
        "already_answered": sum(row.status == "already_answered" for row in rows),
        "unresolved": sum(row.status == "unresolved" for row in rows),
        "rows": [asdict(row) for row in rows],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("tex", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--candidate-indices",
        help="全件ベンチで検証済みとなった入力順だけをカンマ区切りで再実行する",
    )
    args = parser.parse_args()
    candidate_indices = None
    if args.candidate_indices:
        candidate_indices = {int(value) for value in args.candidate_indices.split(",") if value.strip()}
    print(
        json.dumps(
            apply_solutions(
                args.tex,
                args.report,
                limit=args.limit,
                candidate_indices=candidate_indices,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
