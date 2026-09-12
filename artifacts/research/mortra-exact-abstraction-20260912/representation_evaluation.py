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
from sympy.core import cache as sympy_cache

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

    def __init__(self, *, keep=12, node_cap=20000):
        self.counts = {kind: 0 for kind in self.KINDS}
        self.log = []
        self.keep = keep
        #: one entry per primitive invocation, in order. This is the execution
        #: graph the run really walked, and it is what a provenance claim about
        #: "which node disappeared" is read from.
        self.nodes = []
        self.node_cap = node_cap
        self.nodes_truncated = False
        self._undo = []

    @staticmethod
    def _signature(kind, args):
        """A short, cheap name for the node, so nodes can be told apart.

        Deliberately cheap: it must not change what the run costs. Where the
        call carries an obvious identity -- the fold letter, the operator being
        differentiated -- that is used; otherwise the argument's type stands in.
        """
        if not args:
            return ""
        first = args[0]
        if kind == "fold_step":
            generator = args[2] if len(args) > 2 else None
            return getattr(generator, "symbol", "?")
        return type(first).__name__

    def _counter(self, original, kind, label):
        def counted(*args, **kwargs):
            self.counts[kind] += 1
            if len(self.log) < self.keep:
                self.log.append(label)
            if len(self.nodes) < self.node_cap:
                self.nodes.append((kind, label, self._signature(kind, args)))
            else:
                self.nodes_truncated = True
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
    """Every cache a rung could benefit from, not only this repository's.

    sympy memoises a great deal of its own work -- `Mul._eval_derivative` and
    `Mul._eval_derivative_n_times` among it -- in one global store. Leaving that
    store warm while clearing only the local caches would make a "cold" run a
    partly warm one, and the memoisation rung would then be credited to
    structure. It is cleared here so that cold means cold, and so the memoised
    rung measures what memoisation is actually worth.
    """
    for function in _caches().values():
        function.cache_clear()
    sympy_cache.clear_cache()


def _node_census(trace):
    """The execution graph, grouped. Kept as a census rather than a full list so
    a run with half a million nodes is still readable, with the first positions
    of each group kept so a node can be located in the order it happened."""
    census = {}
    for position, (kind, label, signature) in enumerate(trace.nodes):
        key = f"{kind}:{label}:{signature}" if signature else f"{kind}:{label}"
        entry = census.setdefault(key, {"kind": kind, "label": label,
                                        "signature": signature, "count": 0,
                                        "first_positions": []})
        entry["count"] += 1
        if len(entry["first_positions"]) < 6:
            entry["first_positions"].append(position)
    return census


def eliminated_nodes(before, after):
    """Which nodes the representation removed, node kind by node kind.

    Not a difference of totals: the census is keyed by kind, instrument and
    signature, so a node that survived under a different name is not counted as
    removed, and a node that appeared only in the represented run is reported as
    added rather than quietly cancelling a removal.
    """
    left, right = before["nodes"], after["nodes"]
    removed, added, kept = {}, {}, {}
    for key, entry in left.items():
        surviving = right.get(key, {}).get("count", 0)
        if surviving < entry["count"]:
            removed[key] = {**entry, "removed": entry["count"] - surviving,
                            "surviving": surviving}
        if surviving:
            kept[key] = surviving
    for key, entry in right.items():
        extra = entry["count"] - left.get(key, {}).get("count", 0)
        if extra > 0:
            added[key] = {**entry, "added": extra}
    return {"removed": removed, "added": added, "kept": kept,
            "nodes_removed": sum(e["removed"] for e in removed.values()),
            "nodes_added": sum(e["added"] for e in added.values()),
            "complete": not (before["nodes_truncated"] or after["nodes_truncated"]),
            "sense": ("the execution graph of the run WITHOUT the "
                      "representation, minus the graph of the run WITH it. "
                      "`complete` is false when the node census hit its cap, in "
                      "which case the counts are a lower bound")}


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
        "nodes": _node_census(trace),
        "nodes_truncated": trace.nodes_truncated,
        "wall_time": round(elapsed, 6),
        "peak_memory": peak,
        "cache_hits": {name: after[name]["hits"] - before[name]["hits"]
                       for name in before},
        "cache_misses": {name: after[name]["misses"] - before[name]["misses"]
                         for name in before},
        "cold_caches": cold,
        "caches_cleared": (["holonomic_route_discovery._annihilator",
                            "holonomic_route_discovery._coefficients",
                            "sympy.core.cache (global)"] if cold else []),
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

#: the ladder, in order. Each rung is a real run, so the marginal differences
#: between them add up to the whole and nothing has to be apportioned.
LADDER = (
    ("naive", "the task done the obvious way, caches cleared"),
    ("memoised", "the same route again with the caches left warm"),
    ("mathematical", "an existing mathematical route, available without "
                     "learning anything"),
    ("generic_search", "a standard search improvement -- merging equal states "
                       "-- with no learned representation"),
    ("representation", "the learned representation, on top of all of the above"),
)

