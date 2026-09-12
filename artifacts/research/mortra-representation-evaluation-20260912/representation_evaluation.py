"""What a learned representation actually saved, measured rather than asserted.

Four different things get called "compression" in the literature and they are
kept apart here, because a gain in one is not a gain in another:

    description compression   MDL and library learning: the corpus plus the
                              library is shorter than the corpus alone. Recorded
                              as `raw_description_bits`, `representation_bits`,
                              `conditional_description_bits` and their net.
    state reduction           model reduction and invariant representations: the
                              task no longer needs the whole state, only a closed
                              subspace of observables. Recorded as
                              `raw_state_dimension` against
                              `representation_dimension`.
    recomputation reduction   partial evaluation and memoization: the same value
                              is not computed twice. Counted SEPARATELY from work
                              the representation removed outright, because a
                              cache hit and a computation that never needed to
                              exist are not the same saving. Every comparison
                              here is run with the caches cleared; what
                              memoisation alone gives is measured on its own.
    execution depth           the general notion behind recurrent-depth and
                              looped architectures, used here only as *how many
                              times the same compute core must be applied in
                              sequence*. No architecture-specific claim is made
                              and nothing here depends on any unpublished design.

Depth reduction is recorded, not required. A representation that costs a deeper
computation to acquire but repays it over many later problems is the normal case
and is kept with its `break_even_reuse_count` rather than scored down.

Nothing is collapsed into one number. Every component is logged on its own.

How the primitive counts are obtained: the primitives are wrapped, not
reimplemented, and the wrap sits at the chokepoint rather than at the convenience
entry. `sympy.Expr.diff` is that chokepoint for differentiation -- `sympy.diff`
calls it, `expr.diff(...)` is it, and sympy's own recursion re-enters it -- so a
recorded zero is the statement that no derivative was taken anywhere beneath the
call, not that one spelling of it was avoided.
"""
from __future__ import annotations

import sys
import time
import tracemalloc

import sympy as sp

SCHEMA = "mortra.representation-evaluation.v1"

#: what each counter wraps, so a number can be read back to its instrument
INSTRUMENTS = {
    "derivative": ["sympy.Expr.diff (every entry, sympy's own recursion "
                   "included)", "sympy.Poly.diff"],
    "derivative_request": ["sympy.diff (top-level requests only)"],
    "simplify": ["sympy.simplify", "sympy.cancel"],
    "solver": ["sympy.solve", "sympy.linsolve"],
    "fold_step": ["rigid_fold_problem_discovery.apply_fold_generator"],
    "proof": ["holonomic_route_discovery.annihilator",
              "finite_generator_problem_dna.discover_action_observable_basis",
              "abstraction_correspondence.prove_identity"],
}


