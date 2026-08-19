# -*- coding: utf-8 -*-
"""型付き演繹データベースによる標準模型エンジン。

Chou/Gao/Zhang (2000) の演繹データベース方式: 型付き Atom の定理 bank による
前向き固定点閉包。Chou/Gao/Zhang (1996) の全角法: 有向角を線分方向の
アーベル群として線形系で解く。答えは閉包が一意に値を固定した時だけ返す。

  text → typed atoms → 固定点閉包（定理bank）→ 全角アーベル群の線形解 → 一意値

誤答0の関門:
  - 線形系が不整合（EmptySet）なら棄権
  - 目標角の値が一意に定まらない（自由変数が残る）なら棄権
  - 値が (0,180) にないなら棄権
  - オプションに一意一致する時だけ答える
"""

from __future__ import annotations

import re
import sys
import time
from dataclasses import dataclass, field
from itertools import combinations
from typing import Iterable, Optional

import sympy as sp

sys.path.insert(0, r"C:\Users\81808\.openclaw\workspace\math-web\worker\backend")

from geometry_proof_hypergraph import Atom  # noqa: E402
from wu_geometry_kernel import _plain, _matches_option, _option_values  # noqa: E402


# ---------------------------------------------------------------------------
# 型付き Atom の正規化
# ---------------------------------------------------------------------------

def _canon(atom: Atom) -> Atom:
    """全角法の表現に合わせた正規化。

    - coll(A,B,C): B が真ん中の順序を保つ（直線角は真ん中の頂点で立つ。
      規則の位置パターンが成り立つためソートしない）
    - para/perp/cong: 線分ペアで整列（既存 canonical と同じ）
    - eqangle: 有向角なので並びを変えない（A,B,C = D,E,F の向きは維持）
    - cyclic: 向かい合う角の組（0,2）（1,3）が保たれるよう順序を維持
    """
    name = atom.predicate.lower()
    args = atom.arguments
    if name in {"para", "perp", "cong"} and len(args) == 4:
        left = tuple(sorted(args[:2]))
        right = tuple(sorted(args[2:]))
        first, second = sorted((left, right))
        args = (*first, *second)
    elif name == "mid" and len(args) == 3:
        args = (args[0], *sorted(args[1:]))
    return Atom(name, tuple(args))

def _ang(*points: str) -> Atom:
    return Atom("angval", tuple(points))


# ---------------------------------------------------------------------------
# 定理 bank（前向き Horn 規則）
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Rule:
    name: str
    premises: tuple[Atom, ...]
    conclusion: Atom


def _rules() -> tuple[Rule, ...]:
    a = lambda name, *args: Atom(name, tuple(args))  # noqa: E731
    return (
        # ---- 並行・垂直の伝搬（線分の同値性） ----
        Rule("parallel-transitivity",
             (a("para", "?A", "?B", "?C", "?D"), a("para", "?C", "?D", "?E", "?F")),
             a("para", "?A", "?B", "?E", "?F")),
        Rule("perpendicular-transport-over-parallel",
             (a("perp", "?A", "?B", "?C", "?D"), a("para", "?C", "?D", "?E", "?F")),
             a("perp", "?A", "?B", "?E", "?F")),
        Rule("common-perpendicular-implies-parallel",
             (a("perp", "?A", "?B", "?C", "?D"), a("perp", "?E", "?F", "?C", "?D")),
             a("para", "?A", "?B", "?E", "?F")),
        Rule("segment-congruence-transitivity",
             (a("cong", "?A", "?B", "?C", "?D"), a("cong", "?C", "?D", "?E", "?F")),
             a("cong", "?A", "?B", "?E", "?F")),
        Rule("equal-angle-transitivity",
             (a("eqangle", "?A", "?B", "?C", "?D", "?E", "?F"),
              a("eqangle", "?D", "?E", "?F", "?G", "?H", "?I")),
             a("eqangle", "?A", "?B", "?C", "?G", "?H", "?I")),
        Rule("equal-angle-symmetry",
             (a("eqangle", "?A", "?B", "?C", "?D", "?E", "?F"),),
             a("eqangle", "?D", "?E", "?F", "?A", "?B", "?C")),
        # ---- 中点 ----
        Rule("midpoint-implies-collinear",
             (a("mid", "?M", "?A", "?B"),),
             a("coll", "?A", "?M", "?B")),
        Rule("midpoint-implies-equal-halves",
             (a("mid", "?M", "?A", "?B"),),
             a("cong", "?A", "?M", "?M", "?B")),
        # ---- 共線上の点は三角形を切る（三角形の内角の決定に必要） ----
        Rule("collinear-splits-triangle",
             (a("tri", "?A", "?B", "?C"), a("coll", "?A", "?D", "?C")),
             a("tri", "?A", "?B", "?D")),
        Rule("collinear-splits-triangle-2",
             (a("tri", "?A", "?B", "?C"), a("coll", "?A", "?D", "?C")),
             a("tri", "?D", "?B", "?C")),
        # ---- 共円四角形は 4 つの三角形を持つ ----
        Rule("cyclic-implies-triangles",
             (a("cyclic", "?A", "?B", "?C", "?D"),),
             a("tri", "?A", "?B", "?C")),
        Rule("cyclic-implies-triangles-2",
             (a("cyclic", "?A", "?B", "?C", "?D"),),
             a("tri", "?B", "?C", "?D")),
        Rule("cyclic-implies-triangles-3",
             (a("cyclic", "?A", "?B", "?C", "?D"),),
             a("tri", "?C", "?D", "?A")),
        Rule("cyclic-implies-triangles-4",
             (a("cyclic", "?A", "?B", "?C", "?D"),),
             a("tri", "?D", "?A", "?B")),
        # ---- 二等辺三角形の底角 ----
        Rule("isosceles-base-angles",
             (a("tri", "?A", "?B", "?C"), a("cong", "?A", "?B", "?A", "?C")),
             a("eqangle", "?A", "?B", "?C", "?B", "?C", "?A")),
        # ---- 平行四辺形の対辺 ----
        Rule("parallelogram-opposite-sides",
             (a("para", "?A", "?B", "?C", "?D"), a("para", "?B", "?C", "?A", "?D")),
             a("cong", "?A", "?B", "?C", "?D")),
        Rule("parallelogram-opposite-sides-2",
             (a("para", "?A", "?B", "?C", "?D"), a("para", "?B", "?C", "?A", "?D")),
             a("cong", "?B", "?C", "?A", "?D")),
        # ---- 平行線と横断線（同位角・錯角）----
        # P,Q 上の X と R,S 上の Y を結ぶ線が横断線: ∠PXY = ∠XYS（錯角）
        Rule("parallel-alternate-interior",
             (a("para", "?P", "?Q", "?R", "?S"), a("coll", "?P", "?X", "?Q"),
              a("coll", "?R", "?Y", "?S")),
             a("eqangle", "?P", "?X", "?Y", "?X", "?Y", "?S")),
        Rule("parallel-corresponding",
             (a("para", "?P", "?Q", "?R", "?S"), a("coll", "?P", "?X", "?Q"),
              a("coll", "?R", "?Y", "?S")),
             a("eqangle", "?P", "?X", "?Y", "?R", "?Y", "?X")),
        # ---- 共円（円周角） ----
        Rule("cyclic-inscribed-same-chord-1",
             (a("cyclic", "?A", "?B", "?C", "?D"),),
             a("eqangle", "?A", "?B", "?C", "?A", "?D", "?C")),
        Rule("cyclic-inscribed-same-chord-2",
             (a("cyclic", "?A", "?B", "?C", "?D"),),
             a("eqangle", "?B", "?C", "?D", "?B", "?A", "?D")),
        # ---- タレス（直径の円周角は直角） ----
        Rule("thales-right-angle",
             (a("oncircle", "?A", "?O"), a("oncircle", "?B", "?O"),
              a("oncircle", "?C", "?O"), a("coll", "?A", "?O", "?B")),
             a("angval", "?A", "?C", "?B", "90")),
        # ---- 接線の傾き（tgt_T の接線を線形系に加えるのは _build 側） ----
        # 接弦定理の結論（合成点 tgt_T を含む等角）は閉包の手動ブロックで生成。
        # ---- 垂直の共有頂点 → 90° ----
        Rule("perpendicular-shared-vertex-right-angle",
             (a("perp", "?A", "?B", "?B", "?C"),),
             a("angval", "?A", "?B", "?C", "90")),
        Rule("perpendicular-shared-vertex-right-angle-2",
             (a("perp", "?B", "?A", "?B", "?C"),),
             a("angval", "?A", "?B", "?C", "90")),
        Rule("perpendicular-shared-vertex-right-angle-3",
             (a("perp", "?A", "?B", "?A", "?C"),),
             a("angval", "?C", "?A", "?B", "90")),
        # ---- 垂線の足は直角（altitude foot） ----
        Rule("perpendicular-foot-right-angle",
             (a("perp", "?P", "?Q", "?R", "?S"), a("coll", "?R", "?Q", "?S")),
             a("angval", "?P", "?Q", "?R", "90")),
        # ---- 推移律（Chou/Gao/Zhang 2000 の演繹DB基本規則、上に定義済み） ----
        # ---- 等角の逆（底角が等しい → 二等辺） ----
        Rule("isosceles-converse",
             (a("tri", "?A", "?B", "?C"), a("eqangle", "?A", "?B", "?C", "?B", "?C", "?A")),
             a("cong", "?A", "?B", "?A", "?C")),
        # ---- 合同三角形（対応する辺・角） ----
        Rule("congruent-triangles-sides",
             (a("congr_tri", "?A", "?B", "?C", "?D", "?E", "?F"),),
             a("cong", "?A", "?B", "?D", "?E")),
        Rule("congruent-triangles-sides-2",
             (a("congr_tri", "?A", "?B", "?C", "?D", "?E", "?F"),),
             a("cong", "?B", "?C", "?E", "?F")),
        Rule("congruent-triangles-sides-3",
             (a("congr_tri", "?A", "?B", "?C", "?D", "?E", "?F"),),
             a("cong", "?A", "?C", "?D", "?F")),
        Rule("congruent-triangles-angles",
             (a("congr_tri", "?A", "?B", "?C", "?D", "?E", "?F"),),
             a("eqangle", "?A", "?B", "?C", "?D", "?E", "?F")),
        Rule("congruent-triangles-angles-2",
             (a("congr_tri", "?A", "?B", "?C", "?D", "?E", "?F"),),
             a("eqangle", "?B", "?C", "?A", "?E", "?F", "?D")),
        Rule("congruent-triangles-angles-3",
             (a("congr_tri", "?A", "?B", "?C", "?D", "?E", "?F"),),
             a("eqangle", "?C", "?A", "?B", "?F", "?D", "?E")),
        # ---- 相似三角形（対応する角） ----
        Rule("similar-triangles-angles",
             (a("sim_tri", "?A", "?B", "?C", "?D", "?E", "?F"),),
             a("eqangle", "?A", "?B", "?C", "?D", "?E", "?F")),
        Rule("similar-triangles-angles-2",
             (a("sim_tri", "?A", "?B", "?C", "?D", "?E", "?F"),),
             a("eqangle", "?B", "?C", "?A", "?E", "?F", "?D")),
        Rule("similar-triangles-angles-3",
             (a("sim_tri", "?A", "?B", "?C", "?D", "?E", "?F"),),
             a("eqangle", "?C", "?A", "?B", "?F", "?D", "?E")),
        # ---- 平行四辺形（パーサーが発行する向き para(A,B,D,C), para(B,C,A,D)） ----
        Rule("parallelogram-opposite-angles",
             (a("para", "?A", "?B", "?D", "?C"), a("para", "?B", "?C", "?A", "?D")),
             a("eqangle", "?D", "?A", "?B", "?B", "?C", "?D")),
        Rule("parallelogram-opposite-angles-2",
             (a("para", "?A", "?B", "?D", "?C"), a("para", "?B", "?C", "?A", "?D")),
             a("eqangle", "?A", "?B", "?C", "?C", "?D", "?A")),
        # ---- タレスの逆（直角2つ → 共円、直径AI 上の円周角） ----
        Rule("thales-converse-cyclic",
             (a("angval", "?A", "?E", "?I", "90"), a("angval", "?A", "?F", "?I", "90")),
             a("cyclic", "?A", "?E", "?I", "?F")),
        # ---- 同一円上の3点は三角形（非退化） ----
        Rule("three-points-on-circle-triangle",
             (a("oncircle", "?A", "?O"), a("oncircle", "?B", "?O"),
              a("oncircle", "?C", "?O")),
             a("tri", "?A", "?B", "?C")),
        # ---- 同一円上の4点は共円（循環四角形の和 = 360° と同弦円周角に供給） ----
        Rule("four-points-on-circle-cyclic",
             (a("oncircle", "?A", "?O"), a("oncircle", "?B", "?O"),
              a("oncircle", "?C", "?O"), a("oncircle", "?D", "?O")),
             a("cyclic", "?A", "?B", "?C", "?D")),
        # ---- 中心角 = 2 × 円周角（同一円・同弦） ----
        # 全角群では 2·∠ACB − ∠AOB = m·180（k は円周角側にかかる）。
        Rule("central-angle-double-inscribed",
             (a("oncircle", "?A", "?O"), a("oncircle", "?B", "?O"),
              a("oncircle", "?C", "?O")),
             a("angrel", "?A", "?C", "?B", "?A", "?O", "?B", "2")),
        # ---- 等長の弦は等しい円周角を持つ ----
        Rule("equal-chords-equal-angles",
             (a("cong", "?A", "?B", "?C", "?D"),
              a("oncircle", "?A", "?O"), a("oncircle", "?B", "?O"),
              a("oncircle", "?C", "?O"), a("oncircle", "?D", "?O"),
              a("oncircle", "?E", "?O"), a("oncircle", "?F", "?O")),
             a("eqangle", "?A", "?E", "?B", "?C", "?F", "?D")),
        # ---- 接線の長さ（同一円の外部点から引いた2接線は等長） ----
        # パーサーが tangent_at を発行するので、同じ外部点を共有する組で
        # 等長を導出する（外部点は接点の tangent_at と共線で特定）。
        Rule("tangent-lengths-equal",
             (a("tangent_at", "?E", "?O"), a("tangent_at", "?F", "?O"),
              a("coll", "?A", "?E", "?B"), a("coll", "?A", "?F", "?C")),
             a("cong", "?A", "?E", "?A", "?F")),
        # ---- 中点連結定理（中点2つを結ぶ線分は対辺に平行） ----
        Rule("midline-parallel",
             (a("mid", "?M", "?A", "?B"), a("mid", "?N", "?A", "?C")),
             a("para", "?M", "?N", "?B", "?C")),
        # ---- 直角三角形の斜辺の中点は3頂点から等距離（外心） ----
        Rule("right-triangle-hypotenuse-midpoint",
             (a("mid", "?M", "?A", "?B"), a("angval", "?A", "?C", "?B", "90")),
             a("cong", "?M", "?C", "?M", "?A")),
        # ---- ひし形（平行四辺形 + 隣辺等長）の対角線は直交 ----
        Rule("rhombus-diagonals-perpendicular",
             (a("para", "?A", "?B", "?D", "?C"), a("para", "?B", "?C", "?A", "?D"),
              a("cong", "?A", "?B", "?B", "?C")),
             a("perp", "?A", "?C", "?B", "?D")),
        # ---- 半径は等しい（同円） ----
        Rule("same-circle-radii-equal",
             (a("oncircle", "?A", "?O"), a("oncircle", "?B", "?O")),
             a("cong", "?O", "?A", "?O", "?B")),
    )