#: what each rung's marginal step is credited to
CAUSE = {"memoised": "memoisation_reduction",
         "mathematical": "mathematical_reduction",
         "generic_search": "generic_search_reduction",
         "representation": "representation_reduction"}

LADDER_METRICS = ("primitive_calls", "derivative_calls", "fold_step_calls",
                  "search_nodes", "wall_time")


def attribute(ladder):
    """Split the saving four ways, by measuring each rung rather than guessing.

    A rung that does not exist for this task is absent, not zero, and the step
    that would have been credited to it is credited to the next rung that does
    exist -- with `from_rung` naming the comparison each number came from, so
    nothing is silently reattributed.
    """
    order = [name for name, _ in LADDER]
    described = dict(LADDER)
    present = [(name, ladder[name]) for name in order
               if ladder.get(name) is not None]
    if len(present) < 2 or present[0][0] != "naive":
        raise ValueError("the ladder needs a naive rung and at least one more")
    causes = {CAUSE[name]: None for name in order if name in CAUSE}
    previous_name, previous = present[0]
    for name, rung in present[1:]:
        step = {}
        for metric in LADDER_METRICS:
            before, after = previous.get(metric), rung.get(metric)
            if before is None or after is None:
                step[metric] = None
            elif metric == "wall_time":
                step[metric] = round(before - after, 6)
            else:
                step[metric] = before - after
        causes[CAUSE[name]] = {**step, "from_rung": previous_name,
                               "to_rung": name,
                               "description": described[name]}
        previous_name, previous = name, rung

    first, last = present[0][1], present[-1][1]
    total = {}
    for metric in LADDER_METRICS:
        before, after = first.get(metric), last.get(metric)
        if before is None or after is None:
            total[metric] = None
        elif metric == "wall_time":
            total[metric] = round(before - after, 6)
        else:
            total[metric] = before - after
    adds_up = {}
    for metric in LADDER_METRICS:
        parts = [cause[metric] for cause in causes.values()
                 if cause is not None and cause[metric] is not None]
        adds_up[metric] = (None if total[metric] is None
                           else abs(sum(parts) - total[metric]) < 1e-6)
    return {**causes,
            "rungs_measured": [name for name, _ in present],
            "rungs_absent": [name for name in order if ladder.get(name) is None],
            "total": total, "marginals_add_up_to_total": adds_up,
            "sense": ("each rung is a separate run of the same task. The step "
                      "from one rung to the next is credited to that rung and "
                      "to nothing else, so the four causes are measured rather "
                      "than apportioned"),
            "reading": ("`representation_reduction` is the only column that "
                        "belongs to the learned representation. A large total "
                        "with a small representation column means the saving "
                        "was already available without it.")}

