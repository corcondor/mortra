"""Read a saved session back as text. Nothing is added that is not in the file.

Every line this prints is a field of `session.json`. Programs are rendered from
their stored structure by a fixed printer, so what appears is the term that was
actually proposed, defined or expanded -- not a description of it.
"""
from __future__ import annotations

import json
from pathlib import Path

BAR = "=" * 78


def render(node, depth=0):
    """A stored program as an expression. Structure only; nothing interpreted."""
    if depth > 40:
        return "..."
    if isinstance(node, dict):
        if "series_parameter" in node:
            return f"<{node['series_parameter']}>"
        if "parameter" in node:
            multiplier = node.get("multiplier")
            name = f"<{node['parameter']}>"
            return name if multiplier in (None, 1, "1") else f"{multiplier}*{name}"
        op = node.get("op")
        if op == "end":
            return "."
        if op == "then":
            # a fold term, flattened the way `fold_library_bridge.word` reads it
            parts, stack = [], [node]
            while stack:
                current = stack.pop()
                if not isinstance(current, dict):
                    parts.append(render(current, depth + 1))
                elif current.get("op") == "then":
                    stack.append(current["tail"])
                    stack.append(current["head"])
                elif current.get("op") == "end":
                    parts.append(".")
                else:
                    parts.append(render(current, depth + 1))
            return " ".join(parts)
        if op in ("A", "C", "G", "T"):
            return op
        if op == "use":
            arguments = ", ".join(f"{k}={render(v, depth+1)}"
                                  for k, v in sorted(node.get("arguments", {}).items()))
            return f"H{node.get('abstraction')}({arguments})"
        if op == "hyper":
            a = ",".join(str(v) for v in node.get("a", []))
            b = ",".join(str(v) for v in node.get("b", []))
            return f"hyper({a};{b})"
        if op == "poly":
            return "poly[" + ",".join(str(c) for c in node.get("coefficients", [])) + "]"
        if op == "diff":
            return f"D({render(node['child'], depth+1)})"
        if op == "scale":
            return f"({node.get('factor')})*{render(node['child'], depth+1)}"
        if op in ("mul", "add"):
            sign = "*" if op == "mul" else "+"
            return (f"({render(node['left'], depth+1)} {sign} "
                    f"{render(node['right'], depth+1)})")
        if op == "pullback":
            return f"pullback({render(node['child'], depth+1)})"
        if op == "ode":
            return f"ode({json.dumps(node.get('operator'))[:40]})"
        return op if op else json.dumps(node)[:60]
    if isinstance(node, list):
        return "[" + ", ".join(render(v, depth+1) for v in node) + "]"
    return str(node)


def holes_of(template):
    found = set()

    def walk(node):
        if isinstance(node, dict):
            if "series_parameter" in node:
                found.add(node["series_parameter"])
            elif "parameter" in node:
                found.add(node["parameter"])
            else:
                for value in node.values():
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
    walk(template)
    return sorted(found)


