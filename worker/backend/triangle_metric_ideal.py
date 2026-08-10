"""三角形の計量イデアルの実行 backend。

worker/src の HyperMorphismSchema は backend 名（'sympy.groebner' 等）を
文字列で持つだけで、それを走らせる側が存在しない。ここでは経路
  MetricRelationIdeal -> EquationEncoding -> DesignatedRootEvaluation
の3射に対して実際に計算する実体を与える。

設計上の約束: 余弦定理そのものは書かない。
入れるのは
  (1) 座標実現（A=(0,0), B=(c,0), C=(x,y)）
  (2) 距離の定義
  (3) 余弦の定義（内積 / 長さの積）
だけ。余弦定理は x, y を終結式/Groebner で消去した結果として落ちてくる。

stdin に JSON {"steps":[...], "data":{...}} を受け取り stdout に JSON を返す。
"""
import json
import sys

import sympy as sp

A_, B_, C_ = sp.symbols("a b c", positive=True)
X, Y = sp.symbols("x y", real=True)
COS = {"A": sp.Symbol("cA", real=True), "B": sp.Symbol("cB", real=True), "C": sp.Symbol("cC", real=True)}


def metric_relation_ideal(data):
    """TriangleMetricData -> PolynomialSystem

    生成元は「座標に置いた三角形が満たす関係」だけ。
    a = BC, b = CA, c = AB（標準の対辺記法）。
    """
    vertex = data.get("vertex", "A")
    # 頂点 A を原点、B を x 軸上に置く。C は自由。
    #   |AB| = c, |AC| = b, |BC| = a
    gens = [
        sp.expand(X**2 + Y**2 - B_**2),          # |AC|^2 = b^2
        sp.expand((X - C_) ** 2 + Y**2 - A_**2),  # |BC|^2 = a^2
    ]
    # 余弦の定義: cos(角) = (辺ベクトルの内積) / (長さの積)
    if vertex == "A":
        # A における角: ベクトル AB=(c,0), AC=(x,y)
        gens.append(sp.expand(B_ * C_ * COS["A"] - (C_ * X)))
    elif vertex == "B":
        # B における角: ベクトル BA=(-c,0), BC=(x-c,y)
        gens.append(sp.expand(A_ * C_ * COS["B"] - (-C_ * (X - C_))))
    else:
        # C における角: ベクトル CA=(-x,-y), CB=(c-x,-y)
        gens.append(sp.expand(A_ * B_ * COS["C"] - ((-X) * (C_ - X) + Y**2)))
    return {
        "sort": "PolynomialSystem",
        "generators": [sp.srepr(g) for g in gens],
        "generators_str": [str(g) for g in gens],
        "eliminate": ["x", "y"],
        "keep": ["a", "b", "c", "c" + vertex],
        "vertex": vertex,
        "provenance": ["coordinate-realization", "distance-definition", "cosine-as-normalized-inner-product"],
    }


def equation_encoding(system):
    """PolynomialSystem -> AlgebraicSet

    x, y を消去して、辺長と余弦だけの関係式を取り出す。
    """
    gens = [sp.sympify(g) for g in system["generators"]]  # srepr なので仮定が保存される
    vertex = system["vertex"]
    unknown = COS[vertex]
    order = [X, Y, unknown, A_, B_, C_]
    gb = sp.groebner(gens, *order, order="lex")
    eliminated = [p for p in gb.exprs if not (p.has(X) or p.has(Y))]
    return {
        "sort": "AlgebraicSet",
        "groebner_basis": [str(p) for p in gb.exprs],
        "eliminated_generators": [sp.srepr(p) for p in eliminated],
        "eliminated_generators_str": [str(p) for p in eliminated],
        "unknown": str(unknown),
        "vertex": vertex,
    }


def designated_root_evaluation(algebraic_set, data):
    """AlgebraicSet -> Real

    辺長を代入し、指定した未知数について解く。実数かつ (-1,1) の根を選ぶ。
    """
    sides = data["sides"]
    subs = {A_: sp.Integer(sides["a"]), B_: sp.Integer(sides["b"]), C_: sp.Integer(sides["c"])}
    unknown = COS[algebraic_set["vertex"]]
    polys = [sp.sympify(p).subs(subs) for p in algebraic_set["eliminated_generators"]]
    polys = [sp.expand(p) for p in polys if sp.expand(p) != 0]
    if not polys:
        return {"sort": "Real", "value": None, "reason": "消去後に関係式が残らなかった"}
    solutions = set()
    for p in polys:
        for s in sp.solve(sp.Eq(p, 0), unknown, dict=False):
            s = sp.nsimplify(sp.simplify(s))
            if s.is_real and sp.Abs(s) < 1:
                solutions.add(s)
    values = sorted(solutions, key=lambda v: float(v))
    return {
        "sort": "Real",
        "substituted_relations": [str(p) for p in polys],
        "value": str(values[0]) if len(values) == 1 else None,
        "all_roots": [str(v) for v in values],
        "value_float": float(values[0]) if len(values) == 1 else None,
    }


HANDLERS = {
    "MetricRelationIdeal": lambda payload, data: metric_relation_ideal(data),
    "EquationEncoding": lambda payload, data: equation_encoding(payload),
    "DesignatedRootEvaluation": lambda payload, data: designated_root_evaluation(payload, data),
}


def main():
    request = json.loads(sys.stdin.read())
    data = request["data"]
    payload = None
    trace = []
    for step in request["steps"]:
        name = step["morphism"]
        handler = HANDLERS.get(name)
        if handler is None:
            trace.append({"morphism": name, "backend": step.get("backend"), "status": "no-handler"})
            print(json.dumps({"error": f"no backend handler for {name}", "trace": trace}, ensure_ascii=False))
            return
        payload = handler(payload, data)
        trace.append({
            "morphism": name,
            "backend": step.get("backend"),
            "status": "executed",
            "output_sort": payload["sort"],
            "output": payload,
        })
    print(json.dumps({"trace": trace, "result": payload}, ensure_ascii=False))


if __name__ == "__main__":
    main()
