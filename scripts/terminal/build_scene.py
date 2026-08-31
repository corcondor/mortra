# -*- coding: utf-8 -*-
"""証明図の実座標と証明文から、terminal 上演用の Scene を組む。

座標は extract_proof_figure.py が SVG から取った実測値。
段の順序と文言は proof.md の構成文と目標から取る。
このスクリプトは点も線も文も作らない。並べ替えるだけである。

線の段割りも決め打ちしない。線分の両端が名前つきの点と一致するなら、
その両端が定義され終わる最初の段に置く。どちらの端も名前と一致しない線分は
装飾として最後の段に回す。

    python scripts/terminal/build_scene.py 2009G6 \
        --figure build/terminal/2009G6.json \
        --proof artifacts/.../2009G6.proof.md \
        --output build/terminal/2009G6.scene.json
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

# "M x y \nL x y \n" だけを扱う。曲線が来たら落とす。
MOVETO = re.compile(r"M\s+([-\d.]+)\s+([-\d.]+)")
LINETO = re.compile(r"L\s+([-\d.]+)\s+([-\d.]+)")

TOL = 1e-6
# 目標が図の上で成立していると見なす上限。px と度の両方に使う。
TOL_GOAL = 1e-3


def load_figure(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def named_points(fig: dict) -> dict[str, tuple[float, float]]:
    """ラベルと散布点を結ぶ。matplotlib はラベルを点から一定量ずらして置く。"""
    pts: list[tuple[float, float]] = []
    for s in fig["scatter"]:
        for p in s["points"]:
            pts.append((float(p["x"]), float(p["y"])))
    out: dict[str, tuple[float, float]] = {}
    offsets: list[tuple[float, float]] = []
    for lab in fig["labels"]:
        text = (lab.get("text") or "").strip()
        # 図題のような非ASCIIは点ではない
        if not text or not text.isascii() or not re.fullmatch(r"[A-Za-z][A-Za-z0-9']*", text):
            continue
        lx, ly = float(lab["x"]), float(lab["y"])
        best = min(pts, key=lambda q: (q[0] - lx) ** 2 + (q[1] - ly) ** 2)
        out[text] = best
        offsets.append((lx - best[0], ly - best[1]))
    # ずれが一定でないなら、対応付けを信用しない
    if offsets:
        ox = {round(o[0], 3) for o in offsets}
        oy = {round(o[1], 3) for o in offsets}
        if len(ox) > 1 or len(oy) > 1:
            raise SystemExit(
                f"ラベルと点のずれが一定でない: dx={sorted(ox)} dy={sorted(oy)}。"
                "対応付けを確認してください。")
    return out


def segments(fig: dict) -> list[dict]:
    """patch_* は枠なので落とす。line2d_* の端点だけを取る。"""
    out = []
    for p in fig["paths"]:
        gid = p.get("group") or ""
        if not gid.startswith("line2d"):
            continue
        m = MOVETO.search(p["d"])
        ls = LINETO.findall(p["d"])
        if not m or not ls:
            continue
        a = (float(m.group(1)), float(m.group(2)))
        for lx, ly in ls:
            b = (float(lx), float(ly))
            out.append({"id": gid, "a": a, "b": b})
            a = b
    return out


def parse_construction(proof_md: str) -> tuple[list[dict], str]:
    """構成文を段に割る。各段が定義する点の名前を取る。"""
    m = re.search(r"```text\n(.*?)\n```", proof_md, re.S)
    if not m:
        raise SystemExit("構成文が proof.md に見つかりません")
    stmt = m.group(1).strip()
    body, _, goal = stmt.partition("?")
    steps = []
    for clause in body.split(";"):
        clause = clause.strip().rstrip(";").strip()
        if not clause:
            continue
        lhs, eq, rhs = clause.partition("=")
        if eq:
            names = lhs.split()
            defines = [n.strip().upper() for n in names if n.strip()]
        else:
            defines = []
        steps.append({"text": clause, "defines": defines})
    return steps, goal.strip()


def _ang(p, q, r, s) -> float:
    """直線 pq と rs のなす角。0..90 度。"""
    ux, uy = q[0] - p[0], q[1] - p[1]
    vx, vy = s[0] - r[0], s[1] - r[1]
    nu, nv = math.hypot(ux, uy), math.hypot(vx, vy)
    if nu == 0 or nv == 0:
        return float("nan")
    c = max(-1.0, min(1.0, abs(ux * vx + uy * vy) / (nu * nv)))
    return math.degrees(math.acos(c))


def _circle(a, b, c):
    """3点を通る円の中心と半径。退化なら None。"""
    d = 2 * (a[0] * (b[1] - c[1]) + b[0] * (c[1] - a[1]) + c[0] * (a[1] - b[1]))
    if abs(d) < 1e-12:
        return None
    a2, b2, c2 = a[0] ** 2 + a[1] ** 2, b[0] ** 2 + b[1] ** 2, c[0] ** 2 + c[1] ** 2
    ux = (a2 * (b[1] - c[1]) + b2 * (c[1] - a[1]) + c2 * (a[1] - b[1])) / d
    uy = (a2 * (c[0] - b[0]) + b2 * (a[0] - c[0]) + c2 * (b[0] - a[0])) / d
    return (ux, uy), math.hypot(a[0] - ux, a[1] - uy)


def measure_goal(goal: str, pts: dict) -> dict:
    """目標を図の実測座標で測る。主張ではなく測定値を持たせる。

    測れないものは何も足さない。空欄を埋めない。
    """
    tok = goal.replace("?", " ").split()
    if not tok:
        return {}
    kind, names = tok[0].lower(), [t.upper() for t in tok[1:]]
    if not names or not all(n in pts for n in names):
        return {}
    P = [pts[n] for n in names]
    out: dict = {"goal_kind": kind, "goal_points": names}

    if kind == "coll" and len(P) >= 3:
        # 最も離れた2点を基準線にして、残りの点のずれの最大値
        far = max(((i, j) for i in range(len(P)) for j in range(i + 1, len(P))),
                  key=lambda ij: math.dist(P[ij[0]], P[ij[1]]))
        a, b = P[far[0]], P[far[1]]
        base = math.dist(a, b)
        if base == 0:
            return out
        dev = max(abs((b[0] - a[0]) * (a[1] - p[1]) - (a[0] - p[0]) * (b[1] - a[1])) / base
                  for p in P)
        out.update(residual=dev, residual_unit="px",
                   draw=[(names[far[0]], names[far[1]])])

    elif kind == "cyclic" and len(P) >= 4:
        cr = _circle(P[0], P[1], P[2])
        if cr is None:
            return out
        (cx, cy), r = cr
        out.update(residual=max(abs(math.hypot(p[0] - cx, p[1] - cy) - r) for p in P[3:]),
                   residual_unit="px", circle=[cx, cy, r])

    elif kind == "perp" and len(P) >= 4:
        out.update(residual=abs(90.0 - _ang(P[0], P[1], P[2], P[3])),
                   residual_unit="deg", draw=[(names[0], names[1]), (names[2], names[3])])

    elif kind == "para" and len(P) >= 4:
        out.update(residual=_ang(P[0], P[1], P[2], P[3]),
                   residual_unit="deg", draw=[(names[0], names[1]), (names[2], names[3])])

    elif kind == "cong" and len(P) >= 4:
        d1, d2 = math.dist(P[0], P[1]), math.dist(P[2], P[3])
        out.update(residual=abs(d1 - d2), residual_unit="px",
                   draw=[(names[0], names[1]), (names[2], names[3])])

    elif kind == "eqangle" and len(P) >= 8:
        out.update(residual=abs(_ang(P[0], P[1], P[2], P[3]) - _ang(P[4], P[5], P[6], P[7])),
                   residual_unit="deg",
                   draw=[(names[0], names[1]), (names[2], names[3]),
                         (names[4], names[5]), (names[6], names[7])])

    if "draw" in out:
        out["segments_goal"] = [
            {"id": "goal", "from": u, "to": v, "a": list(pts[u]), "b": list(pts[v])}
            for u, v in out.pop("draw")]

    # 図が目標を満たしているかの判定。測れたときだけ付ける。
    # 実測では、通っている図の残差は 1e-6 以下に落ちる。ここを外れる図は
    # 目標と配置が食い違っているので、上演しても嘘になる。
    if "residual" in out:
        out["verified"] = out["residual"] < TOL_GOAL
    return out


def build(problem: str, fig: dict, proof_md: str) -> dict:
    pts = named_points(fig)
    segs = segments(fig)
    steps, goal = parse_construction(proof_md)

    # 点名 -> 定義される段の番号
    defined_at: dict[str, int] = {}
    for i, st in enumerate(steps):
        for n in st["defines"]:
            if n in pts and n not in defined_at:
                defined_at[n] = i

    def name_of(q):
        for n, p in pts.items():
            if abs(p[0] - q[0]) < 1e-3 and abs(p[1] - q[1]) < 1e-3:
                return n
        return None

    for st in steps:
        st["points"] = []
        st["segments"] = []

    decoration = []
    for s in segs:
        na, nb = name_of(s["a"]), name_of(s["b"])
        if na is None or nb is None or na not in defined_at or nb not in defined_at:
            decoration.append(s)
            continue
        k = max(defined_at[na], defined_at[nb])
        steps[k]["segments"].append(
            {"id": s["id"], "from": na, "to": nb,
             "a": list(s["a"]), "b": list(s["b"])})

    for n, i in defined_at.items():
        steps[i]["points"].append(n)
    for st in steps:
        st["points"].sort()

    goal_step = {"text": goal, "points": [], "segments": [], "is_goal": True}
    m = measure_goal(goal, pts)
    goal_step["segments"] = m.pop("segments_goal", [])
    goal_step.update(m)
    steps.append(goal_step)

    if decoration:
        steps[-1]["segments"].extend(
            {"id": s["id"], "from": None, "to": None,
             "a": list(s["a"]), "b": list(s["b"])} for s in decoration)

    return {
        "problem": problem,
        "source_figure": fig.get("source_svg"),
        "viewBox": fig.get("viewBox"),
        "points": {k: list(v) for k, v in pts.items()},
        "goal": goal,
        "steps": steps,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("problem")
    ap.add_argument("--figure", type=Path, required=True)
    ap.add_argument("--proof", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()

    fig = load_figure(a.figure)
    scene = build(a.problem, fig, a.proof.read_text(encoding="utf-8"))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(scene, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"  {a.problem}")
    print(f"  点   {len(scene['points'])}")
    print(f"  段   {len(scene['steps'])}")
    for i, st in enumerate(scene["steps"]):
        mark = "goal" if st.get("is_goal") else f"{i:>4}"
        print(f"  {mark}  pts={','.join(st['points']) or '-':<16} "
              f"seg={len(st['segments'])}  {st['text'][:56]}")
    g = scene["steps"][-1]
    if "residual" in g:
        mark = "OK " if g.get("verified") else "NG "
        print(f"  残差  {mark}{g['residual']:.6f} {g['residual_unit']}"
              f"  ({g['goal_kind']} / 図の実測座標での測定値)")
    else:
        print(f"  残差  測っていない（目標の点が図に無い: {g.get('goal_kind') or '?'}）")
    print(f"  -> {a.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
