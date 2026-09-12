"""A search allowance that actually stops the work it is given.

The solve budget B counts rewrite steps a controller takes. This is the other
one: H, the allowance for looking for a candidate at all -- composing it,
proving the relation, rebuilding the controller, running the gate. The two are
separate because a proposer that never finds anything must still be charged.

Counting reductions is not enough, because most of that work never calls
`reduce`: `certify_equal` expands series and compares coefficients on its own.
So the unit here is executed Python lines, taken from the interpreter's trace
hook, and the allowance is enforced by raising inside the traced frame. Work
stops where the allowance runs out rather than being measured after the fact.

Two limits are worth stating plainly. Lines executed in C never reach the trace
hook, so a long call into a native routine counts as one line. And the frame
that installs the hook is already running, so its own remaining lines are not
counted; only the calls it makes are. Both make this an undercount, never an
overcount, so a candidate can overrun its allowance but cannot be cut short
before it.
"""
from __future__ import annotations

import sys

SCHEMA = "mortra.search-budget.v1"
UNIT = "executed python lines observed by the interpreter trace hook"


class SearchBudgetExhausted(Exception):
    """Raised inside the running candidate when its allowance is spent."""

    def __init__(self, allowance):
        super().__init__(f"search allowance of {allowance} {UNIT} is spent")
        self.allowance = allowance


class LineBudget:
    """Charge a block of work and interrupt it when the allowance is gone.

    Nests safely: any tracer already installed is restored on exit, so this can
    run under a debugger or a coverage run without stealing their hook.
    """

    def __init__(self, allowance):
        if type(allowance) is not int or allowance < 1:
            raise ValueError("a search allowance must be a positive exact integer")
        self.allowance = allowance
        self.used = 0
        self.exhausted = False
        self._previous = None

    def _trace(self, frame, event, arg):
        if event == "line":
            self.used += 1
            if self.used > self.allowance:
                self.exhausted = True
                raise SearchBudgetExhausted(self.allowance)
        return self._trace

    def __enter__(self):
        self._previous = sys.gettrace()
        sys.settrace(self._trace)
        return self

    def __exit__(self, kind, value, traceback):
        sys.settrace(self._previous)
        # The allowance running out is an outcome of this block, not an error
        # for the caller to handle, so it is swallowed here and reported by the
        # `exhausted` flag.
        return kind is SearchBudgetExhausted

    def spent(self):
        return {"schema": SCHEMA, "unit": UNIT, "allowance": self.allowance,
                "used": self.used, "exhausted": self.exhausted}


def run_within(allowance, work):
    """Run `work()` under an allowance; report the value or the interruption."""
    budget = LineBudget(allowance)
    result = None
    with budget:
        result = work()
    return {"completed": not budget.exhausted,
            "value": None if budget.exhausted else result,
            "cost": budget.spent()}
