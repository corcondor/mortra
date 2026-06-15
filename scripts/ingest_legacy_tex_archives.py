r"""
Inspect old pLaTeX problem archives and emit a normalized JSONL manifest.

The downloaded university bundles are 7z archives containing Shift-JIS/cp932
TeX, PDFs, DVI files, and figures. This script treats TeX as the canonical
source and keeps PDFs/JPGs as verification assets.

Usage:
  python scripts/ingest_legacy_tex_archives.py --output C:\tmp\manifest.jsonl ^
    --summary C:\tmp\summary.json C:\Users\me\Downloads\01_tokyo-20260321.7z
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterable


sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ENCODINGS = ("utf-8", "cp932", "shift_jis", "euc_jp")


def run_tar(args: list[str]) -> bytes:
    result = subprocess.run(
        ["tar", *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"tar failed: {' '.join(args)}\n{stderr}")
    return result.stdout


def list_entries(archive: Path) -> list[str]:
    raw = run_tar(["-tf", str(archive)])
    return [line for line in raw.decode("utf-8", errors="replace").splitlines() if line]


def read_entry(archive: Path, entry: str) -> bytes:
    return run_tar(["-xOf", str(archive), entry])


def extract_entries(archive: Path, destination: Path, entries: list[str]) -> None:
    if not entries:
        return
    list_file = destination / "__tex_entries.txt"
    list_file.write_text("\n".join(entries) + "\n", encoding="utf-8")
    run_tar(["-xf", str(archive), "-C", str(destination), "-T", str(list_file)])


def extracted_path(root: Path, entry: str) -> Path:
    return root.joinpath(*PurePosixPath(entry).parts)


def decode_tex(raw: bytes) -> tuple[str, str]:
    for encoding in ENCODINGS:
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return raw.decode("cp932", errors="replace"), "cp932-replace"


def extension_of(entry: str) -> str:
    suffix = PurePosixPath(entry).suffix.lower()
    return suffix if suffix else "<dir>" if entry.endswith("/") else "<none>"


def strip_tex_comments(text: str) -> str:
    # Remove unescaped comments while preserving percent signs in commands/data.
    return re.sub(r"(?<!\\)%.*", "", text)


def find_graphics(text: str, entry: str, entries_set: set[str]) -> list[dict[str, object]]:
    base_dir = PurePosixPath(entry).parent
    graphics = []
    for match in re.finditer(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", text):
        name = match.group(1).strip()
        candidate = str(base_dir / name).replace("\\", "/")
        graphics.append(
            {
                "file": name,
                "entry": candidate,
                "exists": candidate in entries_set,
            }
        )
    return graphics


def extract_body(text: str) -> tuple[str, str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = strip_tex_comments(normalized)

    flush = re.search(
        r"\\begin\{flushleft\}(.*?)\\end\{flushleft\}",
        normalized,
        flags=re.DOTALL,
    )
    if flush:
        return flush.group(1), "flushleft"

    document = re.search(
        r"\\begin\{document\}(.*?)\\end\{document\}",
        normalized,
        flags=re.DOTALL,
    )
    if document:
        body = re.sub(
            r"\\includegraphics(?:\[[^\]]*\])?\{[^}]+\}",
            "",
            document.group(1),
        )
        return body, "document"

    return normalized, "raw"


def clean_body(body: str) -> tuple[str, str | None]:
    body = body.strip()
    problem_no = None

    number = re.match(r"^\s*\{\\(?:Huge|huge|LARGE|Large|large)\s+([^}]+)\}\s*", body)
    if number:
        problem_no = number.group(1).strip()
        body = body[number.end() :]

    body = re.sub(r"\\setlength\{\\baselineskip\}\{[^}]+\}", "", body)
    body = re.sub(r"\\(?:noindent|medskip|smallskip|bigskip|newpage|par)\b", " ", body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip(), problem_no


def record_for_tex(
    archive: Path,
    entry: str,
    entries_set: set[str],
    include_raw: bool,
    extracted_root: Path | None = None,
) -> tuple[dict[str, object], str]:
    if extracted_root:
        raw = extracted_path(extracted_root, entry).read_bytes()
    else:
        raw = read_entry(archive, entry)
    text, encoding = decode_tex(raw)
    body, body_source = extract_body(text)
    body_tex, problem_no = clean_body(body)
    graphics = find_graphics(text, entry, entries_set)

    posix = PurePosixPath(entry)
    parts = posix.parts
    year = next((part for part in parts if re.fullmatch(r"\d{4}", part)), None)
    peer_entries = entries_set
    stem = posix.with_suffix("")
    pdf_entry = str(stem.with_suffix(".pdf"))
    dvi_entry = str(stem.with_suffix(".dvi"))

    record: dict[str, object] = {
        "archive": archive.name,
        "collection": parts[0] if parts else archive.stem,
        "entry": entry,
        "year": year,
        "problem_id": posix.stem,
        "problem_no": problem_no,
        "encoding": encoding,
        "body_source": body_source,
        "body_tex": body_tex,
        "body_chars": len(body_tex),
        "has_graphics": bool(graphics),
        "graphics": graphics,
        "pdf_entry": pdf_entry if pdf_entry in peer_entries else None,
        "dvi_entry": dvi_entry if dvi_entry in peer_entries else None,
    }
    if include_raw:
        record["raw_tex"] = text

    return record, encoding


def iter_tex_entries(entries: Iterable[str]) -> list[str]:
    return sorted(e for e in entries if e.lower().endswith(".tex"))


def inspect_archives(
    archives: list[Path],
    output: Path,
    summary_path: Path | None,
    limit: int,
    include_raw: bool,
) -> dict[str, object]:
    output.parent.mkdir(parents=True, exist_ok=True)

    summary: dict[str, object] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "output": str(output),
        "archives": {},
        "totals": {
            "archives": len(archives),
            "entries": 0,
            "tex": 0,
            "records": 0,
            "empty_body": 0,
            "with_graphics": 0,
            "missing_graphics": 0,
            "encodings": {},
            "body_sources": {},
        },
    }

    total_encodings: Counter[str] = Counter()
    total_body_sources: Counter[str] = Counter()

    with output.open("w", encoding="utf-8", newline="\n") as out:
        for archive in archives:
            entries = list_entries(archive)
            entries_set = set(entries)
            tex_entries = iter_tex_entries(entries)
            if limit:
                tex_entries = tex_entries[:limit]

            ext_counts = Counter(extension_of(entry) for entry in entries)
            archive_summary: dict[str, object] = {
                "path": str(archive),
                "entries": len(entries),
                "extensions": dict(sorted(ext_counts.items())),
                "tex_seen": len(tex_entries),
                "records": 0,
                "empty_body": 0,
                "with_graphics": 0,
                "missing_graphics": 0,
                "encodings": {},
                "body_sources": {},
            }
            archive_encodings: Counter[str] = Counter()
            archive_body_sources: Counter[str] = Counter()

            with tempfile.TemporaryDirectory(prefix=f"sakumon_{archive.stem}_") as temp_dir:
                extracted_root = Path(temp_dir)
                extract_entries(archive, extracted_root, tex_entries)

                for entry in tex_entries:
                    record, encoding = record_for_tex(
                        archive,
                        entry,
                        entries_set,
                        include_raw,
                        extracted_root=extracted_root,
                    )
                    out.write(json.dumps(record, ensure_ascii=False) + "\n")

                    graphics = record["graphics"]
                    missing_graphics = sum(1 for g in graphics if not g.get("exists"))  # type: ignore[union-attr]
                    body_source = str(record["body_source"])

                    archive_summary["records"] = int(archive_summary["records"]) + 1
                    archive_summary["empty_body"] = int(archive_summary["empty_body"]) + (1 if not record["body_tex"] else 0)
                    archive_summary["with_graphics"] = int(archive_summary["with_graphics"]) + (1 if record["has_graphics"] else 0)
                    archive_summary["missing_graphics"] = int(archive_summary["missing_graphics"]) + missing_graphics
                    archive_encodings[encoding] += 1
                    archive_body_sources[body_source] += 1

            archive_summary["encodings"] = dict(archive_encodings)
            archive_summary["body_sources"] = dict(archive_body_sources)
            summary["archives"][archive.name] = archive_summary  # type: ignore[index]

            totals = summary["totals"]  # type: ignore[assignment]
            totals["entries"] = int(totals["entries"]) + len(entries)  # type: ignore[index]
            totals["tex"] = int(totals["tex"]) + len(tex_entries)  # type: ignore[index]
            totals["records"] = int(totals["records"]) + int(archive_summary["records"])  # type: ignore[index]
            totals["empty_body"] = int(totals["empty_body"]) + int(archive_summary["empty_body"])  # type: ignore[index]
            totals["with_graphics"] = int(totals["with_graphics"]) + int(archive_summary["with_graphics"])  # type: ignore[index]
            totals["missing_graphics"] = int(totals["missing_graphics"]) + int(archive_summary["missing_graphics"])  # type: ignore[index]
            total_encodings.update(archive_encodings)
            total_body_sources.update(archive_body_sources)

    totals = summary["totals"]  # type: ignore[assignment]
    totals["encodings"] = dict(total_encodings)  # type: ignore[index]
    totals["body_sources"] = dict(total_body_sources)  # type: ignore[index]

    if summary_path:
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archives", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--limit", type=int, default=0, help="Per-archive TeX limit. 0 means all.")
    parser.add_argument("--include-raw", action="store_true")
    args = parser.parse_args()

    archives = [path.expanduser().resolve() for path in args.archives]
    missing = [str(path) for path in archives if not path.exists()]
    if missing:
        raise SystemExit(f"Archive not found: {', '.join(missing)}")

    summary = inspect_archives(
        archives=archives,
        output=args.output.expanduser().resolve(),
        summary_path=args.summary.expanduser().resolve() if args.summary else None,
        limit=max(0, args.limit),
        include_raw=args.include_raw,
    )
    totals = summary["totals"]
    print(
        "OK "
        f"archives={totals['archives']} tex={totals['tex']} "
        f"records={totals['records']} empty_body={totals['empty_body']} "
        f"with_graphics={totals['with_graphics']} missing_graphics={totals['missing_graphics']}"
    )
    print(f"encodings={totals['encodings']}")
    print(f"body_sources={totals['body_sources']}")


if __name__ == "__main__":
    main()
