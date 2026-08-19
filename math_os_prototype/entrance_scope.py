"""高校数学の語彙による範囲判定。

設計方針（有限語彙による記号推論。AlphaGeometryは歴史的参考のみ）:

    言語そのものが制約である。

公開研究では少数の構築操作で大きな幾何探索空間を扱える。だから「大学範囲が出てきた
らどうするか」という問題が構造的に発生しない。書けないものは生成できない。

MathOS も同じにする。ここで定義するのは:

  1. SCHOOL_PRIMITIVES — 数I/A・II/B・III/C の有限語彙（これが言語）
  2. MORPHISM_LOWERING — 各射がその語彙のどの操作に還元されるか

族(family_id)ごとの許可リストは持たない。族を追加しても登録作業は不要で、
既存の射で組まれていれば自動的に範囲内と判定される。新しい射を足したとき
だけ、その還元を1行書く。これは言語の拡張であって、個別問題の審査ではない。

内部探索で大学数学の道具を使うことは禁止しない。禁止するのは、問題文と解法
を高校の語彙で書けないことだけである。行列で導いた一次分数変換の問題は高校
範囲であり、平方剰余で作ったグラフの問題も「差が平方数なら結ぶ」と書ける以
上は高校範囲である。高校範囲であることと易しいことは別である。
"""

from __future__ import annotations

import re
from typing import Any


CURRICULUM = "jp_upper_secondary_math_IA_IIB_IIIC"

# ---------------------------------------------------------------------------
# 1. 言語: 高校数学の有限語彙
# ---------------------------------------------------------------------------
SCHOOL_PRIMITIVES: frozenset[str] = frozenset(
    {
        # 数と式・整数の性質
        "integer_arithmetic",
        "divisibility",
        "prime_factorization",
        "divisor_counting",
        "congruence",
        "gcd_lcm",
        "square_number",
        "euclidean_algorithm",
        # 式と証明
        "polynomial_expansion",
        "polynomial_factorization",
        "vieta_relations",
        "remainder_theorem",
        "algebraic_identity",
        "mathematical_induction",
        "inequality",
        "simultaneous_equations",
        # 二次関数・二次方程式
        "quadratic_equation",
        "quadratic_discriminant",
        "quadratic_extremum",
        "quadratic_range",
        # 図形と計量
        "trigonometric_ratio",
        "trigonometric_identity",
        "trigonometric_equation",
        "sine_cosine_rule",
        "triangle_area",
        "triangle_center",
        # 場合の数と確率
        "counting",
        "combination",
        "permutation",
        "probability",
        "conditional_probability",
        "expectation",
        "variance",
        "recurrence_probability",
        # 数列
        "sequence",
        "recurrence",
        "general_term",
        "geometric_sequence",
        "arithmetic_sequence",
        "sum_of_series",
        "periodicity",
        # 図形と方程式・ベクトル
        "coordinate_geometry",
        "line_equation",
        "circle_equation",
        "distance_formula",
        "midpoint",
        "inner_product",
        "vector_addition",
        "locus",
        "parameter_elimination",
        "area_shoelace",
        "convex_hull",
        "regular_polygon",
        "symmetry",
        "solid_coordinate_geometry",
        "solid_vector",
        "solid_section",
        "polyhedron",
        "sphere",
        "volume",
        # 複素数平面
        "complex_plane",
        "complex_modulus",
        "de_moivre",
        "roots_of_unity",
        # 関数・微分積分
        "function_composition",
        "rational_function",
        "differentiation",
        "tangent_line",
        "normal_line",
        "definite_integral",
        "area_integral",
        "limit",
        "logarithm",
        "exponential",
        "extremum",
        # 二次曲線・媒介変数
        "parabola",
        "ellipse",
        "hyperbola",
        "parametric_curve",
        "envelope",
    }
)


