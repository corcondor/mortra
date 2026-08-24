"""Create a proof, construction graph, and diagram from one native Newclid run.

The important invariant is that all three artifacts are projections of the
same ``JGEXFormulation`` and ``ProofState``.  The diagram is therefore not a
second parser's guess about the problem and the proof text is not attached to
an unrelated sketch.
"""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np

matplotlib.use("Agg")

from matplotlib import pyplot as plt
from newclid.api import GeometricSolverBuilder, PythonDefault
from newclid.jgex.formulation import JGEXFormulation
from newclid.jgex.problem_builder import JGEXProblemBuilder
from newclid.problem import predicate_to_construction
from newclid.proof_data import proof_data_from_state

from worker.backend.jgex_legacy_normalizer import normalize_legacy_formulation
from worker.backend.newclid_sympy_ar_compat import (
    MORTRASympyARDeductor,
    install_variadic_diff_compat,
)


@dataclass(frozen=True)
class ConstructionNode:
    node_id: str
    clause_index: int
    auxiliary: bool
    outputs: tuple[str, ...]
    operation: str
    arguments: tuple[str, ...]


@dataclass(frozen=True)
class ConstructionEdge:
    producer: str
    consumer: str
    point: str


@dataclass(frozen=True)
class NewclidSolutionArtifact:
    status: str
    solved: bool
    formulation_sha256: str
    coordinates: dict[str, tuple[float, float]]
    construction_nodes: tuple[ConstructionNode, ...]
    construction_edges: tuple[ConstructionEdge, ...]
    proof_length: int
    proof_rule_applications: int
    proof_predicates: tuple[str, ...]
    proof_text: str
    diagram_svg: str
    run: dict[str, Any]
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["construction_nodes"] = [asdict(item) for item in self.construction_nodes]
        value["construction_edges"] = [asdict(item) for item in self.construction_edges]
        return value


def construction_graph(
    formulation: JGEXFormulation,
) -> tuple[tuple[ConstructionNode, ...], tuple[ConstructionEdge, ...]]:
    """Build the finite point-production DAG encoded by JGEX clauses."""

    nodes: list[ConstructionNode] = []
    producer_by_point: dict[str, tuple[str, int]] = {}
    setup_count = len(formulation.setup_clauses)
    for clause_index, clause in enumerate(formulation.clauses):
        auxiliary = clause_index >= setup_count
        outputs = tuple(str(point) for point in clause.points)
        for operation_index, construction in enumerate(clause.constructions):
            node_id = f"c{clause_index}.o{operation_index}"
            node = ConstructionNode(
                node_id=node_id,
                clause_index=clause_index,
                auxiliary=auxiliary,
                outputs=outputs,
                operation=construction.name,
                arguments=tuple(str(argument) for argument in construction.args),
            )
            nodes.append(node)
            for point in outputs:
                producer_by_point.setdefault(point, (node_id, clause_index))

    edges: list[ConstructionEdge] = []
    for node in nodes:
        for argument in node.arguments:
            producer_record = producer_by_point.get(argument)
            if producer_record is not None and producer_record[1] < node.clause_index:
                edge = ConstructionEdge(producer_record[0], node.node_id, argument)
                if edge not in edges:
                    edges.append(edge)
    return tuple(nodes), tuple(edges)


def _proof_predicates(proof_data: Any) -> tuple[str, ...]:
    values: list[str] = []
    for item in proof_data.construction_assumptions:
        values.append(str(item.predicate))
    for item in proof_data.numerical_checks:
        values.append(str(item.predicate))
    for step in proof_data.proof_steps:
        values.append(str(step.proven_predicate.predicate))
    for item in proof_data.proven_goals:
        values.append(str(item.predicate))
    return tuple(dict.fromkeys(values))


