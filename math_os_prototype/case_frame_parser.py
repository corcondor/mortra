"""Small case-frame parser for math Japanese.

This layer is not a statistical Japanese parser.  It treats particles as typed
slot markers and compiles common mathematical predicates into inspectable
relations.  Unknown phrases are left as chunks instead of being guessed.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any


PARTICLES = ("から", "まで", "より", "に対して", "について", "上に", "が", "は", "を", "に", "で", "の", "と")


@dataclass(frozen=True)
class Bunsetsu:
    text: str
    head: str
    particle: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CaseFrame:
    predicate: str
    relation: str
    slots: dict[str, str]
    logic: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CaseFrameIR:
    source_text: str
    normalized_text: str
    bunsetsu: list[Bunsetsu]
    frames: list[CaseFrame]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["bunsetsu"] = [item.to_dict() for item in self.bunsetsu]
        payload["frames"] = [item.to_dict() for item in self.frames]
        return payload


def parse_case_frames(text: str) -> CaseFrameIR:
    normalized = normalize_math_japanese(text)
    bunsetsu = split_bunsetsu(normalized)
    frames = infer_frames(normalized, bunsetsu)
    warnings = []
    if not frames and any(particle in normalized for particle in PARTICLES):
        warnings.append("Particles were found, but no mathematical case frame matched.")
    return CaseFrameIR(
        source_text=text,
        normalized_text=normalized,
        bunsetsu=bunsetsu,
        frames=frames,
        warnings=warnings,
    )


def normalize_math_japanese(text: str) -> str:
    text = text.replace("，", "、").replace("．", "。")
    text = text.replace("−", "-").replace("　", " ")
    text = re.sub(r"\\text\{([^{}]*)\}", r" \1 ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def split_bunsetsu(text: str) -> list[Bunsetsu]:
    parts = [part.strip() for part in re.split(r"[、。,.]\s*", text) if part.strip()]
    result: list[Bunsetsu] = []
    for part in parts:
        # Keep TeX/math spans as heads when they attach to a Japanese particle.
        for segment in re.split(r"\s+", part):
            if not segment:
                continue
            result.extend(split_segment(segment))
    return result


def split_segment(segment: str) -> list[Bunsetsu]:
    items: list[Bunsetsu] = []
    cursor = 0
    pattern = re.compile(r"(.+?)(に対して|について|から|まで|より|上に|が|は|を|に|で|の|と)(?=.+|$)")
    for match in pattern.finditer(segment):
        head = segment[match.start(1) : match.end(1)].strip()
        particle = match.group(2)
        if head:
            items.append(Bunsetsu(text=head + particle, head=head, particle=particle))
        cursor = match.end()
    tail = segment[cursor:].strip()
    if tail:
        items.append(Bunsetsu(text=tail, head=tail, particle=None))
    return items


def infer_frames(text: str, bunsetsu: list[Bunsetsu]) -> list[CaseFrame]:
    frames: list[CaseFrame] = []
    frames.extend(infer_satisfies_frames(text))
    frames.extend(infer_query_frames(text))
    frames.extend(infer_prove_frames(text))
    frames.extend(infer_on_frames(text))
    frames.extend(infer_interval_frames(text))
    frames.extend(infer_quantifier_frames(text))
    return unique_frames(frames)


def infer_satisfies_frames(text: str) -> list[CaseFrame]:
    frames = []
    for match in re.finditer(r"(?P<object>[^、。]+?)が(?P<condition>[^、。]+?)を満たす", text):
        obj = clean_phrase(match.group("object"))
        condition = clean_phrase(match.group("condition"))
        frames.append(
            CaseFrame(
                predicate="満たす",
                relation="Satisfies",
                slots={"が": obj, "を": condition},
                logic=f"(Satisfies {atom(obj)} {atom(condition)})",
            )
        )
    return frames


def infer_query_frames(text: str) -> list[CaseFrame]:
    frames = []
    for match in re.finditer(r"(?P<target>[^、。]+?)を(?:すべて)?求めよ", text):
        target = clean_phrase(match.group("target"))
        frames.append(
            CaseFrame(
                predicate="求めよ",
                relation="Query",
                slots={"を": target},
                logic=f"(Query {atom(target)})",
            )
        )
    return frames


def infer_prove_frames(text: str) -> list[CaseFrame]:
    if "示せ" not in text and "証明" not in text:
        return []
    statement = clean_phrase(re.sub(r"(ことを)?示せ.*$", "", text))
    if not statement:
        statement = "goal"
    return [
        CaseFrame(
            predicate="示せ",
            relation="Prove",
            slots={"goal": statement},
            logic=f"(Prove {atom(statement)})",
        )
    ]


def infer_on_frames(text: str) -> list[CaseFrame]:
    frames = []
    patterns = (
        r"(?P<object>[^、。]+?)が(?P<support>[^、。]+?)上にある",
        r"(?P<support>[^、。]+?)上の(?P<object>[^、。]+)",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            obj = clean_phrase(match.group("object"))
            support = clean_phrase(match.group("support"))
            frames.append(
                CaseFrame(
                    predicate="上にある",
                    relation="On",
                    slots={"が": obj, "上に": support},
                    logic=f"(On {atom(obj)} {atom(support)})",
                )
            )
    return frames


def infer_interval_frames(text: str) -> list[CaseFrame]:
    frames = []
    for match in re.finditer(r"(?P<start>[^、。]+?)から(?P<end>[^、。]+?)まで", text):
        start = clean_phrase(match.group("start"))
        end = clean_phrase(match.group("end"))
        frames.append(
            CaseFrame(
                predicate="から-まで",
                relation="Interval",
                slots={"から": start, "まで": end},
                logic=f"(Interval {atom(start)} {atom(end)})",
            )
        )
    return frames


def infer_quantifier_frames(text: str) -> list[CaseFrame]:
    frames = []
    for match in re.finditer(r"(?:任意の|すべての)\s*(?P<object>[^、。]+?)(?:に対して|について|は|が)", text):
        obj = clean_phrase(match.group("object"))
        frames.append(
            CaseFrame(
                predicate="任意",
                relation="Forall",
                slots={"binder": obj},
                logic=f"(Forall {atom(obj)})",
            )
        )
    for match in re.finditer(r"(?P<object>[^、。]+?)が存在する", text):
        obj = clean_phrase(match.group("object"))
        frames.append(
            CaseFrame(
                predicate="存在する",
                relation="Exists",
                slots={"が": obj},
                logic=f"(Exists {atom(obj)})",
            )
        )
    return frames


def clean_phrase(value: str) -> str:
    value = value.strip()
    value = re.sub(r"^\$|\$$", "", value)
    value = re.sub(r"^(とき|ならば|なら|この|その|また)\s*", "", value)
    return value.strip()


def atom(value: str) -> str:
    value = clean_phrase(value)
    if re.fullmatch(r"[A-Za-z0-9_+\-*/^=()., ]+", value):
        return value.replace(" ", "_")
    return '"' + value.replace('"', '\\"') + '"'


def unique_frames(frames: list[CaseFrame]) -> list[CaseFrame]:
    seen = set()
    result = []
    for frame in frames:
        key = (frame.relation, tuple(sorted(frame.slots.items())))
        if key in seen:
            continue
        seen.add(key)
        result.append(frame)
    return result
