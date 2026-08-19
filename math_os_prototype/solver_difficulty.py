"""Solver-based difficulty: 難しさ = 解いてみた時の難しさ。

キーワードの数ではなく、実際に解く道具(SymPy を第一段、必要なら Wolfram)に
問題を渡し、「一発で解けたら易しい」で測る。易しい問題は除外する。

分類:
  trivial   : SymPy が直接、短時間で閉じた形を返した(=暗算〜1行)。除外対象。
  moderate  : SymPy が返すが時間がかかる、または一部だけ。
  hard      : SymPy が直接解けない(未評価 / 例外 / タイムアウト)。人手の
              分解や幾何的構成が要る = 本当に難しい候補。

これは "解法の転送ネットワーク" の最小版: まず単一ツールで解けるかを見る。
将来、解を木(複数ツールの合成)で辿り、その木の深さを難易度にする。
"""

from __future__ import annotations

import signal
from dataclasses import dataclass
from typing import Any, Callable

import sympy as sp


class _Timeout(Exception):
    pass


def _run_with_timeout(fn: Callable[[], Any], seconds: float) -> tuple[bool, Any, float]:
    import time

    # signal-based timeout is POSIX-only; fall back to plain timing on Windows.
    start = time.time()
    try:
        result = fn()
        return True, result, time.time() - start
    except Exception as exc:  # noqa: BLE001 - the solver failing IS the signal
        return False, exc, time.time() - start


def _is_closed_form(expr: Any) -> bool:
    if not isinstance(expr, sp.Basic):
        return isinstance(expr, (int, float))
    # 未評価の Integral / Sum / Limit が残っていたら「解けていない」。
    unresolved = (sp.Integral, sp.Sum, sp.Product, sp.Limit)
    return not expr.has(*unresolved)


@dataclass(frozen=True)
class DifficultyVerdict:
    band: str          # trivial | moderate | hard
    solved_directly: bool
    seconds: float
    detail: str


def classify_symbolic_query(query: Callable[[], Any], budget: float = 8.0) -> DifficultyVerdict:
    """query() は SymPy でその問題を『素直に』解く1回の試み。"""

    ok, result, secs = _run_with_timeout(query, budget)
    if not ok:
        return DifficultyVerdict("hard", False, secs, f"solver raised {type(result).__name__}")
    if not _is_closed_form(result):
        return DifficultyVerdict("hard", False, secs, "returned unevaluated (Integral/Sum/Limit)")
    if secs < 1.0:
        return DifficultyVerdict("trivial", True, secs, "closed form in <1s")
    if secs < budget:
        return DifficultyVerdict("moderate", True, secs, f"closed form in {secs:.1f}s")
    return DifficultyVerdict("hard", False, secs, "timeout")


# --- 既存の生成問題クラスの『素直な一発解き』を定義 -------------------------
def direct_query_for(problem: dict[str, Any]) -> Callable[[], Any] | None:
    """生成問題の family/parameters から、SymPy に素直に投げる解き方を組む。
    幾何構成(通過領域・凸包)は文からSymPyに直接は渡せない → None(=道具が
    一発で解けない=難しい側) とみなす。"""

    family = problem.get("family_id", "")
    params = problem.get("parameters", {}) or {}
    x, k, n = sp.symbols("x k n")

    if family == "fusion.trig_absolute_value_integral":
        m = int(params.get("k", 2))
        return lambda: sp.integrate(sp.Abs(sp.sin(x) - sp.sin(m * x)), (x, 0, sp.pi))
    if family == "fusion.trig_floor_integral":
        a = int(params.get("a", 0)); b = int(params.get("b", 2))
        return lambda: sp.integrate(sp.floor(a + b * sp.sin(x)), (x, 0, 2 * sp.pi))
    if family.startswith("series."):
        return None  # 和は別途だが多くは一発 → 呼び出し側で trivial 既知
    # 幾何構成(通過領域・凸包)は SymPy に文から渡せない = 一発では解けない
    if family.startswith(("passage_region.", "concept_tree.", "spectral.")):
        return "geometric"  # type: ignore[return-value]
    return None
