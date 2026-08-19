"""Collect and analyze math-related X activity for MathOS.

This module is intentionally read-only: it never posts, likes, follows, or
replies.  It uses the existing X credentials only to fetch public/account-visible
timelines and mentions, then writes JSON/JSONL/Markdown reports.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import tweepy

try:
    import sympy as sp
except ImportError:  # pragma: no cover
    sp = None

try:
    from .solution_step_parser import SolutionStepParser, extract_math_expressions, extract_relations
except ImportError:  # pragma: no cover - allows direct script execution
    from solution_step_parser import SolutionStepParser, extract_math_expressions, extract_relations


DEFAULT_CONFIG = Path("C:/Users/81808/.openclaw/workspace/youtube/config.json")
DEFAULT_OUTPUT_DIR = Path("C:/Users/81808/.openclaw/workspace/math_os_prototype/x_analysis")

MATH_TERMS = (
    "数学",
    "問題",
    "作問",
    "解答",
    "解法",
    "証明",
    "整数",
    "幾何",
    "関数",
    "積分",
    "微分",
    "確率",
    "数列",
    "極限",
    "方程式",
    "不等式",
    "円",
    "三角",
    "面積",
    "軌跡",
    "接線",
    "最大",
    "最小",
    "求め",
    "示せ",
    "TUS作問",
    "東京理科",
    "AIME",
    "MathOS",
    "TeX",
    "LaTeX",
)

SOLUTION_TERMS = (
    "解け",
    "解き",
    "答え",
    "解答",
    "解法",
    "証明",
    "計算",
    "代入",
    "両辺",
    "場合",
    "仮定",
    "示せ",
    "より",
    "だから",
    "となる",
    "よって",
    "したがって",
    "∴",
    "=",
    "\\[",
    "$",
)

QUESTION_TERMS = (
    "？",
    "?",
    "ですか",
    "でしょうか",
    "教えて",
    "なぜ",
    "どこ",
    "どうやって",
    "どう示",
    "どう解",
    "どうする",
    "いかが",
    "分かります",
    "知りたい",
)
POSITIVE_TERMS = ("面白", "すご", "良い", "好き", "美しい", "なるほど", "ありがとう", "助か", "ナイス", "楽しい")
CORRECTION_TERMS = ("違う", "間違", "誤", "おかしい", "厳しい", "無理", "わから", "分から", "多分あなた")
MISREAD_TERMS = ("条件", "解釈", "意味", "どこ", "長さ", "設定", "出典", "一回で", "切り", "側面", "底面")
CONFIRM_CORRECT_TERMS = ("正解", "合って", "その通り", "あってます", "正しい", "ナイス")


@dataclass
class MediaItem:
    media_key: str
    type: str | None = None
    url: str | None = None
    preview_image_url: str | None = None
    alt_text: str | None = None
    local_path: str | None = None
    ocr_text: str | None = None
    ocr_error: str | None = None


@dataclass
class XUser:
    id: str
    username: str
    name: str
    public_metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class TweetRecord:
    id: str
    text: str
    author_id: str | None
    created_at: str | None
    conversation_id: str | None
    public_metrics: dict[str, Any]
    referenced_tweets: list[dict[str, Any]]
    in_reply_to_user_id: str | None
    media_keys: list[str]
    url: str
    categories: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    answer_class: str = "non_solution"
    math_expressions: list[str] = field(default_factory=list)
    relations: list[str] = field(default_factory=list)
    parsed_solution: dict[str, Any] | None = None
    machine_checks: list[dict[str, Any]] = field(default_factory=list)


def load_client(config_path: Path) -> tweepy.Client:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    x_api = config["x_api"]
    return tweepy.Client(
        consumer_key=x_api["consumer_key"],
        consumer_secret=x_api["consumer_secret"],
        access_token=x_api["access_token"],
        access_token_secret=x_api["access_token_secret"],
        wait_on_rate_limit=False,
    )


def clean_username(value: str) -> str:
    return value.strip().lstrip("@")


def tweet_url(tweet_id: str) -> str:
    return f"https://x.com/i/web/status/{tweet_id}"


def user_to_record(user: Any) -> XUser:
    return XUser(
        id=str(user.id),
        username=user.username,
        name=user.name,
        public_metrics=getattr(user, "public_metrics", None) or {},
    )


def media_to_record(media: Any) -> MediaItem:
    return MediaItem(
        media_key=getattr(media, "media_key", ""),
        type=getattr(media, "type", None),
        url=getattr(media, "url", None),
        preview_image_url=getattr(media, "preview_image_url", None),
        alt_text=getattr(media, "alt_text", None),
    )


def response_users(response: Any) -> dict[str, XUser]:
    users: dict[str, XUser] = {}
    includes = getattr(response, "includes", None) or {}
    if isinstance(includes, dict):
        for user in includes.get("users", []) or []:
            record = user_to_record(user)
            users[record.id] = record
    return users


def response_media(response: Any) -> dict[str, MediaItem]:
    media_map: dict[str, MediaItem] = {}
    includes = getattr(response, "includes", None) or {}
    if isinstance(includes, dict):
        for media in includes.get("media", []) or []:
            record = media_to_record(media)
            if record.media_key:
                media_map[record.media_key] = record
    return media_map


def tweet_to_record(tweet: Any) -> TweetRecord:
    attachments = getattr(tweet, "attachments", None) or {}
    media_keys = []
    if isinstance(attachments, dict):
        media_keys = [str(key) for key in attachments.get("media_keys", []) or []]
    references = []
    for item in getattr(tweet, "referenced_tweets", None) or []:
        references.append(dict(item.data))
    record = TweetRecord(
        id=str(tweet.id),
        text=html.unescape(tweet.text),
        author_id=str(tweet.author_id) if getattr(tweet, "author_id", None) else None,
        created_at=tweet.created_at.isoformat() if getattr(tweet, "created_at", None) else None,
        conversation_id=str(tweet.conversation_id) if getattr(tweet, "conversation_id", None) else None,
        public_metrics=getattr(tweet, "public_metrics", None) or {},
        referenced_tweets=references,
        in_reply_to_user_id=str(tweet.in_reply_to_user_id) if getattr(tweet, "in_reply_to_user_id", None) else None,
        media_keys=media_keys,
        url=tweet_url(str(tweet.id)),
    )
    enrich_tweet(record)
    return record


def contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def has_math_signal(text: str) -> bool:
    if contains_any(text, MATH_TERMS):
        return True
    if re.search(r"(\\frac|\\sqrt|\\int|\\sum|\\log|\\sin|\\cos|\\tan|\^|≤|≥|≦|≧|[a-zA-Z]\s*[=<>])", text):
        return True
    return False


def classify_text(text: str, *, has_media: bool = False) -> tuple[list[str], list[str]]:
    categories: list[str] = []
    labels: list[str] = []

    if has_math_signal(text):
        categories.append("math_related")
    if has_media:
        categories.append("has_media")
    if has_solution_signal(text):
        categories.append("solution_or_attempt")
    if contains_any(text, QUESTION_TERMS):
        categories.append("question")
    if contains_any(text, POSITIVE_TERMS):
        categories.append("positive")
    if contains_any(text, CORRECTION_TERMS):
        categories.append("critical_or_correction")
    if "http" in text:
        categories.append("link")

    if "question" not in categories and contains_any(text, CONFIRM_CORRECT_TERMS):
        labels.append("confirmed_or_positive")
    if contains_any(text, CORRECTION_TERMS):
        labels.append("wrong_or_correction")
    if contains_any(text, MISREAD_TERMS) and contains_any(text, QUESTION_TERMS + CORRECTION_TERMS):
        labels.append("misread_or_condition_question")
    if contains_any(text, QUESTION_TERMS):
        labels.append("question")
    if "solution_or_attempt" in categories:
        labels.append("solution_candidate")
    if has_media and "solution_or_attempt" in categories:
        labels.append("image_or_media_solution_candidate")
    if has_math_signal(text) and contains_any(text, ("別解", "使わない", "こちら", "こう")):
        labels.append("possible_alternative_solution")

    if not categories:
        categories.append("other")
    if not labels:
        labels.append("unclassified")
    return dedupe(categories), dedupe(labels)


def has_solution_signal(text: str) -> bool:
    """Return True for answer attempts, not for mere "can this be solved?" questions."""
    if re.search(r"(解けるの|解けますか|解いてみてください|取り組んでみてください|方法はありますか|どう解|どう示|どうやって|いかがでしょう)", text):
        return False
    strong_terms = (
        "解答してみ",
        "解いてみ",
        "解けました",
        "解いた",
        "証明終",
        "標準で解け",
        "解法思いつ",
        "場合わけいらない解法",
        "両辺",
        "代入",
        "よって",
        "したがって",
        "∴",
    )
    if contains_any(text, strong_terms):
        return True
    if re.search(r"(\\frac|\\sqrt|\\int|\\sum|\\lim|\\log|\\sin|\\cos|\\tan|[A-Za-z]\s*[=<>]|[≦≧≤≥])", text):
        return True
    return False


def answer_class_for(text: str, categories: list[str], labels: list[str]) -> str:
    """Map raw labels to the requested answer-analysis classes.

    We only use `confirmed_correct` when the text itself contains a clear
    correctness confirmation and is not a question.  Most answer-looking replies
    remain unverified until StepVerifier/CAS checks them.
    """
    if "confirmed_or_positive" in labels and "question" not in categories:
        return "confirmed_correct_or_positive"
    if "wrong_or_correction" in labels:
        return "wrong_or_correction"
    if "misread_or_condition_question" in labels:
        return "misread"
    if "possible_alternative_solution" in labels:
        return "alternative_solution_candidate"
    if "solution_candidate" in labels:
        if contains_any(text, ("途中", "ここまで", "方針", "厳しい", "非自明", "方法")):
            return "partial_solution_or_method_question"
        return "solution_candidate_unverified"
    if "question" in labels:
        return "question"
    return "non_solution"


SUPERSCRIPT_TRANSLATION = str.maketrans({
    "⁰": "0",
    "¹": "1",
    "²": "2",
    "³": "3",
    "⁴": "4",
    "⁵": "5",
    "⁶": "6",
    "⁷": "7",
    "⁸": "8",
    "⁹": "9",
})


def verify_math_claims(text: str) -> list[dict[str, Any]]:
    """Best-effort machine checks for compact answer tweets.

    This is deliberately conservative.  It can certify simple constant
    comparisons and can only sanity-check one-variable inequalities by sampling.
    It is not a proof system.
    """
    if sp is None:
        return [{"status": "unavailable", "method": "sympy"}]
    chains = extract_relation_chains(text)
    checks = []
    for chain in chains[:5]:
        check = verify_relation_chain(chain, source_text=text)
        if check:
            checks.append(check)
    return checks


def extract_relation_chains(text: str) -> list[str]:
    normalized = html.unescape(text)
    normalized = re.sub(r"https?://\S+", " ", normalized)
    normalized = re.sub(r"@\w+", " ", normalized)
    normalized = normalized.replace("≦", "<=").replace("≤", "<=").replace("≧", ">=").replace("≥", ">=")
    candidates = []
    pattern = r"[A-Za-z0-9π√\\{}()\[\].,+\-*/^!_\s]+(?:<=|>=|<|>|=)[A-Za-z0-9π√\\{}()\[\].,+\-*/^!_\s]+"
    for match in re.finditer(pattern, normalized):
        value = re.sub(r"\s+", " ", match.group(0)).strip(" ,.;:。")
        if 3 <= len(value) <= 260 and not re.search(r"[ぁ-んァ-ン一-龥]", value):
            candidates.append(value)
    return dedupe(candidates)


def verify_relation_chain(chain: str, *, source_text: str) -> dict[str, Any] | None:
    parts = re.split(r"(<=|>=|<|>|=)", chain)
    if len(parts) < 3:
        return None
    expressions = [parts[index].strip() for index in range(0, len(parts), 2)]
    ops = [parts[index] for index in range(1, len(parts), 2)]
    if len(ops) == 1 and ops[0] == "=" and re.fullmatch(r"[A-Za-z]\s*=\s*[-+]?\d+(?:\.\d+)?", chain.strip()):
        return {"status": "substitution_detected", "method": "pattern", "chain": chain}
    if (
        len(ops) == 1
        and ops[0] in {"<", ">", "<=", ">="}
        and re.fullmatch(r"[A-Za-z]\s*(?:<=|>=|<|>)\s*[-+]?\d+(?:\.\d+)?", chain.strip())
        and contains_any(source_text, ("において", "for", "where", "条件"))
    ):
        return {"status": "condition_detected", "method": "pattern", "chain": chain}
    try:
        parsed = [parse_math_expr(expr) for expr in expressions]
    except Exception as exc:
        return {"status": "no_parse", "chain": chain, "error": str(exc)[:240]}
    if any(expr is None for expr in parsed):
        return {"status": "no_parse", "chain": chain}

    symbols = sorted({str(symbol) for expr in parsed for symbol in expr.free_symbols})
    if not symbols:
        results = [bool(compare_values(parsed[i], ops[i], parsed[i + 1])) for i in range(len(ops))]
        return {
            "status": "verified_numeric" if all(results) else "failed_numeric",
            "method": "sympy_numeric",
            "chain": chain,
            "results": results,
            "values": [str(sp.N(expr, 12)) for expr in parsed],
        }

    if len(symbols) > 1:
        return {"status": "symbolic_unverified", "method": "too_many_symbols", "chain": chain, "symbols": symbols}

    samples = sample_points_for(symbols[0], source_text)
    counterexamples = []
    symbol = next(iter(parsed[0].free_symbols.union(*[expr.free_symbols for expr in parsed[1:]])))
    for sample in samples:
        evaluated = [expr.subs(symbol, sample) for expr in parsed]
        try:
            ok = all(bool(compare_values(evaluated[i], ops[i], evaluated[i + 1])) for i in range(len(ops)))
        except Exception:
            continue
        if not ok:
            counterexamples.append({symbols[0]: float(sample)})
            break
    return {
        "status": "sample_no_counterexample" if not counterexamples else "counterexample_found",
        "method": "sympy_sampling",
        "chain": chain,
        "symbols": symbols,
        "samples": [float(item) for item in samples],
        "counterexamples": counterexamples,
        "warning": "Sampling is not a proof.",
    }


def parse_math_expr(expr: str) -> Any:
    value = normalize_math_expr(expr)
    if not value:
        return None
    locals_map = {
        "E": sp.E,
        "e": sp.E,
        "pi": sp.pi,
        "sqrt": sp.sqrt,
        "log": sp.log,
        "exp": sp.exp,
        "sin": sp.sin,
        "cos": sp.cos,
        "tan": sp.tan,
    }
    parsed = sp.sympify(value, locals=locals_map)
    if not hasattr(parsed, "free_symbols"):
        raise ValueError("expression did not parse to a scalar SymPy expression")
    return parsed


def normalize_math_expr(expr: str) -> str:
    value = expr.strip()
    value = value.translate(SUPERSCRIPT_TRANSLATION)
    value = value.replace("$", "")
    value = value.replace("\\[", "").replace("\\]", "").replace("\\(", "").replace("\\)", "")
    value = value.replace("\\pi", "pi").replace("π", "pi")
    value = re.sub(r"\\(?:dfrac|frac)\{([^{}]+)\}\{\\sqrt\{([^{}]+)\}\}", r"(\1)/sqrt(\2)", value)
    value = re.sub(r"\\(?:dfrac|frac)\{([^{}]+)\}\{([^{}]+)\}", r"(\1)/(\2)", value)
    value = re.sub(r"\\sqrt\{([^{}]+)\}", r"sqrt(\1)", value)
    value = value.replace("{", "(").replace("}", ")")
    value = value.replace("\\log", "log").replace("\\exp", "exp")
    value = value.replace("\\sin", "sin").replace("\\cos", "cos").replace("\\tan", "tan")
    value = re.sub(r"\\(?:dfrac|frac)\(([^()]+)\)\(([^()]+)\)", r"(\1)/(\2)", value)
    value = re.sub(r"\\sqrt\(([^()]+)\)", r"sqrt(\1)", value)
    value = re.sub(r"√\(([^()]+)\)", r"sqrt(\1)", value)
    value = re.sub(r"√([0-9A-Za-z.]+)", r"sqrt(\1)", value)
    value = re.sub(r"\blog\s+([A-Za-z0-9_.]+)", r"log(\1)", value)
    value = value.replace("^", "**")
    value = re.sub(r"(?<![A-Za-z])e(?=\s*\*\*)", "E", value)
    value = re.sub(r"(?<=\d)(?=(sqrt|sin|cos|tan|log|exp|pi|E|[A-Za-z]))", "*", value)
    value = re.sub(r"(?<=pi)(?=\d)", "*", value)
    value = re.sub(r"(?<=E)(?=\d)", "*", value)
    value = value.replace("･", "*").replace("×", "*")
    value = re.sub(r"[^0-9A-Za-z_+\-*/().,\s]", "", value)
    return value.strip(" ,")


def compare_values(lhs: Any, op: str, rhs: Any) -> Any:
    if op == "<":
        return lhs < rhs
    if op == ">":
        return lhs > rhs
    if op == "<=":
        return lhs <= rhs
    if op == ">=":
        return lhs >= rhs
    if op == "=":
        return sp.simplify(lhs - rhs) == 0
    raise ValueError(f"unsupported operator: {op}")


def sample_points_for(symbol: str, source_text: str) -> list[Any]:
    if f"{symbol}>1" in source_text.replace(" ", "") or f"{symbol} > 1" in source_text:
        return [sp.Rational(11, 10), sp.Rational(3, 2), sp.Integer(2), sp.Integer(3), sp.Integer(5), sp.Integer(10)]
    if f"{symbol}>0" in source_text.replace(" ", "") or f"{symbol} > 0" in source_text:
        return [sp.Rational(1, 10), sp.Rational(1, 2), sp.Integer(1), sp.Integer(2), sp.Integer(5)]
    return [sp.Integer(-3), sp.Integer(-1), sp.Integer(0), sp.Integer(1), sp.Integer(2), sp.Integer(3)]


def enrich_tweet(record: TweetRecord) -> None:
    categories, labels = classify_text(record.text, has_media=bool(record.media_keys))
    record.categories = categories
    record.labels = labels
    record.answer_class = answer_class_for(record.text, categories, labels)
    record.math_expressions = extract_math_expressions(record.text)
    record.relations = extract_relations(record.text)
    if "solution_candidate" in labels:
        parser = SolutionStepParser()
        parsed = parser.parse_answer(record.text, source_url=record.url, answer_id=None)
        record.parsed_solution = parsed.to_dict()
        record.machine_checks = verify_math_claims(record.text)


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def safe_api(label: str, fn: Any) -> tuple[Any | None, dict[str, Any] | None]:
    try:
        return fn(), None
    except Exception as exc:  # Tweepy exceptions differ by endpoint/tier.
        return None, {"label": label, "error_type": type(exc).__name__, "error": str(exc)[:1000]}


class XMathAnalyzer:
    def __init__(self, client: tweepy.Client, *, output_dir: Path, download_media: bool = True, ocr: bool = False):
        self.client = client
        self.output_dir = output_dir
        self.download_media = download_media
        self.ocr = ocr
        self.users: dict[str, XUser] = {}
        self.media: dict[str, MediaItem] = {}
        self.errors: list[dict[str, Any]] = []

    def resolve_users(self, usernames: list[str]) -> list[XUser]:
        resolved: list[XUser] = []
        seen: set[str] = set()
        for username in usernames:
            name = clean_username(username)
            if name in seen:
                continue
            seen.add(name)
            response, error = safe_api(
                f"resolve_user:{name}",
                lambda name=name: self.client.get_user(
                    username=name,
                    user_fields=["username", "name", "public_metrics"],
                    user_auth=True,
                ),
            )
            if error:
                self.errors.append(error)
                continue
            if response and response.data:
                record = user_to_record(response.data)
                self.users[record.id] = record
                resolved.append(record)
        return resolved

    def fetch_timeline(self, user: XUser, *, max_results: int) -> list[TweetRecord]:
        response, error = safe_api(
            f"timeline:{user.username}",
            lambda: self.client.get_users_tweets(
                user.id,
                max_results=max(5, min(max_results, 100)),
                tweet_fields=[
                    "created_at",
                    "conversation_id",
                    "public_metrics",
                    "referenced_tweets",
                    "author_id",
                    "in_reply_to_user_id",
                    "attachments",
                    "entities",
                ],
                expansions=["author_id", "attachments.media_keys", "in_reply_to_user_id"],
                media_fields=["url", "preview_image_url", "type", "alt_text"],
                user_fields=["username", "name", "public_metrics"],
                exclude=["retweets"],
                user_auth=True,
            ),
        )
        if error:
            self.errors.append(error)
            return []
        self.users.update(response_users(response))
        self.media.update(response_media(response))
        return [tweet_to_record(tweet) for tweet in (response.data or [])]

    def fetch_mentions(self, user: XUser, *, max_results: int) -> list[TweetRecord]:
        response, error = safe_api(
            f"mentions:{user.username}",
            lambda: self.client.get_users_mentions(
                user.id,
                max_results=max(5, min(max_results, 100)),
                tweet_fields=[
                    "created_at",
                    "conversation_id",
                    "public_metrics",
                    "referenced_tweets",
                    "author_id",
                    "in_reply_to_user_id",
                    "attachments",
                    "entities",
                ],
                expansions=["author_id", "attachments.media_keys", "in_reply_to_user_id"],
                media_fields=["url", "preview_image_url", "type", "alt_text"],
                user_fields=["username", "name", "public_metrics"],
                user_auth=True,
            ),
        )
        if error:
            self.errors.append(error)
            return []
        self.users.update(response_users(response))
        self.media.update(response_media(response))
        return [tweet_to_record(tweet) for tweet in (response.data or [])]

    def fetch_tweets_by_id(self, tweet_ids: list[str], *, label: str) -> dict[str, TweetRecord]:
        records: dict[str, TweetRecord] = {}
        unique_ids = [tweet_id for tweet_id in dedupe(tweet_ids) if tweet_id]
        for start in range(0, len(unique_ids), 100):
            batch = unique_ids[start : start + 100]
            response, error = safe_api(
                f"{label}:{start}",
                lambda batch=batch: self.client.get_tweets(
                    batch,
                    tweet_fields=[
                        "created_at",
                        "conversation_id",
                        "public_metrics",
                        "referenced_tweets",
                        "author_id",
                        "in_reply_to_user_id",
                        "attachments",
                        "entities",
                    ],
                    expansions=["author_id", "attachments.media_keys", "in_reply_to_user_id"],
                    media_fields=["url", "preview_image_url", "type", "alt_text"],
                    user_fields=["username", "name", "public_metrics"],
                    user_auth=True,
                ),
            )
            if error:
                self.errors.append(error)
                continue
            self.users.update(response_users(response))
            self.media.update(response_media(response))
            for tweet in response.data or []:
                record = tweet_to_record(tweet)
                records[record.id] = record
        return records

    def fetch_quote_tweets(self, tweet_ids: list[str], *, per_tweet: int, max_tweets: int) -> dict[str, list[TweetRecord]]:
        quotes: dict[str, list[TweetRecord]] = {}
        for tweet_id in dedupe(tweet_ids)[:max_tweets]:
            response, error = safe_api(
                f"quotes:{tweet_id}",
                lambda tweet_id=tweet_id: self.client.get_quote_tweets(
                    tweet_id,
                    max_results=max(10, min(per_tweet, 100)),
                    tweet_fields=[
                        "created_at",
                        "conversation_id",
                        "public_metrics",
                        "referenced_tweets",
                        "author_id",
                        "in_reply_to_user_id",
                        "attachments",
                    ],
                    expansions=["author_id", "attachments.media_keys"],
                    media_fields=["url", "preview_image_url", "type", "alt_text"],
                    user_fields=["username", "name", "public_metrics"],
                    user_auth=True,
                ),
            )
            if error:
                self.errors.append(error)
                quotes[tweet_id] = []
                continue
            self.users.update(response_users(response))
            self.media.update(response_media(response))
            quotes[tweet_id] = [tweet_to_record(tweet) for tweet in (response.data or [])]
        return quotes

    def download_media_files(self) -> None:
        if not self.download_media:
            return
        media_dir = self.output_dir / "media"
        media_dir.mkdir(parents=True, exist_ok=True)
        for media_key, item in list(self.media.items()):
            source = item.url or item.preview_image_url
            if not source:
                continue
            suffix = Path(source.split("?")[0]).suffix or ".jpg"
            destination = media_dir / f"{media_key}{suffix}"
            if not destination.exists():
                try:
                    response = requests.get(source, timeout=20)
                    response.raise_for_status()
                    destination.write_bytes(response.content)
                except Exception as exc:
                    item.ocr_error = f"download failed: {type(exc).__name__}: {str(exc)[:300]}"
                    continue
            item.local_path = str(destination)
            if self.ocr:
                self.run_ocr(item, destination)

    def run_ocr(self, item: MediaItem, path: Path) -> None:
        try:
            import pytesseract
            from PIL import Image

            item.ocr_text = pytesseract.image_to_string(Image.open(path), lang="jpn+eng")
        except Exception as exc:
            item.ocr_error = f"ocr unavailable: {type(exc).__name__}: {str(exc)[:300]}"

    def analyze(
        self,
        *,
        usernames: list[str],
        mention_username: str,
        timeline_limit: int,
        mentions_limit: int,
        quote_limit: int,
        quote_per_tweet: int,
    ) -> dict[str, Any]:
        users = self.resolve_users(usernames)
        timelines: dict[str, list[TweetRecord]] = {}
        for user in users:
            timelines[user.username] = self.fetch_timeline(user, max_results=timeline_limit)

        mention_user = next((u for u in users if u.username.lower() == clean_username(mention_username).lower()), None)
        if mention_user is None:
            resolved = self.resolve_users([mention_username])
            mention_user = resolved[0] if resolved else None

        mentions = self.fetch_mentions(mention_user, max_results=mentions_limit) if mention_user else []
        origin_ids = [record.conversation_id for record in mentions if record.conversation_id]
        origins = self.fetch_tweets_by_id(origin_ids, label="conversation_origin")

        candidate_quote_ids = rank_problem_tweet_ids(timelines, origins, limit=quote_limit)
        quotes = self.fetch_quote_tweets(candidate_quote_ids, per_tweet=quote_per_tweet, max_tweets=quote_limit) if quote_limit else {}
        self.download_media_files()

        threads = build_threads(mentions=mentions, origins=origins, quotes=quotes)
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "scope": {
                "usernames": usernames,
                "mention_username": mention_username,
                "timeline_limit": timeline_limit,
                "mentions_limit": mentions_limit,
                "quote_limit": quote_limit,
                "quote_per_tweet": quote_per_tweet,
                "api_limitations": [
                    "recent_search_tweets may be unavailable on the current X API tier",
                    "mentions are available only for the authenticated account",
                    "reply trees are incomplete unless replies mention the authenticated account",
                    "image math OCR is optional and depends on a local Tesseract executable",
                ],
            },
            "users": {key: asdict(value) for key, value in self.users.items()},
            "media": {key: asdict(value) for key, value in self.media.items()},
            "timelines": {key: [asdict(item) for item in value] for key, value in timelines.items()},
            "mentions": [asdict(item) for item in mentions],
            "conversation_origins": {key: asdict(value) for key, value in origins.items()},
            "quote_tweets": {key: [asdict(item) for item in value] for key, value in quotes.items()},
            "threads": threads,
            "aggregates": aggregate(timelines=timelines, mentions=mentions, origins=origins, quotes=quotes, threads=threads),
            "errors": self.errors,
        }
        return report


def engagement(record: TweetRecord | dict[str, Any]) -> int:
    metrics = record.public_metrics if isinstance(record, TweetRecord) else record.get("public_metrics", {})
    return sum(int(metrics.get(key, 0) or 0) for key in ("like_count", "reply_count", "retweet_count", "quote_count", "bookmark_count"))


def rank_problem_tweet_ids(
    timelines: dict[str, list[TweetRecord]],
    origins: dict[str, TweetRecord],
    *,
    limit: int,
) -> list[str]:
    candidates: list[TweetRecord] = []
    for records in timelines.values():
        candidates.extend(
            record
            for record in records
            if "math_related" in record.categories or "has_media" in record.categories or "solution_or_attempt" in record.categories
        )
    candidates.extend(record for record in origins.values() if "math_related" in record.categories or "has_media" in record.categories)
    candidates = sorted({record.id: record for record in candidates}.values(), key=engagement, reverse=True)
    return [record.id for record in candidates[:limit]]


def build_threads(
    *,
    mentions: list[TweetRecord],
    origins: dict[str, TweetRecord],
    quotes: dict[str, list[TweetRecord]],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[TweetRecord]] = defaultdict(list)
    for mention in mentions:
        if mention.conversation_id:
            grouped[mention.conversation_id].append(mention)

    threads = []
    for conversation_id, replies in grouped.items():
        origin = origins.get(conversation_id)
        quote_items = quotes.get(conversation_id, [])
        labels = Counter(label for reply in replies for label in reply.labels)
        categories = Counter(category for reply in replies for category in reply.categories)
        answer_classes = Counter(reply.answer_class for reply in replies)
        threads.append(
            {
                "conversation_id": conversation_id,
                "origin": asdict(origin) if origin else None,
                "reply_count_in_sample": len(replies),
                "quote_count_in_sample": len(quote_items),
                "reply_labels": dict(labels),
                "reply_categories": dict(categories),
                "answer_classes": dict(answer_classes),
                "replies": [asdict(reply) for reply in replies],
                "quotes": [asdict(quote) for quote in quote_items],
                "needs_verification": any("solution_candidate" in reply.labels for reply in replies),
            }
        )
    return sorted(threads, key=lambda item: engagement(item["origin"] or {}), reverse=True)


def aggregate(
    *,
    timelines: dict[str, list[TweetRecord]],
    mentions: list[TweetRecord],
    origins: dict[str, TweetRecord],
    quotes: dict[str, list[TweetRecord]],
    threads: list[dict[str, Any]],
) -> dict[str, Any]:
    timeline_counts = {username: len(records) for username, records in timelines.items()}
    mention_categories = Counter(category for item in mentions for category in item.categories)
    mention_labels = Counter(label for item in mentions for label in item.labels)
    mention_answer_classes = Counter(item.answer_class for item in mentions)
    machine_check_statuses = Counter(
        check.get("status", "unknown")
        for item in mentions
        for check in item.machine_checks
    )
    quote_total = sum(len(items) for items in quotes.values())
    problem_posts = []
    for records in timelines.values():
        problem_posts.extend(
            item
            for item in records
            if "math_related" in item.categories or "has_media" in item.categories or contains_any(item.text, ("作問", "問題", "求め", "示せ"))
        )
    top_problem_posts = sorted({item.id: item for item in problem_posts}.values(), key=engagement, reverse=True)[:20]
    return {
        "timeline_counts": timeline_counts,
        "mentions_count": len(mentions),
        "conversation_origins_count": len(origins),
        "threads_count": len(threads),
        "quote_tweets_count": quote_total,
        "mention_categories": dict(mention_categories),
        "mention_labels": dict(mention_labels),
        "mention_answer_classes": dict(mention_answer_classes),
        "machine_check_statuses": dict(machine_check_statuses),
        "top_problem_posts": [asdict(item) for item in top_problem_posts],
        "threads_with_solution_candidates": sum(1 for item in threads if item.get("needs_verification")),
    }


def write_outputs(report: dict[str, Any], *, output_dir: Path, prefix: str) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{prefix}.json"
    jsonl_path = output_dir / f"{prefix}_threads.jsonl"
    md_path = output_dir / f"{prefix}_report.md"

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for thread in report["threads"]:
            handle.write(json.dumps(thread, ensure_ascii=False) + "\n")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, jsonl_path, md_path


def render_markdown(report: dict[str, Any]) -> str:
    aggregates = report["aggregates"]
    lines: list[str] = []
    lines.append("# X Math Activity Analysis")
    lines.append("")
    lines.append(f"Generated: {report['generated_at']}")
    lines.append("")
    lines.append("## Scope")
    lines.append("")
    scope = report["scope"]
    lines.append(f"- Accounts: {', '.join('@' + name for name in scope['usernames'])}")
    lines.append(f"- Mention inbox: @{scope['mention_username']}")
    lines.append(f"- Timeline counts: {json.dumps(aggregates['timeline_counts'], ensure_ascii=False)}")
    lines.append(f"- Mentions: {aggregates['mentions_count']}")
    lines.append(f"- Conversation origins fetched: {aggregates['conversation_origins_count']}")
    lines.append(f"- Threads from mentions: {aggregates['threads_count']}")
    lines.append(f"- Quote tweets fetched: {aggregates['quote_tweets_count']}")
    lines.append("")
    lines.append("## API Limitations")
    lines.append("")
    for item in scope["api_limitations"]:
        lines.append(f"- {item}")
    if report["errors"]:
        lines.append("")
        lines.append("Observed API errors:")
        for error in report["errors"][:10]:
            lines.append(f"- {error.get('label')}: {error.get('error_type')} - {error.get('error')}")
    lines.append("")
    lines.append("## Reply / Solution Labels")
    lines.append("")
    lines.append("Mention categories:")
    for key, value in sorted(aggregates["mention_categories"].items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("Mention labels:")
    for key, value in sorted(aggregates["mention_labels"].items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("Answer classes:")
    for key, value in sorted(aggregates["mention_answer_classes"].items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("Machine check statuses:")
    if aggregates.get("machine_check_statuses"):
        for key, value in sorted(aggregates["machine_check_statuses"].items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## High-Signal Problem Posts")
    lines.append("")
    for item in aggregates["top_problem_posts"][:10]:
        lines.append(format_tweet_bullet(item))
    lines.append("")
    lines.append("## Threads With Answer / Misread Signals")
    lines.append("")
    interesting = [
        thread
        for thread in report["threads"]
        if thread.get("needs_verification")
        or thread.get("reply_labels", {}).get("wrong_or_correction")
        or thread.get("reply_labels", {}).get("misread_or_condition_question")
        or thread.get("reply_labels", {}).get("question")
    ]
    for thread in interesting[:15]:
        origin = thread.get("origin") or {}
        lines.append(f"### {origin.get('url', 'unknown thread')}")
        origin_text = compact(origin.get("text", ""))
        if origin_text:
            lines.append(f"Origin: {origin_text}")
        lines.append(f"Replies in sample: {thread['reply_count_in_sample']}, quotes in sample: {thread['quote_count_in_sample']}")
        lines.append(f"Labels: {json.dumps(thread['reply_labels'], ensure_ascii=False)}")
        lines.append(f"Answer classes: {json.dumps(thread.get('answer_classes', {}), ensure_ascii=False)}")
        for reply in thread["replies"][:4]:
            author = username_for(report, reply.get("author_id"))
            lines.append(
                f"- @{author or '?'} [{reply.get('answer_class', 'non_solution')} / {', '.join(reply.get('labels', []))}]: "
                f"{compact(reply.get('text', ''))}"
            )
        lines.append("")
    lines.append("## Verification Queue")
    lines.append("")
    queue = []
    for thread in report["threads"]:
        for reply in thread["replies"]:
            if "solution_candidate" in reply.get("labels", []):
                queue.append((thread, reply))
    if not queue:
        lines.append("- No solution candidates found in the current sample.")
    for thread, reply in queue[:20]:
        origin = thread.get("origin") or {}
        author = username_for(report, reply.get("author_id"))
        lines.append(f"- Thread: {origin.get('url', thread.get('conversation_id'))}")
        lines.append(f"  Reply: {reply.get('url')} by @{author or '?'}")
        lines.append(f"  Class: {reply.get('answer_class')}")
        lines.append(f"  Relations: {json.dumps(reply.get('relations', []), ensure_ascii=False)}")
        lines.append(f"  Machine checks: {json.dumps(reply.get('machine_checks', []), ensure_ascii=False)}")
        lines.append(f"  Text: {compact(reply.get('text', ''), 220)}")
    lines.append("")
    lines.append("## Next Engineering Steps")
    lines.append("")
    lines.append("- Add browser-backed collection for full reply trees and quote tweets when X API search is unavailable.")
    lines.append("- Add OCR/vision math extraction for attached answer images; current OCR requires local Tesseract.")
    lines.append("- Route `solution_candidate` replies through `SolutionStepParser -> StepVerifier` and mark `verified_correct` only when the steps check.")
    lines.append("- Track per-problem ambiguity: condition questions and correction clusters should become problem statement feedback.")
    return "\n".join(lines) + "\n"


def username_for(report: dict[str, Any], user_id: str | None) -> str | None:
    if not user_id:
        return None
    user = report.get("users", {}).get(str(user_id))
    if not user:
        return None
    return user.get("username")


def compact(text: str, limit: int = 180) -> str:
    value = re.sub(r"\s+", " ", text).strip()
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def format_tweet_bullet(item: dict[str, Any]) -> str:
    metrics = item.get("public_metrics", {})
    score = sum(int(metrics.get(key, 0) or 0) for key in ("like_count", "reply_count", "retweet_count", "quote_count", "bookmark_count"))
    return (
        f"- {item.get('url')} score={score} "
        f"likes={metrics.get('like_count', 0)} replies={metrics.get('reply_count', 0)} "
        f"quotes={metrics.get('quote_count', 0)} bookmarks={metrics.get('bookmark_count', 0)}: "
        f"{compact(item.get('text', ''))}"
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze math-related X activity for MathOS.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--prefix", default=None)
    parser.add_argument("--users", nargs="+", default=["corcondol", "tuSakumon", "tuSakumon2025"])
    parser.add_argument("--mention-user", default="corcondol")
    parser.add_argument("--timeline-limit", type=int, default=50)
    parser.add_argument("--mentions-limit", type=int, default=100)
    parser.add_argument("--quote-limit", type=int, default=10)
    parser.add_argument("--quote-per-tweet", type=int, default=10)
    parser.add_argument("--no-download-media", action="store_true")
    parser.add_argument("--ocr", action="store_true")
    return parser


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = build_arg_parser().parse_args()
    prefix = args.prefix or f"x_math_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    client = load_client(args.config)
    analyzer = XMathAnalyzer(
        client,
        output_dir=args.output_dir,
        download_media=not args.no_download_media,
        ocr=args.ocr,
    )
    report = analyzer.analyze(
        usernames=args.users,
        mention_username=args.mention_user,
        timeline_limit=args.timeline_limit,
        mentions_limit=args.mentions_limit,
        quote_limit=args.quote_limit,
        quote_per_tweet=args.quote_per_tweet,
    )
    json_path, jsonl_path, md_path = write_outputs(report, output_dir=args.output_dir, prefix=prefix)
    print(json.dumps({
        "ok": True,
        "json": str(json_path),
        "jsonl": str(jsonl_path),
        "report": str(md_path),
        "aggregates": report["aggregates"],
        "errors": report["errors"][:5],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
