r"""
Import the normalized legacy TeX archive manifest into Supabase.

The manifest is produced by scripts/ingest_legacy_tex_archives.py. Imported
rows are marked with generation=-2 and meta.source_kind=legacy_exam_tex_archive
so they stay separate from the older hand-made/PDF corpus (generation=-1).

Usage:
  python scripts/import_legacy_tex_manifest.py --dry-run --manifest C:\tmp\sakumon_legacy_tex_manifest.jsonl
  python scripts/import_legacy_tex_manifest.py --delete-old-corpus --manifest C:\tmp\sakumon_legacy_tex_manifest.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import dotenv_values


sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = Path(r"C:\tmp\sakumon_legacy_tex_manifest.jsonl")
LEGACY_GENERATION = -2

UNIVERSITIES = {
    "01_tokyo": ("東京大学", "東大"),
    "02_kyoto": ("京都大学", "京大"),
    "03_hokudai": ("北海道大学", "北大"),
    "04_tohoku": ("東北大学", "東北大"),
    "05_nagoya": ("名古屋大学", "名大"),
    "06_osaka": ("大阪大学", "阪大"),
    "07_kyushu": ("九州大学", "九大"),
    "08_titech": ("東京工業大学", "東工大"),
}

TOPIC_LABELS = {
    "calculus": "微積分",
    "algebra": "代数",
    "geometry": "幾何",
    "number_theory": "整数",
    "probability": "確率",
    "combinatorics": "組合せ",
    "inequality": "不等式",
    "sequence": "数列",
    "complex": "複素数",
    "polynomial": "多項式",
    "trigonometry": "三角関数",
    "integral": "積分",
    "recurrence": "漸化式",
    "matrix": "行列",
}

TOPIC_RULES: list[tuple[str, list[str]]] = [
    ("probability", ["確率", "サイコロ", "さいころ", "くじ", "袋", "玉を", "コイン", "硬貨"]),
    ("number_theory", ["整数", "自然数", "素数", "約数", "倍数", "余り", "合同", "割り切", "\\pmod", "mod"]),
    ("sequence", ["数列", "漸化式", "等差", "等比", "\\sum", "Σ"]),
    ("complex", ["複素", "虚数", "実部", "虚部", "絶対値", "arg"]),
    ("trigonometry", ["\\sin", "\\cos", "\\tan", "三角関数", "正弦", "余弦"]),
    ("integral", ["積分", "\\int", "面積を求めよ", "体積を求めよ"]),
    ("calculus", ["極限", "\\lim", "微分", "導関数", "接線", "曲線", "最大値", "最小値"]),
    ("matrix", ["行列", "固有値", "逆行列"]),
    ("geometry", ["三角形", "\\triangle", "円", "球", "直線", "平面", "角", "面積", "体積", "図示", "軌跡", "ベクトル"]),
    ("combinatorics", ["場合の数", "組合せ", "組み合わせ", "順列", "通り", "個の", "塗り分け"]),
    ("inequality", ["不等式", "証明せよ", "示せ", "\\le", "\\ge"]),
    ("polynomial", ["多項式", "方程式", "因数", "解と係数", "根"]),
]

TAG_RULES: list[tuple[str, list[str]]] = [
    ("極限", ["極限", "\\lim"]),
    ("微分", ["微分", "導関数", "接線"]),
    ("積分", ["積分", "\\int"]),
    ("面積", ["面積"]),
    ("体積", ["体積"]),
    ("最大最小", ["最大", "最小"]),
    ("軌跡・領域", ["軌跡", "領域", "範囲", "図示"]),
    ("図形", ["三角形", "\\triangle", "円", "球", "角", "直線", "平面"]),
    ("ベクトル", ["ベクトル"]),
    ("数列", ["数列", "漸化式", "\\sum", "Σ"]),
    ("整数", ["整数", "自然数", "素数", "約数", "倍数", "余り", "合同"]),
    ("確率", ["確率", "サイコロ", "くじ", "袋", "玉を"]),
    ("場合の数", ["場合の数", "組合せ", "組み合わせ", "順列", "通り"]),
    ("複素数", ["複素", "虚数"]),
    ("三角関数", ["\\sin", "\\cos", "\\tan", "三角関数"]),
    ("多項式", ["多項式", "因数", "根"]),
    ("方程式", ["方程式", "連立"]),
    ("不等式", ["不等式", "\\le", "\\ge"]),
    ("証明", ["証明せよ", "示せ"]),
    ("行列", ["行列", "固有値", "逆行列"]),
]


def load_env() -> tuple[str, str]:
    env = {**dotenv_values(ROOT / ".env.local"), **os.environ}
    url = (env.get("NEXT_PUBLIC_SUPABASE_URL") or "").rstrip("/")
    key = env.get("SUPABASE_SERVICE_KEY") or ""
    if not url or not key:
        raise SystemExit("NEXT_PUBLIC_SUPABASE_URL / SUPABASE_SERVICE_KEY が .env.local に必要です")
    return url, key


def request_json(
    method: str,
    base_url: str,
    key: str,
    path: str,
    payload: Any | None = None,
    prefer: str | None = None,
    timeout: int = 60,
) -> tuple[int, str | None, Any]:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
    }
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if prefer:
        headers["Prefer"] = prefer

    req = urllib.request.Request(f"{base_url}{path}", data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            body = res.read().decode("utf-8", errors="replace")
            parsed = json.loads(body) if body else None
            return res.status, res.headers.get("Content-Range"), parsed
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} failed: HTTP {exc.code} {body}") from exc


def rest_count(base_url: str, key: str, table: str, query: str = "") -> int:
    path = f"/rest/v1/{table}?select=id{query}"
    status, content_range, _ = request_json(
        "GET",
        base_url,
        key,
        path,
        prefer="count=exact",
        timeout=30,
    )
    if status == 200 and content_range == "*/0":
        return 0
    if not content_range or "/" not in content_range:
        raise RuntimeError(f"count failed for {table}{query}: Content-Range={content_range}")
    return int(content_range.rsplit("/", 1)[1])


def fetch_ids(base_url: str, key: str, table: str, query: str) -> list[str]:
    ids: list[str] = []
    start = 0
    step = 1000
    while True:
        range_query = f"{query}&limit={step}&offset={start}"
        _, _, rows = request_json("GET", base_url, key, f"/rest/v1/{table}?select=id{range_query}", timeout=60)
        batch = rows or []
        ids.extend(str(row["id"]) for row in batch)
        if len(batch) < step:
            return ids
        start += step


def delete_old_corpus(base_url: str, key: str) -> dict[str, int]:
    old_ids = fetch_ids(base_url, key, "problems", "&generation=eq.-1")
    if not old_ids:
        return {"old_problem_ids": 0, "ratings_deleted_chunks": 0, "problems_deleted": 0}

    rating_chunks = 0
    for chunk in chunks(old_ids, 100):
        encoded = ",".join(urllib.parse.quote(problem_id, safe="") for problem_id in chunk)
        request_json(
            "DELETE",
            base_url,
            key,
            f"/rest/v1/ratings?problem_id=in.({encoded})",
            prefer="return=minimal",
            timeout=60,
        )
        rating_chunks += 1

    before = rest_count(base_url, key, "problems", "&generation=eq.-1")
    request_json(
        "DELETE",
        base_url,
        key,
        "/rest/v1/problems?generation=eq.-1",
        prefer="return=minimal",
        timeout=120,
    )
    after = rest_count(base_url, key, "problems", "&generation=eq.-1")
    return {
        "old_problem_ids": len(old_ids),
        "ratings_deleted_chunks": rating_chunks,
        "problems_deleted": before - after,
    }


def chunks(items: list[Any], size: int) -> list[list[Any]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def contains_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)


def classify_topic(statement: str) -> str:
    for topic, needles in TOPIC_RULES:
        if contains_any(statement, needles):
            return topic
    return "algebra"


def infer_tags(statement: str, topic: str) -> list[str]:
    tags = [label for label, needles in TAG_RULES if contains_any(statement, needles)]
    topic_label = TOPIC_LABELS.get(topic)
    if topic_label and topic_label not in tags:
        tags.insert(0, topic_label)
    if not tags:
        tags = ["入試数学", topic_label or "数学"]
    if "入試数学" not in tags:
        tags.append("入試数学")
    deduped: list[str] = []
    for tag in tags:
        if tag not in deduped:
            deduped.append(tag)
    return deduped[:6]


def infer_difficulty(record: dict[str, Any], statement: str, topic: str, tags: list[str]) -> int:
    collection = str(record.get("collection") or "")
    base = 7 if collection in {"01_tokyo", "02_kyoto", "08_titech"} else 6
    if topic in {"number_theory", "geometry", "integral", "complex"}:
        base += 1
    if any(tag in tags for tag in ["証明", "最大最小", "軌跡・領域"]):
        base += 1
    if len(statement) > 450:
        base += 1
    if len(statement) < 130:
        base -= 1
    return max(3, min(10, base))


def difficulty_letter(difficulty10: int) -> str:
    if difficulty10 >= 9:
        return "A"
    if difficulty10 >= 7:
        return "B"
    if difficulty10 >= 4:
        return "C"
    return "D"


def make_feature(university: str, year: str | None, topic: str, tags: list[str]) -> str:
    source = f"{university} {year}年" if year else university
    topic_label = TOPIC_LABELS.get(topic, topic)
    tag_text = "・".join(tags[:3])
    return f"{source}の過去問TeXから取り込んだ{topic_label}問題。{tag_text}を軸に、条件整理と解法選択が問われる。"


def row_from_record(record: dict[str, Any], imported_at: str) -> dict[str, Any]:
    statement = str(record["body_tex"]).strip()
    collection = str(record.get("collection") or "")
    university, short_name = UNIVERSITIES.get(collection, (collection, collection))
    year = str(record.get("year") or "") or None
    topic = classify_topic(statement)
    tags = infer_tags(statement, topic)
    difficulty10 = infer_difficulty(record, statement, topic, tags)
    points = 20 + max(0, difficulty10 - 5) * 5
    title_parts = [short_name]
    if year:
        title_parts.append(f"{year}年")
    if record.get("problem_no"):
        title_parts.append(f"第{record['problem_no']}問")
    title = " ".join(title_parts)
    features = make_feature(university, year, topic, tags)

    meta = {
        "title": title,
        "tags": tags,
        "features": features,
        "points": points,
        "difficulty10": difficulty10,
        "source_kind": "legacy_exam_tex_archive",
        "archive": record.get("archive"),
        "collection": collection,
        "university": university,
        "university_short": short_name,
        "year": year,
        "problem_no": record.get("problem_no"),
        "tex_entry": record.get("entry"),
        "pdf_entry": record.get("pdf_entry"),
        "dvi_entry": record.get("dvi_entry"),
        "graphics": record.get("graphics") or [],
        "encoding": record.get("encoding"),
        "body_source": record.get("body_source"),
        "imported_at": imported_at,
        "enrichment_method": "heuristic_tex_keywords_v1",
    }

    numeric_score = float(difficulty10)
    entry = str(record.get("entry") or "")
    entry_hash = hashlib.sha1(entry.encode("utf-8")).hexdigest()[:16]
    problem_id = f"legacy_exam:{collection}:{entry_hash}"
    return {
        "id": problem_id,
        "topic_a": topic,
        "topic_b": None,
        "variation": 0,
        "statement": statement,
        "answer": None,
        "difficulty": difficulty_letter(difficulty10),
        "solution": None,
        "surprise": min(10.0, numeric_score),
        "minimality": 6.0,
        "connection": 6.5 if len(tags) >= 3 else 5.5,
        "inevitability": 6.0,
        "diff_cal": numeric_score,
        "total": numeric_score,
        "inspiration": features,
        "meta": json.dumps(meta, ensure_ascii=False),
        "generation": LEGACY_GENERATION,
        "parent_ids": [],
        "source_file": entry,
    }


def load_rows(manifest: Path) -> list[dict[str, Any]]:
    imported_at = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    with manifest.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            record = json.loads(line)
            if not str(record.get("body_tex") or "").strip():
                continue
            row = row_from_record(record, imported_at)
            if row["id"] in seen:
                raise RuntimeError(f"duplicate generated id: {row['id']}")
            seen.add(row["id"])
            rows.append(row)
    return rows


def upsert_table(base_url: str, key: str, table: str, rows: list[dict[str, Any]], batch_size: int) -> int:
    written = 0
    for index, batch in enumerate(chunks(rows, batch_size), 1):
        request_json(
            "POST",
            base_url,
            key,
            f"/rest/v1/{table}?on_conflict={'problem_id' if table == 'ratings' else 'id'}",
            payload=batch,
            prefer="resolution=merge-duplicates,return=minimal",
            timeout=120,
        )
        written += len(batch)
        if index % 10 == 0:
            print(f"  {table}: {written}/{len(rows)}")
        time.sleep(0.05)
    return written


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--delete-old-corpus", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument(
        "--create-ratings",
        action="store_true",
        help="Also create pending ratings. Use only when ratings has a unique problem_id constraint.",
    )
    args = parser.parse_args()

    manifest = args.manifest.expanduser().resolve()
    if not manifest.exists():
        raise SystemExit(f"manifest not found: {manifest}")

    rows = load_rows(manifest)
    topics = Counter(str(row["topic_a"]) for row in rows)
    difficulties = Counter(str(row["difficulty"]) for row in rows)
    print(f"manifest={manifest}")
    print(f"prepared_rows={len(rows)} generation={LEGACY_GENERATION}")
    print(f"topics={dict(topics.most_common())}")
    print(f"difficulties={dict(sorted(difficulties.items()))}")
    print("sample:")
    for row in rows[:3]:
        meta = json.loads(str(row["meta"]))
        print(f"  {row['id']} {row['topic_a']} {row['difficulty']} {meta['title']} tags={meta['tags']}")

    if args.dry_run:
        return

    base_url, key = load_env()
    before_all = rest_count(base_url, key, "problems")
    before_old = rest_count(base_url, key, "problems", "&generation=eq.-1")
    before_legacy = rest_count(base_url, key, "problems", f"&generation=eq.{LEGACY_GENERATION}")
    print(f"before: all={before_all} old_generation_-1={before_old} legacy_generation_{LEGACY_GENERATION}={before_legacy}")

    if args.delete_old_corpus:
        deleted = delete_old_corpus(base_url, key)
        print(f"deleted_old_corpus={deleted}")

    problem_count = upsert_table(base_url, key, "problems", rows, max(1, args.batch_size))
    rating_count = 0
    if args.create_ratings:
        rating_rows = [{"problem_id": row["id"], "status": "pending", "x_posted": False} for row in rows]
        rating_count = upsert_table(base_url, key, "ratings", rating_rows, max(1, args.batch_size))
    else:
        print("ratings: skipped (the app treats missing ratings as pending)")

    after_all = rest_count(base_url, key, "problems")
    after_old = rest_count(base_url, key, "problems", "&generation=eq.-1")
    after_legacy = rest_count(base_url, key, "problems", f"&generation=eq.{LEGACY_GENERATION}")
    print(
        "done: "
        f"problems_upserted={problem_count} ratings_upserted={rating_count} "
        f"after_all={after_all} old_generation_-1={after_old} "
        f"legacy_generation_{LEGACY_GENERATION}={after_legacy}"
    )


if __name__ == "__main__":
    main()
