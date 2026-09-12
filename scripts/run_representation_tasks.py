"""The normal entry point: hand in tasks, let the run find and use representations.

    python scripts/run_representation_tasks.py --output <dir> \
        --task axis1 --task c1-plus-c2 --task axis1-from-AG \
        --task axis1-collision-free

By default, look for a compatible stored certificate, then close the task's own
evaluation with the existing observable-basis prover. Explicit comparison routes
also expose the former candidate grammar, the exact concrete route and reuse
without acquisition. Check maximum, maximizing word count and distribution by
independent enumeration at the declared small lengths.

Nothing about a representation is passed in. The tasks are named, and their
content is fixed in `fold_tasks.TASKS`, written before any of this was run.

Afterwards, every representation the run kept is saved to one ledger, and the
last phase answers a task again by reading that ledger instead of acquiring
anything -- which is the reuse the whole arrangement is for.
"""
from pathlib import Path
import argparse
import json
import sys
import time
from hashlib import sha256
import platform

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from math_os_prototype import fold_tasks
from math_os_prototype import representation_ledger as ledgers
from math_os_prototype import representation_policy as policy
from math_os_prototype import self_directed_search as search


def ascii_page(traces, reuse):
    """The picture, from the data these runs actually produced."""
    lines = []
    for name, trace in traces.items():
        lines.append("=" * 78)
        lines.append(f"TASK  {trace['task']}")
        lines.append("=" * 78)
        contract = trace["task_contract"]
        lines.append(f"  counts   {contract['counted']}")
        lines.append(f"  state    {contract['state']}")
        lines.append(f"  legality {contract['legality']}")
        lines.append("     |")
        lines.append(f"     v  route {trace.get('route', 'enumerate')} offers "
                     f"{len(trace['candidates_offered'])} candidates")
        lines.append("  CANDIDATES")
        closure_refusals = trace.get("refused_at_closure", [])
        certificate_refusals = trace.get("refused_by_certificate", [])
        lines.append(f"     |   refused at the closure prover : {len(closure_refusals)}")
        lines.append(f"     |   refused by the certificate    : {len(certificate_refusals)}")
        reasons = {}
        for row in certificate_refusals:
            for why in row["refused_by"]:
                reasons[why] = reasons.get(why, 0) + 1
        for why, count in sorted(reasons.items()):
            lines.append(f"     |       {why}: {count}")
        witness = next((row["counterexample"] for row in certificate_refusals
                        if row.get("counterexample")), None)
        if witness:
            lines.append(f"     |       one counterexample: "
                         f"{witness.get('check')} at length "
                         f"{witness.get('length')}, "
                         f"{witness.get('word_a')!r} -> {witness.get('value_a')} "
                         f"vs {witness.get('word_b')!r} -> {witness.get('value_b')}")
        lines.append(f"     |   admitted                      : "
                     f"{len(trace.get('admitted', []))}")
        classes = trace.get("span_classes", [])
        if classes:
            lines.append(f"     v   spanning {len(classes)} distinct space(s)")
            for row in classes:
                lines.append(f"  SPACE  {row['representative']} (dim "
                             f"{row['dimension']}) <- {row['size']} candidate(s)")
        if "stopped" in trace:
            lines.append("     |")
            lines.append(f"  STOPPED  {trace['stopped']}")
            for key, value in trace.get("stopping_point", {}).items():
                lines.append(f"     |   {key}: {value}")
            lines.append("")
            continue
        lines.append("     |")
        lines.append(f"     v   Pareto fronts {trace['selection']['front_sizes']}, "
                     "no weighting and no total")
        selected = trace["selected"]
        learned = bool(selected.get("basis"))
        lines.append(f"  SELECTED  {selected['observable']}  dim "
                     f"{selected['dimension']}  front {selected['front']}")
        if learned:
            lines.append(f"     |   basis    {selected['basis']}")
            lines.append(f"     |   readout  qbar(z) = {selected['readout']} . z")
        else:
            lines.append("     |   concrete answer selected; any acquisition paid "
                         "before selection remains in the acquisition record")
        tie = trace.get("tie_break_workload", {})
        if tie.get("measured"):
            lines.append(f"     |   tie-break over the declared workload "
                         f"n={tie['lengths']} (wall time, then grammar order):")
            for candidate, found in sorted(
                    tie["measured"].items(),
                    key=lambda kv: kv[1]["total_wall_time"]):
                lines.append(f"     |       {candidate[:40]:<40s} "
                             f"{found['acquisition_wall_time']:6.2f}s acquire + "
                             f"{found['workload_wall_time']:6.2f}s run = "
                             f"{found['total_wall_time']:6.2f}s   "
                             f"{found['workload_nodes']:>7} nodes")
            if tie.get("units_disagree"):
                lines.append(f"     |       units disagree -- by wall time "
                             f"{tie['order_by_wall_time'][0][:34]}, by nodes "
                             f"{tie['order_by_workload_nodes'][0][:34]}")
        for row in trace.get("learned_alternatives", [])[:3]:
            lines.append(f"     |   learned alternative left on front "
                         f"{row['front']}: {row['observable']} dim "
                         f"{row['dimension']}")
        lines.append("     |")
        lines.append("     v   layered DP, merging on "
                     + ("the certified observation" if learned
                        else "the concrete state")
                     + ", multiplicity carried")
        for check in trace["verification"]:
            lines.append(f"  n={check['length']:<3} enumeration "
                         f"v_max={check['by_enumeration']['v_max']:>4} "
                         f"count={check['by_enumeration']['count_max']:<8} "
                         f"| agrees {check['answers_agree']} "
                         f"dist {check['distributions_agree']} "
                         f"| {check['nodes_enumerating']} -> "
                         f"{check['nodes_with_representation']} nodes")
        for answer in trace["answers"]:
            lines.append(f"  n={answer['length']:<3} DP only       "
                         f"v_max={answer['answer']['v_max']:>4} "
                         f"count={answer['answer']['count_max']:<8} "
                         f"| NOT enumerated "
                         f"| {answer['search_nodes']} nodes, "
                         f"{answer['classes_expanded']} classes")
        lines.append("")
    if reuse:
        lines.append("=" * 78)
        lines.append("REUSE: the same store, read back for another length")
        lines.append("=" * 78)
        for name, row in reuse.items():
            if not row.get("reused"):
                lines.append(f"  {name}: not reused -- {row.get('reason')}")
                continue
            lines.append(f"  {name}: entry {row['from_entry']} "
                         f"({row['observable']}, dim {row['dimension']}), "
                         f"acquired again: {row['acquired_again']}, "
                         f"prover calls: {row['cost']['proof_calls']}")
            for answer in row["answers"]:
                lines.append(f"      n={answer['length']}  "
                             f"v_max={answer['answer']['v_max']} "
                             f"count={answer['answer']['count_max']}  "
                             f"{answer['search_nodes']} nodes, "
                             f"{answer['classes_expanded']} classes, "
                             f"{row['cost']['wall_time']:.2f}s for the call")
            lines.append(f"      instrumented primitive calls for the call: "
                         f"{row['cost']['primitive_calls']} -- the matrix "
                         f"arithmetic this route uses is not wrapped, so read "
                         f"the node count, not this zero")
        lines.append("")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="representation-task-results")
    parser.add_argument("--task", action="append", dest="tasks",
                        default=None)
    parser.add_argument("--degree", type=int, default=1)
    parser.add_argument("--max-terms", type=int, default=2)
    parser.add_argument("--certificate-depth", type=int, default=4)
    parser.add_argument("--probe-length", type=int, default=4)
    parser.add_argument("--verify", type=int, nargs="*", default=[5, 6, 7])
    parser.add_argument("--answer", type=int, nargs="*", default=[10, 12])
    parser.add_argument("--reuse-length", type=int, default=14)
    parser.add_argument("--route", choices=("existing", "enumerate", "q-directed", "reuse"),
                        default="q-directed")
    parser.add_argument("--ledger", type=Path, help="stored certified representations")
    arguments = parser.parse_args(argv)
    names = arguments.tasks or ["axis1", "c1-plus-c2", "axis1-from-AG",
                                "axis1-collision-free"]

    output = Path(arguments.output)
    output.mkdir(parents=True, exist_ok=True)
    if (output / "input-seal.json").exists() or (output / "traces.json").exists():
        parser.error("output already holds a run; use a new directory")
    root = Path(__file__).resolve().parents[1]
    sources = sorted([*root.glob("math_os_prototype/*.py"),
                      root / "scripts/run_representation_tasks.py"])
    def source_hashes():
        return {str(p.relative_to(root)): sha256(p.read_bytes()).hexdigest() for p in sources}
    frozen = source_hashes()
    (output / "input-seal.json").write_text(json.dumps({
        "arguments": vars(arguments), "sources": frozen,
        "python": platform.python_version(),
        "ledger_sha256": sha256(arguments.ledger.read_bytes()).hexdigest()
                           if arguments.ledger else None,
        "note": "version checks, not a proof of non-intervention"},
        indent=2, default=str), encoding="utf-8")
    load_started = time.perf_counter()
    book = ledgers.Ledger.load(arguments.ledger) if arguments.ledger else ledgers.Ledger()
    load_wall_time = time.perf_counter() - load_started
    traces, reuse = {}, {}

    for name in names:
        task = fold_tasks.task_by_name(name)
        print(f"\n=== {name}: {task.name} ===", flush=True)
        trace, book = search.solve(
            task, route=arguments.route, degree=arguments.degree, max_terms=arguments.max_terms,
            coefficients=(1, -1) if arguments.max_terms > 1 else (1,),
            certificate_depth=arguments.certificate_depth,
            probe_length=arguments.probe_length,
            verify_lengths=tuple(arguments.verify),
            answer_lengths=tuple(arguments.answer),
            ledger=book, progress=lambda line: print(line, flush=True))
        traces[name] = trace
        (output / "traces.json").write_text(
            json.dumps({"tasks": traces, "reuse": reuse}, indent=2, default=str),
            encoding="utf-8")
        book.save(output / "ledger.json")
        print(search.render(trace), flush=True)

    print("\n=== reuse from the store, no acquisition ===", flush=True)
    book.save(output / "ledger.json")
    reload_started = time.perf_counter()
    book = ledgers.Ledger.load(output / "ledger.json")
    reload_wall_time = time.perf_counter() - reload_started
    for name in names:
        task = fold_tasks.task_by_name(name)
        row = search.solve_from_store(task, book, verify_lengths=(),
                                      answer_lengths=(arguments.reuse_length,))
        reuse[name] = row
        if row.get("reused"):
            print(f"  {name}: {row['observable']} from entry {row['from_entry']}, "
                  f"n={arguments.reuse_length} -> "
                  f"v_max={row['answers'][0]['answer']['v_max']} "
                  f"count={row['answers'][0]['answer']['count_max']}", flush=True)
        else:
            print(f"  {name}: not reused -- {row['reason']}", flush=True)

    (output / "traces.json").write_text(
        json.dumps({"tasks": traces, "reuse": reuse}, indent=2, default=str),
        encoding="utf-8")
    (output / "result-seal.json").write_text(json.dumps({
        "sources_unchanged": frozen == source_hashes(),
        "completed": True,
        "all_checked_answers_agree": all(t.get("all_checks_agree", True)
                                         for t in [*traces.values(), *reuse.values()]),
        "stopped_tasks": [name for name, trace in traces.items() if "stopped" in trace],
        "ledger_load_wall_time": load_wall_time,
        "ledger_reload_wall_time": reload_wall_time,
        "note": "stopped task records remain stopped; completion is not universal success"},
        indent=2), encoding="utf-8")
    book.save(output / "ledger.json")
    (output / "policy.txt").write_text(
        "\n\n".join(policy.explain(book.all_entries(),
                                   task=fold_tasks.task_by_name(name).name)
                    for name in names) + "\n", encoding="utf-8")
    page = ascii_page(traces, reuse)
    (output / "ascii.txt").write_text(page + "\n", encoding="utf-8")
    for name, trace in traces.items():
        (output / f"run-{name}.txt").write_text(search.render(trace) + "\n",
                                                encoding="utf-8")
    print()
    print(page)
    print(f"written to {output.resolve()}")
    agrees = all(t.get("all_checks_agree", True) for t in [*traces.values(), *reuse.values()])
    return 0 if frozen == source_hashes() and agrees else 2


if __name__ == "__main__":
    raise SystemExit(main())
