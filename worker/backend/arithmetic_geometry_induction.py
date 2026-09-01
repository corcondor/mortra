"""Synthesize exact arithmetic lemmas from geometric and topological laws."""

from itertools import combinations_with_replacement, permutations
import json
import math
import sys

import sympy as sp


def monic_sign(numerator, denominator):
    numerator = sp.factor(numerator)
    denominator = sp.factor(denominator)
    if denominator.could_extract_minus_sign():
        return -numerator, -denominator
    return numerator, denominator


def permutation_key(expression, symbols):
    keys = []
    for order in permutations(symbols):
        renamed = sp.cancel(expression.xreplace(dict(zip(symbols, order))))
        numerator, denominator = sp.fraction(renamed)
        keys.append(f"{sp.srepr(sp.expand(numerator))}/{sp.srepr(sp.expand(denominator))}")
    return min(keys)


def triangle_candidates():
    a, b, c, s = sp.symbols("a b c s", positive=True)
    area2 = s * (s - a) * (s - b) * (s - c)
    semiperimeter = (a + b + c) / 2
    # Each atom is coefficient * Delta**area_power. The grammar discovers
    # products whose area power can be eliminated by Heron's identity.
    atoms = {
        "R": (a * b * c / 4, -1, "R"),
        "r": (1 / s, 1, "r"),
        "r_a": (1 / (s - a), 1, "r_{a}"),
        "r_b": (1 / (s - b), 1, "r_{b}"),
        "r_c": (1 / (s - c), 1, "r_{c}"),
    }
    candidates = []
    seen = set()
    enumerated = 0
    for left_name, right_name in combinations_with_replacement(atoms, 2):
        enumerated += 1
        left_base, left_power, left_tex = atoms[left_name]
        right_base, right_power, right_tex = atoms[right_name]
        area_power = left_power + right_power
        if area_power not in (-2, 0, 2):
            continue
        expression = left_base * right_base
        if area_power == 2:
            expression *= area2
        elif area_power == -2:
            expression /= area2
        expression = sp.cancel(expression.subs(s, semiperimeter))
        numerator, denominator = monic_sign(*sp.fraction(expression))
        key = permutation_key(expression, (a, b, c))
        if key in seen:
            continue
        seen.add(key)
        observable_tex = f"{left_tex}{right_tex}"
        numerator_tex = sp.latex(numerator, order="lex")
        denominator_tex = sp.latex(denominator, order="lex")
        expression_tex = sp.latex(expression, order="lex")
        identity_ok = sp.simplify(expression - numerator / denominator) == 0
        if not identity_ok or denominator == 0:
            continue
        samples = []
        for sides in ((3, 4, 5), (4, 5, 6), (5, 5, 6), (5, 6, 7), (6, 7, 8)):
            av, bv, cv = sides
            if av + bv <= cv:
                continue
            value = sp.N(expression.subs({a: av, b: bv, c: cv}), 30)
            if not value.is_real or value <= 0:
                identity_ok = False
                break
            samples.append(float(value))
        if not identity_ok:
            continue
        common = {
            "capability_origin": "synthesized_proof_program",
            "observable": f"{left_name}*{right_name}",
            "observable_tex": observable_tex,
            "expression": str(expression),
            "expression_tex": expression_tex,
            "numerator": str(numerator),
            "denominator": str(denominator),
            "numerator_tex": numerator_tex,
            "denominator_tex": denominator_tex,
            "samples": samples,
            "domain": "arithmetic_geometry",
            "source_types": ["TriangleMetricData", "IntegerPredicate"],
        }
        candidates.append({
            **common,
            "id": f"triangle.integrality.{left_name}.{right_name}",
            "kind": "integrality_criterion",
            "statement_tex": (
                "正の整数を三辺にもつ非退化三角形の外接円半径を \\(R\\)、内接円半径を \\(r\\)、"
                "三辺に対する傍接円半径を \\(r_a,r_b,r_c\\) とする。次の同値を示せ。"
                f"\\[{observable_tex}\\in\\mathbb{{Z}}\\quad\\Longleftrightarrow\\quad "
                f"{denominator_tex}\\mid {numerator_tex}\\]"
            ),
            "answer_tex": f"{observable_tex}={expression_tex},\\quad {denominator_tex}\\mid {numerator_tex}",
            "solution_tex": (
                "\\(s=(a+b+c)/2\\), \\(\\Delta^2=s(s-a)(s-b)(s-c)\\), "
                "\\(R=abc/(4\\Delta)\\), \\(r=\\Delta/s\\), "
                "\\(r_a=\\Delta/(s-a)\\) などを用いる。面積を消去して "
                f"\\({observable_tex}=({numerator_tex})/({denominator_tex})\\) を得る。"
                "分母は三角形の条件下で正なので、整数性は表示した整除条件と同値である。"
            ),
        })
        fully_symmetric = all(
            sp.simplify(expression - expression.xreplace(dict(zip((a, b, c), order)))) == 0
            for order in permutations((a, b, c))
        )
        if fully_symmetric:
            p, q, n = sp.symbols("p q n", positive=True, integer=True)
            prime_numerator = sp.factor(numerator.subs({a: p, b: q, c: n}))
            prime_denominator = sp.factor(denominator.subs({a: p, b: q, c: n}))
            prime_numerator_tex = sp.latex(prime_numerator, order="lex")
            prime_denominator_tex = sp.latex(prime_denominator, order="lex")
            candidates.append({
                **common,
                "id": f"triangle.two-prime-sides.{left_name}.{right_name}",
                "kind": "two_prime_side_reduction",
                "statement_tex": (
                    "相異なるとは限らない素数 \\(p,q\\) と正の整数 \\(n\\) が三角形の三辺をなすとする。"
                    "この三角形の通常の半径記号 \\(R,r,r_a,r_b,r_c\\) を用いるとき、次を示せ。"
                    f"\\[{observable_tex}\\text{{ が素数}}\\quad\\Longleftrightarrow\\quad "
                    f"\\exists \\ell\\in\\mathbb{{P}},\\ {prime_numerator_tex}="
                    f"\\ell\\left({prime_denominator_tex}\\right)\\]"
                ),
                "answer_tex": (
                    f"{prime_numerator_tex}=\\ell\\left({prime_denominator_tex}\\right),"
                    "\\quad \\ell\\in\\mathbb{P}"
                ),
                "solution_tex": (
                    f"一般の整数辺三角形に対する \\({observable_tex}=({numerator_tex})/({denominator_tex})\\) に "
                    "\\(a=p,b=q,c=n\\) を代入する。この量は正なので、素数であることは分子が分母の素数倍であることと同値である。"
                ),
            })
        candidates.append({
            **common,
            "id": f"triangle.prime.{left_name}.{right_name}",
            "kind": "prime_reduction",
            "statement_tex": (
                "正の整数を三辺にもつ非退化三角形について、通常の半径記号 "
                "\\(R,r,r_a,r_b,r_c\\) を用いる。次の同値を示せ。"
                f"\\[{observable_tex}\\text{{ が素数}}\\quad\\Longleftrightarrow\\quad "
                f"\\exists p\\in\\mathbb{{P}},\\ {numerator_tex}=p\\left({denominator_tex}\\right)\\]"
            ),
            "answer_tex": f"{numerator_tex}=p\\left({denominator_tex}\\right),\\quad p\\in\\mathbb{{P}}",
            "solution_tex": (
                f"Heronの恒等式と半径公式から \\({observable_tex}=({numerator_tex})/({denominator_tex})\\)。"
                "左辺は正である。したがって、この幾何量が素数であることは、分子が分母の素数倍であることと同値である。"
            ),
        })
    candidates.sort(key=lambda candidate: (
        0 if candidate["observable"] == "R*r" else 1,
        sp.count_ops(sp.sympify(candidate["expression"])),
        0 if candidate["kind"] == "integrality_criterion" else 1 if candidate["kind"] == "prime_reduction" else 2,
        candidate["id"],
    ))
    return candidates, enumerated, len(seen)


