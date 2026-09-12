"""Hand one task to the system and let it work, with nothing picked by hand.

    python scripts/run_self_directed_task.py --output <directory>

The task states its transition, the quantity it reads, its goal and which words
it may use. Which observable to try, which representation closes, whether that
representation preserves what the task needs, and which of the surviving ones to
use are all decided by the run: by the grammar's enumeration, the closure
prover, the certificate, and a Pareto frontier over measured components.

`--collision-free` asks the constrained variant of the same task, which every
representation of the state is expected to be refused for -- self-intersection
is a property of the word, not of the state it ends in. That refusal is the
point of running it.
"""
from pathlib import Path
import argparse
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from math_os_prototype import fold_tasks
from math_os_prototype import representation_policy as policy
from math_os_prototype import self_directed_search as search


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="self-directed-results")
    parser.add_argument("--axis", type=int, default=0)
    parser.add_argument("--collision-free", action="store_true")
    parser.add_argument("--degree", type=int, default=1)
    parser.add_argument("--max-terms", type=int, default=1)
    parser.add_argument("--certificate-depth", type=int, default=5)
    parser.add_argument("--probe-length", type=int, default=5)
    parser.add_argument("--verify", type=int, nargs="*", default=[5, 6, 7])
    parser.add_argument("--answer", type=int, nargs="*", default=[10, 12, 14])
    arguments = parser.parse_args(argv)

    task = fold_tasks.displacement_task(axis=arguments.axis,
                                        collision_free=arguments.collision_free)
    print(f"task: {task.name}", flush=True)
    produced = search.solve(
        task, degree=arguments.degree, max_terms=arguments.max_terms,
        coefficients=(1, -1) if arguments.max_terms > 1 else (1,),
        certificate_depth=arguments.certificate_depth,
        probe_length=arguments.probe_length,
        verify_lengths=tuple(arguments.verify),
        answer_lengths=tuple(arguments.answer))
    trace, book = produced if isinstance(produced, tuple) else (produced, None)

    output = Path(arguments.output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "trace.json").write_text(json.dumps(trace, indent=2, default=str),
                                       encoding="utf-8")
    (output / "run.txt").write_text(search.render(trace) + "\n", encoding="utf-8")
    if book is not None:
        book.save(output / "ledger.json")
        (output / "policy.txt").write_text(
            policy.explain(book.all_entries(), task=task.name) + "\n",
            encoding="utf-8")
    print(search.render(trace))
    print(f"\nwritten to {output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