# ---------------------------------------------------------------------------
# 2. 射 -> 高校原始操作への還元
# ---------------------------------------------------------------------------
# 各射について「高校生がこの一手をどう実行するか」を書く。内部で線型代数や
# 有限体を使っていても、答案として書ける経路があるならその経路を記録する。
# 経路が存在しない射だけが範囲外になる。
MORPHISM_LOWERING: dict[str, tuple[str, ...]] = {
    # --- 整数・数論 ---
    "AlgebraicNorm": ("polynomial_factorization", "integer_arithmetic"),
    "ArithmeticObservation": ("integer_arithmetic",),
    "CoprimeIndexFilter": ("gcd_lcm", "counting"),
    "DivisorCount": ("prime_factorization", "divisor_counting"),
    "EulerCriterion": ("congruence", "square_number"),
    "EulerTotient": ("gcd_lcm", "counting"),
    "IntegerInvariant": ("integer_arithmetic", "algebraic_identity"),
    "IntegerNormalization": ("integer_arithmetic",),
    "IntegerValue": ("integer_arithmetic",),
    "LegendreSymbol": ("congruence", "square_number"),
    "ModularReduction": ("congruence",),
    "ModularPeriod": ("congruence", "periodicity"),
    "MultiplicativeOrder": ("congruence", "periodicity"),
    "PrimeFactorization": ("prime_factorization",),
    "LargestPrimeFactor": ("prime_factorization",),
    # 有限体 F_p は「0 以上 p 未満の整数を p で割った余りで考える」に還元する。
    "PrimeField": ("congruence", "integer_arithmetic"),
    "QuadraticResidueSet": ("congruence", "square_number", "counting"),
    "ScalarPeriod": ("periodicity", "congruence"),
    # --- 多項式・方程式 ---
    "CompanionMatrix": ("recurrence", "general_term"),
    "CubicPolynomial": ("polynomial_expansion", "vieta_relations"),
    "CyclotomicPolynomial": ("polynomial_factorization", "roots_of_unity"),
    "CyclotomicRelation": ("roots_of_unity", "polynomial_factorization"),
    "PolynomialDiscriminant": (
        "vieta_relations",
        "polynomial_expansion",
        "quadratic_discriminant",
    ),
    "PolynomialEvaluation": ("remainder_theorem", "polynomial_expansion"),
    "PolynomialFactorization": ("polynomial_factorization",),
    "ResultantElimination": ("simultaneous_equations", "parameter_elimination"),
    "RootSumRelation": ("vieta_relations",),
    "ThreeRealRootSet": ("differentiation", "extremum", "quadratic_discriminant"),
    "VandermondeDeterminant": ("polynomial_factorization", "algebraic_identity"),
    "VanishingSum": ("roots_of_unity", "sum_of_series"),
    # --- 数列・漸化式 ---
    "BoundaryRecurrence": ("recurrence", "simultaneous_equations"),
    "GeneralTerm": ("general_term",),
    "GeometricIteration": ("geometric_sequence", "recurrence"),
    "GrowthRate": ("geometric_sequence", "limit"),
    "LinearRecurrence": ("recurrence", "general_term"),
    "MinimalPeriod": ("periodicity",),
    "RatioClosedForm": ("geometric_sequence", "general_term"),
    "ReciprocalTransform": ("recurrence", "algebraic_identity"),
    "FixedPoint": ("simultaneous_equations",),
    "FixedPointShift": ("recurrence", "algebraic_identity"),
    "FixedPointSolve": ("quadratic_equation", "simultaneous_equations"),
    "ContractionHalf": ("geometric_sequence", "limit"),
    # --- 極限・微積分 ---
    "ComplexLimit": ("complex_plane", "limit"),
    "LimitEvaluation": ("limit",),
    "LogarithmicLimit": ("logarithm", "limit"),
    "GreenAreaMorphism": ("definite_integral", "area_integral"),
    "AreaObservation": ("area_integral",),
    "AreaSquare": ("area_shoelace",),
    "ClosedCurveOrientation": ("parametric_curve", "area_integral"),
    # --- 複素数平面 ---
    "ComplexLimitEvaluation": ("complex_plane", "limit"),
    "DeMoivrePower": ("de_moivre",),
    "PrimitiveRootOfUnity": ("roots_of_unity", "de_moivre"),
    "PrimitiveRootSet": ("roots_of_unity",),
    "RootOfUnity": ("roots_of_unity",),
    "RootOfUnityChart": ("roots_of_unity", "complex_plane"),
    "RootOfUnityOrbit": ("roots_of_unity", "de_moivre", "symmetry"),
    "HalfStepRotation": ("de_moivre", "complex_plane"),
    "TrigonometricChart": ("trigonometric_identity", "complex_plane"),
    # 一次分数変換は行列で書けるが、高校では合成関数と有理式で追える。
    "MobiusToMatrix": ("rational_function", "function_composition"),
    # 2x2 の固有構造は、高校では f(x)=x すなわち不動点の二次方程式に対応する。
    # グラフの固有値は別の射(AdjacencySpectrum 等)であり、こちらは還元不能。
    "Eigenstructure": ("quadratic_equation", "simultaneous_equations"),
    "MatrixPower": ("function_composition", "periodicity"),
    "MatrixCube": ("function_composition", "counting"),
    "LinearImageRecognition": ("coordinate_geometry", "vector_addition"),
    "DeterminantAreaScaling": ("area_shoelace", "coordinate_geometry"),
    "HomothetyRecognition": ("coordinate_geometry", "symmetry"),
    "SymmetryReduction": ("symmetry",),
    # --- 図形・座標 ---
    "AltitudeConstraint": ("inner_product", "line_equation"),
    "AxisEndpointPair": ("ellipse", "coordinate_geometry"),
    "CentroidMap": ("coordinate_geometry", "midpoint"),
    "CircleParameter": ("circle_equation",),
    "ConicElimination": ("parameter_elimination", "simultaneous_equations"),
    "CoordinateSolve": ("coordinate_geometry", "simultaneous_equations"),
    "CubicCurve": ("differentiation", "coordinate_geometry"),
    "CubicReintersection": ("vieta_relations", "tangent_line", "differentiation"),
    "DistanceMultiset": ("distance_formula", "counting"),
    "DistanceProduct": ("distance_formula", "polynomial_factorization"),
    "DualLinePair": ("line_equation", "tangent_line"),
    "EdgeLengthObservation": ("distance_formula",),
    "EllipseObject": ("ellipse",),
    "HyperbolaObject": ("hyperbola",),
    "CyclicQuadrilateral": ("circle_equation", "trigonometric_ratio"),
    "InscribedAngle": ("circle_equation", "trigonometric_ratio"),
    "CosineRule": ("sine_cosine_rule",),
    "PtolemyRelation": ("circle_equation", "sine_cosine_rule", "algebraic_identity"),
    "AsymptoteLine": ("hyperbola", "line_equation"),
    "FocalProperty": ("hyperbola", "distance_formula"),
    "Eccentricity": ("hyperbola", "algebraic_identity"),
    "IncircleRadius": ("triangle_area", "triangle_center"),
    "ExcircleRadius": ("triangle_area", "triangle_center"),
    "EulerTriangleIdentity": (
        "triangle_center",
        "circle_equation",
        "algebraic_identity",
    ),
    "DiceGeneratingFunction": ("probability", "polynomial_expansion", "counting"),
    "ModalOutcome": ("counting", "combination"),
    "VarianceOfSum": ("variance", "expectation"),
    "EnvelopeStationarity": ("envelope", "parameter_elimination", "differentiation"),
    "EvoluteParametrization": ("parametric_curve", "normal_line", "envelope"),
    "AstroidIdentification": ("parametric_curve", "envelope"),
    "ImageEllipse": ("ellipse", "parameter_elimination"),
    "ImplicitCurveObservation": ("locus", "parameter_elimination"),
    "JoiningLine": ("line_equation",),
    "LineFamily": ("line_equation", "parameter_elimination"),
    "LinearIntersection": ("simultaneous_equations", "line_equation"),
    "LocusEquationObservation": ("locus", "parameter_elimination"),
    "MajorAxisVertexPair": ("ellipse", "coordinate_geometry"),
    "MidpointLocus": ("midpoint", "locus", "parameter_elimination"),
    "MinkowskiAddition": ("vector_addition", "convex_hull"),
    "TriangleConfiguration": ("coordinate_geometry", "triangle_area"),
    "IndependentPointPair": ("coordinate_geometry", "vector_addition"),
    "DisplacementMap": ("vector_addition", "locus"),
    "DifferenceBody": ("vector_addition", "convex_hull"),
    "VertexDifferenceSet": ("vector_addition", "coordinate_geometry"),
    "ConvexHull": ("convex_hull",),
    "CentralSymmetry": ("symmetry", "vector_addition"),
    "HexagonRecognition": ("coordinate_geometry", "area_shoelace"),
    "AffineNormalization": ("coordinate_geometry", "vector_addition"),
    "ConvexPolygon": ("convex_hull", "coordinate_geometry"),
    "MovingCenter": ("locus", "coordinate_geometry"),
    "DiskTranslation": ("circle_equation", "vector_addition"),
    "PassageUnion": ("locus", "area_integral"),
    "ParallelBody": ("vector_addition", "convex_hull"),
    "EdgeStripDecomposition": ("area_integral", "distance_formula"),
    "ExteriorAngleSum": ("regular_polygon", "trigonometric_identity"),
    "SectorAreaMerge": ("circle_equation", "area_integral"),
    # --- 空間図形 ---
    "TetrahedronConfiguration": ("polyhedron", "solid_coordinate_geometry"),
    "SpatialDisplacementMap": ("solid_vector", "locus"),
    "ThreeDimensionalDifferenceBody": ("solid_vector", "polyhedron"),
    "AffineSimplexNormalization": ("solid_coordinate_geometry", "solid_vector"),
    "CoordinateSignPartition": ("solid_coordinate_geometry", "inequality"),
    "PositiveNegativeMassConstraints": ("inequality", "solid_coordinate_geometry"),
    "OrthantSimplexDecomposition": ("polyhedron", "volume", "counting"),
    "BinomialVolumeMerge": ("combination", "volume"),
    "AffineVolumeScaling": ("solid_coordinate_geometry", "volume"),
    "VolumeObservation": ("volume",),
    "CubeConfiguration": ("polyhedron", "solid_coordinate_geometry"),
    "BodyDiagonalDirection": ("solid_vector", "inner_product"),
    "ParallelPlaneFamily": ("solid_coordinate_geometry", "solid_section"),
    "SublevelSolid": ("inequality", "polyhedron", "volume"),
    "SliceVolumeCorrespondence": ("solid_section", "definite_integral", "volume"),
    "CoordinateSimplexVolume": ("solid_coordinate_geometry", "volume"),
    "ThreeCornerExclusion": ("polyhedron", "volume"),
    "InclusionExclusion": ("counting", "algebraic_identity"),
    "PiecewiseQuadraticSectionArea": ("solid_section", "quadratic_extremum"),
    "CentralSymmetryReduction": ("symmetry",),
    "ExtremumObservation": ("extremum",),
    "MovingSphereCenter": ("sphere", "solid_coordinate_geometry"),
    "SpatialPassageUnion": ("sphere", "locus", "volume"),
    "ThreeDimensionalMinkowskiAddition": ("solid_vector", "polyhedron"),
    "FaceEdgeVertexStratification": ("polyhedron", "counting"),
    "FacePrismContribution": ("polyhedron", "volume"),
    "QuarterCylinderEdgeContribution": ("definite_integral", "volume"),
    "SphericalOctantVertexContribution": ("sphere", "volume"),
    "DisjointBoundaryLayerMerge": ("volume", "algebraic_identity"),
    "MovingTriangle": ("coordinate_geometry", "triangle_area"),
    "NormalDirection": ("normal_line", "differentiation"),
    "NormalLine": ("normal_line", "differentiation"),
    "NormalLineFamily": ("normal_line", "parameter_elimination"),
    "OppositeVertexPairing": ("regular_polygon", "symmetry"),
    "OrthocenterIntersection": ("triangle_center", "inner_product"),
    "ParabolaEmbedding": ("parabola", "coordinate_geometry"),
    "ParabolaObject": ("parabola",),
    "ParameterElimination": ("parameter_elimination",),
    "PairedParameterShift": ("parameter_elimination", "symmetry"),
    "PerimeterObservation": ("distance_formula", "sum_of_series"),
    "RegularPolygon": ("regular_polygon",),
    "RegularDoublePolygon": ("regular_polygon", "symmetry"),
    "SecondRegularPolygon": ("regular_polygon", "symmetry"),
    "Reintersection": ("vieta_relations", "simultaneous_equations"),
    "RightAngleCondition": ("inner_product",),
    "ShoelaceArea": ("area_shoelace",),
    "SlopeProductInvariant": ("line_equation", "algebraic_identity"),
    "StationaryParameterSolve": ("differentiation", "extremum"),
    "SupportDirectionMerge": ("vector_addition", "convex_hull"),
    "TangentDualization": ("tangent_line", "parameter_elimination"),
    "TangentLine": ("tangent_line", "differentiation"),
    "TangentVector": ("differentiation", "vector_addition"),
    "TriangleConstruction": ("coordinate_geometry", "triangle_area"),
    "TriangleDecomposition": ("triangle_area", "coordinate_geometry"),
    "AreaSum": ("triangle_area", "sum_of_series"),
    "SquaredDistanceSum": ("distance_formula", "sum_of_series"),
    "VectorSumVanishing": ("vector_addition", "roots_of_unity"),
    "Midpoint": ("midpoint",),
    "LocusElimination": ("locus", "parameter_elimination"),
    "VertexDistances": ("distance_formula", "regular_polygon"),
    "VertexSumHull": ("vector_addition", "convex_hull"),
    "TrigonometricDiagonalization": ("trigonometric_identity", "de_moivre"),
    # --- 場合の数・確率 ---
    "AbsorbingBoundary": ("recurrence_probability", "simultaneous_equations"),
    "AbsorbingWalk": ("probability", "recurrence_probability"),
    "SymmetricRandomWalk": ("probability", "recurrence_probability"),
    "PathStateSpace": ("counting", "recurrence"),
    "HittingTime": ("expectation", "recurrence_probability"),
    "FirstMomentConditioning": ("conditional_probability", "expectation"),
    "FirstMomentLinearSystem": ("expectation", "simultaneous_equations"),
    "SecondMomentConditioning": ("conditional_probability", "variance"),
    "SecondMomentLinearSystem": ("variance", "simultaneous_equations"),
    "VarianceTransform": ("variance", "expectation"),
    "SubsetCount": ("counting", "combination"),
    "ReflectionBijection": ("counting", "combination", "symmetry"),
    "PairCounting": ("counting", "combination"),
    "EdgeExclusion": ("counting", "combination"),
    "SymmetryCount": ("symmetry", "counting"),
    "IncenterWeights": ("triangle_center", "coordinate_geometry"),
    "PowerSequence": ("geometric_sequence", "exponential"),
    "DecimalDigitCount": ("logarithm", "integer_arithmetic"),
    "LeadingDigit": ("logarithm", "integer_arithmetic"),
    "SubsetFamily": ("combination",),
    "CycleCount": ("counting", "combination"),
    "TriangleCount": ("counting", "combination"),
    "ClosedWalkCount": ("counting", "recurrence"),
    "FourCycleDoubleCount": ("counting", "combination"),
    "CommonNeighborCount": ("counting",),
    "CommonNeighborRelation": ("counting", "congruence"),
    "EdgeCommonNeighbors": ("counting", "congruence"),
    # グラフは「頂点を並べ、条件を満たす2点を結ぶ」で高校の数え上げに落ちる。
    "PaleyGraph": ("congruence", "square_number", "counting"),
    "QuadraticResidueGraph": ("congruence", "square_number", "counting"),
    "QuadraticResidueEdges": ("congruence", "square_number", "counting"),
    "ResidueVertices": ("congruence", "counting"),
    "AdjacencyMatrix": ("counting",),
    "StronglyRegularParameters": ("counting", "combination"),
    # --- 通過領域・軌跡（媒介変数の消去）---
    "ParametricLineFamily": ("line_equation", "parameter_elimination"),
    "ParametricParabolaFamily": ("parabola", "parameter_elimination"),
    "ExistenceElimination": ("parameter_elimination", "quadratic_range"),
    "SweptRegionArea": ("parameter_elimination", "area_integral"),
    "ParametricGraph": ("parametric_curve", "quadratic_range"),
    "ContinuousIntervalImage": ("quadratic_range", "inequality"),
    "QuadraticParameterExtrema": ("quadratic_extremum", "inequality"),
    "PiecewiseRegionBounds": ("quadratic_range", "inequality"),
    "VerticalSliceWidth": ("inequality", "area_integral"),
    "DifferentiateParameter": ("differentiation",),
    "StationaryParameterElimination": (
        "differentiation",
        "parameter_elimination",
    ),
    "BoundaryComponent": ("parameter_elimination", "inequality"),
    # --- 関数列・反復・多項式根集合の関係閉包 ---
    "AffineRecurrence": ("recurrence", "function_composition"),
    "FixedPointCoordinate": ("simultaneous_equations", "recurrence"),
    "MonotoneBound": ("inequality", "mathematical_induction"),
    "NonlinearIteration": ("recurrence", "polynomial_expansion"),
    "ErrorCoordinate": ("algebraic_identity", "recurrence"),
    "RepeatedSquaring": ("recurrence", "exponential"),
    "PolynomialRootSet": ("vieta_relations", "polynomial_factorization"),
    "AffineRootMap": ("function_composition", "simultaneous_equations"),
    "PolynomialPullback": (
        "function_composition",
        "polynomial_expansion",
    ),
    "PolynomialExpansion": ("polynomial_expansion",),
    "ReciprocalRootMap": ("rational_function", "simultaneous_equations"),
    "CoefficientReversal": (
        "polynomial_expansion",
        "polynomial_factorization",
    ),
    "TangentDual": ("tangent_line", "parameter_elimination"),
    "Projectivize": ("coordinate_geometry", "parameter_elimination"),
    "AxisIntercepts": ("line_equation", "coordinate_geometry"),
    "ConvexHull": ("convex_hull",),
    "Centroid": ("coordinate_geometry", "midpoint"),
    "Area": ("area_shoelace",),
    "VandermondeArea": ("area_shoelace", "polynomial_factorization"),
    "CyclicOrder": ("symmetry", "counting"),
    "PairwiseAddition": ("vector_addition",),
    "Norm": ("complex_modulus", "distance_formula"),
    # --- 融合（三角関数×絶対値・床関数）---
    "AbsoluteIntegral": ("definite_integral", "trigonometric_equation"),
    "SignPartition": ("trigonometric_equation", "inequality"),
    "SignReduction": ("inequality", "trigonometric_identity"),
    "FloorStep": ("inequality", "counting"),
    "PiecewiseIntegral": ("definite_integral", "inequality"),
    "ComplementIntegral": ("definite_integral", "area_integral"),
    "TrigLevelSets": ("trigonometric_equation", "inequality"),
    "TrigDifference": ("trigonometric_identity",),
    "TrigonometricNormalForm": ("trigonometric_identity",),
    "ReflectionSubstitution": ("definite_integral", "symmetry"),
    "CaseSplit": ("inequality",),
    # --- 微積分・極限 ---
    "Differentiate": ("differentiation",),
    "Maximum": ("extremum", "differentiation"),
    "Minimum": ("extremum", "differentiation"),
    "ConstrainedSymmetric": ("inequality", "algebraic_identity"),
    "SubstituteConstraint": ("simultaneous_equations", "algebraic_identity"),
    "SquareCompletion": ("polynomial_factorization", "inequality"),
    "InequalityProof": ("inequality", "algebraic_identity"),
    "TriangleAngleSum": ("trigonometric_identity",),
    "SumToProduct": ("trigonometric_identity",),
    "ParametricPoint": ("parametric_curve", "coordinate_geometry"),
    "FocalChordConstraint": ("parabola", "line_equation"),
    "DistanceFormula": ("distance_formula",),
    "EqualityCase": ("inequality",),
    "IncrementLimit": ("limit", "differentiation"),
    "StolzCesaro": ("limit", "sequence"),
    "DominatedConvergence": ("limit", "inequality"),
    "IntegralTransform": ("definite_integral",),
    "BetaEvaluation": ("definite_integral", "polynomial_expansion"),
    "EvaluateMeasure": ("area_integral",),
    "EvaluateClosedForm": ("algebraic_identity",),
    "EvaluateAtZero": ("remainder_theorem",),
    "PowerSubstitution": ("definite_integral", "algebraic_identity"),
    "PositiveSquareRoot": ("quadratic_equation", "inequality"),
    "SimplifyRational": ("rational_function", "algebraic_identity"),
    "PartialFraction": ("rational_function", "algebraic_identity"),
    "ClearInverses": ("rational_function", "algebraic_identity"),
    # --- 数列・級数 ---
    "FiniteSum": ("sum_of_series",),
    "FiniteProduct": ("sum_of_series", "algebraic_identity"),
    "HarmonicSum": ("sum_of_series",),
    "TelescopeCollapse": ("sum_of_series", "algebraic_identity"),
    "SolveRecurrence": ("recurrence", "general_term"),
    "Interpolation": ("polynomial_factorization", "simultaneous_equations"),
    "LinearElimination": ("simultaneous_equations",),
    # --- 二項係数・格子路・確率 ---
    "BinomialExpansion": ("polynomial_expansion", "combination"),
    "BinomialDifference": ("combination", "algebraic_identity"),
    "BinomialGeneratingFunction": ("combination", "polynomial_expansion"),
    "LatticePathEncoding": ("counting", "combination"),
    "BridgePathSpace": ("counting", "combination"),
    "ReflectionPrinciple": ("counting", "combination", "symmetry"),
    "Expectation": ("expectation",),
    "LinearityExpectation": ("expectation",),
    "RecordIndicator": ("probability", "expectation"),
    "Cardinality": ("counting",),
    # --- 複素数・整数 ---
    "ComplexRootSet": ("complex_plane", "roots_of_unity"),
    "RootSet": ("polynomial_factorization",),
    "RootOfUnityFilter": ("roots_of_unity", "sum_of_series"),
    "RootOfUnityReduction": ("roots_of_unity", "congruence"),
    "VanishingTransform": ("roots_of_unity", "sum_of_series"),
    "SquareObservable": ("square_number", "integer_arithmetic"),
    "QuadraticCharacter": ("congruence", "square_number"),
    "PrimePowerReduction": ("prime_factorization", "congruence"),
    "DivisorSumExpansion": ("divisor_counting", "sum_of_series"),
    "DivisorIncidence": ("divisibility", "counting"),
    "MultiplicativeAssembly": ("prime_factorization", "divisor_counting"),
    "Discriminant": ("quadratic_discriminant",),
    "QuadraticDiscriminant": ("quadratic_discriminant",),
    "UniformLatticePair": ("counting", "probability"),
    "LatticeRescaling": ("coordinate_geometry", "limit"),
    "RegionLimit": ("limit", "definite_integral"),
    "RootDifference": ("quadratic_equation", "algebraic_identity"),
    "RestrictedAverage": ("counting", "sum_of_series", "limit"),
    # --- モルフォロジー・アトラスの隣接射 ---
    "CoefficientInstantiation": ("integer_arithmetic", "counting"),
    "DiscriminantFilter": ("quadratic_discriminant", "inequality"),
    "ScalingLimit": ("coordinate_geometry", "limit"),
    "RegionMeasure": ("area_integral",),
    "RestrictedMoment": ("definite_integral", "probability"),
    "CyclicOrbit": ("roots_of_unity", "symmetry"),
    "OrbitResidues": ("congruence", "periodicity"),
    "FiniteFourierTransform": ("roots_of_unity", "sum_of_series"),
    "CoefficientEncoding": ("polynomial_expansion", "sum_of_series"),
    "CoefficientClass": ("counting", "combination"),
    "UniformMeasure": ("probability", "counting"),
    "CoordinateRealization": ("coordinate_geometry", "distance_formula"),
    "EquationEncoding": ("simultaneous_equations", "polynomial_expansion"),
    "RootExtraction": ("quadratic_equation", "vieta_relations"),
    "InvariantQuotient": ("vieta_relations", "algebraic_identity"),
    "ComplexRootEncoding": ("complex_plane", "roots_of_unity"),
    "InvariantLocus": ("coordinate_geometry", "parameter_elimination"),
    "ExtremalObservation": ("locus", "extremum", "differentiation"),
    "AntipodalFactorization": ("roots_of_unity", "polynomial_factorization"),
    "CompatibilityClass": ("counting", "combination", "symmetry"),
    "CardinalityObservation": ("counting",),
    "ZeroIndicators": ("counting",),
    # --- 高校の語彙に還元できない射（範囲外）---
    # 行列式・スペクトル・フーリエは、答案として高校の一手に分解できない。
    "Determinant": (),
    "DeterminantFunctor": (),
    "LaplaceExpansion": (),
    "Triangularize": (),
    "MatrixModel": (),
    "RemoveKernel": (),
    "Laplacian": (),
    "FourierSpectrum": (),
    "ExtensionFieldEvaluation": (),
    # 固有値・スペクトル・行列木定理は、答案として高校の一手に分解できない。
    # 内部探索では使ってよいが、この射が解法に残る限り受験用には出さない。
    "AdjacencySpectrum": (),
    "LaplacianSpectrum": (),
    "LaplacianTransform": (),
    "NonzeroEigenvalueProduct": (),
    "MatrixTreeTheorem": (),
    "SpanningTreeCount": (),
    "TraceInvariant": (),
}


