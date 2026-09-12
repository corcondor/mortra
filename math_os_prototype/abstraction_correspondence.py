"""Acquiring an abstract object together with the operations that survive on it.

Keeping only part of an object is easy. What makes the remainder usable is that
the operations still land somewhere definite:

    concrete x ------- f ------> f(x)
        |                          |
      alpha                      alpha
        |                          |
    abstract a ----- f_bar -----> f_bar(a)

so that alpha(f(x)) = f_bar(alpha(x)). Equivalently, alpha(x) = alpha(y) must
force alpha(f(x)) = alpha(f(y)); otherwise f_bar is not a function and the
abstract object cannot be computed with.

One description of the abstract side
    Every stage -- proposing an abstraction, proving an operation descends,
    storing what was acquired, and generating what to do next -- reads the same
    `abstract_signature`: one coordinate name per component of alpha, the
    explicitly declared parameters, and nothing else. The feature list handed to
    the guesser is built from that signature in that order, so the index a
    relation refers to and the name it is rewritten with cannot disagree.

    Only those names may appear in a candidate for the induced operation. A
    state variable that alpha discarded is not available on the abstract side,
    so it is not offered to the search either.

What the witnesses are for and what they are not
    A witness binds each hole to a concrete program so a candidate can be
    proposed and screened. Two declared inputs may happen to be the same program
    under one witness; that is a fact about the witness, not about the abstract
    names, and it never merges the names. Admission rests on `prove_identity`
    over independent symbols, and the candidate search is decided by the same
    identity, so a relation that fits these operands without being an identity
    is discarded where it is found rather than admitted and refused later.

The image of alpha
    Abstract coordinates need not be independent: alpha may be redundant, and a
    redundant coordinate is not an error. What is required is that the relations
    holding on the image are recorded, so a quantity that looks preserved can be
    told apart from one that was never free to vary there. `classify_on_image`
    substitutes alpha back in and says which of the three a quantity is.

What is deliberately not claimed
    Nothing here computes all invariant relations of the operations, nothing
    computes the full ideal of the image, and nothing replaces a concrete object
    by an abstract one. A correspondence records what it supports; the concrete
    route stays available for everything else.
"""
from __future__ import annotations

from copy import deepcopy

from math_os_prototype.holonomic_joint_relations import (
    certify_relation, guess_relations, make_features, relation_program)
from math_os_prototype.holonomic_route_discovery import certify_equal, key
from math_os_prototype.representation_progress import digest

SCHEMA = "mortra.abstraction-correspondence.v3"
SCOPE = ("one abstraction with the operations proved to descend to it; not a "
         "complete set of invariants, not the full ideal of the image, and not a "
         "replacement for the concrete objects")

# ---- what a search procedure is allowed to report -------------------------
#
# A boolean cannot tell "this candidate is wrong" from "there is no candidate"
# from "this procedure does not handle it", and collapsing them makes a whole
# mathematical question look settled when only one method declined. Every
# procedure here returns one of these with the grammar it searched, the premises
# it used, and what it spent.

PROVED = "PROVED"
CANDIDATE_REFUTED = "CANDIDATE_REFUTED"
NO_SOLUTION_IN_SPACE = "NO_SOLUTION_IN_SPACE"
NOT_APPLICABLE = "NOT_APPLICABLE"
OPEN_OBLIGATIONS = "OPEN_OBLIGATIONS"
SUSPENDED = "SUSPENDED"
BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
INTERNAL_ERROR = "INTERNAL_ERROR"
STATUSES = (PROVED, CANDIDATE_REFUTED, NO_SOLUTION_IN_SPACE, NOT_APPLICABLE,
            OPEN_OBLIGATIONS, SUSPENDED, BUDGET_EXHAUSTED, INTERNAL_ERROR)


def verdict(status, *, reason, grammar=None, premises=(), spent=None, **extra):
    """One result, saying what was searched and under what assumptions."""
    if status not in STATUSES:
        raise ValueError(f"unknown result status {status!r}")
    record = {"status": status, "reason": reason, "grammar": grammar,
              "premises": list(premises), "spent": dict(spent or {}),
              "found": status == PROVED}
    record.update(extra)
    return record


# ---- programs with holes --------------------------------------------------

def slot(name):
    """A hole standing for one named argument."""
    return {"op": "hyper", "a": [f"__slot__{name}"], "b": []}


def _slot_name(program):
    if program.get("op") == "hyper" and len(program.get("a", [])) == 1:
        first = str(program["a"][0])
        if first.startswith("__slot__"):
            return first[len("__slot__"):]
    return None


def fill(template, bindings):
    """Replace every hole by the program bound to it."""
    name = _slot_name(template)
    if name is not None:
        if name not in bindings:
            raise ValueError(f"no program was bound to slot {name}")
        return deepcopy(bindings[name])
    built = deepcopy(template)
    if built["op"] in ("add", "mul"):
        built["left"] = fill(template["left"], bindings)
        built["right"] = fill(template["right"], bindings)
    elif built["op"] in ("diff", "scale", "pullback"):
        built["child"] = fill(template["child"], bindings)
    return built


def slot_expressions(names, *, depth=1, factors=("2", "-1")):
    """Programs over the given holes, built by the existing ring operations.

    One grammar, used wherever a candidate expression over named holes is
    needed: abstraction candidates, morphism candidates, and the parameter of a
    composition law all come from here.
    """
    built = [slot(name) for name in names]
    for _ in range(depth):
        grown = list(built)
        for left in built:
            for right in built:
                grown.append({"op": "add", "left": deepcopy(left),
                              "right": deepcopy(right)})
                grown.append({"op": "mul", "left": deepcopy(left),
                              "right": deepcopy(right)})
            for factor in factors:
                grown.append({"op": "scale", "child": deepcopy(left), "factor": factor})
        seen, unique = set(), []
        for program in grown:
            name = digest(program)
            if name not in seen:
                seen.add(name)
                unique.append(program)
        built = unique
    return built


# ---- the ring fragment ----------------------------------------------------

RING_OPERATIONS = ("add", "mul", "scale")
RING_LAW = ("commutative ring: addition and multiplication of the operands, and "
            "scaling by a constant")
SYMBOL_PREFIX = "sym_"


class OutsideRingFragment(ValueError):
    """Raised when a program needs a law the ring axioms do not supply."""


