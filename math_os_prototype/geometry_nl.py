"""Rule-based natural-language to Geometry DSL compiler.

This is a replaceable front-end. A small learned model can later emit the same
Geometry DSL, while the downstream CAS/proof pipeline stays unchanged.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass


TASK_MARKERS = {
    "envelope": ("包絡線", "envelope"),
    "region": ("通過領域", "動く範囲", "存在範囲", "点全体の領域", "少なくとも一つ", "passing region", "region"),
    "locus": ("軌跡", "locus"),
}

KNOWN_FUNCTIONS = {"sin", "cos", "tan", "exp", "log", "sqrt"}


@dataclass
class GeometryNLConversion:
    source: str
    dsl: str
    task: str
    confidence: float
    equations: dict[str, str]
    parameter: str
    domain: str
    notes: list[str]

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


def convert_geometry_nl(source: str) -> GeometryNLConversion | None:
    text = normalize_text(source)
    task = detect_task(text)
    if task is None:
        return None

    equations = extract_equations(text, task)
    if not equations:
        return None

    parameter = extract_parameter(text, equations) or "t"
    domain = extract_domain(text, parameter)
    notes: list[str] = []

    if task in {"envelope", "region"} and "y" not in equations:
        notes.append("Expected a family y = f(x,param); conversion rejected.")
        return None
    if task == "locus" and not {"x", "y"}.issubset(equations):
        notes.append("Expected x = f(param) and y = g(param); conversion rejected.")
        return None

    confidence = 0.70
    if any(marker in text.lower() for marker in TASK_MARKERS[task]):
        confidence += 0.10
    if parameter != "t" or "t" in "".join(equations.values()):
        confidence += 0.05
    if domain != "R":
        confidence += 0.05

    dsl_parts = [f"task {task}"]
    if task == "locus":
        dsl_parts.extend([f"x = {equations['x']}", f"y = {equations['y']}"])
    else:
        dsl_parts.append(f"family y = {equations['y']}")
    dsl_parts.append(f"param {parameter} in {domain}")

    return GeometryNLConversion(
        source=source,
        dsl="; ".join(dsl_parts),
        task=task,
        confidence=min(confidence, 0.95),
        equations=equations,
        parameter=parameter,
        domain=domain,
        notes=notes,
    )


def detect_task(text: str) -> str | None:
    lower = text.lower()
    for task, markers in TASK_MARKERS.items():
        if any(marker in lower for marker in markers):
            return task
    return None


def extract_equations(text: str, task: str) -> dict[str, str]:
    if task == "locus":
        coordinate_equations = extract_coordinate_pair(text)
        if coordinate_equations:
            return coordinate_equations

    equations: dict[str, str] = {}
    for variable in ("x", "y"):
        expr = extract_assignment_rhs(text, variable)
        if expr:
            equations[variable] = expr
    return equations


def extract_coordinate_pair(text: str) -> dict[str, str] | None:
    compact = text.replace(" ", "")
    patterns = (
        r"\(x,y\)=\((.+?),(.+?)\)",
        r"\(x\(t\),y\(t\)\)=\((.+?),(.+?)\)",
    )
    for pattern in patterns:
        match = re.search(pattern, compact, flags=re.IGNORECASE)
        if not match:
            continue
        return {
            "x": clean_expression(match.group(1)),
            "y": clean_expression(match.group(2)),
        }
    return None


def extract_assignment_rhs(text: str, variable: str) -> str | None:
    pattern = rf"\b{re.escape(variable)}\s*=\s*"
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None

    tail = text[match.end() :]
    stop_match = re.search(
        r"(?=\s*(?:の)?(?:包絡線|通過領域|動く範囲|存在範囲|点全体の領域|軌跡|を求|を考|について|とする|とした|where|find|求めよ|求める|$|[。。，，;；]))",
        tail,
        flags=re.IGNORECASE,
    )
    if stop_match:
        expr = tail[: stop_match.start()]
    else:
        expr = tail

    # If a sentence contains both x = ... and y = ..., stop the first expression
    # before the next assignment.
    next_assignment = re.search(r"\b[xy]\s*=", expr, flags=re.IGNORECASE)
    if next_assignment and next_assignment.start() > 0:
        expr = expr[: next_assignment.start()]
    return clean_expression(expr)


def extract_parameter(text: str, equations: dict[str, str]) -> str | None:
    explicit_patterns = (
        r"(?:parameter|param|媒介変数|パラメータ)\s*[:=]?\s*([a-zA-Z_][a-zA-Z_0-9]*)",
        r"([a-zA-Z_][a-zA-Z_0-9]*)\s*(?:を|は)?\s*(?:実数|媒介変数|パラメータ)",
        r"([a-zA-Z_][a-zA-Z_0-9]*)\s*(?:in|∈|\\in)\s*(?:R|Real|Reals|ℝ)",
        r"[<≤≦]\s*([a-zA-Z_][a-zA-Z_0-9]*)\s*[<≤≦]",
    )
    for pattern in explicit_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1)

    names: list[str] = []
    for expr in equations.values():
        names.extend(re.findall(r"[a-zA-Z_][a-zA-Z_0-9]*", expr))
    for name in names:
        if name not in {"x", "y"} and name not in KNOWN_FUNCTIONS:
            return name
    return None


def extract_domain(text: str, parameter: str) -> str:
    lower = text.lower()
    escaped = re.escape(parameter)
    if re.search(rf"{escaped}\s*(?:in|∈|\\in)\s*(?:r|real|reals|ℝ)", lower):
        return "R"
    if re.search(rf"{escaped}\s*(?:は|を)?\s*実数", text):
        return "R"

    interval_patterns = (
        rf"([+-]?\d+(?:\.\d+)?)\s*(<=|≤|≦|<)\s*{escaped}\s*(<=|≤|≦|<)\s*([+-]?\d+(?:\.\d+)?)",
        rf"{escaped}\s*(?:in|∈|\\in)\s*([\[(])\s*([^,\])\)]+)\s*,\s*([^\])\)]+)\s*([\])])",
    )
    match = re.search(interval_patterns[0], text, flags=re.IGNORECASE)
    if match:
        left_bracket = "[" if match.group(2) in {"<=", "≤", "≦"} else "("
        right_bracket = "]" if match.group(3) in {"<=", "≤", "≦"} else ")"
        return f"{left_bracket}{match.group(1)},{match.group(4)}{right_bracket}"

    match = re.search(interval_patterns[1], text, flags=re.IGNORECASE)
    if match:
        return f"{match.group(1)}{match.group(2)},{match.group(3)}{match.group(4)}"

    return "R"


def normalize_text(text: str) -> str:
    table = str.maketrans(
        {
            "０": "0",
            "１": "1",
            "２": "2",
            "３": "3",
            "４": "4",
            "５": "5",
            "６": "6",
            "７": "7",
            "８": "8",
            "９": "9",
            "ｘ": "x",
            "ｙ": "y",
            "ｔ": "t",
            "Ｘ": "X",
            "Ｙ": "Y",
            "Ｔ": "T",
            "＝": "=",
            "＋": "+",
            "－": "-",
            "−": "-",
            "×": "*",
            "＊": "*",
            "＾": "^",
            "，": ",",
            "；": ";",
            "（": "(",
            "）": ")",
            "［": "[",
            "］": "]",
        }
    )
    return text.translate(table)


def clean_expression(expr: str) -> str:
    cleaned = normalize_text(expr)
    cleaned = cleaned.strip(" \t\n\r,.;。")
    cleaned = re.sub(r"\s+", "", cleaned)
    cleaned = cleaned.replace("^", "**")
    cleaned = re.sub(r"(?<=\d)(?=[a-zA-Z_])", "*", cleaned)
    cleaned = re.sub(r"(?<=[a-zA-Z_])(?=\d)", "*", cleaned)
    cleaned = trim_trailing_japanese(cleaned)
    return cleaned


def trim_trailing_japanese(expr: str) -> str:
    match = re.match(r"([0-9a-zA-Z_+\-*/().\[\]{}^]+)", expr)
    return match.group(1) if match else expr