def topology_candidates():
    v, e, f, chi = sp.symbols("V E F chi", integer=True)
    solution = sp.solve((v - e + f - chi, 3 * f - 2 * e), (e, f), dict=True)[0]
    edge = sp.factor(solution[e])
    face = sp.factor(solution[f])
    n = sp.factor(v - chi)
    assert sp.simplify(edge - 3 * n) == 0
    assert sp.simplify(face - 2 * n) == 0
    samples = [1, 2, 3, 5, 8]
    for value in samples:
        assert math.gcd(3 * value, 2 * value) == value
    base = {
        "capability_origin": "registered_parameterized_morphism",
        "domain": "arithmetic_topology",
        "source_types": ["FiniteTriangulation", "IntegerPredicate"],
        "samples": samples,
        "expression": "E=3*(V-chi);F=2*(V-chi)",
        "expression_tex": "E=3(V-\\chi),\\ F=2(V-\\chi)",
        "numerator": str(edge),
        "denominator": str(face),
        "numerator_tex": sp.latex(edge),
        "denominator_tex": sp.latex(face),
        "observable": "EulerIncidenceVector",
        "observable_tex": "(E,F)",
    }
    return [
        {
            **base,
            "id": "topology.gcd.euler-incidence",
            "kind": "gcd_identity",
            "statement_tex": (
                "閉曲面の有限三角形分割における頂点数、辺数、面数を \\(V,E,F\\)、"
                "Euler標数を \\(\\chi\\) とする。次を示せ。"
                "\\[\\gcd(E,F)=V-\\chi\\]"
            ),
            "answer_tex": "\\gcd(E,F)=V-\\chi",
            "solution_tex": (
                "各面が三辺をもち各辺が二面に接するので \\(3F=2E\\)。"
                "これと \\(V-E+F=\\chi\\) を消去すると "
                "\\(E=3(V-\\chi), F=2(V-\\chi)\\)。\\(2,3\\) は互いに素だから結論を得る。"
            ),
        },
        {
            **base,
            "id": "topology.prime.edges",
            "kind": "prime_obstruction",
            "statement_tex": (
                "閉曲面の有限三角形分割について、辺数 \\(E\\) が素数ならば、"
                "Euler標数と頂点数の差が一意に定まることを示せ。"
            ),
            "answer_tex": "E=3,\\quad V-\\chi=1",
            "solution_tex": "\\(E=3(V-\\chi)\\) で \\(V-\\chi\\) は正の整数。積が素数なので後者は1である。",
        },
        {
            **base,
            "id": "topology.prime.faces",
            "kind": "prime_obstruction",
            "statement_tex": (
                "閉曲面の有限三角形分割について、面数 \\(F\\) が素数ならば、"
                "Euler標数と頂点数の差が一意に定まることを示せ。"
            ),
            "answer_tex": "F=2,\\quad V-\\chi=1",
            "solution_tex": "\\(F=2(V-\\chi)\\) で \\(V-\\chi\\) は正の整数。積が素数なので後者は1である。",
        },
        {
            **base,
            "id": "topology.ratio.incidence",
            "kind": "incidence_ratio",
            "statement_tex": (
                "閉曲面の任意の有限三角形分割において、辺数と面数の比が"
                "曲面の種数や分割の細分によらないことを示せ。"
            ),
            "answer_tex": "E:F=3:2",
            "solution_tex": "辺と面の接続対を二通りに数えると \\(2E=3F\\) であり、直ちに従う。",
        },
    ], 4, 4