def ring_expression(template, symbols=None):
    """Read a slot program as an expression in independent symbols.

    Only the operations whose meaning is fixed by the ring axioms are accepted.
    Differentiation and pullback are refused rather than translated, because
    their laws are extra assumptions and a proof that quietly used them would be
    claiming more than the axioms give.
    """
    import sympy as sp

    if symbols is None:
        symbols = {}
    name = _slot_name(template)
    if name is not None:
        return symbols.setdefault(name, sp.Symbol(f"{SYMBOL_PREFIX}{name}"))
    op = template.get("op")
    if op == "add":
        return (ring_expression(template["left"], symbols)
                + ring_expression(template["right"], symbols))
    if op == "mul":
        return (ring_expression(template["left"], symbols)
                * ring_expression(template["right"], symbols))
    if op == "scale":
        return sp.Rational(str(template["factor"])) * ring_expression(
            template["child"], symbols)
    if op == "poly":
        coefficients = [sp.Rational(str(c)) for c in template["coefficients"]]
        if any(c != 0 for c in coefficients[1:]):
            raise OutsideRingFragment(
                "only a constant polynomial is a ring constant here")
        return coefficients[0] if coefficients else sp.Integer(0)
    raise OutsideRingFragment(
        f"operation {op!r} is outside {RING_LAW}; its law would have to be supplied")


def ring_program(expression):
    """Write a polynomial in the symbols back as a program over the same holes.

    The inverse of `ring_expression` on the fragment it accepts. A quantity that
    has been solved for -- a conserved quantity, a composition parameter -- only
    becomes something later stages can carry, fill and run once it is a program
    again.
    """
    import sympy as sp

    expression = sp.expand(sp.sympify(expression))
    if expression.is_number:
        return {"op": "poly", "coefficients": [str(sp.Rational(expression))]}
    if expression.is_Symbol:
        name, order = jet_name(expression)
        if name is None:
            return slot(str(expression))
        built = slot(name)
        for _ in range(order):
            built = {"op": "diff", "child": built}
        return built
    if expression.is_Add:
        built = None
        for argument in expression.args:
            piece = ring_program(argument)
            built = piece if built is None else {"op": "add", "left": built,
                                                 "right": piece}
        return built
    if expression.is_Mul:
        coefficient, rest = expression.as_coeff_Mul()
        if coefficient != 1:
            return {"op": "scale", "child": ring_program(rest),
                    "factor": str(sp.Rational(coefficient))}
        built = None
        for argument in expression.args:
            piece = ring_program(argument)
            built = piece if built is None else {"op": "mul", "left": built,
                                                 "right": piece}
        return built
    if expression.is_Pow:
        base, exponent = expression.args
        if not (exponent.is_Integer and exponent > 0):
            raise OutsideRingFragment(f"the exponent {exponent} is outside {RING_LAW}")
        built = ring_program(base)
        for _ in range(int(exponent) - 1):
            built = {"op": "mul", "left": deepcopy(built), "right": ring_program(base)}
        return built
    raise OutsideRingFragment(f"{expression} is not a polynomial over {RING_OPERATIONS}")


def normal_form(programs):
    """A key two programs share exactly when they denote the same expression.

    `scale(u, "2")` and `add(u, u)` are different programs and the same
    abstraction. Keying on the syntax offers both, proves the same operations
    twice, and reports one object as two; keying on the normalised expression
    does not. A program outside the fragment keeps its syntactic key, because
    nothing here can say what else it might equal.
    """
    import sympy as sp

    def one(program):
        try:
            return sp.srepr(sp.expand(ring_expression(program, {})))
        except OutsideRingFragment:
            return digest(program)

    if isinstance(programs, dict) and "op" in programs:
        return digest([one(programs)])
    if isinstance(programs, dict):
        return digest([f"{name}={one(programs[name])}" for name in sorted(programs)])
    return digest([one(program) for program in programs])


# ---- the same ring, with a derivation ------------------------------------

DERIVATION_LAW = ("commutative differential ring: the ring operations together with "
                  "a derivation D that is additive, obeys the Leibniz rule, and "
                  "sends constants to zero")


class OutsideDifferentialFragment(OutsideRingFragment):
    """Raised when a program needs a law neither the ring nor the derivation gives."""


def jet_symbol(name, order=0):
    """The symbol standing for the `order`-th derivative of a hole."""
    import sympy as sp

    return sp.Symbol(f"{SYMBOL_PREFIX}{name}" + ("" if order == 0 else f"__d{order}"))


def jet_name(symbol):
    """The hole and derivative order a jet symbol stands for."""
    text = str(symbol)
    if not text.startswith(SYMBOL_PREFIX):
        return None, 0
    text = text[len(SYMBOL_PREFIX):]
    if "__d" in text:
        head, _, order = text.partition("__d")
        return head, int(order)
    return text, 0


def derive(expression):
    """The derivation on the polynomial ring the jet symbols generate.

    Additive and Leibniz by construction, because on a polynomial the chain rule
    over the jet variables is exactly that derivation, and it sends every
    constant to zero. This is a law about every element of such a ring, not a
    fact about the series that were tried.
    """
    import sympy as sp

    total = sp.Integer(0)
    for symbol in sorted(expression.free_symbols, key=str):
        name, order = jet_name(symbol)
        if name is None:
            continue
        total += sp.diff(expression, symbol) * jet_symbol(name, order + 1)
    return sp.expand(total)


def differential_expression(template, symbols=None):
    """Read a program as an element of the differential ring.

    Everything `ring_expression` accepts, and `diff` besides. `pullback`, `ode`
    and `hyper` with real parameters stay outside: composition and a named
    special function are not consequences of these axioms.
    """
    import sympy as sp

    if symbols is None:
        symbols = {}
    name = _slot_name(template)
    if name is not None:
        return symbols.setdefault(name, jet_symbol(name, 0))
    op = template.get("op")
    if op == "add":
        return (differential_expression(template["left"], symbols)
                + differential_expression(template["right"], symbols))
    if op == "mul":
        return (differential_expression(template["left"], symbols)
                * differential_expression(template["right"], symbols))
    if op == "scale":
        return sp.Rational(str(template["factor"])) * differential_expression(
            template["child"], symbols)
    if op == "diff":
        return derive(sp.expand(differential_expression(template["child"], symbols)))
    if op == "poly":
        coefficients = [sp.Rational(str(c)) for c in template["coefficients"]]
        if any(c != 0 for c in coefficients[1:]):
            raise OutsideDifferentialFragment(
                "only a constant polynomial is a constant of this ring")
        return coefficients[0] if coefficients else sp.Integer(0)
    raise OutsideDifferentialFragment(
        f"operation {op!r} is outside {DERIVATION_LAW}; its law would have to be "
        "supplied")


def uses_derivation(expression):
    return any(jet_name(s)[1] > 0 for s in expression.free_symbols)