def break_evens(*, acquisition_primitive_calls, representation_bits,
                bits_saved_per_task, saving_against_naive,
                saving_against_best_baseline, best_baseline_rung="naive",
                measured_reuses=1):
    """Break-even counts, one per comparison target, never mixed.

    This is a reporting definition, not a standard index from any of the cited
    papers. For a comparison target B, with `A` the difference in preparation
    cost and `delta` the saving per use,

        gain_B(N) = [B preparation + N * B per-use] - [acquisition + N * per-use]

    and where `A > 0` and `delta > 0` the smallest `N` with `gain_B(N) >= 0` is
    `ceil(A / delta)`. That is a steady-state estimate from the measured per-use
    figures, not a proof about all future use.

    `None` never means "never repays". It is always accompanied by a reason
    saying which of the three it is: no crossing under the present model, not
    reached inside the measured range, or not enough measurement to say.
    """
    def turn(cost, saving, what):
        if saving is None:
            return None, f"{what}: not measured"
        if saving > 0:
            return -(-cost // saving), f"{what}: crossing at this many reuses"
        if saving == 0:
            return None, (f"{what}: no crossing under the present steady-state "
                          "model -- the measured per-use saving is exactly zero, "
                          "so the two costs stay parallel. This is a statement "
                          "about the measured model, not about all future use")
        return None, (f"{what}: no crossing under the present steady-state "
                      "model -- the measured per-use saving is negative, so the "
                      "gap widens with use. A different task mix or a later "
                      "measurement could differ; this does not establish that it "
                      "never repays")

    compute, compute_reason = turn(acquisition_primitive_calls,
                                   saving_against_naive, "compute vs naive")
    best, best_reason = turn(acquisition_primitive_calls,
                             saving_against_best_baseline,
                             f"compute vs {best_baseline_rung}")
    description, description_reason = turn(representation_bits,
                                           bits_saved_per_task,
                                           "description")

    def joint(one, two):
        """Both conditions met, against the SAME comparison target."""
        if one is None or two is None:
            return None
        return max(one, two)

    return {
        "compute_break_even_reuse_count": compute,
        "compute_break_even_reuse_count_against_best_baseline": best,
        "description_break_even_task_count": description,
        "best_baseline_rung": best_baseline_rung,
        "joint_break_even_against_naive": joint(compute, description),
        "joint_break_even_against_best_baseline": joint(best, description),
        "reasons": {"compute_vs_naive": compute_reason,
                    "compute_vs_best": best_reason,
                    "description": description_reason},
        "acquisition_primitive_calls": acquisition_primitive_calls,
        "representation_bits": representation_bits,
        "per_use_primitive_saving_against_naive": saving_against_naive,
        "per_use_primitive_saving_against_best_baseline":
            saving_against_best_baseline,
        "bits_saved_per_task": bits_saved_per_task,
        "measured_reuses": measured_reuses,
        "definitions": {
            "compute_break_even_reuse_count":
                ("reuses until the acquisition primitive calls are repaid, "
                 "against the NAIVE route"),
            "compute_break_even_reuse_count_against_best_baseline":
                ("the same against the strongest route available WITHOUT this "
                 "representation. This is the figure that says what the "
                 "representation itself is worth"),
            "description_break_even_task_count":
                ("tasks until the bits of the representation are repaid by the "
                 "bits it saves per task"),
            "joint_break_even_against_naive":
                ("the smallest count at which BOTH the compute and the "
                 "description condition hold against the naive target -- the "
                 "maximum of the two, valid because each is a monotone "
                 "threshold. Not a sum, and not across targets"),
            "joint_break_even_against_best_baseline":
                ("the same joint, taken entirely against the best existing "
                 "target. Never mixed with the naive figure: a joint of a naive "
                 "compute count and a description count would compare two "
                 "different things")},
        "not_a_claim": ("no figure here is a proof about future use, and a "
                        "`None` is a measurement statement with its reason "
                        "recorded, never a claim that the representation can "
                        "never repay"),
    }


def evaluate(name, *, baseline, represented, acquisition,
             raw_description_bits, representation_bits,
             conditional_description_bits,
             raw_state_dimension, representation_dimension,
             state_dimension_sense=None,
             search_units=None, flop_proxy_note=None,
             ladder=None, certificate=None,
             memoisation_only=None,
             successful_reuses=0, heldout_successes=0, failed_reuses=0,
             agreement=None, note=None, representation=None):
    """Assemble the record. Every component stays separate.

    `ladder` carries the other rungs -- the same task with memoisation only,
    with an existing mathematical route, with a standard search improvement --
    so the saving can be split four ways instead of all of it landing on the
    representation. Without it the record still assembles and says which rungs
    were not run.
    """
    rungs = dict(ladder or {})
    rungs.setdefault("naive", baseline)
    rungs.setdefault("representation", represented)
    for rung in ("memoised", "mathematical", "generic_search"):
        rungs.setdefault(rung, None)
    attribution = attribute(rungs)

    best_name = next((n for n in ("generic_search", "mathematical", "memoised")
                      if rungs.get(n) is not None), "naive")
    best = rungs[best_name]

    per_use = {
        "primitive_calls": baseline["primitive_calls"] - represented["primitive_calls"],
        "derivative_calls": baseline["derivative_calls"] - represented["derivative_calls"],
        "simplify_calls": baseline["simplify_calls"] - represented["simplify_calls"],
        "fold_step_calls": baseline["fold_step_calls"] - represented["fold_step_calls"],
        "wall_time": round(baseline["wall_time"] - represented["wall_time"], 6),
        "peak_memory": baseline["peak_memory"] - represented["peak_memory"],
    }
    cost = acquisition.get("acquisition_primitive_calls", 0)
    turns = break_evens(
        acquisition_primitive_calls=cost,
        representation_bits=representation_bits,
        bits_saved_per_task=raw_description_bits - conditional_description_bits,
        saving_against_naive=per_use["primitive_calls"],
        saving_against_best_baseline=(best["primitive_calls"]
                                      - represented["primitive_calls"]),
        best_baseline_rung=best_name)
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
        "certificate": certificate,
        "instruments": {kind: list(where) for kind, where in INSTRUMENTS.items()},

        "description_compression": {
            "raw_description_bits": raw_description_bits,
            "representation_bits": representation_bits,
            "conditional_description_bits": conditional_description_bits,
            "net_description_gain_bits": (raw_description_bits
                                          - conditional_description_bits
                                          - representation_bits),
            "bits_saved_per_task": raw_description_bits - conditional_description_bits,
            "description_break_even_task_count":
                turns["description_break_even_task_count"],
            "sense": ("MDL / library learning: the corpus given the "
                      "representation, plus the representation, against the "
                      "corpus on its own. A negative net on ONE task is the "
                      "normal case and is not a failure -- the library is "
                      "written once and the conditional description is paid per "
                      "task, so `description_break_even_task_count` is where "
                      "the accounting turns, exactly as "
                      "`compute_break_even_reuse_count` is for calls")},

        "state_reduction": {
            "raw_state_dimension": raw_state_dimension,
            "representation_dimension": representation_dimension,
            "sense": state_dimension_sense or
                     "model reduction: a closed subspace instead of the whole state"},

        "attribution": attribution,

        "primitive_reduction": {
            "primitive_calls_before": baseline["primitive_calls"],
            "primitive_calls_after": represented["primitive_calls"],
            "derivative_calls_before": baseline["derivative_calls"],
            "derivative_calls_after": represented["derivative_calls"],
            "derivative_request_calls_before": baseline["derivative_request_calls"],
            "derivative_request_calls_after": represented["derivative_request_calls"],
            "derivative_counting": ("`derivative_calls` counts every entry to "
                                    "sympy.Expr.diff, including sympy own "
                                    "recursion; `derivative_request_calls` "
                                    "counts only top-level sympy.diff requests. "
                                    "Two different quantities, never added "
                                    "together"),
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
            "best_baseline_without_this_representation": {
                "rung": best_name,
                "primitive_calls": best["primitive_calls"],
                "derivative_calls": best["derivative_calls"],
                "wall_time": best["wall_time"],
                "sense": ("the strongest route that did NOT use this "
                          "representation. This is the comparison that says "
                          "what the representation itself is worth")},
            "caches_cold_on_both_sides": bool(baseline["cold_caches"]
                                              and represented["cold_caches"]),
            "caches_cleared": baseline.get("caches_cleared"),
            "sense": ("both sides ran with the memoisation cleared -- this "
                      "repository's and sympy own global store -- so a "
                      "reduction here is work the representation removed, not a "
                      "value the process happened to remember. The memoised "
                      "rung in `attribution` is where remembering is counted")},

        "provenance": {
            "against_naive": eliminated_nodes(baseline, represented),
            "against_best_baseline": eliminated_nodes(best, represented),
            "best_baseline_rung": best_name,
            "sense": ("which computation nodes stopped happening. Both are "
                      "kept: `against_naive` is the whole difference from the "
                      "obvious route, `against_best_baseline` is the part that "
                      "would still have been executed by the strongest route "
                      "available WITHOUT this representation -- which is the "
                      "one that answers what having this representation saved"),
            "node_identity": ("nodes are keyed by primitive kind, the "
                              "instrument they were counted at, and a short "
                              "signature of the call, so a node that survived "
                              "under another name is not counted as removed")},

        "recomputation_reduction": {
            "cache_hits_during_baseline": baseline["cache_hits"],
            "cache_hits_during_represented": represented["cache_hits"],
            "memoisation_only": memoisation_only,
            "attributed": attribution.get("memoisation_reduction"),
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
            "generic_improvement_alone": (
                None if rungs.get("generic_search") is None else
                {"search_nodes": rungs["generic_search"]["search_nodes"],
                 "candidates_generated":
                     rungs["generic_search"]["candidates_generated"],
                 "sense": ("merging equal states, a standard technique, with no "
                           "learned representation. What the representation "
                           "adds is the step from here, not from the naive "
                           "enumeration")}),
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
                                        "and the break-evens are where that is "
                                        "read")},

        "real_cost": {
            "wall_time_before": baseline["wall_time"],
            "wall_time_after": represented["wall_time"],
            "peak_memory_before": baseline["peak_memory"],
            "peak_memory_after": represented["peak_memory"],
            "flop_proxy_before": baseline["flop_proxy"],
            "flop_proxy_after": represented["flop_proxy"],
            "flop_proxy_note": flop_proxy_note or
                ("an exact operation count where the arithmetic of the route is "
                 "known; null where it was not instrumented, rather than "
                 "estimated")},

        "acquisition_cost": dict(acquisition),

        "reuse": {"successful_reuses": successful_reuses,
                  "heldout_successes": heldout_successes,
                  "failed_reuses": failed_reuses},

        "agreement": agreement,

        "cumulative": {
            "per_use_saving": per_use,
            "break_evens": turns,
            "measured_in": "primitive calls and description bits, separately",
            "reason": ("primitive calls are deterministic where wall time is "
                       "not; wall time is reported beside them and is not what "
                       "any break-even is counted in"),
            "cumulative_primitive_calls": [
                {"reuses": k,
                 "naive": baseline["primitive_calls"] * k,
                 "best_baseline": best["primitive_calls"] * k,
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
