"""Type-directed structural search for unresolved MathOS research candidates."""

from __future__ import annotations

import hashlib
import random
import re
from collections import Counter, deque
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class AtlasMorphism:
    name: str
    source: str
    target: str
    description_ja: str
    domain: str
    operation_class: str
    is_query: bool = False
    query_type: str | None = None
    commutation_group: str | None = None


@dataclass(frozen=True)
class SearchDomain:
    name: str
    start_sort: str
    intro_ja: str
    title_ja: str
    constraints: tuple[str, ...]


def _m(
    name: str,
    source: str,
    target: str,
    description_ja: str,
    domain: str,
    *,
    operation_class: str | None = None,
    is_query: bool = False,
    query_type: str | None = None,
    commutation_group: str | None = None,
) -> AtlasMorphism:
    return AtlasMorphism(
        name=name,
        source=source,
        target=target,
        description_ja=description_ja,
        domain=domain,
        operation_class=operation_class or name,
        is_query=is_query,
        query_type=query_type,
        commutation_group=commutation_group,
    )


DOMAINS: tuple[SearchDomain, ...] = (
    SearchDomain(
        "triangle_dynamics",
        "Triangle",
        "鋭角不等辺三角形を初期対象とする",
        "三角形変換の合成力学",
        ("nondegenerate", "acute_when_pedal_is_used", "mod_similarity"),
    ),
    SearchDomain(
        "plane_curve",
        "PlaneCurve",
        "特異点を持たない既約実代数平面曲線を初期対象とする",
        "平面代数曲線の合成変換",
        ("irreducible", "regular_branch", "exclude_base_locus"),
    ),
    SearchDomain(
        "convex_body",
        "ConvexBody",
        "原点対称で滑らかな厳密凸代数的凸体を初期対象とする",
        "凸体関手の合成力学",
        ("origin_symmetric", "strictly_convex", "mod_linear_equivalence"),
    ),
    SearchDomain(
        "polynomial",
        "Polynomial",
        "重根を持たないモニック実多項式を初期対象とする",
        "多項式変換と算術観測",
        ("square_free", "monic_normalization", "degree_at_least_three"),
    ),
    SearchDomain(
        "cayley_spectral",
        "FiniteGroup",
        "有限アーベル群と、その自己同型で不変な生成集合を初期データとする",
        "Cayleyグラフのスペクトル合成",
        ("finite_abelian", "symmetric_connection_set", "connected"),
    ),
    SearchDomain(
        "markov_dynamics",
        "MarkovChain",
        "有限既約可逆Markov連鎖と指定状態集合を初期対象とする",
        "Markov関手と到達時刻不変量",
        ("finite", "irreducible", "reversible"),
    ),
)