def prove_identity(left_template, right_template):
    """Is the difference identically zero in independent symbols?

    This is the statement the acceptance needs and the one `certify_equal`
    cannot make: it holds for every input in any commutative ring, not for the
    operands that happened to be tried. Once it holds, condition (2) follows,
    because alpha(f(x)) is computed from alpha(x) alone.

    The reader is the differential one, so a program that differentiates is
    decided by the derivation axioms rather than refused. Which law was actually
    needed is reported, because a claim under the derivation axioms is a
    different claim from one under the ring axioms alone.
    """
    import sympy as sp

    symbols = {}
    try:
        left = differential_expression(left_template, symbols)
        right = differential_expression(right_template, symbols)
    except OutsideRingFragment as exc:
        return {"proved": False, "reason": str(exc), "law": DERIVATION_LAW,
                "fragment": None, "outside_fragment": True}
    residual = sp.expand(left - right)
    differential = uses_derivation(left) or uses_derivation(right)
    return {"proved": residual == 0,
            "reason": ("the difference normalises to zero for independent inputs"
                       if residual == 0 else
                       f"the difference does not vanish: {sp.srepr(residual)[:120]}"),
            "law": DERIVATION_LAW if differential else RING_LAW,
            "fragment": "differential ring" if differential else "commutative ring",
            "outside_fragment": False,
            "symbols": sorted(str(s) for s in symbols.values()),
            "residual": "0" if residual == 0 else str(residual)}


# ---- one description of the abstract side ---------------------------------

def abstract_signature(alpha, *, coordinate_names, parameter_names=()):
    """The names the abstract side has, in the order every stage uses them.

    A coordinate for each component of alpha and the parameters that were
    declared. Nothing else is an abstract argument: a state variable alpha threw
    away has no name here and therefore never reaches a candidate.
    """
    coordinate_names = list(coordinate_names)
    parameter_names = list(parameter_names)
    if len(coordinate_names) != len(alpha):
        raise ValueError("one coordinate name is needed for each component of alpha")
    names = coordinate_names + parameter_names
    if len(set(names)) != len(names):
        raise ValueError("coordinate and parameter names must be distinct")
    return {"schema": "mortra.abstract-signature.v1",
            "alpha": deepcopy(list(alpha)),
            "coordinate_names": coordinate_names,
            "parameter_names": parameter_names,
            "names": names,
            "law": RING_LAW}


def abstract_inputs(signature, bindings):
    """What each abstract name stands for under one witness, in feature order.

    The order is the signature's order, so feature origin `i + 1` is
    `signature["names"][i]` by construction rather than by coincidence.
    """
    programs = [fill(part, bindings) for part in signature["alpha"]]
    for name in signature["parameter_names"]:
        if name not in bindings:
            raise ValueError(f"the witness binds no program to the parameter {name}")
        programs.append(deepcopy(bindings[name]))
    return programs


def signature_state_names(signature):
    """The holes alpha reads, which is what a morphism has to rearrange."""
    found = set()

    def walk(template):
        name = _slot_name(template)
        if name is not None:
            found.add(name)
            return
        if template.get("op") in ("add", "mul"):
            walk(template["left"])
            walk(template["right"])
        elif template.get("op") in ("diff", "scale", "pullback"):
            walk(template["child"])

    for part in signature["alpha"]:
        walk(part)
    return sorted(found)


def _abstract_to_state(signature, template):
    """Read a program over the abstract names back as a program over the holes."""
    bindings = {name: signature["alpha"][index]
                for index, name in enumerate(signature["coordinate_names"])}
    bindings.update({name: slot(name) for name in signature["parameter_names"]})
    return fill(template, bindings)


# ---- alpha and the conditions that hold on its image ----------------------

def alpha_expressions(signature):
    """Each component of alpha as an expression in the state symbols."""
    return [ring_expression(part, {}) for part in signature["alpha"]]


def image_substitution(signature):
    """The map that sends each abstract coordinate to what alpha makes of it."""
    import sympy as sp

    parts = alpha_expressions(signature)
    return {sp.Symbol(f"{SYMBOL_PREFIX}{name}"): parts[index]
            for index, name in enumerate(signature["coordinate_names"])}


def classify_on_image(expression, signature):
    """What a quantity on the abstract coordinates is, once alpha is put back in.

    Three outcomes, and the coordinates being redundant is not by itself a
    defect:

        identically zero -- a relation that holds on the image, so it says what
                            the abstract domain is rather than what an operation
                            preserves
        constant         -- a constant observation on the image
        otherwise        -- a quantity that actually varies there
    """
    import sympy as sp

    try:
        value = sp.expand(sp.sympify(expression).subs(image_substitution(signature),
                                                      simultaneous=True))
    except OutsideRingFragment as exc:
        return {"class": "unknown", "reason": str(exc), "on_image": None}
    if value == 0:
        return {"class": "domain_relation", "on_image": "0",
                "reason": "vanishes identically once alpha is substituted, so it is a "
                          "relation the image satisfies rather than a quantity on it"}
    if not value.free_symbols:
        return {"class": "constant", "on_image": str(value),
                "reason": "takes one value on the image"}
    return {"class": "observable", "on_image": str(value),
            "reason": "varies on the image of alpha"}


# ---- condition (2), decided by the same law the acceptance uses -----------

def _same_expression(left_template, right_template, bindings=None):
    """Equal as ring expressions; only if that cannot be asked, equal as series."""
    import sympy as sp

    try:
        left = differential_expression(left_template, {})
        right = differential_expression(right_template, {})
    except OutsideRingFragment:
        if bindings is None:
            return False
        return certify_equal(fill(left_template, bindings),
                             fill(right_template, bindings)
                             )["status"] == "exact_formal_series_equality"
    return sp.expand(left - right) == 0


def preserves_abstraction(signature, morphism, bindings=None):
    """Does g leave alpha untouched, so g(x) is another x with the same image?"""
    return all(_same_expression(fill(part, morphism), part, bindings)
               for part in signature["alpha"])


def descends(signature, morphism, rearrangements, bindings=None):
    """Check condition (2) itself, not a proxy for it.

    If g leaves alpha unchanged then x and g(x) are two concrete objects with one
    image, so f may only descend when alpha(f(x)) and alpha(f(g(x))) agree as
    well. This is a refutation: passing it admits nothing on its own.
    """
    failures = []
    for name, rearrangement in rearrangements.items():
        after_morphism = {slotname: fill(program, rearrangement)
                          for slotname, program in morphism.items()}
        for index, part in enumerate(signature["alpha"]):
            if not _same_expression(fill(part, morphism),
                                    fill(part, after_morphism), bindings):
                failures.append({"rearrangement": name, "component": index})
    return {"descends": not failures, "failures": failures,
            "rearrangements_checked": sorted(rearrangements)}


# ---- writing something over the declared abstract names -------------------

def _uses(feature, origin):
    return any(factor["origin"] == origin for factor in feature["factors"])


def _linear_target(features, origin=0):
    """The feature that is exactly the left hand side, once and undifferentiated."""
    for index, feature in enumerate(features):
        if (feature["power_x"] == 0 and len(feature["factors"]) == 1
                and feature["factors"][0] == {"origin": origin, "derivative": 0}):
            return index
    return None