class PrimitiveTrace:
    """Counts entries to each primitive for the duration of one task.

    `log` keeps the first few entries in order, so a claim like "no derivative
    was taken" can be read off the trace instead of trusted.
    """

    KINDS = tuple(INSTRUMENTS)

    def __init__(self, *, keep=12):
        self.counts = {kind: 0 for kind in self.KINDS}
        self.log = []
        self.keep = keep
        self._undo = []

    def _counter(self, original, kind, label):
        def counted(*args, **kwargs):
            self.counts[kind] += 1
            if len(self.log) < self.keep:
                self.log.append(label)
            return original(*args, **kwargs)
        return counted

    def _wrap_attribute(self, holder, attribute, kind, label):
        """Wrap one attribute in place (used for the sympy class methods)."""
        original = getattr(holder, attribute, None)
        if original is None:
            return
        setattr(holder, attribute, self._counter(original, kind, label))
        self._undo.append((holder, attribute, original))

    def _wrap_everywhere(self, original, kind, label):
        """Wrap every binding of one function across the package.

        `from x import f` copies the reference, so patching the home module
        alone would leave those copies uncounted and make a zero mean nothing.
        Every module in the package is scanned for a binding that IS this
        function and each one is replaced by a wrapper around the original, so a
        call passes through exactly one counter no matter which name it used.
        """
        if original is None:
            return
        counted = self._counter(original, kind, label)
        for name, module in list(sys.modules.items()):
            if module is None or not (name == "math_os_prototype"
                                      or name.startswith("math_os_prototype.")):
                continue
            for attribute, value in list(vars(module).items()):
                if value is original:
                    setattr(module, attribute, counted)
                    self._undo.append((module, attribute, original))

    def __enter__(self):
        from math_os_prototype import abstraction_correspondence as correspondence
        from math_os_prototype import finite_generator_problem_dna as dna
        from math_os_prototype import holonomic_route_discovery as route
        from math_os_prototype import rigid_fold_problem_discovery as fold

        # the chokepoint first: every derivative in sympy passes through here,
        # including sympy's own recursion, so a zero is a real zero
        self._wrap_attribute(sp.Expr, "diff", "derivative", "Expr.diff")
        self._wrap_attribute(sp.Poly, "diff", "derivative", "Poly.diff")
        for original, kind, label in (
                (sp.diff, "derivative_request", "sympy.diff"),
                (sp.simplify, "simplify", "simplify"),
                (sp.cancel, "simplify", "cancel"),
                (sp.solve, "solver", "solve"),
                (sp.linsolve, "solver", "linsolve"),
                (fold.apply_fold_generator, "fold_step", "apply_fold_generator"),
                (route.annihilator, "proof", "annihilator"),
                (dna.discover_action_observable_basis, "proof",
                 "discover_action_observable_basis"),
                (getattr(correspondence, "prove_identity", None), "proof",
                 "prove_identity")):
            self._wrap_everywhere(original, kind, label)
        # sympy's own module attributes, for calls written as sp.diff(...)
        self._wrap_attribute(sp, "diff", "derivative_request", "sympy.diff")
        self._wrap_attribute(sp, "simplify", "simplify", "simplify")
        self._wrap_attribute(sp, "cancel", "simplify", "cancel")
        self._wrap_attribute(sp, "solve", "solver", "solve")
        self._wrap_attribute(sp, "linsolve", "solver", "linsolve")
        return self

    def __exit__(self, *exception):
        for holder, attribute, original in reversed(self._undo):
            setattr(holder, attribute, original)
        self._undo.clear()
        return False


# ---- memoisation, kept apart from what the representation removed ----------

def _caches():
    from math_os_prototype.holonomic_route_discovery import _annihilator, _coefficients
    return {"annihilator": _annihilator, "coefficients": _coefficients}


def cache_state():
    return {name: function.cache_info()._asdict()
            for name, function in _caches().items()}


def clear_caches():
    for function in _caches().values():
        function.cache_clear()


# ---- measuring one run -----------------------------------------------------

def measure(run, *, cold=True, **extra):
    """Run one task and record what it cost.

    `run` returns either a plain value, or a dict carrying `value` together with
    whatever the task counted for itself -- `sequential_depth`,
    `candidates_generated`, `search_nodes`, `rejected_candidates`. Those are
    structural counts of the graph the task actually walked, so they come from
    the task rather than from an estimate made here.

    `cold=True` clears the repository's memoisation first, so a reduction
    observed afterwards is structural and not a remembered value. The cache
    counters are reported either way, which is where memoisation is read.
    """
    if cold:
        clear_caches()
    before = cache_state()
    trace = PrimitiveTrace()
    tracemalloc.start()
    started = time.perf_counter()
    with trace:
        produced = run()
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    after = cache_state()

    # a task that wants to report its own structural counts returns a dict
    # carrying "value"; anything else is the value itself, dict or not
    reported = (dict(produced) if isinstance(produced, dict) and "value" in produced
                else {"value": produced})
    record = {
        "value": reported.get("value"),
        "primitive_calls": sum(trace.counts[k] for k in trace.KINDS
                               if k != "derivative_request"),
        "derivative_calls": trace.counts["derivative"],
        "derivative_request_calls": trace.counts["derivative_request"],
        "simplify_calls": trace.counts["simplify"],
        "solver_calls": trace.counts["solver"],
        "fold_step_calls": trace.counts["fold_step"],
        "proof_calls": trace.counts["proof"],
        "trace_sample": list(trace.log),
        "wall_time": round(elapsed, 6),
        "peak_memory": peak,
        "cache_hits": {name: after[name]["hits"] - before[name]["hits"]
                       for name in before},
        "cache_misses": {name: after[name]["misses"] - before[name]["misses"]
                         for name in before},
        "cold_caches": cold,
        "sequential_depth": reported.get("sequential_depth"),
        "candidates_generated": reported.get("candidates_generated"),
        "search_nodes": reported.get("search_nodes"),
        "rejected_candidates": reported.get("rejected_candidates"),
        "flop_proxy": reported.get("flop_proxy"),
    }
    # anything else the task counted for itself is carried through unchanged
    for field, value in reported.items():
        record.setdefault(field, value)
    record.update(extra)
    return record


