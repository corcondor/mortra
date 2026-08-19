"""Audit the public jukenmath.net corpus without crawling detail pages.

The site exposes a paginated public RPC used by its own problem-list UI.  This
module calls that RPC at a deliberately low rate, then records derived
structural metadata.  It does not import comments, user profiles, or solutions.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

try:
    from math_os_prototype.corpus_lift_protocol import CorpusCase, evaluate_case
except ImportError:
    from corpus_lift_protocol import CorpusCase, evaluate_case


SITE_ROOT = "https://jukenmath.net"
PUBLIC_PAGE_RPC = "get_public_problem_page_optimized"
DEFAULT_OUTPUT = Path("problem_synthesis/jukenmath_public_full_audit.json")
SCRIPT_PATTERN = re.compile(r"""<script[^>]+src=["']([^"']+)["']""")
SUPABASE_URL_PATTERN = re.compile(r"https://[a-z0-9]+\.supabase\.co")
PUBLIC_KEY_PATTERN = re.compile(r"sb_publishable_[A-Za-z0-9_-]+")
# Public browser credentials previously exposed by the site's own list UI.
# The current server-rendered deployment no longer includes both values in a
# client bundle, but the same read-only public RPC remains active.  The RPC
# response schema is validated by fetch_public_problems before data is used.
KNOWN_PUBLIC_CONFIG = (
    "https://nrmfumnedbccpspirvyg.supabase.co",
    "sb_publishable_Mn04HgQ_CDUCylSLyHoQWA_YFlQ_24L",
)


def canonical_surface(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\\(?:left|right|displaystyle|textstyle)", "", text)
    text = re.sub(r"\s+", "", text)
    return text


def surface_ngrams(text: str, n: int = 3) -> frozenset[str]:
    compact = canonical_surface(text)
    if len(compact) <= n:
        return frozenset({compact}) if compact else frozenset()
    return frozenset(compact[index : index + n] for index in range(len(compact) - n + 1))


def jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    if not left and not right:
        return 1.0
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def discover_public_config(site_root: str = SITE_ROOT) -> tuple[str, str]:
    html = request_text(site_root + "/")
    script_urls = [
        urllib.parse.urljoin(site_root + "/", match.group(1))
        for match in SCRIPT_PATTERN.finditer(html)
        if "_next/static/chunks/" in match.group(1)
    ]
    for script_url in script_urls:
        script = request_text(script_url)
        url_match = SUPABASE_URL_PATTERN.search(script)
        key_match = PUBLIC_KEY_PATTERN.search(script)
        if url_match and key_match:
            return url_match.group(0), key_match.group(0)
    return KNOWN_PUBLIC_CONFIG


def request_text(url: str, *, timeout: float = 30.0) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "MathOS-CorpusAudit/1.0 (+research; low-rate public RPC)"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def post_json(
    url: str,
    payload: dict[str, Any],
    *,
    public_key: str,
    timeout: float = 30.0,
) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "apikey": public_key,
            "Content-Type": "application/json",
            "User-Agent": "MathOS-CorpusAudit/1.0 (+research; low-rate public RPC)",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not isinstance(result, dict):
        raise RuntimeError("The public problem RPC returned a non-object response.")
    return result


def fetch_public_problems(
    *,
    site_root: str = SITE_ROOT,
    page_size: int = 24,
    delay_seconds: float = 0.35,
    max_pages: int | None = None,
) -> list[dict[str, Any]]:
    if not 1 <= page_size <= 24:
        raise ValueError("page_size must be between 1 and 24")
    supabase_url, public_key = discover_public_config(site_root)
    endpoint = f"{supabase_url.rstrip('/')}/rest/v1/rpc/{PUBLIC_PAGE_RPC}"
    rows: list[dict[str, Any]] = []
    seen: set[int] = set()
    page = 1
    expected_total: int | None = None
    while max_pages is None or page <= max_pages:
        payload = {
            "search_query": "",
            "requested_category": "",
            "requested_sort": "newest",
            "requested_page": page,
            "requested_page_size": page_size,
        }
        response = post_json(endpoint, payload, public_key=public_key)
        page_rows = response.get("problems")
        total = response.get("total")
        if not isinstance(page_rows, list) or not isinstance(total, int):
            raise RuntimeError("The public problem RPC response has an unexpected schema.")
        expected_total = total if expected_total is None else expected_total
        if total != expected_total:
            raise RuntimeError("The public corpus changed while the snapshot was being read.")
        for row in page_rows:
            problem_id = int(row["id"])
            if problem_id not in seen:
                seen.add(problem_id)
                rows.append(dict(row))
        if not page_rows or len(rows) >= total:
            break
        page += 1
        time.sleep(max(0.0, delay_seconds))
    return rows


def analyze_rows(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    materialized = list(rows)
    category_counts: Counter[str] = Counter()
    family_counts: Counter[str] = Counter()
    graph_counts: Counter[str] = Counter()
    lengths: list[int] = []
    records: list[dict[str, Any]] = []
    exact_groups: dict[str, list[int]] = defaultdict(list)
    ngrams: dict[int, frozenset[str]] = {}

    for row in materialized:
        problem_id = int(row["id"])
        statement = str(row.get("problem_tex") or "")
        category = str(row.get("category") or "未分類")
        digest = sha256(canonical_surface(statement).encode("utf-8")).hexdigest()
        exact_groups[digest].append(problem_id)
        ngrams[problem_id] = surface_ngrams(statement)
        category_counts[category] += 1
        lengths.append(len(canonical_surface(statement)))

        lift = evaluate_case(
            CorpusCase(
                source="jukenmath.net",
                subset=category,
                index=problem_id,
                problem=statement,
            )
        )
        family_counts.update(lift.lift_families or ["<none>"])
        graph_counts[lift.graph_status or "<empty>"] += 1
        records.append(
            {
                "id": problem_id,
                "source_url": f"{SITE_ROOT}/problems/{problem_id}",
                "title": str(row.get("title") or ""),
                "category": category,
                "statement_sha256": digest,
                "surface_length": len(canonical_surface(statement)),
                "has_solution": bool(row.get("has_solution")),
                "is_official_certified": bool(row.get("is_official_certified")),
                "official_difficulty": row.get("official_difficulty"),
                "graph_status": lift.graph_status,
                "lifted": lift.lifted,
                "lift_families": lift.lift_families,
                "certificate_signatures": lift.certificate_signatures,
                "backend_executed": lift.backend_executed,
                "backend_answer_unchecked": lift.answer,
                "verification_level": (
                    "backend_result_without_gold"
                    if lift.backend_executed
                    else "lift_only"
                    if lift.lifted
                    else "syntax_semantics_only"
                ),
                "error": lift.error,
            }
        )

    near_duplicates = find_near_duplicates(ngrams)
    exact_duplicates = [
        ids for ids in exact_groups.values() if len(ids) > 1
    ]
    lifted = sum(bool(record["lifted"]) for record in records)
    backend = sum(bool(record["backend_executed"]) for record in records)
    errors = sum(record["error"] is not None for record in records)
    official = sum(bool(record["is_official_certified"]) for record in records)
    solutions = sum(bool(record["has_solution"]) for record in records)
    total = len(records)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "site": SITE_ROOT,
            "collection_method": "public paginated RPC used by the site UI",
            "detail_pages_crawled": 0,
            "solutions_imported": False,
            "comments_imported": False,
        },
        "verification_contract": {
            "semantic_compilation": "checked for every fetched problem",
            "lift_certificate": "checked for every fetched problem",
            "backend_execution": "attempted only from admissible certificates",
            "answer_correctness": (
                "not claimed: the public list RPC exposes has_solution but not gold answers"
            ),
        },
        "summary": {
            "total": total,
            "official_certified": official,
            "has_solution": solutions,
            "semantic_errors": errors,
            "lifted": lifted,
            "backend_executed": backend,
            "lift_rate": lifted / total if total else 0.0,
            "backend_execution_rate": backend / total if total else 0.0,
            "surface_length": describe_lengths(lengths),
            "category_counts": dict(category_counts.most_common()),
            "graph_status_counts": dict(graph_counts.most_common()),
            "family_counts": dict(family_counts.most_common()),
            "exact_duplicate_groups": exact_duplicates,
            "near_duplicate_pairs": near_duplicates,
        },
        "records": records,
    }


def find_near_duplicates(
    ngrams: dict[int, frozenset[str]],
    *,
    threshold: float = 0.82,
    max_pairs: int = 80,
) -> list[dict[str, Any]]:
    identifiers = sorted(ngrams)
    matches: list[dict[str, Any]] = []
    for left_index, left_id in enumerate(identifiers):
        left = ngrams[left_id]
        for right_id in identifiers[left_index + 1 :]:
            right = ngrams[right_id]
            if min(len(left), len(right)) < 8:
                continue
            ratio = len(left) / len(right) if len(left) <= len(right) else len(right) / len(left)
            if ratio < 0.55:
                continue
            score = jaccard(left, right)
            if score >= threshold:
                matches.append({"left_id": left_id, "right_id": right_id, "score": round(score, 4)})
    return sorted(matches, key=lambda item: (-item["score"], item["left_id"], item["right_id"]))[:max_pairs]


def describe_lengths(lengths: list[int]) -> dict[str, float | int]:
    if not lengths:
        return {"min": 0, "median": 0, "mean": 0.0, "max": 0}
    ordered = sorted(lengths)
    middle = len(ordered) // 2
    median = (
        ordered[middle]
        if len(ordered) % 2
        else (ordered[middle - 1] + ordered[middle]) / 2
    )
    return {
        "min": ordered[0],
        "median": median,
        "mean": round(sum(ordered) / len(ordered), 2),
        "max": ordered[-1],
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    markdown = render_markdown(report)
    path.with_suffix(".md").write_text(markdown, encoding="utf-8")


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# jukenmath.net 公開問題 全件構造監査",
        "",
        f"- 取得件数: {summary['total']}",
        f"- 公式認定: {summary['official_certified']}",
        f"- 解答あり表示: {summary['has_solution']}",
        f"- 意味コンパイルエラー: {summary['semantic_errors']}",
        f"- LiftCertificate生成: {summary['lifted']} ({summary['lift_rate']:.1%})",
        f"- backend実行: {summary['backend_executed']} ({summary['backend_execution_rate']:.1%})",
        "",
        "## 検証範囲",
        "",
        "全問題について構文・型付き意味グラフ・LiftCertificateを調べた。"
        "公開一覧APIには正答本文が含まれないため、backendが返した値を正答とは扱わない。",
        "",
        "## 分野",
        "",
        "| 分野 | 件数 |",
        "| --- | ---: |",
    ]
    for category, count in summary["category_counts"].items():
        lines.append(f"| {category} | {count} |")
    lines.extend(
        [
            "",
            "## Lift family",
            "",
            "| family | 件数 |",
            "| --- | ---: |",
        ]
    )
    for family, count in summary["family_counts"].items():
        lines.append(f"| `{family}` | {count} |")
    lines.extend(
        [
            "",
            "## 重複監査",
            "",
            f"- 完全一致グループ: {len(summary['exact_duplicate_groups'])}",
            f"- 高類似ペア: {len(summary['near_duplicate_pairs'])}",
            "",
            "このレポートは問題文や解答の再配布物ではなく、導出した構造メタデータである。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--delay", type=float, default=0.35)
    parser.add_argument("--max-pages", type=int)
    args = parser.parse_args()
    rows = fetch_public_problems(delay_seconds=args.delay, max_pages=args.max_pages)
    report = analyze_rows(rows)
    write_report(args.output, report)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