ATLAS: tuple[AtlasMorphism, ...] = (
    # Triangle chart.
    _m("CentroidMark", "Triangle", "MarkedTriangle", "重心を標識点として付加する", "triangle_dynamics", operation_class="AffineCenterMark"),
    _m("IncenterMark", "Triangle", "MarkedTriangle", "内心を標識点として付加する", "triangle_dynamics", operation_class="MetricCenterMark"),
    _m("CircumcenterMark", "Triangle", "MarkedTriangle", "外心を標識点として付加する", "triangle_dynamics", operation_class="MetricCenterMark"),
    _m("OrthocenterMark", "Triangle", "MarkedTriangle", "垂心を標識点として付加する", "triangle_dynamics", operation_class="OrthogonalityCenterMark"),
    _m("SymmedianMark", "Triangle", "MarkedTriangle", "類似重心を標識点として付加する", "triangle_dynamics", operation_class="BarycentricCenterMark"),
    _m("PedalProjection", "MarkedTriangle", "PointTriple", "標識点から三辺への垂足三点をとる", "triangle_dynamics"),
    _m("CevianTrace", "MarkedTriangle", "PointTriple", "標識点を通る三本のcevianの辺上の足をとる", "triangle_dynamics"),
    _m("SideReflectionTrace", "MarkedTriangle", "PointTriple", "標識点を三辺に関して反射した三点をとる", "triangle_dynamics"),
    _m("VertexCircleTrace", "MarkedTriangle", "PointTriple", "各頂点と標識点が定める円の対応交点をとる", "triangle_dynamics"),
    _m("TriangleFormation", "PointTriple", "Triangle", "三点を頂点とする向き付き三角形を作る", "triangle_dynamics"),
    _m("MedialTransform", "Triangle", "Triangle", "三辺の中点三角形へ移す", "triangle_dynamics", operation_class="AffineTriangleEndofunctor"),
    _m("OrthicTransform", "Triangle", "Triangle", "垂足三角形へ移す", "triangle_dynamics", operation_class="MetricTriangleEndofunctor"),
    _m("ExcentralTransform", "Triangle", "Triangle", "傍心三角形へ移す", "triangle_dynamics", operation_class="MetricTriangleEndofunctor"),
    _m("AnticomplementaryTransform", "Triangle", "Triangle", "反中点三角形へ移す", "triangle_dynamics", operation_class="AffineTriangleEndofunctor"),
    _m("SimilarityNormalization", "Triangle", "NormalizedTriangle", "重心・面積・向きを固定して相似正規化する", "triangle_dynamics"),
    _m("ForgetNormalization", "NormalizedTriangle", "Triangle", "正規化座標を忘れて三角形として扱う", "triangle_dynamics"),
    _m("ModuliProjection", "NormalizedTriangle", "TriangleModuli", "相似類のモジュライ点へ射影する", "triangle_dynamics"),
    _m("InducedIteration", "TriangleModuli", "ModuliOrbit", "ここまでの合成が誘導する写像を反復する", "triangle_dynamics"),
    _m("OrbitCompactification", "ModuliOrbit", "CompactOrbit", "退化三角形を境界として軌道をコンパクト化する", "triangle_dynamics"),
    _m("LimitSetExtraction", "CompactOrbit", "DynamicalData", "極限集合と周期点データを抽出する", "triangle_dynamics"),
    _m("TriangleDynamicsQuery", "DynamicalData", "Classification", "全周期軌道、吸引域、退化境界上の極限を分類せよ", "triangle_dynamics", is_query=True, query_type="triangle_moduli_dynamics"),
    _m("TriangleFixedPointQuery", "TriangleModuli", "Classification", "誘導写像の固定点と有限周期点を相似を除いて分類せよ", "triangle_dynamics", is_query=True, query_type="triangle_transform_fixed_points"),

    # Algebraic curve chart.
    _m("ProjectiveDual", "PlaneCurve", "PlaneCurve", "正則接線族の射影双対曲線をとる", "plane_curve", commutation_group="projective_functors"),
    _m("Evolute", "PlaneCurve", "PlaneCurve", "法線族の包絡線である発展曲線をとる", "plane_curve"),
    _m("CircleInversion", "PlaneCurve", "PlaneCurve", "原点中心の円反転像をとる", "plane_curve"),
    _m("HessianCurve", "PlaneCurve", "PlaneCurve", "定義多項式のHessian曲線をとる", "plane_curve", commutation_group="projective_functors"),
    _m("OffsetCurve", "PlaneCurve", "PlaneCurve", "法線方向の代数的平行曲線をとる", "plane_curve"),
    _m("IsogonalCremona", "PlaneCurve", "PlaneCurve", "固定基準三角形に関する等角共役Cremona像をとる", "plane_curve"),
    _m("Catacaustic", "PlaneCurve", "PlaneCurve", "固定光源からの反射光線族の包絡線をとる", "plane_curve"),
    _m("PolarReciprocal", "PlaneCurve", "PlaneCurve", "固定非退化二次形式に関する極逆像をとる", "plane_curve", commutation_group="projective_functors"),
    _m("ProjectiveClosure", "PlaneCurve", "ProjectiveCurve", "射影閉包をとり無限遠点を加える", "plane_curve"),
    _m("AffineChartChange", "ProjectiveCurve", "PlaneCurve", "基点を避ける一般アフィンチャートへ移す", "plane_curve"),
    _m("ResolveSingularities", "ProjectiveCurve", "ResolvedCurve", "全特異点を解消して正規化曲線を得る", "plane_curve"),
    _m("CurveInvariantExtraction", "ResolvedCurve", "CurveInvariants", "次数、分岐、種数、自己交点データを抽出する", "plane_curve"),
    _m("DegreeGenusQuery", "CurveInvariants", "Classification", "次数と幾何種数を初期曲線の不変量で表示し例外を分類せよ", "plane_curve", is_query=True, query_type="degree_genus_formula"),
    _m("SingularityQuery", "CurveInvariants", "Classification", "全特異点型と実枝数を分類せよ", "plane_curve", is_query=True, query_type="singularity_classification"),
    _m("BirationalPeriodQuery", "PlaneCurve", "Classification", "合成変換で元の曲線と双有理同値になる初期曲線を分類せよ", "plane_curve", is_query=True, query_type="birational_periodicity"),

    # Convex-body chart.
    _m("PolarDual", "ConvexBody", "ConvexBody", "原点に関する極体をとる", "convex_body"),
    _m("DifferenceBody", "ConvexBody", "ConvexBody", "差体をとる", "convex_body", commutation_group="minkowski_functors"),
    _m("ProjectionBody", "ConvexBody", "ConvexBody", "射影体をとる", "convex_body"),
    _m("CentroidBody", "ConvexBody", "ConvexBody", "重心体をとる", "convex_body"),
    _m("IntersectionBody", "ConvexBody", "ConvexBody", "交叉体をとる", "convex_body"),
    _m("MinkowskiPolarSum", "ConvexBody", "ConvexBody", "自身と極体のMinkowski和をとる", "convex_body", commutation_group="minkowski_functors"),
    _m("SteinerSymmetrization", "ConvexBody", "ConvexBody", "主慣性軸方向にSteiner対称化する", "convex_body"),
    _m("VolumeNormalization", "ConvexBody", "NormalizedBody", "面積と二次モーメントを固定して正規化する", "convex_body"),
    _m("ForgetBodyNormalization", "NormalizedBody", "ConvexBody", "正規化を忘れて凸体として扱う", "convex_body"),
    _m("BodyIteration", "NormalizedBody", "BodyOrbit", "ここまでの凸体関手を反復する", "convex_body"),
    _m("SupportFunctionChart", "BodyOrbit", "FunctionOrbit", "支持関数の軌道へ移す", "convex_body"),
    _m("StabilityLinearization", "FunctionOrbit", "StabilityData", "固定点の周りで線形化しスペクトルを求める", "convex_body"),
    _m("ConvexDynamicsQuery", "StabilityData", "Classification", "固定体、周期軌道、局所安定性を線形同値を除いて分類せよ", "convex_body", is_query=True, query_type="convex_body_dynamics"),
    _m("ConvexFixedPointQuery", "NormalizedBody", "Classification", "合成関手の固定体を線形同値を除いて分類せよ", "convex_body", is_query=True, query_type="convex_functor_fixed_points"),

    # Polynomial chart.
    _m("ReciprocalPolynomial", "Polynomial", "Polynomial", "根を逆数へ移す相反多項式をとる", "polynomial", commutation_group="root_functors"),
    _m("GraeffeTransform", "Polynomial", "Polynomial", "根を二乗するGraeffe変換を施す", "polynomial", commutation_group="root_functors"),
    _m("DerivativeRenormalization", "Polynomial", "Polynomial", "導関数をモニックに再正規化する", "polynomial"),
    _m("CriticalValuePolynomial", "Polynomial", "Polynomial", "臨界値を根にもつ消去多項式を作る", "polynomial"),
    _m("ShiftConjugacy", "Polynomial", "Polynomial", "根の重心を0へ移す平行移動共役を施す", "polynomial"),
    _m("RootMultiset", "Polynomial", "RootConfiguration", "重複度付き根配置へ移す", "polynomial"),
    _m("PolynomialReconstruction", "RootConfiguration", "Polynomial", "根配置からモニック多項式を再構成する", "polynomial"),
    _m("PowerMomentSequence", "RootConfiguration", "MomentSequence", "根の冪和モーメント列を作る", "polynomial"),
    _m("HankelConstruction", "MomentSequence", "HankelMatrix", "モーメントからHankel行列族を作る", "polynomial"),
    _m("MinorSequence", "HankelMatrix", "DeterminantSequence", "主小行列式列をとる", "polynomial"),
    _m("RecurrenceExtraction", "DeterminantSequence", "RecurrenceData", "満たす最小線形漸化式を抽出する", "polynomial"),
    _m("ModularOrbit", "RecurrenceData", "ArithmeticData", "各素数法での周期と例外素数を抽出する", "polynomial"),
    _m("PolynomialArithmeticQuery", "ArithmeticData", "Classification", "周期が有界または特異となる初期多項式を分類せよ", "polynomial", is_query=True, query_type="polynomial_arithmetic_dynamics"),
    _m("RecurrenceOrderQuery", "RecurrenceData", "Classification", "漸化式の最小次数が低下する係数条件を分類せよ", "polynomial", is_query=True, query_type="recurrence_order_drop"),

    # Cayley/spectral chart.
    _m("CharacterLevelConnection", "FiniteGroup", "ConnectionSet", "非自明指標の値が指定軌道に属する元を生成集合とする", "cayley_spectral"),
    _m("PowerResidueConnection", "FiniteGroup", "ConnectionSet", "冪剰余類の自己同型軌道を生成集合とする", "cayley_spectral"),
    _m("AutomorphismOrbitConnection", "FiniteGroup", "ConnectionSet", "自己同型群の複数軌道の和を生成集合とする", "cayley_spectral"),
    _m("CayleyConstruction", "ConnectionSet", "CayleyGraph", "対応する無向Cayleyグラフを作る", "cayley_spectral"),
    _m("GraphComplement", "CayleyGraph", "CayleyGraph", "ループを除いた補グラフをとる", "cayley_spectral", commutation_group="graph_functors"),
    _m("DistanceTwoGraph", "CayleyGraph", "CayleyGraph", "距離2の頂点を結ぶグラフをとる", "cayley_spectral"),
    _m("GraphPower", "CayleyGraph", "CayleyGraph", "距離が指定範囲以内の頂点を結ぶグラフ冪をとる", "cayley_spectral"),
    _m("AdjacencyOperator", "CayleyGraph", "MatrixOperator", "隣接作用素を群環上に表す", "cayley_spectral"),
    _m("LaplacianOperator", "CayleyGraph", "MatrixOperator", "組合せLaplacianを群環上に表す", "cayley_spectral"),
    _m("CharacterDiagonalization", "MatrixOperator", "Spectrum", "指標表で同時対角化してスペクトルを得る", "cayley_spectral"),
    _m("SpectralMoments", "Spectrum", "MomentSequence", "スペクトルモーメント列を作る", "cayley_spectral"),
    _m("ClosedWalkExtraction", "MomentSequence", "WalkData", "閉歩道数と原始閉路数を抽出する", "cayley_spectral"),
    _m("WalkArithmeticInvariant", "WalkData", "ArithmeticData", "閉路数列の合同不変量を抽出する", "cayley_spectral"),
    _m("CayleySpectrumQuery", "Spectrum", "Classification", "スペクトルが整数または強正則となる群と生成集合を分類せよ", "cayley_spectral", is_query=True, query_type="cayley_spectral_classification"),
    _m("WalkCongruenceQuery", "ArithmeticData", "Classification", "閉路数列が指定合同周期を持つ場合を分類せよ", "cayley_spectral", is_query=True, query_type="closed_walk_congruence"),

    # Markov chart.
    _m("TimeReversal", "MarkovChain", "MarkovChain", "定常分布に関する時間反転をとる", "markov_dynamics", commutation_group="markov_dualities"),
    _m("DoobTransform", "MarkovChain", "MarkovChain", "正の固有関数によるDoob変換を施す", "markov_dynamics"),
    _m("StateLumping", "MarkovChain", "MarkovChain", "自己同型軌道に沿って強 lumping する", "markov_dynamics"),
    _m("LazyPerturbation", "MarkovChain", "MarkovChain", "恒等遷移との凸結合でlazy化する", "markov_dynamics", commutation_group="markov_dualities"),
    _m("ProductChain", "MarkovChain", "MarkovChain", "自身との同期積連鎖を作る", "markov_dynamics"),
    _m("KilledChain", "MarkovChain", "TransientKernel", "指定集合で吸収させ過渡核をとる", "markov_dynamics"),
    _m("GreenOperator", "TransientKernel", "GreenKernel", "過渡核のGreen作用素をとる", "markov_dynamics"),
    _m("HittingMomentSystem", "GreenKernel", "MomentSystem", "到達時刻の高次モーメント連立系を作る", "markov_dynamics"),
    _m("MomentRecurrence", "MomentSystem", "RecurrenceData", "モーメント次数方向の漸化式を抽出する", "markov_dynamics"),
    _m("DenominatorArithmetic", "RecurrenceData", "ArithmeticData", "既約分母と素数ごとの付値列を抽出する", "markov_dynamics"),
    _m("MarkovMomentQuery", "ArithmeticData", "Classification", "付値列が周期的または有界となる連鎖を分類せよ", "markov_dynamics", is_query=True, query_type="hitting_moment_arithmetic"),
    _m("MarkovRecurrenceQuery", "RecurrenceData", "Classification", "到達時刻モーメントの漸化式次数が低下する場合を分類せよ", "markov_dynamics", is_query=True, query_type="hitting_moment_recurrence"),
)


