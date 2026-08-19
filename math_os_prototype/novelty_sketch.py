"""Compact MinHash snapshot for corpus screening in GitHub Actions."""

from __future__ import annotations

import argparse
import hashlib
import json
import zlib
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import numpy as np

try:
    from math_os_prototype.jukenmath_full_audit import (
        canonical_surface,
        surface_ngrams,
    )
except ImportError:  # pragma: no cover
    from jukenmath_full_audit import canonical_surface, surface_ngrams


HERE = Path(__file__).resolve().parent
DEFAULT_SNAPSHOT = HERE / "problem_synthesis" / "world_corpus_minhash64.npz"
HASH_COUNT = 64
PRIME = np.uint64(4_294_967_311)
SKETCH_REJECTION_THRESHOLD = 0.45


def _coefficients() -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(20260726)
    a = rng.integers(1, int(PRIME), HASH_COUNT, dtype=np.uint64)
    a |= np.uint64(1)
    b = rng.integers(0, int(PRIME), HASH_COUNT, dtype=np.uint64)
    return a, b


def minhash_signature(text: str) -> np.ndarray:
    grams = surface_ngrams(text)
    if not grams:
        return np.full(HASH_COUNT, np.iinfo(np.uint32).max, dtype=np.uint32)
    base = np.fromiter(
        (zlib.crc32(gram.encode("utf-8")) for gram in grams),
        dtype=np.uint64,
    )
    a, b = _coefficients()
    values = (a[:, None] * base[None, :] + b[:, None]) % PRIME
    return values.min(axis=1).astype(np.uint32)


def build_snapshot(
    records: Iterable[dict[str, str]],
    output: Path = DEFAULT_SNAPSHOT,
) -> dict[str, Any]:
    materialized = list(records)
    signatures = np.empty((len(materialized), HASH_COUNT), dtype=np.uint32)
    exact_hashes = np.empty((len(materialized), 32), dtype=np.uint8)
    source_names = sorted({str(record["source"]) for record in materialized})
    source_index = {name: index for index, name in enumerate(source_names)}
    sources = np.empty(len(materialized), dtype=np.uint16)
    for index, record in enumerate(materialized):
        statement = str(record["statement"])
        signatures[index] = minhash_signature(statement)
        exact_hashes[index] = np.frombuffer(
            hashlib.sha256(
                canonical_surface(statement).encode("utf-8")
            ).digest(),
            dtype=np.uint8,
        )
        sources[index] = source_index[str(record["source"])]
    metadata = {
        "corpus_size": len(materialized),
        "hash_count": HASH_COUNT,
        "source_names": source_names,
        "screening_method": "minhash64_conservative",
        "rejection_threshold": SKETCH_REJECTION_THRESHOLD,
        "scope": "surface 3-gram sketch; not a proof of mathematical novelty",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output,
        signatures=signatures,
        exact_hashes=exact_hashes,
        sources=sources,
        metadata=np.array(json.dumps(metadata, ensure_ascii=False)),
    )
    return metadata


@lru_cache(maxsize=2)
def _load_snapshot(path_text: str) -> dict[str, Any] | None:
    path = Path(path_text)
    if not path.exists():
        return None
    with np.load(path, allow_pickle=False) as payload:
        return {
            "signatures": payload["signatures"],
            "exact_hashes": payload["exact_hashes"],
            "sources": payload["sources"],
            "metadata": json.loads(str(payload["metadata"].item())),
        }


def screen_snapshot(
    statement: str,
    path: Path = DEFAULT_SNAPSHOT,
) -> dict[str, Any] | None:
    snapshot = _load_snapshot(str(path.resolve()))
    if snapshot is None:
        return None
    signature = minhash_signature(statement)
    similarities = (
        snapshot["signatures"] == signature[None, :]
    ).mean(axis=1)
    best_index = int(np.argmax(similarities))
    best = float(similarities[best_index])
    digest = np.frombuffer(
        hashlib.sha256(
            canonical_surface(statement).encode("utf-8")
        ).digest(),
        dtype=np.uint8,
    )
    exact = bool(np.any(np.all(snapshot["exact_hashes"] == digest, axis=1)))
    metadata = snapshot["metadata"]
    source_code = int(snapshot["sources"][best_index])
    source_names = metadata["source_names"]
    return {
        "passed": not exact and best < float(metadata["rejection_threshold"]),
        "corpus_size": int(metadata["corpus_size"]),
        "estimated_maximum_surface_jaccard": round(best, 4),
        "closest_source": source_names[source_code],
        "exact_surface_collision": exact,
        "method": metadata["screening_method"],
        "rejection_threshold": metadata["rejection_threshold"],
        "scope": metadata["scope"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_SNAPSHOT)
    args = parser.parse_args()
    try:
        from math_os_prototype.world_novelty_check import load_world_corpus
    except ImportError:  # pragma: no cover
        from world_novelty_check import load_world_corpus
    metadata = build_snapshot(load_world_corpus(), args.output)
    print(json.dumps(metadata, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
