"""Lightweight LaTeX problem front-end.

The goal is not to render TeX. It extracts problem text and normalizes common
math notation enough for the natural-language and Geometry DSL layers.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass


KNOWN_FUNCTIONS = {"sin", "cos", "tan", "exp", "log", "sqrt", "factorial"}
LATEX_FUNCTIONS = {
    r"\sin": "sin",
    r"\cos": "cos",
    r"\tan": "tan",
    r"\exp": "exp",
    r"\log": "log",
}
GREEK_NAMES = {
    "alpha": "alpha",
    "beta": "beta",
    "gamma": "gamma",
    "theta": "theta",
    "rho": "rho",
    "lambda": "lambda",
    "mu": "mu",
    "pi": "pi",
}


@dataclass
class LatexProblem:
    source: str
    body: str
    normalized_text: str
    math_segments: list[str]
    notes: list[str]

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


@dataclass(frozen=True)
class TexMathSpan:
    delimiter: str
    content: str
    start: int
    end: int


def looks_like_latex(source: str) -> bool:
    markers = (
        r"\begin",
        r"\end",
        r"\(",
        r"\)",
        r"\[",
        r"\]",
        r"\frac",
        r"\mathbb",
        r"\documentclass",
        r"\item",
    )
    # A dollar amount such as ``$5,000 ... $8,000`` is prose, not a TeX math
    # span. Remove currency markers before looking for paired math delimiters.
    non_currency_source = re.sub(r"\$(?=\d[\d,]*(?:\.\d+)?(?:\b|\s|[.,]))", "", source)
    return any(marker in source for marker in markers) or bool(re.search(r"\$[^$]+\$", non_currency_source))


def parse_latex_problem(source: str) -> LatexProblem:
    # Percent signs are comments in a TeX document, but percentages in mixed
    # prose (often alongside inline math) are data and must survive scanning.
    without_comments = strip_comments(source) if is_tex_document(source) else source
    body = extract_document_body(without_comments)
    math_segments: list[str] = []

    text, spans = split_tex_text_math(body)
    for span in spans:
        math_segments.append(normalize_latex_math(span.content))
    text = normalize_latex_text(text)
    normalized_text = normalize_spacing(text)
    notes = [
        "LaTeX was normalized without full TeX macro expansion.",
        "Math delimiters were scanned by a deterministic TeX input scanner.",
    ]
    return LatexProblem(source, body, normalized_text, math_segments, notes)


def is_tex_document(source: str) -> bool:
    return any(
        marker in source
        for marker in (r"\documentclass", r"\usepackage", r"\begin{document}", r"\end{document}")
    )


def split_tex_text_math(source: str) -> tuple[str, list[TexMathSpan]]:
    """Split TeX text into normalized math placeholders using a small scanner.

    This is intentionally a scanner, not a full TeX parser. It behaves like a
    deterministic automaton over the input stream for math delimiters, while
    the later math normalizer handles braced macro arguments with a depth
    counter. That is enough for exam-style TeX input and avoids brittle regex
    matching across nested fractions.
    """

    spans: list[TexMathSpan] = []
    output: list[str] = []
    text_start = 0
    i = 0
    while i < len(source):
        delimiter = math_start_delimiter(source, i)
        if delimiter is None:
            i += 1
            continue

        content_start = i + len(delimiter)
        close_delimiter = {"$": "$", "$$": "$$", r"\(": r"\)", r"\[": r"\]"}[delimiter]
        end = find_math_end(source, content_start, close_delimiter)
        if end is None:
            i += len(delimiter)
            continue

        output.append(source[text_start:i])
        content = source[content_start:end]
        normalized = normalize_latex_math(content)
        output.append(f" {normalized} ")
        spans.append(TexMathSpan(delimiter=delimiter, content=content, start=i, end=end + len(close_delimiter)))
        i = end + len(close_delimiter)
        text_start = i

    output.append(source[text_start:])
    return "".join(output), spans


def math_start_delimiter(source: str, index: int) -> str | None:
    if source.startswith(r"\(", index):
        return r"\("
    if source.startswith(r"\[", index):
        return r"\["
    if source.startswith("$$", index) and not is_escaped(source, index):
        return "$$"
    if source[index] == "$" and not is_escaped(source, index):
        return "$"
    return None


def find_math_end(source: str, start: int, close_delimiter: str) -> int | None:
    i = start
    while i < len(source):
        if close_delimiter in {"$", "$$"}:
            if source.startswith(close_delimiter, i) and not is_escaped(source, i):
                if close_delimiter == "$" and source.startswith("$$", i):
                    i += 2
                    continue
                return i
        elif source.startswith(close_delimiter, i):
            return i
        if source[i] == "\\":
            i += 2
        else:
            i += 1
    return None


def is_escaped(source: str, index: int) -> bool:
    slash_count = 0
    cursor = index - 1
    while cursor >= 0 and source[cursor] == "\\":
        slash_count += 1
        cursor -= 1
    return slash_count % 2 == 1


def strip_comments(source: str) -> str:
    lines = []
    for line in source.splitlines():
        lines.append(re.sub(r"(?<!\\)%.*$", "", line))
    return "\n".join(lines)


def extract_document_body(source: str) -> str:
    match = re.search(r"\\begin\{document\}(.*?)\\end\{document\}", source, flags=re.DOTALL)
    return match.group(1) if match else source


def normalize_latex_text(text: str) -> str:
    text = re.sub(r"\\(?:section|subsection|subsubsection|paragraph)\*?\{([^{}]*)\}", r" \1 ", text)
    text = re.sub(r"\\(?:textbf|textit|emph|underline)\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\begin\{[^{}]+\}", " ", text)
    text = re.sub(r"\\end\{[^{}]+\}", " ", text)
    text = re.sub(r"\\(?:documentclass|usepackage)(?:\[[^\]]*\])?\{[^{}]*\}", " ", text)
    text = re.sub(r"\\item(?:\[[^\]]*\])?", " ", text)
    text = text.replace(r"\\", " ")
    text = text.replace(r"\,", " ")
    text = text.replace(r"\;", " ")
    text = text.replace(r"\quad", " ")
    text = text.replace(r"\qquad", " ")
    text = text.replace("~", " ")
    return text


def normalize_latex_math(expr: str) -> str:
    expr = expr.strip()
    expr = normalize_unicode_math_symbols(expr)
    expr = re.sub(r"\\begin\{(?:aligned|align\*?|gathered|cases)\}", " ", expr)
    expr = re.sub(r"\\end\{(?:aligned|align\*?|gathered|cases)\}", " ", expr)
    expr = expr.replace("&", "")
    # Preserve display rows as mathematical statement separators.  The
    # symbolic lowering stage consumes these as a constraint conjunction.
    expr = expr.replace(r"\\", ";")
    expr = expr.replace(r"\left", "").replace(r"\right", "")
    expr = expr.replace(r"\,", "").replace(r"\;", "").replace(r"\!", "")
    expr = expr.replace(r"\ ", " ")
    expr = normalize_text_macros(expr)
    expr = normalize_mathbb(expr)
    expr = normalize_fractions(expr)
    expr = normalize_sqrt(expr)
    expr = normalize_bare_function_arguments(expr)
    for latex, plain in LATEX_FUNCTIONS.items():
        expr = expr.replace(latex, plain)
    for name, plain in GREEK_NAMES.items():
        expr = expr.replace(f"\\{name}", plain)
    # At this point ``\\neq`` is still a LaTeX command, so a literal ``!``
    # can only denote factorial notation.  Lowering it here avoids confusing
    # ``n!=3`` (factorial followed by equality) with the ``!=`` relation.
    expr = normalize_factorials(expr)
    replacements = {
        r"\int": "integral",
        r"\cdot": "*",
        r"\times": "*",
        r"\div": "/",
        r"\ast": " astop ",
        r"\to": " to ",
        r"\infty": "infinity",
        r"\lim": "limit",
        r"\in": " in ",
        r"\leq": "<=",
        r"\le": "<=",
        r"\geq": ">=",
        r"\ge": ">=",
        r"\neq": "!=",
        r"\ne": "!=",
        r"\lt": "<",
        r"\gt": ">",
        r"\{": "{",
        r"\}": "}",
    }
    for old, new in replacements.items():
        expr = expr.replace(old, new)
    expr = normalize_powers(expr)
    expr = expr.replace("{", "").replace("}", "")
    expr = expr.replace("^", "**")
    expr = normalize_spacing(expr)
    return insert_implicit_multiplication(expr)


def normalize_bare_function_arguments(expr: str) -> str:
    r"""Parenthesize TeX function applications with an unbraced atomic argument.

    TeX writes ``\sin\theta`` and ``\sin x`` without an application
    delimiter.  Leaving those forms until implicit-multiplication insertion
    merges them into identifiers such as ``sintheta``.  This scanner-level
    rewrite preserves application structure without knowing the surrounding
    problem type.
    """
    greek = "|".join(re.escape(name) for name in GREEK_NAMES)
    functions = "|".join(re.escape(name.removeprefix("\\")) for name in LATEX_FUNCTIONS)
    expr = re.sub(
        rf"\\(?P<function>{functions})\s*\\(?P<argument>{greek})(?![A-Za-z])",
        lambda match: f"{match.group('function')}({GREEK_NAMES[match.group('argument')]})",
        expr,
    )
    expr = re.sub(
        rf"\\(?P<function>{functions})\s*(?P<argument>[A-Za-z])(?![A-Za-z0-9_])",
        lambda match: f"{match.group('function')}({match.group('argument')})",
        expr,
    )
    return expr


def normalize_text_macros(expr: str) -> str:
    for command in (r"\text", r"\mbox", r"\mathrm"):
        while command in expr:
            start = expr.find(command)
            arg_start = skip_spaces(expr, start + len(command))
            if arg_start >= len(expr) or expr[arg_start] != "{":
                break
            content, arg_end = read_braced(expr, arg_start)
            expr = expr[:start] + f" {content} " + expr[arg_end:]
    return expr


def normalize_mathbb(expr: str) -> str:
    expr = re.sub(r"\\mathbb\{R\}", "R", expr)
    expr = re.sub(r"\\mathbb\s*R", "R", expr)
    expr = re.sub(r"\\mathbb\{Z\}", "Z", expr)
    expr = re.sub(r"\\mathbb\s*Z", "Z", expr)
    return expr


def normalize_fractions(expr: str) -> str:
    for command in (r"\dfrac", r"\tfrac", r"\frac"):
        mixed_braced = re.compile(
            rf"(?<![A-Za-z0-9.])(\d+)\s*{re.escape(command)}\s*\{{([^{{}}]+)\}}\s*\{{([^{{}}]+)\}}"
        )
        expr = mixed_braced.sub(
            lambda match: (
                f"({match.group(1)}+(({normalize_latex_math(match.group(2))})/"
                f"({normalize_latex_math(match.group(3))})))"
            ),
            expr,
        )
        mixed_compact = re.compile(rf"(?<![A-Za-z0-9.])(\d+)\s*{re.escape(command)}\s*(\d)\s*(\d)")
        expr = mixed_compact.sub(
            lambda match: f"({match.group(1)}+(({match.group(2)})/({match.group(3)})))",
            expr,
        )
        compact_pattern = re.compile(rf"{re.escape(command)}\s*([A-Za-z0-9])\s*([A-Za-z0-9])")
        expr = compact_pattern.sub(
            lambda match: f"(({normalize_latex_math(match.group(1))})/({normalize_latex_math(match.group(2))}))",
            expr,
        )
        while command in expr:
            start = expr.find(command)
            first_start = skip_spaces(expr, start + len(command))
            if first_start >= len(expr) or expr[first_start] != "{":
                break
            numerator, first_end = read_braced(expr, first_start)
            second_start = skip_spaces(expr, first_end)
            if second_start >= len(expr):
                break
            if expr[second_start] == "{":
                denominator, second_end = read_braced(expr, second_start)
            else:
                denominator = expr[second_start]
                second_end = second_start + 1
            replacement = f"(({normalize_latex_math(numerator)})/({normalize_latex_math(denominator)}))"
            expr = expr[:start] + replacement + expr[second_end:]
    return expr


def normalize_sqrt(expr: str) -> str:
    command = r"\sqrt"
    while command in expr:
        start = expr.find(command)
        arg_start = skip_spaces(expr, start + len(command))
        if arg_start >= len(expr):
            break
        root_degree = "2"
        if expr[arg_start] == "[":
            degree_end = expr.find("]", arg_start + 1)
            if degree_end < 0:
                break
            root_degree = expr[arg_start + 1:degree_end].strip()
            arg_start = skip_spaces(expr, degree_end + 1)
        if expr[arg_start] == "{":
            arg, arg_end = read_braced(expr, arg_start)
        else:
            match = re.match(r"[A-Za-z0-9]+", expr[arg_start:])
            if not match:
                break
            arg = match.group(0)
            arg_end = arg_start + len(arg)
        normalized_arg = normalize_latex_math(arg)
        replacement = (
            f"sqrt({normalized_arg})"
            if root_degree == "2"
            else f"(({normalized_arg})**(1/({normalize_latex_math(root_degree)})))"
        )
        expr = expr[:start] + replacement + expr[arg_end:]
    return expr


def normalize_powers(expr: str) -> str:
    expr = re.sub(r"\^\{([^{}]+)\}", lambda match: f"**({normalize_latex_math(match.group(1))})", expr)
    expr = re.sub(r"\^([A-Za-z0-9]+)", r"**\1", expr)
    return expr


def normalize_factorials(expr: str) -> str:
    previous = None
    while expr != previous:
        previous = expr
        expr = re.sub(r"(?<!!)(\([^()]+\)|[A-Za-z]|\d+)\s*!(?!!)", r"factorial(\1)", expr)
    return expr


def read_braced(text: str, start: int) -> tuple[str, int]:
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
            if depth == 1:
                content_start = index + 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[content_start:index], index + 1
    raise ValueError("unclosed braced LaTeX expression")


def skip_spaces(text: str, index: int) -> int:
    while index < len(text) and text[index].isspace():
        index += 1
    return index


def insert_implicit_multiplication(expr: str) -> str:
    expr = re.sub(r"(?<=\d)(?=[A-Za-z_(])", "*", expr)
    expr = re.sub(r"(?<=[A-Za-z])(?=\d|\()", "*", expr)
    expr = re.sub(r"(?<=\))(?=[A-Za-z_0-9(])", "*", expr)
    expr = split_compact_variables(expr)
    for function_name in KNOWN_FUNCTIONS:
        expr = expr.replace(f"{function_name}*(", f"{function_name}(")
    return expr


def split_compact_variables(expr: str) -> str:
    def replace(match: re.Match[str]) -> str:
        word = match.group(0)
        syntax_words = {
            "and",
            "as",
            "astop",
            "for",
            "if",
            "in",
            "is",
            "lim",
            "max",
            "min",
            "mod",
            "not",
            "of",
            "or",
            "to",
        }
        if (
            word in KNOWN_FUNCTIONS
            or word in GREEK_NAMES.values()
            or word in syntax_words
            or (len(word) == 2 and word.startswith("d"))
        ):
            return word
        if len(word) <= 4 and word.isalpha() and word.islower():
            return "*".join(word)
        return word

    return re.sub(r"\b[A-Za-z_]{2,}\b", replace, expr)


def normalize_spacing(text: str) -> str:
    text = normalize_unicode_math_symbols(text)
    text = text.replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_unicode_math_symbols(text: str) -> str:
    return (
        text.replace("＋", "+")
        .replace("－", "-")
        .replace("−", "-")
        .replace("×", "*")
        .replace("＊", "*")
        .replace("・", "*")
        .replace("＾", "^")
        .replace("＝", "=")
    )