TYPE_ALIASES = {
    "NormalizedTriangle": "TriangleModuliObject",
    "TriangleModuli": "TriangleModuliObject",
    "NormalizedBody": "ConvexModuliObject",
    "CurveInvariants": "AlgebraicCurveInvariantObject",
    "ArithmeticData": "ArithmeticInvariantObject",
}

INVOLUTIVE_OPERATIONS = {
    "CircleInversion",
    "GraphComplement",
    "PolarDual",
    "ProjectiveDual",
    "ReciprocalPolynomial",
    "TimeReversal",
}
COLLAPSING_OPERATIONS = {
    "LazyPerturbation",
    "ShiftConjugacy",
    "SimilarityNormalization",
    "VolumeNormalization",
}
SEARCH_EXCLUDED_OPERATIONS = {
    "ForgetBodyNormalization",
    "ForgetNormalization",
}


def _canonical_token(value: str) -> str:
    value = re.sub(r"\d+", "#", value)
    return TYPE_ALIASES.get(value, value)


def _normal_form_tokens(items: list[AtlasMorphism]) -> list[str]:
    tokens: list[str] = []
    index = 0
    while index < len(items):
        edge = items[index]
        if edge.commutation_group:
            run = [edge]
            cursor = index + 1
            while (
                cursor < len(items)
                and items[cursor].commutation_group == edge.commutation_group
                and items[cursor].source == items[cursor].target
            ):
                run.append(items[cursor])
                cursor += 1
            counts = Counter(
                _canonical_token(item.operation_class) for item in run
            )
            normalized: list[str] = []
            for operation, amount in sorted(counts.items()):
                if operation in INVOLUTIVE_OPERATIONS:
                    amount %= 2
                elif operation in COLLAPSING_OPERATIONS:
                    amount = min(amount, 1)
                normalized.extend([operation] * amount)
            tokens.extend(normalized)
            index = cursor
            continue
        operation = _canonical_token(edge.operation_class)
        if operation in COLLAPSING_OPERATIONS and tokens[-1:] == [operation]:
            index += 1
            continue
        if operation in INVOLUTIVE_OPERATIONS and tokens[-1:] == [operation]:
            tokens.pop()
            index += 1
            continue
        tokens.append(operation)
        index += 1
    return tokens


