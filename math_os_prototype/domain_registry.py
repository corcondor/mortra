"""Domain registry and domain-level IR for broad math problem routing."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DomainSpec:
    name: str
    label_ja: str
    keywords: tuple[str, ...]
    tools: tuple[str, ...]
    methods: tuple[str, ...]
    verification: tuple[str, ...]
    retrieval_queries: tuple[str, ...]
    ir_schema: str


@dataclass
class DomainMatch:
    domain: str
    label_ja: str
    score: float
    confidence: float
    matched_features: list[str]


@dataclass
class DomainIR:
    domain: str
    label_ja: str
    confidence: float
    operation: str
    objects: list[str]
    symbols: list[str]
    target_tools: list[str]
    methods: list[str]
    verification: list[str]
    retrieval_queries: list[str]
    candidates: list[dict[str, Any]]
    status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DOMAIN_SPECS: tuple[DomainSpec, ...] = (
    DomainSpec(
        name="algebra",
        label_ja="代数",
        keywords=("solve", "equation", "factor", "polynomial", "方程式", "因数分解", "多項式", "連立"),
        tools=("SymPy", "Wolfram"),
        methods=("symbolic_solve", "factorization", "substitution_verification"),
        verification=("substitute_solution", "simplify_residual_zero"),
        retrieval_queries=("algebra equation solving factorization",),
        ir_schema="AlgebraIR(equations, variables, operation)",
    ),
    DomainSpec(
        name="linear_algebra",
        label_ja="線形代数",
        keywords=("matrix", "determinant", "eigenvalue", "rank", "linear transformation", "行列", "固有値", "固有ベクトル", "階数", "行列式", "線形変換"),
        tools=("SymPy", "Wolfram", "NumPy"),
        methods=("matrix_normal_form", "eigen_decomposition", "rank_or_determinant"),
        verification=("multiply_back", "check_characteristic_polynomial"),
        retrieval_queries=("linear algebra eigenvalue matrix rank determinant",),
        ir_schema="LinearAlgebraIR(matrices, vectors, operation)",
    ),
    DomainSpec(
        name="calculus",
        label_ja="微積分",
        keywords=("derivative", "differentiate", "integral", "limit", "series", "微分", "積分", "極限", "級数", "接線"),
        tools=("SymPy", "Wolfram"),
        methods=("differentiate_or_integrate", "limit_simplification", "series_expansion"),
        verification=("differentiate_antiderivative", "numeric_sample_check"),
        retrieval_queries=("calculus derivative integral limit symbolic computation",),
        ir_schema="CalculusIR(expression, variable, operation, point)",
    ),
    DomainSpec(
        name="real_analysis",
        label_ja="実解析",
        keywords=("sequence", "converge", "uniform", "continuity", "epsilon", "delta", "数列", "収束", "一様収束", "連続", "上限", "下限"),
        tools=("SymPy", "Wolfram", "Lean"),
        methods=("limit_argument", "epsilon_delta_plan", "counterexample_search"),
        verification=("sample_sequence_terms", "formalize_assumptions"),
        retrieval_queries=("real analysis sequence convergence epsilon delta proof",),
        ir_schema="AnalysisIR(objects, assumptions, target_claim)",
    ),
    DomainSpec(
        name="complex_analysis",
        label_ja="複素解析",
        keywords=("complex", "holomorphic", "analytic", "residue", "contour", "複素数", "複素関数", "正則", "解析的", "留数", "周回積分"),
        tools=("SymPy", "Wolfram", "Lean"),
        methods=("complex_simplification", "residue_theorem", "contour_strategy"),
        verification=("numeric_complex_sample", "check_singularity_conditions"),
        retrieval_queries=("complex analysis residue contour integral holomorphic",),
        ir_schema="ComplexAnalysisIR(functions, domain, singularities, operation)",
    ),
    DomainSpec(
        name="geometry",
        label_ja="幾何",
        keywords=(
            "triangle",
            "circle",
            "curve",
            "locus",
            "envelope",
            "region",
            "diagram",
            "parabola",
            "intersection",
            "三角形",
            "円",
            "曲線",
            "放物線",
            "軌跡",
            "包絡線",
            "通過領域",
            "交点",
            "回転",
            "角",
            "面積",
            "領域",
            "図形",
        ),
        tools=("SymPy", "Wolfram", "Shapely", "Lean"),
        methods=("coordinate_geometry", "parameter_elimination", "synthetic_to_algebraic_ir"),
        verification=("substitute_constraints", "numeric_geometry_sample"),
        retrieval_queries=("geometry locus envelope coordinate geometry elimination",),
        ir_schema="GeometryIR(points, curves, constraints, target)",
    ),
    DomainSpec(
        name="convex_geometry",
        label_ja="凸幾何",
        keywords=("minkowski", "convex", "support function", "halfspace", "polytope", "ミンコフスキー", "凸", "凸包", "支持関数", "半空間"),
        tools=("Shapely", "SymPy", "Wolfram", "Z3"),
        methods=("support_function", "convex_hull", "halfspace_intersection"),
        verification=("check_extreme_points", "sample_containment"),
        retrieval_queries=("convex geometry support function minkowski sum halfspace",),
        ir_schema="ConvexGeometryIR(vertices, halfspaces, operation)",
    ),
    DomainSpec(
        name="number_theory",
        label_ja="整数論",
        keywords=("prime", "mod", "congruence", "divisibility", "integer", "gcd", "素数", "合同式", "割り切れる", "整数", "最大公約数", "余り"),
        tools=("SymPy", "Z3", "Wolfram", "Lean"),
        methods=("modular_reduction", "case_split", "small_counterexample_search"),
        verification=("check_modular_cases", "bruteforce_small_bounds"),
        retrieval_queries=("number theory modular arithmetic divisibility prime",),
        ir_schema="NumberTheoryIR(variables, congruences, divisibility, bounds)",
    ),
    DomainSpec(
        name="combinatorics",
        label_ja="組合せ",
        keywords=("count", "permutation", "combination", "pigeonhole", "ways", "数え上げ", "何通り", "順列", "組合せ", "鳩の巣"),
        tools=("Python", "SymPy", "Z3"),
        methods=("case_enumeration", "generating_function", "recurrence"),
        verification=("bruteforce_small_cases", "check_recurrence"),
        retrieval_queries=("combinatorics counting permutations combinations recurrence",),
        ir_schema="CombinatoricsIR(objects, constraints, counting_target)",
    ),
    DomainSpec(
        name="graph_theory",
        label_ja="グラフ理論",
        keywords=("graph", "vertex", "edge", "path", "tree", "coloring", "グラフ", "頂点", "辺", "経路", "木", "彩色"),
        tools=("NetworkX", "Z3", "Python"),
        methods=("graph_model", "search_or_coloring", "invariant_check"),
        verification=("check_graph_constraints", "small_graph_exhaustion"),
        retrieval_queries=("graph theory vertex edge coloring path tree",),
        ir_schema="GraphTheoryIR(vertices, edges, constraints, target)",
    ),
    DomainSpec(
        name="probability",
        label_ja="確率",
        keywords=("probability", "random", "expected", "variance", "correlation", "distribution", "確率", "期待値", "分散", "相関", "相関係数", "確率変数", "分布", "ランダム"),
        tools=("SymPy", "Python", "Wolfram"),
        methods=("sample_space_model", "expectation_linearity", "distribution_transform"),
        verification=("probabilities_sum_to_one", "monte_carlo_sanity_check"),
        retrieval_queries=("probability expected value variance distribution problem",),
        ir_schema="ProbabilityIR(random_variables, sample_space, target)",
    ),
    DomainSpec(
        name="statistics",
        label_ja="統計",
        keywords=("statistics", "estimator", "likelihood", "regression", "confidence interval", "correlation", "統計", "推定量", "尤度", "回帰", "信頼区間", "標本", "相関", "相関係数"),
        tools=("Python", "SymPy", "Wolfram"),
        methods=("likelihood_derivation", "estimator_properties", "data_summary"),
        verification=("simulation_check", "dimension_and_assumption_check"),
        retrieval_queries=("statistics likelihood estimator regression confidence interval",),
        ir_schema="StatisticsIR(data, model, estimator, target)",
    ),
    DomainSpec(
        name="optimization",
        label_ja="最適化",
        keywords=("maximize", "minimize", "maximum", "minimum", "optimization", "constraint", "linear programming", "最大化", "最小化", "最大値", "最小値", "最大", "最小", "最適化", "制約", "ラグランジュ"),
        tools=("SymPy", "Wolfram", "Z3", "SciPy"),
        methods=("critical_points", "lagrange_multiplier", "convex_relaxation"),
        verification=("check_constraints", "compare_boundary_candidates"),
        retrieval_queries=("optimization constraints lagrange multiplier maximum minimum",),
        ir_schema="OptimizationIR(objective, constraints, variables, domain)",
    ),
    DomainSpec(
        name="differential_equations",
        label_ja="微分方程式",
        keywords=("differential equation", "ode", "pde", "dy/dx", "initial condition", "微分方程式", "常微分", "偏微分", "初期条件"),
        tools=("SymPy", "Wolfram", "SciPy"),
        methods=("ode_classification", "dsolve", "numeric_solution_check"),
        verification=("substitute_solution_into_equation", "check_initial_conditions"),
        retrieval_queries=("differential equation ODE initial condition dsolve",),
        ir_schema="DifferentialEquationIR(equations, functions, conditions)",
    ),
    DomainSpec(
        name="inequalities",
        label_ja="不等式",
        keywords=("inequality", "nonnegative", "不等式", "非負", "相加相乗", "大小関係"),
        tools=("SymPy", "Z3", "Wolfram", "Lean"),
        methods=("normalization", "sum_of_squares_attempt", "boundary_search"),
        verification=("random_sample_check", "symbolic_nonnegativity_check"),
        retrieval_queries=("inequality proof sum of squares AM GM",),
        ir_schema="InequalityIR(expressions, assumptions, target_relation)",
    ),
    DomainSpec(
        name="functional_equations",
        label_ja="関数方程式",
        keywords=("functional equation", "function f", "for all x", "関数方程式", "関数 f", "すべての", "任意の x"),
        tools=("SymPy", "Z3", "Lean"),
        methods=("substitution_patterns", "special_values", "candidate_function_search"),
        verification=("substitute_candidate", "check_domain_cases"),
        retrieval_queries=("functional equation substitution special values",),
        ir_schema="FunctionalEquationIR(functions, equations, domain, target)",
    ),
    DomainSpec(
        name="topology",
        label_ja="位相",
        keywords=("topology", "open set", "compact", "connected", "homeomorphism", "位相", "開集合", "コンパクト", "連結", "同相"),
        tools=("Lean", "retrieval"),
        methods=("definition_expansion", "counterexample_search", "formal_proof_plan"),
        verification=("check_definitions", "lean_formalization_target"),
        retrieval_queries=("topology compact connected open set homeomorphism proof",),
        ir_schema="TopologyIR(spaces, subsets, properties, target_claim)",
    ),
    DomainSpec(
        name="formal_proof",
        label_ja="形式証明",
        keywords=("lean", "mathlib", "proof assistant", "形式証明", "証明支援"),
        tools=("Lean", "retrieval"),
        methods=("statement_formalization", "library_search", "proof_repair_loop"),
        verification=("lean_kernel_check",),
        retrieval_queries=("Lean Mathlib theorem proof formalization",),
        ir_schema="FormalProofIR(assumptions, conclusion, theorem_stub)",
    ),
)


UNKNOWN_SPEC = DomainSpec(
    name="unknown",
    label_ja="未分類",
    keywords=(),
    tools=("retrieval", "simulation", "human_review"),
    methods=("classify_then_search", "construct_counterexamples", "ask_for_structure"),
    verification=("no_verified_solver_yet",),
    retrieval_queries=("mathematics problem solving strategy",),
    ir_schema="UnknownMathIR(raw_problem, candidate_domains)",
)


class DomainRegistry:
    def __init__(self, specs: tuple[DomainSpec, ...] = DOMAIN_SPECS):
        self.specs = {spec.name: spec for spec in specs}

    def analyze(self, problem_text: str, parsed_ir: dict[str, Any] | None = None) -> DomainIR:
        text = normalize_text(problem_text)
        matches = self.rank(problem_text, parsed_ir)
        top = matches[0] if matches else DomainMatch("unknown", UNKNOWN_SPEC.label_ja, 0.0, 0.15, [])
        spec = self.specs.get(top.domain, UNKNOWN_SPEC)
        operation = infer_operation(text, parsed_ir)
        status = "classified" if top.domain != "unknown" and top.confidence >= 0.35 else "needs_more_context"
        return DomainIR(
            domain=spec.name,
            label_ja=spec.label_ja,
            confidence=top.confidence,
            operation=operation,
            objects=infer_objects(text, parsed_ir),
            symbols=extract_symbols(text),
            target_tools=list(spec.tools),
            methods=list(spec.methods),
            verification=list(spec.verification),
            retrieval_queries=list(spec.retrieval_queries),
            candidates=[asdict(match) for match in matches[:5]],
            status=status,
        )

    def rank(self, problem_text: str, parsed_ir: dict[str, Any] | None = None) -> list[DomainMatch]:
        text = normalize_text(problem_text)
        intent = str((parsed_ir or {}).get("intent", "")).lower()
        route = str((parsed_ir or {}).get("route", "")).lower()
        matches: list[DomainMatch] = []
        for spec in self.specs.values():
            score, features = score_domain(text, intent, route, spec, parsed_ir)
            if score > 0:
                matches.append(
                    DomainMatch(
                        domain=spec.name,
                        label_ja=spec.label_ja,
                        score=score,
                        confidence=score_to_confidence(score),
                        matched_features=features,
                    )
                )
        if not matches:
            return [DomainMatch("unknown", UNKNOWN_SPEC.label_ja, 0.0, 0.15, [])]
        return sorted(matches, key=lambda item: item.score, reverse=True)


def score_domain(
    text: str,
    intent: str,
    route: str,
    spec: DomainSpec,
    parsed_ir: dict[str, Any] | None = None,
) -> tuple[float, list[str]]:
    score = 0.0
    features: list[str] = []
    parsed_givens = (parsed_ir or {}).get("givens", {})
    parser_has_structure = bool(parsed_givens)
    suppress_algebra_route = spec.name == "algebra" and has_specialized_non_algebra_features(text)
    for keyword in spec.keywords:
        if keyword.lower() in text:
            score += 1.0 + min(len(keyword), 16) / 32.0
            features.append(keyword)

    if spec.name == "functional_equations" and ("関数方程式" in text or "functional equation" in text):
        score += 2.5
        features.append("functional_equation_exact")

    route_map = {
        "symbolic_algebra": "algebra",
        "calculus": "calculus",
        "geometry_symbolic": "geometry",
        "convex_geometry": "convex_geometry",
        "formal_proof": "formal_proof",
        "vision_geometry": "geometry",
    }
    route_is_reliable = parser_has_structure or route not in {"symbolic_algebra"}
    if route_map.get(route) == spec.name and route_is_reliable and not suppress_algebra_route:
        score += 3.0
        features.append(f"route:{route}")

    intent_map = {
        "minkowski": "convex_geometry",
        "container": "convex_geometry",
        "geometry_dsl": "geometry",
        "geometry_nl_to_dsl": "geometry",
        "envelope": "geometry",
        "locus": "geometry",
        "region": "geometry",
        "cas_symbolic_algebra": "algebra",
        "calculus_symbolic": "calculus",
        "lean": "formal_proof",
    }
    for needle, domain in intent_map.items():
        if needle == "cas_symbolic_algebra" and (not parser_has_structure or suppress_algebra_route):
            continue
        if needle in intent and domain == spec.name:
            score += 4.0
            features.append(f"intent:{needle}")

    if spec.name == "inequalities" and re.search(r"(<=|>=|<|>|≤|≥)", text):
        score += 1.5
        features.append("relation")
    if spec.name == "algebra" and "=" in text and not suppress_algebra_route:
        score += 0.75
        features.append("equation")
    return score, features


def has_specialized_non_algebra_features(text: str) -> bool:
    specialized = (
        "素数",
        "整数",
        "割り切",
        "合同",
        " mod ",
        "確率",
        "期待値",
        "分散",
        "相関",
        "カード",
        "サイコロ",
        "何通り",
        "選ぶ",
        "グラフ",
        "頂点",
        "辺",
        "行列",
        "固有",
        "微分方程式",
        "関数方程式",
        "三角形",
        "円",
        "曲線",
        "放物線",
        "交点",
        "回転",
        "領域",
        "半径",
        "面積",
        "極限",
        " limit ",
        "収束",
        "不等式",
        "制約",
        "最大",
        "最小",
        "複素",
        "留数",
    )
    return any(item in text for item in specialized)


def infer_operation(text: str, parsed_ir: dict[str, Any] | None = None) -> str:
    intent = str((parsed_ir or {}).get("intent", "")).lower()
    operation_map = (
        ("minkowski", "minkowski_sum"),
        ("ミンコフスキー", "minkowski_sum"),
        ("container", "containment_sweep"),
        ("包絡線", "envelope"),
        ("envelope", "envelope"),
        ("通過領域", "passing_region"),
        ("通過する領域", "passing_region"),
        ("region", "passing_region"),
        ("軌跡", "locus"),
        ("locus", "locus"),
        ("\\lim", "limit"),
        ("極限", "limit"),
        ("limit", "limit"),
        ("微分", "differentiate"),
        ("derivative", "differentiate"),
        ("積分", "integrate"),
        ("integral", "integrate"),
        ("一般項", "closed_form"),
        ("相関係数", "correlation"),
        ("最大", "optimize"),
        ("最小", "optimize"),
        ("maximize", "optimize"),
        ("minimize", "optimize"),
        ("期待値", "expectation"),
        ("確率", "probability"),
        ("probability", "probability"),
        ("何個", "count"),
        ("個数", "count"),
        ("何通り", "count"),
        ("count", "count"),
        ("体積", "volume"),
        ("面積", "area"),
        ("存在", "existence"),
        ("示せ", "prove"),
        ("証明", "prove"),
        ("prove", "prove"),
        ("方程式", "solve_equation"),
        ("solve", "solve_equation"),
    )
    combined = f"{intent} {text}"
    for needle, operation in operation_map:
        if needle in combined:
            return operation
    return "classify_and_plan"


def infer_objects(text: str, parsed_ir: dict[str, Any] | None = None) -> list[str]:
    objects = []
    object_needles = (
        ("matrix", "matrix"),
        ("行列", "matrix"),
        ("triangle", "triangle"),
        ("三角形", "triangle"),
        ("circle", "circle"),
        ("円", "circle"),
        ("graph", "graph"),
        ("グラフ", "graph"),
        ("sequence", "sequence"),
        ("数列", "sequence"),
        ("function", "function"),
        ("関数", "function"),
        ("polynomial", "polynomial"),
        ("多項式", "polynomial"),
        ("prime", "prime"),
        ("素数", "prime"),
        ("random", "random_variable"),
        ("確率変数", "random_variable"),
        ("convex", "convex_set"),
        ("凸", "convex_set"),
    )
    for needle, obj in object_needles:
        if needle in text and obj not in objects:
            objects.append(obj)
    if parsed_ir:
        givens = parsed_ir.get("givens", {})
        if isinstance(givens, dict):
            if "geometry_problem" in givens and "geometry_problem" not in objects:
                objects.append("geometry_problem")
            if "container_problem" in givens and "container_problem" not in objects:
                objects.append("container_problem")
    return objects


def extract_symbols(text: str) -> list[str]:
    symbols = sorted(
        {
            token
            for token in re.findall(r"\b[a-zA-Z]\b", text)
            if token.lower() not in {"a", "i"}
        }
    )
    return symbols[:12]


def normalize_text(text: str) -> str:
    return (
        text.lower()
        .replace("\\sqrt", " sqrt")
        .replace("\\frac", " frac")
        .replace("\\in", " in ")
        .replace("\\mathbb", " mathbb ")
        .replace("{", " ")
        .replace("}", " ")
        .replace("$", " ")
        .replace("≤", "<=")
        .replace("≥", ">=")
    )


def score_to_confidence(score: float) -> float:
    if score <= 0:
        return 0.15
    return round(min(0.96, 0.25 + score / 10.0), 3)


def run_domain_benchmark(path: Path | None = None) -> dict[str, Any]:
    benchmark_path = path or Path(__file__).with_name("domain_benchmark.jsonl")
    registry = DomainRegistry()
    rows = []
    correct = 0
    for line in benchmark_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        result = registry.analyze(row["text"])
        ok = result.domain == row["expected_domain"]
        correct += int(ok)
        rows.append(
            {
                "text": row["text"],
                "expected_domain": row["expected_domain"],
                "predicted_domain": result.domain,
                "confidence": result.confidence,
                "ok": ok,
            }
        )
    total = len(rows)
    return {
        "total": total,
        "correct": correct,
        "accuracy": correct / total if total else 0.0,
        "rows": rows,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect Math OS domain classification.")
    parser.add_argument("problem", nargs="*", help="Problem text to classify.")
    parser.add_argument("--benchmark", action="store_true", help="Run the bundled domain benchmark.")
    parser.add_argument("--benchmark-file", type=Path, help="Run a custom JSONL benchmark.")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    if args.benchmark or args.benchmark_file:
        print(json.dumps(run_domain_benchmark(args.benchmark_file), ensure_ascii=False, indent=2))
        return 0
    text = " ".join(args.problem).strip()
    if not text:
        raise SystemExit("provide a problem or use --benchmark")
    result = DomainRegistry().analyze(text)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
