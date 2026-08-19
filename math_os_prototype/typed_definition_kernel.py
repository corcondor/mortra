"""Typed definition kernel for MathOS.

This module is intentionally not a solver.  Its job is to compile mathematical
vocabulary into typed definitions and logic-level obligations.  The same
definition should be reused when numbers, coefficients, or surface phrasing
change.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

try:
    from math_os_prototype.case_frame_parser import parse_case_frames
    from math_os_prototype.structural_parser import StructuralIR, analyze_structure
except ImportError:  # Allows local script use.
    from case_frame_parser import parse_case_frames
    from structural_parser import StructuralIR, analyze_structure


@dataclass(frozen=True)
class SortSpec:
    name: str
    kind: str
    definition: str
    parameters: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DefinitionEntry:
    canonical: str
    surfaces: tuple[str, ...]
    role: str
    type_signature: str
    expansion: str
    backend_theory: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TypedDefinitionIR:
    source_text: str
    normalized_text: str
    status: str
    sorts: list[dict[str, Any]]
    definitions_used: list[dict[str, Any]]
    declarations: list[dict[str, str]]
    terms: list[dict[str, Any]]
    predicates: list[dict[str, Any]]
    query: dict[str, Any]
    logic: str
    backend_obligations: list[dict[str, Any]]
    case_frames: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


CORE_SORTS: tuple[SortSpec, ...] = (
    SortSpec("Bool", "primitive", "truth values"),
    SortSpec("Real", "primitive", "complete ordered field"),
    SortSpec("Complex", "primitive", "algebraic closure of Real"),
    SortSpec("Integer", "primitive", "discrete ordered ring"),
    SortSpec("Natural", "subsort", "{n in Integer | n >= 0}"),
    SortSpec("Point2", "alias", "Vector(Real, 2)"),
    SortSpec("Point3", "alias", "Vector(Real, 3)"),
    SortSpec("Vector", "type_constructor", "Fin(n) -> Real", ["n"]),
    SortSpec("Matrix", "type_constructor", "Fin(m) x Fin(n) -> Real", ["m", "n"]),
    SortSpec("Polynomial", "structure", "FiniteSupport(Natural, Real)"),
    SortSpec("Sequence", "type_constructor", "Natural -> T", ["T"]),
    SortSpec("Graph", "structure", "(VertexSet, EdgeRelation)"),
    SortSpec("EigenvalueMultiset", "alias", "FiniteMultiset(Number)"),
    SortSpec("Vector2", "alias", "Vector(Real, 2)"),
    SortSpec("Fin", "indexed_sort", "{0, ..., n-1}", ["n"]),
    SortSpec("Set", "type_constructor", "T -> Bool", ["T"]),
    SortSpec("Function", "type_constructor", "A -> B", ["A", "B"]),
    SortSpec("Curve2", "alias", "Set(Point2)"),
    SortSpec("Region2", "alias", "Set(Point2)"),
    SortSpec("Region3", "alias", "Set(Point3)"),
    SortSpec("ProbabilitySpace", "structure", "(Omega, Sigma, P)"),
    SortSpec("RandomVariable", "alias", "Omega -> Real"),
    SortSpec("StochasticProcess", "alias", "Index -> RandomVariable"),
    SortSpec("InnerProductSpace", "structure", "(V, <.,.>)"),
)


LEXICON: tuple[DefinitionEntry, ...] = (
    DefinitionEntry(
        "Point2",
        ("点", "point"),
        "sort",
        "Sort",
        "Point2 := Vector(Real, 2)",
        "linear_real_arithmetic",
    ),
    DefinitionEntry(
        "Line2",
        ("直線", "line"),
        "definition",
        "Point2 x Point2 -> Curve2",
        "Line(A,B) := {P:Point2 | exists t:Real, P = A + t*(B-A)}",
        "real_closed_fields",
    ),
    DefinitionEntry(
        "Curve2",
        ("曲線", "curve", "グラフ"),
        "sort",
        "Sort",
        "Curve2 := Set(Point2); Graph(f) := {(x,y):Point2 | y=f(x)}",
        "real_closed_fields",
    ),
    DefinitionEntry(
        "Circle",
        ("円", "circle"),
        "definition",
        "Point2 x Real -> Curve2",
        "Circle(O,r) := {P:Point2 | dist(P,O)^2 = r^2 and r >= 0}",
        "real_closed_fields",
    ),
    DefinitionEntry(
        "FiniteShape",
        ("有限図形", "finite shape"),
        "definition",
        "Natural -> Sort",
        "FiniteShape(n) := Fin(n) -> Point2",
        "dependent_type",
    ),
    DefinitionEntry(
        "Polygon",
        ("多角形", "polygon", "三角形", "四角形", "五角形"),
        "definition",
        "Natural -> (Fin(n)->Point2) -> Prop",
        "Polygon(n,P) := P:Fin(n)->Point2 and NondegenerateCyclicPointSequence(n,P)",
        "real_closed_fields",
    ),
    DefinitionEntry(
        "RegularPolygon",
        ("正多角形", "regular polygon", "正三角形", "正方形", "正五角形"),
        "definition",
        "Natural -> (Fin(n)->Point2) -> Prop",
        "RegularPolygon(n,P) := Polygon(n,P) and all edges equal and all turning angles equal",
        "real_closed_fields",
    ),
    DefinitionEntry(
        "EdgeLength",
        ("辺の長さ", "三辺", "edge length", "side length"),
        "definition",
        "(Fin(n)->Point2) x Fin(n) -> Real",
        "EdgeLength(P,i) := dist(P(i), P((i+1) mod n))",
        "real_closed_fields",
    ),
    DefinitionEntry(
        "Circumradius",
        ("外接円半径", "外接円の半径", "circumradius"),
        "definition",
        "(Fin(n)->Point2) -> Real",
        "Circumradius(P) := the nonnegative r for which exists O, forall i, dist(P(i),O)=r",
        "real_closed_fields",
    ),
    DefinitionEntry(
        "Inradius",
        ("内接円半径", "内接円の半径", "inradius"),
        "definition",
        "(Fin(n)->Point2) -> Real",
        "Inradius(P) := the nonnegative distance from the incenter to every supporting edge",
        "real_closed_fields",
    ),
    DefinitionEntry(
        "Irrational",
        ("無理数", "irrational"),
        "definition",
        "Real -> Prop",
        "Irrational(x) := not exists p q:Integer, q != 0 and x = p/q",
        "number_theory",
    ),
    DefinitionEntry(
        "Centroid",
        ("重心", "centroid"),
        "definition",
        "Natural -> (Fin(n)->Point2) -> Point2",
        "Centroid(n,P) := (1/n) * Sum(i in Fin(n), P(i))",
        "linear_real_arithmetic",
    ),
    DefinitionEntry(
        "Tangent",
        ("接線", "tangent"),
        "definition",
        "Curve2 x Point2 -> Line2",
        "Tangent(C,P) := line with first-order contact with C at P",
        "differential_algebra",
    ),
    DefinitionEntry(
        "Intersection",
        ("交点", "intersection"),
        "definition",
        "Set(T) x Set(T) -> Set(T)",
        "Intersection(A,B) := {x | x in A and x in B}",
        "set_theory",
    ),
    DefinitionEntry(
        "Locus",
        ("軌跡", "locus"),
        "definition",
        "Variable(T) x Prop -> Set(T)",
        "Locus(x, phi) := {x | phi}",
        "set_theory",
    ),
    DefinitionEntry(
        "Region2",
        ("領域", "region"),
        "sort",
        "Sort",
        "Region2 := Set(Point2)",
        "set_theory",
    ),
    DefinitionEntry(
        "Area",
        ("面積", "area"),
        "definition",
        "Region2 -> Real",
        "Area(R) := LebesgueMeasure2(R)",
        "measure_theory",
    ),
    DefinitionEntry(
        "Volume",
        ("体積", "volume"),
        "definition",
        "Region3 -> Real",
        "Volume(R) := LebesgueMeasure3(R)",
        "measure_theory",
    ),
    DefinitionEntry(
        "Limit",
        ("極限", "\\lim", "limit"),
        "definition",
        "Function -> Real",
        "Limit(f) := L where f converges to L in the declared filter",
        "real_analysis",
    ),
    DefinitionEntry(
        "Correlation",
        ("相関係数", "correlation coefficient", "correlation"),
        "definition",
        "RandomVariable x RandomVariable -> Real",
        "Correlation(X,Y) := NormalizedInnerProduct(Center(X), Center(Y)) in L2(P)",
        "probability",
    ),
    DefinitionEntry(
        "Center",
        ("中心化", "centered", "centering"),
        "definition",
        "RandomVariable -> RandomVariable",
        "Center(X) := X - Expectation(P,X)",
        "probability",
    ),
    DefinitionEntry(
        "Covariance",
        ("共分散", "covariance"),
        "definition",
        "RandomVariable x RandomVariable -> Real",
        "Covariance(X,Y) := InnerProduct(Center(X), Center(Y)) in L2(P)",
        "probability",
    ),
    DefinitionEntry(
        "Polynomial",
        ("多項式", "polynomial"),
        "sort",
        "Sort",
        "Polynomial(R) := finitely supported coefficient sequence over ring R",
        "polynomial_ring",
    ),
    DefinitionEntry(
        "Evaluation",
        ("の値", "evaluate", "evaluation"),
        "definition",
        "Function x Object -> Number",
        "Evaluation(f,x) := f(x)",
        "function_theory",
    ),
    DefinitionEntry(
        "Sequence",
        ("数列", "sequence"),
        "sort",
        "Sort",
        "Sequence(T) := Natural -> T",
        "discrete_math",
    ),
    DefinitionEntry(
        "LinearRecurrence",
        ("線形漸化式", "漸化式", "linear recurrence", "recurrence"),
        "definition",
        "Sequence(Real) x Natural x Vector -> Prop",
        "LinearRecurrence(x,k,c) := forall n, x(n+k)=Sum(i in Fin(k), c(i)*x(n+i))",
        "discrete_math",
    ),
    DefinitionEntry(
        "Floor",
        ("床関数", "\\lfloor", "floor"),
        "definition",
        "Real -> Integer",
        "Floor(x) := the unique z:Integer such that z <= x < z+1",
        "integer_arithmetic",
    ),
    DefinitionEntry(
        "QuadraticCurve",
        ("二次曲線", "双曲線", "楕円", "放物線", "conic", "hyperbola", "ellipse", "parabola"),
        "definition",
        "SymmetricMatrix(3) -> Curve2",
        "QuadraticCurve(Q) := {p:Point2 | Homogeneous(p)^T Q Homogeneous(p)=0}",
        "real_closed_fields",
    ),
    DefinitionEntry(
        "Graph",
        ("グラフ", "graph"),
        "sort",
        "Sort",
        "Graph := (V,E) where E is a binary relation on V",
        "graph_theory",
    ),
    DefinitionEntry(
        "Matrix",
        ("行列", "matrix"),
        "sort",
        "Sort",
        "Matrix(m,n) := Fin(m) x Fin(n) -> Real",
        "linear_algebra",
    ),
    DefinitionEntry(
        "Laplacian",
        ("ラプラシアン", "laplacian"),
        "definition",
        "Graph -> Matrix",
        "Laplacian(G) := DegreeMatrix(G) - AdjacencyMatrix(G)",
        "spectral_graph_theory",
    ),
    DefinitionEntry(
        "Eigenvalues",
        ("固有値", "eigenvalue", "eigenvalues", "spectrum"),
        "definition",
        "Matrix -> FiniteMultiset(Number)",
        "Eigenvalues(A) := multiset of roots of det(lambda I-A)",
        "linear_algebra",
    ),
    DefinitionEntry(
        "Determinant",
        ("行列式", "determinant"),
        "definition",
        "Matrix -> Number",
        "Determinant(A) := alternating multilinear volume form normalized at I",
        "linear_algebra",
    ),
    DefinitionEntry(
        "InnerProduct",
        ("内積", "inner product", "inner-product"),
        "definition",
        "InnerProductSpace x Vector x Vector -> Real",
        "InnerProduct(V,x,y) is bilinear, symmetric, and positive definite",
        "linear_algebra",
    ),
    DefinitionEntry(
        "Norm",
        ("ノルム", "norm"),
        "definition",
        "InnerProductSpace x Vector -> Real",
        "Norm(V,x) := sqrt(InnerProduct(V,x,x))",
        "linear_algebra",
    ),
    DefinitionEntry(
        "NormalizedInnerProduct",
        ("正規化内積", "normalized inner product", "cosine similarity"),
        "definition",
        "InnerProductSpace x Vector x Vector -> Real",
        "NormalizedInnerProduct(V,x,y) := InnerProduct(V,x,y)/(Norm(V,x)*Norm(V,y))",
        "linear_algebra",
    ),
    DefinitionEntry(
        "FrobeniusInnerProduct",
        ("フロベニウス内積", "Frobenius inner product", "Frobenius積"),
        "definition",
        "Matrix x Matrix -> Real",
        "FrobeniusInnerProduct(A,B) := Trace(Transpose(A)*B)",
        "linear_algebra",
    ),
    DefinitionEntry(
        "CorrelationFunction",
        ("相関関数", "自己相関", "autocorrelation", "correlation function"),
        "definition",
        "StochasticProcess x Integer -> Real",
        "CorrelationFunction(X,k) := Correlation(X_t, X_(t+k)) for a stationary process",
        "probability",
    ),
    DefinitionEntry(
        "QuadraticForm",
        ("二次形式", "quadratic form"),
        "definition",
        "Matrix x Vector -> Real",
        "QuadraticForm(Q,x) := InnerProduct(x,Q*x)",
        "linear_algebra",
    ),
    DefinitionEntry(
        "PositiveDefinite",
        ("正定値", "positive definite"),
        "definition",
        "Matrix -> Prop",
        "PositiveDefinite(Q) := forall x != 0, QuadraticForm(Q,x) > 0",
        "linear_algebra",
    ),
    DefinitionEntry(
        "Projection",
        ("直交射影", "射影", "orthogonal projection", "projection"),
        "definition",
        "InnerProductSpace x Vector x Set(Vector) -> Vector",
        "Projection(V,x,S) := unique y in S with x-y orthogonal to S",
        "linear_algebra",
    ),
    DefinitionEntry(
        "Maximum",
        ("最大値", "maximum", "max"),
        "definition",
        "(T->Real) x Set(T) -> Real",
        "Maximum(f,S) := a where exists x in S, f(x)=a and forall y in S, f(y)<=a",
        "optimization",
    ),
    DefinitionEntry(
        "Minimum",
        ("最小値", "最小化", "minimum", "minimize", "min"),
        "definition",
        "(T->Real) x Set(T) -> Real",
        "Minimum(f,S) := a where exists x in S, f(x)=a and forall y in S, a<=f(y)",
        "optimization",
    ),
    DefinitionEntry(
        "Integer",
        ("整数", "integer"),
        "sort",
        "Sort",
        "Integer := {...,-2,-1,0,1,2,...}",
        "integer_arithmetic",
    ),
    DefinitionEntry(
        "Natural",
        ("自然数", "正の整数", "natural number", "positive integer"),
        "sort",
        "Sort",
        "Natural := {n:Integer | n >= 0}; PositiveInteger := {n:Integer | n > 0}",
        "integer_arithmetic",
    ),
    DefinitionEntry(
        "Prime",
        ("素数", "prime"),
        "definition",
        "Integer -> Prop",
        "Prime(n) := n > 1 and forall d:Integer, d divides n -> d=1 or d=n",
        "number_theory",
    ),
    DefinitionEntry(
        "Divides",
        ("割り切る", "約数", "因数", "divides", "divisor"),
        "definition",
        "Integer x Integer -> Prop",
        "Divides(d,n) := exists k:Integer, n = d*k",
        "integer_arithmetic",
    ),
    DefinitionEntry(
        "GCD",
        ("最大公約数", "gcd"),
        "definition",
        "Integer x Integer -> Integer",
        "GCD(a,b) := greatest d such that Divides(d,a) and Divides(d,b)",
        "number_theory",
    ),
    DefinitionEntry(
        "LCM",
        ("最小公倍数", "lcm"),
        "definition",
        "Integer x Integer -> Integer",
        "LCM(a,b) := least positive m such that Divides(a,m) and Divides(b,m)",
        "number_theory",
    ),
    DefinitionEntry(
        "Factorial",
        ("階乗", "factorial"),
        "definition",
        "Natural -> Natural",
        "Factorial(n) := product(k in {1,...,n}, k)",
        "integer_arithmetic",
    ),
    DefinitionEntry(
        "ProbabilitySpace",
        ("確率", "probability"),
        "structure",
        "Sort",
        "ProbabilitySpace := (Omega, Sigma, P) with P(Omega)=1",
        "probability",
    ),
    DefinitionEntry(
        "Expectation",
        ("期待値", "\\operatorname{E}", "expectation", "expected value"),
        "definition",
        "ProbabilitySpace x RandomVariable -> Real",
        "Expectation(P,X) := integral_Omega X dP",
        "measure_theory",
    ),
    DefinitionEntry(
        "Forall",
        ("すべて", "任意", "各", "forall", "for all"),
        "logical_form",
        "(T -> Prop) -> Prop",
        "forall x:T, phi(x)",
        "logic",
    ),
    DefinitionEntry(
        "And",
        ("かつ", "および", "and", "∧"),
        "logical_connective",
        "Prop x Prop -> Prop",
        "And(phi, psi) := phi ∧ psi",
        "logic",
    ),
    DefinitionEntry(
        "Or",
        ("または", "or", "∨"),
        "logical_connective",
        "Prop x Prop -> Prop",
        "Or(phi, psi) := phi ∨ psi",
        "logic",
    ),
    DefinitionEntry(
        "Implies",
        ("ならば", "なら", "implies", "=>", "→"),
        "logical_connective",
        "Prop x Prop -> Prop",
        "Implies(phi, psi) := phi -> psi",
        "logic",
    ),
    DefinitionEntry(
        "Not",
        ("でない", "ではない", "not", "¬"),
        "logical_connective",
        "Prop -> Prop",
        "Not(phi) := phi -> False",
        "logic",
    ),
    DefinitionEntry(
        "Equals",
        ("=", "等しい", "equal"),
        "logical_relation",
        "T x T -> Prop",
        "Equals(a,b) := a = b with both sides sharing a type",
        "logic",
    ),
    DefinitionEntry(
        "Member",
        ("属する", "含まれる", "∈", " in "),
        "logical_relation",
        "T x Set(T) -> Prop",
        "Member(x,S) := S(x)",
        "logic",
    ),
    DefinitionEntry(
        "SetComprehension",
        ("集合", "全体", "set", "such that"),
        "term_constructor",
        "Variable(T) x Prop -> Set(T)",
        "SetOf(x:T | phi) := lambda x, phi",
        "set_theory",
    ),
    DefinitionEntry(
        "Equation",
        ("方程式", "equation"),
        "definition",
        "Term(T) x Term(T) -> Prop",
        "Equation(lhs,rhs) := Equals(lhs,rhs)",
        "equational_logic",
    ),
    DefinitionEntry(
        "RootSet",
        ("実根", "根", "解集合", "solution set", "roots"),
        "term_constructor",
        "Equation x Sort -> Set(T)",
        "RootSet(eq,T) := {x:T | eq(x)}",
        "real_closed_fields",
    ),
    DefinitionEntry(
        "Distinct",
        ("相異なる", "互いに異なる", "distinct"),
        "logical_relation",
        "Set(T) -> Prop",
        "Distinct(S) := forall x,y in S, x != y when their indices differ",
        "logic",
    ),
    DefinitionEntry(
        "Cardinality",
        ("個数", "濃度", "cardinality"),
        "definition",
        "FiniteSet(T) -> Natural",
        "Cardinality(S) := the number of elements of finite set S",
        "finite_set_theory",
    ),
    DefinitionEntry(
        "Map",
        ("写像", "対応させる", "対応させ", "対応する", "map"),
        "term_constructor",
        "T x Function(T,U) -> U",
        "Map(f,x) := f(x)",
        "function_theory",
    ),
    DefinitionEntry(
        "Image",
        ("像", "image"),
        "term_constructor",
        "Function(T,U) x Set(T) -> Set(U)",
        "Image(f,S) := {f(x) | x in S}",
        "set_theory",
    ),
    DefinitionEntry(
        "ConvexHull",
        ("凸包", "convex hull"),
        "term_constructor",
        "Set(Point2) -> Region2",
        "ConvexHull(S) := the least convex region containing S",
        "linear_real_arithmetic",
    ),
    DefinitionEntry(
        "Derivative",
        ("導関数", "微分", "derivative"),
        "definition",
        "Function(Real,Real) -> Function(Real,Real)",
        "Derivative(f)(x) := limit(h->0, (f(x+h)-f(x))/h)",
        "differential_algebra",
    ),
    DefinitionEntry(
        "Integral",
        ("積分", "定積分", "integral"),
        "definition",
        "Function(Real,Real) x Interval -> Real",
        "Integral(f,[a,b]) := the signed measure limit of integrable simple approximations",
        "real_analysis",
    ),
    DefinitionEntry(
        "FiniteSum",
        ("総和", "\\sum", "sum"),
        "definition",
        "FiniteSet(T) x Function(T,A) -> A",
        "FiniteSum(S,f) := fold(Add, 0, Image(f,S))",
        "algebra",
    ),
    DefinitionEntry(
        "FiniteProduct",
        ("総積", "\\prod", "すべて掛け", "product"),
        "definition",
        "FiniteSet(T) x Function(T,A) -> A",
        "FiniteProduct(S,f) := fold(Multiply, 1, Image(f,S))",
        "algebra",
    ),
    DefinitionEntry(
        "Variance",
        ("分散", "variance"),
        "definition",
        "ProbabilitySpace x RandomVariable -> Real",
        "Variance(P,X) := Expectation(P,(X-Expectation(P,X))^2)",
        "probability",
    ),
    DefinitionEntry(
        "Exists",
        ("存在する", "少なくとも一つ", "exists", "there exists"),
        "logical_form",
        "(T -> Prop) -> Prop",
        "exists x:T, phi(x)",
        "logic",
    ),
    DefinitionEntry(
        "Satisfies",
        ("満たす", "satisfy"),
        "logical_form",
        "Object x Prop -> Prop",
        "Satisfies(x, phi) := phi(x)",
        "logic",
    ),
    DefinitionEntry(
        "Find",
        ("求めよ", "求める", "表せ", "find", "compute"),
        "query",
        "Term(T) -> Query(T)",
        "Find(target) asks for a witness, value, or exact characterization",
        "query_compiler",
    ),
    DefinitionEntry(
        "Decide",
        ("判定", "存在するか", "可能か", "なり得るか", "whether", "decide"),
        "query",
        "Prop -> Query(Bool)",
        "Decide(phi) asks whether phi is true, false, or conditionally true under assumptions",
        "query_compiler",
    ),
    DefinitionEntry(
        "Prove",
        ("示せ", "証明", "prove", "show that"),
        "query",
        "Prop -> Query(Proof)",
        "Prove(phi) asks for a proof object whose kernel checks phi",
        "proof_assistant",
    ),
)


def compile_typed_definition_ir(text: str) -> TypedDefinitionIR:
    structure = analyze_structure(text)
    case_frame_ir = parse_case_frames(text)
    definitions = definitions_for_structure(structure)
    declarations = infer_typed_declarations(structure, definitions)
    terms = infer_terms(structure, definitions)
    predicates = infer_predicates(structure, definitions, case_frame_ir.to_dict())
    query = infer_typed_query(structure, definitions, predicates, case_frame_ir.to_dict())
    logic = build_logic(structure, declarations, predicates, query)
    backend_obligations = infer_backend_obligations(definitions, query, logic)
    warnings = infer_warnings(structure, definitions, query)
    status = "type_checked" if not warnings else "needs_review"
    return TypedDefinitionIR(
        source_text=text,
        normalized_text=structure.normalized_text,
        status=status,
        sorts=[asdict(item) for item in CORE_SORTS],
        definitions_used=[item.to_dict() for item in definitions],
        declarations=declarations,
        terms=terms,
        predicates=predicates,
        query=query,
        logic=logic,
        backend_obligations=backend_obligations,
        case_frames=case_frame_ir.to_dict(),
        warnings=warnings,
    )


def definitions_for_structure(structure: StructuralIR) -> list[DefinitionEntry]:
    normalized = structure.normalized_text.lower()
    used: list[DefinitionEntry] = []
    for entry in LEXICON:
        if any(surface.lower() in normalized for surface in entry.surfaces):
            used.append(entry)

    entity_kinds = {entity.kind for entity in structure.entities}
    operation_kinds = {operation.kind for operation in structure.operations}
    quantity_set = set(structure.quantities)
    canonical_needed: set[str] = set()
    if entity_kinds & {"curve", "function"} or any(relation.startswith("y=") for relation in structure.relations):
        canonical_needed.add("Curve2")
    if entity_kinds & {"triangle", "equilateral_triangle", "square"}:
        canonical_needed.update({"Point2", "FiniteShape", "Polygon"})
    if "equilateral_triangle" in entity_kinds or "正" in structure.normalized_text and "角形" in structure.normalized_text:
        canonical_needed.add("RegularPolygon")
    if "重心" in structure.normalized_text:
        canonical_needed.add("Centroid")
    if "locus" in operation_kinds:
        canonical_needed.add("Locus")
    if "area" in quantity_set or "measure" in operation_kinds:
        canonical_needed.update({"Region2", "Area"})
    if "prove" in operation_kinds:
        canonical_needed.add("Prove")
    query_operation_kinds = {
        "compute_or_solve",
        "solve_all",
        "query_count",
        "query_measure",
        "query_select",
        "query_classify",
        "query_compute",
        "factor",
        "simplify",
        "expand",
    }
    if operation_kinds & query_operation_kinds or "表せ" in structure.normalized_text:
        canonical_needed.add("Find")
    if any(item.kind in {"integer", "positive_integer", "nonnegative_integer"} for item in structure.constraints):
        canonical_needed.add("Integer")
    if contains_any(structure.normalized_text, ("自然数", "正の整数")):
        canonical_needed.add("Natural")
    if any(item.kind == "prime" for item in structure.constraints) or "素数" in structure.normalized_text:
        canonical_needed.add("Prime")
    if contains_any(structure.normalized_text, ("割り切", "約数", "因数")):
        canonical_needed.add("Divides")
    if contains_any(structure.normalized_text, ("最大公約数", "gcd")):
        canonical_needed.add("GCD")
    if contains_any(structure.normalized_text, ("最小公倍数", "lcm")):
        canonical_needed.add("LCM")
    if "階乗" in structure.normalized_text or re.search(
        r"(?:[A-Za-z0-9_)])\s*!(?!=)",
        structure.normalized_text,
    ):
        canonical_needed.add("Factorial")
    if contains_any(structure.normalized_text, ("最大値", "最大化")):
        canonical_needed.update({"Maximum", "Find"})
    if contains_any(structure.normalized_text, ("最小値", "最小化")):
        canonical_needed.update({"Minimum", "Find"})
    if is_decision_question(structure.normalized_text):
        canonical_needed.add("Decide")
    if "probability" in quantity_set:
        canonical_needed.add("ProbabilitySpace")
    if "expectation" in operation_kinds or "expectation" in quantity_set:
        canonical_needed.add("Expectation")
    if contains_any(
        structure.normalized_text,
        ("相関係数", "共分散", "相関関数", "自己相関"),
    ):
        canonical_needed.update(
            {
                "ProbabilitySpace",
                "Expectation",
                "Center",
                "Covariance",
                "InnerProduct",
                "Norm",
                "NormalizedInnerProduct",
            }
        )
    if contains_any(
        structure.normalized_text,
        ("内積", "フロベニウス", "正規化内積"),
    ):
        canonical_needed.update({"InnerProduct", "Norm"})
    if contains_any(structure.normalized_text, ("フロベニウス内積", "Frobenius")):
        canonical_needed.add("FrobeniusInnerProduct")
    if contains_any(structure.normalized_text, ("二次形式", "正定値")):
        canonical_needed.update(
            {"QuadraticForm", "PositiveDefinite", "InnerProduct"}
        )
    if contains_any(structure.normalized_text, ("直交射影", "射影")):
        canonical_needed.update({"Projection", "InnerProduct", "Norm"})
    if contains_any(structure.normalized_text, ("すべて", "任意")):
        canonical_needed.add("Forall")
    if contains_any(structure.normalized_text, ("存在", "少なくとも一つ")):
        canonical_needed.add("Exists")
    if contains_any(structure.normalized_text, ("かつ", "および", "∧")):
        canonical_needed.add("And")
    if contains_any(structure.normalized_text, ("または", "∨")):
        canonical_needed.add("Or")
    if contains_any(structure.normalized_text, ("ならば", "なら", "→")):
        canonical_needed.add("Implies")
    if contains_any(structure.normalized_text, ("でない", "ではない", "¬")):
        canonical_needed.add("Not")
    if structure.relations:
        canonical_needed.add("Equals")
    if contains_any(structure.normalized_text, ("属する", "含まれる", " in ", "∈")):
        canonical_needed.add("Member")
    if contains_any(structure.normalized_text, ("集合", "全体")) or operation_kinds & {"locus", "passing_region"}:
        canonical_needed.add("SetComprehension")
    if "満たす" in structure.normalized_text:
        canonical_needed.add("Satisfies")

    by_name = {entry.canonical: entry for entry in LEXICON}
    for name in canonical_needed:
        if name in by_name and by_name[name] not in used:
            used.append(by_name[name])
    return sorted(unique_entries(used), key=lambda item: item.canonical)


def infer_typed_declarations(structure: StructuralIR, definitions: list[DefinitionEntry]) -> list[dict[str, str]]:
    declarations: list[dict[str, str]] = []
    curve_expr = extract_curve_expression(structure)
    polygon_n = infer_polygon_arity(structure.normalized_text)
    function_symbols = infer_function_symbols(structure.source_text, set(structure.variables))
    complex_symbols = infer_complex_symbols(structure.source_text, set(structure.variables))
    if curve_expr:
        declarations.append({"name": "C", "type": "Curve2"})
    if polygon_n is not None:
        declarations.append({"name": "P", "type": f"Fin({polygon_n}) -> Point2"})
    if "Centroid" in {item.canonical for item in definitions} or "Locus" in {item.canonical for item in definitions}:
        declarations.append({"name": "G", "type": "Point2"})
    if "Area" in {item.canonical for item in definitions}:
        declarations.append({"name": "A", "type": "Real"})
    for variable in structure.variables:
        if variable in {item["name"] for item in declarations}:
            continue
        var_type = "Real"
        if variable in function_symbols:
            var_type = "Function(Real, Real)"
        elif variable in complex_symbols:
            var_type = complex_symbols[variable]
        elif any(variable in constraint.variables and constraint.kind in {"integer", "positive_integer", "nonnegative_integer"} for constraint in structure.constraints):
            var_type = "Integer"
        declarations.append({"name": variable, "type": var_type})
    return declarations


KNOWN_FUNCTION_NAMES = {
    "sin", "cos", "tan", "cot", "sec", "csc", "log", "ln", "exp", "sqrt",
    "arg", "max", "min", "lim", "det", "gcd", "lcm", "Re", "Im",
}


def infer_function_symbols(source_text: str, variables: set[str]) -> set[str]:
    """Infer first-class functions from application syntax, independently of phrasing."""
    symbols: set[str] = set()
    pattern = re.compile(r"(?<![\\A-Za-z0-9_])([A-Za-z][A-Za-z0-9_]*)\s*(?:\\left\s*)?\(")
    for match in pattern.finditer(source_text):
        symbol = match.group(1)
        if symbol in variables and symbol not in KNOWN_FUNCTION_NAMES:
            symbols.add(symbol)
    return symbols


def infer_complex_symbols(source_text: str, variables: set[str]) -> dict[str, str]:
    """Type definitions containing the imaginary unit in an explicit complex context."""
    if not any(marker in source_text.lower() for marker in ("複素数", "複素平面", "complex")):
        return {}

    inferred: dict[str, str] = {}
    assignment = re.compile(
        r"(?P<lhs>[A-Za-z](?:_\{?[A-Za-z0-9]+\}?)?)\s*=\s*(?P<rhs>[^$\\\r\n]+)"
    )
    imaginary_unit = re.compile(r"(?<![A-Za-z])i(?![A-Za-z])")
    for match in assignment.finditer(source_text):
        if not imaginary_unit.search(match.group("rhs")):
            continue
        symbol = match.group("lhs").replace("{", "").replace("}", "")
        if symbol not in variables:
            continue
        inferred[symbol] = "Sequence(Complex)" if "_" in symbol else "Complex"
    return inferred


def infer_terms(structure: StructuralIR, definitions: list[DefinitionEntry]) -> list[dict[str, Any]]:
    terms: list[dict[str, Any]] = []
    curve_expr = extract_curve_expression(structure)
    if curve_expr:
        terms.append(
            {
                "name": "C",
                "type": "Curve2",
                "constructor": "Graph",
                "arguments": [{"name": "x", "type": "Real"}, curve_expr],
            }
        )
    polygon_n = infer_polygon_arity(structure.normalized_text)
    if polygon_n is not None:
        constructor = "RegularPolygon" if "RegularPolygon" in {item.canonical for item in definitions} else "Polygon"
        terms.append(
            {
                "name": "P",
                "type": f"Fin({polygon_n}) -> Point2",
                "constructor": constructor,
                "arity": polygon_n,
            }
        )
    if "Centroid" in {item.canonical for item in definitions} and polygon_n is not None:
        terms.append(
            {
                "name": "G",
                "type": "Point2",
                "constructor": "Centroid",
                "arguments": [polygon_n, "P"],
            }
        )
    return terms


def infer_predicates(
    structure: StructuralIR,
    definitions: list[DefinitionEntry],
    case_frames: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    predicates: list[dict[str, Any]] = []
    canonical = {item.canonical for item in definitions}
    curve_expr = extract_curve_expression(structure)
    polygon_n = infer_polygon_arity(structure.normalized_text)
    if curve_expr:
        predicates.append(
            {
                "kind": "definition",
                "formula": f"C = Graph(lambda x: {curve_expr})",
                "uses": ["Curve2"],
            }
        )
    if polygon_n is not None and "EdgeLength" in canonical and "Prime" in canonical:
        normalized = structure.normalized_text.replace(" ", "")
        if ("三辺" in normalized or "辺の長さ" in normalized) and "素数" in normalized:
            predicates.append(
                {
                    "kind": "constraint",
                    "formula": f"forall i:Fin({polygon_n}), Prime(EdgeLength(P,i))",
                    "uses": ["Forall", "Prime", "EdgeLength"],
                }
            )
    if polygon_n is not None and {"Circumradius", "Inradius", "Prime"} <= canonical:
        normalized = structure.normalized_text.replace(" ", "")
        if "外接円半径と内接円半径の積" in normalized and "素数" in normalized:
            predicates.append(
                {
                    "kind": "constraint",
                    "formula": "Prime(Circumradius(P) * Inradius(P))",
                    "uses": ["Prime", "Circumradius", "Inradius"],
                }
            )
    if curve_expr and polygon_n is not None:
        predicates.append(
            {
                "kind": "constraint",
                "formula": f"forall i:Fin({polygon_n}), On(P(i), C)",
                "uses": ["Point2", "Curve2", "Forall"],
            }
        )
    if polygon_n is not None:
        polygon_name = "RegularPolygon" if "RegularPolygon" in canonical else "Polygon"
        predicates.append(
            {
                "kind": "constraint",
                "formula": f"{polygon_name}({polygon_n}, P)",
                "uses": [polygon_name],
            }
        )
    if "Centroid" in canonical and polygon_n is not None:
        predicates.append(
            {
                "kind": "constraint",
                "formula": f"G = Centroid({polygon_n}, P)",
                "uses": ["Centroid"],
            }
        )
    for relation in structure.relations:
        if curve_expr and relation.replace(" ", "") == f"y={curve_expr}".replace(" ", ""):
            continue
        predicates.append({"kind": "constraint", "formula": relation, "uses": ["Real"]})
    for frame in (case_frames or {}).get("frames", []):
        if frame.get("relation") in {"Query", "Prove"}:
            continue
        predicates.append(
            {
                "kind": "case_frame",
                "formula": frame.get("logic", ""),
                "uses": [frame.get("relation", "CaseFrame")],
            }
        )
    return predicates


def infer_typed_query(
    structure: StructuralIR,
    definitions: list[DefinitionEntry],
    predicates: list[dict[str, Any]],
    case_frames: dict[str, Any] | None = None,
) -> dict[str, Any]:
    canonical = {item.canonical for item in definitions}
    polygon_n = infer_polygon_arity(structure.normalized_text)
    if {"Area", "Locus", "Centroid"} <= canonical and polygon_n is not None:
        body = " and ".join(predicate["formula"] for predicate in predicates if predicate["kind"] == "constraint")
        return {
            "kind": "compute",
            "target": "A",
            "target_type": "Real",
            "expression": f"Area(BoundedRegion(Locus(G, exists P:Fin({polygon_n})->Point2, {body})))",
            "definition_driven": True,
        }
    if "Prove" in canonical:
        surface_goal = next(
            (
                frame.get("slots", {}).get("goal", "")
                for frame in (case_frames or {}).get("frames", [])
                if frame.get("relation") == "Prove"
            ),
            "",
        )
        typed_goal = typed_goal_from_surface(surface_goal, canonical, polygon_n)
        return {
            "kind": "prove",
            "target": "proposition",
            "target_type": "Proof",
            "expression": typed_goal,
            "surface_goal": surface_goal,
            "definition_driven": typed_goal != "UnknownProposition",
        }
    if "Decide" in canonical:
        return {"kind": "decide", "target": "proposition", "target_type": "Bool", "definition_driven": True}
    if "Limit" in canonical:
        return {
            "kind": "compute",
            "target": "limit",
            "target_type": "Real",
            "expression": "Limit(target)",
            "definition_driven": True,
        }
    if "Minimum" in canonical:
        return {"kind": "compute", "target": "minimum", "target_type": "Real", "definition_driven": True}
    if "Maximum" in canonical:
        return {"kind": "compute", "target": "maximum", "target_type": "Real", "definition_driven": True}
    if "CorrelationFunction" in canonical:
        return {
            "kind": "compute",
            "target": "correlation_function",
            "target_type": "Function",
            "expression": "CorrelationFunction(X,k)",
            "definition_driven": True,
        }
    if "Correlation" in canonical:
        return {
            "kind": "compute",
            "target": "correlation",
            "target_type": "Real",
            "expression": "Correlation(X,Y)",
            "definition_driven": True,
        }
    if "FrobeniusInnerProduct" in canonical:
        return {
            "kind": "compute",
            "target": "frobenius_inner_product",
            "target_type": "Real",
            "expression": "FrobeniusInnerProduct(A,B)",
            "definition_driven": True,
        }
    if "NormalizedInnerProduct" in canonical:
        return {
            "kind": "compute",
            "target": "normalized_inner_product",
            "target_type": "Real",
            "expression": "NormalizedInnerProduct(V,x,y)",
            "definition_driven": True,
        }
    if "Projection" in canonical:
        return {
            "kind": "compute",
            "target": "projection",
            "target_type": "Vector",
            "expression": "Projection(V,x,S)",
            "definition_driven": True,
        }
    if "InnerProduct" in canonical:
        return {
            "kind": "compute",
            "target": "inner_product",
            "target_type": "Real",
            "expression": "InnerProduct(V,x,y)",
            "definition_driven": True,
        }
    if "Expectation" in canonical:
        return {
            "kind": "compute",
            "target": "expectation",
            "target_type": "Real",
            "expression": "Expectation(P,X)",
            "definition_driven": True,
        }
    if "Volume" in canonical:
        return {
            "kind": "compute",
            "target": "volume",
            "target_type": "Real",
            "expression": "Volume(target_region)",
            "definition_driven": True,
        }
    if "Area" in canonical:
        return {
            "kind": "compute",
            "target": "area",
            "target_type": "Real",
            "expression": "Area(target_region)",
            "definition_driven": True,
        }
    if "Find" in canonical:
        if polygon_n is not None and contains_any(structure.normalized_text, ("全て求め", "すべて求め", "find all")):
            return {
                "kind": "enumerate",
                "target": "P",
                "target_type": f"Set(Fin({polygon_n})->Point2)",
                "expression": "{P | all constraints}",
                "definition_driven": True,
            }
        observation = next(
            (
                operation
                for operation in reversed(structure.operations)
                if operation.kind
                in {
                    "compute_or_solve",
                    "solve_all",
                    "query_count",
                    "query_measure",
                    "query_select",
                    "query_classify",
                    "query_compute",
                    "factor",
                    "simplify",
                    "expand",
                }
            ),
            None,
        )
        if observation is not None:
            query_kind = {
                "solve_all": "enumerate",
                "query_count": "count",
                "query_measure": "measure",
                "query_select": "select",
                "query_classify": "classify",
            }.get(observation.kind, "compute_or_characterize")
            return {
                "kind": query_kind,
                "target": observation.target or "requested_value",
                "target_type": observation.qualifiers.get("target_type", "Real"),
                "definition_driven": True,
            }
        return {
            "kind": "compute_or_characterize",
            "target": "requested_value",
            "target_type": "Real",
            "definition_driven": True,
        }
    return {"kind": "unknown", "target": "", "target_type": "Unknown", "definition_driven": False}


def typed_goal_from_surface(surface_goal: str, canonical: set[str], polygon_n: int | str | None) -> str:
    compact = surface_goal.replace(" ", "")
    if (
        polygon_n is not None
        and {"Circumradius", "Irrational"} <= canonical
        and "外接円半径" in compact
        and "無理数" in compact
    ):
        return "Irrational(Circumradius(P))"
    if surface_goal:
        escaped = surface_goal.replace('"', '\\"')
        return f'SurfaceProposition("{escaped}")'
    return "UnknownProposition"


def build_logic(
    structure: StructuralIR,
    declarations: list[dict[str, str]],
    predicates: list[dict[str, Any]],
    query: dict[str, Any],
) -> str:
    decl_text = " ".join(f"({item['name']} {item['type']})" for item in declarations)
    predicate_text = "\n    ".join(f"({predicate['formula']})" for predicate in predicates) or "True"
    target = query.get("expression") or query.get("target") or "Unknown"
    return (
        "(typed-problem\n"
        f"  (declare {decl_text})\n"
        "  (constraints\n"
        f"    {predicate_text}\n"
        "  )\n"
        f"  (query {query.get('kind')} {target})\n"
        ")"
    )


def infer_backend_obligations(
    definitions: list[DefinitionEntry],
    query: dict[str, Any],
    logic: str,
) -> list[dict[str, Any]]:
    theories = unique_preserve_order([entry.backend_theory for entry in definitions if entry.backend_theory != "query_compiler"])
    obligations: list[dict[str, Any]] = []
    for theory in theories:
        obligations.append(
            {
                "theory": theory,
                "status": "planned",
                "input": logic,
                "purpose": obligation_purpose(theory, query),
            }
        )
    return obligations


def infer_warnings(
    structure: StructuralIR,
    definitions: list[DefinitionEntry],
    query: dict[str, Any],
) -> list[str]:
    warnings: list[str] = []
    if query["kind"] == "unknown":
        warnings.append("TypedDefinitionKernel could not infer a query form.")
    if structure.entities and not definitions:
        warnings.append("Mathematical entities were detected but no definitions matched.")
    return warnings


def extract_curve_expression(structure: StructuralIR) -> str | None:
    for relation in structure.relations:
        compact = relation.replace(" ", "")
        if compact.startswith("y="):
            return compact.split("=", 1)[1]
    match = re.search(r"\by\s*=\s*([A-Za-z0-9_+\-*/^().]+)", structure.normalized_text)
    return match.group(1) if match else None


def infer_polygon_arity(text: str) -> int | str | None:
    normalized = text.replace(" ", "")
    explicit = (
        ("三角形", 3),
        ("四角形", 4),
        ("五角形", 5),
        ("六角形", 6),
        ("七角形", 7),
        ("八角形", 8),
        ("九角形", 9),
        ("十角形", 10),
        ("正方形", 4),
    )
    for marker, arity in explicit:
        if marker in normalized:
            return arity
    match = re.search(r"正?([A-Za-z]|n|\d+)角形", normalized)
    if match:
        raw = match.group(1)
        return int(raw) if raw.isdigit() else raw
    if "多角形" in normalized:
        return "n"
    return None


def is_decision_question(text: str) -> bool:
    compact = text.replace(" ", "").rstrip("。．.")
    return (
        compact.endswith("か")
        or "なり得るか" in compact
        or "素数か" in compact
        or "判定" in compact
    )


def obligation_purpose(theory: str, query: dict[str, Any]) -> str:
    if theory == "real_closed_fields":
        return "expand definitions to polynomial constraints and run quantifier elimination/CAD"
    if theory == "measure_theory":
        return "turn bounded locus or probability expression into a measure/integral obligation"
    if theory == "number_theory":
        return "expand divisibility/prime definitions and dispatch to integer arithmetic"
    if theory == "proof_assistant":
        return "check the final proposition or proof object in a small trusted kernel"
    if theory == "logic":
        return "normalize quantifiers and connectives"
    return f"handle {query.get('kind', 'query')} obligations for {theory}"


def contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def unique_entries(entries: list[DefinitionEntry]) -> list[DefinitionEntry]:
    seen = set()
    result = []
    for entry in entries:
        if entry.canonical in seen:
            continue
        seen.add(entry.canonical)
        result.append(entry)
    return result


def unique_preserve_order(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
