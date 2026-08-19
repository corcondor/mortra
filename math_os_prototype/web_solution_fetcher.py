"""Fetch candidate solution text from web retrieval hits.

Currently this focuses on Math StackExchange via the public StackExchange API.
The fetcher returns raw question/answer text; it does not trust answers.
Downstream parsers and verifiers must validate reusable steps.
"""

from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class WebAnswer:
    answer_id: int
    score: int
    is_accepted: bool
    body_text: str
    link: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WebSolution:
    source: str
    question_id: int
    title: str
    url: str
    question_text: str
    answers: list[WebAnswer] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class WebSolutionFetcher:
    def __init__(self, site: str = "math", timeout_seconds: int = 12):
        self.site = site
        self.timeout_seconds = timeout_seconds

    def fetch_from_hits(self, hits: list[dict[str, Any]], limit: int = 3) -> list[WebSolution]:
        solutions: list[WebSolution] = []
        seen: set[int] = set()
        for hit in hits:
            url = str(hit.get("url") or "")
            question_id = extract_stackexchange_question_id(url)
            if question_id is None or question_id in seen:
                continue
            seen.add(question_id)
            solutions.append(self.fetch_stackexchange_question(question_id, url))
            if len(solutions) >= limit:
                break
        return solutions

    def fetch_stackexchange_question(self, question_id: int, url: str = "") -> WebSolution:
        try:
            question = self._api_get(
                f"questions/{question_id}",
                {
                    "site": self.site,
                    "filter": "withbody",
                },
            )
            question_items = question.get("items", [])
            if not question_items:
                return WebSolution(
                    source=f"stackexchange:{self.site}",
                    question_id=question_id,
                    title="",
                    url=url,
                    question_text="",
                    error="question not found",
                )
            item = question_items[0]
            answers = self.fetch_stackexchange_answers(question_id)
            return WebSolution(
                source=f"stackexchange:{self.site}",
                question_id=question_id,
                title=strip_html(item.get("title", "")),
                url=item.get("link") or url,
                question_text=strip_html(item.get("body", "")),
                answers=answers,
            )
        except Exception as exc:  # pragma: no cover - network boundary.
            return WebSolution(
                source=f"stackexchange:{self.site}",
                question_id=question_id,
                title="",
                url=url,
                question_text="",
                error=str(exc),
            )

    def fetch_stackexchange_answers(self, question_id: int, limit: int = 3) -> list[WebAnswer]:
        payload = self._api_get(
            f"questions/{question_id}/answers",
            {
                "site": self.site,
                "order": "desc",
                "sort": "votes",
                "pagesize": str(limit),
                "filter": "withbody",
            },
        )
        answers = []
        for item in payload.get("items", [])[:limit]:
            answers.append(
                WebAnswer(
                    answer_id=int(item.get("answer_id", 0)),
                    score=int(item.get("score", 0)),
                    is_accepted=bool(item.get("is_accepted", False)),
                    body_text=strip_html(item.get("body", "")),
                    link=item.get("link"),
                )
            )
        return sorted(answers, key=lambda item: (item.is_accepted, item.score), reverse=True)

    def _api_get(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        query = urllib.parse.urlencode(params)
        url = f"https://api.stackexchange.com/2.3/{path}?{query}"
        request = urllib.request.Request(url, headers={"User-Agent": "math-os-prototype/0.2"})
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))


def extract_stackexchange_question_id(url: str) -> int | None:
    match = re.search(r"stackexchange\.com/questions/(\d+)", url)
    if not match:
        return None
    return int(match.group(1))


def strip_html(text: str) -> str:
    text = re.sub(r"<pre><code>(.*?)</code></pre>", lambda m: "\n" + m.group(1) + "\n", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