# ---------------------------------------------------------------------------
# 3. 表面語の書き換え（禁止ではなく lowering）
# ---------------------------------------------------------------------------
# 「Paley グラフ」のような語は、その直前で対象が完全に定義されている場合、
# 単に付け足された固有名詞にすぎない。定義が済んでいるならラベルを外すだけで
# 高校の語彙になる。名前で却下するのではなく、名前を外す。
def _residue_set(match: "re.Match[str]") -> str:
    """\\mathbb Z_n を数式中でそのまま読める集合表記に落とす。"""
    n = int(match.group(1))
    return r"\{0,1,\dots," + str(n - 1) + r"\}"


SURFACE_REWRITES: tuple[tuple[str, Any], ...] = (
    # 「x-y が平方剰余のとき結んで得られる Paley グラフ」→ 定義済みなのでラベル不要
    (r"結んで得られる\s*(?:Paley|ペイリー)\s*グラフ", "結んで得られるグラフ"),
    (r"(?:Paley|ペイリー)\s*グラフ\s*([A-Za-z])\s*を", r"グラフ \1 を"),
    # 「Minkowski和 P+Q={p+q|...}」→ 集合の定義が併記されているのでラベル不要
    (r"(?:Minkowski|ミンコフスキー)\s*和", "図形"),
    # ルジャンドル記号は定義を書き下せば「1 か -1 か」を問うだけになる
    (
        r"ルジャンドル記号\s*\\\(\\left\(\\dfrac\{([^{}]+)\}\{([^{}]+)\}"
        r"\\right\)\\\)\s*の値を求めよ",
        r"\\(\1\\) が \\(\2\\) を法として平方数と合同ならば \\(1\\)，"
        r"そうでなければ \\(-1\\) とする。この値を求めよ",
    ),
    # 平方剰余は高校の言葉では「平方数と合同」
    (r"平方剰余である", "平方数と合同である"),
    (r"平方剰余のとき", "平方数と合同なとき"),
    # Z_n は数式中なので、そのまま数式として書ける形に落とす
    (r"\\mathbb\s*Z_\{([0-9]+)\}", _residue_set),
    (r"\\mathbb\s*Z_([0-9]+)", _residue_set),
)


