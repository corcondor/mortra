"""Deterministic natural-language/TeX to AlphaGeometry2 formalization.

This is intentionally a finite mathematical grammar, not a general prose
translator.  It produces a typed predicate IR, constructs a numerical witness
by constrained optimization, and emits an AG2 statement only when every
mathematical relation in the supported input has been consumed.
"""

from __future__ import annotations

import hashlib
import itertools
import re
from dataclasses import asdict, dataclass
from fractions import Fraction
from typing import Any, Iterable

import numpy as np
from scipy.optimize import least_squares


RELATION_SYMBOLS = (
    "perp", "para", "cong", "coll", "cyclic", "eqangle",
    "rconst", "eqratio", "s_angle", "distseq",
)
QUERY_MARKERS_JA = ("を示せ", "を証明せよ", "を証明しなさい", "ことを示せ", "ことを証明せよ")
QUERY_MARKERS_EN = ("prove that", "show that", "prove", "show")


@dataclass(frozen=True)
class TypedPredicate:
    name: str
    points: tuple[str, ...]
    source: str
    constants: tuple[str, ...] = ()

    def render(self) -> str:
        return " ".join((self.name, *self.points, *self.constants))


@dataclass
class GeometryFormalization:
    status: str
    normalized_text: str
    points: list[str]
    predicates: list[TypedPredicate]
    goal: TypedPredicate | None
    # 結論は一本とは限らない。「四辺形ABCDは平行四辺形」は平行2本、
    # 「4点は同一直線上」は3点組4本、「AとBは平行で、CとDは直交」は2本。
    # 一本に落ちないものを落としていたのは、こちらの誤りだった。
    goals: list[TypedPredicate]
    triangles: list[tuple[str, str, str]]
    unresolved_relations: list[str]
    coordinates: dict[str, tuple[float, float]]
    diagram_residual: float | None
    restarts: int
    formal_problem: str | None
    discourse_objects: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["predicates"] = [asdict(item) for item in self.predicates]
        value["goal"] = asdict(self.goal) if self.goal else None
        value["goals"] = [asdict(g) for g in self.goals]
        return value


def candidate_splits(normalized: str) -> list[tuple[str, str]]:
    """前提と結論の切り方の候補を並べる。

    入試の問題文は (1)(2)(3) が連結していたり、設定と結論が
    「…とすれば、…であること」のように一文に同居していたりする。
    切り方を一つに決め打ちすると、そこで外したら全部落ちる。
    候補を作って、実際に述語が取れたものを採る。
    """
    out: list[tuple[str, str]] = []

    def push(p: str, g: str) -> None:
        p, g = p.strip("。 、"), g.strip("。 、")
        if g and (p, g) not in out:
            out.append((p, g))

    base_p, base_g = split_goal(normalized)
    push(*peel_subordinate(base_p, base_g))
    push(base_p, base_g)

    # 小問が連結している場合、最後の問いだけを見る。
    # 直前の「示せ/求めよ」より後ろが、最後の小問の設定と結論。
    for marker in ("を示せ", "を証明せよ", "を求めよ", "求めよ", "答えよ"):
        cut = normalized.rfind(marker)
        if cut <= 0:
            continue
        head = normalized[:cut]
        prev = max(head.rfind(m) for m in ("示せ", "証明せよ", "求めよ", "答えよ"))
        if prev > 0:
            tail = head[prev:].lstrip("示せ証明求よ答。 、")
            p, g = split_goal(tail + marker)
            push(*peel_subordinate(p, g))
        break

    # 「…こと」で終わる結論節を、単独で結論として試す
    for m in re.finditer(r"[。、]([^。]{4,120}?)(?:である)?こと(?:を示せ|を証明せよ|$)", normalized):
        push(normalized[:m.start()], m.group(1))

    # 最後の一文だけを結論にする
    sentences = [s for s in normalized.split("。") if s.strip()]
    if len(sentences) >= 2:
        push("。".join(sentences[:-1]), sentences[-1])
    return out


def formalize_geometry_text(text: str, *, max_restarts: int = 20) -> GeometryFormalization:
    """候補の切り方を順に試し、最も多くの関係を消費できたものを返す。

    一回試して落ちたら終わり、では問題文との相性で結果が決まってしまう。
    """
    normalized = normalize_text(text)
    best: GeometryFormalization | None = None
    for premise_text, goal_text in candidate_splits(normalized):
        attempt = _formalize_split(normalized, premise_text, goal_text, max_restarts=max_restarts)
        if attempt.status == "formalized":
            return attempt
        # 落ちたものの中では、結論が一本に決まっていて前提を多く読めたものを残す
        def score(r: GeometryFormalization) -> tuple[int, int, int]:
            return (r.goal is not None, len(r.predicates), -len(r.unresolved_relations))
        if best is None or score(attempt) > score(best):
            best = attempt
    return best if best is not None else _formalize_split(normalized, normalized, "", max_restarts=max_restarts)


def _formalize_split(
    normalized: str, premise_text: str, goal_text: str, *, max_restarts: int = 20,
) -> GeometryFormalization:
    from geometry_discourse import elaborate_circle_discourse

    discourse = elaborate_circle_discourse(premise_text, goal_text)
    premise_text, goal_text = discourse.premise_text, discourse.goal_text
    triangles = extract_triangles(normalized)
    predicates, premise_spans = extract_predicates(premise_text)
    goals, goal_spans = extract_predicates(goal_text)
    predicates.extend(
        TypedPredicate(item.name, item.points, item.source)
        for item in discourse.premise_relations
    )
    goals.extend(
        TypedPredicate(item.name, item.points, item.source)
        for item in discourse.goal_relations
    )
    predicates = expand_derived_predicates(predicates, triangles)
    goals = deduplicate_predicates(goals)
    goal = goals[0] if goals else None
    unresolved = unresolved_relation_fragments(premise_text, premise_spans)
    unresolved.extend(unresolved_relation_fragments(goal_text, goal_spans))
    unresolved.extend(discourse.unresolved)
    unsupported = sorted({item.name for item in [*predicates, *goals] if item.name not in RELATION_SYMBOLS})
    unresolved.extend(f"unsupported typed predicate: {name}" for name in unsupported)
    for item in [*predicates, *goals]:
        issue = predicate_type_issue(item)
        if issue:
            unresolved.append(f"ill-typed predicate {item.render()}: {issue}")
    if not goals:
        unresolved.append("no goal predicate was identified")

    points = sorted({point for item in [*predicates, *goals] for point in item.points} | {
        point for triangle in triangles for point in triangle
    })
    if len(points) < 2:
        unresolved.append("fewer than two geometric points were identified")

    result = GeometryFormalization(
        status="unresolved" if unresolved else "parsed",
        normalized_text=normalized,
        points=points,
        predicates=deduplicate_predicates(predicates),
        goal=goal,
        goals=goals,
        triangles=triangles,
        unresolved_relations=unresolved,
        coordinates={},
        diagram_residual=None,
        restarts=0,
        formal_problem=None,
        discourse_objects=[item.to_dict() for item in discourse.circles],
    )
    if unresolved or goal is None:
        return result

    coordinates, residual, restarts = construct_diagram(
        points,
        [*result.predicates, *goals],
        triangles,
        seed_text=normalized,
        max_restarts=max_restarts,
    )
    result.coordinates = coordinates
    result.diagram_residual = residual
    result.restarts = restarts
    if not coordinates:
        result.status = "diagram_failed"
        result.unresolved_relations.append("typed constraints did not yield a nondegenerate numerical diagram")
        return result
    result.formal_problem = render_formal_problem(points, coordinates, result.predicates, goal)
    result.status = "formalized"
    return result


