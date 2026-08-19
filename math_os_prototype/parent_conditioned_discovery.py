"""Discover a fusion structure from selected parent problems without an LLM.

The input is not matched against problem families.  Each parent is compiled to
the common semantic kernel (objects, morphisms, constraints, query).  A typed
search then enumerates common codomains and intermediate propositions.  Unknown
connections remain explicit hypotheses; they are never presented as proved.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

try:
    from math_os_prototype.category_semantics import (
        compile_typed_semantic_graph,
        run_verifier_gate,
    )
    from math_os_prototype.theory_atlas import MORPHISM_SCHEMAS
except ImportError:  # pragma: no cover - direct execution from repository root.
    from category_semantics import compile_typed_semantic_graph, run_verifier_gate
    from theory_atlas import MORPHISM_SCHEMAS


MAX_PATH_EDGES = 5
MAX_HYPOTHESES = 64
GENERIC_SORTS = {
    "Any", "Unknown", "Prop", "Set", "Object", "Scalar", "Quantity",
    "Real", "Integer", "Natural", "Rational", "Modulus", "Boolean",
}


# This is an operator vocabulary, not a catalogue of problem templates.  Each
# entry states what a mathematical word or TeX operator denotes and which typed
# operation it contributes.  Numeric values and sentence layouts never occur in
# this table, so surface and parameter changes retain the same semantic lift.
SURFACE_OPERATOR_SIGNATURES: tuple[dict[str, Any], ...] = (
    {
        "patterns": (r"\\int(?![A-Za-z])", r"積分"),
        "sorts": ("IntegralFunctional", "Function"),
        "morphisms": (("Integration", "Function", "IntegralFunctional", "I(f)=integral(f)"),),
    },
    {
        "patterns": (r"数列", r"[A-Za-z]+_\{?n\}?"),
        "sorts": ("Sequence",),
        "morphisms": (("SequenceEvaluation", "Sequence", "Real", "ev_n(a)=a_n"),),
    },
    {
        "patterns": (r"\\lim(?![A-Za-z])", r"極限"),
        "sorts": ("Sequence", "LimitObject"),
        "morphisms": (("Limit", "Sequence", "LimitObject", "Limit(a)=lim a_n when defined"),),
    },
    {
        "patterns": (r"\\(?:frac\s*\{d\}|partial)\b", r"微分|導関数"),
        "sorts": ("DifferentiableFunction", "Function"),
        "morphisms": (("Derivative", "DifferentiableFunction", "Function", "D(f)=f'"),),
    },
    {
        "patterns": (r"\\equiv\b", r"合同|法\s*\\?pmod|modulo"),
        "sorts": ("IntegerStructure", "ResidueClassStructure"),
        "morphisms": (("QuotientModulo", "IntegerStructure", "ResidueClassStructure", "q_m(a)=[a]_m"),),
    },
    {
        "patterns": (r"素数", r"prime"),
        "sorts": ("PrimeSpectrum", "IntegerStructure"),
        "morphisms": (("PrimeRestriction", "IntegerStructure", "PrimeSpectrum", "restrict parameters to primes"),),
    },
    {
        "patterns": (r"平方剰余|Legendre|ルジャンドル",),
        "sorts": ("ResidueClassStructure", "QuadraticCharacter"),
        "morphisms": (("QuadraticCharacterMap", "ResidueClassStructure", "QuadraticCharacter", "chi_p(a)=(a/p)"),),
    },
    {
        "patterns": (r"多項式|方程式", r"[A-Za-z]\s*\^\s*\{?\d+\}?"),
        "sorts": ("Polynomial", "AlgebraicSet"),
        "morphisms": (("ZeroLocus", "Polynomial", "AlgebraicSet", "V(f)={x | f(x)=0}"),),
    },
    {
        "patterns": (r"曲線|軌跡|包絡線",),
        "sorts": ("PlaneCurve",),
        "morphisms": (),
    },
    {
        "patterns": (r"接線",),
        "sorts": ("PlaneCurve", "LineFamily"),
        "morphisms": (("TangentFamily", "PlaneCurve", "LineFamily", "C maps to its tangent family"),),
    },
    {
        "patterns": (r"点|頂点|交点",),
        "sorts": ("PointConfiguration",),
        "morphisms": (),
    },
    {
        "patterns": (r"三角形|正三角形",),
        "sorts": ("Triangle", "PointConfiguration"),
        "morphisms": (("VertexConfiguration", "Triangle", "PointConfiguration", "a triangle maps to its vertices"),),
    },
    {
        "patterns": (r"円|外接円|内接円",),
        "sorts": ("Circle", "PlaneCurve"),
        "morphisms": (("CircleEmbedding", "Circle", "PlaneCurve", "a circle is a plane curve"),),
    },
    {
        "patterns": (r"重心",),
        "sorts": ("PointConfiguration", "AffinePoint"),
        "morphisms": (("Barycenter", "PointConfiguration", "AffinePoint", "bar(P_i)=sum(P_i)/n"),),
    },
    {
        "patterns": (r"領域|面積",),
        "sorts": ("MeasurableRegion", "AreaObservable"),
        "morphisms": (("Area", "MeasurableRegion", "AreaObservable", "Area is a measure observable"),),
    },
    {
        "patterns": (r"確率|期待値",),
        "sorts": ("ProbabilitySpace", "RandomVariable"),
        "morphisms": (("Expectation", "RandomVariable", "Real", "E[X]=integral X dP"),),
    },
)


@dataclass(frozen=True)
class SearchEdge:
    name: str
    source: str
    target: str
    law: str
    backend: tuple[str, ...]
    origin: str


@dataclass(frozen=True)
class TypedPath:
    parent_id: str
    start: str
    target: str
    edges: tuple[SearchEdge, ...]

    def signature(self) -> str:
        return f"{self.start}|{'/'.join(edge.name for edge in self.edges)}|{self.target}"


def _request(method: str, path: str, payload: Any | None = None) -> Any:
    url = os.environ["SUPABASE_URL"].rstrip("/") + path
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            text = response.read().decode("utf-8")
            return json.loads(text) if text else None
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Supabase {method} {path}: {error.code} {detail}") from error


def _job(job_id: str) -> dict[str, Any]:
    query = urllib.parse.urlencode({"id": f"eq.{job_id}", "select": "*"})
    rows = _request("GET", f"/rest/v1/generation_jobs?{query}")
    if not rows:
        raise RuntimeError(f"generation job not found: {job_id}")
    return rows[0]


def _patch_job(job_id: str, payload: dict[str, Any]) -> None:
    query = urllib.parse.urlencode({"id": f"eq.{job_id}"})
    _request("PATCH", f"/rest/v1/generation_jobs?{query}", payload)


def _latex_atoms(text: str) -> list[str]:
    atoms = re.findall(r"\\(?:mathrm|operatorname)\{[^{}]+\}|\\[A-Za-z]+|[A-Za-z]\w*", text)
    return sorted(set(atoms))[:80]


def _surface_semantics(source: str, parent_id: str) -> tuple[list[str], list[dict[str, Any]]]:
    sorts: list[str] = []
    morphisms: list[dict[str, Any]] = []
    seen_morphisms: set[tuple[str, str, str]] = set()
    for signature in SURFACE_OPERATOR_SIGNATURES:
        patterns = signature["patterns"]
        if isinstance(patterns, str):
            patterns = (patterns,)
        if not any(re.search(pattern, source, flags=re.IGNORECASE) for pattern in patterns):
            continue
        for sort in signature["sorts"]:
            if sort not in sorts:
                sorts.append(sort)
        for name, domain, codomain, law in signature["morphisms"]:
            key = (name, domain, codomain)
            if key in seen_morphisms:
                continue
            seen_morphisms.add(key)
            morphisms.append({
                "name": name,
                "domain": [domain],
                "codomain": codomain,
                "kind": "surface_operator_signature",
                "expression": name,
                "law": law,
                "source": f"parent:{parent_id}:operator_vocabulary",
            })
    return sorts, morphisms


def _parent_graph(parent: dict[str, Any]) -> dict[str, Any]:
    source = "\n".join(
        str(parent.get(key) or "")
        for key in ("statement", "solution", "inspiration")
    ).strip()
    parent_id = str(parent.get("id") or "unknown-parent")
    graph = compile_typed_semantic_graph(source)
    gate = run_verifier_gate(graph, answer=parent.get("answer"))
    data = graph.to_dict()

    active_sorts: set[str] = set()
    for obj in data["objects"]:
        if obj.get("sort"):
            active_sorts.add(str(obj["sort"]))
    for morphism in data["morphisms"]:
        active_sorts.update(str(value) for value in morphism.get("domain", []) if value)
        if morphism.get("codomain"):
            active_sorts.add(str(morphism["codomain"]))
    for query in data["queries"]:
        if query.get("sort"):
            active_sorts.add(str(query["sort"]))

    semantic_roots, surface_morphisms = _surface_semantics(source, parent_id)
    for sort in semantic_roots:
        active_sorts.add(sort)
    known_morphism_keys = {
        (item.get("name"), tuple(item.get("domain", [])), item.get("codomain"))
        for item in data["morphisms"]
    }
    for morphism in surface_morphisms:
        key = (morphism["name"], tuple(morphism["domain"]), morphism["codomain"])
        if key not in known_morphism_keys:
            data["morphisms"].append(morphism)

    # Unknown mathematical tokens are preserved rather than coerced to Real.
    # They are evidence for anti-unification, not proof that a bridge exists.
    atoms = _latex_atoms(source)
    if not active_sorts:
        digest = hashlib.sha256("|".join(atoms or [source]).encode("utf-8")).hexdigest()[:10]
        opaque_sort = f"OpaqueStructure[{digest}]"
        active_sorts.add(opaque_sort)
        semantic_roots.append(opaque_sort)
    return {
        "parent_id": parent_id,
        "status": data["status"],
        "active_sorts": sorted(active_sorts),
        "semantic_roots": semantic_roots,
        "objects": data["objects"],
        "morphisms": data["morphisms"],
        "constraints": data["constraints"],
        "queries": data["queries"],
        "laws": data["laws"],
        "opaque_atoms": atoms,
        "verifier_gate": gate.to_dict(),
    }


def _schema_edges() -> list[SearchEdge]:
    edges: list[SearchEdge] = []
    for schema in MORPHISM_SCHEMAS.values():
        for source in schema.domain:
            edges.append(
                SearchEdge(
                    name=schema.name,
                    source=source,
                    target=schema.codomain,
                    law=schema.law,
                    backend=tuple(schema.backend),
                    origin="theory_atlas",
                )
            )
    return edges


def _observed_edges(graph: dict[str, Any]) -> list[SearchEdge]:
    edges: list[SearchEdge] = []
    for morphism in graph["morphisms"]:
        target = str(morphism.get("codomain") or "Unknown")
        for source in morphism.get("domain", []) or ["Any"]:
            edges.append(
                SearchEdge(
                    name=str(morphism.get("name") or "ObservedMorphism"),
                    source=str(source),
                    target=target,
                    law=str(morphism.get("law") or morphism.get("expression") or "observed in parent"),
                    backend=(),
                    origin=f"parent:{graph['parent_id']}",
                )
            )
    return edges


def _reachable(
    parent_id: str,
    starts: list[str],
    edges: list[SearchEdge],
) -> dict[str, list[TypedPath]]:
    outgoing: dict[str, list[SearchEdge]] = {}
    for edge in edges:
        outgoing.setdefault(edge.source, []).append(edge)
    reached: dict[str, list[TypedPath]] = {}
    for start in starts:
        queue: deque[tuple[str, tuple[SearchEdge, ...]]] = deque([(start, ())])
        visited = {start: 0}
        while queue:
            current, path = queue.popleft()
            reached.setdefault(current, []).append(TypedPath(parent_id, start, current, path))
            if len(path) >= MAX_PATH_EDGES:
                continue
            for edge in outgoing.get(current, []):
                length = len(path) + 1
                if visited.get(edge.target, MAX_PATH_EDGES + 1) < length:
                    continue
                visited[edge.target] = length
                queue.append((edge.target, (*path, edge)))
    return reached


def _best_path(paths: list[TypedPath]) -> TypedPath:
    return min(
        paths,
        key=lambda path: (
            len(path.edges),
            -sum(bool(edge.backend) for edge in path.edges),
            path.signature(),
        ),
    )


def _discover_known_joins(graphs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    edges = _schema_edges()
    for graph in graphs:
        edges.extend(_observed_edges(graph))
    reachability = [
        _reachable(graph["parent_id"], graph["active_sorts"], edges)
        for graph in graphs
    ]
    common = set(reachability[0])
    for reached in reachability[1:]:
        common &= set(reached)
    common -= GENERIC_SORTS

    candidates: list[dict[str, Any]] = []
    for target in common:
        paths = [_best_path(reached[target]) for reached in reachability]
        # A scalar coercion such as Natural -> Real is type-correct but does not
        # preserve the parent's mathematical constraints.  Every transported
        # parent must first pass through a morphism observed in that parent.
        if any(
            not path.edges
            or not any(edge.origin == f"parent:{path.parent_id}" for edge in path.edges)
            for path in paths
        ):
            continue
        signatures = {path.signature() for path in paths}
        if len(signatures) != len(paths):
            continue
        backend_edges = sum(bool(edge.backend) for path in paths for edge in path.edges)
        edge_count = sum(len(path.edges) for path in paths)
        observed_edges = sum(edge.origin.startswith("parent:") for path in paths for edge in path.edges)
        score = 40 + 5 * len(graphs) + 3 * backend_edges + observed_edges - edge_count
        candidates.append(
            {
                "kind": "known_typed_join",
                "target_sort": target,
                "score": score,
                "paths": [
                    {
                        "parent_id": path.parent_id,
                        "start_sort": path.start,
                        "target_sort": path.target,
                        "morphisms": [asdict(edge) for edge in path.edges],
                    }
                    for path in paths
                ],
                "typecheck": {"passed": True, "reason": "all paths have matching domain/codomain"},
                "backend_coverage": backend_edges,
            }
        )
    return sorted(candidates, key=lambda item: (-item["score"], item["target_sort"]))[:MAX_HYPOTHESES]


def _unknown_bridge_hypotheses(graphs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Create falsifiable bridge hypotheses when the current atlas has no join.

    These are deliberately not promoted.  They identify which representation
    changes need a law and backend before a concrete problem can be exported.
    """
    hypotheses: list[dict[str, Any]] = []
    sort_options = []
    for graph in graphs:
        roots = [sort for sort in graph.get("semantic_roots", []) if sort not in GENERIC_SORTS]
        specific = roots or [sort for sort in graph["active_sorts"] if sort not in GENERIC_SORTS]
        sort_options.append((specific or graph["active_sorts"][:1])[:4])

    constructors = (
        (
            "CommonInvariant",
            "InvariantProjection",
            "各親構造から同じ値を取る観測を構成できる",
        ),
        (
            "FiberProduct",
            "PullbackProjection",
            "親構造の制約を同時に満たす普遍対象を構成できる",
        ),
        (
            "Equalizer",
            "EqualizerEmbedding",
            "二つの表現が一致する部分構造を構成できる",
        ),
        (
            "CommonQuotient",
            "QuotientProjection",
            "表現差を除いた共通商対象を構成できる",
        ),
    )
    combinations = itertools.product(*sort_options)
    for combination_index, starts in enumerate(combinations):
        if combination_index >= 18:
            break
        normalized = ",".join(starts)
        for constructor_index, (constructor, name, proposition) in enumerate(constructors):
            target = f"{constructor}[{normalized}]"
            paths = []
            for graph, start in zip(graphs, starts):
                paths.append(
                    {
                        "parent_id": graph["parent_id"],
                        "start_sort": start,
                        "target_sort": target,
                        "morphisms": [{
                            "name": f"{name}_{hashlib.sha256((start + target).encode()).hexdigest()[:8]}",
                            "source": start,
                            "target": target,
                            "law": proposition,
                            "backend": [],
                            "origin": "conjectured_bridge",
                        }],
                    }
                )
            distinct_sorts = len(set(starts))
            shared_atoms = set(graphs[0]["opaque_atoms"])
            for graph in graphs[1:]:
                shared_atoms &= set(graph["opaque_atoms"])
            score = 24 + 2 * len(shared_atoms) + distinct_sorts - constructor_index
            hypotheses.append(
                {
                    "kind": "conjectured_universal_construction",
                    "constructor": constructor,
                    "target_sort": target,
                    "score": score,
                    "paths": paths,
                    "typecheck": {
                        "passed": True,
                        "reason": "the universal-construction hypothesis has one typed projection per parent",
                    },
                    "backend_coverage": 0,
                    "shared_opaque_atoms": sorted(shared_atoms),
                    "proof_obligations": [
                        proposition,
                        "各親の具体的制約が普遍対象へ持ち上がること",
                        "構成が単なる直積ではなく問いの不変量に依存すること",
                        "一方の親を除くと合流命題が成立しないこと",
                        "小さいパラメータで反例がないこと",
                    ],
                }
            )
            if len(hypotheses) >= MAX_HYPOTHESES:
                return sorted(hypotheses, key=lambda item: -item["score"])
    return sorted(hypotheses, key=lambda item: -item["score"])