def _usable_terms(features, holdout=16, origin=0):
    """Every relation that writes the left hand side in the other coordinates.

    The left side has to appear exactly once and undifferentiated, and no other
    term may mention it, or the relation would express the left side through
    itself. All of them are yielded rather than the first: which candidate the
    guesser puts first depends on how many features were built, and a usable
    relation further down the list would otherwise be lost.
    """
    target = _linear_target(features, origin)
    if target is None:
        return
    for candidate in guess_relations(features, holdout=holdout)["candidates"]:
        terms = candidate["terms"]
        if not any(term["feature"] == target for term in terms):
            continue
        if any(term["feature"] != target and _uses(features[term["feature"]], origin)
               for term in terms):
            continue
        yield terms


def induced_template(terms, features, names):
    """Rebuild a certified relation as a program over the declared names.

    The relation comes back as coefficients against features, which is a fact
    about the operands it was found with. Rewriting it over the signature's
    holes turns it into something that can be applied to any input, which is the
    whole point of acquiring it. Feature origin `i + 1` is `names[i]`, because
    the feature list was built from the signature in that order.
    """
    import sympy as sp

    target = _linear_target(features)
    lead = next(sp.Rational(str(t["coefficient"]))
                for t in terms if t["feature"] == target)
    built = None
    for term in terms:
        if term["feature"] == target:
            continue
        feature = features[term["feature"]]
        if feature["power_x"] != 0:
            raise OutsideRingFragment("a term carries a power of x, which is not a hole")
        piece = None
        for factor in feature["factors"]:
            if factor["derivative"] != 0:
                raise OutsideRingFragment("a term is differentiated, which the ring "
                                          "axioms do not cover")
            index = factor["origin"] - 1
            if not 0 <= index < len(names):
                raise OutsideRingFragment(
                    f"a term refers to input {factor['origin']}, which the signature "
                    "does not name")
            here = slot(names[index])
            piece = here if piece is None else {"op": "mul", "left": piece,
                                                "right": here}
        coefficient = -sp.Rational(str(term["coefficient"])) / lead
        if piece is None:
            piece = {"op": "poly", "coefficients": [str(coefficient)]}
        elif coefficient != 1:
            piece = {"op": "scale", "child": piece, "factor": str(coefficient)}
        built = piece if built is None else {"op": "add", "left": built, "right": piece}
    if built is None:
        built = {"op": "poly", "coefficients": ["0"]}
    return built


def _projection(signature, left_template):
    """Is the composite already one of the declared abstract names?

    Asked over the symbols, not over a witness. This is the case an operation
    that fixes a component of alpha lands in -- the identity above all -- and
    the relation guesser cannot be asked about it, because expressing a name
    through itself is exactly what it refuses to do. Refusing an operation here
    for that reason would confuse "this rearrangement does nothing on the
    abstract side" with "this relation is empty".
    """
    import sympy as sp

    try:
        composite = differential_expression(left_template, {})
    except OutsideRingFragment:
        return None
    for index, part in enumerate(signature["alpha"]):
        try:
            value = differential_expression(part, {})
        except OutsideRingFragment:
            continue
        if sp.expand(composite - value) == 0:
            return signature["coordinate_names"][index]
    for name in signature["parameter_names"]:
        if sp.expand(composite - jet_symbol(name, 0)) == 0:
            return name
    return None


def _collisions(programs, labels):
    """Declared inputs that this witness happens to make the same program."""
    seen, clashes = {}, []
    for label, program in zip(labels, programs):
        encoded = key(program)
        if encoded in seen:
            clashes.append(f"{seen[encoded]} and {label}")
        else:
            seen[encoded] = label
    return clashes


def monomial_basis(names, *, degree=2, derivatives=0):
    """The span a complete solve is complete in, and its generators.

    Generators are the declared names and, when the derivation is in play, their
    derivatives up to the stated order. Nothing outside this span is claimed
    either way: a higher degree, a rational function, or another representation
    may still hold what this span does not.
    """
    import sympy as sp
    from itertools import combinations_with_replacement

    generators = [jet_symbol(name, order)
                  for name in names for order in range(derivatives + 1)]
    built, seen, unique = [sp.Integer(1)], set(), []
    for size in range(1, degree + 1):
        for pick in combinations_with_replacement(generators, size):
            built.append(sp.prod(pick))
    for monomial in built:
        text = sp.srepr(sp.expand(monomial))
        if text not in seen:
            seen.add(text)
            unique.append(monomial)
    return generators, unique


def _image_substitution(signature, derivatives):
    """Each abstract name, and each of its derivatives, in the state symbols."""
    substitution = {}
    for name, part in zip(signature["coordinate_names"], signature["alpha"]):
        value = differential_expression(part, {})
        for order in range(derivatives + 1):
            substitution[jet_symbol(name, order)] = value
            value = derive(value)
    return substitution


def solve_component(signature, left_template, *, degree=2, derivatives=0):
    """Solve for one component in a declared span, by comparing coefficients.

    alpha, the operation and the span are fixed and the unknowns are the
    coefficients. No witness is consulted and no coefficient is guessed from
    one: the identity is required over the independent state symbols, so the
    answer cannot depend on which operands happened to be bound.

    Complete in the span it declares, and silent outside it. `NO_SOLUTION_IN_SPACE`
    means this span has none, not that the induced operation does not exist.
    """
    import sympy as sp

    grammar = {"space": "linear span of monomials over the declared abstract names",
               "names": list(signature["names"]), "degree": degree,
               "derivatives": derivatives}
    premises = [DERIVATION_LAW if derivatives else RING_LAW]
    try:
        left = sp.expand(differential_expression(left_template, {}))
        substitution = _image_substitution(signature, derivatives)
    except OutsideRingFragment as exc:
        return verdict(NOT_APPLICABLE, reason=str(exc), grammar=grammar,
                       premises=premises, template=None, proof=None, terms=None,
                       certificate=None, residual=None, route="coefficient comparison")

    generators, monomials = monomial_basis(signature["names"], degree=degree,
                                           derivatives=derivatives)
    unknowns = sp.symbols(f"lam0:{len(monomials)}")
    candidate = sum(u * m for u, m in zip(unknowns, monomials))
    residual = sp.expand(candidate.subs(substitution, simultaneous=True) - left)
    free = sorted(residual.free_symbols - set(unknowns), key=str)
    equations = list(sp.Poly(residual, *free).coeffs()) if free else [residual]
    solution = sp.linsolve(equations, unknowns)
    spent = {"monomials": len(monomials), "equations": len(equations)}
    if solution is sp.EmptySet or len(solution) == 0:
        return verdict(NO_SOLUTION_IN_SPACE,
                       reason=("the coefficient comparison is inconsistent, so this "
                               "span contains no such component; a larger degree, a "
                               "rational form or another representation is untouched"),
                       grammar=grammar, premises=premises, spent=spent,
                       template=None, proof=None, terms=None, certificate=None,
                       residual=None, route="coefficient comparison")
    values = list(next(iter(solution)))
    remaining = set()
    for value in values:
        remaining |= set(value.free_symbols) & set(unknowns)
    values = [sp.expand(v.subs({u: 0 for u in remaining})) for v in values]
    solved = sp.expand(sum(v * m for v, m in zip(values, monomials)))
    template = ring_program(solved)
    proof = prove_identity(left_template, _abstract_to_state(signature, template))
    if not proof["proved"]:
        return verdict(INTERNAL_ERROR,
                       reason=("the linear solve returned a component the identity "
                               f"check rejects: residual {proof['residual'][:60]}"),
                       grammar=grammar, premises=premises, spent=spent,
                       template=template, proof=proof, terms=None, certificate=None,
                       residual=None, route="coefficient comparison")
    return verdict(PROVED,
                   reason=("solved in the declared span and proved for independent "
                           "inputs"),
                   grammar=grammar, premises=[proof["law"]], spent=spent,
                   template=template, proof=proof, terms=None, certificate=None,
                   residual=None, route="coefficient comparison",
                   free_coefficients=len(remaining))


