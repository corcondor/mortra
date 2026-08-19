"""構造的に新しいが、MathOSがまだ解けない研究候補を保存する。

ここでの ``unresolved_by_mathos`` は人類にとっての未解決問題を意味しない。
型検査と既知問題スクリーニングを通した後、現在のbackendでは証明も反例も
得られなかった、という機械の状態だけを表す。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from math_os_prototype.jukenmath_full_audit import canonical_surface
except ImportError:  # pragma: no cover
    from jukenmath_full_audit import canonical_surface


HERE = Path(__file__).resolve().parent
DEFAULT_OUTPUT = HERE / "problem_synthesis" / "unresolved_candidates.json"
DEFAULT_REPORT = HERE / "docs" / "generated" / "latest-research-candidates.md"

KNOWN_PROBLEM_MARKERS = {
    "fermat": "Fermat's Last Theorem",
    "フェルマー": "Fermat's Last Theorem",
    "goldbach": "Goldbach conjecture",
    "ゴールドバッハ": "Goldbach conjecture",
    "riemann": "Riemann hypothesis",
    "リーマン予想": "Riemann hypothesis",
    "collatz": "Collatz conjecture",
    "コラッツ": "Collatz conjecture",
    "poncelet": "Poncelet porism",
    "ポンスレ": "Poncelet porism",
    "morley": "Morley's trisector theorem",
    "モーリー": "Morley's trisector theorem",
    "gauss circle": "Gauss circle problem",
    "ガウスの円問題": "Gauss circle problem",
    "four color": "Four color theorem",
    "四色": "Four color theorem",
}


@dataclass(frozen=True)
class TypedMorphism:
    name: str
    source: str
    target: str


@dataclass(frozen=True)
class ResearchSpec:
    family_id: str
    title: str
    statement_tex: str
    morphisms: tuple[TypedMorphism, ...]
    query_type: str
    proof_attempts: tuple[str, ...]
    falsification_attempts: tuple[str, ...]
    hardness_reasons: tuple[str, ...]


def _chain(*items: tuple[str, str, str]) -> tuple[TypedMorphism, ...]:
    return tuple(
        TypedMorphism(name=name, source=source, target=target)
        for source, name, target in items
    )


RESEARCH_SPECS: tuple[ResearchSpec, ...] = (
    ResearchSpec(
        "research.geometry.centroid_pedal_iteration",
        "重心ペダル三角形の反復力学",
        r"鋭角不等辺三角形 \(T_0\) をとる。\(T_n\) の重心から3辺へ下ろした"
        r"垂線の足が作る三角形を \(T_{n+1}\) とする。各段階で重心を原点，"
        r"面積を1，第1頂点を正の \(x\) 軸上に置く相似正規化を行う。"
        r"三角形のモジュライ空間における全ての極限集合と周期軌道を分類せよ。",
        _chain(
            ("Triangle", "Centroid", "InteriorPoint"),
            ("InteriorPoint", "PedalProjection", "PointTriple"),
            ("PointTriple", "TriangleFormation", "Triangle"),
            ("Triangle", "SimilarityNormalization", "NormalizedTriangle"),
            ("NormalizedTriangle", "ModuliProjection", "TriangleModuli"),
            ("TriangleModuli", "Iteration", "Orbit"),
            ("Orbit", "Compactification", "CompactOrbit"),
            ("CompactOrbit", "LimitSet", "InvariantSet"),
            ("InvariantSet", "PeriodicDecomposition", "PeriodicData"),
            ("PeriodicData", "ClassificationQuery", "Classification"),
        ),
        "dynamical_classification",
        ("not executed: symbolic fixed-point backend is currently unsupported",),
        ("not executed: random acute-triangle orbit search is scheduled",),
        ("iteration on a two-dimensional moduli space", "global classification"),
    ),
    ResearchSpec(
        "research.geometry.quartic_orthocenter_locus",
        "四次曲線上の頂点が作る垂心軌跡",
        r"\(A=(-1,0),B=(1,0)\) とし，\(P\) を \(x^4+y^4=1,\ y>0\) 上で動かす。"
        r"三角形 \(ABP\) の垂心 \(H(P)\) の軌跡の射影閉包について，"
        r"既約分解・全特異点・幾何種数を決定せよ。",
        _chain(
            ("Superellipse", "MovingPoint", "Point"),
            ("Point", "TriangleAttachment", "Triangle"),
            ("Triangle", "AltitudeConstruction", "LinePair"),
            ("LinePair", "Intersection", "Orthocenter"),
            ("Orthocenter", "RationalCoordinateMap", "RationalImage"),
            ("RationalImage", "ParameterElimination", "AffineCurve"),
            ("AffineCurve", "ProjectiveClosure", "ProjectiveCurve"),
            ("ProjectiveCurve", "SingularityResolution", "ResolvedCurve"),
            ("ResolvedCurve", "GenusComputation", "CurveInvariants"),
            ("CurveInvariants", "ClassificationQuery", "Classification"),
        ),
        "algebraic_curve_invariants",
        ("not executed: resultant and singularity-resolution pipeline is unavailable",),
        ("not executed: real-parameter branch sampling is scheduled",),
        ("singularity resolution", "projective genus computation"),
    ),
    ResearchSpec(
        "research.geometry.ellipse_tritangent_center_locus",
        "楕円の三接線が作る三角形中心の分類",
        r"楕円 \(E:x^2/a^2+y^2/b^2=1\ (a>b>0)\) の媒介点を \(P(t)\) とする。"
        r"接線 \(l_t,l_{t+\alpha},l_{t+\beta}\) が作る三角形の九点中心を \(N(t)\)"
        r"とする。\(0<\alpha<\beta<2\pi\) に対し，\(N(t)\) の軌跡が円錐曲線"
        r"となるための必要十分条件を求め，各場合の方程式を決定せよ。",
        _chain(
            ("Ellipse", "TrigonometricChart", "ParameterCircle"),
            ("ParameterCircle", "TwoShiftAction", "ParameterTriple"),
            ("ParameterTriple", "TangentDualization", "LineTriple"),
            ("LineTriple", "PairwiseIntersection", "Triangle"),
            ("Triangle", "CenterPairConstruction", "CircumcenterOrthocenterPair"),
            ("CircumcenterOrthocenterPair", "MidpointCombination", "NinePointCenter"),
            ("NinePointCenter", "TrigonometricNormalForm", "ParametricCenterCurve"),
            ("ParametricCenterCurve", "ParameterElimination", "Locus"),
            ("Locus", "ConicRecognition", "ConicCondition"),
            ("ConicCondition", "ParameterClassification", "Classification"),
        ),
        "parameter_classification",
        ("not executed: generic symbolic elimination exceeds the configured contract",),
        ("not executed: rational-angle sampling is scheduled",),
        ("two continuous shift parameters", "necessary-and-sufficient classification"),
    ),
    ResearchSpec(
        "research.geometry.inversion_evolute_commutator",
        "反転と発展曲線の可換性",
        r"原点を通らない非退化実円錐曲線 \(C\) と単位円反転 \(I\) を考える。"
        r"正則枝ごとの発展曲線を \(\mathcal E(C)\) とする。"
        r"\(I(\mathcal E(C))\) と \(\mathcal E(I(C))\) が相似変換で一致する"
        r"円錐曲線 \(C\) を，相似を除いて全て分類せよ。",
        _chain(
            ("Conic", "EvoluteWithSource", "ConicEvolutePair"),
            ("ConicEvolutePair", "CircleInversionOfPair", "InvertedConicEvolutePair"),
            ("InvertedConicEvolutePair", "RegularBranchSelection", "RegularCurvePair"),
            ("RegularCurvePair", "SecondEvoluteConstruction", "EvolutePair"),
            ("EvolutePair", "CurveComparison", "ComparedCurvePair"),
            ("ComparedCurvePair", "BranchCompatibility", "CompatibleCurvePair"),
            ("CompatibleCurvePair", "SimilarityWitness", "SimilarityData"),
            ("SimilarityData", "SimilarityQuotient", "SimilarityClassPair"),
            ("SimilarityClassPair", "CommutatorVanishing", "Constraint"),
            ("Constraint", "ConicClassification", "Classification"),
        ),
        "commutation_classification",
        ("not executed: no branch-safe evolute backend for rational quartics",),
        ("not executed: circle and ellipse sampling is scheduled",),
        ("nested envelopes", "classification modulo similarity"),
    ),
    ResearchSpec(
        "research.geometry.minkowski_polar_iteration",
        "Minkowski和と極双対による凸体力学",
        r"原点対称で \(C^\infty\) 級，厳密凸な代数的凸体 \(K\subset\mathbb R^2\)"
        r"を面積 \(\pi\) に正規化する。極体を \(K^\circ\) とし，"
        r"\(\Phi(K)\) を \(K+K^\circ\) を再び面積 \(\pi\) に正規化した凸体とする。"
        r"代数的境界を持つ固定点を線形同値を除いて分類し，"
        r"\(\Phi^n(K)\) の収束・非収束条件を決定せよ。",
        _chain(
            ("AlgebraicConvexBody", "PolarPairing", "BodyDualPair"),
            ("BodyDualPair", "MinkowskiPairing", "BodyPair"),
            ("BodyPair", "MinkowskiAddition", "ConvexBody"),
            ("ConvexBody", "AreaNormalization", "NormalizedBody"),
            ("NormalizedBody", "Iteration", "BodyOrbit"),
            ("BodyOrbit", "SupportFunctionChart", "FunctionOrbit"),
            ("FunctionOrbit", "FixedPointEquation", "FunctionalEquation"),
            ("FunctionalEquation", "LinearEquivalenceQuotient", "ModuliConstraint"),
            ("ModuliConstraint", "StabilityAnalysis", "StabilityData"),
            ("StabilityData", "GlobalClassification", "Classification"),
        ),
        "convex_dynamical_classification",
        ("not executed: functional fixed-point solver is unavailable",),
        ("not executed: finite Fourier truncation search is scheduled",),
        ("infinite-dimensional state before algebraic restriction", "global convergence"),
    ),
    ResearchSpec(
        "research.geometry.polynomial_evolute_real_cusps",
        "多項式グラフの発展曲線に現れる実尖点の最大数",
        r"\(d\ge3\) を固定し，実係数モニック多項式 \(f\)（次数 \(d\)）の"
        r"グラフ \(y=f(x)\) の発展曲線を考える。係数を動かしたときに現れ得る"
        r"孤立実尖点の最大数を \(d\) の式で求め，最大値を達成する多項式を"
        r"係数空間の連結成分ごとに特徴付けよ。",
        _chain(
            ("MonicPolynomial", "CoefficientSpace", "ParameterSpace"),
            ("ParameterSpace", "UniversalPolynomial", "PolynomialFamily"),
            ("PolynomialFamily", "GraphEmbedding", "PlaneCurveFamily"),
            ("PlaneCurveFamily", "NormalField", "NormalFamilyBundle"),
            ("NormalFamilyBundle", "Envelope", "EvoluteFamily"),
            ("EvoluteFamily", "SingularityCondition", "DiscriminantSystem"),
            ("DiscriminantSystem", "RealStratification", "StratifiedSpace"),
            ("StratifiedSpace", "CuspCountFunction", "ConstructibleFunction"),
            ("ConstructibleFunction", "GlobalMaximum", "ExtremalValue"),
            ("ExtremalValue", "ExtremizerClassification", "Classification"),
        ),
        "extremal_real_singularity_count",
        ("not executed: quantifier elimination exceeds the configured degree budget",),
        ("not executed: small-degree coefficient sampling is scheduled",),
        ("variable degree", "real algebraic stratification", "extremal classification"),
    ),
    ResearchSpec(
        "research.geometry.isogonal_curve_transform",
        "曲線の等角共役像の次数・種数公式",
        r"三角形の重心座標で等角共役写像を "
        r"\(\iota[x:y:z]=[yz:zx:xy]\) とする。三頂点を成分に持たない既約平面曲線"
        r"\(C\) について，次数，三頂点での重複度，接錐のデータから"
        r"\(\overline{\iota(C)}\) の次数・全特異点・幾何種数を与える完全な公式を求めよ。",
        _chain(
            ("PlaneCurve", "VertexMultiplicityData", "DecoratedCurve"),
            ("DecoratedCurve", "QuadraticCremonaMap", "RationalImage"),
            ("RationalImage", "BasePointBlowup", "ResolvedMap"),
            ("ResolvedMap", "StrictTransform", "TransformedCurve"),
            ("TransformedCurve", "DegreeAndExceptionalData", "DecoratedTransform"),
            ("DecoratedTransform", "SingularityExtraction", "SingularityData"),
            ("SingularityData", "DeltaInvariant", "DeltaData"),
            ("DeltaData", "AdjunctionFormula", "ArithmeticGenusWithCorrections"),
            ("ArithmeticGenusWithCorrections", "GenusCorrection", "GeometricGenus"),
            ("GeometricGenus", "ClosedFormulaQuery", "Classification"),
        ),
        "birational_invariant_formula",
        ("not executed: blowup bookkeeping is not represented in the current kernel",),
        ("not executed: low-degree curve checks are scheduled",),
        ("base-point resolution", "formula uniform in degree and tangent data"),
    ),
    ResearchSpec(
        "research.geometry.inverted_chord_envelope",
        "楕円の倍角弦を反転した円族の包絡線",
        r"楕円 \(E:x^2/a^2+y^2/b^2=1\) を \(P(t)\) で媒介表示し，整数 \(m\ge2\)"
        r"に対して弦 \(P(t)P(mt)\) を考える。各弦を単位円反転で原点を通る円へ"
        r"移した円族の包絡線について，既約成分，次数，幾何種数を \(m\) の関数として"
        r"決定し，有理成分を持つ \(m\) を分類せよ。",
        _chain(
            ("Ellipse", "TrigonometricChart", "ParameterCircle"),
            ("ParameterCircle", "MultiplicationMap", "PointPair"),
            ("PointPair", "ChordConstruction", "LineFamily"),
            ("LineFamily", "CircleInversion", "CircleFamily"),
            ("CircleFamily", "EnvelopeStationarity", "EnvelopeSystem"),
            ("EnvelopeSystem", "TrigonometricAlgebraization", "PolynomialSystem"),
            ("PolynomialSystem", "ParameterElimination", "AlgebraicCurve"),
            ("AlgebraicCurve", "IrreducibleDecomposition", "CurveComponents"),
            ("CurveComponents", "GenusComputation", "ComponentInvariants"),
            ("ComponentInvariants", "IntegerParameterClassification", "Classification"),
        ),
        "degree_genus_classification",
        ("not executed: symbolic resultant size is expected to grow with m",),
        ("not executed: m=2,3 envelope sampling is scheduled",),
        ("degree growth with an integer parameter", "envelope after inversion"),
    ),
    ResearchSpec(
        "research.geometry.cyclic_polygon_circumcenter_iteration",
        "巡回三頂点外心写像による多角形力学",
        r"同一直線上に3点を持たない凸 \(n\) 角形 \(P_0=(V_1,\ldots,V_n)\) に対し，"
        r"\(V_{i-1},V_i,V_{i+1}\) の外心を新しい頂点 \(W_i\) として \(P_{k+1}\)"
        r"を作る。重心0・二次モーメント1に正規化しながら反復するとき，"
        r"全ての周期軌道と収束する初期多角形を相似を除いて分類せよ。",
        _chain(
            ("ConvexPolygon", "ConsecutiveTriple", "TriangleCycle"),
            ("TriangleCycle", "Circumcenter", "PointCycle"),
            ("PointCycle", "PolygonFormation", "Polygon"),
            ("Polygon", "MomentNormalization", "NormalizedPolygon"),
            ("NormalizedPolygon", "Iteration", "PolygonOrbit"),
            ("PolygonOrbit", "SimilarityQuotient", "PolygonModuliOrbit"),
            ("PolygonModuliOrbit", "OrbitClosure", "CompactifiedOrbit"),
            ("CompactifiedOrbit", "PeriodicAndLimitData", "DynamicalData"),
            ("DynamicalData", "PeriodicPointEquation", "PeriodicConstraint"),
            ("PeriodicConstraint", "AlgebraicDecomposition", "PeriodicData"),
            ("PeriodicData", "GlobalClassification", "Classification"),
        ),
        "polygon_dynamical_classification",
        ("not executed: polygon-moduli dynamics backend is unavailable",),
        ("not executed: random convex-polygon iteration is scheduled",),
        ("high-dimensional rational dynamics", "all periods and basins"),
    ),
    ResearchSpec(
        "research.geometry.superellipse_symmedian_locus",
        "超楕円上の頂点が作る類似重心の軌跡",
        r"\(A=(-1,0),B=(1,0)\) とし，\(P\) を \(x^{2r}+y^{2r}=1,\ y>0\)"
        r"上で動かす。三角形 \(ABP\) の類似重心（symmedian point）\(K(P)\) の"
        r"軌跡の射影閉包について，次数・既約成分・幾何種数を \(r\ge2\) の"
        r"関数として決定し，有理軌跡となる \(r\) を分類せよ。",
        _chain(
            ("SuperellipseFamily", "MovingPoint", "Point"),
            ("Point", "TriangleAttachment", "Triangle"),
            ("Triangle", "SideLengthSquareWeights", "BarycentricWeights"),
            ("BarycentricWeights", "BarycentricCombination", "SymmedianPoint"),
            ("SymmedianPoint", "RationalCoordinateMap", "RationalImage"),
            ("RationalImage", "ParameterElimination", "AlgebraicCurve"),
            ("AlgebraicCurve", "ProjectiveClosure", "ProjectiveCurve"),
            ("ProjectiveCurve", "IrreducibleDecomposition", "CurveComponents"),
            ("CurveComponents", "GenusComputation", "ComponentInvariants"),
            ("ComponentInvariants", "IntegerParameterClassification", "Classification"),
        ),
        "parametric_locus_classification",
        ("not executed: symbolic elimination is budgeted only for small r",),
        ("not executed: r=2,3 numerical sampling is scheduled",),
        ("uniform dependence on r", "triangle-center rational map"),
    ),
    ResearchSpec(
        "research.geometry.offset_polar_duality",
        "平行曲線と極双対の可換性",
        r"原点を内部に持つ \(C^\infty\) 級厳密凸代数曲線 \(C\) に対し，"
        r"外向き距離 \(s\) の平行曲線を \(C_s\)，極双対を \(C^\circ\) とする。"
        r"\((C_s)^\circ\) と \((C^\circ)_t\) がある \(s,t>0\) で相似になる"
        r"代数曲線 \(C\) を相似を除いて分類せよ。",
        _chain(
            ("AlgebraicConvexCurve", "SupportAndDualChart", "PairedSupport"),
            ("PairedSupport", "OffsetAddition", "OffsetSupportPair"),
            ("OffsetSupportPair", "CurveReconstruction", "OffsetCurvePair"),
            ("OffsetCurvePair", "PolarOnFirstBranch", "PolarComparedPair"),
            ("PolarComparedPair", "RegularityRestriction", "RegularCurvePair"),
            ("RegularCurvePair", "SimilarityComparison", "CurvePair"),
            ("CurvePair", "SimilarityInvariantExtraction", "InvariantPair"),
            ("InvariantPair", "OffsetParameterElimination", "ParameterConstraint"),
            ("ParameterConstraint", "FunctionalConstraint", "SupportEquation"),
            ("SupportEquation", "AlgebraicCurveClassification", "Classification"),
        ),
        "duality_commutation_classification",
        ("not executed: support-function equation solver is unavailable",),
        ("not executed: Fourier truncation search is scheduled",),
        ("functional equation", "algebraicity plus convexity constraints"),
    ),
    ResearchSpec(
        "research.geometry.iterated_conic_caustic_degree",
        "円錐曲線の反射焦線を反復したときの次数成長",
        r"光源 \(S\) と，\(S\) を通らない非退化実円錐曲線 \(C_0\) をとる。"
        r"\(C_{n+1}\) を，\(S\) から \(C_n\) へ入射して反射する光線族の包絡線の"
        r"射影閉包とする。退化成分を除いた次数列の成長率を決定し，"
        r"次数が有界または周期的となる \((C_0,S)\) を射影同値を除いて分類せよ。",
        _chain(
            ("ConicSourcePair", "IncidentRayFamily", "RayFamily"),
            ("RayFamily", "ReflectionLaw", "ReflectedRayFamily"),
            ("ReflectedRayFamily", "Envelope", "Caustic"),
            ("Caustic", "ProjectiveClosure", "ProjectiveCurve"),
            ("ProjectiveCurve", "DegenerateComponentRemoval", "ReducedCurve"),
            ("ReducedCurve", "Iteration", "CurveOrbit"),
            ("CurveOrbit", "DegreeSequence", "IntegerSequence"),
            ("IntegerSequence", "AsymptoticGrowth", "GrowthInvariant"),
            ("GrowthInvariant", "DegreeDynamics", "DegreeDynamicsData"),
            ("DegreeDynamicsData", "ExceptionalParameterExtraction", "ParameterConstraint"),
            ("ParameterConstraint", "ProjectiveClassification", "Classification"),
        ),
        "degree_growth_classification",
        ("not executed: iterated-envelope backend is unavailable",),
        ("not executed: one-step degree sampling is scheduled",),
        ("iterated singular envelopes", "classification of exceptional parameters"),
    ),
)


def typecheck_chain(morphisms: tuple[TypedMorphism, ...]) -> tuple[bool, str | None]:
    if not morphisms:
        return False, "empty chain"
    for left, right in zip(morphisms, morphisms[1:]):
        if left.target != right.source:
            return False, f"{left.name}:{left.target} != {right.name}:{right.source}"
    return True, None


def screen_known_problem(text: str) -> list[str]:
    compact = canonical_surface(text)
    return sorted(
        {
            label
            for marker, label in KNOWN_PROBLEM_MARKERS.items()
            if canonical_surface(marker) in compact
        }
    )


def hardness_score(spec: ResearchSpec) -> int:
    score = len(spec.morphisms)
    score += 3 if "classification" in spec.query_type else 0
    score += 2 if any("global" in reason for reason in spec.hardness_reasons) else 0
    score += 2 if any("degree" in reason for reason in spec.hardness_reasons) else 0
    return score


def build_payload() -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    signatures: set[str] = set()
    for spec in RESEARCH_SPECS:
        type_ok, type_error = typecheck_chain(spec.morphisms)
        chain = tuple(morphism.name for morphism in spec.morphisms)
        signature = " -> ".join(
            f"{morphism.source}:{morphism.name}:{morphism.target}"
            for morphism in spec.morphisms
        )
        known_matches = screen_known_problem(spec.statement_tex)
        record = {
            "candidate_id": "research:"
            + hashlib.sha256(spec.family_id.encode("utf-8")).hexdigest()[:12],
            "family_id": spec.family_id,
            "title": spec.title,
            "statement_tex": spec.statement_tex,
            "answer_tex": None,
            "answer_status": "unresolved_by_mathos",
            "not_claimed_human_open": True,
            "query_type": spec.query_type,
            "structural_signature": signature,
            "morphism_chain": list(chain),
            "morphism_count": len(chain),
            "typecheck": {"passed": type_ok, "error": type_error},
            "known_problem_screen": {
                "passed": not known_matches,
                "matches": known_matches,
                "scope": "local marker list; not a literature proof of novelty",
            },
            "proof_attempts": list(spec.proof_attempts),
            "falsification_attempts": list(spec.falsification_attempts),
            "hardness": {
                "score": hardness_score(spec),
                "reasons": list(spec.hardness_reasons),
            },
            "hold_reason": (
                "well-typed and no local famous-problem marker, but current "
                "backend produced neither proof nor counterexample"
            ),
        }
        if not type_ok or known_matches or signature in signatures:
            rejected.append(record)
            continue
        signatures.add(signature)
        records.append(record)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "semantics": {
            "unresolved_by_mathos": (
                "MathOS has not proved or refuted the candidate. This is not a "
                "claim that the problem is open to humanity."
            ),
            "creativity_unit": "unique typed structural_signature, not parameter variants",
        },
        "summary": {
            "retained": len(records),
            "rejected": len(rejected),
            "unique_structural_signatures": len(signatures),
            "unique_query_types": len({record["query_type"] for record in records}),
            "parameter_variants": 0,
        },
        "candidates": records,
        "rejected_candidates": rejected,
    }


def _preserve_stronger_corpus_evidence(
    current: dict[str, Any],
    previous: dict[str, Any] | None,
) -> dict[str, Any]:
    """Keep a larger successful screen when a reduced CI corpus is used."""

    if not previous:
        return current
    if not current.get("passed") or not previous.get("passed"):
        return current
    previous_size = int(previous.get("corpus_size", 0))
    current_size = int(current.get("corpus_size", 0))
    if previous_size < current_size:
        return current
    if previous_size > current_size:
        return previous
    method_strength = {
        "exact_3gram_jaccard": 2,
        "minhash64_conservative": 1,
    }
    previous_strength = method_strength.get(
        str(previous.get("method", "exact_3gram_jaccard")),
        0,
    )
    current_strength = method_strength.get(str(current.get("method", "")), 0)
    if previous_strength <= current_strength:
        return current
    return previous


def apply_corpus_screen(
    payload: dict[str, Any],
    previous_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        from math_os_prototype.jukenmath_full_audit import surface_ngrams
        from math_os_prototype.world_novelty_check import (
            load_jukenmath_hashes,
            load_world_corpus,
            world_novelty,
        )
    except ImportError:  # pragma: no cover
        from jukenmath_full_audit import surface_ngrams
        from world_novelty_check import (
            load_jukenmath_hashes,
            load_world_corpus,
            world_novelty,
        )

    world = load_world_corpus()
    world_grams = [
        (record["source"], surface_ngrams(record["statement"]))
        for record in world
    ]
    juken_hashes = load_jukenmath_hashes()
    try:
        from math_os_prototype.novelty_sketch import screen_snapshot
    except ImportError:  # pragma: no cover
        from novelty_sketch import screen_snapshot
    previous_by_family = {
        record.get("family_id"): record
        for record in (previous_payload or {}).get("candidates", [])
    }
    retained: list[dict[str, Any]] = []
    rejected = list(payload["rejected_candidates"])
    for record in payload["candidates"]:
        novelty = world_novelty(
            record["statement_tex"],
            world_grams,
            juken_hashes,
        )
        corpus_evidence = {
            "passed": novelty["world_novel"],
            "corpus_size": len(world),
            "maximum_surface_jaccard": novelty["max_surface_jaccard"],
            "closest_source": novelty["closest_source"],
            "exact_jukenmath_collision": novelty["exact_jukenmath_collision"],
            "method": "exact_3gram_jaccard",
        }
        sketch = screen_snapshot(record["statement_tex"])
        if sketch and sketch["corpus_size"] > len(world):
            corpus_evidence = {
                "passed": novelty["world_novel"] and sketch["passed"],
                "corpus_size": sketch["corpus_size"],
                "maximum_surface_jaccard": max(
                    novelty["max_surface_jaccard"],
                    sketch["estimated_maximum_surface_jaccard"],
                ),
                "closest_source": sketch["closest_source"],
                "exact_jukenmath_collision": (
                    novelty["exact_jukenmath_collision"]
                    or sketch["exact_surface_collision"]
                ),
                "method": sketch["method"],
                "rejection_threshold": sketch["rejection_threshold"],
                "scope": sketch["scope"],
            }
        previous_record = previous_by_family.get(record["family_id"], {})
        if previous_record.get("statement_tex") == record["statement_tex"]:
            previous_evidence = previous_record.get(
                "known_problem_screen", {}
            ).get("corpus")
            corpus_evidence = _preserve_stronger_corpus_evidence(
                corpus_evidence,
                previous_evidence,
            )
        record["known_problem_screen"]["corpus"] = corpus_evidence
        record["known_problem_screen"]["passed"] = (
            record["known_problem_screen"]["passed"]
            and corpus_evidence["passed"]
        )
        if corpus_evidence["passed"]:
            retained.append(record)
        else:
            record["rejection_reason"] = "reference corpus collision"
            rejected.append(record)

    payload["candidates"] = retained
    payload["rejected_candidates"] = rejected
    corpus_sizes = [
        int(record["known_problem_screen"]["corpus"]["corpus_size"])
        for record in retained
    ]
    payload["summary"].update(
        {
            "retained": len(retained),
            "rejected": len(rejected),
            "unique_structural_signatures": len(
                {record["structural_signature"] for record in retained}
            ),
            "unique_query_types": len(
                {record["query_type"] for record in retained}
            ),
            "reference_corpus_size": min(corpus_sizes, default=len(world)),
            "reference_corpus_size_max": max(corpus_sizes, default=len(world)),
            "current_runtime_corpus_size": len(world),
        }
    )
    return payload


def build_report(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    autonomous = payload.get("autonomous_search", {})
    lines = [
        "# MathOS 研究候補・保留キュー",
        "",
        "> `unresolved_by_mathos` は人類未解決という意味ではない。",
        "> 現在のMathOSが証明も反例も得られなかった状態を表す。",
        "",
        "## 集計",
        "",
        f"- 保留候補: **{summary['retained']}件**",
        f"- 異なる型付き射列: **{summary['unique_structural_signatures']}件**",
        f"- 問いの型: **{summary['unique_query_types']}種類**",
        f"- 数値替え: **{summary['parameter_variants']}件**",
        f"- 各候補の照合母数: **{summary['reference_corpus_size']}問以上**",
        f"- atlas自律探索候補: **{summary.get('autonomous_candidates', 0)}件**",
        f"- 今回の自律追加: **{summary.get('added_by_autonomous_search', 0)}件**",
        f"- 現在の探索深さ下限: **{summary.get('current_depth_floor', 10)}射**",
        "",
        "## 自律探索",
        "",
        f"- 世代: `{autonomous.get('epoch', 0)}`",
        f"- 射アトラス: `{autonomous.get('atlas_morphisms', 0)}射`",
        f"- チャート: `{autonomous.get('domains', 0)}領域`",
        f"- 探索試行: `{autonomous.get('attempts', 0)}`",
        f"- 商: `{autonomous.get('quotient', 'not run')}`",
        "",
        "## 候補",
        "",
    ]
    for record in payload["candidates"]:
        lines.extend(
            [
                f"### {record['title']}",
                "",
                f"- ID: `{record['family_id']}`",
                f"- 状態: `{record['answer_status']}`",
                f"- 射数: `{record['morphism_count']}`",
                f"- 問い: `{record['query_type']}`",
                f"- 難度仮説: `{record['hardness']['score']}`",
                f"- 生成元: `{record.get('origin', 'curated_seed')}`",
                "- 既知問題との表層衝突: `"
                + (
                    "検出なし"
                    if record["known_problem_screen"]["passed"]
                    else "検出あり"
                )
                + "`",
                "- 表層照合コーパス: `"
                + str(
                    record["known_problem_screen"]["corpus"]["corpus_size"]
                )
                + "問`",
                "- 最大表層Jaccard: `"
                + str(
                    record["known_problem_screen"]["corpus"][
                        "maximum_surface_jaccard"
                    ]
                )
                + "`",
                "- 照合方式: `"
                + str(
                    record["known_problem_screen"]["corpus"].get(
                        "method", "exact_3gram_jaccard"
                    )
                )
                + "`",
                "",
                str(record["statement_tex"]),
                "",
                "射列: `" + " → ".join(record["morphism_chain"]) + "`",
                "",
            ]
        )
    lines.extend(
        [
            "## 注意",
            "",
            "- 有名問題スクリーニングは局所マーカーと既存コーパス照合の入口であり、",
            "  文献調査や研究上の新規性証明の代わりではない。",
            "- 保留候補は公開前に専門家レビュー、文献検索、より長い反例探索を行う。",
            "- 解けなかったこと自体を難しさや新規性の証拠にはしない。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--autonomous-count",
        type=int,
        default=0,
        help="typed atlas searchで今回追加する保留候補数",
    )
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()
    previous_payload: dict[str, Any] | None = None
    if args.output.exists():
        try:
            previous_payload = json.loads(args.output.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            previous_payload = None
    try:
        from math_os_prototype.autonomous_morphism_search import grow_payload
    except ImportError:  # pragma: no cover
        from autonomous_morphism_search import grow_payload

    payload = grow_payload(
        build_payload(),
        previous_payload,
        count=max(args.autonomous_count, 0),
        seed=args.seed,
    )
    retained: list[dict[str, Any]] = []
    rejected = list(payload["rejected_candidates"])
    for record in payload["candidates"]:
        matches = screen_known_problem(record["statement_tex"])
        if matches:
            record["known_problem_screen"]["passed"] = False
            record["known_problem_screen"]["matches"] = matches
            record["rejection_reason"] = "known-problem marker collision"
            rejected.append(record)
        else:
            retained.append(record)
    payload["candidates"] = retained
    payload["rejected_candidates"] = rejected
    payload = apply_corpus_screen(payload, previous_payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        stream.write("\n")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(build_report(payload))
    print(json.dumps(payload["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
