"""Category-flavored typed semantic graph for MathOS.

This is the layer above the quantity-specific semantic checker.  It does not
solve problems by itself.  Its job is to make every parsed problem expose the
same core shape:

    typed objects + morphisms + constraints + query

The implementation is deliberately conservative.  It records typed structure
that existing parsers already found, then runs a verifier gate that can reject
or downgrade answers whose semantic provenance is too weak.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

try:
    from math_os_prototype.quantity_reasoner import extract_quantities
    from math_os_prototype.prime_power_symmetry import compile_prime_power_symmetric_ir
    from math_os_prototype.structural_parser import analyze_structure
    from math_os_prototype.theory_atlas import LiftCertificate, build_lift_certificates
except ImportError:  # Allows local script use from the package directory.
    from quantity_reasoner import extract_quantities
    from prime_power_symmetry import compile_prime_power_symmetric_ir
    from structural_parser import analyze_structure
    from theory_atlas import LiftCertificate, build_lift_certificates


@dataclass(frozen=True)
class SemanticSort:
    name: str
    kind: str = "sort"
    parent: str | None = None
    theory: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SemanticObject:
    name: str
    sort: str
    role: str
    expression: str | None = None
    source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SemanticMorphism:
    name: str
    domain: list[str]
    codomain: str
    kind: str
    expression: str
    law: str | None = None
    source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Constraint:
    kind: str
    expression: str
    objects: list[str] = field(default_factory=list)
    morphisms: list[str] = field(default_factory=list)
    source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SemanticQuery:
    kind: str
    target: str
    sort: str | None
    expression: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ConstraintIR:
    status: str
    constraints: list[Constraint]
    query: SemanticQuery | None
    obligations: list[str]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "constraints": [item.to_dict() for item in self.constraints],
            "query": self.query.to_dict() if self.query else None,
            "obligations": self.obligations,
            "warnings": self.warnings,
        }


@dataclass(frozen=True)
class VerifierGateReport:
    status: str
    checks: list[str]
    obligations: list[str]
    warnings: list[str] = field(default_factory=list)
    rejection: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TypedSemanticGraph:
    source_text: str
    status: str
    sorts: list[SemanticSort]
    objects: list[SemanticObject]
    morphisms: list[SemanticMorphism]
    constraints: list[Constraint]
    queries: list[SemanticQuery]
    laws: list[str]
    lift_certificates: list[LiftCertificate] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_text": self.source_text,
            "status": self.status,
            "sorts": [item.to_dict() for item in self.sorts],
            "objects": [item.to_dict() for item in self.objects],
            "morphisms": [item.to_dict() for item in self.morphisms],
            "constraints": [item.to_dict() for item in self.constraints],
            "queries": [item.to_dict() for item in self.queries],
            "laws": self.laws,
            "lift_certificates": [item.to_dict() for item in self.lift_certificates],
            "warnings": self.warnings,
        }

    def constraint_ir(self) -> ConstraintIR:
        query = self.queries[0] if self.queries else None
        warnings = []
        if not self.constraints:
            warnings.append("no constraints compiled into semantic graph")
        if query is None:
            warnings.append("no query compiled into semantic graph")
        obligations = [
            "(objects are sorted)",
            "(morphisms preserve domain/codomain sorts)",
            "(constraints mention declared objects or formulas)",
        ]
        if query is not None:
            obligations.append(f"(query target has sort {query.sort or 'Unknown'})")
        return ConstraintIR(
            status="well_formed" if not warnings else "needs_review",
            constraints=self.constraints,
            query=query,
            obligations=obligations,
            warnings=warnings,
        )


def compile_typed_semantic_graph(
    text: str,
    *,
    structural_ir: dict[str, Any] | None = None,
    typed_definition_ir: dict[str, Any] | None = None,
    formal_ir: dict[str, Any] | None = None,
    arithmetic_problem: dict[str, Any] | None = None,
    symbolic_query_ir: dict[str, Any] | None = None,
    vector_query_ir: dict[str, Any] | None = None,
    matrix_query_ir: dict[str, Any] | None = None,
    discrete_query_ir: dict[str, Any] | None = None,
) -> TypedSemanticGraph:
    structure = structural_ir or analyze_structure(text).to_dict()
    semantic_text = str(structure.get("normalized_text") or text)
    typed = typed_definition_ir or {}
    formal = formal_ir or {}

    sort_map: dict[str, SemanticSort] = {}
    object_map: dict[str, SemanticObject] = {}
    morphisms: list[SemanticMorphism] = []
    constraints: list[Constraint] = []
    queries: list[SemanticQuery] = []
    warnings: list[str] = []

    add_core_sorts(sort_map)
    lift_typed_definition_ir(typed, sort_map, object_map, morphisms, constraints, queries)
    lift_structural_ir(structure, sort_map, object_map, constraints)
    lift_formal_ir(formal, constraints, queries)
    lift_quantity_chart(semantic_text, arithmetic_problem, sort_map, object_map, morphisms, constraints, queries)
    lift_symbolic_query_ir(symbolic_query_ir, sort_map, object_map, morphisms, constraints, queries)
    lift_vector_query_ir(vector_query_ir, sort_map, object_map, morphisms, constraints, queries)
    lift_matrix_query_ir(matrix_query_ir, sort_map, object_map, morphisms, constraints, queries)
    lift_discrete_query_ir(discrete_query_ir, sort_map, object_map, morphisms, constraints, queries)
    lift_math_morphism_library(text, sort_map, object_map, morphisms, constraints, queries)

    if not queries:
        inferred = infer_query_from_text(semantic_text, typed)
        if inferred:
            queries.append(inferred)

    deduped_morphisms = dedupe_morphisms(morphisms)
    deduped_constraints = dedupe_constraints(constraints)
    deduped_queries = dedupe_queries(queries)
    lift_certificates = build_lift_certificates(
        text,
        sort_map.values(),
        object_map.values(),
        deduped_morphisms,
        deduped_constraints,
        deduped_queries,
    )

    warnings.extend(find_graph_warnings(sort_map, object_map, deduped_morphisms, deduped_constraints, deduped_queries))
    status = "type_checked" if not warnings else "needs_review"
    return TypedSemanticGraph(
        source_text=text,
        status=status,
        sorts=sorted(sort_map.values(), key=lambda item: item.name),
        objects=sorted(object_map.values(), key=lambda item: item.name),
        morphisms=deduped_morphisms,
        constraints=deduped_constraints,
        queries=deduped_queries,
        laws=[
            "identity: every sort T has id_T : T -> T",
            "composition: if f:A->B and g:B->C then g∘f:A->C",
            "type_preservation: every compiled operation must preserve declared codomain",
            "query_answer: an accepted answer is a term inhabiting the query codomain",
        ],
        lift_certificates=lift_certificates,
        warnings=warnings,
    )


def add_core_sorts(sort_map: dict[str, SemanticSort]) -> None:
    for sort in (
        SemanticSort("Object", "universe"),
        SemanticSort("Prop", "primitive", theory="logic"),
        SemanticSort("Proof", "primitive", parent="Prop", theory="proof_assistant"),
        SemanticSort("Query", "primitive", theory="logic"),
        SemanticSort("State", "primitive", theory="transition_system"),
        SemanticSort("Event", "primitive", theory="transition_system"),
        SemanticSort("Number", "primitive", theory="arithmetic"),
        SemanticSort("Real", "primitive", parent="Number", theory="real_closed_fields"),
        SemanticSort("Complex", "primitive", parent="Number", theory="complex_algebra"),
        SemanticSort("Integer", "primitive", parent="Number", theory="integer_arithmetic"),
        SemanticSort("Natural", "subsort", parent="Integer", theory="integer_arithmetic"),
        SemanticSort("Bool", "primitive", theory="logic"),
        SemanticSort("Point2", "alias", parent="Object", theory="linear_real_arithmetic"),
        SemanticSort("Vector", "type_constructor", parent="Object", theory="linear_algebra"),
        SemanticSort("Matrix", "type_constructor", parent="Object", theory="linear_algebra"),
        SemanticSort("Vector2", "alias", parent="Object", theory="linear_real_arithmetic"),
        SemanticSort("Line2", "alias", parent="Object", theory="linear_real_arithmetic"),
        SemanticSort("Curve2", "alias", parent="Object", theory="real_closed_fields"),
        SemanticSort("Region1", "alias", parent="Object", theory="real_closed_fields"),
        SemanticSort("Region2", "alias", parent="Object", theory="measure_theory"),
        SemanticSort("Polynomial", "structure", parent="Function", theory="polynomial_ring"),
        SemanticSort("Expression", "structure", parent="Object", theory="symbolic_algebra"),
        SemanticSort("Set", "type_constructor", parent="Object", theory="set_theory"),
        SemanticSort("Interval", "structure", parent="Object", theory="order_topology"),
        SemanticSort("Probability", "measure", parent="Real", theory="probability"),
        SemanticSort("ProbabilitySpace", "structure", parent="Object", theory="probability"),
        SemanticSort("StochasticProcess", "structure", parent="Function", theory="probability"),
        SemanticSort("InnerProductSpace", "structure", parent="Object", theory="linear_algebra"),
        SemanticSort("Function", "type_constructor", parent="Object", theory="analysis"),
        SemanticSort("Measure", "morphism_family", theory="measure_theory"),
        SemanticSort("Sequence", "structure", parent="Function", theory="discrete_math"),
        SemanticSort("Index", "subsort", parent="Natural", theory="discrete_math"),
        SemanticSort("Angle", "quantity", parent="Real", theory="geometry"),
        SemanticSort("Percent", "quantity", parent="Real", theory="arithmetic"),
        SemanticSort("Currency", "quantity", parent="Real", theory="arithmetic"),
        SemanticSort("TimeOfDay", "structure", parent="Object", theory="time"),
        SemanticSort("Base", "subsort", parent="Integer", theory="number_theory"),
        SemanticSort("DigitString", "structure", parent="Object", theory="number_theory"),
        SemanticSort("Modulus", "subsort", parent="Natural", theory="number_theory"),
    ):
        sort_map.setdefault(sort.name, sort)


def lift_symbolic_query_ir(
    payload: dict[str, Any] | None,
    sort_map: dict[str, SemanticSort],
    object_map: dict[str, SemanticObject],
    morphisms: list[SemanticMorphism],
    constraints: list[Constraint],
    queries: list[SemanticQuery],
) -> None:
    if not payload:
        return
    target = str(payload.get("target") or "")
    operator = str(payload.get("query_operator") or "")
    output_sort = str(payload.get("output_sort") or "Unknown")
    if not target or not operator:
        return
    # The explicit Constraint + QueryOperator IR is authoritative. Earlier
    # lexical/formal guesses are retained elsewhere in the trace, but must not
    # compete as answer-producing queries.
    queries.clear()
    sort_map.setdefault(output_sort, SemanticSort(output_sort, parent="Object", theory="symbolic_algebra"))
    object_map.setdefault(
        "symbolic_target",
        SemanticObject(
            name="symbolic_target",
            sort="Expression",
            role="query_input",
            expression=target,
            source="symbolic_query_ir",
        ),
    )
    for expression in payload.get("constraints", []) or []:
        constraints.append(
            Constraint(
                kind="symbolic_relation",
                expression=str(expression),
                objects=["symbolic_target"],
                source="symbolic_query_ir.constraint",
            )
        )
    morphisms.append(
        SemanticMorphism(
            name=operator,
            domain=["Expression"],
            codomain=output_sort,
            kind="query_operator",
            expression=f"{operator}({target})",
            law="exact symbolic backend contract",
            source="symbolic_query_ir",
        )
    )
    queries.append(
        SemanticQuery(
            kind=operator,
            target="symbolic_target",
            sort=output_sort,
            expression=target,
        )
    )


def lift_discrete_query_ir(
    payload: dict[str, Any] | None,
    sort_map: dict[str, SemanticSort],
    object_map: dict[str, SemanticObject],
    morphisms: list[SemanticMorphism],
    constraints: list[Constraint],
    queries: list[SemanticQuery],
) -> None:
    """Lift finite-domain and congruence queries into the shared graph."""
    if not payload:
        return
    operator = str(payload.get("operator") or "")
    output_sort = str(payload.get("output_sort") or "Natural")
    domain = payload.get("domain") or {}
    if not operator or not isinstance(domain, dict):
        return
    queries.clear()
    sort_map.setdefault(output_sort, SemanticSort(output_sort, parent="Number", theory="discrete_math"))
    object_map["discrete_domain"] = SemanticObject(
        name="discrete_domain",
        sort="Set",
        role="finite_or_congruence_domain",
        expression=str(domain),
        source="discrete_constraint_query_ir",
    )
    for index, predicate in enumerate(payload.get("predicates") or []):
        constraints.append(
            Constraint(
                kind="finite_predicate",
                expression=str(predicate),
                objects=["discrete_domain"],
                source=f"discrete_constraint_query_ir.predicate[{index}]",
            )
        )
    morphisms.append(
        SemanticMorphism(
            name=operator,
            domain=["Set"],
            codomain=output_sort,
            kind="query_operator",
            expression=f"{operator}({domain})",
            law="finite enumeration or modular arithmetic with witness rechecking",
            source="discrete_constraint_query_ir",
        )
    )
    queries.append(
        SemanticQuery(
            kind=operator,
            target="discrete_domain",
            sort=output_sort,
            expression=str(payload.get("observation") or "cardinality"),
        )
    )


def lift_vector_query_ir(
    payload: dict[str, Any] | None,
    sort_map: dict[str, SemanticSort],
    object_map: dict[str, SemanticObject],
    morphisms: list[SemanticMorphism],
    constraints: list[Constraint],
    queries: list[SemanticQuery],
) -> None:
    """Lift an executable vector observation into the shared semantic graph."""
    if not payload:
        return
    operator = str(payload.get("operator") or "")
    output_sort = str(payload.get("output_sort") or "Vector")
    if not operator:
        return

    queries.clear()
    sort_map.setdefault(output_sort, SemanticSort(output_sort, parent="Object", theory="linear_algebra"))
    declared: list[str] = []
    for name, entries in sorted((payload.get("vectors") or {}).items()):
        object_name = f"vector_{name}"
        declared.append(object_name)
        object_map[object_name] = SemanticObject(
            name=object_name,
            sort="Vector",
            role="declared_vector",
            expression=str(entries),
            source="vector_query_ir",
        )

    parameters = payload.get("parameters") or {}
    if operator == "intersect_affine_subspaces":
        for side in ("left", "right"):
            if side not in parameters:
                continue
            object_name = f"affine_{side}"
            declared.append(object_name)
            object_map[object_name] = SemanticObject(
                name=object_name,
                sort="Set",
                role="affine_subspace",
                expression=str(parameters[side]),
                source="vector_query_ir",
            )
        constraints.append(
            Constraint(
                kind="vector_equality",
                expression="affine_left(parameter) = affine_right(parameter)",
                objects=declared,
                source="vector_query_ir.constraint",
            )
        )
    elif operator == "select_direction_vectors":
        constraints.append(
            Constraint(
                kind="direction_equivalence",
                expression=f"dy/dx = {parameters.get('slope')}",
                objects=declared,
                source="vector_query_ir.constraint",
            )
        )
    else:
        constraints.append(
            Constraint(
                kind="typed_vector_term",
                expression=str(payload.get("target") or ""),
                objects=declared,
                source="vector_query_ir.constraint",
            )
        )

    morphisms.append(
        SemanticMorphism(
            name=operator,
            domain=[object_map[name].sort for name in declared],
            codomain=output_sort,
            kind="query_operator",
            expression=str(payload.get("target") or parameters),
            law="exact linear-algebra backend contract with substitution verification",
            source="vector_query_ir",
        )
    )
    object_map["vector_observation"] = SemanticObject(
        name="vector_observation",
        sort=output_sort,
        role="query_output",
        expression=str(payload.get("target") or parameters),
        source="vector_query_ir",
    )
    queries.append(
        SemanticQuery(
            kind=operator,
            target="vector_observation",
            sort=output_sort,
            expression=str(payload.get("target") or parameters),
        )
    )


def lift_matrix_query_ir(
    payload: dict[str, Any] | None,
    sort_map: dict[str, SemanticSort],
    object_map: dict[str, SemanticObject],
    morphisms: list[SemanticMorphism],
    constraints: list[Constraint],
    queries: list[SemanticQuery],
) -> None:
    """Lift a typed matrix chart and its observation contract into the kernel."""
    if not payload:
        return
    operator = str(payload.get("query_operator") or "")
    target = str(payload.get("target") or "")
    output_sort = str(payload.get("output_sort") or "Object")
    chart = str(payload.get("chart") or "matrix_chart")
    representation = payload.get("representation") or {}
    if not operator or not target:
        return

    queries.clear()
    sort_map.setdefault(output_sort, SemanticSort(output_sort, parent="Object", theory="linear_algebra"))
    object_map["matrix_chart"] = SemanticObject(
        name="matrix_chart",
        sort="Matrix",
        role=chart,
        expression=str(representation),
        source="matrix_query_ir",
    )
    for name, expression in sorted((payload.get("source_objects") or {}).items()):
        constraints.append(
            Constraint(
                kind="matrix_chart_constraint",
                expression=f"{name} = {expression}",
                objects=["matrix_chart"],
                source="matrix_query_ir.constraint",
            )
        )
    morphisms.append(
        SemanticMorphism(
            name=operator,
            domain=["Matrix"],
            codomain=output_sort,
            kind="query_operator",
            expression=f"{operator}({chart})",
            law="typed matrix chart executor contract",
            source="matrix_query_ir",
        )
    )
    queries.append(
        SemanticQuery(
            kind=operator,
            target="matrix_chart",
            sort=output_sort,
            expression=target,
        )
    )


def lift_typed_definition_ir(
    typed: dict[str, Any],
    sort_map: dict[str, SemanticSort],
    object_map: dict[str, SemanticObject],
    morphisms: list[SemanticMorphism],
    constraints: list[Constraint],
    queries: list[SemanticQuery],
) -> None:
    for sort in typed.get("sorts", []) or []:
        name = str(sort.get("name") or "")
        if name:
            sort_map.setdefault(
                name,
                SemanticSort(
                    name=name,
                    kind=str(sort.get("kind") or "sort"),
                    theory=infer_theory_from_sort(name),
                ),
            )

    for declaration in typed.get("declarations", []) or []:
        name = str(declaration.get("name") or "")
        sort = str(declaration.get("type") or "Object")
        if name:
            object_map.setdefault(
                name,
                SemanticObject(name=name, sort=sort, role="declaration", source="typed_definition_ir"),
            )
            register_sort_expression(sort, sort_map)

    for term in typed.get("terms", []) or []:
        name = str(term.get("name") or term.get("constructor") or "")
        sort = str(term.get("type") or "Object")
        if name:
            object_map.setdefault(
                name,
                SemanticObject(
                    name=name,
                    sort=sort,
                    role="constructed_term",
                    expression=str(term.get("constructor") or term),
                    source="typed_definition_ir.term",
                ),
            )
            register_sort_expression(sort, sort_map)

    for definition in typed.get("definitions_used", []) or []:
        canonical = str(definition.get("canonical") or "")
        role = str(definition.get("role") or "definition")
        signature = str(definition.get("type_signature") or "")
        if not canonical or role == "sort":
            continue
        domain, codomain = parse_type_signature(signature)
        morphisms.append(
            SemanticMorphism(
                name=canonical,
                domain=domain,
                codomain=codomain,
                kind=role_to_morphism_kind(role),
                expression=str(definition.get("expansion") or canonical),
                law=str(definition.get("backend_theory") or ""),
                source="typed_definition_ir.definition",
            )
        )
        register_sort_expression(codomain, sort_map)
        for item in domain:
            register_sort_expression(item, sort_map)

    for predicate in typed.get("predicates", []) or []:
        formula = str(predicate.get("formula") or "")
        if formula:
            constraints.append(
                Constraint(
                    kind=str(predicate.get("kind") or "constraint"),
                    expression=formula,
                    source="typed_definition_ir.predicate",
                )
            )

    query = typed.get("query") or {}
    if query:
        kind = str(query.get("kind") or "compute")
        raw_target = str(query.get("target") or "")
        if kind == "unknown" and not raw_target:
            return
        target = raw_target or "answer"
        expression = str(query.get("expression") or query)
        queries.append(
            SemanticQuery(
                kind=kind,
                target=target,
                sort=str(query.get("type") or query.get("target_type") or infer_sort_from_query_target(target) or "Unknown"),
                expression=expression,
            )
        )


def lift_structural_ir(
    structure: dict[str, Any],
    sort_map: dict[str, SemanticSort],
    object_map: dict[str, SemanticObject],
    constraints: list[Constraint],
) -> None:
    for entity in structure.get("entities", []) or []:
        name = str(entity.get("text") or entity.get("kind") or "")
        if not name:
            continue
        sort = structural_kind_to_sort(str(entity.get("kind") or "Object"))
        sort_map.setdefault(sort, SemanticSort(sort, parent="Object"))
        object_map.setdefault(
            safe_name(name),
            SemanticObject(
                name=safe_name(name),
                sort=sort,
                role="mentioned_entity",
                expression=name,
                source="structural_ir.entity",
            ),
        )
    for relation in structure.get("relations", []) or []:
        constraints.append(Constraint(kind="structural_relation", expression=str(relation), source="structural_ir.relation"))
    for constraint in structure.get("constraints", []) or []:
        expression = str(constraint.get("expression") or constraint.get("text") or constraint)
        constraints.append(Constraint(kind=str(constraint.get("kind") or "constraint"), expression=expression, source="structural_ir.constraint"))


def lift_formal_ir(
    formal: dict[str, Any],
    constraints: list[Constraint],
    queries: list[SemanticQuery],
) -> None:
    goal = formal.get("goal")
    if goal:
        constraints.append(Constraint(kind="formal_goal", expression=str(goal), source="formal_ir.goal"))
    status = formal.get("status")
    if status:
        constraints.append(Constraint(kind="formal_status", expression=str(status), source="formal_ir.status"))
    for meta in formal.get("metas", []) or []:
        name = str(meta.get("name") or "")
        if name:
            queries.append(
                SemanticQuery(
                    kind="formal_meta",
                    target=name,
                    sort=str(meta.get("type") or "Unknown"),
                    expression=str(meta),
                )
            )


def lift_quantity_chart(
    text: str,
    arithmetic_problem: dict[str, Any] | None,
    sort_map: dict[str, SemanticSort],
    object_map: dict[str, SemanticObject],
    morphisms: list[SemanticMorphism],
    constraints: list[Constraint],
    queries: list[SemanticQuery],
) -> None:
    quantities = []
    metadata = (arithmetic_problem or {}).get("metadata") if arithmetic_problem else None
    quantities_are_typed = False
    if isinstance(metadata, dict):
        quantities = list(metadata.get("quantities") or [])
        quantities_are_typed = bool(quantities)
    if not quantities:
        if not quantity_chart_applicable(text):
            return
        try:
            quantities = [quantity.to_dict() for quantity in extract_quantities(text)]
        except Exception:
            quantities = []
    if quantities and not quantities_are_typed:
        quantities = [quantity for quantity in quantities if quantity_has_semantic_object(quantity)]
    if not quantities:
        return

    sort_map.setdefault("Quantity", SemanticSort("Quantity", "structure", parent="Object", theory="many_sorted_logic"))
    sort_map.setdefault("Observable", SemanticSort("Observable", "morphism_family", theory="many_sorted_logic"))
    for quantity in quantities:
        qid = str(quantity.get("id", len(object_map)))
        obj = normalize_object(str(quantity.get("obj") or quantity.get("unit") or "quantity"))
        owner = safe_name(str(quantity.get("owner") or "unknown_owner"))
        state = safe_name(str(quantity.get("time") or f"s{quantity.get('sentence_index', 0)}"))
        count_sort = f"Count[{obj}]" if obj else "Quantity"
        sort_map.setdefault(count_sort, SemanticSort(count_sort, "indexed_sort", parent="Quantity", theory="many_sorted_logic"))
        for name, sort, role in (
            (owner, "Object", "quantity_owner"),
            (state, "State", "quantity_state"),
            (f"{obj}_object", "Object", "quantity_object"),
        ):
            object_map.setdefault(name, SemanticObject(name=name, sort=sort, role=role, source="quantity_chart"))
        term_name = f"q{qid}"
        object_map.setdefault(
            term_name,
            SemanticObject(
                name=term_name,
                sort=count_sort,
                role=str(quantity.get("role") or "quantity"),
                expression=str(quantity.get("value") or quantity.get("surface") or ""),
                source=str(quantity.get("text") or "quantity_chart"),
            ),
        )
        morphism_name = f"observe_{obj or 'quantity'}"
        morphisms.append(
            SemanticMorphism(
                name=morphism_name,
                domain=["Object", "Object", "State"],
                codomain=count_sort,
                kind="observable",
                expression=f"observe({owner}, {obj}, {state})",
                law="observable(subject, object, state) = value",
                source="quantity_chart",
            )
        )
        constraints.append(
            Constraint(
                kind="observable_value",
                expression=f"{morphism_name}({owner}, {obj}_object, {state}) = {quantity.get('value') or quantity.get('surface')}",
                objects=[term_name, owner, state],
                morphisms=[morphism_name],
                source="quantity_chart",
            )
        )

    query_obj = query_object(text)
    if query_obj:
        target_sort = f"Count[{query_obj}]"
        sort_map.setdefault(target_sort, SemanticSort(target_sort, "indexed_sort", parent="Quantity", theory="many_sorted_logic"))
        queries.append(
            SemanticQuery(
                kind="compute_observable",
                target=f"answer_{query_obj}",
                sort=target_sort,
                expression=f"find observable(..., {query_obj}, final_state)",
            )
        )


def quantity_chart_applicable(text: str) -> bool:
    """Return whether text denotes measured state/events, not bare math syntax.

    Numeric literals alone are insufficient evidence for a Quantity chart.
    The gate requires lexical evidence for ownership, units, state transitions,
    rates, or finite-object counts.  This prevents TeX commands and variables
    from becoming spurious observables while preserving arithmetic word
    problems in English and Japanese.
    """

    normalized = f" {text.lower()} "
    markers = (
        " had ",
        " has ",
        " bought ",
        " brought ",
        " got ",
        " received ",
        " gave ",
        " sold ",
        " left ",
        " remaining ",
        " altogether ",
        " total ",
        " each ",
        " per ",
        " cost ",
        " dollars ",
        "個",
        "枚",
        "人",
        "円",
        "本",
        "台",
        "箱",
        "袋",
        "残り",
        "合わせて",
        "増え",
        "減り",
        "買",
        "売",
        "配",
        "引いた",
    )
    return any(marker in normalized for marker in markers)


def quantity_has_semantic_object(quantity: dict[str, Any]) -> bool:
    obj = str(quantity.get("obj") or quantity.get("unit") or "").strip().lower()
    if not obj or obj in {
        "quantity",
        "dollar",
        "frac",
        "dfrac",
        "displaystyle",
        "sqrt",
        "sin",
        "cos",
        "tan",
        "pi",
        "theta",
        "ldot",
        "cdot",
        "quad",
        "infty",
    }:
        return False
    if re.fullmatch(r"[a-z]", obj):
        return False
    if obj.startswith("\\"):
        return False
    return True


def lift_math_morphism_library(
    text: str,
    sort_map: dict[str, SemanticSort],
    object_map: dict[str, SemanticObject],
    morphisms: list[SemanticMorphism],
    constraints: list[Constraint],
    queries: list[SemanticQuery],
) -> None:
    """Lift surface-independent mathematical notions into graph morphisms.

    This function intentionally does not compute final answers.  It records the
    mathematical objects and arrows that a backend may later use.  That keeps
    curriculum discoveries from becoming direct surface-template solvers.
    """

    normalized = text.lower()
    lift_sequence_morphisms(normalized, object_map, morphisms, constraints, queries)
    lift_point_geometry_morphisms(normalized, object_map, morphisms, constraints, queries)
    lift_number_theory_morphisms(normalized, object_map, morphisms, constraints, queries)
    lift_prime_power_symmetric_primality(normalized, object_map, morphisms, constraints, queries)
    lift_measurement_morphisms(normalized, object_map, morphisms, constraints, queries)
    lift_state_event_morphisms(normalized, object_map, morphisms, constraints, queries)
    lift_probability_morphisms(normalized, object_map, morphisms, constraints, queries)
    lift_algebra_morphisms(normalized, object_map, morphisms, constraints, queries)
    lift_representation_change_morphisms(normalized, object_map, morphisms)
    lift_growth_morphisms(normalized, object_map, morphisms, constraints, queries)
    lift_combinatorics_morphisms(normalized, object_map, morphisms, constraints, queries)
    lift_function_morphisms(normalized, object_map, morphisms, constraints, queries)
    lift_vector_geometry_morphisms(normalized, object_map, morphisms, constraints, queries)
    lift_calculus_morphisms(normalized, object_map, morphisms, constraints, queries)


def lift_representation_change_morphisms(
    text: str,
    object_map: dict[str, SemanticObject],
    morphisms: list[SemanticMorphism],
) -> None:
    """Expose proof-level changes of representation as reusable typed arrows."""
    specs = [
        (
            "PolynomialTranslation",
            ("x=y-", "x = y -", "x=y+", "x = y +", "平行移動"),
            ["Polynomial", "Real"],
            "Polynomial",
            "coordinate_change",
            "p(x) -> p(y-h)",
            "translation is an automorphism of the polynomial ring",
        ),
        (
            "Differentiation",
            ("導関数", "微分", "'(x)", "'(y)", "' (x)", "' (y)"),
            ["Function"],
            "Function",
            "functorial_operator",
            "f -> D(f)",
            "D is linear and satisfies the Leibniz rule",
        ),
        (
            "MonotonicityTest",
            ("単調増加", "単調減少", "monotonic", "increasing", "decreasing"),
            ["Function", "Region1"],
            "Prop",
            "order_certificate",
            "Sign(D(f)) -> Monotone(f)",
            "a derivative with fixed sign certifies monotonicity on an interval",
        ),
        (
            "Discriminant",
            ("判別式", "discriminant"),
            ["Polynomial"],
            "Real",
            "invariant",
            "p -> discriminant(p)",
            "the discriminant is invariant under root permutation",
        ),
        (
            "CoefficientComparison",
            ("係数比較", "係数を比較", "comparing coefficients", "coefficient comparison"),
            ["Polynomial", "Polynomial"],
            "Prop",
            "extensionality",
            "p=q -> coefficients(p)=coefficients(q)",
            "polynomials are equal iff all corresponding coefficients are equal",
        ),
        (
            "ComplexConjugation",
            ("共役", "conjugate"),
            ["Complex"],
            "Complex",
            "involution",
            "z -> conjugate(z)",
            "conjugate(conjugate(z)) = z",
        ),
        (
            "CaseSplit",
            ("場合分け", "case 1", "case 2", "(i)", "(ii)"),
            ["Prop"],
            "Proof",
            "logical_eliminator",
            "P or not P -> proof by cases",
            "case branches must be exhaustive and each branch prove the goal",
        ),
    ]
    for name, markers, domain, codomain, kind, expression, law in specs:
        if not any(marker in text for marker in markers):
            continue
        morphisms.append(
            SemanticMorphism(
                name=name,
                domain=domain,
                codomain=codomain,
                kind=kind,
                expression=expression,
                law=law,
                source="math_morphism_library.representation_change",
            )
        )

    derived_specs = [
        (
            "UniformLatticePair",
            bool(
                re.search(r"\([a-z],[a-z]\).*?\\in.*?\\{1,2,\\ldots,[a-z]\\}\^2", text, re.DOTALL)
                or ("格子点" in text and "1,2,\\ldots" in text)
            ),
            ["Natural"],
            "Object",
            "finite_sampling",
            "n -> {(a,b) | 1<=a,b<=n}",
            "the finite coefficient grid carries the uniform counting measure",
        ),
        (
            "QuadraticDiscriminant",
            bool(
                ("判別式" in text or "discriminant" in text or "実数解" in text)
                and re.search(r"[a-z]\^2.*?[a-z].*?=", text, re.DOTALL)
            ),
            ["Polynomial"],
            "Real",
            "invariant",
            "p -> discriminant(p)",
            "a real quadratic has a real root iff its discriminant is nonnegative",
        ),
        (
            "LatticeRescaling",
            bool(
                "格子点" in text
                and len(re.findall(r"[a-z]\s*=\s*[a-z]\s*/\s*[a-z]", text)) >= 2
            ),
            ["Object"],
            "Point2",
            "coordinate_change",
            "(a,b) -> (a/n,b/n)",
            "uniform lattice rescaling sends normalized sums to Riemann sums",
        ),
        (
            "RegionLimit",
            "リーマン和" in text or "riemann sum" in text,
            ["Object"],
            "Region2",
            "limit_passage",
            "finite grids -> limiting region",
            "normalized lattice sums converge to integrals when the boundary has area zero",
        ),
        (
            "AreaObservation",
            bool(("領域" in text or "region" in text) and ("\\int" in text or "\\iint" in text)),
            ["Region2"],
            "Real",
            "measure",
            "D -> area(D)",
            "area is the integral of the indicator of the region",
        ),
        (
            "RootDifference",
            "二解の差" in text or "difference of the two roots" in text,
            ["Polynomial"],
            "Real",
            "root_observable",
            "p -> |alpha-beta|",
            "for a monic quadratic, the absolute root difference is the square root of the discriminant",
        ),
        (
            "RestrictedAverage",
            bool(
                ("平均" in text or "average" in text or re.search(r"\bm_[a-z0-9]+", text))
                and "\\sum" in text
            ),
            ["Object", "Function"],
            "Real",
            "finite_observable",
            "(S,f) -> sum_{x in S} f(x)/|S|",
            "restricted average is the normalized finite sum over the admissible set",
        ),
    ]
    for name, detected, domain, codomain, kind, expression, law in derived_specs:
        if not detected:
            continue
        morphisms.append(
            SemanticMorphism(
                name=name,
                domain=domain,
                codomain=codomain,
                kind=kind,
                expression=expression,
                law=law,
                source="math_morphism_library.representation_change",
            )
        )
        if name == "UniformLatticePair":
            object_map.setdefault(
                "coefficient_grid",
                SemanticObject("coefficient_grid", "Object", "finite_grid", source="math_morphism_library.representation_change"),
            )
        if name in {"QuadraticDiscriminant", "RootDifference"}:
            object_map.setdefault(
                "poly",
                SemanticObject("poly", "Polynomial", "quadratic_family", source="math_morphism_library.representation_change"),
            )
        if name in {"RegionLimit", "AreaObservation"}:
            object_map.setdefault(
                "D",
                SemanticObject("D", "Region2", "limiting_region", source="math_morphism_library.representation_change"),
            )

    if any(item.name in {"PolynomialTranslation", "Discriminant", "CoefficientComparison"} for item in morphisms):
        object_map.setdefault(
            "poly",
            SemanticObject("poly", "Polynomial", "representation_carrier", source="math_morphism_library.representation_change"),
        )


def lift_sequence_morphisms(
    text: str,
    object_map: dict[str, SemanticObject],
    morphisms: list[SemanticMorphism],
    constraints: list[Constraint],
    queries: list[SemanticQuery],
) -> None:
    if not any(marker in text for marker in ("arithmetic sequence", "arithmetic progression", "等差数列")):
        return
    object_map.setdefault("seq", SemanticObject("seq", "Sequence", "sequence", source="math_morphism_library"))
    morphisms.extend(
        [
            SemanticMorphism(
                name="ArithmeticProgression",
                domain=["Sequence"],
                codomain="Prop",
                kind="structure_predicate",
                expression="ArithmeticProgression(seq)",
                law="a(n+1)-a(n)=d",
                source="math_morphism_library.sequence",
            ),
            SemanticMorphism(
                name="CommonDifference",
                domain=["Sequence"],
                codomain="Real",
                kind="observable",
                expression="CommonDifference(seq)",
                law="d = a(n+1)-a(n)",
                source="math_morphism_library.sequence",
            ),
            SemanticMorphism(
                name="NthTerm",
                domain=["Sequence", "Index"],
                codomain="Real",
                kind="evaluation",
                expression="NthTerm(seq,n)",
                law="NthTerm(seq,n)=NthTerm(seq,1)+(n-1)*CommonDifference(seq)",
                source="math_morphism_library.sequence",
            ),
        ]
    )
    constraints.append(
        Constraint(
            kind="structure",
            expression="ArithmeticProgression(seq)",
            objects=["seq"],
            morphisms=["ArithmeticProgression"],
            source="math_morphism_library.sequence",
        )
    )
    first_second = re.search(
        r"first term (?:is|=)\s*(-?\d+).*?second term (?:is|=)\s*(-?\d+)",
        text,
    )
    if not first_second:
        listed_terms = re.search(r"arithmetic sequence\s+(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)", text)
        if listed_terms:
            first_second = listed_terms
    if first_second:
        constraints.extend(
            [
                Constraint(
                    kind="value",
                    expression=f"NthTerm(seq,1) = {first_second.group(1)}",
                    objects=["seq"],
                    morphisms=["NthTerm"],
                    source="math_morphism_library.sequence",
                ),
                Constraint(
                    kind="value",
                    expression=f"NthTerm(seq,2) = {first_second.group(2)}",
                    objects=["seq"],
                    morphisms=["NthTerm"],
                    source="math_morphism_library.sequence",
                ),
            ]
        )
    nth = re.search(r"(\d+)(?:st|nd|rd|th)\s+term", text)
    if nth:
        queries.append(
            SemanticQuery(
                kind="compute_term",
                target=f"NthTerm(seq,{nth.group(1)})",
                sort="Real",
                expression=f"Find NthTerm(seq,{nth.group(1)})",
            )
        )


def lift_point_geometry_morphisms(
    text: str,
    object_map: dict[str, SemanticObject],
    morphisms: list[SemanticMorphism],
    constraints: list[Constraint],
    queries: list[SemanticQuery],
) -> None:
    coordinate_matches = re.findall(r"\((-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)\)", text)
    if "distance" in text or "距離" in text:
        morphisms.append(
            SemanticMorphism(
                name="Distance",
                domain=["Point2", "Point2"],
                codomain="Real",
                kind="metric",
                expression="Distance(P,Q)",
                law="Distance((x1,y1),(x2,y2)) = sqrt((x1-x2)^2+(y1-y2)^2)",
                source="math_morphism_library.geometry",
            )
        )
        object_map.setdefault("O", SemanticObject("O", "Point2", "origin", expression="(0,0)", source="math_morphism_library.geometry"))
        if coordinate_matches:
            x, y = coordinate_matches[0]
            object_map.setdefault("P", SemanticObject("P", "Point2", "point", expression=f"({x},{y})", source="math_morphism_library.geometry"))
            constraints.append(
                Constraint(
                    kind="coordinate",
                    expression=f"P = ({x},{y})",
                    objects=["P"],
                    source="math_morphism_library.geometry",
                )
            )
        if "origin" in text or "原点" in text:
            queries.append(
                SemanticQuery(
                    kind="compute_metric",
                    target="Distance(O,P)",
                    sort="Real",
                    expression="Find Distance(O,P)",
                )
            )

    if "midpoint" in text or "中点" in text:
        morphisms.extend(
            [
                SemanticMorphism(
                    name="Midpoint",
                    domain=["Point2", "Point2"],
                    codomain="Point2",
                    kind="constructor",
                    expression="Midpoint(A,B)",
                    law="Midpoint((x1,y1),(x2,y2))=((x1+x2)/2,(y1+y2)/2)",
                    source="math_morphism_library.geometry",
                ),
                SemanticMorphism(
                    name="CoordinateSum",
                    domain=["Point2"],
                    codomain="Real",
                    kind="observable",
                    expression="CoordinateSum(P)",
                    law="CoordinateSum((x,y))=x+y",
                    source="math_morphism_library.geometry",
                ),
            ]
        )
        for index, name in enumerate(("A", "B")):
            if index < len(coordinate_matches):
                x, y = coordinate_matches[index]
                object_map.setdefault(name, SemanticObject(name, "Point2", "point", expression=f"({x},{y})", source="math_morphism_library.geometry"))
                constraints.append(
                    Constraint(
                        kind="coordinate",
                        expression=f"{name} = ({x},{y})",
                        objects=[name],
                        source="math_morphism_library.geometry",
                    )
                )
        if "sum of the coordinates" in text or "座標の和" in text:
            queries.append(
                SemanticQuery(
                    kind="compute_observable",
                    target="CoordinateSum(Midpoint(A,B))",
                    sort="Real",
                    expression="Find CoordinateSum(Midpoint(A,B))",
                )
            )
        else:
            queries.append(
                SemanticQuery(kind="construct", target="Midpoint(A,B)", sort="Point2", expression="Find Midpoint(A,B)")
            )


def lift_number_theory_morphisms(
    text: str,
    object_map: dict[str, SemanticObject],
    morphisms: list[SemanticMorphism],
    constraints: list[Constraint],
    queries: list[SemanticQuery],
) -> None:
    if any(marker in text for marker in ("mod", "modulo", "remainder", "剰余", "余り")):
        morphisms.extend(
            [
                SemanticMorphism(
                    name="ModResidue",
                    domain=["Integer", "Modulus"],
                    codomain="Integer",
                    kind="quotient_observable",
                    expression="ModResidue(a,m)",
                    law="0 <= r < m and a = q*m + r",
                    source="math_morphism_library.number_theory",
                ),
                SemanticMorphism(
                    name="PowerMod",
                    domain=["Integer", "Natural", "Modulus"],
                    codomain="Integer",
                    kind="iteration_then_quotient",
                    expression="PowerMod(a,n,m)",
                    law="PowerMod(a,n,m)=ModResidue(a^n,m)",
                    source="math_morphism_library.number_theory",
                ),
            ]
        )
        power = re.search(r"(-?\d+)\s*(?:\^|\*\*)\s*(\d+).*?(?:mod|modulo|remainder).*?(\d+)", text)
        if not power:
            power = re.search(
                r"remainder of\s+(-?\d+)\s*(?:\^|\*\*)\s*(\d+).*?divided by\s+(\d+)",
                text,
            )
        if power:
            base, exponent, modulus = power.group(1), power.group(2), power.group(3)
            object_map.setdefault("modulus", SemanticObject("modulus", "Modulus", "modulus", expression=modulus, source="math_morphism_library.number_theory"))
            constraints.append(
                Constraint(
                    kind="modular_expression",
                    expression=f"PowerMod({base},{exponent},{modulus})",
                    objects=["modulus"],
                    morphisms=["PowerMod"],
                    source="math_morphism_library.number_theory",
                )
            )
            queries.append(
                SemanticQuery(
                    kind="compute_residue",
                    target=f"PowerMod({base},{exponent},{modulus})",
                    sort="Integer",
                    expression="Find modular exponentiation residue",
                )
            )
        product = re.search(r"(-?\d+)\s*(?:\*|times|×|\\cdot)\s*(-?\d+).*?(?:mod|modulo).*?(\d+)", text)
        if product:
            queries.append(
                SemanticQuery(
                    kind="compute_residue",
                    target=f"ModResidue({product.group(1)}*{product.group(2)},{product.group(3)})",
                    sort="Integer",
                    expression="Find modular product residue",
                )
            )

    if "base" in text and "equation" in text:
        object_map.setdefault("base", SemanticObject("base", "Base", "unknown_base", source="math_morphism_library.number_theory"))
        morphisms.append(
            SemanticMorphism(
                name="BaseExpansion",
                domain=["DigitString", "Base"],
                codomain="Integer",
                kind="notation_semantics",
                expression="BaseExpansion(digits,b)",
                law="BaseExpansion(d_k...d_0,b)=sum_i d_i*b^i",
                source="math_morphism_library.number_theory",
            )
        )
        equation = re.search(r"equation\s+\$?([^$=]+?)=([^$.]+?)\$?\s+is valid", text)
        if not equation:
            equation = re.search(r"equation\s+(.+?)=([^?.]+?)\s+is valid", text)
        if equation:
            constraints.append(
                Constraint(
                    kind="base_equation_raw",
                    expression=f"BaseEquation({equation.group(1).strip()} = {equation.group(2).strip()})",
                    objects=["base"],
                    morphisms=["BaseExpansion"],
                    source="math_morphism_library.number_theory",
                )
            )
        constraints.append(
            Constraint(
                kind="base_equation",
                expression="Equality after BaseExpansion(_, base)",
                objects=["base"],
                morphisms=["BaseExpansion"],
                source="math_morphism_library.number_theory",
            )
        )
        queries.append(SemanticQuery(kind="compute_parameter", target="base", sort="Base", expression="Find base satisfying expanded equation"))


def lift_prime_power_symmetric_primality(
    text: str,
    object_map: dict[str, SemanticObject],
    morphisms: list[SemanticMorphism],
    constraints: list[Constraint],
    queries: list[SemanticQuery],
) -> None:
    ir = compile_prime_power_symmetric_ir(text)
    if ir is None:
        return

    source = "math_morphism_library.prime_power_symmetry"
    for variable in ir.prime_variables:
        object_map.setdefault(
            variable,
            SemanticObject(variable, "Integer", "prime_parameter", expression=variable, source=source),
        )
        constraints.append(
            Constraint(
                kind="prime_predicate",
                expression=f"Prime({variable})",
                objects=[variable],
                morphisms=["PrimePredicate"],
                source=source,
            )
        )

    a = ir.center_variable
    b = ir.positive_offset_variable
    c = ir.negative_offset_variable
    morphisms.extend(
        [
            SemanticMorphism(
                name="SelfPower",
                domain=["Integer"],
                codomain="Integer",
                kind="diagonal_power",
                expression="SelfPower(x)=x^x",
                law="SelfPower(x)=Power(x,x)",
                source=source,
            ),
            SemanticMorphism(
                name="SymmetricPrimePair",
                domain=["Integer", "Integer"],
                codomain="Prop",
                kind="paired_primality_predicate",
                expression="Prime(x+d) and Prime(x-d)",
                law="swap(d,-d) exchanges the two targets",
                source=source,
            ),
            SemanticMorphism(
                name="CongruenceSieve",
                domain=["Integer", "Modulus"],
                codomain="Bool",
                kind="certified_compositeness_filter",
                expression="CongruenceSieve(n,m)=(n mod m != 0)",
                law="n mod p = 0 and 1<p<n implies Composite(n)",
                source=source,
            ),
        ]
    )
    constraints.extend(
        [
            Constraint(
                kind="symmetric_prime_targets",
                expression=f"Prime({a}^{a}+{b}^{b}-{c}^{c}) and Prime({a}^{a}-{b}^{b}+{c}^{c})",
                objects=[a, b, c],
                morphisms=["SelfPower", "SymmetricPrimePair", "PrimePredicate"],
                source=source,
            ),
            Constraint(
                kind="necessary_condition_schema",
                expression="OddDistinctPrimes(a,b,c) and b<a and c<a",
                objects=[a, b, c],
                morphisms=["PrimePredicate"],
                source=source,
            ),
        ]
    )
    queries.append(
        SemanticQuery(
            kind="decide_existence",
            target="Existence(SymmetricPrimePair)",
            sort="Bool",
            expression="Decide whether a prime triple exists",
        )
    )


def lift_measurement_morphisms(
    text: str,
    object_map: dict[str, SemanticObject],
    morphisms: list[SemanticMorphism],
    constraints: list[Constraint],
    queries: list[SemanticQuery],
) -> None:
    has_tip = re.search(r"\btip(?:s|ped|ping)?\b", text) is not None
    asks_tip_percent = has_tip and (
        "percent tip" in text
        or "what percent" in text
        or "find the percent" in text
        or "compute the percent" in text
    )
    if asks_tip_percent or "percent" in text or "%" in text:
        morphisms.append(
            SemanticMorphism(
                name="PercentOf",
                domain=["Real", "Percent"],
                codomain="Real",
                kind="scalar_action",
                expression="PercentOf(amount,p)",
                law="PercentOf(x,p)=x*p/100",
                source="math_morphism_library.measurement",
            )
        )
    if asks_tip_percent:
        object_map.setdefault("bill", SemanticObject("bill", "Currency", "base_amount", source="math_morphism_library.measurement"))
        object_map.setdefault("paid", SemanticObject("paid", "Currency", "final_amount", source="math_morphism_library.measurement"))
        constraints.append(
            Constraint(
                kind="percent_state",
                expression="paid = bill + PercentOf(bill, tip_percent)",
                objects=["bill", "paid"],
                morphisms=["PercentOf"],
                source="math_morphism_library.measurement",
            )
        )
        queries.append(SemanticQuery(kind="compute_percent", target="tip_percent", sort="Percent", expression="Find tip_percent"))
    if "clock" in text and "angle" in text:
        object_map.setdefault("clock_time", SemanticObject("clock_time", "TimeOfDay", "time", source="math_morphism_library.measurement"))
        morphisms.append(
            SemanticMorphism(
                name="ClockAngle",
                domain=["TimeOfDay"],
                codomain="Angle",
                kind="observable",
                expression="ClockAngle(time)",
                law="ClockAngle(h:m)=minimal angle between hour and minute hands",
                source="math_morphism_library.measurement",
            )
        )
        queries.append(SemanticQuery(kind="compute_angle", target="ClockAngle(clock_time)", sort="Angle", expression="Find ClockAngle(clock_time)"))


def lift_state_event_morphisms(
    text: str,
    object_map: dict[str, SemanticObject],
    morphisms: list[SemanticMorphism],
    constraints: list[Constraint],
    queries: list[SemanticQuery],
) -> None:
    text = text.lower()
    if not re.search(r"\bhow many\b", text):
        return
    if re.search(r"\b(each|per|cost|price|dollar|dollars|cents|hour|hours|mile|miles|packs?|boxes?|share|split|times|percent|combined|equal number|twice|as many)\b|[%$]", text):
        return
    if re.search(r"\b(some|initially|originally|at first|at the beginning|started with)\b", text):
        return
    if re.search(r"\b(?:had|has|have)\s+\d+\s+\w+\s+and\s+\d+", text):
        return
    if re.search(r"\b(?:had|has|have)\s+\d+[^?.!]*(?:,\s*\d+|\band\s+\d+)", text):
        return
    if re.search(r"how many[^?.!]+and[^?.!]+(?:left|total|have)", text):
        return

    sentences = [item.strip() for item in re.split(r"[.!?]+", text) if item.strip()]
    facts: list[tuple[str, str, str, int]] = []
    last_owner: str | None = None
    last_object: str | None = None
    for sentence in sentences:
        for kind, owner, obj, quantity in parse_state_sentence(sentence, last_owner, last_object):
            facts.append((kind, owner, obj, quantity))
            last_owner = owner
            last_object = obj
        query = parse_state_query(sentence)
        if query:
            owner, obj = query
            if owner and owner not in {"he", "she", "they", "him", "her", "them", "it"}:
                last_owner = owner
            if obj:
                last_object = obj

    query = next((parse_state_query(sentence) for sentence in sentences if parse_state_query(sentence)), None)
    if not query or not facts:
        return
    query_owner, query_object = query
    owners = {owner for _kind, owner, _obj, _qty in facts}
    objects = {obj for _kind, _owner, obj, _qty in facts}
    if query_owner is None and len(owners) == 1:
        query_owner = next(iter(owners))
    if query_owner in {"he", "she", "they", "him", "her", "them", "it"} and len(owners) == 1:
        query_owner = next(iter(owners))
    if query_object is None and len(objects) == 1:
        query_object = next(iter(objects))
    if query_owner is None or query_object is None:
        return

    relevant = [fact for fact in facts if fact[1] == query_owner and compatible_object(fact[2], query_object)]
    if not relevant:
        return
    if sum(1 for kind, _owner, _obj, _qty in relevant if kind == "initial") != 1:
        return

    object_map.setdefault("state", SemanticObject("state", "State", "quantity_state", source="math_morphism_library.state_event"))
    morphisms.extend(
        [
            SemanticMorphism(
                name="StateObservation",
                domain=["State"],
                codomain="Real",
                kind="observable",
                expression="State(owner,object,time)",
                law="state observation is a typed quantity",
                source="math_morphism_library.state_event",
            ),
            SemanticMorphism(
                name="AdditiveStateTransition",
                domain=["State", "Event"],
                codomain="State",
                kind="transition",
                expression="State += delta(Event)",
                law="final = initial + sum signed deltas",
                source="math_morphism_library.state_event",
            ),
        ]
    )
    for kind, owner, obj, quantity in relevant:
        expression = (
            f"InitialState({owner},{query_object}) = {quantity}"
            if kind == "initial"
            else f"Delta({owner},{query_object}) = {quantity}"
        )
        constraints.append(
            Constraint(
                kind="state_event_quantity",
                expression=expression,
                objects=["state"],
                morphisms=["StateObservation", "AdditiveStateTransition"],
                source="math_morphism_library.state_event",
            )
        )
    queries.append(
        SemanticQuery(
            kind="compute_state",
            target=f"StateQuery({query_owner},{query_object},final)",
            sort="Real",
            expression="Find final owner/object state",
        )
    )


def parse_state_query(sentence: str) -> tuple[str | None, str | None] | None:
    if "how many" not in sentence:
        return None
    match = re.search(r"how many\s+([a-z]+)(?:\s+\w+){0,4}?\s+(?:does|do|did|would)\s+([a-z]+)\s+(?:have|has)", sentence)
    if match:
        return normalize_entity(match.group(2)), normalize_object(match.group(1))
    match = re.search(r"how many\s+(?:would|does|do|did)\s+([a-z]+)\s+(?:have|has)", sentence)
    if match:
        return normalize_entity(match.group(1)), None
    match = re.search(r"how many\s+([a-z]+).*?\b(?:left|remain|remaining|now|total)\b", sentence)
    if match:
        return None, normalize_object(match.group(1))
    return None


def parse_state_sentence(
    sentence: str,
    last_owner: str | None,
    last_object: str | None,
) -> list[tuple[str, str, str, int]]:
    facts: list[tuple[str, str, str, int]] = []
    initial = re.search(r"\b([a-z]+)\s+(?:had|has|have)\s+(\d+)\s+((?:[a-z]+\s+){0,2}[a-z]+)", sentence)
    if initial:
        owner = normalize_state_owner(initial.group(1), last_owner)
        obj = normalize_object_phrase(initial.group(3))
        if owner and obj:
            facts.append(("initial", owner, obj, int(initial.group(2))))
            last_owner = owner
            last_object = obj
    for gain in re.finditer(
        r"\b([a-z]+)\s+(?:got|gets|found|collected|bought|buys|added|received|put|raised|downloaded|downloads)\s+(?:another\s+)?(\d+)\s*((?:[a-z]+\s+){0,3}[a-z]+)?",
        sentence,
    ):
        obj = normalize_object_phrase(gain.group(3) or last_object or "")
        if not obj and last_object:
            obj = last_object
        owner = normalize_state_owner(gain.group(1), last_owner)
        if owner and obj:
            facts.append(("delta", owner, obj, int(gain.group(2))))
            last_owner = owner
            last_object = obj
    transfer_gain = re.search(r"\b[a-z]+\s+g(?:ave|ives)\s+(?:him|her|them|it)\s+(\d+)\s+more\s*((?:[a-z]+\s+){0,2}[a-z]+)?", sentence)
    if transfer_gain and last_owner:
        obj = normalize_object_phrase(transfer_gain.group(2) or last_object or "")
        if not obj and last_object:
            obj = last_object
        if obj:
            facts.append(("delta", last_owner, obj, int(transfer_gain.group(1))))
            last_object = obj
    named_transfer_gain = re.search(
        r"\b(?:[a-z]+\s+){0,2}g(?:ave|ives)\s+([a-z]+)\s+(?:another\s+)?(\d+)\s*((?:[a-z]+\s+){0,2}[a-z]+)?",
        sentence,
    )
    if named_transfer_gain:
        owner = normalize_state_owner(named_transfer_gain.group(1), last_owner)
        obj = normalize_object_phrase(named_transfer_gain.group(3) or last_object or "")
        if not obj and last_object:
            obj = last_object
        if owner and obj:
            facts.append(("delta", owner, obj, int(named_transfer_gain.group(2))))
            last_owner = owner
            last_object = obj
    buy_with_context = re.search(r"\bto\s+buy\s+(\d+)\s+(?:new\s+)?((?:[a-z]+\s+){0,2}[a-z]+)", sentence)
    if buy_with_context and last_owner:
        obj = normalize_object_phrase(buy_with_context.group(2) or last_object or "")
        if not obj and last_object:
            obj = last_object
        if obj:
            facts.append(("delta", last_owner, obj, int(buy_with_context.group(1))))
            last_object = obj
    for loss in re.finditer(
        r"\b([a-z]+)\s+(?:gave away|gave|gives|lost|loses|used|uses|deleted|ate|eats|sold|spent|drank|graded|passes|threw away)\s+(\d+)\s*((?:[a-z]+\s+){0,3}[a-z]+)?",
        sentence,
    ):
        obj = normalize_object_phrase(loss.group(3) or last_object or "")
        if not obj and last_object:
            obj = last_object
        owner = normalize_state_owner(loss.group(1), last_owner)
        if owner and obj:
            facts.append(("delta", owner, obj, -int(loss.group(2))))
            last_owner = owner
            last_object = obj
    transfer_loss = re.search(r"\b[a-z]+\s+took\s+(\d+)\s+from\s+(?:him|her|them|it)", sentence)
    if transfer_loss and last_owner and last_object:
        facts.append(("delta", last_owner, last_object, -int(transfer_loss.group(1))))
    passive_loss = re.search(r"\b(\d+)\s+((?:[a-z]+\s+){0,2}[a-z]+)\s+(?:flew away|were deleted|were used|were lost|left)", sentence)
    if passive_loss and last_owner:
        facts.append(("delta", last_owner, normalize_object_phrase(passive_loss.group(2)), -int(passive_loss.group(1))))
    passive_made = re.search(r"\b(?:another\s+)?(\d+)\s+(?:are|were|is|was)\s+made into\b", sentence)
    if passive_made and last_owner and last_object:
        facts.append(("delta", last_owner, last_object, -int(passive_made.group(1))))
    passive_gain = re.search(r"\b(?:another\s+)?(\d+)\s+(?:were|was)\s+turned in\b", sentence)
    if passive_gain and last_owner and last_object:
        facts.append(("delta", last_owner, last_object, int(passive_gain.group(1))))
    more = re.search(r"\b(?:then|and then|but then|later)?\s*(?:bought|added|got|found|picked)\s+(\d+)\s+more\b", sentence)
    if more and last_owner and last_object:
        facts.append(("delta", last_owner, last_object, int(more.group(1))))
    return facts


def normalize_entity(value: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "", value.lower()) or "entity"


def normalize_state_owner(value: str, last_owner: str | None) -> str | None:
    owner = normalize_entity(value)
    if owner in {"he", "she", "they", "him", "her", "them", "it", "then", "and", "but", "if"}:
        return last_owner
    return owner


def normalize_object_phrase(value: str) -> str:
    words = re.findall(r"[a-z]+", value.lower())
    if not words:
        return ""
    for index, word in enumerate(words):
        if word in {
            "on",
            "in",
            "from",
            "to",
            "for",
            "with",
            "at",
            "by",
            "of",
            "while",
            "and",
            "but",
            "that",
            "which",
            "out",
            "how",
            "many",
            "does",
            "do",
            "did",
            "would",
            "have",
            "has",
        }:
            words = words[:index]
            break
        if index > 0 and word in {"he", "she", "they", "it", "his", "her", "their", "him", "them"}:
            words = words[:index]
            break
    words = [word for word in words if word not in {"old", "new", "more", "total", "left", "ones", "one"}]
    if not words:
        return ""
    return normalize_object(words[-1])


def normalize_object(value: str) -> str:
    value = re.sub(r"[^a-z]+", "", value.lower())
    if value.endswith("ies") and len(value) > 3:
        return value[:-3] + "y"
    if value.endswith("s") and len(value) > 3:
        return value[:-1]
    return value


def compatible_object(left: str, right: str) -> bool:
    return normalize_object(left) == normalize_object(right)


def lift_probability_morphisms(
    text: str,
    object_map: dict[str, SemanticObject],
    morphisms: list[SemanticMorphism],
    constraints: list[Constraint],
    queries: list[SemanticQuery],
) -> None:
    if "probability" not in text:
        return
    binomial = re.search(
        r"(\d+)\s+independent trials.*?success probability\s+(\d+/\d+|\d+(?:\.\d+)?).*?exactly\s+(\d+)\s+success",
        text,
    )
    if binomial:
        n, probability, k = binomial.group(1), binomial.group(2), binomial.group(3)
        object_map.setdefault("trials", SemanticObject("trials", "Natural", "trial_count", expression=n, source="math_morphism_library.probability"))
        object_map.setdefault("successes", SemanticObject("successes", "Natural", "success_count", expression=k, source="math_morphism_library.probability"))
        morphisms.extend(
            [
                SemanticMorphism(
                    name="BinomialCoefficient",
                    domain=["Natural", "Natural"],
                    codomain="Natural",
                    kind="counting_observable",
                    expression="C(n,k)",
                    law="C(n,k)=n!/(k!(n-k)!)",
                    source="math_morphism_library.probability",
                ),
                SemanticMorphism(
                    name="BinomialProbability",
                    domain=["Natural", "Natural", "Probability"],
                    codomain="Probability",
                    kind="probability_observable",
                    expression="BinomialProbability(n,k,p)",
                    law="C(n,k)p^k(1-p)^(n-k)",
                    source="math_morphism_library.probability",
                ),
            ]
        )
        constraints.append(
            Constraint(
                kind="binomial_probability",
                expression=f"BinomialProbability({n},{k},{probability})",
                objects=["trials", "successes"],
                morphisms=["BinomialCoefficient", "BinomialProbability"],
                source="math_morphism_library.probability",
            )
        )
        queries.append(
            SemanticQuery(
                kind="compute_probability",
                target=f"BinomialProbability({n},{k},{probability})",
                sort="Probability",
                expression="Find exact binomial probability",
            )
        )
    if "not" in text or "complement" in text or "does not" in text:
        object_map.setdefault("event", SemanticObject("event", "Event", "event", source="math_morphism_library.probability"))
        morphisms.extend(
            [
                SemanticMorphism(
                    name="ProbabilityMeasure",
                    domain=["Event"],
                    codomain="Probability",
                    kind="measure",
                    expression="P(event)",
                    law="P : Event -> [0,1]",
                    source="math_morphism_library.probability",
                ),
                SemanticMorphism(
                    name="ComplementEvent",
                    domain=["Event"],
                    codomain="Event",
                    kind="logical_complement",
                    expression="Complement(event)",
                    law="P(Complement(A)) = 1 - P(A)",
                    source="math_morphism_library.probability",
                ),
            ]
        )
        probability = re.search(r"(?:is|equals)\s+\$?\s*(\\frac\{[^{}]+\}\{[^{}]+\}|\d+/\d+|\d+(?:\.\d+)?)", text)
        if probability:
            constraints.append(
                Constraint(
                    kind="probability_value",
                    expression=f"P(event) = {probability.group(1)}",
                    objects=["event"],
                    morphisms=["ProbabilityMeasure"],
                    source="math_morphism_library.probability",
                )
            )
        queries.append(
            SemanticQuery(
                kind="compute_probability",
                target="P(Complement(event))",
                sort="Probability",
                expression="Find complement probability",
            )
        )


def lift_algebra_morphisms(
    text: str,
    object_map: dict[str, SemanticObject],
    morphisms: list[SemanticMorphism],
    constraints: list[Constraint],
    queries: list[SemanticQuery],
) -> None:
    if "|" in text and "=" in text and ("smallest" in text or "solve" in text):
        object_map.setdefault("x", SemanticObject("x", "Real", "unknown", source="math_morphism_library.algebra"))
        morphisms.extend(
            [
                SemanticMorphism(
                    name="LinearForm",
                    domain=["Real"],
                    codomain="Real",
                    kind="polynomial",
                    expression="a*x+b",
                    law="linear form over Real",
                    source="math_morphism_library.algebra",
                ),
                SemanticMorphism(
                    name="AbsoluteValue",
                    domain=["Real"],
                    codomain="Real",
                    kind="piecewise_linear",
                    expression="abs(t)",
                    law="abs(u)=abs(v) iff u=v or u=-v",
                    source="math_morphism_library.algebra",
                ),
            ]
        )
        match = re.search(r"\|([^|]+)\|\s*=\s*\|([^|]+)\|", text)
        if match:
            constraints.append(
                Constraint(
                    kind="absolute_value_equation",
                    expression=f"AbsEquation({match.group(1).strip()} = {match.group(2).strip()})",
                    objects=["x"],
                    morphisms=["LinearForm", "AbsoluteValue"],
                    source="math_morphism_library.algebra",
                )
            )
        queries.append(SemanticQuery(kind="compute_min_solution", target="min_solution_x", sort="Real", expression="Find smallest solution of absolute-value equation"))

    if "x^2" in text and ("<=" in text or "\\le" in text) and ("for what values of x" in text or "solve" in text):
        object_map.setdefault("x", SemanticObject("x", "Real", "unknown", source="math_morphism_library.algebra"))
        morphisms.extend(
            [
                SemanticMorphism(
                    name="QuadraticPolynomial",
                    domain=["Real"],
                    codomain="Real",
                    kind="polynomial",
                    expression="x^2+b*x+c",
                    law="degree-2 polynomial over Real",
                    source="math_morphism_library.algebra",
                ),
                SemanticMorphism(
                    name="PolynomialInequality",
                    domain=["Real"],
                    codomain="Prop",
                    kind="order_relation",
                    expression="p(x) <= 0",
                    law="quadratic inequality solution is interval between real roots when leading coefficient is positive",
                    source="math_morphism_library.algebra",
                ),
            ]
        )
        match = re.search(r"x\^2\s*([+-]\s*\d+)\*?x\s*([+-]\s*\d+)\s*(?:<=|\\le)\s*(-?\d+)", text)
        if match:
            constraints.append(
                Constraint(
                    kind="quadratic_inequality",
                    expression=f"x^2 {match.group(1)}*x {match.group(2)} <= {match.group(3)}",
                    objects=["x"],
                    morphisms=["QuadraticPolynomial", "PolynomialInequality"],
                    source="math_morphism_library.algebra",
                )
            )
        queries.append(SemanticQuery(kind="compute_interval", target="solution_interval_x", sort="Region1", expression="Find interval solution of quadratic inequality"))

    quadratic = re.search(r"x\^2\s*([+-]\s*\d+)\*?x\s*([+-]\s*\d+)\s*=\s*0", text)
    if quadratic and ("root" in text or "solution" in text):
        object_map.setdefault("x", SemanticObject("x", "Real", "unknown", source="math_morphism_library.algebra"))
        morphisms.extend(
            [
                SemanticMorphism(
                    name="QuadraticEquation",
                    domain=["Real"],
                    codomain="Prop",
                    kind="polynomial_equation",
                    expression="x^2+b*x+c=0",
                    law="degree-2 polynomial equation over Real",
                    source="math_morphism_library.algebra",
                ),
                SemanticMorphism(
                    name="RootObservable",
                    domain=["Polynomial"],
                    codomain="Real",
                    kind="symmetric_observable",
                    expression="RootObservable(p)",
                    law="Vieta symmetric root invariant",
                    source="math_morphism_library.algebra",
                ),
            ]
        )
        constraints.append(
            Constraint(
                kind="quadratic_equation",
                expression=f"QuadraticEquation(1,{quadratic.group(1).replace(' ', '')},{quadratic.group(2).replace(' ', '')})",
                objects=["x"],
                morphisms=["QuadraticEquation"],
                source="math_morphism_library.algebra",
            )
        )
        target = "RootObservable(product)" if "product" in text else "RootObservable(sum)"
        queries.append(SemanticQuery(kind="compute_root_observable", target=target, sort="Real", expression=f"Find {target}"))

    remainder = re.search(r"remainder of\s+(.+?)\s+when (?:it is )?divided by\s+x\s*-\s*(-?\d+)", text)
    if remainder:
        object_map.setdefault("poly", SemanticObject("poly", "Polynomial", "polynomial", source="math_morphism_library.algebra"))
        morphisms.append(
            SemanticMorphism(
                name="PolynomialRemainder",
                domain=["Polynomial", "Polynomial"],
                codomain="Polynomial",
                kind="quotient_observable",
                expression="PolynomialRemainder(f,x-a)",
                law="remainder by x-a is f(a)",
                source="math_morphism_library.algebra",
            )
        )
        constraints.append(
            Constraint(
                kind="polynomial_remainder",
                expression=f"PolynomialRemainder({remainder.group(1).strip()}, x-{remainder.group(2)})",
                objects=["poly"],
                morphisms=["PolynomialRemainder"],
                source="math_morphism_library.algebra",
            )
        )
        queries.append(SemanticQuery(kind="compute_remainder", target="PolynomialRemainder(poly,linear_divisor)", sort="Real", expression="Find polynomial remainder"))

    repeated_remainder = re.search(
        r"x\^\s*(\d+).*?\(x\s*-\s*(-?\d+)\)\^\s*2.*?(?:余り|remainder)",
        text,
    )
    if not repeated_remainder:
        repeated_remainder = re.search(
            r"(?:余り|remainder).*?x\^\s*(\d+).*?\(x\s*-\s*(-?\d+)\)\^\s*2",
            text,
        )
    if repeated_remainder:
        object_map.setdefault("poly", SemanticObject("poly", "Polynomial", "polynomial", source="math_morphism_library.algebra"))
        morphisms.append(
            SemanticMorphism(
                name="RepeatedLinearRemainder",
                domain=["Polynomial", "Polynomial"],
                codomain="Polynomial",
                kind="quotient_observable",
                expression="RepeatedLinearRemainder(f,(x-a)^2)",
                law="remainder is first-order Taylor jet at a",
                source="math_morphism_library.algebra",
            )
        )
        constraints.append(
            Constraint(
                kind="repeated_linear_remainder",
                expression=f"RepeatedLinearRemainder(x^{repeated_remainder.group(1)}, x-{repeated_remainder.group(2)}, 2)",
                objects=["poly"],
                morphisms=["RepeatedLinearRemainder"],
                source="math_morphism_library.algebra",
            )
        )
        queries.append(
            SemanticQuery(
                kind="compute_remainder",
                target="RepeatedLinearRemainder(poly,repeated_linear_divisor)",
                sort="Polynomial",
                expression="Find polynomial remainder modulo repeated linear divisor",
            )
        )

    system = re.search(
        r"system\s+(-?\d+)\*?x\s*([+-]\s*\d+)\*?y\s*=\s*(-?\d+)\s+and\s+(-?\d+)\*?x\s*([+-]\s*\d+)\*?y\s*=\s*(-?\d+)",
        text,
    )
    if system:
        object_map.setdefault("x", SemanticObject("x", "Real", "unknown", source="math_morphism_library.algebra"))
        object_map.setdefault("y", SemanticObject("y", "Real", "unknown", source="math_morphism_library.algebra"))
        morphisms.append(
            SemanticMorphism(
                name="LinearSystem2",
                domain=["Real", "Real"],
                codomain="Prop",
                kind="linear_system",
                expression="A*[x,y]=b",
                law="2x2 linear system over Real",
                source="math_morphism_library.algebra",
            )
        )
        constraints.append(
            Constraint(
                kind="linear_system_2x2",
                expression=(
                    "LinearSystem2("
                    f"{system.group(1)},{system.group(2).replace(' ', '')},{system.group(3)},"
                    f"{system.group(4)},{system.group(5).replace(' ', '')},{system.group(6)})"
                ),
                objects=["x", "y"],
                morphisms=["LinearSystem2"],
                source="math_morphism_library.algebra",
            )
        )
        target = "LinearSystem2(x+y)" if "x + y" in text or "x+y" in text else "LinearSystem2(solution)"
        queries.append(SemanticQuery(kind="compute_linear_observable", target=target, sort="Real", expression="Solve 2x2 system"))


def lift_growth_morphisms(
    text: str,
    object_map: dict[str, SemanticObject],
    morphisms: list[SemanticMorphism],
    constraints: list[Constraint],
    queries: list[SemanticQuery],
) -> None:
    if "compounds annually" not in text and "compound" not in text:
        return
    if "interest rate" not in text:
        return
    object_map.setdefault("principal", SemanticObject("principal", "Currency", "initial_amount", source="math_morphism_library.growth"))
    object_map.setdefault("final_amount", SemanticObject("final_amount", "Currency", "final_amount", source="math_morphism_library.growth"))
    morphisms.append(
        SemanticMorphism(
            name="CompoundGrowth",
            domain=["Real", "Percent", "Natural"],
            codomain="Real",
            kind="dynamical_system",
            expression="principal*(1+r/100)^years",
            law="final = principal*(1+r/100)^years",
            source="math_morphism_library.growth",
        )
    )
    start = re.search(r"(?:invests|investment of)\s+(\d+(?:\.\d+)?)\s+dollars", text)
    years = re.search(r"after\s+(\w+|\d+)\s+years", text)
    final = re.search(r"grown to\s+(\d+(?:\.\d+)?)\s+dollars", text)
    if start and years and final:
        constraints.append(
            Constraint(
                kind="compound_growth_equation",
                expression=f"CompoundGrowth({start.group(1)}, rate_percent, {years.group(1)}) = {final.group(1)}",
                objects=["principal", "final_amount"],
                morphisms=["CompoundGrowth"],
                source="math_morphism_library.growth",
            )
        )
    queries.append(SemanticQuery(kind="compute_percent", target="rate_percent", sort="Percent", expression="Find compound annual interest rate percent"))


def lift_combinatorics_morphisms(
    text: str,
    object_map: dict[str, SemanticObject],
    morphisms: list[SemanticMorphism],
    constraints: list[Constraint],
    queries: list[SemanticQuery],
) -> None:
    choose = re.search(r"(?:choose|select)\s+(\d+)\s+(?:objects|students|items|members)\s+from\s+(\d+)", text)
    if not choose and "how many ways" in text:
        choose = re.search(r"(\d+)\s+(?:objects|students|items|members).*?choose\s+(\d+)", text)
        if choose:
            n, k = choose.group(1), choose.group(2)
        else:
            n = k = None
    elif choose:
        k, n = choose.group(1), choose.group(2)
    else:
        n = k = None
    if n is None or k is None:
        return
    object_map.setdefault("n", SemanticObject("n", "Natural", "set_size", expression=n, source="math_morphism_library.combinatorics"))
    object_map.setdefault("k", SemanticObject("k", "Natural", "selection_size", expression=k, source="math_morphism_library.combinatorics"))
    morphisms.append(
        SemanticMorphism(
            name="BinomialCoefficient",
            domain=["Natural", "Natural"],
            codomain="Natural",
            kind="counting_observable",
            expression="C(n,k)",
            law="C(n,k)=n!/(k!(n-k)!)",
            source="math_morphism_library.combinatorics",
        )
    )
    constraints.append(
        Constraint(
            kind="binomial_coefficient",
            expression=f"BinomialCoefficient({n},{k})",
            objects=["n", "k"],
            morphisms=["BinomialCoefficient"],
            source="math_morphism_library.combinatorics",
        )
    )
    queries.append(SemanticQuery(kind="compute_count", target=f"BinomialCoefficient({n},{k})", sort="Natural", expression="Find number of selections"))


def lift_function_morphisms(
    text: str,
    object_map: dict[str, SemanticObject],
    morphisms: list[SemanticMorphism],
    constraints: list[Constraint],
    queries: list[SemanticQuery],
) -> None:
    log_eq = re.search(r"log base\s+(\d+)\s+of\s+x\s+(?:equals|=)\s+(-?\d+)", text)
    if log_eq:
        object_map.setdefault("x", SemanticObject("x", "Real", "unknown", source="math_morphism_library.functions"))
        morphisms.append(
            SemanticMorphism(
                name="Logarithm",
                domain=["Real", "Real"],
                codomain="Real",
                kind="elementary_function",
                expression="log_b(x)",
                law="log_b(x)=k iff x=b^k",
                source="math_morphism_library.functions",
            )
        )
        constraints.append(
            Constraint(
                kind="log_equation",
                expression=f"LogEquation({log_eq.group(1)},x,{log_eq.group(2)})",
                objects=["x"],
                morphisms=["Logarithm"],
                source="math_morphism_library.functions",
            )
        )
        queries.append(SemanticQuery(kind="compute_unknown", target="log_unknown_x", sort="Real", expression="Find x in logarithm equation"))

    exp_eq = re.search(r"(\d+)\^x\s*=\s*(\d+)", text)
    if exp_eq:
        object_map.setdefault("x", SemanticObject("x", "Real", "unknown", source="math_morphism_library.functions"))
        morphisms.append(
            SemanticMorphism(
                name="ExponentialPower",
                domain=["Real", "Real"],
                codomain="Real",
                kind="elementary_function",
                expression="b^x",
                law="b^x=N",
                source="math_morphism_library.functions",
            )
        )
        constraints.append(
            Constraint(
                kind="exponential_equation",
                expression=f"ExponentialEquation({exp_eq.group(1)},x,{exp_eq.group(2)})",
                objects=["x"],
                morphisms=["ExponentialPower"],
                source="math_morphism_library.functions",
            )
        )
        queries.append(SemanticQuery(kind="compute_unknown", target="exponent_unknown_x", sort="Real", expression="Find exponent x"))

    trig = re.search(r"sin\(theta\)\s*=\s*(\d+/\d+).*?cos\^2\(theta\)", text)
    if trig:
        object_map.setdefault("theta", SemanticObject("theta", "Angle", "angle", source="math_morphism_library.functions"))
        morphisms.append(
            SemanticMorphism(
                name="TrigPythagorean",
                domain=["Angle"],
                codomain="Prop",
                kind="identity",
                expression="sin^2(theta)+cos^2(theta)=1",
                law="unit circle invariant",
                source="math_morphism_library.functions",
            )
        )
        constraints.append(
            Constraint(
                kind="trig_pythagorean",
                expression=f"SinValue(theta,{trig.group(1)})",
                objects=["theta"],
                morphisms=["TrigPythagorean"],
                source="math_morphism_library.functions",
            )
        )
        queries.append(SemanticQuery(kind="compute_trig", target="cos_square(theta)", sort="Real", expression="Find cos^2(theta)"))


def lift_vector_geometry_morphisms(
    text: str,
    object_map: dict[str, SemanticObject],
    morphisms: list[SemanticMorphism],
    constraints: list[Constraint],
    queries: list[SemanticQuery],
) -> None:
    dot = re.search(r"dot product of (?:vectors? )?\((-?\d+),\s*(-?\d+)\)\s+and\s+\((-?\d+),\s*(-?\d+)\)", text)
    if dot:
        object_map.setdefault("u", SemanticObject("u", "Vector2", "vector", expression=f"({dot.group(1)},{dot.group(2)})", source="math_morphism_library.vector_geometry"))
        object_map.setdefault("v", SemanticObject("v", "Vector2", "vector", expression=f"({dot.group(3)},{dot.group(4)})", source="math_morphism_library.vector_geometry"))
        morphisms.append(
            SemanticMorphism(
                name="DotProduct",
                domain=["Vector2", "Vector2"],
                codomain="Real",
                kind="inner_product",
                expression="DotProduct(u,v)",
                law="u1*v1+u2*v2",
                source="math_morphism_library.vector_geometry",
            )
        )
        constraints.append(
            Constraint(
                kind="vector_coordinates",
                expression=f"DotProductVectors({dot.group(1)},{dot.group(2)},{dot.group(3)},{dot.group(4)})",
                objects=["u", "v"],
                morphisms=["DotProduct"],
                source="math_morphism_library.vector_geometry",
            )
        )
        queries.append(SemanticQuery(kind="compute_inner_product", target="DotProduct(u,v)", sort="Real", expression="Find dot product"))

    lines = re.search(
        r"intersection of\s+y\s*=\s*(-?\d+)\*?x\s*([+-]\s*\d+)\s+and\s+y\s*=\s*(-?\d+)\*?x\s*([+-]\s*\d+)",
        text,
    )
    if lines:
        morphisms.extend(
            [
                SemanticMorphism(
                    name="LineIntersection",
                    domain=["Line2", "Line2"],
                    codomain="Point2",
                    kind="affine_constructor",
                    expression="LineIntersection(l1,l2)",
                    law="solve two affine equations",
                    source="math_morphism_library.vector_geometry",
                ),
                SemanticMorphism(
                    name="CoordinateSum",
                    domain=["Point2"],
                    codomain="Real",
                    kind="observable",
                    expression="CoordinateSum(P)",
                    law="CoordinateSum((x,y))=x+y",
                    source="math_morphism_library.vector_geometry",
                ),
            ]
        )
        constraints.append(
            Constraint(
                kind="line_pair",
                expression=(
                    "LineIntersection("
                    f"{lines.group(1)},{lines.group(2).replace(' ', '')},"
                    f"{lines.group(3)},{lines.group(4).replace(' ', '')})"
                ),
                morphisms=["LineIntersection"],
                source="math_morphism_library.vector_geometry",
            )
        )
        queries.append(SemanticQuery(kind="compute_observable", target="LineIntersectionCoordinateSum", sort="Real", expression="Find sum of intersection coordinates"))

    circle = re.search(
        r"circle with center\s+\((-?\d+),\s*(-?\d+)\)\s+passes through\s+\((-?\d+),\s*(-?\d+)\).*?radius",
        text,
    )
    if not circle and "radius" in text:
        circle = re.search(
            r"circle with center\s+\((-?\d+),\s*(-?\d+)\)\s+passes through\s+\((-?\d+),\s*(-?\d+)\)",
            text,
        )
    if circle:
        object_map.setdefault("C", SemanticObject("C", "Point2", "center", expression=f"({circle.group(1)},{circle.group(2)})", source="math_morphism_library.vector_geometry"))
        object_map.setdefault("P", SemanticObject("P", "Point2", "point_on_circle", expression=f"({circle.group(3)},{circle.group(4)})", source="math_morphism_library.vector_geometry"))
        morphisms.append(
            SemanticMorphism(
                name="CircleRadius",
                domain=["Point2", "Point2"],
                codomain="Real",
                kind="metric_observable",
                expression="CircleRadius(C,P)",
                law="radius=Distance(C,P)",
                source="math_morphism_library.vector_geometry",
            )
        )
        constraints.append(
            Constraint(
                kind="circle_radius_data",
                expression=f"CircleRadiusData({circle.group(1)},{circle.group(2)},{circle.group(3)},{circle.group(4)})",
                objects=["C", "P"],
                morphisms=["CircleRadius"],
                source="math_morphism_library.vector_geometry",
            )
        )
        queries.append(SemanticQuery(kind="compute_metric", target="CircleRadius(C,P)", sort="Real", expression="Find radius"))


def lift_calculus_morphisms(
    text: str,
    object_map: dict[str, SemanticObject],
    morphisms: list[SemanticMorphism],
    constraints: list[Constraint],
    queries: list[SemanticQuery],
) -> None:
    derivative = re.search(r"f\(x\)\s*=\s*(-?\d+)\*?x\^2\s*([+-]\s*\d+)\*?x\s*([+-]\s*\d+).*?(?:at|when)\s+x\s*=\s*(-?\d+).*?(?:derivative|slope)", text)
    if derivative:
        object_map.setdefault("f", SemanticObject("f", "Function", "polynomial_function", source="math_morphism_library.calculus"))
        morphisms.append(
            SemanticMorphism(
                name="Derivative",
                domain=["Function"],
                codomain="Function",
                kind="differential_operator",
                expression="Derivative(f)",
                law="D(a*x^2+b*x+c)=2*a*x+b",
                source="math_morphism_library.calculus",
            )
        )
        constraints.append(
            Constraint(
                kind="polynomial_derivative_value",
                expression=(
                    f"DerivativeValue({derivative.group(1)},{derivative.group(2).replace(' ', '')},"
                    f"{derivative.group(3).replace(' ', '')},{derivative.group(4)})"
                ),
                objects=["f"],
                morphisms=["Derivative"],
                source="math_morphism_library.calculus",
            )
        )
        queries.append(SemanticQuery(kind="compute_derivative_value", target="DerivativeValue(f,t)", sort="Real", expression="Find derivative value"))

    integral = re.search(
        r"integral from 0 to\s+(-?\d+)\s+of\s+(-?\d+)\*?x\^2\s*([+-]\s*\d+)\*?x\s*([+-]\s*\d+)\s+dx",
        text,
    )
    if integral:
        object_map.setdefault("f", SemanticObject("f", "Function", "polynomial_function", source="math_morphism_library.calculus"))
        morphisms.append(
            SemanticMorphism(
                name="DefiniteIntegral",
                domain=["Function", "Interval"],
                codomain="Real",
                kind="integral_operator",
                expression="DefiniteIntegral(f,[0,r])",
                law="integral over compact interval",
                source="math_morphism_library.calculus",
            )
        )
        constraints.append(
            Constraint(
                kind="polynomial_definite_integral",
                expression=(
                    f"DefiniteIntegral(0,{integral.group(1)},{integral.group(2)},"
                    f"{integral.group(3).replace(' ', '')},{integral.group(4).replace(' ', '')})"
                ),
                objects=["f"],
                morphisms=["DefiniteIntegral"],
                source="math_morphism_library.calculus",
            )
        )
        queries.append(SemanticQuery(kind="compute_integral", target="DefiniteIntegral(f,[0,r])", sort="Real", expression="Find definite integral"))


def run_verifier_gate(graph: TypedSemanticGraph, *, answer: str | None = None) -> VerifierGateReport:
    checks: list[str] = []
    warnings: list[str] = list(graph.warnings)
    obligations = graph.constraint_ir().obligations

    if graph.sorts:
        checks.append("sorts_declared")
    if graph.objects:
        checks.append("objects_declared")
    if graph.morphisms:
        checks.append("morphisms_declared")
    if graph.constraints:
        checks.append("constraints_declared")
    if graph.queries:
        checks.append("query_declared")
    else:
        warnings.append("answer cannot be fully checked because no semantic query was compiled")

    missing_sorts = missing_morphism_sorts(graph)
    if missing_sorts:
        warnings.append("morphism references undeclared sorts: " + ", ".join(sorted(missing_sorts)))
    else:
        checks.append("morphism_sorts_resolved")

    if answer is not None:
        checks.append("answer_present")
        if graph.queries and not graph.constraints:
            warnings.append("answer has query but no constraints")
    else:
        warnings.append("no answer available for verifier gate")

    rejection = None
    if missing_sorts and answer is not None:
        rejection = "answer blocked by unresolved semantic sorts"
    status = "rejected" if rejection else ("accepted" if checks and not warnings else "needs_review")
    return VerifierGateReport(status=status, checks=checks, obligations=obligations, warnings=dedupe_strings(warnings), rejection=rejection)


def parse_type_signature(signature: str) -> tuple[list[str], str]:
    cleaned = signature.strip()
    if not cleaned or cleaned == "Sort":
        return [], "Object"
    parts = [part.strip() for part in re.split(r"\s*->\s*", cleaned) if part.strip()]
    if len(parts) < 2:
        return [], cleaned
    domain_text = " -> ".join(parts[:-1])
    codomain = parts[-1]
    domain = [item.strip() for item in re.split(r"\s+x\s+|,\s*", domain_text) if item.strip()]
    return domain or ["Object"], codomain


def register_sort_expression(sort: str, sort_map: dict[str, SemanticSort]) -> None:
    if not sort or sort in sort_map:
        return
    base = re.split(r"[\[(]", sort, 1)[0]
    parent = base if base and base != sort else "Object"
    sort_map.setdefault(sort, SemanticSort(sort, "derived", parent=parent))


def role_to_morphism_kind(role: str) -> str:
    if role == "query":
        return "query_constructor"
    if role in {"logical_form", "logical_relation", "logical_connective"}:
        return "logical"
    if role == "term_constructor":
        return "constructor"
    return "operation"


def infer_theory_from_sort(name: str) -> str | None:
    if name in {"Real", "Point2", "Curve2", "Region2"}:
        return "real_closed_fields"
    if name == "Complex" or "Complex" in name:
        return "complex_algebra"
    if name in {"Integer", "Natural"}:
        return "integer_arithmetic"
    if name in {"Probability", "ProbabilitySpace"}:
        return "probability"
    return None


def infer_sort_from_query_target(target: str) -> str | None:
    if target in {"A", "answer", "value"}:
        return "Real"
    if target.startswith("P"):
        return "Prop"
    return None


def structural_kind_to_sort(kind: str) -> str:
    mapping = {
        "point": "Point2",
        "line": "Curve2",
        "curve": "Curve2",
        "circle": "Curve2",
        "triangle": "FiniteShape",
        "equilateral_triangle": "FiniteShape",
        "square": "FiniteShape",
        "region": "Region2",
        "integer": "Integer",
        "positive_integer": "Natural",
        "function": "Function",
    }
    return mapping.get(kind, "Object")


def infer_query_from_text(text: str, typed: dict[str, Any]) -> SemanticQuery | None:
    normalized = text.lower()
    if any(marker in normalized for marker in ("求め", "find", "compute", "how many", "how much")):
        target = query_object(normalized) or "answer"
        sort = f"Count[{target}]" if target != "answer" else "Real"
        return SemanticQuery(kind="compute", target=f"answer_{target}", sort=sort, expression=f"Find({target})")
    if any(marker in normalized for marker in ("示せ", "prove", "show that")):
        return SemanticQuery(kind="prove", target="proof", sort="Prop", expression="Prove(goal)")
    query = typed.get("query") if typed else None
    if query:
        return SemanticQuery(kind=str(query.get("kind") or "compute"), target=str(query.get("target") or "answer"), sort=str(query.get("type") or "Unknown"), expression=str(query))
    return None


def find_graph_warnings(
    sort_map: dict[str, SemanticSort],
    object_map: dict[str, SemanticObject],
    morphisms: list[SemanticMorphism],
    constraints: list[Constraint],
    queries: list[SemanticQuery],
) -> list[str]:
    warnings = []
    if not object_map:
        warnings.append("semantic graph has no typed objects")
    if not morphisms:
        warnings.append("semantic graph has no morphisms")
    if not constraints:
        warnings.append("semantic graph has no constraints")
    if not queries:
        warnings.append("semantic graph has no query")
    missing = missing_morphism_sorts_from_parts(sort_map, morphisms)
    if missing:
        warnings.append("undeclared morphism sorts: " + ", ".join(sorted(missing)))
    return warnings


def missing_morphism_sorts(graph: TypedSemanticGraph) -> set[str]:
    return missing_morphism_sorts_from_parts({item.name: item for item in graph.sorts}, graph.morphisms)


def missing_morphism_sorts_from_parts(sort_map: dict[str, SemanticSort], morphisms: list[SemanticMorphism]) -> set[str]:
    missing = set()
    for morphism in morphisms:
        for sort in [*morphism.domain, morphism.codomain]:
            if is_sort_expression_resolved(sort, sort_map):
                continue
            missing.add(sort)
    return missing


def is_sort_expression_resolved(sort: str, sort_map: dict[str, SemanticSort]) -> bool:
    if not sort or sort in sort_map:
        return True
    base = re.split(r"[\[(]", sort, 1)[0]
    if base in sort_map:
        return True
    if "->" in sort:
        return True
    if sort.startswith("Fin("):
        return True
    return False


def query_object(text: str) -> str | None:
    for pattern in (
        r"how many more (?P<object>[a-z-]+)",
        r"how many (?P<object>[a-z-]+)",
        r"how much (?P<object>money|water|cost|distance|area|time)",
        r"how much (?P<object>[a-z-]+)",
    ):
        match = re.search(pattern, text.lower())
        if match:
            return normalize_object(match.group("object"))
    return None


def normalize_object(value: str) -> str:
    value = re.sub(r"[^a-zA-Z_]", "", value.lower())
    if value.endswith("ies"):
        value = value[:-3] + "y"
    elif value.endswith("s") and len(value) > 3:
        value = value[:-1]
    return value or "quantity"


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z_\u3040-\u30ff\u3400-\u9fff]+", "_", value.strip())
    cleaned = cleaned.strip("_")
    return cleaned or "object"


def dedupe_morphisms(items: list[SemanticMorphism]) -> list[SemanticMorphism]:
    seen = set()
    output = []
    for item in items:
        key = (item.name, tuple(item.domain), item.codomain, item.kind, item.expression)
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


def dedupe_constraints(items: list[Constraint]) -> list[Constraint]:
    seen = set()
    output = []
    for item in items:
        key = (item.kind, item.expression)
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


def dedupe_queries(items: list[SemanticQuery]) -> list[SemanticQuery]:
    seen = set()
    output = []
    for item in items:
        key = (item.kind, item.target, item.sort, item.expression)
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


def dedupe_strings(items: list[str]) -> list[str]:
    seen = set()
    output = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output