def express(signature, left_template, bindings, *, degree_x=1, derivatives=0,
            product_degree=2, proof_backend="closure", span_degree=2,
            span_derivatives=0):
    """Write a template over the holes as a program over the declared names.

    Three routes, tried in order, each reporting what it searched. A route that
    declines stops only itself: `NOT_APPLICABLE` from one never settles the
    question, and `NO_SOLUTION_IN_SPACE` is about that span alone.

        projection             the composite already is one of the names
        coefficient comparison a complete solve in a declared span of monomials
        relation search        the existing guesser over the series certifier,
                               which can reach operands the span does not describe
    """
    attempts = []

    projection = _projection(signature, left_template)
    if projection is not None:
        template = slot(projection)
        proof = prove_identity(left_template, _abstract_to_state(signature, template))
        status = PROVED if proof["proved"] else CANDIDATE_REFUTED
        return verdict(status, route="projection", template=template, proof=proof,
                       terms=None, certificate=None, residual=None,
                       grammar={"space": "the declared abstract names themselves"},
                       premises=[proof["law"]],
                       reason=f"the composite is the declared input {projection}",
                       attempts=attempts)

    solved = solve_component(signature, left_template, degree=span_degree,
                             derivatives=span_derivatives)
    attempts.append({k: solved[k] for k in ("route", "status", "reason", "grammar")})
    if solved["status"] == PROVED:
        solved["attempts"] = attempts
        return solved

    left = fill(left_template, bindings)
    inputs = abstract_inputs(signature, bindings)
    labels = ["the left hand side"] + list(signature["names"])
    collisions = _collisions([left] + inputs, labels)
    if collisions:
        attempts.append({"route": "relation search", "status": NOT_APPLICABLE,
                         "reason": "witness collision", "grammar": None})
        return verdict(NOT_APPLICABLE, route="blocked", template=None, proof=None,
                       terms=None, certificate=None, residual=None,
                       grammar={"space": "features over the declared inputs"},
                       reason=("this witness makes " + "; ".join(collisions) +
                               " the same program, so a relation over the declared "
                               "inputs cannot be posed here"),
                       attempts=attempts)

    features = make_features([left] + inputs, degree_x=degree_x,
                             derivatives=derivatives, product_degree=product_degree)
    rejected = []
    for terms in _usable_terms(features):
        try:
            template = induced_template(terms, features, signature["names"])
        except OutsideRingFragment as exc:
            rejected.append(str(exc))
            continue
        # The identity is decided first because it is the cheaper of the two and
        # the one admission rests on: normalising a polynomial costs nothing
        # beside computing a common annihilator. Screening with the certifier
        # instead would pay the expensive check for every numeric fit the guesser
        # offers, almost all of which are not identities.
        proof = prove_identity(left_template, _abstract_to_state(signature, template))
        if not proof["proved"]:
            rejected.append("a fitted relation is not an identity "
                            f"(residual {proof['residual'][:48]})")
            continue
        certificate = certify_relation(features, terms, proof_backend)
        if not isinstance(certificate, dict) or "proof_attempt" in certificate:
            rejected.append("the identity holds but the series certifier did not "
                            "confirm it for these operands")
            continue
        attempts.append({"route": "relation search", "status": PROVED,
                         "reason": "a fitted relation was also an identity",
                         "grammar": {"space": "features over the declared inputs"}})
        return verdict(PROVED, route="relation search", template=template,
                       proof=proof, terms=deepcopy(terms), certificate=certificate,
                       residual=relation_program(features, terms),
                       grammar={"space": "features over the declared inputs",
                                "degree_x": degree_x, "derivatives": derivatives,
                                "product_degree": product_degree},
                       premises=[proof["law"],
                                 "Q[[x]] at zero; analytic germs only"],
                       reason=("proposed by the guesser, proved for independent "
                               "inputs, and confirmed by the certifier for these "
                               "operands"),
                       attempts=attempts)
    status = CANDIDATE_REFUTED if rejected else NOT_APPLICABLE
    attempts.append({"route": "relation search", "status": status,
                     "reason": "; ".join(rejected[:2]) or "nothing certified",
                     "grammar": {"space": "features over the declared inputs"}})
    return verdict(status, route="relation search", template=None, proof=None,
                   terms=None, certificate=None, residual=None,
                   grammar={"space": "features over the declared inputs"},
                   reason="; ".join(rejected[:3]) or
                          "no relation over the declared inputs was certified",
                   attempts=attempts)


def induced_component(signature, morphism, component, bindings, **search):
    """Find and prove one component of f_bar over the declared abstract names."""
    left_template = fill(signature["alpha"][component], morphism)
    found = express(signature, left_template, bindings, **search)
    found["component"] = component
    found["left_template"] = left_template
    found["left"] = fill(left_template, bindings)
    return found


def well_defined(signature, morphism, component, witnesses, *, checks=3, **search):
    """Re-run the same search with the operands replaced.

    Admission does not rest on this -- the identity over independent symbols
    does -- but a component that can only be found for the operands it was found
    with is worth recording as such.
    """
    outcomes = []
    for bindings in witnesses[:checks]:
        found = induced_component(signature, morphism, component, bindings, **search)
        outcomes.append({"bindings": sorted(bindings), "held": found["found"],
                         "route": found["route"],
                         "template_sha256": digest(found["template"])[:16]
                         if found["template"] else None,
                         "reason": None if found["found"] else found["reason"]})
    held = [o for o in outcomes if o["held"]]
    shapes = {o["template_sha256"] for o in held}
    return {"well_defined": len(held) == len(outcomes),
            "same_template_every_time": len(shapes) <= 1,
            "checked": len(outcomes), "outcomes": outcomes}


