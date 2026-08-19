"""World-novelty & difficulty assessment plumbing for MathOS.

Claude's role is NOT to author problems. This module is a *connection*: it lets
MathOS's own generators be judged objectively — is a generated problem actually
new to the world, and is it actually hard?

"New to the world" = low surface + structural overlap with the reference
corpora (jukenmath.net, MathNet olympiad set, the self-authored 全問題.tex set,
previously generated batches).

"Hard" is scored from objective, statement-level signals rather than taste:

* concept-fusion breadth (how many distinct mathematical concept families the
  statement combines),
* unusual-pair bonus (fusions that textbooks almost never combine — trig×floor,
  trig×abs, prime×geometry, …),
* surface-brevity vs conceptual-load (the 京大 hallmark: a short statement that
  hides several structural layers),
* answer non-obviousness (the answer's form is not syntactically predictable
  from the statement).

None of these need a human's "sense"; they are computed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

try:
    from math_os_prototype.jukenmath_full_audit import (
        canonical_surface,
        jaccard,
        surface_ngrams,
    )
except ImportError:  # pragma: no cover
    from jukenmath_full_audit import canonical_surface, jaccard, surface_ngrams


ROOT = Path(__file__).resolve().parent
MATHNET_PARQUET = Path(
    os.environ.get(
        "MATHOS_MATHNET_PARQUET",
        "C:/Users/81808/.openclaw/workspace/memory/mathnet/data/all/"
        "train-00000-of-00001.parquet",
    )
)
SELF_CORPUS = ROOT / "problem_synthesis" / "all_problems_selfauthored81.jsonl"
NOVELTY_SURFACE_THRESHOLD = 0.60


# ---------------------------------------------------------------------------
# Objective difficulty vocabulary
# ---------------------------------------------------------------------------
CONCEPT_PATTERNS: dict[str, str] = {
    "integral": r"\\int|積分|∫",
    "derivative": r"\\frac\{d|微分|導関数",
    "limit": r"\\lim|極限|\\to\s*\\infty|n\\to",
    "floor": r"\\lfloor|\\lceil|床関数|整数部分|\[x\]|ガウス",
    "abs": r"\\left\||絶対値|\\lvert|\|.*\|",
    "trig": r"\\sin|\\cos|\\tan|正弦|余弦|三角",
    "prime": r"素数|prime|\\mathbb\s*F|素因数",
    "modular": r"\\pmod|\\bmod|合同|剰余|mod",
    "gcd": r"\\gcd|最大公約数|互いに素",
    "binomial": r"\\binom|二項|組合せ|\\dbinom",
    "probability": r"確率|期待値|\\operatorname\{E\}|expectation|一様",
    "recurrence": r"a_\{n\+1\}|漸化式|数列",
    "matrix": r"行列|\\det|固有値|determinant|\\begin\{pmatrix\}",
    "roots": r"実根|方程式.*根|解をもつ|\\alpha,\\beta",
    "convex_hull": r"凸包|convex",
    "region": r"通過.*領域|存在範囲|囲まれ|面積|軌跡|包絡",
    "complex": r"複素|虚数|z\^|\\bar z|偏角",
    "polynomial": r"多項式|次式|\\deg|係数",
    "series_sum": r"\\sum|総和|\\displaystyle\\sum",
    "geometry_solid": r"体積|回転体|球|立体",
    "inequality": r"\\le|\\ge|不等式|最大値|最小値",
}
# Pairs textbooks rarely combine — real "ありえない事象" fusion.
UNUSUAL_PAIRS: set[frozenset[str]] = {
    frozenset({"trig", "floor"}),
    frozenset({"trig", "abs"}),
    frozenset({"prime", "region"}),
    frozenset({"prime", "convex_hull"}),
    frozenset({"floor", "prime"}),
    frozenset({"complex", "region"}),
    frozenset({"probability", "region"}),
    frozenset({"matrix", "prime"}),
    frozenset({"recurrence", "matrix"}),
    frozenset({"integral", "floor"}),
    frozenset({"integral", "abs"}),
}


def concepts_in(statement: str) -> set[str]:
    found = set()
    for name, pattern in CONCEPT_PATTERNS.items():
        if re.search(pattern, statement):
            found.add(name)
    return found


def solution_depth(problem: dict[str, Any]) -> float:
    """解法の深さ = 難しさ。答えの値の大小ではなく、解に要する概念数と長さで測る。
    綺麗な答え(極限=2 など)でも、解法が多段なら難問。"""

    solution = problem.get("solution_tex", "") or ""
    if not solution:
        return 0.0
    concepts = len(concepts_in(solution))
    length = len(canonical_surface(solution))
    # 定理・変換の言及(→, より, したがって, 定理名)を段数の代理に。
    steps = len(re.findall(r"より|したがって|よって|定理|公式|変換|置換|→|\\to", solution))
    return concepts + length / 180.0 + 0.6 * steps


def fusion_reward(fusion: int) -> float:
    # 2概念では甘い。3で立ち上がり、5以上で全分野融合として大きく報いる。
    if fusion <= 2:
        return fusion * 0.5
    return 1.0 + (fusion - 2) ** 1.8


# ユーザーの本物の難問176問から較正した特徴(構築・条件・豊かさ)。
# 「計算せよ」型と、「対象を構築し条件を課して問う」型を分ける。
_CONSTRUCT = re.compile(r"定める|定義|とする|とおく|次のように|与えられ|構成")
_CONDITION = re.compile(r"かつ|満たす|ならば|に対して|任意の|存在|相異なる|ちょうど|どんな")
_MATHBLOCK = re.compile(r"\$\$|\\\[|\\begin")


def difficulty(problem: dict[str, Any]) -> dict[str, Any]:
    statement = problem.get("statement_tex", "")
    answer = problem.get("answer_tex", problem.get("answer_exact", ""))
    concepts = concepts_in(statement)
    fusion = len(concepts)
    unusual = ["×".join(sorted(pair)) for pair in UNUSUAL_PAIRS if pair <= concepts]
    surface_len = max(len(canonical_surface(statement)), 1)

    # データ較正した主特徴
    construct = len(_CONSTRUCT.findall(statement))   # 対象の構築
    condition = len(_CONDITION.findall(statement))   # 課された条件
    mathblocks = len(_MATHBLOCK.findall(statement))
    richness = min(surface_len / 50.0, 8.0)          # 短さは加点しない(逆だった)
    depth = solution_depth(problem)

    ans_tokens = set(re.findall(r"[A-Za-z\\]+", answer))
    stmt_tokens = set(re.findall(r"[A-Za-z\\]+", statement))
    overlap = len(ans_tokens & stmt_tokens) / max(len(ans_tokens), 1)
    nonobvious = 1.0 - overlap

    score = (
        2.5 * construct
        + 2.0 * condition
        + 1.0 * min(mathblocks, 6)
        + richness
        + 1.0 * depth
        + 1.0 * len(unusual)
        + 0.5 * fusion
    )
    # 「構築も条件も無く短い」= ただの計算問題 = 教科書
    just_calculation = construct == 0 and condition <= 1 and surface_len < 120

    if just_calculation:
        band = "D_textbook"
    elif score >= 14:
        band = "A_olympiad"
    elif score >= 8:
        band = "B_hard_university"
    elif score >= 4.5:
        band = "C_standard_university"
    else:
        band = "D_textbook"
    return {
        "score": round(score, 2),
        "band": band,
        "concepts": sorted(concepts),
        "fusion": fusion,
        "unusual_fusions": unusual,
        "construct": construct,
        "condition": condition,
        "solution_depth": round(depth, 2),
        "just_calculation": just_calculation,
        "surface_length": surface_len,
        "answer_nonobviousness": round(nonobvious, 2),
    }


# ---------------------------------------------------------------------------
# World corpus + novelty
# ---------------------------------------------------------------------------
CURATION_DBS = (
    Path("C:/Users/81808/.openclaw/workspace/math-dataset/curation.db"),
    Path("C:/Users/81808/.openclaw/workspace/automation/ui/curation.db"),
)
CORPUS_TEX_DIR = Path("C:/Users/81808/.openclaw/workspace/corpus")


CORPUS_SNAPSHOT = ROOT / "problem_synthesis" / "local_hard_corpus.json"


def load_local_hard_corpus() -> list[dict[str, str]]:
    """ユーザー自作の本物の難問（作問ステーションDB・手作りTeX）をローカルから。
    ネット不要。これが最も信頼できる新規性・難易度の基準。

    ローカルの DB / TeX が無い環境（GitHub Actions などクラウド）では、
    リポジトリに同梱したスナップショットへフォールバックする。"""

    import sqlite3

    try:
        from math_os_prototype.difficulty_reference import (
            extract_problem_statement,
            normalize_reference_rows,
        )
    except ImportError:  # pragma: no cover
        from difficulty_reference import (
            extract_problem_statement,
            normalize_reference_rows,
        )

    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for db in CURATION_DBS:
        if not db.exists():
            continue
        try:
            con = sqlite3.connect(str(db))
            for (statement,) in con.execute(
                "select statement from problems where statement is not null"
            ):
                try:
                    s = extract_problem_statement(str(statement))
                except ValueError:
                    continue
                if s and s not in seen:
                    seen.add(s)
                    rows.append({"source": "sakumon_curation", "id": str(len(rows)), "statement": s})
            con.close()
        except Exception:
            continue
    if CORPUS_TEX_DIR.exists():
        for path in CORPUS_TEX_DIR.glob("*.tex"):
            try:
                text = extract_problem_statement(
                    path.read_text(encoding="utf-8", errors="replace")
                )
            except (OSError, ValueError):
                continue
            if text and text not in seen:
                seen.add(text)
                rows.append({"source": "corpus_tex", "id": path.stem, "statement": text})
    if not rows and CORPUS_SNAPSHOT.exists():
        # クラウド実行: 同梱スナップショットを使う
        try:
            payload = json.loads(CORPUS_SNAPSHOT.read_text(encoding="utf-8"))
            rows = normalize_reference_rows(payload.get("problems", []))
        except (OSError, json.JSONDecodeError):
            rows = []
    return rows


def load_world_corpus() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = list(load_local_hard_corpus())
    if MATHNET_PARQUET.exists():
        try:
            import pandas as pd

            frame = pd.read_parquet(MATHNET_PARQUET)
            for i, v in enumerate(frame.get("problem_markdown", []).astype(str)):
                if v and v.lower() != "nan":
                    rows.append({"source": "mathnet", "id": str(i), "statement": v})
        except Exception:
            pass
    if SELF_CORPUS.exists():
        for i, line in enumerate(SELF_CORPUS.read_text(encoding="utf-8").splitlines()):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            s = str(obj.get("statement_tex") or "")
            if s:
                rows.append({"source": "selfauthored", "id": str(i), "statement": s})
    for path in sorted(
        (ROOT / "problem_synthesis").glob("continuous_verified_problem_batch*.json")
    ):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for j, p in enumerate(payload.get("problems", [])):
            s = str(p.get("statement_tex") or "")
            if s:
                rows.append({"source": path.stem, "id": str(j), "statement": s})
    return rows


def load_jukenmath_hashes() -> set[str]:
    """jukenmath audit stores canonical-surface sha256 (not statements). Use it
    for exact-collision detection only."""

    juken = ROOT / "problem_synthesis" / "jukenmath_world.json"
    hashes: set[str] = set()
    if juken.exists():
        try:
            payload = json.loads(juken.read_text(encoding="utf-8"))
            for rec in payload.get("records", []):
                h = rec.get("statement_sha256")
                if h:
                    hashes.add(str(h))
        except (OSError, json.JSONDecodeError):
            pass
    return hashes


@dataclass(frozen=True)
class SurfaceNgramIndex:
    """Exact Jaccard search using an inverted 3-gram index.

    Documents with no shared n-gram have Jaccard score zero, so they cannot
    improve a positive maximum.  The index only removes those provably
    irrelevant comparisons; it does not approximate the score.
    """

    sources: tuple[str, ...]
    grams: tuple[frozenset[str], ...]
    postings: dict[str, tuple[int, ...]]

    @classmethod
    def build(
        cls,
        rows: Sequence[tuple[str, frozenset[str]]],
    ) -> "SurfaceNgramIndex":
        postings: dict[str, list[int]] = defaultdict(list)
        sources: list[str] = []
        grams: list[frozenset[str]] = []
        for document_id, (source, tokens) in enumerate(rows):
            sources.append(source)
            grams.append(tokens)
            for token in tokens:
                postings[token].append(document_id)
        return cls(
            sources=tuple(sources),
            grams=tuple(grams),
            postings={
                token: tuple(document_ids)
                for token, document_ids in postings.items()
            },
        )

    def maximum_jaccard(
        self,
        query: frozenset[str],
    ) -> tuple[float, str | None]:
        intersections: Counter[int] = Counter()
        for token in query:
            intersections.update(self.postings.get(token, ()))
        best = 0.0
        best_source: str | None = None
        for document_id in sorted(intersections):
            intersection = intersections[document_id]
            denominator = (
                len(query) + len(self.grams[document_id]) - intersection
            )
            score = intersection / denominator if denominator else 1.0
            if score > best:
                best = score
                best_source = self.sources[document_id]
        return best, best_source


def world_novelty(
    statement: str,
    world_grams: (
        Sequence[tuple[str, frozenset[str]]] | SurfaceNgramIndex
    ),
    juken_hashes: set[str],
) -> dict[str, Any]:
    from hashlib import sha256

    grams = surface_ngrams(statement)
    if isinstance(world_grams, SurfaceNgramIndex):
        best, best_src = world_grams.maximum_jaccard(grams)
    else:
        best = 0.0
        best_src = None
        for src, other in world_grams:
            score = jaccard(grams, other)
            if score > best:
                best, best_src = score, src
    digest = sha256(canonical_surface(statement).encode("utf-8")).hexdigest()
    exact_juken = digest in juken_hashes
    return {
        "max_surface_jaccard": round(best, 4),
        "closest_source": best_src,
        "exact_jukenmath_collision": exact_juken,
        "world_novel": best < NOVELTY_SURFACE_THRESHOLD and not exact_juken,
    }


def assess_pool(problems: Iterable[dict[str, Any]]) -> dict[str, Any]:
    world = load_world_corpus()
    world_grams = SurfaceNgramIndex.build(
        [(r["source"], surface_ngrams(r["statement"])) for r in world]
    )
    juken_hashes = load_jukenmath_hashes()
    results = []
    for p in problems:
        nov = world_novelty(p.get("statement_tex", ""), world_grams, juken_hashes)
        diff = difficulty(p)
        results.append(
            {
                "candidate_id": p.get("candidate_id"),
                "statement_tex": p.get("statement_tex", "")[:80],
                "world_novel": nov["world_novel"],
                "max_jaccard": nov["max_surface_jaccard"],
                "difficulty_band": diff["band"],
                "difficulty_score": diff["score"],
                "unusual_fusions": diff["unusual_fusions"],
                "concepts": diff["concepts"],
            }
        )
    from collections import Counter

    novel = [r for r in results if r["world_novel"]]
    hard = [r for r in results if r["difficulty_band"] in ("A_olympiad", "B_hard_university")]
    novel_and_hard = [r for r in novel if r["difficulty_band"] in ("A_olympiad", "B_hard_university")]
    return {
        "world_corpus_size": len(world),
        "jukenmath_exact_hashes": len(juken_hashes),
        "assessed": len(results),
        "world_novel": len(novel),
        "hard_or_olympiad": len(hard),
        "world_novel_and_hard": len(novel_and_hard),
        "band_counts": dict(Counter(r["difficulty_band"] for r in results)),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pool", type=Path, required=True, help="pool JSON with a problems[] array")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.pool.read_text(encoding="utf-8"))
    report = assess_pool(payload.get("problems", []))
    if args.output:
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    summary = {k: v for k, v in report.items() if k != "results"}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