# ---------------------------------------------------------------------------
# 固定点閉包（前向き演繹）
# ---------------------------------------------------------------------------

def _is_var(value: str) -> bool:
    return value.startswith("?")


def _unify(pattern: Atom, ground: Atom, initial: dict | None = None):
    if pattern.predicate != ground.predicate or len(pattern.arguments) != len(ground.arguments):
        return None
    substitution = dict(initial or {})
    for expected, actual in zip(pattern.arguments, ground.arguments):
        if _is_var(expected):
            previous = substitution.get(expected)
            if previous is not None and previous != actual:
                return None
            substitution[expected] = actual
        elif expected != actual:
            return None
    return substitution


def _instantiate(pattern: Atom, substitution: dict) -> Atom | None:
    values: list[str] = []
    for value in pattern.arguments:
        if _is_var(value):
            if value not in substitution:
                return None
            values.append(substitution[value])
        else:
            values.append(value)
    return _canon(Atom(pattern.predicate, tuple(values)))


def _premise_matches(premises: tuple[Atom, ...], facts: set[Atom], index: int = 0,
                     substitution: dict | None = None):
    if index == len(premises):
        yield dict(substitution or {}), ()
        return
    pattern = premises[index]
    for fact in facts:
        merged = _unify(pattern, fact, substitution)
        if merged is None:
            continue
        for final, tail in _premise_matches(premises, facts, index + 1, merged):
            yield final, (fact,) + tail


def _is_degenerate(atom: Atom) -> bool:
    """退化結論を弾く: 同一線分の平行/垂直/合同、共線の重複点、同一角の等角など。

    推移律が同じ事実を 2 回マッチさせて para(A,B,A,B) のような自明な
    結論を生成するのを防ぐ（導出は正しいが全角法の線形系を汚すだけ）。
    """
    name, args = atom.predicate, atom.arguments
    if name in ("para", "perp", "cong") and len(args) == 4:
        return (args[0], args[1]) == (args[2], args[3])
    if name == "coll" and len(args) == 3:
        return len({args[0], args[1], args[2]}) < 3
    if name == "cyclic" and len(args) == 4:
        return len(set(args)) < 4
    if name == "tri" and len(args) == 3:
        return len(set(args)) < 3
    if name in ("eqangle", "angrel", "angrel_ub") and len(args) >= 7:
        return (len(set(args[:3])) < 3 or len(set(args[3:6])) < 3 or args[:3] == args[3:6])
    if name == "eqangle" and len(args) == 6:
        return len(set(args[:3])) < 3 or len(set(args[3:])) < 3 or args[:3] == args[3:]
    if name == "angval" and len(args) == 4:
        return len(set(args[:3])) < 3
    if name == "mid" and len(args) == 3:
        return args[0] == args[2] or args[1] == args[2]
    return False


def fixpoint_closure(facts: Iterable[Atom], *, max_rounds: int = 30) -> tuple[set[Atom], list[tuple[str, str]]]:
    """型付き Atom を定理 bank で前向きに閉じる。 (facts, 導出記録) を返す。

    記録は (定理名, 結論の表示) のリスト。証明 DAG は後段の全角法が持つ
    線形系と certificate で再構成できる。
    """
    known = {_canon(fact) for fact in facts}
    rules = _rules()
    derived: list[tuple[str, str]] = []
    for _ in range(max_rounds):
        additions: dict[Atom, str] = {}
        for rule in rules:
            for substitution, _matched in _premise_matches(rule.premises, known):
                conclusion = _instantiate(rule.conclusion, substitution)
                if conclusion is None or _is_degenerate(conclusion):
                    continue
                if conclusion in known or conclusion in additions:
                    continue
                additions[conclusion] = rule.name
        # coll は _canon でソートされるため位置パターンの規則は使えない。
        # 手動導出: 三角形の 2 頂点と共線の 3 点目で新たな三角形を作る。
        for tri_atom in list(known) + list(additions):
            if tri_atom.predicate != "tri" or len(tri_atom.arguments) != 3:
                continue
            tri_set = set(tri_atom.arguments)
            for coll_atom in list(known):
                if coll_atom.predicate != "coll" or len(coll_atom.arguments) != 3:
                    continue
                coll_set = set(coll_atom.arguments)
                shared = tri_set & coll_set
                if len(shared) != 2:
                    continue
                extra = (coll_set - shared).pop()
                if extra in tri_set:
                    continue
                tri_only = (tri_set - shared).pop()
                # 三角形の非共有頂点と、共線上の点・共有頂点 1 つで分割三角形
                for shared_point in shared:
                    new_tri = _canon(Atom("tri", (tri_only, extra, shared_point)))
                    if new_tri not in known and new_tri not in additions:
                        additions[new_tri] = "collinear-splits-triangle"
        # 等辺の共有端点は二等辺三角形を作る（3 点が既知の共線に載っていない時のみ）。
        # 共線上の等辺（例: "A B=C D" と別の "coll(A,B,D)"）から退化三角形を
        # 作ると内角 CSP が壊れるため、既知の coll と完全一致する組は除く。
        for cong_atom in list(known):
            if cong_atom.predicate != "cong" or len(cong_atom.arguments) != 4:
                continue
            p1, q1, p2, q2 = cong_atom.arguments
            shared = set((p1, q1)) & set((p2, q2))
            if len(shared) != 1:
                continue
            (vertex,) = shared
            others = [x for x in (p1, q1, p2, q2) if x != vertex]
            if len(set(others)) != 2:
                continue
            a, b = others
            collinear = any(
                atom.predicate == "coll" and len(atom.arguments) == 3
                and set(atom.arguments) == {vertex, a, b}
                for atom in known
            )
            if collinear:
                continue
            new_tri = _canon(Atom("tri", (vertex, a, b)))
            if new_tri not in known and new_tri not in additions:
                additions[new_tri] = "cong-implies-isosceles-triangle"
            # 底角の等しさ（既存規則と同じ向き: ∠(v,a,b) = ∠(a,b,v)）
            if new_tri in known or new_tri in additions:
                eq = _canon(Atom("eqangle", (vertex, a, b, a, b, vertex)))
                if eq not in known and eq not in additions:
                    additions[eq] = "isosceles-base-angles"
        # 接弦定理: 接点 T の接線（合成点 tgt_T）と弦 TA のなす角は、
        # 反対側の円周角 ∠ABT に等しい（有向角 mod 180 で一致）。
        for tangent_atom in list(known) + list(additions):
            if tangent_atom.predicate != "tangent_at" or len(tangent_atom.arguments) != 2:
                continue
            tpt, center = tangent_atom.arguments
            on_center = [
                fact.arguments[0]
                for fact in known
                if fact.predicate == "oncircle" and len(fact.arguments) == 2
                and fact.arguments[1] == center
            ]
            for a_pt in on_center:
                for b_pt in on_center:
                    if len({a_pt, b_pt, tpt}) != 3:
                        continue
                    conc = _canon(Atom("eqangle", (a_pt, tpt, f"tgt_{tpt}", a_pt, b_pt, tpt)))
                    if conc not in known and conc not in additions:
                        additions[conc] = "tangent-chord-angle"
        if not additions:
            break
        for conclusion in sorted(additions, key=lambda item: (item.predicate, item.arguments)):
            derived.append((additions[conclusion], _render(conclusion)))
        known |= set(additions)
    return known, derived