def query_survives(signature, query, witnesses, *, checks=3, **search):
    """Does a question depend only on alpha(x)?

    A query that fails is not a defect; it is the part of the object the
    abstraction dropped, and the concrete route keeps it.
    """
    outcomes, template = [], None
    for bindings in witnesses[:checks]:
        found = express(signature, query, bindings, **search)
        outcomes.append({"bindings": sorted(bindings), "held": found["found"],
                         "route": found["route"]})
        if not found["found"]:
            return {"survives": False, "checked": len(outcomes), "outcomes": outcomes,
                    "template": None, "reason": found["reason"]}
        template = found["template"]
    return {"survives": True, "checked": len(outcomes), "outcomes": outcomes,
            "template": template,
            "reason": "rewritten over the declared abstract names and proved"}


# ---- the induced operation as something callable --------------------------

def operation_record(signature, *, body, proofs, routes, morphism=None,
                     provenance=None):
    """One callable operation, carrying what later stages need to keep reading.

    Body, the names its arguments have, the domain it runs on, and the proofs it
    was admitted by travel together. A stage that only copies the body leaves the
    operation unable to say why it is allowed.
    """
    record = {"schema": "mortra.induced-operation.v1",
              "body": deepcopy(body),
              "coordinate_names": list(signature["coordinate_names"]),
              "parameter_names": list(signature["parameter_names"]),
              "domain": {"abstraction_map": deepcopy(signature["alpha"]),
                         "coordinate_names": list(signature["coordinate_names"]),
                         "parameter_names": list(signature["parameter_names"]),
                         "image_conditions": [],
                         "law": RING_LAW},
              "proofs": deepcopy(proofs),
              "proved": all(p["proved"] for p in proofs),
              "routes": list(routes),
              "law": RING_LAW,
              "provenance": deepcopy(provenance) if provenance else {}}
    if morphism is not None:
        record["morphism_program"] = deepcopy(morphism)
    record["sha256"] = digest({k: v for k, v in record.items() if k != "sha256"})
    return record


def induced_operation(signature, morphism, bindings, **search):
    """f_bar for one rearrangement, with the proof that makes it well defined."""
    components, proofs, routes, attempts = [], [], [], []
    for component in range(len(signature["alpha"])):
        found = induced_component(signature, morphism, component, bindings, **search)
        attempts.append({"component": component, "status": found["status"],
                         "route": found["route"],
                         "tried": found.get("attempts", [])})
        if not found["found"]:
            return {"proved": False, "body": None, "component": component,
                    "status": found["status"], "route": found["route"],
                    "reason": found["reason"], "attempts": attempts,
                    "coordinate_names": list(signature["coordinate_names"]),
                    "parameter_names": list(signature["parameter_names"])}
        components.append(found["template"])
        proofs.append(found["proof"])
        routes.append(found["route"])
    record = operation_record(signature, body=components, proofs=proofs, routes=routes,
                              morphism=morphism)
    record["status"] = PROVED
    record["attempts"] = attempts
    record["law"] = (DERIVATION_LAW
                     if any(p.get("law") == DERIVATION_LAW for p in proofs)
                     else RING_LAW)
    return record


def apply_operation(operation, arguments):
    """Run an acquired operation on any input, as a program in the coordinates."""
    return [fill(component, arguments) for component in operation["body"]]


def operation_expressions(operation):
    """The body as expressions in the argument symbols."""
    return [ring_expression(component, {}) for component in operation["body"]]


def is_identity_operation(operation):
    """Does the operation move anything at all?

    Worth knowing before asking what it preserves: an operation that moves
    nothing preserves everything, and that is not structure.
    """
    import sympy as sp

    try:
        moved = operation_expressions(operation)
    except OutsideRingFragment:
        return False
    for name, value in zip(operation["coordinate_names"], moved):
        if sp.expand(value - sp.Symbol(f"{SYMBOL_PREFIX}{name}")) != 0:
            return False
    return True


def uses_parameters(operation):
    """The declared parameters the body actually depends on."""
    import sympy as sp

    try:
        moved = operation_expressions(operation)
    except OutsideRingFragment:
        return list(operation["parameter_names"])
    free = set()
    for expression in moved:
        free |= set(expression.free_symbols)
    return [name for name in operation["parameter_names"]
            if sp.Symbol(f"{SYMBOL_PREFIX}{name}") in free]


def same_domain(left, right):
    """Are these two operations defined on the same abstract object?

    Two abstractions can both call their coordinates a0 and a1 and mean entirely
    different things by them. Agreeing on the number and the spelling of the
    arguments is not agreeing on the object, and composing across that gap would
    produce a body whose proofs refer to two different domains.
    """
    return (left.get("coordinate_names") == right.get("coordinate_names")
            and (left.get("domain") or {}).get("abstraction_map")
            == (right.get("domain") or {}).get("abstraction_map"))


def compose_operations(outer, inner, *, coordinate_names=None, rename=None):
    """Run one acquired operation on the output of another.

    Self-composition is allowed and is the usual case: the outer copy's
    parameters are renamed so the two copies take independent arguments rather
    than being forced to share one. Correctness is inherited -- both factors were
    admitted by their own identities, and substituting a proved body into a
    proved body needs no new proof -- and that inheritance is recorded as a
    reference rather than restated as a proof of its own. Whether the composite
    is again the same operation at some combined parameter is a different
    question, and `composition_law` is where it is asked.
    """
    if not same_domain(outer, inner):
        raise ValueError("these operations are defined on different abstract objects; "
                         "composing them would mix two domains")
    coordinate_names = list(coordinate_names or outer["coordinate_names"])
    if rename is None:
        taken = set(inner["parameter_names"]) | set(coordinate_names)
        rename = {}
        for name in outer["parameter_names"]:
            fresh, index = name, 2
            while fresh in taken:
                fresh, index = f"{name}_{index}", index + 1
            taken.add(fresh)
            rename[name] = fresh
    inner_result = apply_operation(inner, dict(
        {name: slot(name) for name in coordinate_names},
        **{name: slot(name) for name in inner["parameter_names"]}))
    arguments = {coordinate_names[i]: inner_result[i]
                 for i in range(len(coordinate_names))}
    arguments.update({name: slot(rename.get(name, name))
                      for name in outer["parameter_names"]})
    parameters = sorted(set(inner["parameter_names"])
                        | {rename.get(n, n) for n in outer["parameter_names"]})
    # The premise of the composite is the stronger of its factors': substituting
    # a body that needed the derivation into one that did not still needs it.
    law = (DERIVATION_LAW
           if DERIVATION_LAW in (outer.get("law"), inner.get("law"))
           else RING_LAW)
    record = {"schema": "mortra.composed-operation.v1",
              "body": apply_operation(outer, arguments),
              "coordinate_names": coordinate_names,
              "parameter_names": parameters,
              "domain": deepcopy(inner.get("domain") or {}),
              "law": law,
              "rename": dict(rename),
              "composed_of": [outer.get("sha256"), inner.get("sha256")],
              "inherited_proofs": {
                  "outer": deepcopy(outer.get("proofs")),
                  "inner": deepcopy(inner.get("proofs")),
                  "rule": ("substituting a body proved for independent inputs into "
                           "another such body needs no further proof; correctness is "
                           "inherited, the composition law is not")},
              "proved": bool(outer.get("proved")) and bool(inner.get("proved")),
              "proofs": []}
    record["sha256"] = digest({k: v for k, v in record.items() if k != "sha256"})
    return record


