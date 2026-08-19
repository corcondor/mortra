"""problem 記録の difficulty 欄を、形が違っても同じように読む。

生成器によって形が2通りある:

  * autonomous_loop が作る記録  -> {"band": "C", "score": 12.5, ...}
  * construct_engine が直接書く記録 -> "A"

既存プールを読み直すと両方が混ざる。文字列に .get を呼んで CI が2度落ちた
（autonomous_loop.py と merge_shards.py で同じ書き方をしていた）ので、
読み取りをここに集めて三度目が起きないようにする。
"""

from __future__ import annotations

from typing import Any

# A が最難。文字列表記を score に対応させる。
BAND_SCORES: dict[str, float] = {"A": 4.0, "B": 3.0, "C": 2.0, "D": 1.0}


def difficulty_score(record: dict[str, Any]) -> float:
    value = record.get("difficulty")
    if isinstance(value, dict):
        try:
            return float(value.get("score", 0) or 0)
        except (TypeError, ValueError):
            return 0.0
    if isinstance(value, str):
        return BAND_SCORES.get(value.strip().upper(), 0.0)
    return 0.0


def difficulty_band(record: dict[str, Any]) -> str:
    value = record.get("difficulty")
    if isinstance(value, dict):
        return str(value.get("band", "?"))
    if isinstance(value, str) and value.strip():
        return value.strip()
    return "?"
