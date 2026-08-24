"""Record source provenance separately from MORTRA runtime integration claims."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class SourceSpec:
    name: str
    directory: str
    integration: str
    evidence: tuple[str, ...] = ()
    limitation: str = ""
    paper_method: str = ""
    benchmark_artifacts: tuple[str, ...] = ()


SOURCES = (
    SourceSpec(
        "C-RASP state-tracking theory",
        "state-tracking-crasp",
        "reference-controller-audit",
        evidence=(
            "data/crasp-upstream-decider-reproduction-2026-08-22.json",
        ),
        limitation=(
            "the upstream decider classifies regular-language state tracking; "
            "a MORTRA proof search is not itself supplied as a regular expression"
        ),
        paper_method=(
            "algebraic decomposition decides which finite-state languages admit "
            "C-RASP length generalization"
        ),
    ),
    SourceSpec(
        "AlphaGeometry",
        "AlphaGeometry",
        "reference-only",
        limitation="official DDAR/LM runtime is not the MORTRA scoring process",
        paper_method="DD+AR closes a symbolic proof graph; a language model proposes auxiliary constructions",
    ),
    SourceSpec("AlphaGeometry2", "alphageometry2", "reference-only", limitation="public DDAR core is not directly invoked by MORTRA"),
    SourceSpec("AutoGPS", "AutoGPS", "reference-only"),
    SourceSpec("Euclean", "Euclean", "reference-only"),
    SourceSpec("FGPS", "FGPS", "reference-only"),
    SourceSpec(
        "FormalGeo",
        "FormalGeo",
        "native-runtime-bridge",
        evidence=(
            "scripts/run_formalgeo_runtime.py",
            "worker/backend/formalgeo_runtime_bridge.py",
            "worker/backend/jgex_formalgeo_translator.py",
            "worker/backend/test_formalgeo_runtime_bridge.py",
            "worker/backend/test_jgex_formalgeo_translator.py",
            "scripts/experiment_hageo_passk.py",
            "worker/backend/construction_block_proof_dag.py",
            "worker/backend/local_polynomial_elimination.py",
            "worker/backend/chordal_buchberger_elimination.py",
            "scripts/experiment_construction_block_dag_cohort.py",
            "worker/backend/test_construction_block_proof_dag.py",
            "worker/backend/test_chordal_buchberger_elimination.py",
        ),
        limitation=(
            "official GPL runtime is isolated behind JSON; GDL construction "
            "coverage is partial and FormalGeo obligations still require "
            "Newclid/GCLC replay before MORTRA counts a solution"
        ),
        paper_method="GDL theorem instances support forward hypergraph closure and backward AND/OR goal decomposition",
    ),
    SourceSpec(
        "GCLC",
        "gclc",
        "native-runtime-bridge",
        evidence=(
            "worker/backend/gclc_newclid_bridge.py",
            "worker/backend/jgex_gclc_translator.py",
            "scripts/experiment_gclc_newclid_certificate_bridge.py",
        ),
        paper_method="Area, Wu, and Groebner provers emit symbolic proof obligations and proof artifacts",
        benchmark_artifacts=(
            "data/gclc-newclid-concrete-certificate-bridge-2026-08-15.json",
            "data/hageo-certified-capability-union-gclc-2026-08-21.json",
        ),
    ),
    SourceSpec("GenesisGeo", "GenesisGeo", "dataset-and-grammar-input", evidence=("scripts/experiment_hageo_passk.py",)),
    SourceSpec("GeoParser", "GeoParser", "reference-only"),
    SourceSpec(
        "HAGeo",
        "HAGeo",
        "independent-reconstruction",
        evidence=("scripts/experiment_hageo_passk.py", "scripts/benchmark_hageo_passk_cohort.py"),
        limitation="upstream repository states that full code is not released",
        paper_method="N-round/K-trajectory auxiliary construction with six numerical-incidence candidate families",
        benchmark_artifacts=("data/hageo-certified-capability-union-gclc-2026-08-21.json",),
    ),
    SourceSpec(
        "Hilbert-Geo",
        "Hilbert-Geo",
        "predicate-schema-adaptation",
        evidence=(
            "worker/backend/mortra_geometry_content_dictionary.py",
            "worker/backend/test_mortra_geometry_content_dictionary.py",
        ),
        limitation=(
            "the public predicate schema informed MORTRA's independent typed "
            "2D/3D vocabulary; its theorem bank is not copied into the runtime"
        ),
        paper_method="typed spatial predicates and theorem-guided 3D reasoning",
    ),
    SourceSpec(
        "LEAP",
        "LEAP",
        "paper-derived-symbolic-adaptation",
        evidence=(
            "worker/backend/typed_open_proof_dag.py",
            "worker/backend/test_typed_open_proof_dag.py",
            "scripts/experiment_proof_dag_progress_ablation.py",
        ),
        limitation=(
            "no official code checkout was found; MORTRA implements an exact, "
            "LLM-free decomposition reviewer and verifier-feedback ranking"
        ),
        paper_method="OR-rooted subgoal DAG with proof feedback and no-progress review",
        benchmark_artifacts=(
            "data/proof-dag-progress-ablation-frozen5-2026-08-22.json",
            "data/proof-dag-feedback-routing-ablation-frozen5-2026-08-22.json",
        ),
    ),
    SourceSpec(
        "OpenMath Content Dictionaries",
        "OpenMath-CDs",
        "semantic-schema-adaptation",
        evidence=(
            "worker/backend/mortra_geometry_content_dictionary.py",
            "worker/backend/test_mortra_geometry_content_dictionary.py",
        ),
        limitation=(
            "MORTRA reuses public symbol URIs where semantics agree and keeps "
            "new spatial symbols in a private content dictionary"
        ),
        paper_method="content dictionaries assign stable semantics and signatures to symbols",
    ),
    SourceSpec(
        "MMT",
        "MMT",
        "independent-theory-view-runtime",
        evidence=(
            "worker/backend/mmt_exact_coordination.py",
            "worker/backend/hageo_mmt_certificate_bridge.py",
            "worker/backend/test_mmt_exact_coordination.py",
            "worker/backend/test_hageo_mmt_certificate_bridge.py",
            "data/six-paper-mmt-hageo-runtime-smoke-2007p4-2026-08-22.json",
        ),
        limitation=(
            "this is an independent executable subset of theory views and exact "
            "certificate transport, not an embedding of the Scala MMT server"
        ),
        paper_method="foundation-independent theory graphs and meaning-preserving views",
    ),
    SourceSpec("HyperGNet", "HyperGNet", "reference-only"),
    SourceSpec(
        "Newclid/Yuclid",
        "Newclid",
        "native-runtime",
        evidence=(
            "worker/backend/yuclid_native_verifier.py",
            "scripts/benchmark_hageo409_native.py",
        ),
        paper_method="Native deductive-database and algebraic-reasoning proof replay",
        benchmark_artifacts=("data/yuclid-imo-ag-30-all-ar-2026-08-15.json",),
    ),
    SourceSpec(
        "Seed-Prover",
        "Seed-Prover",
        "unusable-checkout",
        limitation="local checkout has extensive missing or modified files and is not evidence of reproduction",
    ),
    SourceSpec(
        "Sheaf-ADMM",
        "sheaf-admm",
        "partial-independent-adaptation",
        evidence=(
            "worker/backend/native_formal_obligation_sheaf.py",
            "worker/backend/symbolic_sheaf_learning.py",
            "worker/backend/test_native_formal_obligation_sheaf.py",
            "worker/backend/test_symbolic_sheaf_learning.py",
            "data/six-paper-sheaf-ablation-2026-08-22.json",
        ),
        limitation=(
            "official JAX/Flax encoder training and paper task reproduction are "
            "not in the MORTRA scoring path; frozen MORTRA tests have not shown "
            "an additional certified solve"
        ),
        paper_method="Overlapping local views solve convex subproblems and coordinate through sheaf-constrained ADMM",
    ),
    SourceSpec("TongGeometry", "tong-geometry", "reference-derived-view", evidence=("scripts/experiment_newclid_construction_stalk.py",)),
    SourceSpec("egglog", "egglog", "library-runtime", evidence=("worker/backend/primitive_law_induction.py",)),
    SourceSpec("cvc5", "cvc5", "library-runtime", evidence=("worker/backend/primitive_law_induction.py",)),
    SourceSpec("Ruler", "ruler-oopsla21", "reference-only"),
    SourceSpec("LNN", "LNN", "reference-only"),
    SourceSpec("Scallop", "scallop", "reference-only", evidence=("scripts/experiment_typed_logic_circuit.py",)),
    SourceSpec("DiffLogic", "difflogic", "reference-only"),
)


def _git(path: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ("git", "-C", str(path), *arguments),
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(source_root: Path) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for spec in SOURCES:
        checkout = source_root / spec.directory
        evidence = []
        for relative in spec.evidence:
            path = ROOT / relative
            evidence.append(
                {
                    "path": relative,
                    "exists": path.is_file(),
                    "sha256": _sha256(path) if path.is_file() else None,
                }
            )
        benchmark_artifacts = []
        for relative in spec.benchmark_artifacts:
            path = ROOT / relative
            benchmark_artifacts.append(
                {
                    "path": relative,
                    "exists": path.is_file(),
                    "sha256": _sha256(path) if path.is_file() else None,
                }
            )
        dirty_lines = _git(checkout, "status", "--porcelain").splitlines()
        rows.append(
            {
                **asdict(spec),
                "checkout_exists": checkout.is_dir(),
                "git_head": _git(checkout, "rev-parse", "HEAD"),
                "origin": _git(checkout, "remote", "get-url", "origin"),
                "dirty_entry_count": len(dirty_lines),
                "evidence": evidence,
                "benchmark_artifacts": benchmark_artifacts,
                "runtime_claim_supported": (
                    spec.integration in {
                        "independent-theory-view-runtime",
                        "native-runtime",
                        "native-runtime-bridge",
                        "library-runtime",
                    }
                    and bool(evidence)
                    and all(item["exists"] for item in evidence)
                ),
                "score_claim_supported": (
                    bool(benchmark_artifacts)
                    and all(item["exists"] for item in benchmark_artifacts)
                ),
            }
        )
    return {
        "experiment": "mortra_external_source_integration_audit",
        "protocol": {
            "clone_is_not_integration": True,
            "documentation_is_not_runtime_evidence": True,
            "independent_reconstruction_is_not_full_reproduction": True,
            "score_claim_requires_separate_benchmark_artifact": True,
            "paper_method_must_be_recorded_before_derived_implementation_claim": True,
        },
        "summary": {
            "sources": len(rows),
            "native_or_library_runtime": sum(
                bool(row["runtime_claim_supported"]) for row in rows
            ),
            "reference_only": sum(
                row["integration"] == "reference-only" for row in rows
            ),
            "complete_reverse_engineering_claim": False,
        },
        "sources": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-root",
        type=Path,
        default=Path.home() / ".cache" / "mortra-research-sources",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.source_root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