def composition_law(base, composed, *, depth=1):
    """Is the composite the same operation again at some combined parameter?

    Searched, not supplied: the candidate parameters come from the same grammar
    every other candidate comes from, and each is decided by `prove_identity`.
    This is a claim about the family, quite separate from the composite being
    correct, which it already is by inheritance.
    """
    if len(base["parameter_names"]) != 1:
        return {"proved": False, "searched": 0,
                "reason": "a composition law is only asked of a one-parameter family"}
    parameter = base["parameter_names"][0]
    effective = uses_parameters(base)
    coordinates = {name: slot(name) for name in composed["coordinate_names"]}
    searched = 0
    for candidate in slot_expressions(composed["parameter_names"], depth=depth):
        searched += 1
        bound = dict(coordinates)
        bound[parameter] = candidate
        proofs = [prove_identity(composed["body"][index], fill(part, bound))
                  for index, part in enumerate(base["body"])]
        if all(p["proved"] for p in proofs):
            return {"proved": True, "searched": searched,
                    "parameter": str(ring_expression(candidate, {})),
                    "parameter_program": deepcopy(candidate),
                    "proofs": proofs,
                    "parameter_free_base": not effective,
                    "reason": ("the composite is the same operation at this parameter"
                               if effective else
                               "the base body does not depend on its parameter, so the "
                               "law holds for any candidate and says nothing")}
    return {"proved": False, "searched": searched,
            "parameter_free_base": not effective,
            "reason": "no candidate parameter from the grammar made the two agree"}


# ---- what the acquired operation leaves alone -----------------------------

def _generated_by(quantity, kept, coordinates):
    """Is this quantity a polynomial in the ones already found?

    Anything preserved has its square preserved as well, and its product with
    any other preserved quantity. Raising the degree budget therefore always
    produces more solutions, and counting them would report the same fact as
    many times as the budget allows. Only the ones that are not generated by
    what is already there are new.
    """
    import sympy as sp

    if not kept:
        return None
    target = sp.Poly(quantity, *coordinates).total_degree()
    basis, seen, frontier = [sp.Integer(1)], set(), [sp.Integer(1)]
    for _ in range(max(1, target)):
        grown = []
        for value in frontier:
            for other in kept:
                product = sp.expand(value * other)
                if product == 0:
                    continue
                if sp.Poly(product, *coordinates).total_degree() > target:
                    continue
                text = sp.srepr(product)
                if text in seen:
                    continue
                seen.add(text)
                grown.append(product)
                basis.append(product)
        frontier = grown
        if not grown:
            break
    unknowns = sp.symbols(f"g0:{len(basis)}")
    residual = sp.expand(quantity - sum(u * b for u, b in zip(unknowns, basis)))
    # Each coefficient of the residual in the coordinates has to vanish. They are
    # passed as expressions rather than as equalities: a coefficient that is a
    # bare non-zero number is exactly the inconsistent case, and wrapping it in
    # `Eq` turns it into a boolean the solver cannot read.
    try:
        equations = list(sp.Poly(residual, *coordinates).coeffs())
    except sp.PolynomialError:
        return None
    solution = sp.linsolve(equations, unknowns)
    if solution is sp.EmptySet or len(solution) == 0:
        return None
    return ("a polynomial in the quantities already found at this degree, so it "
            "repeats them rather than adding structure")


def conserved_quantities(operation, *, degree=2, signature=None):
    """Solve for the quantities the acquired operation does not move.

    A generic polynomial of the given degree is written with unknown
    coefficients, pushed through the operation, and the difference is required
    to vanish identically in the coordinates and the parameters at once. What
    comes back is whatever the linear system allows; the degree is the search
    budget and no target expression is supplied.

    Each survivor is then put back through alpha. A quantity that vanishes there
    is a relation the abstract domain satisfies, and one that is constant there
    is a constant observation; neither is something the operation preserves in
    any informative sense. Saying so is not the same as forbidding a redundant
    coordinate: the coordinate stays, and the relation is kept with it.
    """
    import sympy as sp
    from itertools import combinations_with_replacement

    if is_identity_operation(operation):
        return {"found": [], "quantities": [], "degree": degree, "monomials": [],
                "reason": "the operation moves nothing, so every quantity is preserved "
                          "and none of them is structure"}

    coordinates = [sp.Symbol(f"{SYMBOL_PREFIX}{name}")
                   for name in operation["coordinate_names"]]
    monomials = [sp.Integer(1)]
    for size in range(1, degree + 1):
        for pick in combinations_with_replacement(coordinates, size):
            monomials.append(sp.prod(pick))
    unknowns = sp.symbols(f"k0:{len(monomials)}")
    generic = sum(k * m for k, m in zip(unknowns, monomials))

    moved = {}
    for name, component in zip(operation["coordinate_names"], operation["body"]):
        moved[sp.Symbol(f"{SYMBOL_PREFIX}{name}")] = ring_expression(component, {})
    difference = sp.expand(generic.subs(moved, simultaneous=True) - generic)

    free = sorted(difference.free_symbols - set(unknowns), key=str)
    equations = [sp.Eq(c, 0) for c in
                 sp.Poly(difference, *free).coeffs()] if free else [sp.Eq(difference, 0)]
    solution = sp.solve(equations, unknowns, dict=True)
    if not solution:
        return {"found": [], "quantities": [], "degree": degree,
                "monomials": [str(m) for m in monomials],
                "reason": "the linear system has only the trivial solution"}
    resolved = generic.subs(solution[0])
    remaining = sorted(resolved.free_symbols & set(unknowns), key=str)
    solved = []
    for parameter in remaining:
        quantity = sp.expand(sp.diff(resolved, parameter))
        if quantity == 0 or not (quantity.free_symbols & set(coordinates)):
            continue
        solved.append(quantity)
    # Lowest degree first, so a generator is kept before whatever it generates.
    solved.sort(key=lambda q: (sp.Poly(q, *coordinates).total_degree(), str(q)))
    quantities, kept, repeated = [], [], []
    for quantity in solved:
        generated = _generated_by(quantity, kept, coordinates)
        if generated is not None:
            repeated.append({"expression": str(sp.factor(quantity)),
                             "reason": generated})
            continue
        kept.append(quantity)
        quantity = sp.factor(quantity)
        program = ring_program(quantity)
        entry = {"expression": str(quantity), "program": program,
                 "class": "observable", "on_image": None,
                 "reason": "no abstraction was supplied to substitute back"}
        if signature is not None:
            entry.update(classify_on_image(quantity, signature))
        entry["invariance"] = prove_identity(
            fill(program, dict(
                {name: operation["body"][index] for index, name
                 in enumerate(operation["coordinate_names"])},
                **{name: slot(name) for name in operation["parameter_names"]})),
            program)
        quantities.append(entry)
    varying = [q for q in quantities if q["class"] == "observable"]
    return {"found": [q["expression"] for q in varying],
            "quantities": quantities, "generated": repeated, "degree": degree,
            "monomials": [str(m) for m in monomials],
            "reason": ("quantities the operation leaves alone that also vary on the "
                       "image of alpha" if varying else
                       "every preserved quantity at this degree is generated by "
                       "another, or is a relation of the image, or is constant on it")}