def description_bits(value):
    from math_os_prototype.representation_progress import description_bits as bits
    return bits(value)


def power_by_squaring(matrix, exponent, *, identity):
    """A matrix power, with the multiplications and the depth it really took.

    Written out rather than delegated so the depth reported is the depth walked.
    The point of the measurement is that this route exists at all: matrix
    multiplication is associative, so the exponent can be halved; the kinematics
    it replaces is a chain of state updates and cannot be.
    """
    if exponent < 0:
        raise ValueError("a non-negative exponent is required")
    result, base, multiplications, depth = identity, matrix, 0, 0
    remaining = exponent
    while remaining:
        if remaining & 1:
            result = result * base
            multiplications += 1
            depth += 1
        remaining >>= 1
        if remaining:
            base = base * base
            multiplications += 1
            depth += 1
    return {"value": result, "multiplications": multiplications, "depth": depth}


# ---- assembling the record -------------------------------------------------

def evaluate(name, *, baseline, represented, acquisition,
             raw_description_bits, representation_bits,
             conditional_description_bits,
             raw_state_dimension, representation_dimension,
             state_dimension_sense=None,
             search_units=None, flop_proxy_note=None,
             memoisation_only=None,
             successful_reuses=0, heldout_successes=0, failed_reuses=0,
             agreement=None, note=None, representation=None):
    """Assemble the record. Every component stays separate.

    `break_even_reuse_count` is counted in primitive calls, because those are
    deterministic where wall time is not. A representation that saves nothing
    per use has no break-even and says so rather than reporting a large one.
    """
    per_use = {
        "primitive_calls": baseline["primitive_calls"] - represented["primitive_calls"],
        "derivative_calls": baseline["derivative_calls"] - represented["derivative_calls"],
        "simplify_calls": baseline["simplify_calls"] - represented["simplify_calls"],
        "fold_step_calls": baseline["fold_step_calls"] - represented["fold_step_calls"],
        "wall_time": round(baseline["wall_time"] - represented["wall_time"], 6),
        "peak_memory": baseline["peak_memory"] - represented["peak_memory"],
    }
    saving = per_use["primitive_calls"]
    cost = acquisition.get("acquisition_primitive_calls", 0)
    break_even = -(-cost // saving) if saving > 0 else None
    before_depth = baseline.get("sequential_depth")
    after_depth = represented.get("sequential_depth")
    ratio = (before_depth / after_depth
             if before_depth is not None and after_depth else None)

    eliminated = {kind: getattr_count(baseline, kind) - getattr_count(represented, kind)
                  for kind in ("derivative_calls", "simplify_calls",
                               "solver_calls", "proof_calls", "fold_step_calls")}
    return {
        "schema": SCHEMA, "name": name, "note": note,
        # which learned representation this record is about; the same
        # representation can be evaluated by more than one task
        "representation": representation,
        "instruments": {kind: list(where) for kind, where in INSTRUMENTS.items()},

        "description_compression": {
            "raw_description_bits": raw_description_bits,
            "representation_bits": representation_bits,
            "conditional_description_bits": conditional_description_bits,
            "net_description_gain_bits": (raw_description_bits
                                          - conditional_description_bits
                                          - representation_bits),
            "bits_saved_per_task": raw_description_bits - conditional_description_bits,
            "description_break_even_task_count": (
                -(-representation_bits // (raw_description_bits
                                           - conditional_description_bits))
                if raw_description_bits > conditional_description_bits else None),
            "sense": ("MDL / library learning: the corpus given the "
                      "representation, plus the representation, against the "
                      "corpus on its own. A negative net on ONE task is the "
                      "normal case and is not a failure -- the library is "
                      "written once and the conditional description is paid "
                      "per task, so `description_break_even_task_count` is "
                      "where the accounting turns, exactly as "
                      "`break_even_reuse_count` is for calls")},

        "state_reduction": {
            "raw_state_dimension": raw_state_dimension,
            "representation_dimension": representation_dimension,
            "sense": state_dimension_sense or
                     "model reduction: a closed subspace instead of the whole state"},

        "primitive_reduction": {
            "primitive_calls_before": baseline["primitive_calls"],
            "primitive_calls_after": represented["primitive_calls"],
            "derivative_calls_before": baseline["derivative_calls"],
            "derivative_calls_after": represented["derivative_calls"],
            "derivative_request_calls_before": baseline["derivative_request_calls"],
            "derivative_request_calls_after": represented["derivative_request_calls"],
            "simplify_calls_before": baseline["simplify_calls"],
            "simplify_calls_after": represented["simplify_calls"],
            "solver_calls_before": baseline["solver_calls"],
            "solver_calls_after": represented["solver_calls"],
            "proof_calls_before": baseline["proof_calls"],
            "proof_calls_after": represented["proof_calls"],
            "fold_step_calls_before": baseline["fold_step_calls"],
            "fold_step_calls_after": represented["fold_step_calls"],
            "trace_sample_before": baseline["trace_sample"],
            "trace_sample_after": represented["trace_sample"],
            "eliminated_by_representation": eliminated,
            "caches_cold_on_both_sides": bool(baseline["cold_caches"]
                                              and represented["cold_caches"]),
            "sense": ("both sides ran with the memoisation cleared, so a "
                      "reduction here is work the representation removed, not a "
                      "value the process happened to remember")},

        "recomputation_reduction": {
            "cache_hits_during_baseline": baseline["cache_hits"],
            "cache_hits_during_represented": represented["cache_hits"],
            "memoisation_only": memoisation_only,
            "sense": ("partial evaluation / memoization, kept apart: "
                      "`memoisation_only` is the SAME baseline run a second "
                      "time with the caches left warm. Whatever it saves is "
                      "remembering, not representation.")},

        "search_reduction": {
            "candidates_generated_before": baseline["candidates_generated"],
            "candidates_generated_after": represented["candidates_generated"],
            "search_nodes_before": baseline["search_nodes"],
            "search_nodes_after": represented["search_nodes"],
            "rejected_candidates_before": baseline["rejected_candidates"],
            "rejected_candidates_after": represented["rejected_candidates"],
            "units": search_units or ("not a search on either side; these rows "
                                      "are empty rather than zero")},

        "execution_depth": {
            "sequential_depth_before": before_depth,
            "sequential_depth_after": after_depth,
            "depth_reduction_ratio": ratio,
            "sense": ("how many times the same compute core must be applied in "
                      "sequence. The general recurrent-depth notion only; no "
                      "architecture-specific claim and no dependence on any "
                      "unpublished design"),
            "not_a_success_condition": ("a ratio at or below 1 is recorded, not "
                                        "penalised: an acquisition that costs "
                                        "more depth and repays it over later "
                                        "problems is the case worth keeping, "
                                        "and break_even_reuse_count is where "
                                        "that is read")},

        "real_cost": {
            "wall_time_before": baseline["wall_time"],
            "wall_time_after": represented["wall_time"],
            "peak_memory_before": baseline["peak_memory"],
            "peak_memory_after": represented["peak_memory"],
            "flop_proxy_before": baseline["flop_proxy"],
            "flop_proxy_after": represented["flop_proxy"],
            "flop_proxy_note": flop_proxy_note or
                ("an exact operation count where the route's arithmetic is "
                 "known; null where it was not instrumented, rather than "
                 "estimated")},

        "acquisition_cost": dict(acquisition),

        "reuse": {"successful_reuses": successful_reuses,
                  "heldout_successes": heldout_successes,
                  "failed_reuses": failed_reuses},

        "agreement": agreement,

        "cumulative": {
            "per_use_saving": per_use,
            "acquisition_primitive_calls": cost,
            "break_even_reuse_count": break_even,
            "measured_in": "primitive calls",
            "reason": ("primitive calls are deterministic where wall time is "
                       "not; wall time is reported beside them and is not what "
                       "break-even is counted in"),
            "cumulative_primitive_calls": [
                {"reuses": k,
                 "baseline": baseline["primitive_calls"] * k,
                 "representation": cost + represented["primitive_calls"] * k}
                for k in (0, 1, 2, 4, 8, 16, 32)]},
    }


def getattr_count(record, field):
    return record.get(field, 0) or 0


# ---- the one required picture ---------------------------------------------

def ascii_graphs(title, *, raw, representation, reduced, legend=()):
    """raw computation graph -> learned representation -> reduced graph."""
    lines = [f"{title}", "=" * len(title), "",
             "[1] raw computation graph (no representation)", ""]
    lines += ["    " + row for row in raw]
    lines += ["", "[2] learned representation", ""]
    lines += ["    " + row for row in representation]
    lines += ["", "[3] reduced computation graph (with the representation)", ""]
    lines += ["    " + row for row in reduced]
    if legend:
        lines += ["", "legend", ""]
        lines += ["    " + row for row in legend]
    return "\n".join(lines)