def build_newclid_solution_artifact(
    text: str,
    *,
    seed: int = 0,
    include_auxiliary: bool = True,
) -> NewclidSolutionArtifact:
    """Execute the official Newclid construction, solver, writer, and renderer."""

    normalized = text.strip()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    formulation = JGEXFormulation.from_text(normalized)
    try:
        install_variadic_diff_compat()
        rng = np.random.default_rng(seed)
        # Parsing intentionally accepts both current Newclid syntax and the
        # older AlphaGeometry dialect used by the frozen benchmark.  Resolve
        # omitted/reordered output arguments from the official construction
        # signatures before construction, proof, and drawing all consume the
        # formulation.
        definition_source = JGEXProblemBuilder(rng=rng, problem=formulation)
        formulation, normalization = normalize_legacy_formulation(
            formulation,
            definition_source.jgex_defs,
        )
        nodes, edges = construction_graph(formulation)
        problem_builder = JGEXProblemBuilder(rng=rng, problem=formulation)
        problem_builder.include_auxiliary_clauses(include_auxiliary)
        problem_setup = problem_builder.build()
        # Select Newclid's official portable backend explicitly.  Auto-selection
        # prefers py_yuclid when it happens to be importable, which makes the
        # artifact depend on a machine-local Yuclid executable path.
        yuclid_binary = Path(sys.executable).with_name(
            "yuclid.exe" if os.name == "nt" else "yuclid"
        )
        if yuclid_binary.is_file():
            runtime_paths = [yuclid_binary.parent]
            if len(yuclid_binary.parents) > 3:
                boost_runtime = yuclid_binary.parents[3] / "boost_1_88_dlls"
                if boost_runtime.is_dir():
                    runtime_paths.append(
                        next(
                            (path.parent for path in boost_runtime.rglob("*.dll")),
                            boost_runtime,
                        )
                    )
            os.environ["PATH"] = os.pathsep.join(
                [*(str(path) for path in runtime_paths), os.environ.get("PATH", "")]
            )
            solver_builder = GeometricSolverBuilder(rng=rng)
            backend_name = "yuclid"
        else:
            solver_builder = GeometricSolverBuilder(
                rng=rng,
                api_default=PythonDefault(use_sympy_ar=False),
            ).with_deductors([MORTRASympyARDeductor()])
            backend_name = "python_sympy_compat"
        solver = solver_builder.build(problem_setup)
        solved = solver.run()

        # The construction diagram is evidence about the attempted problem,
        # not a reward reserved for successful proofs.  Persist it for failed
        # runs as well so an unresolved obligation can be audited against the
        # exact numerical realization consumed by Newclid.
        with tempfile.TemporaryDirectory(prefix="mortra-newclid-artifact-") as raw:
            svg_path = Path(raw) / "proof-figure.svg"
            figure, _axes = solver.draw_figure(
                out_file=svg_path,
                jgex_problem=formulation,
            )
            try:
                diagram_svg = svg_path.read_text(encoding="utf-8")
            finally:
                plt.close(figure)

        if solved:
            goals = [
                predicate_to_construction(goal) for goal in solver.proof_state.goals
            ]
            proof_data = proof_data_from_state(goals, solver.proof_state)
            proof_text = solver.proof(goals)
            proof_length = proof_data.proof_length
            proof_rule_applications = proof_data.proof_rules_length
            proof_predicates = _proof_predicates(proof_data)
        else:
            proof_text = ""
            proof_length = 0
            proof_rule_applications = 0
            proof_predicates = ()

        coordinates = {
            str(point.name): (float(point.num.x), float(point.num.y))
            for point in problem_setup.points
        }
        return NewclidSolutionArtifact(
            status="proved" if solved else "unproved",
            solved=solved,
            formulation_sha256=digest,
            coordinates=coordinates,
            construction_nodes=nodes,
            construction_edges=edges,
            proof_length=proof_length,
            proof_rule_applications=proof_rule_applications,
            proof_predicates=proof_predicates,
            proof_text=proof_text,
            diagram_svg=diagram_svg,
            run={
                **(
                    solver.run_infos.model_dump()
                    if solver.run_infos is not None
                    else {}
                ),
                "legacy_normalization": asdict(normalization),
                "backend": backend_name,
            },
        )
    except Exception as exc:
        nodes, edges = construction_graph(formulation)
        return NewclidSolutionArtifact(
            status="execution_error",
            solved=False,
            formulation_sha256=digest,
            coordinates={},
            construction_nodes=nodes,
            construction_edges=edges,
            proof_length=0,
            proof_rule_applications=0,
            proof_predicates=(),
            proof_text="",
            diagram_svg="",
            run={},
            error=f"{type(exc).__name__}: {exc}",
        )


__all__ = [
    "ConstructionEdge",
    "ConstructionNode",
    "NewclidSolutionArtifact",
    "build_newclid_solution_artifact",
    "construction_graph",
]