# 書き換え後も残ってはいけない語。残っている場合は lowering が未完了である
# ことの証拠として扱う（族が悪いのではなく、文章がまだ高校語彙でない）。
OUT_OF_VOCABULARY_SURFACE_TERMS: tuple[str, ...] = (
    "Paley",
    "ラプラシアン",
    "隣接行列",
    "全域木",
    "固有値",
    "スペクトル",
    "Minkowski",
    "ミンコフスキー",
    "ルジャンドル記号",
    "行列木定理",
    r"\mathbb F_",
)


def lower_surface(text: str) -> str:
    """問題文・解法を高校の語彙へ書き換える。"""
    out = text
    for pattern, replacement in SURFACE_REWRITES:
        out = re.sub(pattern, replacement, out)
    return out


def unregistered_morphisms(chain: list[str]) -> list[str]:
    """まだ還元が書かれていない射を返す。言語を広げるときの作業指示になる。"""
    return [m for m in chain if m not in MORPHISM_LOWERING]


def certify_entrance_scope(
    problem: dict[str, Any],
) -> dict[str, Any] | None:
    """問題が高校数学の語彙だけで書けるなら証明書を返す。

    族名は一切参照しない。射の並びと問題文の表面語だけで判定する。
    """
    lift = problem.get("lift_certificate") or {}
    morphisms = list(lift.get("morphism_chain") or [])
    if not morphisms or not lift.get("type_checked"):
        return None

    # 1) すべての射に還元が登録されているか
    lowering: list[str] = []
    by_morphism: list[dict[str, Any]] = []
    for morphism in morphisms:
        primitives = MORPHISM_LOWERING.get(morphism)
        if primitives is None:
            return None  # 未登録の射: 言語がまだこれを含んでいない
        if not primitives:
            return None  # 還元経路なし: 高校の一手に分解できない
        for primitive in primitives:
            if primitive not in SCHOOL_PRIMITIVES:
                return None
            if primitive not in lowering:
                lowering.append(primitive)
        # どの射がどの原始操作に落ちるかを射ごとに残す。
        # lowering_chain は重複を除いた集合なので、位置で対応づけてはいけない。
        by_morphism.append({"morphism": morphism, "primitives": list(primitives)})

    # 2) 問題文と解法を高校の語彙へ書き換える
    statement = str(problem.get("statement_tex") or "")
    solution = str(problem.get("solution_tex") or "")
    lowered_statement = lower_surface(statement)
    lowered_solution = lower_surface(solution)

    # 3) 書き換えても残る語があれば lowering 未完了
    surface = f"{lowered_statement} {lowered_solution}"
    residual = [t for t in OUT_OF_VOCABULARY_SURFACE_TERMS if t in surface]
    if residual:
        return None

    certificate: dict[str, Any] = {
        "scope": CURRICULUM,
        "type_checked": True,
        "abstract_morphism_chain": morphisms,
        "lowering_chain": lowering,
        "lowering_by_morphism": by_morphism,
        "uses_only_school_level_primitives": True,
    }
    if lowered_statement != statement or lowered_solution != solution:
        certificate["surface_rewritten"] = True
        certificate["statement_tex_lowered"] = lowered_statement
        certificate["solution_tex_lowered"] = lowered_solution
    return certificate