# ---- the acquired unit ----------------------------------------------------

def correspondence(signature, morphisms, witnesses, *, queries=(), abstract_domain,
                   source_type, checks=3, **search):
    """Acquire the abstraction, the operations that descend, and the proofs.

    Operations that do not descend are recorded as unsupported rather than
    dropped, because the point of the record is to say what may be computed on
    the abstract object and what may not.
    """
    if not witnesses:
        raise ValueError("a correspondence needs at least one binding to prove against")
    rearrangements = {name: morphism for name, morphism in morphisms.items()
                      if preserves_abstraction(signature, morphism, witnesses[0])}

    supported, unsupported = [], []
    for name, morphism in morphisms.items():
        verdict_two = descends(signature, morphism, rearrangements, witnesses[0])
        if not verdict_two["descends"]:
            # A counterexample to this operation on this abstraction, and to
            # nothing else: another operation, or the same operation on a finer
            # abstraction, is untouched by it.
            unsupported.append({"morphism": name, "status": CANDIDATE_REFUTED,
                                "route": "condition (2)",
                                "reason": "condition (2) fails: two objects with one "
                                          "image are sent to different images",
                                "counterexample": verdict_two["failures"],
                                "condition_two": verdict_two})
            continue
        operation = induced_operation(signature, morphism, witnesses[0], **search)
        if not operation.get("proved"):
            unsupported.append({"morphism": name, "condition_two": verdict_two,
                                "status": operation.get("status", NOT_APPLICABLE),
                                "reason": operation.get(
                                    "reason", "no induced operation was proved"),
                                "route": operation.get("route"),
                                "attempts": operation.get("attempts"),
                                "component": operation.get("component")})
            continue
        regression = [well_defined(signature, morphism, component, witnesses,
                                   checks=checks, **search)
                      for component in range(len(signature["alpha"]))]
        entry = dict(operation)
        entry.update({"morphism": name,
                      "argument_correspondence": {
                          "coordinates": {signature["coordinate_names"][i]:
                                          deepcopy(signature["alpha"][i])
                                          for i in range(len(signature["alpha"]))},
                          "parameters": {p: p for p in signature["parameter_names"]}},
                      "identity_proofs": operation["proofs"],
                      "substitution_regression": regression,
                      "admitted_by": "identity proved for independent inputs"})
        supported.append(entry)

    surviving, dropped = [], []
    for name, query in queries:
        verdict = query_survives(signature, query, witnesses, checks=checks, **search)
        if verdict["survives"]:
            surviving.append({"query": name, "template": verdict["template"],
                              "checked": verdict["checked"]})
        else:
            dropped.append({"query": name, "reason": verdict["reason"],
                            "checked": verdict["checked"]})

    record = {"schema": SCHEMA, "source_type": source_type,
              "abstract_type": abstract_domain,
              "signature": deepcopy(signature),
              "abstraction_map": deepcopy(signature["alpha"]),
              "abstraction_arity": len(signature["alpha"]),
              "coordinate_names": list(signature["coordinate_names"]),
              "parameter_names": list(signature["parameter_names"]),
              "image_conditions": [],
              "supported_morphisms": supported,
              "unsupported_morphisms": unsupported,
              "supported_queries": surviving,
              "dropped_queries": dropped,
              "alpha_preserving_rearrangements": sorted(rearrangements),
              "admission_rule": ("an operation is admitted only when the square is "
                                 "proved for independent inputs; a rearrangement that "
                                 "finds no counterexample never admits anything"),
              "domain_conditions": {
                  "proved_for_bindings": [sorted(b) for b in witnesses[:checks]],
                  "universality": ("each admitted square was proved over independent "
                                   "symbols in a commutative ring, so it holds for "
                                   "every input those axioms cover"),
                  "available_names": list(signature["names"]),
                  "law": RING_LAW},
              "scope": SCOPE}
    record["sha256"] = digest(record)
    return record


def record_image_condition(record, entry):
    """Keep a relation that holds on the image with the abstract object.

    A quantity that vanishes once alpha is substituted says what the abstract
    domain is. Storing it there is what lets a later stage tell a preserved
    quantity from one that was never free to vary.
    """
    known = {condition["expression"] for condition in record["image_conditions"]}
    if entry["expression"] in known:
        return False
    record["image_conditions"].append(
        {"expression": entry["expression"], "program": deepcopy(entry["program"]),
         "on_image": entry["on_image"], "reason": entry["reason"]})
    for operation in record["supported_morphisms"]:
        operation["domain"]["image_conditions"] = deepcopy(record["image_conditions"])
    return True


def abstract_seeds(record, bindings):
    """The abstract coordinates as programs, for the next round of generation."""
    return [fill(part, bindings) for part in record["abstraction_map"]]


def induced_operations(record):
    """The names of the operations that may be run on the abstract object."""
    return [entry["morphism"] for entry in record["supported_morphisms"]]


def induced_images(record, bindings):
    """The abstract coordinates after each supported operation has been applied.

    The existing generator takes programs, so the way to make an induced
    operation available to it is to hand over what that operation produces. Only
    operations that were admitted appear here; the rest never reach a later round.
    """
    coordinates = dict(zip(record["coordinate_names"],
                           abstract_seeds(record, bindings)))
    coordinates.update({name: deepcopy(bindings[name])
                        for name in record["parameter_names"] if name in bindings})
    images = []
    for entry in record["supported_morphisms"]:
        for index, program in enumerate(apply_operation(entry, coordinates)):
            images.append({"morphism": entry["morphism"], "component": index,
                           "program": program})
    return images


def next_round_seeds(record, bindings):
    """Abstract objects and what the supported operations make of them."""
    seeds = [{"origin": "abstract_coordinate", "component": index, "program": program}
             for index, program in enumerate(abstract_seeds(record, bindings))]
    return seeds + [{"origin": "induced_operation", **image}
                    for image in induced_images(record, bindings)]