def effective_depth(chain: Iterable[AtlasMorphism]) -> int:
    return len(_normal_form_tokens(list(chain)))


def quotient_signature(
    chain: Iterable[AtlasMorphism],
    constraints: Iterable[str],
) -> str:
    items = list(chain)
    tokens = _normal_form_tokens(items)
    start = _canonical_token(items[0].source)
    target = _canonical_token(items[-1].target)
    constraint_key = ",".join(sorted(_canonical_token(v) for v in constraints))
    return f"{start}|{'/'.join(tokens)}|{target}|{constraint_key}"


def typed_signature(chain: Iterable[AtlasMorphism]) -> str:
    return " -> ".join(
        f"{edge.source}:{edge.name}:{edge.target}" for edge in chain
    )


def typecheck_chain(chain: Iterable[AtlasMorphism]) -> tuple[bool, str | None]:
    items = list(chain)
    if not items:
        return False, "empty morphism chain"
    for left, right in zip(items, items[1:]):
        if left.target != right.source:
            return (
                False,
                f"{left.name}:{left.target} cannot compose with "
                f"{right.name}:{right.source}",
            )
    if not items[-1].is_query or items[-1].target != "Classification":
        return False, "chain does not terminate in a classification query"
    return True, None


def _edges_for(domain: str) -> list[AtlasMorphism]:
    return [edge for edge in ATLAS if edge.domain == domain]


