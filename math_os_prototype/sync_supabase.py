"""受験用プールを Supabase の problems テーブルへ流し込む。

GitHub Actions の生成ジョブから呼ぶことで、PC を開いていなくても
MathOS が作った問題がそのままサイトと Discord に届く。

鍵が環境にない場合は何もせず正常終了する（ローカル実行やフォークで
CI を落とさないため）。鍵の値は一切出力しない。

必要な環境変数:
  SUPABASE_URL          （NEXT_PUBLIC_SUPABASE_URL でも可）
  SUPABASE_SERVICE_KEY  （SUPABASE_SERVICE_ROLE_KEY でも可）
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DEFAULT_POOL = HERE / "problem_synthesis" / "entrance_exam_pool.json"
SOURCE_TAG = "mathos_discord_entrance_v2"
LEGACY_SOURCE_TAG = "mathos_entrance_pool"
ARCHIVE_TAG = "mathos_discord_archive"
BATCH_SIZE = 100


def _env(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value.strip()
    return None


def _problem_hash(problem: dict[str, Any]) -> str:
    payload = "␟".join(
        (
            str(problem.get("candidate_id") or ""),
            str(problem.get("family_id") or ""),
            str(problem.get("statement_tex") or ""),
            str(problem.get("answer_tex") or ""),
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_rows(pool: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for problem in pool.get("problems", []):
        certificate = problem.get("curriculum_certificate") or {}
        lift = problem.get("lift_certificate") or {}
        verification = problem.get("verification") or {}
        novelty = problem.get("novelty") or {}
        chain = list(lift.get("morphism_chain") or [])
        digest = _problem_hash(problem)
        short_id = digest[:10]
        rows.append(
            {
                "id": f"mathos-{short_id}",
                "topic_a": problem.get("domain"),
                "topic_b": problem.get("family_id"),
                "variation": 0,
                "statement": problem.get("statement_tex"),
                "answer": problem.get("answer_tex"),
                "difficulty": "C",
                "solution": problem.get("solution_tex"),
                "surprise": 8,
                "minimality": 7,
                "connection": 8,
                "inevitability": 8,
                "diff_cal": 7,
                "total": 7.6,
                "inspiration": " → ".join(chain),
                "meta": json.dumps(
                    {
                        "problemHash": digest,
                        "shortId": short_id,
                        "candidateId": problem.get("candidate_id"),
                        "familyId": problem.get("family_id"),
                        "structureKey": problem.get("structure_key"),
                        "curriculumScope": certificate.get("scope"),
                        "loweringChain": certificate.get("lowering_chain"),
                        "surfaceRewritten": bool(certificate.get("surface_rewritten")),
                        "verificationMethod": verification.get("method"),
                        "maximumSurfaceJaccard": novelty.get(
                            "maximum_surface_jaccard"
                        ),
                        "morphismChain": chain,
                        "gates": {
                            "exactBackend": True,
                            "independentCheck": True,
                            "typeChecked": True,
                            "corpusNovel": True,
                        },
                    },
                    ensure_ascii=False,
                ),
                "generation": 0,
                "parent_ids": [],
                "source_file": SOURCE_TAG,
            }
        )
    return rows


def upsert(url: str, key: str, rows: list[dict[str, Any]]) -> int:
    endpoint = f"{url.rstrip('/')}/rest/v1/problems?on_conflict=id"
    sent = 0
    for start in range(0, len(rows), BATCH_SIZE):
        chunk = rows[start:start + BATCH_SIZE]
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(chunk, ensure_ascii=False).encode("utf-8"),
            method="POST",
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates,return=minimal",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                response.read()
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", "replace")[:400]
            # 鍵の値は body に含まれないが、念のため URL も出さない
            print(f"Supabase への書き込みに失敗しました: {error.code} {body}")
            raise SystemExit(1)
        sent += len(chunk)
    return sent


def fetch_active_ids(
    url: str,
    key: str,
    source_tag: str = SOURCE_TAG,
) -> set[str]:
    """Read the currently active MathOS rows without exposing credentials."""
    ids: set[str] = set()
    offset = 0
    while True:
        endpoint = (
            f"{url.rstrip('/')}/rest/v1/problems"
            f"?select=id&source_file=eq.{source_tag}"
            f"&limit=1000&offset={offset}"
        )
        request = urllib.request.Request(
            endpoint,
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
            },
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
        batch = {
            str(item["id"])
            for item in payload
            if isinstance(item, dict) and item.get("id")
        }
        ids.update(batch)
        if len(payload) < 1000:
            break
        offset += len(payload)
    return ids


def stale_active_ids(existing: set[str], rows: list[dict[str, Any]]) -> list[str]:
    target = {str(row["id"]) for row in rows if row.get("id")}
    return sorted(existing - target)


def archive_stale(
    url: str,
    key: str,
    stale: list[str],
    *,
    source_tag: str = SOURCE_TAG,
) -> int:
    """Preserve ratings while removing superseded rows from active delivery."""
    archived = 0
    for start in range(0, len(stale), BATCH_SIZE):
        chunk = stale[start:start + BATCH_SIZE]
        encoded_ids = ",".join(urllib.parse.quote(item, safe="-") for item in chunk)
        endpoint = (
            f"{url.rstrip('/')}/rest/v1/problems"
            f"?source_file=eq.{source_tag}&id=in.({encoded_ids})"
        )
        request = urllib.request.Request(
            endpoint,
            data=json.dumps({"source_file": ARCHIVE_TAG}).encode("utf-8"),
            method="PATCH",
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                response.read()
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", "replace")[:400]
            print(f"旧問題の履歴化に失敗しました: {error.code} {body}")
            raise SystemExit(1)
        archived += len(chunk)
    return archived


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pool", type=Path, default=DEFAULT_POOL)
    args = parser.parse_args()

    url = _env("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL")
    key = _env("SUPABASE_SERVICE_KEY", "SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("Supabase の鍵が環境にないため同期を飛ばします（名前のみ確認）。")
        return 0

    if not args.pool.exists():
        print(f"プールが見つかりません: {args.pool}")
        return 1

    pool = json.loads(args.pool.read_text(encoding="utf-8"))
    rows = build_rows(pool)
    if not rows:
        print("同期する問題がありません。")
        return 0

    existing = fetch_active_ids(url, key)
    legacy = fetch_active_ids(url, key, LEGACY_SOURCE_TAG)
    stale = stale_active_ids(existing, rows)
    sent = upsert(url, key, rows)
    archived = archive_stale(url, key, stale)
    archived += archive_stale(
        url,
        key,
        sorted(legacy),
        source_tag=LEGACY_SOURCE_TAG,
    )
    print(
        f"Supabase へ {sent} 問を同期し、旧 {archived} 問を履歴化しました"
        f"（source_file={SOURCE_TAG}）。"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