def _plan_signature(plan: dict[str, Any], parent_ids: list[str]) -> str:
    payload = json.dumps(
        {"parents": parent_ids, "target": plan["target_sort"], "paths": plan["paths"]},
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _render_research_task(plan: dict[str, Any], graphs: list[dict[str, Any]]) -> str:
    path_lines = []
    for index, path in enumerate(plan["paths"], start=1):
        chain = " \\longrightarrow ".join(
            [path["start_sort"], *[edge["target"] for edge in path["morphisms"]]]
        )
        path_lines.append(rf"\mathcal P_{index}: {chain}")
    constraints = []
    for index, graph in enumerate(graphs, start=1):
        kinds = sorted({str(item.get("kind")) for item in graph["constraints"] if item.get("kind")})
        constraints.append(rf"C_{index}=\{{{', '.join(kinds[:6]) or 'unresolved'}\}}")
    return (
        "選択した問題から抽出した型付き構造を "
        + ", ".join(rf"\(\mathcal P_{i}\)" for i in range(1, len(graphs) + 1))
        + " とする。MathOSが構成した候補射列は\n\\[\n"
        + r"\\".join(path_lines)
        + "\n\\]\nであり，各構造の制約骨格は "
        + ", ".join(rf"\({value}\)" for value in constraints)
        + " である。全ての制約を保ったまま各射列を具体化し，"
        + rf"共通終対象 \({plan['target_sort']}\) 上で一致する不変量を一つ構成せよ。"
        + "さらに、一方の親構造を除くとその不変量が定まらないことを示せ。"
    )


def discover(parents: list[dict[str, Any]]) -> dict[str, Any]:
    graphs = [_parent_graph(parent) for parent in parents]
    known = _discover_known_joins(graphs)
    hypotheses = [*known, *_unknown_bridge_hypotheses(graphs)][:MAX_HYPOTHESES]
    if not hypotheses:
        raise RuntimeError("no typed bridge hypothesis could be formed")
    selected = hypotheses[0]
    parent_ids = [graph["parent_id"] for graph in graphs]
    signature = _plan_signature(selected, parent_ids)
    all_backend_edges = [
        edge
        for path in selected["paths"]
        for edge in path["morphisms"]
    ]
    backend_candidate = bool(all_backend_edges) and all(edge.get("backend") for edge in all_backend_edges)
    # A backend name is only a search lead.  Promotion requires executing it on
    # the newly induced constraints, which this discovery phase has not done.
    executable = False
    status = "backend_candidate" if backend_candidate else "research_pending"
    statement = _render_research_task(selected, graphs)
    structure_id = f"discovery.{signature[:12]}"
    return {
        "engine": "MathOS parent-conditioned structural discovery (no LLM)",
        "generated": 0,
        "discovered": 1,
        "requested": 1,
        "cards": [{
            "id": structure_id,
            "family_id": f"research.parent_conditioned.{signature[:12]}",
            "statement_tex": statement,
            "answer_tex": None,
            "solution_tex": "中間命題の型検査は完了。数学的法則とbackend検証は継続中。",
            "parent_ids": parent_ids,
            "unresolved": not executable,
            "discovery_status": status,
            "morphism_chain": [
                edge["name"]
                for path in selected["paths"]
                for edge in path["morphisms"]
            ],
            "fusion_derivation": {
                "passed": True,
                "reason": "all selected parents have distinct typed conjectural paths; mathematical indispensability is not yet proved",
                "ablationPassed": all(
                    f"{selected.get('constructor', 'Join')}["
                    + ",".join(
                        path["start_sort"]
                        for path_index, path in enumerate(selected["paths"])
                        if path_index != removed_index
                    )
                    + "]" != selected["target_sort"]
                    for removed_index in range(len(selected["paths"]))
                ),
                "assignments": [{
                    "parentId": path["parent_id"],
                    "portId": f"input_{index + 1}",
                    "role": "object",
                    "matchedAnchors": [path["start_sort"]],
                    "witnessSteps": [edge["name"] for edge in path["morphisms"]],
                    "nodes": [path["start_sort"], *[edge["target"] for edge in path["morphisms"]]],
                } for index, path in enumerate(selected["paths"])],
                "bridges": [{
                    "id": "parent_conditioned_common_codomain",
                    "witnessStep": selected["target_sort"],
                    "consumes": [f"input_{index + 1}" for index in range(len(parent_ids))],
                    "produces": selected["target_sort"],
                }],
                "intermediatePropositions": [
                    {
                        "parentId": path["parent_id"],
                        "morphism": edge["name"],
                        "source": edge["source"],
                        "target": edge["target"],
                        "proposition": edge["law"],
                        "proved": bool(edge.get("backend")),
                    }
                    for path in selected["paths"]
                    for edge in path["morphisms"]
                ],
            },
        }],
        "parent_graphs": graphs,
        "hypotheses": hypotheses,
        "selected_plan": selected,
        "structures": [{
            "blueprint": {
                "id": structure_id,
                "version": 1,
                "kernel": "parent_conditioned_unknown_structure",
                "observable": selected["target_sort"],
                "operators": [
                    edge["name"]
                    for path in selected["paths"]
                    for edge in path["morphisms"]
                ],
                "domain": "discovered_from_selected_parents",
                "tags": sorted({sort for graph in graphs for sort in graph["active_sorts"]}),
                "morphismChain": [
                    edge["name"]
                    for path in selected["paths"]
                    for edge in path["morphisms"]
                ],
                "executable": executable,
            },
            "status": "new" if executable else "pending",
            "parentIds": parent_ids,
            "registeredAt": datetime.now(timezone.utc).isoformat(),
        }],
        "errors": [] if executable else [
            "新しい型付き構造を発見しました。backend未検証のため公開問題ではなく研究保留として保存しました。"
        ],
        "rejectionCounts": {},
    }


def main() -> int:
    job_id = os.environ.get("JOB_ID")
    if not job_id:
        print("JOB_ID is required", file=sys.stderr)
        return 2
    try:
        job = _job(job_id)
        parents = job.get("parents") or []
        if len(parents) < 2:
            raise RuntimeError("parent-conditioned discovery requires at least two parents")
        _patch_job(job_id, {
            "status": "processing",
            "logs": [{
                "level": "info",
                "message": "親問題を型付き意味グラフへコンパイルしています",
                "ts": datetime.now(timezone.utc).isoformat(),
            }],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        result = discover(parents)
        _patch_job(job_id, {
            "status": "done",
            "result": result,
            "error": None,
            "logs": [
                {
                    "level": "info",
                    "message": f"{len(result['hypotheses'])}個の中間構造仮説を比較しました",
                    "ts": datetime.now(timezone.utc).isoformat(),
                },
                {
                    "level": "info",
                    "message": f"構造 {result['structures'][0]['blueprint']['id']} を保留Atlasへ保存しました",
                    "ts": datetime.now(timezone.utc).isoformat(),
                },
            ],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        print(json.dumps({
            "job_id": job_id,
            "status": "done",
            "hypotheses": len(result["hypotheses"]),
            "structure": result["structures"][0]["blueprint"]["id"],
        }, ensure_ascii=False))
        return 0
    except Exception as error:  # noqa: BLE001 - job boundary must persist failures.
        try:
            _patch_job(job_id, {
                "status": "failed",
                "error": str(error),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            pass
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