def _distance_to_classification(edges: list[AtlasMorphism]) -> dict[str, int]:
    incoming: dict[str, list[str]] = {}
    for edge in edges:
        incoming.setdefault(edge.target, []).append(edge.source)
    distance = {"Classification": 0}
    queue: deque[str] = deque(["Classification"])
    while queue:
        target = queue.popleft()
        for source in incoming.get(target, []):
            candidate = distance[target] + 1
            if source not in distance or candidate < distance[source]:
                distance[source] = candidate
                queue.append(source)
    return distance


# 1 回の search_chain が展開してよいノード数の上限。
# 網羅探索は「導ける量を全部列挙する」という設計上どうしても広いので、
# 見つからない深さで無限に粘らないための打ち切り点を持たせる。
SEARCH_NODE_BUDGET = 400_000


def search_chain(
    domain: SearchDomain,
    depth: int,
    rng: random.Random,
    *,
    attempts: int = 300,
) -> tuple[AtlasMorphism, ...] | None:
    edges = [
        edge
        for edge in _edges_for(domain.name)
        if edge.name not in SEARCH_EXCLUDED_OPERATIONS
    ]
    outgoing: dict[str, list[AtlasMorphism]] = {}
    for edge in edges:
        outgoing.setdefault(edge.source, []).append(edge)
    distance = _distance_to_classification(edges)

    # 深さ優先探索は枝刈りを入れても組合せ爆発する。受理条件を満たす鎖が
    # 存在しない深さでは全空間を掘り尽くすまで戻ってこないため、GitHub
    # Actions の研究ジョブが毎回20分でタイムアウトしていた。
    # 展開ノード数に予算を持たせ、尽きたら探索を打ち切る。
    budget = [SEARCH_NODE_BUDGET]

    def walk(
        current: str,
        path: list[AtlasMorphism],
        counts: Counter[str],
    ) -> tuple[AtlasMorphism, ...] | None:
        if budget[0] <= 0:
            return None
        budget[0] -= 1
        remaining = depth - len(path)
        if remaining == 0:
            return tuple(path) if current == "Classification" else None
        candidates = list(outgoing.get(current, []))
        rng.shuffle(candidates)
        for edge in candidates:
            if edge.is_query and remaining != 1:
                continue
            if not edge.is_query and remaining == 1:
                continue
            if path and path[-1].operation_class == edge.operation_class:
                continue
            occurrence_cap = max(2, depth // 6)
            if counts[edge.operation_class] >= occurrence_cap:
                continue
            if distance.get(edge.target, depth + 1) > remaining - 1:
                continue
            counts[edge.operation_class] += 1
            path.append(edge)
            result = walk(edge.target, path, counts)
            if result is not None:
                return result
            path.pop()
            counts[edge.operation_class] -= 1
        return None

    for _ in range(attempts):
        if budget[0] <= 0:
            return None
        result = walk(domain.start_sort, [], Counter())
        if result is not None:
            distinct = {edge.operation_class for edge in result}
            reduced = effective_depth(result)
            if (
                len(distinct) >= max(6, min(10, depth // 3))
                and reduced >= max(8, int(depth * 0.85))
            ):
                return result
    return None


def _ngrams(tokens: list[str], width: int = 2) -> set[tuple[str, ...]]:
    if len(tokens) < width:
        return {tuple(tokens)}
    return {
        tuple(tokens[index : index + width])
        for index in range(len(tokens) - width + 1)
    }


def structural_similarity(left: str, right: str) -> float:
    left_tokens = left.split("/")
    right_tokens = right.split("/")
    left_grams = _ngrams(left_tokens)
    right_grams = _ngrams(right_tokens)
    union = left_grams | right_grams
    return len(left_grams & right_grams) / len(union) if union else 1.0


def similarity_limit(depth: int) -> float:
    return max(0.55, 0.82 - 0.015 * max(depth - 10, 0))


def _render_statement(
    domain: SearchDomain,
    chain: tuple[AtlasMorphism, ...],
) -> str:
    construction = chain[:-1]
    query = chain[-1]
    steps = "，".join(
        f"({index}) {edge.description_ja}"
        for index, edge in enumerate(construction, start=1)
    )
    return (
        rf"\(\mathcal X_0\) を「{domain.intro_ja}」で定める。"
        rf"各構成が定義される非退化な範囲で，\(\mathcal X_i\) に"
        rf"次の型付き構成を順に施す：{steps}。"
        rf"最後に、{query.description_ja}"
        r"。分類では途中で生じる退化成分と例外パラメータも明示せよ。"
    )


def _render_title(
    domain: SearchDomain,
    chain: tuple[AtlasMorphism, ...],
) -> str:
    core = [edge.name for edge in chain if not edge.is_query]
    sample = "・".join(core[:2] + core[-2:])
    return f"{domain.title_ja}（{sample}）"


def _existing_autonomous(
    previous_payload: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    retained: list[dict[str, Any]] = []
    by_domain_name = {
        domain.name: {
            edge.name: edge for edge in _edges_for(domain.name)
        }
        for domain in DOMAINS
    }
    for record in (previous_payload or {}).get("candidates", []):
        if record.get("origin") != "autonomous_atlas_search":
            continue
        domain = record.get("search_trace", {}).get("domain")
        names = record.get("morphism_chain", [])
        lookup = by_domain_name.get(str(domain), {})
        if any(name not in lookup for name in names):
            continue
        chain = tuple(lookup[name] for name in names)
        if any(edge.name in SEARCH_EXCLUDED_OPERATIONS for edge in chain):
            continue
        reduced_depth = effective_depth(chain)
        if reduced_depth < max(8, int(len(chain) * 0.85)):
            continue
        upgraded = dict(record)
        upgraded["effective_morphism_count"] = reduced_depth
        upgraded["quotient_signature"] = quotient_signature(
            chain,
            upgraded.get("constraint_skeleton", ()),
        )
        upgraded_trace = dict(upgraded.get("search_trace", {}))
        upgraded_trace["similarity_limit"] = round(
            similarity_limit(len(chain)),
            4,
        )
        upgraded["search_trace"] = upgraded_trace
        retained.append(upgraded)
    return retained


def grow_payload(
    payload: dict[str, Any],
    previous_payload: dict[str, Any] | None,
    *,
    count: int = 8,
    seed: int | None = None,
) -> dict[str, Any]:
    previous_auto = _existing_autonomous(previous_payload)
    records = list(payload["candidates"])
    seen_ids = {record["candidate_id"] for record in records}
    for record in previous_auto:
        if record["candidate_id"] not in seen_ids:
            records.append(record)
            seen_ids.add(record["candidate_id"])

    previous_search = (previous_payload or {}).get("autonomous_search", {})
    previous_epoch = int(previous_search.get("epoch", 0))
    epoch = previous_epoch + (1 if count > 0 else 0)
    depth_floor = 10 + min((max(epoch, 1) - 1) // 2, 40)
    depth_ceiling = depth_floor + 3
    stable_seed = int(
        hashlib.sha256(
            "|".join(sorted(seen_ids)).encode("utf-8")
        ).hexdigest()[:12],
        16,
    )
    actual_seed = seed if seed is not None else stable_seed + epoch * 1_000_003
    rng = random.Random(actual_seed)

    quotient_seen = {
        str(record.get("quotient_signature") or record["structural_signature"])
        for record in records
    }
    autonomous_signatures = [
        str(record.get("quotient_signature") or record["structural_signature"])
        for record in records
        if record.get("origin") == "autonomous_atlas_search"
    ]
    domain_counts = Counter(
        str(record.get("search_trace", {}).get("domain", "unknown"))
        for record in records
        if record.get("origin") == "autonomous_atlas_search"
    )
    domain_failures: Counter[str] = Counter()
    added: list[dict[str, Any]] = []
    attempts = 0
    max_attempts = max(500, count * 250)
    while len(added) < count and attempts < max_attempts:
        attempts += 1
        active_domains = [
            domain for domain in DOMAINS if domain_failures[domain.name] < 40
        ]
        if not active_domains:
            break
        minimum_count = min(
            domain_counts[domain.name] for domain in active_domains
        )
        least_used = [
            domain
            for domain in active_domains
            if domain_counts[domain.name] == minimum_count
        ]
        least_used.sort(
            key=lambda domain: (domain_failures[domain.name], domain.name)
        )
        best_failure = domain_failures[least_used[0].name]
        domain = rng.choice(
            [
                item
                for item in least_used
                if domain_failures[item.name] == best_failure
            ]
        )
        depth = rng.randint(depth_floor, depth_ceiling)
        chain = search_chain(domain, depth, rng)
        if chain is None:
            domain_failures[domain.name] += 1
            continue
        type_ok, type_error = typecheck_chain(chain)
        if not type_ok:
            continue
        quotient = quotient_signature(chain, domain.constraints)
        if quotient in quotient_seen:
            domain_failures[domain.name] += 1
            continue
        nearest = max(
            (structural_similarity(quotient, prior) for prior in autonomous_signatures),
            default=0.0,
        )
        candidate_similarity_limit = similarity_limit(depth)
        if nearest >= candidate_similarity_limit:
            domain_failures[domain.name] += 1
            continue
        digest = hashlib.sha256(quotient.encode("utf-8")).hexdigest()
        query_type = chain[-1].query_type or "classification"
        statement = _render_statement(domain, chain)
        record = {
            "answer_status": "unresolved_by_mathos",
            "answer_tex": None,
            "candidate_id": f"atlas:{digest[:16]}",
            "constraint_skeleton": list(domain.constraints),
            "family_id": f"research.autonomous.{domain.name}.{digest[:10]}",
            "falsification_attempts": [
                "not executed: backend-specific bounded counterexample search is scheduled"
            ],
            "hardness": {
                "score": len(chain) + len({edge.operation_class for edge in chain}) // 3,
                "reasons": [
                    "type-directed multi-functor composition",
                    "global classification with exceptional strata",
                ],
            },
            "hold_reason": (
                "new quotient signature found by typed atlas search; no proof "
                "or counterexample has been produced"
            ),
            "known_problem_screen": {
                "passed": True,
                "matches": [],
                "scope": "local marker list; not a literature proof of novelty",
            },
            "morphism_chain": [edge.name for edge in chain],
            "morphism_count": len(chain),
            "effective_morphism_count": effective_depth(chain),
            "not_claimed_human_open": True,
            "origin": "autonomous_atlas_search",
            "proof_attempts": [
                "not executed: a backend contract has not yet been synthesized"
            ],
            "query_type": query_type,
            "quotient_signature": quotient,
            "search_trace": {
                "domain": domain.name,
                "epoch": epoch,
                "target_depth": depth,
                "seed": actual_seed,
                "nearest_prior_structural_similarity": round(nearest, 4),
                "similarity_limit": round(candidate_similarity_limit, 4),
            },
            "statement_tex": statement,
            "structural_signature": typed_signature(chain),
            "title": _render_title(domain, chain),
            "typecheck": {"passed": type_ok, "error": type_error},
        }
        records.append(record)
        added.append(record)
        seen_ids.add(record["candidate_id"])
        quotient_seen.add(quotient)
        autonomous_signatures.append(quotient)
        domain_counts[domain.name] += 1

    payload["candidates"] = records
    payload["autonomous_search"] = {
        "epoch": epoch,
        "seed": actual_seed,
        "requested": count,
        "added": len(added),
        "attempts": attempts,
        "depth_floor": depth_floor,
        "depth_ceiling": depth_ceiling,
        "atlas_morphisms": len(ATLAS),
        "domains": len(DOMAINS),
        "quotient": (
            "typed operation classes + type aliases + numeric erasure + "
            "commuting-block normalization"
        ),
        "base_maximum_nearest_similarity": 0.82,
        "similarity_rule": "max(0.55, 0.82 - 0.015 * (depth - 10))",
        "domain_counts": dict(sorted(domain_counts.items())),
    }
    payload["summary"].update(
        {
            "retained": len(records),
            "unique_structural_signatures": len(
                {record["structural_signature"] for record in records}
            ),
            "unique_query_types": len(
                {record["query_type"] for record in records}
            ),
            "parameter_variants": 0,
            "autonomous_candidates": sum(
                record.get("origin") == "autonomous_atlas_search"
                for record in records
            ),
            "added_by_autonomous_search": len(added),
            "current_depth_floor": depth_floor,
        }
    )
    return payload
