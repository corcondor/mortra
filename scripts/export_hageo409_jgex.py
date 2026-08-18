"""Export the MIT-licensed HAGeo-409 AlphaGeometry column as JGEX text."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

import pandas as pd


_CLAUSE = re.compile(r"^\s*(?P<outputs>[A-Za-z0-9_@.\-\s]+?)\s*=\s*(?P<body>.+?)\s*$")


def lower_known_dialect_constructions(formulation: str) -> str:
    """Lower constructor aliases by typed meaning, never by problem ID."""

    setup, separator, goal = formulation.partition("?")
    lowered: list[str] = []
    for raw_clause in setup.split(";"):
        clause = raw_clause.strip()
        if not clause:
            continue
        clause = re.sub(r"\beq_trapezoid\b", "iso_trapezoid", clause)
        match = _CLAUSE.match(clause)
        if match is None:
            lowered.append(clause)
            continue
        outputs = match.group("outputs").split()
        body = match.group("body").split()
        if len(body) == 4 and body[0] == "centroid" and len(outputs) in {1, 4}:
            if len(outputs) == 1:
                point = outputs[0]
                hidden = tuple(
                    f"{point}__median{index}" for index in range(1, 4)
                )
                centroid_outputs = (*hidden, point)
            else:
                centroid_outputs = tuple(outputs)
            lowered.append(
                f"{' '.join(centroid_outputs)} = centroid "
                f"{' '.join((*centroid_outputs, *body[1:]))}"
            )
            continue
        if len(outputs) == 4 and len(body) == 4 and body[0] == "ninepoints":
            first, second, third, center = outputs
            a, b, c = body[1:]
            lowered.extend(
                (
                    f"{first} = midpoint {b} {c}",
                    f"{second} = midpoint {c} {a}",
                    f"{third} = midpoint {a} {b}",
                    f"{center} = circumcenter {first} {second} {third}",
                )
            )
            continue
        lowered.append(clause)
    normalized_setup = "; ".join(lowered)
    return (
        f"{normalized_setup} ? {' '.join(goal.split())}"
        if separator
        else normalized_setup
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parquet", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()

    frame = pd.read_parquet(args.parquet.resolve())
    required = {
        "Problem_ID",
        "Natural_Language",
        "AlphaGeometry",
        "HAGeo",
        "Difficulty_Score",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"missing HAGeo-409 columns: {missing}")

    identifiers = [str(value).strip() for value in frame["Problem_ID"]]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("HAGeo-409 contains duplicate Problem_ID values")
    lines: list[str] = []
    for identifier, formulation in zip(
        identifiers,
        frame["AlphaGeometry"],
        strict=True,
    ):
        text = lower_known_dialect_constructions(
            " ".join(str(formulation).strip().split())
        )
        if not identifier or "?" not in text:
            raise ValueError(f"invalid HAGeo-409 row: {identifier!r}")
        lines.extend((identifier, text))
    payload = "\n".join(lines) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload, encoding="utf-8")

    difficulty = pd.to_numeric(frame["Difficulty_Score"], errors="coerce")
    manifest = {
        "dataset": "HAGeo-409",
        "license": "MIT",
        "source": "https://huggingface.co/datasets/HAGeo-IMO/HAGeo-409",
        "row_count": len(frame),
        "unique_problem_ids": len(set(identifiers)),
        "difficulty": {
            "minimum": float(difficulty.min()),
            "maximum": float(difficulty.max()),
            "mean": float(difficulty.mean()),
        },
        "parquet_sha256": hashlib.sha256(args.parquet.read_bytes()).hexdigest(),
        "jgex_sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "uses_external_llm": False,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