def _render(atom: Atom) -> str:
    return f"{atom.predicate}({','.join(atom.arguments)})"


# ---------------------------------------------------------------------------
# 全角法: 線分方向のアーベル群で角度の線形系を解く
# ---------------------------------------------------------------------------

@dataclass
class AngleSystem:
    """有向角を線分方向 θ(line) の差 mod 180 として扱う線形系。

    閉包済み Atom から方程式を作る:
      coll(A,B,C)      θ(AB) = θ(BC) = θ(AC)
      para(AB,CD)      θ(AB) = θ(CD)
      perp(AB,CD)      θ(CD) = θ(AB) + 90
      eqangle(ABC,DEF) (θ(BC)−θ(BA)) = (θ(EF)−θ(ED))
      angval(ABC,v)    θ(BC)−θ(BA) = v mod 180
    """

    def __init__(self, atoms: Iterable[Atom]) -> None:
        self.atoms = {_canon(atom) for atom in atoms}
        self.lines: dict[tuple[str, str], sp.Symbol] = {}
        self.equations: list[sp.Expr] = []
        self.angval_choices: list[tuple[sp.Expr, sp.Expr]] = []
        self.eqangle_choices: list[tuple[sp.Expr, sp.Expr]] = []
        self._eqangle_keys: set[tuple[str, str]] = set()
        self.perp_choices: list[sp.Expr] = []
        self.angrel_choices: list[list[tuple[sp.Expr, sp.Integer]]] = []
        self.angrel_csp: list[tuple[sp.Expr, tuple[str, frozenset], Optional[tuple[str, frozenset]],
                                     Optional[sp.Expr], bool]] = []
        self._angrel_keys: set[tuple] = set()
        self.triangles: list[tuple[str, str, str]] = []
        self.quads: list[tuple[str, str, str, str]] = []
        self.polys: list[tuple[str, ...]] = []
        self.collinear: list[tuple[str, str, str]] = []
        self._build()

    def _line(self, p: str, q: str) -> sp.Symbol:
        key = tuple(sorted((p, q)))
        if key not in self.lines:
            self.lines[key] = sp.Symbol(f"t_{key[0]}{key[1]}", real=True)
        return self.lines[key]

    def _directed(self, a: str, b: str, c: str) -> sp.Expr:
        """∠ABC の有向角: θ(BC) − θ(BA) mod 180"""
        return self._line(b, c) - self._line(b, a)

    def _build(self) -> None:
        for atom in sorted(self.atoms, key=lambda item: (item.predicate, item.arguments)):
            name, args = atom.predicate, atom.arguments
            if name == "coll" and len(args) == 3:
                a, b, c = args
                self.equations.append(self._line(a, b) - self._line(b, c))
                self.equations.append(self._line(a, b) - self._line(a, c))
                self.collinear.append(args)
            elif name == "tri" and len(args) == 3:
                self.triangles.append(args)
            elif name == "cyclic" and len(args) == 4:
                self.quads.append(args)
            elif name == "poly" and 3 <= len(args) <= 10:
                self.polys.append(args)
            elif name == "angrel" and len(args) == 7:
                a1, b1, c1, d1, e1, f1, k = args
                kk = sp.sympify(k)
                key = (kk, (b1, frozenset((a1, c1))), (e1, frozenset((d1, f1))))
                if key in self._angrel_keys:
                    continue
                self._angrel_keys.add(key)
                expr = kk * self._directed(a1, b1, c1) - self._directed(d1, e1, f1)
                n_off = int(sp.ceiling(kk))
                self.angrel_choices.append(
                    [(expr, sp.Integer(m * 180)) for m in range(n_off)])
                self.angrel_csp.append(
                    (kk, (b1, frozenset((a1, c1))), (e1, frozenset((d1, f1))), None, False))
            elif name == "angrel_ub" and len(args) == 8:
                p, q, r, s, a1, b1, c1, k = args
                kk = sp.sympify(k)
                key = (kk, (b1, frozenset((a1, c1))),
                       frozenset(((p, q), (r, s))))
                if key in self._angrel_keys:
                    continue
                self._angrel_keys.add(key)
                between = self._line(r, s) - self._line(p, q)
                expr = kk * self._directed(a1, b1, c1) - between
                n_off = int(sp.ceiling(kk))
                options = [(expr, sp.Integer(m * 180)) for m in range(n_off)]
                options += [(-expr, sp.Integer(m * 180)) for m in range(n_off)]
                self.angrel_choices.append(options)
                self.angrel_csp.append(
                    (kk, (b1, frozenset((a1, c1))), None, between, True))
            elif name == "para" and len(args) == 4:
                a, b, c, d = args
                self.equations.append(self._line(a, b) - self._line(c, d))
            elif name == "tangent_at" and len(args) == 2:
                tangent_pt, center = args
                tangent_line = self._line(tangent_pt, f"tgt_{tangent_pt}")
                self.equations.append(
                    sp.Rational(2) * (tangent_line - self._line(tangent_pt, center)) - 180
                )
            elif name == "perp" and len(args) == 4:
                a, b, c, d = args
                if {a, b} & {c, d}:
                    # 頂点を共有する垂直は閉包の angval(...,90) が正確に
                    # 90° を定めるので、ここでは方程式を足さない
                    # （両方を足すと ±90 の代表が食い違って EmptySet になる）。
                    continue
                # 全角群では垂直は 2(θ1−θ2) ≡ 180 (mod 360)。±90 の両枝が
                # 同じ線形式に収まる（Chou/Gao/Zhang 1996 の全角関係）。
                self.perp_choices.append(
                    sp.Rational(2) * (self._line(a, b) - self._line(c, d)) - 180
                )
            elif name == "eqangle" and len(args) == 6:
                a, b, c, d, e, f = args
                expr = self._directed(a, b, c) - self._directed(d, e, f)
                canon = sorted((str(expr), str(-expr)))
                key = tuple(canon)
                if key not in self._eqangle_keys:
                    self._eqangle_keys.add(key)
                    self.eqangle_choices.append(expr)
            elif name == "angval" and len(args) == 4:
                a, b, c, value = args
                expr = self._value_expr(value)
                if expr is not None and expr != 0:
                    # 有向角 mod 180 では内角 v は ±v のどちらでもあり得る。
                    # 向きの代表（符号）は _solve で全組合せを試す。
                    self.angval_choices.append((self._directed(a, b, c), expr))

    @staticmethod
    def _value_expr(value: str) -> sp.Expr | None:
        cleaned = value.strip()
        try:
            return sp.sympify(cleaned)
        except Exception:  # noqa: BLE001
            return None

    def goal_value(self, a: str, b: str, c: str) -> Optional[sp.Expr]:
        """∠ABC の値が全代表枝で一意に定まる時だけ (0,180) の実数値を返す。

        有向角は mod 180 の群なので、正確な Q 線形系には向きの代表（枝）が
        ある: 垂直 ±90、与角は内角 v に対し有向代表 {v, −v}（90° は
        同一クラスなので 1 枝）、等角は差が 0 か ±180、角の倍数 angrel は
        k·directed − directed = m·180（m=0..k−1、無向の間の角は ± の両向き）。
        全枝を解き、ゴール角が全枝で同じ値に定まる時だけ答える（誤答 0）。
        """
        n_perp = len(self.perp_choices)
        # 内角 v の有向代表: v, v−180, −v, 180−v（90° は v と −v の 2 種）。
        # 代表は実数としての線形式の等式なので、補角（180−v）側を落とすと
        # 鈍角の内角を線形系が弾いてしまう（要 4 代表）。
        ang_pairs_options = [
            ((sp.Integer(1), sp.Integer(0)), (sp.Integer(1), sp.Integer(-1)),
             (sp.Integer(-1), sp.Integer(0)), (sp.Integer(-1), sp.Integer(1)))
            if sp.simplify(value - 90) != 0
            else ((sp.Integer(1), sp.Integer(0)), (sp.Integer(-1), sp.Integer(0)))
            for _expr, value in self.angval_choices
        ]
        n_branches = (2 ** n_perp)
        for options in ang_pairs_options:
            n_branches *= len(options)
        n_branches *= (3 ** len(self.eqangle_choices))
        for options in self.angrel_choices:
            n_branches *= len(options)
        if n_branches > 20000:
            return None
        candidates: set[str] = set()
        for perp_signs in _product((sp.Integer(1), sp.Integer(-1)), repeat=n_perp):
            for ang_pairs in _product(*ang_pairs_options):
                for eqa_offsets in _product((sp.Integer(0), sp.Integer(180), sp.Integer(-180)),
                                            repeat=len(self.eqangle_choices)):
                    for angrel_picks in _product(*self.angrel_choices):
                        assignments = self._solve_branch(
                            perp_signs, ang_pairs, eqa_offsets, angrel_picks)
                        if assignments is None:
                            continue
                        goal = sp.simplify(self._directed(a, b, c).subs(assignments))
                        if goal.free_symbols or not goal.is_number:
                            continue
                        value = sp.nsimplify(goal) % 180
                        value = sp.simplify(value)
                        if value == 0:
                            continue
                        if not (0 < value < 180):
                            value = sp.simplify(value + 180)
                        if not (0 < value < 180):
                            continue
                        interior = self._disambiguate(a, b, c, value, assignments)
                        if interior is not None:
                            candidates.add(sp.sstr(interior))
        if len(candidates) == 1:
            return sp.sympify(next(iter(candidates)))
        return None

    def _pins(self) -> dict[tuple[str, frozenset], sp.Expr]:
        """angval 原子は『内角がちょうど v』を主張する。

        有向角 mod 180 の方程式（±v の両枝）だけでは内角 60 と 120 を
        区別できないので、閉包済み原子集合の angval を内角の pin として
        向きの列挙に持ち込む。
        """
        pins: dict[tuple[str, frozenset], sp.Expr] = {}
        for atom in self.atoms:
            if atom.predicate == "angval" and len(atom.arguments) == 4:
                a, b, c, value = atom.arguments
                expr = self._value_expr(value)
                if expr is not None and 0 < sp.simplify(expr) < 180:
                    pins[(b, frozenset((a, c)))] = expr
        return pins

    def _solve_branch(self, perp_signs: tuple[sp.Integer, ...],
                      ang_pairs: tuple[tuple[sp.Integer, sp.Integer], ...],
                      eqa_offsets: tuple[sp.Integer, ...],
                      angrel_picks: tuple[tuple[sp.Expr, sp.Integer], ...]) -> Optional[dict]:
        equations = list(self.equations)
        for expr, sign in zip(self.perp_choices, perp_signs):
            equations.append(expr * sign)
        for (expr, value), (sign, delta) in zip(self.angval_choices, ang_pairs):
            equations.append(expr - sign * value - 180 * delta)
        for expr, offset in zip(self.eqangle_choices, eqa_offsets):
            equations.append(expr - offset)
        for expr, offset in angrel_picks:
            equations.append(expr - offset)
        symbols = list(self.lines.values())
        try:
            solution = sp.linsolve(equations, symbols)
        except Exception:  # noqa: BLE001
            return None
        if solution is sp.EmptySet:
            return None
        if not isinstance(solution, sp.FiniteSet) or not solution.args:
            return None
        return dict(zip(symbols, solution.args[0]))

    def _disambiguate(self, a: str, b: str, c: str, value: sp.Expr,
                      assignments: dict) -> Optional[sp.Expr]:
        """有向角 mod 180 の値 v は内角 v か 180−v のどちらか。

        内角の CSP:
          - 各角 (頂点, 端点組) は有向値 v（数値に定まったものだけ）に対し
            内角 ∈ {v, 180−v} の 2 択
          - 同一頂点を通る同一直線上の端点を持つ角は同一の内角（key の
            collapse: ∠BAC と ∠EAF は E∈AC, F∈AB なら同じ角）
          - angval の pin は内角を固定（collapse された組にも適用）
          - 三角形: 3 内角の和 = 180
          - 共円四角形: 向かい合う 2 内角の和 = 180
          - 多角形: 内角の和 = (n−2)·180
          - 角の倍数 angrel: k·内角(X) ≡ 内角(Y) (mod 360)（無向の間の角は ±）
        全変数の択を列挙し、ゴール角の内角が一意に定まる時だけ答える。
        """
        pins = self._pins()
        goal_key = (b, frozenset((a, c)))

        def directed_value(p: str, q: str, r: str) -> Optional[sp.Expr]:
            try:
                item = sp.simplify(self._directed(p, q, r).subs(assignments))
            except Exception:  # noqa: BLE001
                return None
            if item.free_symbols or not item.is_number:
                return None
            item = sp.nsimplify(item) % 180
            item = sp.simplify(item)
            if not (0 < item < 180):
                return None
            return item

        def expr_value(expr: sp.Expr) -> Optional[sp.Expr]:
            try:
                item = sp.simplify(expr.subs(assignments))
            except Exception:  # noqa: BLE001
                return None
            if item.free_symbols or not item.is_number:
                return None
            item = sp.nsimplify(item) % 180
            item = sp.simplify(item)
            if not (0 < item < 180):
                return None
            return item

        # 登場する角の有向値（数値に定まったものだけ）。
        # 三角形・四角形・多角形に加え、等角・角の倍数の原子も含める
        # （角の分割 ∠CAD + ∠DAB = ∠CAB の制約に必要な頂点 A の角が
        # 三角形だけからは出てこないため）。
        raw: dict[tuple[str, frozenset], sp.Expr] = {}
        for t1, t2, t3 in self.triangles:
            for p, q, r in ((t1, t2, t3), (t2, t3, t1), (t3, t1, t2)):
                value_d = directed_value(p, q, r)
                if value_d is not None:
                    raw.setdefault((q, frozenset((p, r))), value_d)
        for q1, q2, q3, q4 in self.quads:
            for p, q, r in ((q1, q2, q3), (q2, q3, q4), (q3, q4, q1), (q4, q1, q2)):
                value_d = directed_value(p, q, r)
                if value_d is not None:
                    raw.setdefault((q, frozenset((p, r))), value_d)
        for vertices in self.polys:
            n = len(vertices)
            for i, q in enumerate(vertices):
                p, r = vertices[i - 1], vertices[(i + 1) % n]
                value_d = directed_value(p, q, r)
                if value_d is not None:
                    raw.setdefault((q, frozenset((p, r))), value_d)
        for atom in self.atoms:
            if atom.predicate == "eqangle" and len(atom.arguments) == 6:
                for triple in (atom.arguments[:3], atom.arguments[3:]):
                    p, q, r = triple
                    value_d = directed_value(p, q, r)
                    if value_d is not None:
                        raw.setdefault((q, frozenset((p, r))), value_d)
            elif atom.predicate == "angrel" and len(atom.arguments) == 7:
                for triple in (atom.arguments[:3], atom.arguments[3:6]):
                    p, q, r = triple
                    value_d = directed_value(p, q, r)
                    if value_d is not None:
                        raw.setdefault((q, frozenset((p, r))), value_d)
            elif atom.predicate == "angrel_ub" and len(atom.arguments) == 8:
                p, q, r = atom.arguments[4:7]
                value_d = directed_value(p, q, r)
                if value_d is not None:
                    raw.setdefault((q, frozenset((p, r))), value_d)

        coll_triples = {frozenset(atom.arguments) for atom in self.atoms
                        if atom.predicate == "coll" and len(atom.arguments) == 3}

        def same_line_at(v: str, u: str, w: str) -> bool:
            if u == w:
                return True
            return frozenset((v, u, w)) in coll_triples

        # 同一の内角の key を union-find でまとめる
        keys = list(raw.keys())
        parent = {key: key for key in keys}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x, y):
            rx, ry = find(x), find(y)
            if rx != ry:
                parent[max(rx, ry)] = min(rx, ry)

        for i, key1 in enumerate(keys):
            v1, ends1 = key1
            for key2 in keys[i + 1:]:
                v2, ends2 = key2
                if v1 != v2:
                    continue
                p, q = ends1
                r, s = ends2
                if (same_line_at(v1, p, r) and same_line_at(v1, q, s)) or \
                        (same_line_at(v1, p, s) and same_line_at(v1, q, r)):
                    union(key1, key2)

        angles: dict[tuple[str, frozenset], sp.Expr] = {}
        class_pins: dict[tuple[str, frozenset], Optional[sp.Expr]] = {}

        def canon(key):
            return find(key) if key in raw else key

        for key, value_d in raw.items():
            rep = find(key)
            if rep not in angles:
                angles[rep] = value_d
            pin = pins.get(key)
            if pin is not None:
                existing = class_pins.get(rep)
                if existing is not None and sp.simplify(existing - pin) != 0:
                    return None
                class_pins[rep] = pin

        if goal_key not in raw:
            # 三角形・四角形・多角形・等角に含まれない角は、pin 済み（与値）
            # または自己補角（90°）の時だけ答えられる。
            goal_pin = pins.get(goal_key)
            if goal_pin is not None:
                if sp.simplify(value - goal_pin) == 0 or sp.simplify(value + goal_pin - 180) == 0:
                    return goal_pin
                return None
            if sp.simplify(value - 90) == 0:
                return value
            return None
        goal_rep = find(goal_key)

        # 三角形の 3 和の制約（3 角とも数値の時だけ）
        triple_sums: list[tuple[tuple[str, frozenset], tuple[str, frozenset], tuple[str, frozenset]]] = []
        for t1, t2, t3 in self.triangles:
            keys_t = tuple((q, frozenset((p, r)))
                           for p, q, r in ((t1, t2, t3), (t2, t3, t1), (t3, t1, t2)))
            if all(key in raw for key in keys_t):
                triple_sums.append(tuple(canon(key) for key in keys_t))
        # 共円四角形の対角の和の制約（4 角とも数値の時だけ）
        quad_sums: list[tuple[tuple[str, frozenset], tuple[str, frozenset]]] = []
        for q1, q2, q3, q4 in self.quads:
            keys_t = ((q2, frozenset((q1, q3))), (q4, frozenset((q1, q3))),
                      (q1, frozenset((q2, q4))), (q3, frozenset((q2, q4))))
            if all(key in raw for key in keys_t):
                quad_sums.append((canon(keys_t[0]), canon(keys_t[1])))
                quad_sums.append((canon(keys_t[2]), canon(keys_t[3])))
        # 多角形の内角の和 (n−2)·180
        poly_sums: list[tuple[sp.Expr, tuple]] = []
        for vertices in self.polys:
            n = len(vertices)
            keys_t = tuple((vertices[i], frozenset((vertices[i - 1], vertices[(i + 1) % n])))
                           for i in range(n))
            if all(key in raw for key in keys_t):
                poly_sums.append((sp.Rational((n - 2) * 180),
                                  tuple(canon(key) for key in keys_t)))
        # 共線関係の制約:
        #   - 折り返し点 x の隣接角（直線上の内角の和 = 180）
        #   - 頂点 p での角の分割 ∠apx + ∠xpb = ∠apb
        # collapse で同一の角になってしまった組は制約にしない（同一直線の
        # 同じ側では隣接角は相等しいため和 180 の式は成立しない）。
        linear_pairs: list[tuple[tuple[str, frozenset], tuple[str, frozenset]]] = []
        split_sums: list[tuple[tuple[str, frozenset], tuple[str, frozenset], tuple[str, frozenset]]] = []
        for a, x, b in self.collinear:
            for p in {point for key in raw for point in key[1]}:
                key_axp = (x, frozenset((a, p)))
                key_bxp = (x, frozenset((b, p)))
                if key_axp in raw and key_bxp in raw and canon(key_axp) != canon(key_bxp):
                    linear_pairs.append((canon(key_axp), canon(key_bxp)))
                key_pax = (p, frozenset((a, x)))
                key_pxb = (p, frozenset((x, b)))
                key_pab = (p, frozenset((a, b)))
                if key_pax in raw and key_pxb in raw and key_pab in raw:
                    triple = (canon(key_pax), canon(key_pxb), canon(key_pab))
                    if len(set(triple)) == 3:
                        split_sums.append(triple)
        # 角の倍数の制約: k·内角(X) ≡ 内角(Y) (mod 360)
        angrel_csp: list[tuple[sp.Expr, tuple[str, frozenset], Optional[tuple[str, frozenset]],
                               Optional[sp.Expr], bool]] = []
        for kk, key_x, key_y, y_expr, unoriented in self.angrel_csp:
            if key_x not in raw:
                continue
            if key_y is not None and key_y not in raw:
                continue
            angrel_csp.append((kk, canon(key_x),
                               canon(key_y) if key_y is not None else None,
                               y_expr, unoriented))

        variables = list(angles.keys())
        n = len(variables)
        if n > 14:
            return None
        # pin 済みの角は内角が確定しているので列挙しない（枝数を大幅に削減）。
        unpinned = [key for key in variables if key not in class_pins]
        goal_values: set[str] = set()
        for bits in range(1 << len(unpinned)):
            picked: dict[tuple[str, frozenset], sp.Expr] = {}
            ok = True
            for idx, key in enumerate(unpinned):
                v = angles[key]
                interior = sp.simplify(180 - v) if (bits >> idx) & 1 else v
                if not (0 < interior < 180):
                    ok = False
                    break
                picked[key] = interior
            if not ok:
                continue
            for key in variables:
                if key in picked:
                    continue
                v = angles[key]
                pin = class_pins[key]
                if sp.simplify(pin - v) != 0 and sp.simplify(pin - (180 - v)) != 0:
                    ok = False
                    break
                picked[key] = pin
            for keys_t in triple_sums:
                if sp.simplify(sum(picked[key] for key in keys_t) - 180) != 0:
                    ok = False
                    break
            if not ok:
                continue
            for key1, key2 in quad_sums:
                if sp.simplify(picked[key1] + picked[key2] - 180) != 0:
                    ok = False
                    break
            if not ok:
                continue
            for total, keys_t in poly_sums:
                if sp.simplify(sum(picked[key] for key in keys_t) - total) != 0:
                    ok = False
                    break
            if not ok:
                continue
            for key1, key2 in linear_pairs:
                if sp.simplify(picked[key1] + picked[key2] - 180) != 0:
                    ok = False
                    break
            if not ok:
                continue
            for key1, key2, key3 in split_sums:
                if sp.simplify(picked[key1] + picked[key2] - picked[key3]) != 0:
                    ok = False
                    break
            if not ok:
                continue
            for kk, key_x, key_y, y_expr, unoriented in angrel_csp:
                ix = picked[key_x]
                if key_y is not None:
                    iy_options = (picked[key_y],)
                else:
                    v_y = expr_value(y_expr)
                    if v_y is None:
                        ok = False
                        break
                    iy_options = (v_y, sp.simplify(180 - v_y))
                satisfied = False
                for iy in iy_options:
                    if sp.Mod(kk * ix - iy, 360) == 0:
                        satisfied = True
                        break
                    if unoriented and sp.Mod(kk * ix + iy, 360) == 0:
                        satisfied = True
                        break
                if not satisfied:
                    ok = False
                    break
            if not ok:
                continue
            goal_values.add(sp.sstr(picked[goal_rep]))
        if len(goal_values) == 1:
            return sp.sympify(next(iter(goal_values)))
        return None


