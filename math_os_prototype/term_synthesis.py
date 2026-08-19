"""Type-directed term synthesis for MathOS.

This module does *not* add a competing type system.  It reuses the canonical
vocabulary of ``typed_definition_kernel.LEXICON`` (names, backend theories) and
the many-sorted intuition of ``semantic_logic``, and turns the type information
from a *post-hoc filter* into a *generator*:

  * Geometry / formal side -- ``synthesize`` performs type inhabitation: given a
    goal type it builds well-typed terms by connecting operation output types to
    input types, instead of emitting a hard-coded goal s-expression.

  * Arithmetic side -- a relation such as ``final = initial + gain - loss`` is
    stored once as a :class:`Law` and solved for *whichever* slot is unknown
    (unknown-slot unification), instead of one builder per unknown position.

The engine is additive: nothing here replaces the existing builders.  It is
meant to be tried first, with the current specialized/generic paths kept as
fallback (see ``module docstring`` of ``reasoning_pipeline``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Callable, Iterable

try:  # Reuse existing definition atoms; do not duplicate them.
    from math_os_prototype.typed_definition_kernel import LEXICON
except ImportError:  # Allows direct script execution.
    from typed_definition_kernel import LEXICON


# --------------------------------------------------------------------------- #
# Types (string-based, with a tiny subtype relation -- no competing class).    #
# --------------------------------------------------------------------------- #

# subtype -> supertypes it can stand in for.
SUBTYPES: dict[str, frozenset[str]] = {
    "Triangle": frozenset({"Triangle", "Polygon"}),
    "Square": frozenset({"Square", "Polygon"}),
    "Polygon": frozenset({"Polygon"}),
    "PositiveInteger": frozenset({"PositiveInteger", "Integer", "Real"}),
    "Integer": frozenset({"Integer", "Real"}),
}

# Backend theory per canonical operation, pulled from the existing LEXICON so we
# do not invent a parallel registry of meanings.
_BACKEND_BY_CANONICAL = {entry.canonical.lower(): entry.backend_theory for entry in LEXICON}


def is_subtype(sub: str, sup: str) -> bool:
    if sub == sup:
        return True
    return sup in SUBTYPES.get(sub, frozenset({sub}))


# --------------------------------------------------------------------------- #
# Typed operations and term IR.                                                #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Operation:
    name: str
    input_types: tuple[str, ...]
    output_type: str
    semantic_tags: tuple[str, ...] = ()
    backend_theory: str = ""
    cost: int = 1


@dataclass(frozen=True)
class Atom:
    """A variable or constant already available from the problem."""

    name: str
    type: str
    kind: str = "const"  # "const" | "var"


@dataclass(frozen=True)
class App:
    op: str
    args: tuple["Term", ...]
    type: str


Term = Any  # Atom | App


def term_type(term: Term) -> str:
    return term.type


def sexpr(term: Term) -> str:
    if isinstance(term, Atom):
        return term.name
    return "(" + term.op + ("".join(" " + sexpr(arg) for arg in term.args)) + ")"


# --------------------------------------------------------------------------- #
# A curated, monomorphic operation set that *references* LEXICON canonicals.    #
# The LEXICON ``type_signature`` strings are curried / dependent and not meant  #
# to be machine-parsed; we attach clean signatures keyed by the same names so   #
# meanings (and backend theories) stay single-sourced.                          #
# --------------------------------------------------------------------------- #


def _op(name: str, inputs: tuple[str, ...], output: str, *tags: str, cost: int = 1) -> Operation:
    return Operation(
        name=name,
        input_types=inputs,
        output_type=output,
        semantic_tags=tuple(tags) or (name,),
        backend_theory=_BACKEND_BY_CANONICAL.get(name.lower(), ""),
        cost=cost,
    )


GEOMETRY_OPS: tuple[Operation, ...] = (
    _op("area", ("Region",), "Real", "area", "面積"),
    _op("bounded_region", ("SetPoint",), "Region", "bounded_region", "領域"),
    _op("locus", ("Point",), "SetPoint", "locus", "軌跡"),
    _op("centroid", ("Polygon",), "Point", "centroid", "重心"),
    _op("circumcenter", ("Triangle",), "Point", "circumcenter", "外心"),
    _op("incenter", ("Triangle",), "Point", "incenter", "内心"),
    _op("midpoint", ("Point", "Point"), "Point", "midpoint", "中点", cost=2),
    _op("equilateral_triangle_on_curve", ("Curve",), "Triangle", "equilateral", "正三角形"),
)


# --------------------------------------------------------------------------- #
# Candidate + observability.                                                    #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Candidate:
    term: Term
    type: str
    depth: int
    cost: int
    semantic_score: float
    covered: frozenset[str] = frozenset()

    def sexpr(self) -> str:
        return sexpr(self.term)


def explain(candidate: Candidate, goal_type: str) -> dict[str, Any]:
    term = candidate.term
    selected_rule = term.op if isinstance(term, App) else f"atom:{term.name}"
    subgoals = [arg.type for arg in term.args] if isinstance(term, App) else []
    return {
        "goal_type": goal_type,
        "term": candidate.sexpr(),
        "selected_rule": selected_rule,
        "subgoals": subgoals,
        "bindings": {},
        "type_checks": [f"{candidate.type} <: {goal_type}"],
        "semantic_score": candidate.semantic_score,
        "cost": candidate.cost,
        "depth": candidate.depth,
        "rejected_reason": None,
    }


# --------------------------------------------------------------------------- #
# Type-directed synthesis (type inhabitation with pruning).                     #
# --------------------------------------------------------------------------- #


def apply_op(op: Operation, args: tuple[Term, ...]) -> App | None:
    """Build an application only if every argument types-checks. Returns None
    otherwise -- this is the generation-time guard that makes ``Area(Point)`` or
    ``Centroid(Real)`` impossible to construct in the first place."""
    if len(args) != len(op.input_types):
        return None
    for arg, expected in zip(args, op.input_types):
        if not is_subtype(term_type(arg), expected):
            return None
    return App(op=op.name, args=args, type=op.output_type)


def synthesize(
    goal_type: str,
    atoms: Iterable[Atom],
    operations: Iterable[Operation] = GEOMETRY_OPS,
    *,
    max_depth: int = 7,
    concept_hints: frozenset[str] = frozenset(),
    beam: int = 8,
    _ancestors: tuple[str, ...] = (),
) -> list[Candidate]:
    """Return well-typed terms whose type is a subtype of ``goal_type``.

    Backward search: pick an operation that outputs the goal type, recurse on its
    input types, fill leaves with atoms.  Type-incompatible branches are never
    built (not generated then filtered).  Self-similar recursion (e.g. a Point
    built from Points) is bounded by both ``max_depth`` and an ancestor guard so
    the search terminates.
    """
    atoms = list(atoms)
    operations = list(operations)
    candidates: list[Candidate] = []

    # Base case: an available atom that fits the goal type.
    for atom in atoms:
        if is_subtype(atom.type, goal_type):
            candidates.append(Candidate(atom, atom.type, depth=1, cost=0, semantic_score=0.0, covered=frozenset()))

    if max_depth <= 1:
        return _rank(candidates, concept_hints, beam)

    for op in operations:
        if not is_subtype(op.output_type, goal_type):
            continue
        # Ancestor guard: allow an output type to recur at most once on a path.
        if _ancestors.count(op.output_type) >= 1 and op.output_type in op.input_types:
            continue
        per_arg: list[list[Candidate]] = []
        ok = True
        for input_type in op.input_types:
            sub = synthesize(
                input_type,
                atoms,
                operations,
                max_depth=max_depth - 1,
                concept_hints=concept_hints,
                beam=beam,
                _ancestors=_ancestors + (op.output_type,),
            )
            if not sub:
                ok = False
                break
            per_arg.append(sub[:beam])
        if not ok:
            continue
        for combo in _product(per_arg):
            app = apply_op(op, tuple(c.term for c in combo))
            if app is None:
                continue
            depth = 1 + max((c.depth for c in combo), default=0)
            if depth > max_depth:
                continue
            cost = op.cost + sum(c.cost for c in combo)
            # Alignment is coverage of *distinct* hinted concepts, not a count --
            # using a hinted op twice must not beat a simpler covering term.
            covered = frozenset(concept_hints & set(op.semantic_tags))
            for c in combo:
                covered |= c.covered
            candidates.append(
                Candidate(app, op.output_type, depth, cost, float(len(covered)), covered)
            )

    return _rank(candidates, concept_hints, beam)


def _product(per_arg: list[list[Candidate]]) -> Iterable[tuple[Candidate, ...]]:
    if not per_arg:
        yield ()
        return
    head, *tail = per_arg
    for item in head:
        for rest in _product(tail):
            yield (item, *rest)


def _rank(candidates: list[Candidate], concept_hints: frozenset[str], beam: int) -> list[Candidate]:
    seen: set[str] = set()
    unique: list[Candidate] = []
    for cand in candidates:
        key = cand.sexpr()
        if key in seen:
            continue
        seen.add(key)
        unique.append(cand)
    # Best first: cover more distinct hinted concepts, then shallower, then
    # cheaper, then stable lexicographic tie-break for determinism.
    unique.sort(key=lambda c: (-len(c.covered), c.depth, c.cost, c.sexpr()))
    return unique[: max(beam, 1)]


# --------------------------------------------------------------------------- #
# Laws and unknown-slot unification (the arithmetic side).                      #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Law:
    """A single relation solved for whichever slot is unknown.

    ``kind="linear"`` encodes ``sum(coeff[s] * slot[s]) == const``.  One linear
    solver then solves for *any* slot -- there is no per-unknown function.
    ``kind="product"`` encodes ``out == product(factors)``.
    """

    name: str
    kind: str
    slot_types: dict[str, str]
    coeffs: dict[str, Fraction] = field(default_factory=dict)
    const: Fraction = Fraction(0)
    out_slot: str | None = None
    factor_slots: tuple[str, ...] = ()


CONSERVATION = Law(
    name="state_conservation",
    kind="linear",
    slot_types={"initial": "Quantity", "gain": "Quantity", "loss": "Quantity", "final": "Quantity"},
    # initial + gain - loss - final == 0
    coeffs={"initial": Fraction(1), "gain": Fraction(1), "loss": Fraction(-1), "final": Fraction(-1)},
    const=Fraction(0),
)

PART_WHOLE = Law(
    name="part_whole",
    kind="linear",
    slot_types={"whole": "Quantity", "part": "Quantity", "rest": "Quantity"},
    # part + rest - whole == 0
    coeffs={"part": Fraction(1), "rest": Fraction(1), "whole": Fraction(-1)},
    const=Fraction(0),
)

DIFFERENCE = Law(
    name="difference",
    kind="linear",
    slot_types={"big": "Quantity", "small": "Quantity", "diff": "Quantity"},
    # big - small - diff == 0
    coeffs={"big": Fraction(1), "small": Fraction(-1), "diff": Fraction(-1)},
    const=Fraction(0),
)

RATE_PRODUCT = Law(
    name="rate_product",
    kind="product",
    slot_types={"money": "Money", "rate": "Rate", "count": "Count"},
    out_slot="money",
    factor_slots=("rate", "count"),
)

PRIMITIVE_LAWS: tuple[Law, ...] = (CONSERVATION, PART_WHOLE, DIFFERENCE, RATE_PRODUCT)


class LawError(ValueError):
    pass


def solve_law(law: Law, bindings: dict[str, Fraction]) -> tuple[str, Fraction]:
    """Given values for all-but-one slot, solve for the remaining slot.

    The same solver handles every unknown position of a law -- this is the
    unknown-slot unification that replaces per-unknown builders.
    """
    unknowns = [slot for slot in law.slot_types if slot not in bindings]
    if len(unknowns) != 1:
        raise LawError(f"{law.name}: expected exactly one unknown slot, got {unknowns}")
    unknown = unknowns[0]

    if law.kind == "linear":
        # coeff[unknown]*x = const - sum_{s != unknown} coeff[s]*value[s]
        acc = law.const
        for slot, coeff in law.coeffs.items():
            if slot == unknown:
                continue
            acc -= coeff * Fraction(bindings[slot])
        denom = law.coeffs[unknown]
        if denom == 0:
            raise LawError(f"{law.name}: zero coefficient for unknown {unknown}")
        return unknown, acc / denom

    if law.kind == "product":
        out = law.out_slot
        if unknown == out:
            value = Fraction(1)
            for factor in law.factor_slots:
                value *= Fraction(bindings[factor])
            return unknown, value
        # Solve for a factor: factor = out / product(other factors)
        numerator = Fraction(bindings[out])
        denom = Fraction(1)
        for factor in law.factor_slots:
            if factor == unknown:
                continue
            denom *= Fraction(bindings[factor])
        if denom == 0:
            raise LawError(f"{law.name}: division by zero solving for {unknown}")
        return unknown, numerator / denom

    raise LawError(f"{law.name}: unknown law kind {law.kind}")


# Additive type compatibility, mirroring semantic_logic's many-sorted check.
_ADDITIVE_GROUPS = (
    frozenset({"Quantity", "Count", "Scalar"}),
    frozenset({"Money"}),
    frozenset({"Time"}),
)


def sorts_addable(sort_a: str, sort_b: str) -> bool:
    if sort_a == sort_b:
        return True
    return any({sort_a, sort_b} <= group for group in _ADDITIVE_GROUPS)


def instantiate_law(
    law: Law,
    typed_values: dict[str, tuple[Fraction, str]],
) -> tuple[str, Fraction]:
    """Map typed quantities onto law slots, reject sort-incompatible additions,
    and solve for the missing slot.

    ``typed_values`` maps slot name -> (value, sort).  A linear (additive) law
    requires its bound slots to share an additive super-sort; e.g. mixing
    ``Money`` and ``Time`` is rejected here, not after the fact.
    """
    if law.kind == "linear":
        sorts = [sort for _, (_, sort) in typed_values.items()]
        for other in sorts[1:]:
            if not sorts_addable(sorts[0], other):
                raise LawError(f"{law.name}: incompatible additive sorts {sorts}")
    bindings = {slot: value for slot, (value, _) in typed_values.items()}
    return solve_law(law, bindings)


# --------------------------------------------------------------------------- #
# Convenience entry points for integration (called *before* legacy builders).  #
# --------------------------------------------------------------------------- #


def synthesize_area_goal(concept_hints: frozenset[str] = frozenset()) -> Candidate | None:
    """Synthesize an area-of-bounded-locus goal term from type signatures only.

    Replaces the hard-coded ``(area (bounded_region (locus (centroid ...))))``
    string in ``formal_language``: the same term now falls out of the operation
    signatures, and swapping the Point producer (centroid/circumcenter/...) is a
    type-preserving change driven by ``concept_hints``.
    """
    curve = Atom("curve", "Curve", kind="const")
    hints = concept_hints or frozenset({"area", "locus", "centroid", "equilateral"})
    results = synthesize("Real", [curve], GEOMETRY_OPS, max_depth=7, concept_hints=hints)
    return results[0] if results else None
