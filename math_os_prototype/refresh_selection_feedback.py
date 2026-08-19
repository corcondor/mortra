"""Refresh the active-delivery skip list from Sakumon Station ratings."""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
DEFAULT_OUTPUT = HERE / "problem_synthesis" / "selection_feedback_snapshot.json"
BATCH_SIZE = 100


def _env(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value.strip()
    return None


def _request_json(url: str, key: str) -> list[dict[str, Any]]:
    request = urllib.request.Request(
        url,
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, list) else []


def _fetch_problem_structures(url: str, key: str) -> dict[str, str]:
    result: dict[str, str] = {}
    offset = 0
    while True:
        query = urllib.parse.urlencode(
            {
                "select": "id,meta",
                "source_file": "in.(mathos_discord_entrance_v2,mathos_discord_archive)",
                "limit": "1000",
                "offset": str(offset),
            }
        )
        rows = _request_json(f"{url.rstrip('/')}/rest/v1/problems?{query}", key)
        for row in rows:
            try:
                meta = json.loads(row.get("meta") or "{}")
            except (TypeError, json.JSONDecodeError):
                continue
            structure_key = meta.get("structureKey")
            if row.get("id") and structure_key:
                result[str(row["id"])] = str(structure_key)
        if len(rows) < 1000:
            break
        offset += len(rows)
    return result


def _fetch_ratings(
    url: str,
    key: str,
    problem_ids: list[str],
) -> list[dict[str, Any]]:
    ratings: list[dict[str, Any]] = []
    for start in range(0, len(problem_ids), BATCH_SIZE):
        chunk = problem_ids[start:start + BATCH_SIZE]
        id_filter = "in.(" + ",".join(chunk) + ")"
        query = urllib.parse.urlencode(
            {
                "select": "problem_id,status,updated_at,note",
                "problem_id": id_filter,
                "status": "in.(selected,rejected)",
            }
        )
        ratings.extend(
            _request_json(f"{url.rstrip('/')}/rest/v1/ratings?{query}", key)
        )
    return ratings


def summarize_ratings(
    problem_structures: dict[str, str],
    ratings: list[dict[str, Any]],
) -> dict[str, Any]:
    statuses: dict[str, set[str]] = defaultdict(set)
    vote_rows: dict[str, int] = defaultdict(int)
    for rating in ratings:
        structure_key = problem_structures.get(str(rating.get("problem_id") or ""))
        status = str(rating.get("status") or "")
        if not structure_key or status not in {"selected", "rejected"}:
            continue
        statuses[structure_key].add(status)
        vote_rows[structure_key] += 1

    structures = []
    for structure_key in sorted(statuses):
        values = statuses[structure_key]
        label = next(iter(values)) if len(values) == 1 else "conflict"
        structures.append(
            {
                "structure_key": structure_key,
                "label": label,
                "disposition": "remove_from_active" if label == "rejected" else "retain",
                "vote_rows": vote_rows[structure_key],
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "unit": "structure_key",
        "policy": {
            "rejected": "remove from active delivery and retain vote history",
            "selected": "retain",
            "conflict": "retain pending re-rating",
        },
        "summary": {
            "structures": len(structures),
            "rejected": sum(item["label"] == "rejected" for item in structures),
            "selected": sum(item["label"] == "selected" for item in structures),
            "conflict": sum(item["label"] == "conflict" for item in structures),
        },
        "structures": structures,
    }


def main() -> int:
    url = _env("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL")
    key = _env("SUPABASE_SERVICE_KEY", "SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        if DEFAULT_OUTPUT.exists():
            print("Supabase key unavailable; using committed selection snapshot.")
            return 0
        print("Supabase key unavailable and no selection snapshot exists.")
        return 1

    problem_structures = _fetch_problem_structures(url, key)
    ratings = _fetch_ratings(url, key, sorted(problem_structures))
    payload = summarize_ratings(problem_structures, ratings)
    DEFAULT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