# ---------------------------------------------------------------------------
# 英語・LaTeXの幾何問題文 → 型付き Atom
# ---------------------------------------------------------------------------

class ProblemParser:
    """英語・LaTeXの幾何問題文からデータセット非依存の Atom を抽出する。"""

    def __init__(self, question: str) -> None:
        self.question = question
        text = _plain(question)
        text = re.sub(r"\bangle\b", "ANG", text, flags=re.IGNORECASE)
        self.text = text
        self.atoms: list[Atom] = []
        self.goal: Optional[tuple[str, str, str]] = None
        self.goal_symbol: Optional[str] = None
        self._center: Optional[str] = None
        self._parse()

    # -- 三角形・四角形 --------------------------------------------------
    def _parse(self) -> None:
        text = self.text
        for match in re.finditer(
            r"(?:TRIANGLE|[Tt]riangle)s?\s*(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])(?![A-Za-z])",
            text,
        ):
            a, b, c = match.group(1), match.group(2), match.group(3)
            self._parse_triangle(a, b, c)
        for match in re.finditer(
            r"(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])(?![A-Za-z])"
            r"\s+(?:is|are)\s+(?:an?\s+)?(?:TRIANGLE|[Tt]riangle)s?",
            text,
        ):
            a, b, c = match.group(1), match.group(2), match.group(3)
            self._parse_triangle(a, b, c)
        for match in re.finditer(
            r"(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])(?![A-Za-z])"
            r"\s+(?:is|are)\s+(?:an?\s+)?"
            r"(?:equilateral|isosceles|right-?angled)\s+(?:TRIANGLE|[Tt]riangle)s?",
            text,
        ):
            a, b, c = match.group(1), match.group(2), match.group(3)
            self._parse_triangle(a, b, c)
        for match in re.finditer(
            r"(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])(?![A-Za-z])"
            r"\s+(?:is|are)\s+(?:an?\s+)?congruent\s+"
            r"(?:(?:equilateral|isosceles|right-?angled)\s+)?(?:TRIANGLE|[Tt]riangle)s?",
            text,
        ):
            a, b, c = match.group(1), match.group(2), match.group(3)
            self._parse_triangle(a, b, c)
        # "V W X and X Y Z are congruent equilateral triangles" — 2 つの三角形
        for match in re.finditer(
            r"(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])\s+(?i:and)\s+"
            r"(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])(?![A-Za-z])"
            r"\s+(?i:are)\s+(?i:an?)?\s*(?i:congruent)\s+"
            r"(?:(?i:equilateral|isosceles|right-?angled)\s+)?(?:TRIANGLE|[Tt]riangle)s?",
            text,
        ):
            self._parse_triangle(match.group(1), match.group(2), match.group(3))
            self._parse_triangle(match.group(4), match.group(5), match.group(6))
        self._parse_segments()
        self._parse_angles()
        self._parse_perp_para()
        self._parse_midpoints()
        self._parse_collinear()
        self._parse_circle()
        self._parse_goal()
        # 相似・合同三角形（6点対応）
        for match in re.finditer(
            r"(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])(?![A-Za-z])\s+(?i:is|are)\s+"
            r"(?i:similar)\s+(?i:to)\s+(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])(?![A-Za-z])",
            text,
        ):
            g = match.groups()
            self._parse_triangle(*g[:3])
            self._parse_triangle(*g[3:])
            self.atoms.append(Atom("sim_tri", tuple(g)))
        for match in re.finditer(
            r"(?i:triangle)s?\s*(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])(?![A-Za-z])"
            r"\s+(?i:is)\s+(?i:similar)\s+(?i:to)\s+(?i:triangle)s?\s*"
            r"(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])(?![A-Za-z])",
            text,
        ):
            g = match.groups()
            self._parse_triangle(*g[:3])
            self._parse_triangle(*g[3:])
            self.atoms.append(Atom("sim_tri", tuple(g)))
        for match in re.finditer(
            r"(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])\s+(?i:and)\s+"
            r"(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])(?![A-Za-z])"
            r"\s+(?i:are)\s+(?i:similar)\s+(?:TRIANGLE|[Tt]riangle)s?",
            text,
        ):
            g = match.groups()
            self._parse_triangle(*g[:3])
            self._parse_triangle(*g[3:])
            self.atoms.append(Atom("sim_tri", tuple(g)))
        for match in re.finditer(
            r"(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])(?![A-Za-z])\s+(?i:is|are)\s+"
            r"(?i:congruent)\s+(?i:to)\s+(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])(?![A-Za-z])",
            text,
        ):
            g = match.groups()
            self._parse_triangle(*g[:3])
            self._parse_triangle(*g[3:])
            self.atoms.append(Atom("congr_tri", tuple(g)))
        for match in re.finditer(
            r"(?i:triangle)s?\s*(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])(?![A-Za-z])"
            r"\s+(?i:is)\s+(?i:congruent)\s+(?i:to)\s+(?i:triangle)s?\s*"
            r"(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])(?![A-Za-z])",
            text,
        ):
            g = match.groups()
            self._parse_triangle(*g[:3])
            self._parse_triangle(*g[3:])
            self.atoms.append(Atom("congr_tri", tuple(g)))
        for match in re.finditer(
            r"(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])\s+(?i:and)\s+"
            r"(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])(?![A-Za-z])"
            r"\s+(?i:are)\s+(?i:congruent)\s+(?:TRIANGLE|[Tt]riangle)s?",
            text,
        ):
            g = match.groups()
            self._parse_triangle(*g[:3])
            self._parse_triangle(*g[3:])
            self.atoms.append(Atom("congr_tri", tuple(g)))
        # 多角形（四角形以上、正多角形は内角 pin + 隣接内角の等角連鎖）
        polygon_names = (
            r"(?:quadrilateral|pentagon|hexagon|heptagon|octagon|nonagon|decagon)"
        )
        for match in re.finditer(
            r"(?i:(?:regular\s+)?(?:quadrilateral|pentagon|hexagon|heptagon|"
            r"octagon|nonagon|decagon))s?\s*(?<![A-Za-z])([A-Z](?:\s*[A-Z]){3,9})(?![A-Za-z])",
            text,
        ):
            letters = [g.upper() for g in re.findall(r"[A-Z]", match.group(0))]
            shape = re.match(r"[A-Za-z ]+", match.group(0)).group(0).strip().lower()
            self._emit_polygon(letters, shape)
        for match in re.finditer(
            r"(?<![A-Za-z])([A-Z](?:\s*[A-Z]){3,9})(?![A-Za-z])\s+(?i:is|are)\s+"
            r"(?i:a|an)?\s*(?i:regular)?\s*(?:quadrilateral|pentagon|hexagon|"
            r"heptagon|octagon|nonagon|decagon)s?",
            text,
        ):
            letters = [g.upper() for g in re.findall(r"[A-Z]", match.group(1))]
            shape = match.group(0).split()[-1].lower()
            if re.search(r"(?i:regular)", match.group(0)):
                shape = "regular " + shape
            self._emit_polygon(letters, shape)

    def _emit_polygon(self, letters: list[str], shape: str) -> None:
        if len(letters) < 4 or len(letters) > 10:
            return
        n = len(letters)
        shape = shape.strip()
        regular = "regular" in shape
        kind = "square" if n == 4 and "square" in shape else None
        self.atoms.append(Atom("poly", tuple(letters)))
        if n == 4 and kind == "square":
            a, b, c, d = letters
            self.atoms.extend((
                Atom("para", (a, b, d, c)),
                Atom("para", (b, c, a, d)),
                Atom("perp", (a, b, b, c)),
                Atom("cong", (a, b, b, c)),
                Atom("cong", (b, c, c, d)),
            ))
        elif "rectangle" in shape or "parallelogram" in shape:
            a, b, c, d = letters
            self.atoms.extend((
                Atom("para", (a, b, d, c)),
                Atom("para", (b, c, a, d)),
            ))
            if "rectangle" in shape:
                self.atoms.append(Atom("perp", (a, b, b, c)))
        if regular:
            interior = sp.nsimplify(sp.Rational((n - 2) * 180, n))
            self.atoms.append(Atom("angval", (letters[-1], letters[0], letters[1],
                                              str(interior))))
            for i in range(n - 1):
                self.atoms.append(Atom(
                    "eqangle",
                    (letters[i], letters[i + 1], letters[(i + 2) % n],
                     letters[i + 1], letters[(i + 2) % n], letters[(i + 3) % n]),
                ))

    def _parse_triangle(self, a: str, b: str, c: str) -> None:
        text = self.text
        self.atoms.append(Atom("tri", (a, b, c)))
        right = re.search(
            rf"(?i:right-?angled)\s+(?i:triangle)s?\s*{a}\s*{b}\s*{c}\s+(?i:at)\s+([{a}{b}{c}])",
            text,
        ) or re.search(
            rf"(?i:triangle)s?\s*{a}\s*{b}\s*{c}\s+(?i:is)?\s*(?i:right-?angled)\s+(?i:at)\s+([{a}{b}{c}])",
            text,
        )
        if right:
            vertex = right.group(1).upper()
            others = [p for p in (a, b, c) if p != vertex]
            if len(others) == 2:
                self.atoms.append(Atom("angval", (others[0], vertex, others[1], "90")))
        if re.search(
            r"(?i:equilateral)\s+(?i:triangle)s?\s*" + f"{a}\\s*{b}\\s*{c}"
            + r"|" + f"(?i:triangle)s?\\s*{a}\\s*{b}\\s*{c}\\s+(?i:is\\s+(?i:an)?\\s*)?(?i:equilateral)"
            + r"|" + f"{a}\\s*{b}\\s*{c}\\s+(?i:is|are)\\s+(?i:an)?\\s*(?i:equilateral)\\s+(?i:triangle)s?",
            text,
        ):
            # 3 つの 60° を angval で与えると有向角の縮約（和 ≡ 0 mod 180）
            # と線形式が衝突して EmptySet になる。1 つの 60° の pin と
            # 等角関係（eqangle）で表現する。
            self.atoms.extend((
                Atom("cong", (a, b, b, c)),
                Atom("cong", (a, b, a, c)),
                Atom("angval", (b, a, c, "60")),
                Atom("eqangle", (a, b, c, b, c, a)),
                Atom("eqangle", (b, c, a, c, a, b)),
            ))
        if re.search(
            r"(?i:isosceles)\s+(?i:triangle)s?\s*" + f"{a}\\s*{b}\\s*{c}"
            + r"|" + f"(?i:triangle)s?\\s*{a}\\s*{b}\\s*{c}\\s+(?i:is|are)\\s+(?i:an)?\\s*(?i:isosceles)"
            + r"|" + f"{a}\\s*{b}\\s*{c}\\s+(?i:is|are)\\s+(?i:an)?\\s*(?i:isosceles)",
            text,
        ):
            self.atoms.append(Atom("cong", (a, b, a, c)))

    # -- 線分の長さ関係 --------------------------------------------------
    def _parse_segments(self) -> None:
        text = self.text
        segment_text = re.sub(
            r"ANG(?![a-z])\s*[A-Z]\s*[A-Z]\s*[A-Z]\s*"
            r"(?:=\s*ANG(?![a-z])\s*[A-Z]\s*[A-Z]\s*[A-Z])*\s*=\s*(?:\d+|[A-Za-zα-ωθ]+)",
            " ", text, flags=re.IGNORECASE,
        )
        # 連鎖 "AB=CD=EF" を分解して等長の組を作る
        for match in re.finditer(
            r"(?<![A-Za-z])([A-Z])\s*([A-Z])\s*(?:=\s*([A-Z])\s*([A-Z]))+",
            segment_text,
        ):
            letters = re.findall(r"[A-Z]", match.group(0))
            letters = [x.upper() for x in letters]
            pairs = [(letters[i], letters[i + 1]) for i in range(0, len(letters), 2)]
            for i, first in enumerate(pairs):
                for other in pairs[i + 1:]:
                    if first != other:
                        self.atoms.append(Atom("cong", (first[0], first[1], other[0], other[1])))

    # -- 角度 ------------------------------------------------------------
    def _parse_angles(self) -> None:
        text = self.text
        for match in re.finditer(
            r"(?:m\s*)?(?:ANG(?![A-Za-z])\s*)+(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])(?![A-Za-z])"
            r"\s*(?i:is|equals?|=\s*)\s*(\d+(?:\.\d+)?)(?:\s*deg|\s*degrees?|[oO°])?",
            text,
        ):
            a, b, c, value = match.group(1), match.group(2), match.group(3), match.group(4)
            if a.isalpha() and b.isalpha() and c.isalpha():
                self.atoms.append(Atom("angval", (a, b, c, value)))
        chain = re.compile(
            r"(?:ANG(?![A-Za-z])\s*)+(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])(?![A-Za-z])"
            r"((?:\s*=\s*ANG\s*([A-Z])\s*([A-Z])\s*([A-Z]))+)"
            r"\s*=\s*(\d+(?:\.\d+)?)(?:\s*deg|\s*degrees?|\^?\s*[oO°])?"
        )
        for match in chain.finditer(text):
            angles = [match.group(1, 2, 3)]
            for sub in re.finditer(r"ANG\s*([A-Z])\s*([A-Z])\s*([A-Z])", match.group(4)):
                angles.append(sub.group(1, 2, 3))
            value = match.group(8)
            for a, b, c in angles:
                if a.isalpha() and b.isalpha() and c.isalpha():
                    self.atoms.append(Atom("angval", (a, b, c, value)))
        for match in re.finditer(
            r"(?:ANG(?![A-Za-z])\s*)+(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])(?![A-Za-z])"
            r"\s*=\s*ANG\s*([A-Z])\s*([A-Z])\s*([A-Z])", text,
        ):
            self.atoms.append(Atom("eqangle", match.groups()))
        sym = re.search(
            r"ANG\s*([A-Z])\s*([A-Z])\s*([A-Z])\s*=\s*ANG\s*([A-Z])\s*([A-Z])\s*([A-Z])\s*=\s*([α-ωA-Za-z])",
            text,
        )
        if sym:
            self.atoms.append(Atom("eqangle", sym.group(1, 2, 3, 4, 5, 6)))
            self.goal_symbol = sym.group(7)
        for match in re.finditer(
            r"([A-Z])\s*([A-Z])\s+(?i:is)\s+(?i:the)?\s*(?:ANG(?![A-Za-z])\s*)?(?i:bisector)\s+(?i:of)\s+"
            r"(?i:the)?\s*ANG(?![A-Za-z])\s*(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])(?![A-Za-z])",
            text,
        ):
            x, y = match.group(1), match.group(2)
            a, middle, b = match.group(3), match.group(4), match.group(5)
            if y == middle:
                self.atoms.append(Atom("eqangle", (a, middle, x, x, middle, b)))
            elif x == middle:
                self.atoms.append(Atom("eqangle", (a, middle, y, y, middle, b)))
        # "AD is the angle bisector of the angle at A" — 頂点 A の角は
        # 既知の三角形から両端を取る
        for match in re.finditer(
            r"([A-Z])\s*([A-Z])\s+(?i:is)?\s*(?i:the)?\s*(?:ANG(?![A-Za-z])\s*)?(?i:bisector)\s+(?i:of)\s+"
            r"(?i:the)?\s*(?:ANG(?![A-Za-z])\s*)?(?i:at)\s+([A-Z])",
            text,
        ):
            vertex = match.group(3).upper()
            along = match.group(2).upper()
            if vertex == match.group(1).upper() and along != vertex:
                for atom in self.atoms:
                    if atom.predicate == "tri" and vertex in atom.arguments:
                        others = [p for p in atom.arguments if p != vertex]
                        if len(others) == 2:
                            a, b = others
                            self.atoms.append(Atom("eqangle", (a, vertex, along, along, vertex, b)))
                            break

        # 直角: "ANG ABC is a right angle"
        for match in re.finditer(
            r"(?:ANG(?![A-Za-z])\s*)+(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])(?![A-Za-z])"
            r"\s+(?i:is)\s+(?i:a)?\s*(?i:right)\s+(?i:angle)",
            text,
        ):
            self.atoms.append(Atom("angval", (match.group(1), match.group(2),
                                              match.group(3), "90")))
        # 反射角: "reflex ANG abc is v" → 内角 360−v
        for match in re.finditer(
            r"(?i:reflex)\s+(?i:angle)?\s*(?:ANG(?![A-Za-z])\s*)*"
            r"(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])(?![A-Za-z])"
            r"\s+(?i:is|equals?)\s*(\d+(?:\.\d+)?)",
            text,
        ):
            a, b, c = match.group(1), match.group(2), match.group(3)
            v = sp.nsimplify(match.group(4))
            interior = 360 - v if v > 180 else v
            if 0 < interior < 180:
                self.atoms.append(Atom("angval", (a, b, c, str(sp.nsimplify(interior)))))
        # 反射角 at: "the reflex angle at P is 330" → 三角形文脈で 360−v
        for match in re.finditer(
            r"(?i:reflex)\s+(?i:angle)\s+(?i:at)\s+([A-Z])\s+(?i:is|equals?)\s*(\d+(?:\.\d+)?)",
            text,
        ):
            vertex = match.group(1).upper()
            v = sp.nsimplify(match.group(2))
            interior = 360 - v if v > 180 else v
            if 0 < interior < 180:
                for atom in self.atoms:
                    if atom.predicate == "tri" and vertex in atom.arguments:
                        others = [p for p in atom.arguments if p != vertex]
                        if len(others) == 2:
                            self.atoms.append(Atom("angval", (others[0], vertex,
                                                              others[1],
                                                              str(sp.nsimplify(interior)))))
                            break

        # 角の倍数: "ANG ABC is twice ANG DEF" / "is three times" / "is half of"
        word_mult = {
            "twice": 2, "double": 2, "two times": 2,
            "three times": 3, "four times": 4, "five times": 5,
        }
        for match in re.finditer(
            r"(?:ANG(?![A-Za-z])\s*)+(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])(?![A-Za-z])"
            r"\s+(?i:is)\s+(?i:(?:twice|double|two\s+times|three\s+times|four\s+times|"
            r"five\s+times|half|one\s+half))(?:\s+(?i:of))?\s*(?:ANG(?![A-Za-z])\s*)+"
            r"(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])(?![A-Za-z])",
            text,
        ):
            first = (match.group(1), match.group(2), match.group(3))
            second = (match.group(5), match.group(6), match.group(7))
            if not all(x.isalpha() and len(x) == 1 for x in first + second):
                continue
            word = match.group(4).lower()
            if word in ("half", "one half"):
                self.atoms.append(Atom("angrel", (*second, *first, "2")))
            else:
                self.atoms.append(Atom("angrel", (*first, *second, str(word_mult[word]))))
        # "is N times the size of ANG abc"
        for match in re.finditer(
            r"(?:ANG(?![A-Za-z])\s*)+(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])(?![A-Za-z])"
            r"\s+(?i:is)\s+(\d+)\s+(?i:times)\s+(?i:the)?\s*(?i:size|measure|value)?"
            r"\s*(?i:of)?\s*(?:ANG(?![A-Za-z])\s*)*(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])"
            r"(?![A-Za-z])",
            text,
        ):
            first = (match.group(1), match.group(2), match.group(3))
            second = (match.group(5), match.group(6), match.group(7))
            self.atoms.append(Atom("angrel", (*first, *second, match.group(4))))
        # 2 線分の間の角の倍数（無向）: "the (obtuse|acute) angle between PQ and RS
        # is four times the size of ANG abc" → angrel_ub(P,Q,R,S,a,b,c,k)
        word_between_mult = {
            "twice": 2, "double": 2, "two times": 2,
            "three times": 3, "four times": 4, "five times": 5,
            "half": "1/2", "one half": "1/2",
        }
        for match in re.finditer(
            r"(?i:the)?\s*(?i:acute|obtuse)?\s*(?i:angle)\s+(?i:between)\s+"
            r"(?<![A-Za-z])([A-Z])\s*([A-Z])(?![A-Za-z])\s+(?i:and)\s+"
            r"(?<![A-Za-z])([A-Z])\s*([A-Z])(?![A-Za-z])\s+(?i:is)\s+"
            r"(?i:(?:twice|double|two\s+times|three\s+times|four\s+times|five\s+times|"
            r"half|one\s+half))(?:\s+(?i:of))?\s*(?i:the)?\s*(?i:size|measure|value)?"
            r"\s*(?i:of)?\s*(?:ANG(?![A-Za-z])\s*)*(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])"
            r"(?![A-Za-z])",
            text,
        ):
            p, q = match.group(1).upper(), match.group(2).upper()
            r, s = match.group(3).upper(), match.group(4).upper()
            abc = (match.group(5), match.group(6), match.group(7))
            word = match.group(8).lower()
            self.atoms.append(Atom("angrel_ub", (p, q, r, s, *abc,
                                                 str(word_between_mult[word]))))
        for match in re.finditer(
            r"(?i:the)?\s*(?i:acute|obtuse)?\s*(?i:angle)\s+(?i:between)\s+"
            r"(?<![A-Za-z])([A-Z])\s*([A-Z])(?![A-Za-z])\s+(?i:and)\s+"
            r"(?<![A-Za-z])([A-Z])\s*([A-Z])(?![A-Za-z])\s+(?i:is)\s+(\d+)\s+(?i:times)\s+"
            r"(?i:the)?\s*(?i:size|measure|value)?\s*(?i:of)?\s*(?:ANG(?![A-Za-z])\s*)*"
            r"(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])(?![A-Za-z])",
            text,
        ):
            p, q = match.group(1).upper(), match.group(2).upper()
            r, s = match.group(3).upper(), match.group(4).upper()
            abc = (match.group(5), match.group(6), match.group(7))
            self.atoms.append(Atom("angrel_ub", (p, q, r, s, *abc, match.group(8))))
        # "the angle at A is 30"（三角形文脈、反射角と衝突しない）
        for match in re.finditer(
            r"(?<!reflex\s)(?i:the)?\s*(?:ANG(?![A-Za-z])\s*)?(?i:angle)\s+(?i:at)\s+"
            r"([A-Z])\s+(?i:is|equals?)\s*(\d+(?:\.\d+)?)",
            text,
        ):
            vertex = match.group(1).upper()
            value = match.group(2)
            for atom in self.atoms:
                if atom.predicate == "tri" and vertex in atom.arguments:
                    others = [p for p in atom.arguments if p != vertex]
                    if len(others) == 2:
                        self.atoms.append(Atom("angval", (others[0], vertex,
                                                          others[1], value)))
                        break

    # -- 垂直・並行 ------------------------------------------------------
    def _parse_perp_para(self) -> None:
        text = self.text
        for match in re.finditer(
            r"([A-Z])\s*([A-Z])\s+(?i:is)?\s*(?i:perpendicular\s+to)\s+([A-Z])\s*([A-Z])", text,
        ):
            self.atoms.append(Atom("perp", match.groups()))
        for match in re.finditer(
            r"([A-Z])\s*([A-Z])\s+(?i:is)?\s*(?i:the)?\s*(?i:height|altitude)\s+"
            r"(?i:from\s+(?:side\s+)?)?"
            r"([A-Z])\s*([A-Z])", text,
        ):
            x, y, p, q = (match.group(1).upper(), match.group(2).upper(),
                          match.group(3).upper(), match.group(4).upper())
            if y in (p, q):
                y, p = p, y
            if x != y and p != q and x not in (p, q):
                self.atoms.append(Atom("perp", (x, y, p, q)))
                self.atoms.append(Atom("coll", (p, y, q)))
        # "AD is the altitude of triangle ABC" — 頂点 A から対辺 BC への垂線
        for match in re.finditer(
            r"(?<![A-Za-z])([A-Z])\s*([A-Z])(?![A-Za-z])\s+(?i:is)\s+"
            r"(?i:an?|the)?\s*(?i:altitude)\s+(?i:of)\s+(?i:triangle)?\s*"
            r"(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])(?![A-Za-z])",
            text,
        ):
            x, y = match.group(1).upper(), match.group(2).upper()
            t1, t2, t3 = match.group(3).upper(), match.group(4).upper(), match.group(5).upper()
            if x == t1:
                p, q = t2, t3
            elif x == t2:
                p, q = t1, t3
            elif x == t3:
                p, q = t1, t2
            else:
                continue
            if y not in (p, q) and y != x:
                self.atoms.append(Atom("perp", (x, y, p, q)))
                self.atoms.append(Atom("coll", (p, y, q)))
        # 垂直二等分線: "PQ is the perpendicular bisector of AB"
        for match in re.finditer(
            r"(?<![A-Za-z])([A-Z])\s*([A-Z])(?![A-Za-z])\s+(?i:is)\s+"
            r"(?i:the)?\s*(?i:perpendicular)\s+(?i:bisector)\s+(?i:of)\s+"
            r"(?<![A-Za-z])([A-Z])\s*([A-Z])(?![A-Za-z])",
            text,
        ):
            x, y, p, q = (match.group(1).upper(), match.group(2).upper(),
                          match.group(3).upper(), match.group(4).upper())
            if len({x, y, p, q}) == 4:
                self.atoms.append(Atom("perp", (x, y, p, q)))
        # 垂線の足: "D is the foot of the perpendicular from A to BC"
        for match in re.finditer(
            r"(?<![A-Za-z])([A-Z])(?![A-Za-z])\s+(?i:is)\s+(?i:the)?\s*(?i:foot)\s+"
            r"(?i:of)\s+(?i:the)?\s*(?i:perpendicular)\s+(?i:from)\s+([A-Z])\s+"
            r"(?i:to|on)\s+(?i:side)?\s*(?<![A-Za-z])([A-Z])\s*([A-Z])(?![A-Za-z])",
            text,
        ):
            foot = match.group(1).upper()
            from_p = match.group(2).upper()
            p, q = match.group(3).upper(), match.group(4).upper()
            if len({foot, from_p, p, q}) == 4:
                self.atoms.append(Atom("perp", (from_p, foot, p, q)))
                self.atoms.append(Atom("coll", (p, foot, q)))
        for match in re.finditer(r"([A-Z])\s*([A-Z])\s*PERP\s*([A-Z])\s*([A-Z])", text):
            self.atoms.append(Atom("perp", match.groups()))
        for match in re.finditer(
            r"([A-Z])\s*([A-Z])\s+(?i:is)?\s*(?i:parallel\s+to)\s+([A-Z])\s*([A-Z])", text,
        ):
            self.atoms.append(Atom("para", match.groups()))
        for match in re.finditer(r"([A-Z])\s*([A-Z])\s*PARA\s*([A-Z])\s*([A-Z])", text):
            self.atoms.append(Atom("para", match.groups()))

    # -- 中点・共線 ------------------------------------------------------
    def _parse_midpoints(self) -> None:
        text = self.text
        for match in re.finditer(
            r"([A-Z])\s+(?i:is)\s+(?i:the)?\s*(?i:midpoint)\s+(?i:of)\s+"
            r"(?<![A-Za-z])([A-Z])\s*([A-Z])(?![A-Za-z])",
            text,
        ):
            m, a, b = match.group(1).upper(), match.group(2).upper(), match.group(3).upper()
            if m not in (a, b) and len(a) == 1 and len(b) == 1:
                self.atoms.append(Atom("mid", (m, a, b)))
                self.atoms.append(Atom("tri", (a, m, b)))
        # "AM is a median of triangle ABC" — 頂点 A から対辺 BC の中点 M
        for match in re.finditer(
            r"(?<![A-Za-z])([A-Z])\s*([A-Z])(?![A-Za-z])\s+(?i:is)\s+"
            r"(?i:a|the)?\s*(?i:median)\s+(?i:of)\s+(?i:triangle)?\s*"
            r"(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])(?![A-Za-z])",
            text,
        ):
            apex, m = match.group(1).upper(), match.group(2).upper()
            t1, t2, t3 = match.group(3).upper(), match.group(4).upper(), match.group(5).upper()
            if apex == t1:
                p, q = t2, t3
            elif apex == t2:
                p, q = t1, t3
            elif apex == t3:
                p, q = t1, t2
            else:
                continue
            if m not in (p, q) and m != apex:
                self.atoms.append(Atom("mid", (m, p, q)))
                self.atoms.append(Atom("coll", (p, m, q)))

    def _parse_collinear(self) -> None:
        text = self.text
        for match in re.finditer(
            r"([A-Z])\s+(?i:lies?)\s+(?i:on)\s+(?i:the)?\s*(?i:segment)\s*"
            r"(?<![A-Za-z])([A-Z])\s*([A-Z])(?![A-Za-z])",
            text,
        ):
            x, p, q = match.group(1).upper(), match.group(2).upper(), match.group(3).upper()
            if x not in (p, q) and len(p) == 1 and len(q) == 1:
                self.atoms.append(Atom("coll", (p, x, q)))
        for match in re.finditer(
            r"points?\s+([A-Z])(?:\s+(?i:and)\s+([A-Z]))?\s+(?i:are|is)\s+"
            r"(?i:placed|marked|taken|chosen|located|lying)\s+(?i:on)\s+(?i:the)?\s*(?i:side|segment)"
            r"\s*(?<![A-Za-z])([A-Z])\s*([A-Z])(?![A-Za-z])",
            text,
        ):
            groups = [g.upper() for g in match.groups() if g and g.isalpha() and len(g) == 1]
            if len(groups) >= 3:
                endpoints = groups[-2:]
                for point in groups[:-2]:
                    self.atoms.append(Atom("coll", (endpoints[0], point, endpoints[1])))
        # "D is on AC" / "E lies on BC" 形式
        for match in re.finditer(
            r"([A-Z])\s+(?i:is|lies?)\s+(?i:on)\s+([A-Z])\s*([A-Z])(?![A-Za-z])", text,
        ):
            x, p, q = match.group(1).upper(), match.group(2).upper(), match.group(3).upper()
            if len(p) == 1 and len(q) == 1 and x not in (p, q):
                self.atoms.append(Atom("coll", (p, x, q)))
        # "QSR is a straight line" 形式（本文中の点の並び順を保つ）
        for match in re.finditer(
            r"(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])(?![A-Za-z])\s+(?i:is|are)\s+"
            r"(?i:a)?\s*(?i:straight)\s+(?i:line)",
            text,
        ):
            a, b, c = (match.group(1).upper(), match.group(2).upper(), match.group(3).upper())
            if len({a, b, c}) == 3:
                self.atoms.append(Atom("coll", (a, b, c)))

    # -- 円 --------------------------------------------------------------
    def _parse_circle(self) -> None:
        text = self.text
        center = None
        for match in re.finditer(
            r"(?i:circle)\s*(?:(?i:with)\s+(?i:center|centre)\s*([A-Z])|\(([A-Z])\))?", text,
        ):
            center = (match.group(1) or match.group(2) or "").upper() or None
            break
        if center:
            self._center = center
        for match in re.finditer(
            r"(?i:passing\s+through)\s+([A-Z])(?:\s*,\s*([A-Z]))?(?:\s*,\s*([A-Z]))?",
            text,
        ):
            if not center:
                continue
            for point in match.groups():
                if point and point.upper() != center:
                    self.atoms.append(Atom("oncircle", (point.upper(), center)))
        for match in re.finditer(
            r"([A-Z])\s+(?i:is|lies?)\s+(?i:on)\s+(?i:the)?\s*(?i:circle)", text,
        ):
            if center:
                point = match.group(1).upper()
                if point != center:
                    self.atoms.append(Atom("oncircle", (point, center)))
        # 直径: "diameter AB" / "AB is a diameter" → 中心が分かれば coll(A,O,B)。
        # 両端も円周上の点なので oncircle も付ける（タレスの定理の前提）。
        for match in re.finditer(
            r"(?:(?i:diameter)\s*(?<![A-Za-z])([A-Z])\s*([A-Z])(?![A-Za-z])"
            r"|(?<![A-Za-z])([A-Z])\s*([A-Z])(?![A-Za-z])\s+(?i:is|are)\s+(?i:a)?\s*(?i:diameter))",
            text,
        ):
            letters = [g.upper() for g in match.groups() if g and g.isalpha() and len(g) == 1]
            if len(letters) == 2 and center:
                p, q = letters
                self.atoms.append(Atom("coll", (p, center, q)))
                self.atoms.append(Atom("oncircle", (p, center)))
                self.atoms.append(Atom("oncircle", (q, center)))
        for match in re.finditer(
            r"(?:(?i:cyclic\s+quadrilateral)\s*(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])\s*([A-Z])(?![A-Za-z])"
            r"|(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])\s*([A-Z])(?![A-Za-z])"
            r"\s+(?i:is|are)\s+(?i:a)?\s*(?i:cyclic\s+quadrilateral))",
            text,
        ):
            groups = [g.upper() for g in match.groups() if g and g.isalpha() and len(g) == 1]
            if len(groups) == 4:
                self.atoms.append(Atom("cyclic", tuple(groups)))
        for match in re.finditer(
            r"(?i:tangent)\s+(?:(?i:to\s+(?:the\s+)?circle\s+at)\s+([A-Z])"
            r"|(?i:that\s+touches\s+(?:the\s+)?circle\s+in\s+(?:the\s+)?point)\s+([A-Z]))",
            text,
        ):
            point = match.group(1) or match.group(2)
            if center:
                self.atoms.append(Atom("tangent_at", (point.upper(), center)))
                self.atoms.append(Atom("oncircle", (point.upper(), center)))

        # 内接円: "the incircle of triangle ABC touches sides BC, AC, and AB
        # at D, E, and F, respectively" — 中心は合成（無名なら I）。
        # 発行: coll(辺,接点)・oncircle・tangent_at・半径⊥辺の直角×2・
        # 内心の角二等分（内接円の中心は内心）。
        for match in re.finditer(
            r"(?i:incircle)\s+(?i:of)\s+(?i:triangle)?\s*"
            r"(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])(?![A-Za-z])\s+(?i:touches)\s+"
            r"(?i:sides?)?\s*(?<![A-Za-z])([A-Z])\s*([A-Z])(?![A-Za-z])"
            r"(?:\s*,?\s*(?i:and)?\s*(?<![A-Za-z])([A-Z])\s*([A-Z])(?![A-Za-z]))?"
            r"(?:\s*,?\s*(?i:and)?\s*(?<![A-Za-z])([A-Z])\s*([A-Z])(?![A-Za-z]))?"
            r"\s+(?i:at)\s+(?<![A-Za-z])([A-Z])(?![A-Za-z])"
            r"(?:\s*,?\s*(?i:and)?\s*(?<![A-Za-z])([A-Z])(?![A-Za-z]))?"
            r"(?:\s*,?\s*(?i:and)?\s*(?<![A-Za-z])([A-Z])(?![A-Za-z]))?"
            r"\s*(?i:respectively)?",
            text,
        ):
            ic = self._center or "I"
            g = match.groups()
            sides = []
            for i in range(3):
                x, y = g[3 + 2 * i: 5 + 2 * i]
                if x and y:
                    sides.append((x.upper(), y.upper()))
            points = [z.upper() for z in g[9:12] if z]
            if not sides or not points:
                continue
            pairs = list(zip(sides, points))
            if any(len({x, y, z}) != 3 for (x, y), z in pairs):
                continue
            for (x, y), z in pairs:
                if ic in (x, y, z):
                    continue
                self.atoms.extend((
                    Atom("coll", (x, z, y)),
                    Atom("oncircle", (z, ic)),
                    Atom("tangent_at", (z, ic)),
                    Atom("angval", (x, z, ic, "90")),
                    Atom("angval", (y, z, ic, "90")),
                ))
        # "I is the incenter of triangle ABC" → 内心の角二等分のみ
        for match in re.finditer(
            r"(?<![A-Za-z])([A-Z])(?![A-Za-z])\s+(?i:is)\s+(?i:the)?\s*"
            r"(?i:incenter|incentre)\s+(?i:of)\s+(?i:triangle)?\s*"
            r"(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])(?![A-Za-z])",
            text,
        ):
            ic = match.group(1).upper()
            t1, t2, t3 = match.group(2).upper(), match.group(3).upper(), match.group(4).upper()
            if ic in (t1, t2, t3):
                continue
            self.atoms.extend((
                Atom("eqangle", (t2, t1, ic, ic, t1, t3)),
                Atom("eqangle", (t3, t2, ic, ic, t2, t1)),
                Atom("eqangle", (t1, t3, ic, ic, t3, t2)),
            ))

    # -- 目標角 ----------------------------------------------------------
    def _parse_goal(self) -> None:
        text = self.text
        patterns = [
            re.compile(
                r"(?i:what is|how big is|find|determine|calculate)(?i: the)?"
                r"(?i: (?:measure|size|value) of)?"
                r"\s*(?i:the)?\s*(?:ANG(?![A-Za-z])\s*)+"
                r"(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])(?![A-Za-z])",
            ),
            re.compile(
                r"(?i:the )?(?i:measure|size|value) of"
                r"\s*(?i:the)?\s*(?:ANG(?![A-Za-z])\s*)+"
                r"(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])(?![A-Za-z])"
                r"(?=\s*[?。]|\s*$)",
            ),
            re.compile(
                r"(?:ANG(?![A-Za-z])\s*)+(?<![A-Za-z])([A-Z])\s*([A-Z])\s*([A-Z])(?![A-Za-z])"
                r"\s+(?i:is\s+equal\s+to)",
            ),
        ]
        for pattern in patterns:
            for match in pattern.finditer(text):
                g1, g2, g3 = match.group(1), match.group(2), match.group(3)
                if g1.isalpha() and g2.isalpha() and g3.isalpha():
                    self.goal = (g1, g2, g3)
                    return


