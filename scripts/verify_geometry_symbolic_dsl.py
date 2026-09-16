"""Replay recorded symbolic executions, separate from autonomous search."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from math_os_prototype import geometry_contracts as gc
from math_os_prototype import geometry_semantic_dsl as dsl
from math_os_prototype.geometry_symbolic_dsl import certify_compilation
from math_os_prototype.theory_geometry import GeometryDomain
from math_os_prototype.theory_geometry_feedback import GeometryLibrary
from worker.backend.jgex_exact_constraint_bridge import _prepare_exact_system


def verify(run):
    started = time.perf_counter()
    bank = GeometryLibrary()
    for h in json.loads((run/"archive.json").read_text()):
        bank.register(h)
    histories = json.loads((run/"histories.json").read_text())
    rows = []
    for history in histories:
        source, target = history["source_statement"], history["result_statement"]
        domain = GeometryDomain({"statement": source}, {})
        extension = domain.certify_extension(source, target)
        unabridged = domain.certify_extension(source, history.get("unabridged_statement", target))
        execution = history["execution"]
        primitive = dsl.expand(execution["call"], bank.table)
        if primitive != execution["primitive"]:
            raise ValueError("call expansion changed")
        compiled = certify_compilation(source, target, primitive, execution["outputs"])
        expanded = dsl.expand(history["program"], bank.table)
        if expanded != history["primitive_expansion"]:
            raise ValueError("learning program expansion changed")
        # Compare the full learning term (including input constructions) to
        # the actual output. This checks the acquisition record, not just the call.
        before = _prepare_exact_system(source, enable_structural_lemmas=False)[0]
        after = _prepare_exact_system(target, enable_structural_lemmas=False)[0]
        expected = gc._JGEXElaborator()
        expected.coordinates.update(before.coordinates)
        steps, output = gc.dag(expanded, fragment=dsl.FRAGMENT)
        for step in steps:
            dsl.FRAGMENT.primitive(expected, step["family"], step["output"], step["inputs"])
        actual = execution["outputs"][-1][0]
        equal = all(gc.exact_zero(a-b) for a, b in zip(expected.coordinates[output], after.coordinates[actual], strict=True))
        passed = (extension["accepted"] and unabridged["accepted"]
                  and unabridged == history.get("unabridged_extension", history["replay"]["certificate"])
                  and extension == history["replay"]["certificate"]
                  and compiled == history["compilation_certificate"]
                  and compiled["all_residuals_zero"] and equal)
        rows.append({"history": history["id"], "passed": passed, "learning_term_matches_execution": equal})
    return {"passed": all(r["passed"] for r in rows), "histories": len(rows),
            "archive_definitions_recertified": len(bank.archive), "rows": rows,
            "seconds": time.perf_counter()-started,
            "scope": "independent symbolic replay, not a second autonomous search"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", type=Path, required=True)
    args = p.parse_args()
    result = verify(args.run)
    (args.run/"independent-replay.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
