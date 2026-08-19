"""Memory and retrieval layer for Math OS.

The default path is offline and deterministic. Live Stack Exchange search can
be enabled explicitly by the orchestrator or CLI.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class RetrievalHit:
    source: str
    title: str
    url: str
    score: float
    summary: str
    strategy_hint: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


STRATEGY_MEMORY: list[RetrievalHit] = [
    RetrievalHit(
        source="local_strategy_memory",
        title="Support function containment for convex bodies",
        url="memory://convex/support-function-containment",
        score=0.0,
        summary=(
            "A convex body K is contained in a translated polygon P iff the "
            "support-function inequalities for P's outward normals are feasible."
        ),
        strategy_hint="Use support functions, derive translation-feasible region, then sweep orientations.",
    ),
    RetrievalHit(
        source="local_strategy_memory",
        title="Envelope by parameter elimination",
        url="memory://calculus/envelope-resultant",
        score=0.0,
        summary="For a family F(x,y,t)=0, the envelope satisfies F=0 and dF/dt=0.",
        strategy_hint="Introduce F, eliminate the parameter with a resultant or Reduce.",
    ),
    RetrievalHit(
        source="local_strategy_memory",
        title="Locus by resultant",
        url="memory://algebra/locus-resultant",
        score=0.0,
        summary="For x=f(t), y=g(t), eliminate t from x-f(t)=0 and y-g(t)=0.",
        strategy_hint="Lower parametric equations to elimination constraints.",
    ),
    RetrievalHit(
        source="local_strategy_memory",
        title="Passing region as existential formula",
        url="memory://geometry/passing-region-exists",
        score=0.0,
        summary="A point is in the passing region iff there exists a parameter satisfying the family equation.",
        strategy_hint="Build an existential formula and use quantifier elimination.",
    ),
    RetrievalHit(
        source="local_strategy_memory",
        title="Simulation before proof",
        url="memory://exploration/simulate-guess-verify",
        score=0.0,
        summary="Sample configurations, infer symmetry/boundary candidates, then verify symbolically.",
        strategy_hint="Use numerical geometry to propose invariants and boundary pieces.",
    ),
]


class QueryBuilder:
    def build(self, problem_text: str, parsed_ir: dict[str, Any] | None = None) -> list[str]:
        text = normalize_query_text(problem_text)
        queries: list[str] = []

        if "正方形" in text and "正三角形" in text and "通過領域" in text:
            queries.extend(
                [
                    "moving equilateral triangle contains square swept area",
                    "support function triangle contains square",
                    "convex body contained in translated triangle support function",
                ]
            )
        if "包絡線" in text or "envelope" in text.lower():
            queries.extend(["envelope family of curves parameter elimination", "resultant envelope curve"])
        if "通過領域" in text:
            queries.extend(["passing region locus parameter elimination", "existential quantifier elimination geometry"])
        if "軌跡" in text or "locus" in text.lower():
            queries.extend(["locus parametric equations eliminate parameter", "resultant locus curve"])

        if parsed_ir:
            intent = str(parsed_ir.get("intent", ""))
            domain_ir = parsed_ir.get("domain_ir") or {}
            if "container" in intent:
                queries.append("Minkowski difference containment sweep convex geometry")
            if "geometry_nl_to_dsl_region" in intent:
                queries.append("quantifier elimination passing region")
            if isinstance(domain_ir, dict):
                queries.extend(str(query) for query in domain_ir.get("retrieval_queries", [])[:3])

        if text:
            compact = " ".join(token for token in re.findall(r"[A-Za-z0-9_]+|正方形|正三角形|通過領域|包絡線|軌跡", text)[:12])
            if compact:
                queries.append(compact)

        return dedupe(queries)


class MemoryRetriever:
    def retrieve(self, problem_text: str, parsed_ir: dict[str, Any] | None = None, limit: int = 5) -> list[RetrievalHit]:
        query_text = normalize_query_text(problem_text).lower()
        intent = str((parsed_ir or {}).get("intent", "")).lower()
        hits = []
        for item in STRATEGY_MEMORY:
            score = score_memory_item(query_text, intent, item)
            if score > 0:
                hit = RetrievalHit(**{**item.to_dict(), "score": score})
                hits.append(hit)
        return sorted(hits, key=lambda hit: hit.score, reverse=True)[:limit]


class StackExchangeRetriever:
    def __init__(self, site: str = "math", timeout_seconds: int = 10):
        self.site = site
        self.timeout_seconds = timeout_seconds

    def search(self, query: str, pagesize: int = 3) -> list[RetrievalHit]:
        params = urllib.parse.urlencode(
            {
                "order": "desc",
                "sort": "relevance",
                "q": query,
                "site": self.site,
                "pagesize": str(pagesize),
                "filter": "!nKzQURF6Y5",
            }
        )
        url = f"https://api.stackexchange.com/2.3/search/advanced?{params}"
        request = urllib.request.Request(url, headers={"User-Agent": "math-os-prototype/0.1"})
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))

        results = []
        for item in payload.get("items", []):
            title = strip_html(item.get("title", ""))
            link = item.get("link", "")
            score = float(item.get("score", 0))
            tags = ", ".join(item.get("tags", []))
            results.append(
                RetrievalHit(
                    source=f"stackexchange:{self.site}",
                    title=title,
                    url=link,
                    score=score,
                    summary=f"Tags: {tags}",
                    strategy_hint="Inspect similar accepted/high-score answers and adapt only verified method steps.",
                )
            )
        return results


class HybridRetriever:
    def __init__(self, live_search: bool = False):
        self.live_search = live_search
        self.query_builder = QueryBuilder()
        self.memory = MemoryRetriever()
        self.stackexchange = StackExchangeRetriever()

    def retrieve(
        self,
        problem_text: str,
        parsed_ir: dict[str, Any] | None = None,
        limit: int = 5,
    ) -> dict[str, Any]:
        queries = self.query_builder.build(problem_text, parsed_ir)
        hits = self.memory.retrieve(problem_text, parsed_ir, limit=limit)
        live_hits: list[RetrievalHit] = []
        errors = []
        if self.live_search:
            for query in queries[:3]:
                try:
                    live_hits.extend(self.stackexchange.search(query, pagesize=2))
                except Exception as exc:  # pragma: no cover - depends on network/API.
                    errors.append({"query": query, "error": str(exc)})
        all_hits = sorted(hits + live_hits, key=lambda hit: hit.score, reverse=True)[:limit]
        return {
            "queries": queries,
            "memory_hits": [hit.to_dict() for hit in hits],
            "live_hits": [hit.to_dict() for hit in live_hits[:limit]],
            "hits": [hit.to_dict() for hit in all_hits],
            "live_search": self.live_search,
            "errors": errors,
        }


def score_memory_item(query_text: str, intent: str, item: RetrievalHit) -> float:
    haystack = f"{item.title} {item.summary} {item.strategy_hint}".lower()
    score = 0.0
    for token in re.findall(r"[a-zA-Z]+|正方形|正三角形|通過領域|包絡線|軌跡", query_text):
        if token.lower() in haystack:
            score += 1.0
    if "container" in intent and "support" in haystack:
        score += 5.0
    if "envelope" in intent and "envelope" in haystack:
        score += 5.0
    if "locus" in intent and "locus" in haystack:
        score += 5.0
    if "region" in intent and ("passing" in haystack or "existential" in haystack):
        score += 5.0
    if "simulate" in haystack:
        score += 0.5
    return score


def normalize_query_text(text: str) -> str:
    return (
        text.replace("\\sqrt", " sqrt")
        .replace("\\in", " in ")
        .replace("\\mathbb", " mathbb ")
        .replace("{", " ")
        .replace("}", " ")
        .replace("$", " ")
    )


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


def dedupe(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result