# ---------------------------------------------------------------------------
# エントリポイント
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StandardModelResult:
    answer: str
    provenance: str
    semantic_ir: dict
    certificate: dict


def solve_standard_model(question: str, options: Iterable[str] = ()) -> Optional[StandardModelResult]:
    """固定点閉包 + 全角法で角度の値を一意に定めた時だけ答える。"""
    option_list = list(options)
    try:
        parser = ProblemParser(question)
    except Exception:  # noqa: BLE001
        return None
    if not parser.atoms:
        return None
    goal = parser.goal
    if goal is None:
        return None
    closed, derived = fixpoint_closure(parser.atoms)
    system = AngleSystem(closed)
    value = system.goal_value(*goal)
    if value is None:
        return None
    values = _option_values(option_list)
    if option_list:
        numeric = [item for item in values if item[1].is_number]
        if len(numeric) != len(values):
            return None
        matches = [
            label for label, expr in numeric
            if sp.simplify(sp.expand(expr - value)) == 0
        ]
        if len(matches) != 1:
            return None
        answer = matches[0]
    else:
        answer = _format_exact(value)
    certificate = {
        "goal": "".join(goal),
        "goal_value": str(value),
        "atoms": sorted(_render(atom) for atom in closed),
        "derived": derived,
        "equations": [str(eq) for eq in system.equations],
        "goal_symbol": parser.goal_symbol,
    }
    return StandardModelResult(
        answer,
        "text:StandardModelFixpointClosureFullAngleGroup",
        {
            "goal": "".join(goal),
            "method": "typed-deduction-standard-model-full-angle-group",
            "closure_rounds": len(derived),
            "atoms": len(closed),
        },
        certificate,
    )


def extract_formal_propositions(question: str) -> Optional[dict]:
    """形式的命題の抽出: 問題文 → (与件, ゴール, 閉包, 導出記録)。

    型付き演繹標準模型の第一段（パーサー）の出力そのもの。証明 DAG の葉が
    与件・ゴールの形式的表現になり、閉包がその前向き演繹の結果になる。
    """
    try:
        parser = ProblemParser(question)
    except Exception:  # noqa: BLE001
        return None
    if not parser.atoms:
        return None
    closed, derived = fixpoint_closure(parser.atoms)
    goal = parser.goal
    return {
        "givens": sorted(_render(atom) for atom in parser.atoms),
        "goal": "".join(goal) if goal else None,
        "goal_symbol": parser.goal_symbol,
        "closure": sorted(_render(atom) for atom in closed),
        "derived": derived,
    }


from itertools import product as _product


def _format_exact(value: sp.Expr) -> str:
    value = sp.nsimplify(sp.simplify(value))
    if value.is_Integer:
        return str(int(value))
    if value.is_Rational:
        return f"{value.p}/{value.q}"
    return sp.sstr(value)