def normalize_text(text: str) -> str:
    value = text.replace("\r", " ").replace("\n", " ")
    value = re.sub(r"\\text\s*\{([^{}]*)\}", r"\1", value)
    value = re.sub(r"\\frac\s*\{\s*(-?\d+)\s*\}\s*\{\s*(\d+)\s*\}", r"\1/\2", value)
    replacements = {
        "\\perp": "⊥",
        "\\parallel": "∥",
        "\\angle": "∠",
        "^\\circ": "°",
        "\\circ": "°",
        "\\Gamma": "Γ",
        "\\Omega": "Ω",
        "\\gamma": "γ",
        "\\omega": "ω",
        "$": "",
        "（": "(",
        "）": ")",
        "，": ",",
        "；": ";",
        "：": ":",
        "＝": "=",
        "−": "-",
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def split_goal(text: str) -> tuple[str, str]:
    if "?" in text:
        return tuple(part.strip() for part in text.rsplit("?", 1))  # type: ignore[return-value]
    lowered = text.lower()
    for marker in QUERY_MARKERS_EN:
        index = lowered.rfind(marker)
        if index >= 0:
            return text[:index].strip(" ,.;。"), text[index + len(marker):].strip(" ,.;。")
    for marker in QUERY_MARKERS_JA:
        index = text.rfind(marker)
        if index < 0:
            continue
        before = text[:index].rstrip()
        boundary = max(before.rfind("。"), before.rfind(";"), before.rfind("."))
        if boundary >= 0:
            return before[:boundary].strip(), before[boundary + 1:].strip(" ,、")
        comma = max(before.rfind("、"), before.rfind(","))
        if comma >= 0:
            return before[:comma].strip(), before[comma + 1:].strip()
        return "", before.strip()
    return text, ""


# 「…とするとき、」「…ならば、」は前提と結論の境目。
# 「。」だけで切ると、この従属節が結論側に残り、結論の述語が複数個になって落ちる。
#
# 「とすれば」「とすると」は入試で最も多い形。これが無いと、
# 「線分AB、EG…の中点をそれぞれM、P…とすれば、4点は一直線上」で
# 中点の定義が結論側に残り、結論の述語が4本になって落ちる。
SUBORDINATE_JA = (
    "とするとき、", "とおくとき、", "であるとき、", "のとき、", "とき、",
    "とすれば、", "とすれば", "とおけば、", "とおけば",
    "とすると、", "とすると", "とおくと、", "とおくと",
    "をとれば、", "をとれば", "ひけば、", "引けば、",
    "ならば、", "ならば",
)


def peel_subordinate(premise: str, goal: str) -> tuple[str, str]:
    """結論側に紛れ込んだ従属節を前提側へ移す。

    「三角形ABCの垂心をHとする。AHとBCの交点をDとするとき、ADとBCは垂直である」
    を「。」だけで切ると、結論側に交点の定義が残って述語が3本になる。
    最後の従属節境界までを前提へ送り、結論を一本にする。
    """
    ends = [goal.rfind(marker) + len(marker) for marker in SUBORDINATE_JA if marker in goal]
    if not ends:
        return premise, goal
    cut = max(ends)
    moved, rest = goal[:cut], goal[cut:].strip(" 、,")
    if not rest:
        return premise, goal
    return ((premise + "。" + moved).strip("。 ") if premise else moved), rest


def extract_triangles(text: str) -> list[tuple[str, str, str]]:
    patterns = (
        r"(?:三角形|△)\s*([A-Z])([A-Z])([A-Z])",
        r"triangle\s+([A-Z])([A-Z])([A-Z])",
    )
    found: list[tuple[str, str, str]] = []
    for pattern in patterns:
        found.extend(tuple(match.groups()) for match in re.finditer(pattern, text, re.IGNORECASE))
    return list(dict.fromkeys(tuple(point.lower() for point in triangle) for triangle in found))


def extract_predicates(text: str) -> tuple[list[TypedPredicate], list[tuple[int, int]]]:
    predicates: list[TypedPredicate] = []
    spans: list[tuple[int, int]] = []

    def collect(pattern: str, builder) -> None:
        for match in re.finditer(pattern, text):
            if any(match.start() < end and start < match.end() for start, end in spans):
                continue
            value = builder(match)
            if isinstance(value, list):
                predicates.extend(value)
            else:
                predicates.append(value)
            spans.append(match.span())

    segment = r"([A-Z])\s*([A-Z])"
    scalar = r"(-?\d+(?:/\d+|\.\d+)?)"
    # 「直線ABと直線PQは直交する」のように、線分名の前に語が挟まる。
    # これを許さないと、結論が一つも読めない問題が大量に出る。
    LINE = r"(?:直線|線分|辺|半直線)?\s*"
    collect(
        segment + r"\s*:\s*" + segment + r"\s*=\s*" + segment + r"\s*:\s*" + segment,
        lambda m: TypedPredicate("eqratio", tuple(value.lower() for value in m.groups()), m.group(0)),
    )
    collect(
        segment + r"\s*/\s*" + segment + r"\s*=\s*" + scalar,
        lambda m: TypedPredicate(
            "rconst",
            tuple(value.lower() for value in m.groups()[:4]),
            m.group(0),
            (normalize_constant(m.group(5)),),
        ),
    )
    collect(
        r"∠\s*([A-Z])([A-Z])([A-Z])\s*=\s*" + scalar + r"\s*°?",
        lambda m: constant_angle_predicate(m.groups(), m.group(0)),
    )
    collect(r"∠\s*([A-Z])([A-Z])([A-Z])\s*=\s*∠\s*([A-Z])([A-Z])([A-Z])",
            lambda m: angle_predicate(m.groups(), m.group(0)))
    collect(segment + r"\s*(?:⊥|is\s+perpendicular\s+to)\s*" + segment,
            lambda m: predicate("perp", m.groups(), m.group(0)))
    collect(segment + r"\s*(?:∥|//|is\s+parallel\s+to)\s*" + segment,
            lambda m: predicate("para", m.groups(), m.group(0)))
    collect(segment + r"\s*=\s*" + segment,
            lambda m: predicate("cong", m.groups(), m.group(0)))

    collect(
        r"([A-Z])\s*(?:は|is)\s*(?:直線|line)\s*([A-Z])([A-Z])(?:\s*(?:上にある|上|on))",
        lambda m: TypedPredicate("coll", (m.group(2).lower(), m.group(1).lower(), m.group(3).lower()), m.group(0)),
    )
    collect(
        r"([A-Z])\s+(?:lies|is)\s+on\s+(?:the\s+)?line\s+([A-Z])([A-Z])",
        lambda m: TypedPredicate("coll", (m.group(2).lower(), m.group(1).lower(), m.group(3).lower()), m.group(0)),
    )
    collect(
        r"([A-Z])\s*(?:は|is)\s*(?:線分|segment)\s*([A-Z])([A-Z])(?:\s*(?:上|上にある|on))",
        lambda m: TypedPredicate("coll", (m.group(2).lower(), m.group(1).lower(), m.group(3).lower()), m.group(0)),
    )
    collect(
        r"([A-Z])\s*(?:は|is)\s*(?:円|circle)\s*([A-Z])([A-Z])([A-Z])(?:\s*(?:上にある|上|on))",
        lambda m: TypedPredicate(
            "cyclic",
            (m.group(2).lower(), m.group(3).lower(), m.group(4).lower(), m.group(1).lower()),
            m.group(0),
        ),
    )
    collect(
        r"([A-Z])\s+(?:lies|is)\s+on\s+(?:the\s+)?circle\s+through\s+([A-Z])\s*[, ]\s*([A-Z])\s*(?:and|[, ])\s*([A-Z])",
        lambda m: TypedPredicate(
            "cyclic",
            (m.group(2).lower(), m.group(3).lower(), m.group(4).lower(), m.group(1).lower()),
            m.group(0),
        ),
    )
    collect(
        r"([A-Z])\s*(?:は)?\s*([A-Z])\s*[,、]\s*([A-Z])\s*[,、]\s*([A-Z])\s*(?:を通る円|の定める円)(?:周)?上にある",
        lambda m: TypedPredicate(
            "cyclic",
            (m.group(2).lower(), m.group(3).lower(), m.group(4).lower(), m.group(1).lower()),
            m.group(0),
        ),
    )
    collect(
        r"([A-Z])\s*(?:は|is)\s*(?:直線\s*)?([A-Z])([A-Z])\s*(?:と|and)\s*(?:直線\s*)?([A-Z])([A-Z])(?:\s*(?:の|the))?\s*(?:交点|intersection)",
        lambda m: intersection_predicates(m.groups(), m.group(0)),
    )
    collect(
        r"([A-Z])\s+is\s+the\s+intersection\s+of\s+(?:lines?\s+)?([A-Z])([A-Z])\s+and\s+([A-Z])([A-Z])",
        lambda m: intersection_predicates(m.groups(), m.group(0)),
    )
    collect(
        r"(?:直線|line)\s*([A-Z])([A-Z])\s*(?:は|is)?\s*(?:点\s*)?([A-Z])(?:\s*で|\s+at)\s*(?:中心\s*)?([A-Z])(?:\s*の|[- ]centered)?\s*(?:円|circle)(?:\s*に|\s+is)?\s*(?:接する|tangent)",
        lambda m: tangent_predicate(m.groups(), m.group(0)),
    )

    collect(
        r"([A-Z])\s*(?:は|is)\s*(?:線分\s*)?([A-Z])([A-Z])(?:\s*(?:の|the))?\s*(?:中点|midpoint)",
        lambda m: midpoint_predicates(m.groups(), m.group(0)),
    )
    collect(
        r"([A-Z])\s+is\s+the\s+midpoint\s+of\s+([A-Z])([A-Z])",
        lambda m: midpoint_predicates(m.groups(), m.group(0)),
    )
    collect(
        r"([A-Z])\s*(?:は|is)\s*(?:三角形\s*)?([A-Z])([A-Z])([A-Z])(?:\s*(?:の|the))?\s*(?:外心|circumcenter)",
        lambda m: circumcenter_predicates(m.groups(), m.group(0)),
    )
    collect(
        r"([A-Z])\s+is\s+the\s+circumcenter\s+of\s+(?:triangle\s+)?([A-Z])([A-Z])([A-Z])",
        lambda m: circumcenter_predicates(m.groups(), m.group(0)),
    )
    collect(
        r"([A-Z])\s*(?:は|is)\s*(?:三角形\s*)?([A-Z])([A-Z])([A-Z])(?:\s*(?:の|the))?\s*(?:重心|centroid)",
        lambda m: centroid_predicates(m.groups(), m.group(0)),
    )
    collect(
        r"([A-Z])\s+is\s+the\s+centroid\s+of\s+(?:triangle\s+)?([A-Z])([A-Z])([A-Z])",
        lambda m: centroid_predicates(m.groups(), m.group(0)),
    )
    collect(
        r"([A-Z])\s*(?:は|is)\s*(?:三角形\s*)?([A-Z])([A-Z])([A-Z])(?:\s*(?:の|the))?\s*(?:垂心|orthocenter)",
        lambda m: orthocenter_predicates(m.groups(), m.group(0)),
    )
    collect(
        r"([A-Z])\s+is\s+the\s+orthocenter\s+of\s+(?:triangle\s+)?([A-Z])([A-Z])([A-Z])",
        lambda m: orthocenter_predicates(m.groups(), m.group(0)),
    )
    collect(
        r"([A-Z])\s*(?:は|is)\s*(?:三角形\s*)?([A-Z])([A-Z])([A-Z])(?:\s*(?:の|the))?\s*(?:内心|incenter)",
        lambda m: incenter_predicates(m.groups(), m.group(0)),
    )
    collect(
        r"([A-Z])\s+is\s+the\s+incenter\s+of\s+(?:triangle\s+)?([A-Z])([A-Z])([A-Z])",
        lambda m: incenter_predicates(m.groups(), m.group(0)),
    )

    # ------------------------------------------------------------------
    # 「〜を X とする」構文。
    #
    # 入試の日本語は主題化形（「M は BC の中点」）ではなく、ほぼ必ず
    # 措定形（「BC の中点を M とする」）で書かれる。上の は 形だけを
    # 持っていた間、実際の入試文は一つも形式化できなかった。
    # 述語の構成関数は共有し、正規表現の群の並びだけ入れ替える。
    # ------------------------------------------------------------------
    TRI = r"(?:三角形|△)?\s*([A-Z])\s*([A-Z])\s*([A-Z])"
    # 「…をMとする」に加えて、列挙の「…をM、…をNとする」も受ける。
    # 前者だけだと、最初の中点が読まれずに落ちる。
    LET = r"を\s*([A-Z])\s*(?:と(?:する|し|おく|置く|よぶ|呼ぶ)|とすると|(?=[、,]))"

    def center(pattern_word: str, builder):
        """「三角形ABCの◯心をPとする」→ builder(P, A, B, C)"""
        collect(
            TRI + r"\s*の\s*" + pattern_word + LET,
            lambda m: builder((m.group(4), m.group(1), m.group(2), m.group(3)), m.group(0)),
        )

    center("外心", circumcenter_predicates)
    center("重心", centroid_predicates)
    center("垂心", orthocenter_predicates)
    center("内心", incenter_predicates)

    collect(
        r"(?:線分|辺)?\s*([A-Z])\s*([A-Z])\s*の\s*中点" + LET,
        lambda m: midpoint_predicates((m.group(3), m.group(1), m.group(2)), m.group(0)),
    )
    collect(
        r"(?:直線|線分)?\s*([A-Z])\s*([A-Z])\s*と\s*(?:直線|線分)?\s*([A-Z])\s*([A-Z])\s*の\s*交点" + LET,
        lambda m: intersection_predicates(
            (m.group(5), m.group(1), m.group(2), m.group(3), m.group(4)), m.group(0)
        ),
    )

    # ── 垂線の足 ──────────────────────────────────────────────
    # 入試の幾何で最も多い構成。足が無いと垂心・外心の問題がほぼ全部落ちる。
    collect(
        r"([A-Z])\s*(?:から|より)\s*(?:直線|辺)?\s*([A-Z])\s*([A-Z])\s*(?:に|へ)\s*(?:下ろした|おろした|引いた)?\s*"
        r"垂線\s*の\s*足" + LET,
        lambda m: [
            TypedPredicate("coll", (m.group(2).lower(), m.group(4).lower(), m.group(3).lower()), m.group(0)),
            TypedPredicate("perp", (m.group(1).lower(), m.group(4).lower(),
                                    m.group(2).lower(), m.group(3).lower()), m.group(0)),
        ],
    )
    collect(
        r"([A-Z])\s*(?:から|より)\s*(?:直線|辺)?\s*([A-Z])\s*([A-Z])\s*(?:に|へ)\s*垂線\s*([A-Z])\s*([A-Z])\s*を\s*"
        r"(?:下ろす|おろす|引く|下ろし|引き)",
        lambda m: [
            TypedPredicate("coll", (m.group(2).lower(), m.group(5).lower(), m.group(3).lower()), m.group(0)),
            TypedPredicate("perp", (m.group(4).lower(), m.group(5).lower(),
                                    m.group(2).lower(), m.group(3).lower()), m.group(0)),
        ],
    )

    # ── 円 ────────────────────────────────────────────────────
    # 円は中心を実体として持つ。持たないと接線も垂直二等分線も書けない。
    collect(
        TRI + r"\s*の\s*外接円\s*の\s*中心" + LET,
        lambda m: circumcenter_predicates(
            (m.group(4), m.group(1), m.group(2), m.group(3)), m.group(0)),
    )
    collect(
        r"(?:点\s*)?([A-Z])\s*を\s*中心\s*と\s*(?:し|する)[^。]{0,12}?半径\s*([A-Z])\s*([A-Z])\s*の\s*円"
        r"(?:周)?\s*上\s*の\s*点" + LET,
        lambda m: TypedPredicate(
            "cong", (m.group(1).lower(), m.group(4).lower(),
                     m.group(2).lower(), m.group(3).lower()), m.group(0)),
    )
    collect(
        r"(?:点\s*)?([A-Z])\s*を\s*中心\s*と\s*(?:し|する)\s*(?:点\s*)?([A-Z])\s*を\s*通る\s*円",
        lambda m: TypedPredicate(
            "cong", (m.group(1).lower(), m.group(2).lower(),
                     m.group(1).lower(), m.group(2).lower()), m.group(0)),
    )
    # 「ABを直径とする円周上の点P」→ タレスの直角。角度定数ではなく perp で持つ
    collect(
        r"([A-Z])\s*([A-Z])\s*を\s*直径\s*と\s*する\s*円(?:周)?\s*上\s*の\s*点" + LET,
        lambda m: TypedPredicate(
            "perp", (m.group(1).lower(), m.group(3).lower(),
                     m.group(2).lower(), m.group(3).lower()), m.group(0)),
    )

    # ── 接線 ──────────────────────────────────────────────────
    # 接線の数学的な中身は一つだけ ―― 中心から接点への線と接線が直交する。
    # だから接線そのものを対象にせず、接線上の点との垂直関係に落とす。
    # 中心が文中に無ければ、外接円の中心として存在点を作る（expand で処理）。
    collect(
        r"(?:点\s*)?([A-Z])\s*における\s*(?:円|外接円)\s*(?:の)?\s*接線\s*上\s*の\s*点" + LET,
        lambda m: TypedPredicate("tangent_at", (m.group(1).lower(), m.group(2).lower()), m.group(0)),
    )
    collect(
        r"(?:点\s*)?([A-Z])\s*における\s*(?:円|外接円)\s*(?:の)?\s*接線\s*と\s*(?:直線|線分)?\s*"
        r"([A-Z])\s*([A-Z])\s*の\s*交点" + LET,
        lambda m: [
            TypedPredicate("tangent_at", (m.group(1).lower(), m.group(4).lower()), m.group(0)),
            TypedPredicate("coll", (m.group(2).lower(), m.group(4).lower(), m.group(3).lower()), m.group(0)),
        ],
    )
    # 中心が名指しされている場合は、その場で垂直にできる
    collect(
        r"(?:直線|線分)?\s*([A-Z])\s*([A-Z])\s*(?:は|が)\s*(?:中心\s*)?([A-Z])\s*(?:の|を中心とする)\s*円\s*に\s*"
        r"(?:点\s*)?([A-Z])\s*で\s*接する",
        lambda m: [
            TypedPredicate("coll", (m.group(1).lower(), m.group(4).lower(), m.group(2).lower()), m.group(0)),
            TypedPredicate("perp", (m.group(1).lower(), m.group(2).lower(),
                                    m.group(3).lower(), m.group(4).lower()), m.group(0)),
        ],
    )

    # ── 角の二等分線 ──────────────────────────────────────────
    collect(
        r"(?:∠|角)\s*([A-Z])([A-Z])([A-Z])\s*の\s*(?:二等分線|2等分線)\s*と\s*(?:直線|辺|線分)?\s*"
        r"([A-Z])\s*([A-Z])\s*の\s*交点" + LET,
        lambda m: [
            TypedPredicate("eqangle", (
                m.group(2).lower(), m.group(1).lower(), m.group(2).lower(), m.group(6).lower(),
                m.group(2).lower(), m.group(6).lower(), m.group(2).lower(), m.group(3).lower()), m.group(0)),
            TypedPredicate("coll", (m.group(4).lower(), m.group(6).lower(), m.group(5).lower()), m.group(0)),
        ],
    )
    collect(
        r"(?:∠|角)\s*([A-Z])([A-Z])([A-Z])\s*の\s*(?:二等分線|2等分線)\s*上\s*の\s*点" + LET,
        lambda m: TypedPredicate("eqangle", (
            m.group(2).lower(), m.group(1).lower(), m.group(2).lower(), m.group(4).lower(),
            m.group(2).lower(), m.group(4).lower(), m.group(2).lower(), m.group(3).lower()), m.group(0)),
    )

    # ── 内分・外分・延長 ──────────────────────────────────────
    collect(
        r"(?:線分|辺)?\s*([A-Z])\s*([A-Z])\s*を\s*(\d+)\s*:\s*(\d+)\s*に\s*内分\s*する\s*点" + LET,
        lambda m: [
            TypedPredicate("coll", (m.group(1).lower(), m.group(5).lower(), m.group(2).lower()), m.group(0)),
            TypedPredicate("rconst", (m.group(1).lower(), m.group(5).lower(),
                                      m.group(5).lower(), m.group(2).lower()), m.group(0),
                           (normalize_constant(f"{m.group(3)}/{m.group(4)}"),)),
        ],
    )
    collect(
        r"(?:直線|線分|辺)?\s*([A-Z])\s*([A-Z])\s*の\s*([A-Z])\s*を?\s*越えた?\s*延長\s*(?:線)?\s*上\s*の\s*点" + LET,
        lambda m: TypedPredicate(
            "coll", (m.group(1).lower(), m.group(2).lower(), m.group(4).lower()), m.group(0)),
    )
    collect(
        r"(?:直線|線分|辺)?\s*([A-Z])\s*([A-Z])\s*の\s*延長\s*(?:線)?\s*上\s*の\s*点" + LET,
        lambda m: TypedPredicate(
            "coll", (m.group(1).lower(), m.group(2).lower(), m.group(3).lower()), m.group(0)),
    )
    collect(
        r"(?:直線|線分|辺)?\s*([A-Z])\s*([A-Z])\s*上\s*の\s*点" + LET,
        lambda m: TypedPredicate(
            "coll", (m.group(1).lower(), m.group(3).lower(), m.group(2).lower()), m.group(0)),
    )

    # ── 特別な三角形・四角形 ──────────────────────────────────
    collect(
        r"(?:AB\s*=\s*AC\s*(?:である|の)?\s*)?二等辺三角形\s*([A-Z])\s*([A-Z])\s*([A-Z])",
        lambda m: TypedPredicate(
            "cong", (m.group(1).lower(), m.group(2).lower(),
                     m.group(1).lower(), m.group(3).lower()), m.group(0)),
    )
    collect(
        r"正三角形\s*([A-Z])\s*([A-Z])\s*([A-Z])",
        lambda m: [
            TypedPredicate("cong", (m.group(1).lower(), m.group(2).lower(),
                                    m.group(2).lower(), m.group(3).lower()), m.group(0)),
            TypedPredicate("cong", (m.group(2).lower(), m.group(3).lower(),
                                    m.group(3).lower(), m.group(1).lower()), m.group(0)),
        ],
    )
    collect(
        r"平行四辺形\s*([A-Z])\s*([A-Z])\s*([A-Z])\s*([A-Z])",
        lambda m: [
            TypedPredicate("para", (m.group(1).lower(), m.group(2).lower(),
                                    m.group(4).lower(), m.group(3).lower()), m.group(0)),
            TypedPredicate("para", (m.group(1).lower(), m.group(4).lower(),
                                    m.group(2).lower(), m.group(3).lower()), m.group(0)),
            TypedPredicate("cong", (m.group(1).lower(), m.group(2).lower(),
                                    m.group(4).lower(), m.group(3).lower()), m.group(0)),
        ],
    )
    collect(
        r"(?:長方形|矩形)\s*([A-Z])\s*([A-Z])\s*([A-Z])\s*([A-Z])",
        lambda m: [
            TypedPredicate("para", (m.group(1).lower(), m.group(2).lower(),
                                    m.group(4).lower(), m.group(3).lower()), m.group(0)),
            TypedPredicate("perp", (m.group(1).lower(), m.group(2).lower(),
                                    m.group(2).lower(), m.group(3).lower()), m.group(0)),
            TypedPredicate("perp", (m.group(2).lower(), m.group(3).lower(),
                                    m.group(3).lower(), m.group(4).lower()), m.group(0)),
        ],
    )
    collect(
        r"正方形\s*([A-Z])\s*([A-Z])\s*([A-Z])\s*([A-Z])",
        lambda m: [
            TypedPredicate("perp", (m.group(1).lower(), m.group(2).lower(),
                                    m.group(2).lower(), m.group(3).lower()), m.group(0)),
            TypedPredicate("perp", (m.group(2).lower(), m.group(3).lower(),
                                    m.group(3).lower(), m.group(4).lower()), m.group(0)),
            TypedPredicate("cong", (m.group(1).lower(), m.group(2).lower(),
                                    m.group(2).lower(), m.group(3).lower()), m.group(0)),
            TypedPredicate("cong", (m.group(2).lower(), m.group(3).lower(),
                                    m.group(3).lower(), m.group(4).lower()), m.group(0)),
        ],
    )
    collect(
        r"(?:ひし形|菱形)\s*([A-Z])\s*([A-Z])\s*([A-Z])\s*([A-Z])",
        lambda m: [
            TypedPredicate("cong", (m.group(1).lower(), m.group(2).lower(),
                                    m.group(2).lower(), m.group(3).lower()), m.group(0)),
            TypedPredicate("cong", (m.group(2).lower(), m.group(3).lower(),
                                    m.group(3).lower(), m.group(4).lower()), m.group(0)),
            TypedPredicate("para", (m.group(1).lower(), m.group(2).lower(),
                                    m.group(4).lower(), m.group(3).lower()), m.group(0)),
        ],
    )

    # ── 比と角度を語で ────────────────────────────────────────
    collect(
        segment + r"\s*(?::|：)\s*" + segment + r"\s*=\s*(\d+)\s*(?::|：)\s*(\d+)",
        lambda m: TypedPredicate(
            "rconst", tuple(v.lower() for v in m.groups()[:4]), m.group(0),
            (normalize_constant(f"{m.group(5)}/{m.group(6)}"),)),
    )
    collect(
        r"(?:∠|角)\s*([A-Z])([A-Z])([A-Z])\s*(?:は|が|=)\s*" + scalar + r"\s*(?:°|度)",
        lambda m: constant_angle_predicate(m.groups(), m.group(0)),
    )

    # ── 直角三角形・対称点 ────────────────────────────────────
    # 「∠A=90°である直角三角形ABC」。直角の位置は明示されなければ最初の頂点。
    collect(
        r"(?:∠|角)\s*([A-Z])\s*=?\s*(?:90|\{90\})\s*°?\s*(?:である|の)?\s*直角三角形\s*"
        r"([A-Z])\s*([A-Z])\s*([A-Z])",
        lambda m: right_angle_at(m.group(1), (m.group(2), m.group(3), m.group(4)), m.group(0)),
    )
    collect(
        r"直角三角形\s*([A-Z])\s*([A-Z])\s*([A-Z])",
        lambda m: right_angle_at(m.group(1), (m.group(1), m.group(2), m.group(3)), m.group(0)),
    )
    # 「BC に関する D の対称点を F」。折り返しは垂直二等分線の言い換え。
    collect(
        r"(?:直線|線分|辺)?\s*([A-Z])\s*([A-Z])\s*に関(?:する|し(?:て)?)\s*(?:点\s*)?([A-Z])\s*"
        r"(?:と|の)\s*対称(?:な)?(?:点|な点)" + LET,
        lambda m: [
            # 対称点は、軸からの距離が等しく、結ぶ線が軸に垂直
            TypedPredicate("cong", (m.group(1).lower(), m.group(3).lower(),
                                    m.group(1).lower(), m.group(4).lower()), m.group(0)),
            TypedPredicate("cong", (m.group(2).lower(), m.group(3).lower(),
                                    m.group(2).lower(), m.group(4).lower()), m.group(0)),
            TypedPredicate("perp", (m.group(3).lower(), m.group(4).lower(),
                                    m.group(1).lower(), m.group(2).lower()), m.group(0)),
        ],
    )

    # ── 四角形の種類を結論として言う ──────────────────────────
    # 「四辺形ABCDは平行四辺形であること」。前提としては読めていたが結論として読めず、
    # 結論の述語が0本になって落ちていた。
    collect(
        r"(?:四辺形|四角形)\s*([A-Z])\s*([A-Z])\s*([A-Z])\s*([A-Z])\s*(?:は|が)\s*平行四辺形",
        lambda m: [
            TypedPredicate("para", (m.group(1).lower(), m.group(2).lower(),
                                    m.group(4).lower(), m.group(3).lower()), m.group(0)),
            TypedPredicate("para", (m.group(1).lower(), m.group(4).lower(),
                                    m.group(2).lower(), m.group(3).lower()), m.group(0)),
        ],
    )
    collect(
        r"(?:四辺形|四角形)\s*([A-Z])\s*([A-Z])\s*([A-Z])\s*([A-Z])\s*(?:は|が)\s*(?:ひし形|菱形)",
        lambda m: [
            TypedPredicate("cong", (m.group(1).lower(), m.group(2).lower(),
                                    m.group(2).lower(), m.group(3).lower()), m.group(0)),
            TypedPredicate("cong", (m.group(2).lower(), m.group(3).lower(),
                                    m.group(3).lower(), m.group(4).lower()), m.group(0)),
        ],
    )
    collect(
        r"(?:四辺形|四角形)\s*([A-Z])\s*([A-Z])\s*([A-Z])\s*([A-Z])\s*(?:は|が)\s*(?:長方形|矩形)",
        lambda m: [
            TypedPredicate("perp", (m.group(1).lower(), m.group(2).lower(),
                                    m.group(2).lower(), m.group(3).lower()), m.group(0)),
            TypedPredicate("perp", (m.group(2).lower(), m.group(3).lower(),
                                    m.group(3).lower(), m.group(4).lower()), m.group(0)),
        ],
    )

    # 「EF は DC に平行」の形。「EF と DC は平行」しか読めないと半分落ちる。
    collect(
        LINE + segment + r"\s*(?:は|が)\s*" + LINE + segment + r"\s*に\s*(?:垂直|直交)",
        lambda m: predicate("perp", m.groups(), m.group(0)),
    )
    collect(
        LINE + segment + r"\s*(?:は|が)\s*" + LINE + segment + r"\s*に\s*平行",
        lambda m: predicate("para", m.groups(), m.group(0)),
    )

    # 語で書かれた関係。記号（⊥ ∥）しか読めないと、結論部が落ちる。
    # 線分名の前の「直線」「線分」を許す。ここが無いだけで結論が読めない問題が多い。
    collect(
        LINE + segment + r"\s*と\s*" + LINE + segment + r"\s*(?:は|が)?\s*(?:互いに)?\s*(?:垂直|直交)",
        lambda m: predicate("perp", m.groups(), m.group(0)),
    )
    collect(
        LINE + segment + r"\s*と\s*" + LINE + segment + r"\s*(?:は|が)?\s*平行",
        lambda m: predicate("para", m.groups(), m.group(0)),
    )
    collect(
        LINE + segment + r"\s*と\s*" + LINE + segment + r"\s*(?:の長さ)?\s*(?:は|が)?\s*等しい",
        lambda m: predicate("cong", m.groups(), m.group(0)),
    )
    collect(
        r"∠\s*([A-Z])([A-Z])([A-Z])\s*と\s*∠\s*([A-Z])([A-Z])([A-Z])\s*(?:は|が)?\s*等しい",
        lambda m: angle_predicate(m.groups(), m.group(0)),
    )
    collect(
        r"(?:角|∠)\s*([A-Z])([A-Z])([A-Z])\s*と\s*(?:角|∠)\s*([A-Z])([A-Z])([A-Z])\s*(?:は|が)?\s*等しい",
        lambda m: angle_predicate(m.groups(), m.group(0)),
    )

    for match in re.finditer(r"([A-Z](?:\s*[,、]\s*[A-Z]){2,})\s*(?:は|are)?\s*(?:同一)?(?:一直線上|直線上|collinear)", text):
        names = tuple(point.lower() for point in re.findall(r"[A-Z]", match.group(1)))
        for triple in itertools.combinations(names, 3):
            predicates.append(TypedPredicate("coll", triple, match.group(0)))
        spans.append(match.span())
    for match in re.finditer(r"([A-Z](?:\s*[,、]\s*[A-Z]){3,})\s*(?:は|are)?\s*(?:同一円周上|concyclic|cyclic)", text):
        names = tuple(point.lower() for point in re.findall(r"[A-Z]", match.group(1)))
        for quadruple in itertools.combinations(names, 4):
            predicates.append(TypedPredicate("cyclic", quadruple, match.group(0)))
        spans.append(match.span())
    return predicates, merge_spans(spans)


def predicate(name: str, groups: Iterable[str], source: str) -> TypedPredicate:
    return TypedPredicate(name, tuple(value.lower() for value in groups), source)


def right_angle_at(vertex: str, triangle: tuple[str, str, str], source: str) -> TypedPredicate:
    """直角三角形。直角の頂点から出る二辺が直交する"""
    v = vertex.lower()
    others = [p.lower() for p in triangle if p.lower() != v]
    if len(others) != 2:
        others = [p.lower() for p in triangle[1:]]
        v = triangle[0].lower()
    return TypedPredicate("perp", (v, others[0], v, others[1]), source)


def angle_predicate(groups: Iterable[str], source: str) -> TypedPredicate:
    a, b, c, d, e, f = (value.lower() for value in groups)
    return TypedPredicate("eqangle", (b, a, b, c, e, d, e, f), source)


def constant_angle_predicate(groups: Iterable[str], source: str) -> TypedPredicate:
    a, b, c, value = groups
    return TypedPredicate(
        "s_angle",
        (b.lower(), a.lower(), b.lower(), c.lower()),
        source,
        (normalize_constant(value),),
    )


def midpoint_predicates(groups: Iterable[str], source: str) -> list[TypedPredicate]:
    midpoint, a, b = (value.lower() for value in groups)
    return [
        TypedPredicate("coll", (a, midpoint, b), source),
        TypedPredicate("cong", (a, midpoint, midpoint, b), source),
    ]


def circumcenter_predicates(groups: Iterable[str], source: str) -> list[TypedPredicate]:
    center, a, b, c = (value.lower() for value in groups)
    return [
        TypedPredicate("cong", (center, a, center, b), source),
        TypedPredicate("cong", (center, b, center, c), source),
    ]


def centroid_predicates(groups: Iterable[str], source: str) -> list[TypedPredicate]:
    center, a, b, c = (value.lower() for value in groups)
    # Affine centroid is encoded as two additive vector equations during diagram
    # construction. AG2 has no primitive centroid predicate, so do not emit an
    # unsound DDAR premise here.
    return [TypedPredicate("centroid", (center, a, b, c), source)]


def intersection_predicates(groups: Iterable[str], source: str) -> list[TypedPredicate]:
    point, a, b, c, d = (value.lower() for value in groups)
    return [
        TypedPredicate("coll", (a, point, b), source),
        TypedPredicate("coll", (c, point, d), source),
    ]


def tangent_predicate(groups: Iterable[str], source: str) -> TypedPredicate:
    a, b, contact, center = (value.lower() for value in groups)
    return TypedPredicate("perp", (a, b, center, contact), source)


def orthocenter_predicates(groups: Iterable[str], source: str) -> list[TypedPredicate]:
    center, a, b, c = (value.lower() for value in groups)
    return [
        TypedPredicate("perp", (a, center, b, c), source),
        TypedPredicate("perp", (b, center, a, c), source),
    ]


def incenter_predicates(groups: Iterable[str], source: str) -> list[TypedPredicate]:
    center, a, b, c = (value.lower() for value in groups)
    return [
        TypedPredicate("eqangle", (a, b, a, center, a, center, a, c), source),
        TypedPredicate("eqangle", (b, c, b, center, b, center, b, a), source),
    ]


def expand_derived_predicates(
    predicates: list[TypedPredicate],
    triangles: list[tuple[str, str, str]],
) -> list[TypedPredicate]:
    existing = {point for predicate_item in predicates for point in predicate_item.points}
    existing.update(point for triangle in triangles for point in triangle)

    # 既に「BC の中点」として名前が付いている点があるなら、それを使う。
    # 重心の展開で別名を作ると、同じ点が二つの名前を持ち、
    # 数値作図が退化して解けなくなる（「重心をG、BCの中点をM」で実際に落ちた）。
    named_midpoints: dict[frozenset[str], str] = {}
    for item in predicates:
        if item.name != "cong":
            continue
        p, m1, m2, q = item.points
        if m1 == m2 and p != q and any(
            other.name == "coll" and set(other.points) == {p, m1, q} for other in predicates
        ):
            named_midpoints[frozenset((p, q))] = m1

    # 外接円の中心。文中に名前が無くても、接線を書くには中心が要る。
    # 一度だけ作って使い回す（二つ作ると同じ点が二名になり作図が退化する）。
    circumcenter_of: dict[tuple[str, ...], str] = {}
    for item in predicates:
        if item.name != "cong":
            continue
        o, p, o2, q = item.points
        if o == o2 and p != q:
            circumcenter_of.setdefault(tuple(sorted((p, q))), o)

    def circle_center(triangle: tuple[str, str, str]) -> str | None:
        """三角形の外接円の中心。既にあればそれ、無ければ作る"""
        a, b, c = triangle
        for pair in (tuple(sorted((a, b))), tuple(sorted((b, c))), tuple(sorted((a, c)))):
            if pair in circumcenter_of:
                return circumcenter_of[pair]
        name = unused_point_name(existing, "o_circ")
        existing.add(name)
        for pair in (tuple(sorted((a, b))), tuple(sorted((b, c))), tuple(sorted((a, c)))):
            circumcenter_of[pair] = name
        return name

    expanded: list[TypedPredicate] = []
    for item in predicates:
        if item.name == "tangent_at":
            # 「A における接線上の点 T」→ 中心 O について OA ⊥ AT。
            # 接線という対象を持たずに、接線であることの内容だけを持つ。
            contact, outer = item.points
            triangle = next((t for t in triangles if contact in t), None)
            if triangle is None:
                expanded.append(item)  # 円が特定できない。未対応として残す
                continue
            center = circle_center(triangle)
            if center is None:
                expanded.append(item)
                continue
            a, b, c = triangle
            expanded.extend((
                TypedPredicate("cong", (center, a, center, b), item.source),
                TypedPredicate("cong", (center, b, center, c), item.source),
                TypedPredicate("perp", (center, contact, contact, outer), item.source),
            ))
            continue
        if item.name != "centroid":
            expanded.append(item)
            continue
        center, a, b, c = item.points
        midpoint = named_midpoints.get(frozenset((b, c)))
        if midpoint is None:
            midpoint = unused_point_name(existing, f"{center}_mid_{b}{c}")
            named_midpoints[frozenset((b, c))] = midpoint
        existing.add(midpoint)
        expanded.extend((
            TypedPredicate("coll", (b, midpoint, c), item.source),
            TypedPredicate("cong", (b, midpoint, midpoint, c), item.source),
            TypedPredicate("coll", (a, center, midpoint), item.source),
            TypedPredicate("rconst", (a, center, center, midpoint), item.source, ("2",)),
            TypedPredicate("distseq", (a, center, center, midpoint, a, midpoint), item.source, ("1", "1", "-1")),
        ))
    return expanded


def unused_point_name(existing: set[str], seed: str) -> str:
    if seed not in existing:
        return seed
    ordinal = 2
    while f"{seed}_{ordinal}" in existing:
        ordinal += 1
    return f"{seed}_{ordinal}"


def normalize_constant(value: str) -> str:
    fraction = Fraction(value)
    return str(fraction.numerator) if fraction.denominator == 1 else f"{fraction.numerator}/{fraction.denominator}"


def predicate_type_issue(item: TypedPredicate) -> str | None:
    arities = {
        "coll": (3, 0), "cyclic": (4, 0), "perp": (4, 0), "para": (4, 0),
        "cong": (4, 0), "eqangle": (8, 0), "rconst": (4, 1),
        "eqratio": (8, 0), "s_angle": (4, 1), "distseq": (6, 3),
    }
    expected = arities.get(item.name)
    if expected is None:
        return None
    if (len(item.points), len(item.constants)) != expected:
        return f"expected {expected[0]} points and {expected[1]} constants"
    if item.name == "coll" and len(set(item.points)) < 3:
        return "collinearity requires three distinct points"
    if item.name == "cyclic" and len(set(item.points)) < 4:
        return "cyclicity requires four distinct points"
    if item.name in {"perp", "para", "cong", "eqangle", "rconst", "eqratio", "s_angle", "distseq"}:
        for index in range(0, len(item.points), 2):
            if item.points[index] == item.points[index + 1]:
                return "a directed segment has identical endpoints"
    return None


def unresolved_relation_fragments(text: str, consumed: list[tuple[int, int]]) -> list[str]:
    remainder = list(text)
    for start, end in consumed:
        remainder[start:end] = " " * (end - start)
    value = "".join(remainder)
    markers = (
        "⊥", "∥", "//", "∠", "=", "比", "円", "中点", "外心", "重心", "垂心", "内心", "傍心",
        "一直線", "同一円周", "交点", "接する", "上にある", "perpendicular", "parallel",
        "midpoint", "circumcenter", "centroid", "orthocenter", "incenter", "excenter", "intersection",
        "tangent", "collinear", "cyclic",
    )
    return [marker for marker in markers if marker.lower() in value.lower()]


def deduplicate_predicates(predicates: list[TypedPredicate]) -> list[TypedPredicate]:
    result: list[TypedPredicate] = []
    seen: set[tuple[str, tuple[str, ...], tuple[str, ...]]] = set()
    for item in predicates:
        key = (item.name, item.points, item.constants)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if result and start <= result[-1][1]:
            result[-1] = (result[-1][0], max(result[-1][1], end))
        else:
            result.append((start, end))
    return result


def construct_diagram(
    points: list[str],
    constraints: list[TypedPredicate],
    triangles: list[tuple[str, str, str]],
    *,
    seed_text: str,
    max_restarts: int,
) -> tuple[dict[str, tuple[float, float]], float | None, int]:
    if len(points) < 2:
        return {}, None, 0
    seed = int(hashlib.sha256(seed_text.encode("utf-8")).hexdigest()[:16], 16)
    rng = np.random.default_rng(seed)
    best: tuple[float, np.ndarray] | None = None

    def unpack(vector: np.ndarray) -> dict[str, np.ndarray]:
        coordinates = {points[0]: np.asarray([0.0, 0.0]), points[1]: np.asarray([4.0, 0.0])}
        for offset, name in enumerate(points[2:]):
            coordinates[name] = vector[2 * offset:2 * offset + 2]
        return coordinates

    def residuals(vector: np.ndarray) -> np.ndarray:
        coordinates = unpack(vector)
        values = [predicate_residual(item, coordinates) for item in constraints]
        for a, b, c in triangles:
            if all(name in coordinates for name in (a, b, c)):
                area = abs(cross2d(coordinates[b] - coordinates[a], coordinates[c] - coordinates[a]))
                values.append(max(0.0, 0.8 - area))
                # 面積の下限だけでは、長く細い三角形が通ってしまう。
                # 各頂点で sin(角) に下限を置くと、形そのものが縛られる。
                # 0.42 ≈ sin 25°。これ未満の角を持つ図は、そもそも解として出さない。
                for u, v, w in ((a, b, c), (b, c, a), (c, a, b)):
                    e1 = coordinates[v] - coordinates[u]
                    e2 = coordinates[w] - coordinates[u]
                    n1 = float(np.linalg.norm(e1))
                    n2 = float(np.linalg.norm(e2))
                    if n1 < 1e-9 or n2 < 1e-9:
                        values.append(1.0)
                        continue
                    sine = abs(cross2d(e1, e2)) / (n1 * n2)
                    values.append(max(0.0, 0.42 - sine))
        for left, right in itertools.combinations(points, 2):
            if any(item.name == "overlap" and {left, right} == set(item.points) for item in constraints):
                continue
            distance = float(np.linalg.norm(coordinates[left] - coordinates[right]))
            values.append(max(0.0, 0.12 - distance))
        return np.asarray(values, dtype=float)

    variable_count = max(0, 2 * (len(points) - 2))
    # 制約を満たす解は一つではない。最初に見つかった解を返すと、
    # 条件は満たすが人には読めない図（つぶれた三角形、重なったラベル）が出る。
    # 厳密解を集めてから、読みやすさで選ぶ。
    exact: list[tuple[float, np.ndarray, int]] = []
    for restart in range(1, max_restarts + 1):
        initial = rng.normal(0.0, 2.5, size=variable_count)
        solved = least_squares(residuals, initial, max_nfev=3000, ftol=1e-13, xtol=1e-13, gtol=1e-13)
        if residuals(solved.x).size >= variable_count and variable_count:
            solved = least_squares(
                residuals,
                solved.x,
                method="lm",
                max_nfev=10000,
                ftol=1e-15,
                xtol=1e-15,
                gtol=1e-15,
            )
        error = float(np.max(np.abs(residuals(solved.x)))) if residuals(solved.x).size else 0.0
        if best is None or error < best[0]:
            best = (error, solved.x.copy())
        if error <= 1e-14:
            exact.append((error, solved.x.copy(), restart))
            if len(exact) >= 24:
                break

    if exact:
        scored = max(exact, key=lambda item: diagram_legibility(unpack(item[1]), points, triangles))
        coordinates = unpack(scored[1])
        return (
            {name: (float(value[0]), float(value[1])) for name, value in coordinates.items()},
            scored[0],
            scored[2],
        )
    if best is None or best[0] > 5e-14:
        return {}, best[0] if best else None, max_restarts
    coordinates = unpack(best[1])
    return {name: (float(value[0]), float(value[1])) for name, value in coordinates.items()}, best[0], max_restarts


def diagram_legibility(
    coordinates: dict[str, np.ndarray],
    points: list[str],
    triangles: list[tuple[str, str, str]],
) -> float:
    """図の読みやすさ。大きいほど良い。

    美しさを学習する前に、決定的に測れるものを測る。
      - 三角形の最小角     つぶれた三角形を避ける
      - 点どうしの最小距離   ラベルの重なりを避ける
      - 外接箱の縦横比      細長い図は縦動画で小さくなる
    どれも図の大きさに依らないよう、正規化してある。
    """
    names = [name for name in points if name in coordinates]
    if len(names) < 3:
        return 0.0
    xy = np.asarray([coordinates[name] for name in names], dtype=float)

    span_x = float(xy[:, 0].max() - xy[:, 0].min())
    span_y = float(xy[:, 1].max() - xy[:, 1].min())
    diagonal = float(np.hypot(span_x, span_y))
    if diagonal < 1e-9:
        return 0.0

    # 縦横比。1 に近いほど紙面を使い切れる
    aspect = min(span_x, span_y) / max(span_x, span_y) if max(span_x, span_y) > 1e-9 else 0.0

    # 点どうしが近すぎるとラベルが重なる
    gaps = [
        float(np.linalg.norm(xy[i] - xy[j])) / diagonal
        for i in range(len(names))
        for j in range(i + 1, len(names))
    ]
    separation = min(gaps) if gaps else 0.0

    # 三角形がつぶれていないか。最小角をラジアンで
    smallest_angle = np.pi
    for a, b, c in triangles:
        if not all(name in coordinates for name in (a, b, c)):
            continue
        pa, pb, pc = (coordinates[a], coordinates[b], coordinates[c])
        for u, v, w in ((pa, pb, pc), (pb, pc, pa), (pc, pa, pb)):
            e1, e2 = v - u, w - u
            n1, n2 = float(np.linalg.norm(e1)), float(np.linalg.norm(e2))
            if n1 < 1e-9 or n2 < 1e-9:
                return 0.0
            cosine = float(np.clip(np.dot(e1, e2) / (n1 * n2), -1.0, 1.0))
            smallest_angle = min(smallest_angle, float(np.arccos(cosine)))
    # 正三角形（60°）で 1、つぶれると 0
    angle_score = min(1.0, smallest_angle / (np.pi / 3)) if triangles else 1.0

    # 鈍角三角形は垂心や外心が外に出る。数学は正しくても図は読みにくいので、
    # 同じ制約を満たす解が複数あるなら鋭角の方を採る。
    acute = 1.0
    for a, b, c in triangles:
        if not all(name in coordinates for name in (a, b, c)):
            continue
        pa, pb, pc = (coordinates[a], coordinates[b], coordinates[c])
        for u, v, w in ((pa, pb, pc), (pb, pc, pa), (pc, pa, pb)):
            e1, e2 = v - u, w - u
            if float(np.dot(e1, e2)) < 0.0:
                acute = 0.0

    return 3.0 * angle_score + 2.0 * separation + 1.0 * aspect + 1.5 * acute


def predicate_residual(item: TypedPredicate, coordinates: dict[str, np.ndarray]) -> float:
    p = [coordinates[name] for name in item.points]
    if item.name == "coll":
        return cross2d(p[1] - p[0], p[2] - p[0]) / 16.0
    if item.name == "para":
        return cross2d(p[1] - p[0], p[3] - p[2]) / 16.0
    if item.name == "perp":
        return float((p[1] - p[0]) @ (p[3] - p[2])) / 16.0
    if item.name == "cong":
        return (squared_distance(p[0], p[1]) - squared_distance(p[2], p[3])) / 16.0
    if item.name == "eqangle":
        u, v = p[1] - p[0], p[3] - p[2]
        w, z = p[5] - p[4], p[7] - p[6]
        return (cross2d(u, v) * float(w @ z) - float(u @ v) * cross2d(w, z)) / 256.0
    if item.name == "cyclic":
        matrix = np.asarray([[point[0], point[1], point @ point, 1.0] for point in p])
        return float(np.linalg.det(matrix)) / 256.0
    if item.name == "rconst":
        ratio = float(Fraction(item.constants[0]))
        return (squared_distance(p[0], p[1]) - ratio * ratio * squared_distance(p[2], p[3])) / 16.0
    if item.name == "eqratio":
        left_num = squared_distance(p[0], p[1])
        left_den = squared_distance(p[2], p[3])
        right_num = squared_distance(p[4], p[5])
        right_den = squared_distance(p[6], p[7])
        return (left_num * right_den - right_num * left_den) / 256.0
    if item.name == "s_angle":
        angle = np.deg2rad(float(Fraction(item.constants[0])))
        u, v = p[1] - p[0], p[3] - p[2]
        # DDAR encodes dir(u) - dir(v) = angle, modulo 180 degrees.
        return (cross2d(u, v) * np.cos(angle) + float(u @ v) * np.sin(angle)) / 16.0
    if item.name == "distseq":
        return sum(
            float(Fraction(coef)) * float(np.linalg.norm(p[2 * index] - p[2 * index + 1]))
            for index, coef in enumerate(item.constants)
        ) / 4.0
    if item.name == "centroid":
        center, a, b, c = p
        delta = center - (a + b + c) / 3
        return float(np.linalg.norm(delta))
    raise ValueError(f"unsupported numerical predicate: {item.name}")


def squared_distance(a: np.ndarray, b: np.ndarray) -> float:
    delta = a - b
    return float(delta @ delta)


def cross2d(a: np.ndarray, b: np.ndarray) -> float:
    return float(a[0] * b[1] - a[1] * b[0])


def render_formal_problem(
    points: list[str],
    coordinates: dict[str, tuple[float, float]],
    predicates: list[TypedPredicate],
    goal: TypedPredicate,
) -> str:
    declarations = []
    executable = [item for item in predicates if item.name in RELATION_SYMBOLS]
    for index, name in enumerate(points):
        x, y = coordinates[name]
        suffix = ", ".join(item.render() for item in executable) if index == len(points) - 1 else ""
        declarations.append(f"{name}@{format_number(x)}_{format_number(y)} = {suffix}")
    return "; ".join(declarations) + " ? " + goal.render()


def format_number(value: float) -> str:
    if abs(value) < 1e-12:
        value = 0.0
    return f"{value:.17g}"