def report(state, *, stream=None):
    out = []
    write = out.append
    config = state["config"]
    cycles = state["cycles"]

    write(BAR)
    write("SESSION")
    write(BAR)
    write(f"  schema        : {state['schema']}")
    write(f"  cycles run    : {len(cycles)}")
    write(f"  stop reason   : {state['stop_reason']}")
    write(f"  stop note     : {state['stop_note']}")
    write(f"  caps          : max_seconds={config['max_seconds']}  "
          f"max_traced_lines={config['max_traced_lines']}  "
          f"max_cycles={config['max_cycles']}")
    write(f"  settings      : barren_cycles={config['barren_cycles']}  "
          f"min_compression_bits={config['min_compression_bits']}")
    write(f"  seeds         : {[render(p) for p in config['seeds']]}")
    write(f"  state names   : {config['state_names']}   "
          f"parameters {config['parameter_names']}")

    for record in cycles:
        write("")
        write(BAR)
        write(f"CYCLE {record['cycle']}   allowance {record['allowance']}   "
              f"{record['seconds']}s   {record['spent_lines']} traced lines")
        write(BAR)

        write("  candidates actually proposed, per sweep:")
        for sweep in record["sweeps"]:
            kinds = sweep.get("attempted_kinds") or []
            pairs = ", ".join(f"{i}[{k}]" for i, k in
                              zip(sweep.get("attempted", []), kinds)) or "(none)"
            write(f"    sweep {sweep['sweep']}: {pairs}")
            write(f"       accepted {sweep['accepted'] or '-'}   "
                  f"undrafted {sweep['undrafted']}   "
                  f"exhausted {sweep['candidates_exhausted']}   "
                  f"{sweep['spent_lines']} lines")
        write(f"  accepted this cycle: {record['accepted_count']}")

        write(f"  corpus built from this run's own history: "
              f"{record['corpus_programs']} programs, {record['corpus_bits']} bits")

        if record["library"]:
            write("  definitions learned, body and arguments:")
            for entry in record["library"]:
                write(f"    H{entry['index']}  id {entry['id'][:16]}")
                write(f"       arguments : {holes_of(entry['template'])}")
                write(f"       body      : {render(entry['template'])}")
                write(f"       utility {entry['utility_bits']:+d} bits, "
                      f"definition {entry['definition_bits']} bits, "
                      f"touched {entry['programs_touched']} programs")
        else:
            write("  definitions learned: none this cycle")

        for round_record in record.get("learn_rounds", []):
            write(f"    round {round_record.get('round')}: "
                  f"{round_record.get('offered')} offered, "
                  f"{round_record.get('pruned_by_bound')} pruned by the bound, "
                  f"{round_record.get('evaluated')} evaluated, "
                  f"corpus {round_record.get('corpus_bits')} bits")

        write(f"  net compression this cycle: {record['compression_bits']:+d} bits")

        if record["follow_up_calls"]:
            write("  follow-up candidates generated FROM those definitions:")
            for call in record["follow_up_calls"]:
                write(f"    {render(call['call'])}")
                write(f"       expands to : {render(call['expands_to'])}")
                write(f"       {call['call_bits']} bits as a call, "
                      f"{call['expanded_bits']} expanded")
        else:
            write("  follow-up candidates from definitions: none offered")

        write(f"  pending (enumerated, never drafted): {len(record['pending'])}")

    write("")
    write(BAR)
    write("GRAPH")
    write(BAR)
    write(graph(state))
    text = "\n".join(out)
    if stream:
        stream.write(text + "\n")
    return text


def graph(state):
    """The cycle chain, from the stored records only."""
    lines = ["  config", "     |"]
    for record in state["cycles"]:
        accepted = record["accepted_count"]
        library = record["library"]
        calls = record["follow_up_calls"]
        lines.append(f"     v")
        lines.append(f"  +-- cycle {record['cycle']} "
                     f"(allowance {record['allowance']}, {record['spent_lines']} lines)")
        lines.append(f"  |     sweeps -> {accepted} accepted")
        lines.append(f"  |        |")
        lines.append(f"  |        v")
        lines.append(f"  |     corpus from history: {record['corpus_programs']} programs, "
                     f"{record['corpus_bits']} bits")
        lines.append(f"  |        |")
        lines.append(f"  |        v")
        if library:
            for entry in library:
                lines.append(f"  |     H{entry['index']} = {render(entry['template'])}")
                lines.append(f"  |        args {holes_of(entry['template'])}, "
                             f"{entry['utility_bits']:+d} bits, "
                             f"{entry['programs_touched']} programs")
        else:
            lines.append(f"  |     (no definition passed the objective)")
        lines.append(f"  |        |")
        lines.append(f"  |        v")
        if calls:
            for call in calls[:4]:
                lines.append(f"  |     call {render(call['call'])}")
                lines.append(f"  |        -> {render(call['expands_to'])}")
            if len(calls) > 4:
                lines.append(f"  |     ... {len(calls)-4} more calls offered")
        else:
            lines.append(f"  |     (no call offered)")
        lines.append(f"  |        |")
        lines.append(f"  |        v")
        lines.append(f"  |     net {record['compression_bits']:+d} bits, "
                     f"{len(record['pending'])} pending -> next cycle")
        lines.append("  |")
    lines.append("  v")
    lines.append(f"  STOP: {state['stop_reason']}")
    return "\n".join(lines)


def from_directory(directory, *, stream=None):
    path = Path(directory) / "session.json"
    return report(json.loads(path.read_text(encoding="utf-8")), stream=stream)