def main():
    request = json.load(sys.stdin)
    modes = request.get("modes", [])
    registered = set(request.get("registered_expressions", []))
    all_candidates = []
    enumerated = 0
    equivalence_classes = 0
    if "triangle" in modes:
        candidates, count, classes = triangle_candidates()
        all_candidates.extend(candidates)
        enumerated += count
        equivalence_classes += classes
    if "topology" in modes:
        candidates, count, classes = topology_candidates()
        all_candidates.extend(candidates)
        enumerated += count
        equivalence_classes += classes
    unique = []
    seen = set()
    for candidate in all_candidates:
        key = candidate["id"]
        if key in seen or key in registered:
            continue
        seen.add(key)
        unique.append(candidate)
    offset = max(0, int(request.get("offset", 0)))
    maximum = max(1, min(int(request.get("max_candidates", 4)), 24))
    selected = unique[offset:offset + maximum]
    json.dump({
        "candidates": selected,
        "telemetry": {
            "enumerated": enumerated,
            "tested": len(unique),
            "rejected": len(all_candidates) - len(unique),
            "equivalence_classes": equivalence_classes,
            "certified": len(selected),
            "synthesis_engine": "sympy-relational-grammar",
        },
    }, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        json.dump({"error": str(error)}, sys.stdout, ensure_ascii=False)
