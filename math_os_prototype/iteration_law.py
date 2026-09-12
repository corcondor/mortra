"""Hand a proved composition law to the proved induction, and get every n at once.

Nothing here proves anything on its own. Two proofs already exist and had no way
to reach each other:

    `abstraction_correspondence.composition_law` proves, for one fixed pair of
    copies, that `T_{c2} . T_{c} = T_{P(c, c2)}` -- and it proves it by
    normalising a difference to zero in *free independent symbols*, so it is a
    quantified identity and may be instantiated at any ring element.

    `finite_affine_word_law.discover_affine_feature_law` proves, for every finite
    word at once, that a state which each generator moves affinely has a closed
    form affine in the word length -- base case plus every generator step,
    checked symbolically.

The gap between them is that the first speaks about operation bodies and the
second about matrices over a feature machine. This module is that gap and
nothing else: it reads the parameter the composition law found, turns the
accumulation it induces into the matrix the word law wants, and reassembles the
answer into a statement about the operation. It adds no prover, enumerates no
candidate for a fixed n, and never supplies a target coefficient.

The route is:

    s_0 = 0                       forced, and discharged by proving T_0 = id
    s_{k+1} = P(s_k, c)           read off the composition law, not chosen
    s_n = sigma * n + iota        proved for every n by the word law
    T^n = T_{s_n}                 base case + induction step, each step a
                                  rewriting by an equation already proved

The closed form of `T^n` is then obtained by *substituting* `s_n` into the body
that was already proved. Whatever degree in `n` that substitution produces is a
consequence of it; no degree in `n` is fitted, requested or assumed.
"""
from __future__ import annotations

from copy import deepcopy

from math_os_prototype.abstraction_correspondence import (
    CANDIDATE_REFUTED, DERIVATION_LAW, NO_SOLUTION_IN_SPACE, NOT_APPLICABLE,
    OPEN_OBLIGATIONS,
    PROVED, RING_LAW, SYMBOL_PREFIX, apply_operation, compose_operations,
    composition_law, fill, is_identity_operation, prove_identity,
    ring_expression, ring_program, slot, slot_expressions, uses_parameters,
    verdict)
from math_os_prototype.finite_affine_word_law import (
    FiniteFeatureMachine, discover_affine_feature_law)

ACCUMULATOR = "s"
INDEX = "n"

ITERATION_SCOPE = (
    "n ranges over the non-negative integers; T^n is n-fold self-composition and "
    "n * c is the n-fold sum of c. n is an index, not a ring element, and no "
    "claim is made for a symbolic or non-integer n."
)


def _constant(value):
    return {"op": "poly", "coefficients": [str(value)]}


def _symbol(name):
    import sympy as sp

    return sp.Symbol(f"{SYMBOL_PREFIX}{name}")


# ---- 1. is the stored composition-law proof quantified? -------------------

def quantification(base, law):
    """What the composition-law proof is actually quantified over.

    An identity may only be instantiated at an accumulator if it was proved for
    free independent symbols rather than for the operands that were tried. That
    is what `prove_identity` reports, so this reads its report rather than
    restating it: every residual identically zero, one distinct symbol per
    declared name, and the two copies' parameters not aliased to each other.
    """
    if not law.get("proved"):
        return {"quantified": False, "reason": "the composition law was not proved",
                "symbols": [], "expected": []}
    if law.get("parameter_free_base"):
        return {"quantified": False,
                "reason": ("the base body does not depend on its parameter, so the "
                           "law holds vacuously and instantiating it says nothing"),
                "symbols": [], "expected": []}
    seen = sorted({s for proof in law["proofs"] for s in proof.get("symbols", [])})
    residuals = [proof.get("residual") for proof in law["proofs"]]
    laws = sorted({proof.get("law") for proof in law["proofs"]})
    return {"quantified": all(r == "0" for r in residuals) and bool(seen),
            "symbols": seen,
            "residuals": residuals,
            "laws": laws,
            "components_proved": [bool(p.get("proved")) for p in law["proofs"]],
            "reason": ("every component's difference normalises to zero in free "
                       "independent symbols, so the identity may be instantiated "
                       "at any element of the ring")
            if all(r == "0" for r in residuals) else
            "at least one component was not an identity in independent symbols"}


# ---- 2. the base case: is T at the initial parameter the identity? --------

def identity_at(base, value):
    """Prove -- not assume -- that the family at this parameter moves nothing.

    `s_0 = 0` is not a free choice. The base case of the induction is
    `T^0 = T_{s_0}`, and `T^0` is the identity by definition of iteration, so
    `s_0` has to be a parameter at which the family *is* the identity. That is a
    proof obligation, discharged here by the existing identity prover.
    """
    parameters = base["parameter_names"]
    if len(parameters) != 1:
        return verdict(NOT_APPLICABLE,
                       reason="an iteration law is only asked of a one-parameter family",
                       grammar=None, proofs=[], body=None)
    bound = {name: slot(name) for name in base["coordinate_names"]}
    bound[parameters[0]] = _constant(value)
    body = [fill(part, bound) for part in base["body"]]
    proofs = [prove_identity(part, slot(name))
              for name, part in zip(base["coordinate_names"], body)]
    proved = all(p["proved"] for p in proofs)
    return verdict(PROVED if proved else OPEN_OBLIGATIONS,
                   reason=(f"the family at parameter {value} is the identity"
                           if proved else
                           f"the family at parameter {value} moves at least one "
                           "coordinate, so it cannot be the zeroth iterate"),
                   grammar={"space": "the declared coordinates themselves"},
                   premises=sorted({p["law"] for p in proofs}),
                   proofs=proofs, body=body, value=str(value),
                   is_identity=is_identity_operation(
                       dict(base, body=body, parameter_names=[])))


# ---- 3. the bridge: the law's parameter as an accumulation ----------------

def accumulator_recurrence(base, composed, law, *, accumulator=ACCUMULATOR):
    """Turn the parameter the law found into the recurrence the word law wants.

    This is the whole of the connection. `composition_law` hands back a *program*
    `P` over the two copies' parameter slots; `discover_affine_feature_law` wants
    a *matrix* acting on a state. The two meet exactly when `P` is affine in the
    copy that carries the accumulated parameter, because that is the hypothesis
    class the word law can certify for every length.

    Which slot is the accumulator is not a choice either. `compose_operations`
    renames the *outer* copy and leaves the *inner* one alone, and in
    `T^(k+1) = T . T^k` the inner factor is `T^k`. So the accumulator is the
    base's own parameter name and the fresh step's is its rename.

    A law that is not affine in the accumulator is reported as the mismatch it
    is rather than worked around: raising the degree in the accumulator is a
    different theorem and would need a different induction.
    """
    import sympy as sp

    parameter = base["parameter_names"][0]
    fresh = composed.get("rename", {}).get(parameter, parameter)
    if fresh == parameter or fresh not in composed["parameter_names"]:
        return verdict(NOT_APPLICABLE,
                       reason=("the composite did not give the two copies "
                               "independent parameter names, so there is no "
                               "accumulator to separate"),
                       grammar=None, affine=False, accumulator=None, fresh=None)
    if accumulator in composed["parameter_names"] + composed["coordinate_names"]:
        return verdict(NOT_APPLICABLE,
                       reason=f"the accumulator name {accumulator!r} is already taken",
                       grammar=None, affine=False, accumulator=None, fresh=None)

    # inner copy -> the accumulated parameter; outer copy -> this step's parameter
    renaming = {parameter: slot(accumulator), fresh: slot(parameter)}
    recurrence_program = fill(law["parameter_program"], renaming)
    expression = sp.expand(ring_expression(recurrence_program, {}))
    carrier = _symbol(accumulator)

    polynomial = sp.Poly(expression, carrier)
    degree = polynomial.degree()
    if degree > 1:
        return verdict(NOT_APPLICABLE,
                       reason=("the composition law's parameter is of degree "
                               f"{degree} in the accumulated parameter; the "
                               "induction that is available certifies a state each "
                               "generator moves affinely, so this law cannot be "
                               "handed to it without a different induction"),
                       grammar={"space": "affine in the accumulated parameter"},
                       affine=False, degree=degree,
                       accumulator=accumulator, fresh=fresh,
                       recurrence=str(expression))
    slope = sp.expand(polynomial.coeff_monomial(carrier))
    offset = sp.expand(expression - slope * carrier)
    if carrier in slope.free_symbols or carrier in offset.free_symbols:
        return verdict(NOT_APPLICABLE,
                       reason="the affine split still mentions the accumulator",
                       grammar=None, affine=False,
                       accumulator=accumulator, fresh=fresh)
    return verdict(PROVED,
                   reason=("the law's parameter is affine in the accumulated "
                           "parameter, which is the shape the existing induction "
                           "certifies for every length"),
                   grammar={"space": "affine in the accumulated parameter"},
                   premises=[RING_LAW],
                   affine=True, degree=degree,
                   accumulator=accumulator, fresh=fresh,
                   recurrence=str(expression),
                   recurrence_program=recurrence_program,
                   multiplier=str(slope), increment=str(offset),
                   multiplier_program=ring_program(slope),
                   increment_program=ring_program(offset))


def _one_step_machine(symbol="t", state="q"):
    """One generator, one feature state: applying the operation once.

    The word law is stated over an alphabet because it was built for words. An
    iteration is a word over a one-letter alphabet, and its length is n.
    """
    return FiniteFeatureMachine(name="iterate", symbols=(symbol,),
                                initial_state=state,
                                transitions=((state, symbol, state),),
                                public_complexity=1)


def parameter_closed_form(bridge, *, initial=0):
    """Hand the accumulation to the existing induction and read back s_n.

    The state is `(s, 1)` and the generator is the accumulation itself, so the
    matrix is built from the multiplier and increment the bridge separated -- not
    from any guess about what `s_n` should be. What comes back is the word law's
    own verdict, with its own base case and its own generator check.
    """
    import sympy as sp

    if not bridge.get("affine"):
        return verdict(NOT_APPLICABLE, reason=bridge["reason"], grammar=None,
                       closed_form=None, word_law=None)
    multiplier = sp.sympify(bridge["multiplier"])
    increment = sp.sympify(bridge["increment"])
    machine = _one_step_machine()
    generator = sp.ImmutableMatrix(((multiplier, increment), (0, 1)))
    start = sp.ImmutableMatrix((sp.sympify(initial), 1))
    result = discover_affine_feature_law(
        {machine.symbols[0]: generator}, start, machine,
        component_names=(bridge["accumulator"], "one"))
    if not result.get("passed"):
        return verdict(NO_SOLUTION_IN_SPACE,
                       reason=("the accumulation is not affine in the number of "
                               "steps, so the induction that is available does not "
                               "certify it"),
                       grammar={"space": "affine in the word length"},
                       closed_form=None, word_law=result,
                       counterexample=result.get("counterexample"))
    formula = result["feature_state_formulas"][machine.initial_state]
    carried = formula["slope"]["one"], formula["intercept"]["one"]
    if (sp.sympify(carried[0]) != 0) or (sp.sympify(carried[1]) != 1):
        return verdict(OPEN_OBLIGATIONS,
                       reason="the homogeneous coordinate did not stay constant",
                       grammar=None, closed_form=None, word_law=result)
    slope = sp.sympify(formula["slope"][bridge["accumulator"]])
    offset = sp.sympify(formula["intercept"][bridge["accumulator"]])
    closed = sp.expand(slope * _symbol(INDEX) + offset)
    return verdict(PROVED,
                   reason=("base case and every generator step were checked "
                           "symbolically, so the closed form holds for every "
                           "number of steps"),
                   grammar={"space": "affine in the word length",
                            "proposal_depth": result["proposal_depth"]},
                   premises=[result["proof"]],
                   closed_form=str(closed),
                   closed_form_program=ring_program(closed),
                   slope=str(slope), offset=str(offset),
                   scope=result["scope"],
                   base_case_exact=result["initial_identity_exact"],
                   generator_steps=result["generator_transition_identity_count"],
                   all_steps_exact=result["all_generator_transition_identities_exact"],
                   fit_used_as_proof=result["finite_sample_fit_used_as_proof"],
                   word_law=result)


# ---- 4. the assembly: base case and induction step, both checked ---------

def iteration_law(base, *, depth=1, accumulator=ACCUMULATOR, initial=0):
    """`T^n = T_{s_n}` for every n, from the two proofs and nothing else.

    Each obligation below is discharged by `prove_identity`, which is a check,
    not a search: the composite is formed once, the law's parameter is
    instantiated at the accumulator once, and the recurrence joint is normalised
    once. No candidate is enumerated for any particular n.
    """
    parameters = base["parameter_names"]
    if len(parameters) != 1:
        return verdict(NOT_APPLICABLE,
                       reason="an iteration law is only asked of a one-parameter family",
                       grammar=None, stages={})
    if not uses_parameters(base):
        return verdict(NOT_APPLICABLE,
                       reason=("the body does not depend on its parameter, so an "
                               "iteration law about that parameter says nothing"),
                       grammar=None, stages={})

    stages = {}
    composed = compose_operations(base, base)
    law = composition_law(base, composed, depth=depth)
    stages["composition_law"] = {
        "proved": bool(law.get("proved")), "searched": law.get("searched"),
        "parameter": law.get("parameter"), "reason": law.get("reason")}
    if not law.get("proved"):
        return verdict(NO_SOLUTION_IN_SPACE,
                       reason=("no composition law was proved, so there is nothing "
                               "to hand to the induction"),
                       grammar={"space": "the existing candidate grammar",
                                "depth": depth},
                       stages=stages)

    stages["quantification"] = quantification(base, law)
    if not stages["quantification"]["quantified"]:
        return verdict(OPEN_OBLIGATIONS,
                       reason=("the composition law is not a quantified identity, "
                               "so it may not be instantiated at an accumulator: "
                               + stages["quantification"]["reason"]),
                       grammar=None, stages=stages)

    base_case = identity_at(base, initial)
    stages["base_case"] = {"status": base_case["status"],
                           "proved": base_case["found"],
                           "reason": base_case["reason"],
                           "residuals": [p["residual"] for p in base_case["proofs"]]}
    if not base_case["found"]:
        return verdict(OPEN_OBLIGATIONS,
                       reason=("the zeroth iterate is the identity, but the family "
                               "at the initial parameter is not: " + base_case["reason"]),
                       grammar=None, stages=stages)

    bridge = accumulator_recurrence(base, composed, law, accumulator=accumulator)
    stages["bridge"] = {"status": bridge["status"], "affine": bridge.get("affine"),
                        "recurrence": bridge.get("recurrence"),
                        "multiplier": bridge.get("multiplier"),
                        "increment": bridge.get("increment"),
                        "degree_in_accumulator": bridge.get("degree"),
                        "reason": bridge["reason"]}
    if not bridge.get("affine"):
        return verdict(bridge["status"],
                       reason=("the composition law cannot be handed to the "
                               "available induction: " + bridge["reason"]),
                       grammar=bridge.get("grammar"), stages=stages)

    # The induction step, as a checked instance rather than an assertion. The
    # law is instantiated at the accumulator on both sides and the difference is
    # normalised; this is the point at which quantification is actually used.
    fresh = bridge["fresh"]
    instantiate = {parameters[0]: slot(accumulator), fresh: slot(parameters[0])}
    coordinates = {name: slot(name) for name in base["coordinate_names"]}
    left = [fill(part, dict(coordinates, **instantiate)) for part in composed["body"]]
    right = [fill(part, dict(coordinates,
                             **{parameters[0]: deepcopy(bridge["recurrence_program"])}))
             for part in base["body"]]
    step_proofs = [prove_identity(l, r) for l, r in zip(left, right)]
    stages["induction_step"] = {
        "proved": all(p["proved"] for p in step_proofs),
        "residuals": [p["residual"] for p in step_proofs],
        "symbols": sorted({s for p in step_proofs for s in p["symbols"]}),
        "checks": len(step_proofs),
        "rule": ("the law was instantiated at the accumulator, which is allowed "
                 "because it was proved for free independent symbols")}
    if not stages["induction_step"]["proved"]:
        return verdict(OPEN_OBLIGATIONS,
                       reason="the composition law did not survive instantiation "
                              "at the accumulator",
                       grammar=None, stages=stages)

    closed = parameter_closed_form(bridge, initial=initial)
    stages["parameter_induction"] = {
        "status": closed["status"], "closed_form": closed.get("closed_form"),
        "scope": closed.get("scope"), "base_case_exact": closed.get("base_case_exact"),
        "generator_steps": closed.get("generator_steps"),
        "all_steps_exact": closed.get("all_steps_exact"),
        "fit_used_as_proof": closed.get("fit_used_as_proof"),
        "reason": closed["reason"]}
    if not closed["found"]:
        return verdict(closed["status"],
                       reason=("the accumulation was handed to the induction but "
                               "was not certified for every n: " + closed["reason"]),
                       grammar=closed.get("grammar"), stages=stages)

    # The closed-form body is a SUBSTITUTION into a body already proved. Whatever
    # degree in n it has is a consequence of that substitution; none was asked for.
    iterate_body = [fill(part, dict(coordinates,
                                    **{parameters[0]:
                                       deepcopy(closed["closed_form_program"])}))
                    for part in base["body"]]
    iterate = {"schema": "mortra.iterated-operation.v1",
               "body": iterate_body,
               "coordinate_names": list(base["coordinate_names"]),
               "parameter_names": [INDEX],
               "domain": deepcopy(base.get("domain") or {}),
               "law": base.get("law", RING_LAW),
               "proved": True,
               "proofs": [],
               "derived_from": {"base": base.get("sha256"),
                                "composition_law": law.get("parameter"),
                                "rule": "substitution of a proved parameter into a "
                                        "proved body"}}
    return verdict(PROVED,
                   reason=("the composition law was instantiated at the "
                           "accumulated parameter, the accumulation was certified "
                           "for every number of steps by the existing induction, "
                           "and the two were joined by base case and step"),
                   grammar={"space": "the existing candidate grammar", "depth": depth},
                   premises=sorted({law["proofs"][0]["law"],
                                    closed["premises"][0] if closed["premises"] else ""}
                                   - {""}),
                   scope=ITERATION_SCOPE,
                   parameter=closed["closed_form"],
                   parameter_program=closed["closed_form_program"],
                   recurrence=bridge["recurrence"],
                   iterate=iterate,
                   iterate_expressions=[str(ring_expression(part, {}))
                                        for part in iterate_body],
                   stages=stages,
                   searched_for_fixed_n=law.get("searched"),
                   searched_per_n_after_connection=0)


# ---- 5. the general lemma about a correspondence -------------------------

INTERTWINING_RULE = (
    "alpha . S = T . alpha implies alpha . S^n = T^n . alpha for every n, by "
    "induction on n: at n = 0 both sides are alpha, and the step rewrites "
    "alpha . S . S^n by the premise into T . alpha . S^n and then by the "
    "hypothesis into T . T^n . alpha. Every step is a rewriting by an equation "
    "already proved, so the conclusion needs no search."
)


def intertwined_power(signature, morphism, operation, *, checked_to=3):
    """`alpha . S = T . alpha` carried to every power, once and for all.

    The premise is what `induced_component` already proves: it normalises
    `alpha_i(S(u))` against `T_i(alpha(u))` in independent symbols. This re-checks
    that premise from the two objects rather than trusting a stored flag, then
    states the conclusion for every n with the rule that produced it, and
    verifies a few small powers as a regression on the rule -- not as its
    justification.
    """
    coordinates = list(signature["coordinate_names"])
    if len(coordinates) != len(signature["alpha"]):
        return verdict(NOT_APPLICABLE,
                       reason="the signature and the abstraction map disagree in size",
                       grammar=None, premise=None)
    if operation["parameter_names"]:
        binding = {name: slot(name) for name in operation["parameter_names"]}
    else:
        binding = {}

    def abstract_of(state_programs):
        """T applied to alpha(x), as a program in the state holes."""
        bound = dict(binding)
        bound.update({name: state_programs[index]
                      for index, name in enumerate(coordinates)})
        return [fill(part, bound) for part in operation["body"]]

    alpha = [deepcopy(part) for part in signature["alpha"]]
    left = [fill(part, morphism) for part in alpha]          # alpha . S
    right = abstract_of(alpha)                                # T . alpha
    premise = [prove_identity(l, r) for l, r in zip(left, right)]
    if not all(p["proved"] for p in premise):
        return verdict(CANDIDATE_REFUTED,
                       reason=("alpha does not intertwine this rearrangement with "
                               "this operation, so no power of it does either"),
                       grammar=None, premise=premise, powers=[])

    # regression only: the rule is what carries the claim, these confirm the rule
    powers, state = [], alpha
    concrete = morphism
    for power in range(1, max(0, checked_to) + 1):
        state = abstract_of(state)                            # T^power . alpha
        concrete = {name: fill(program, morphism)
                    for name, program in concrete.items()} if power > 1 else morphism
        iterated_left = [fill(part, concrete) for part in alpha]   # alpha . S^power
        proofs = [prove_identity(l, r) for l, r in zip(iterated_left, state)]
        powers.append({"power": power,
                       "proved": all(p["proved"] for p in proofs),
                       "residuals": [p["residual"] for p in proofs]})
    return verdict(PROVED,
                   reason=("the premise holds for independent inputs, so the "
                           "conclusion holds for every power by the stated rule"),
                   grammar={"space": "no search; a rule applied to a proved premise"},
                   premises=sorted({p["law"] for p in premise}),
                   rule=INTERTWINING_RULE,
                   premise=[{"proved": p["proved"], "residual": p["residual"],
                             "symbols": p["symbols"]} for p in premise],
                   powers=powers,
                   regression_only=("the listed powers are a regression on the rule, "
                                    "not the reason the conclusion holds"))


# ---- 6. can the original state be recovered? -----------------------------

def recovery_map(signature, *, depth=1):
    """Is there a proved `r` with `r . alpha = id`?

    Asked in the grammar every other candidate comes from, at the depth the
    caller allows, and decided by the same identity prover. A theorem about the
    abstract coordinates transfers to the original state exactly when this
    succeeds; when it fails the theorem is still a theorem, about less.
    """
    coordinates = list(signature["coordinate_names"])
    state_names = sorted({name for part in signature["alpha"]
                          for name in _slots_of(part)})
    if len(state_names) != 1:
        return verdict(NOT_APPLICABLE,
                       reason=("recovery is asked of an abstraction of a single "
                               f"state hole; this one has {len(state_names)}"),
                       grammar=None, map=None, searched=0)
    state = state_names[0]
    bindings = {name: deepcopy(signature["alpha"][index])
                for index, name in enumerate(coordinates)}
    searched = 0
    for candidate in slot_expressions(coordinates, depth=depth):
        searched += 1
        proof = prove_identity(fill(candidate, bindings), slot(state))
        if proof["proved"]:
            return verdict(PROVED,
                           reason=("this map composed with alpha is the identity on "
                                   "the original state, so anything proved about "
                                   "the abstract coordinates transfers back"),
                           grammar={"space": "the existing candidate grammar",
                                    "depth": depth},
                           premises=[proof["law"]],
                           map=candidate,
                           expression=str(ring_expression(candidate, {})),
                           state=state, proof=proof, searched=searched)
    return verdict(NO_SOLUTION_IN_SPACE,
                   reason=("no map in this grammar recovers the original state from "
                           "the abstract coordinates; the theorem is kept as a "
                           "statement about the abstract coordinates alone"),
                   grammar={"space": "the existing candidate grammar", "depth": depth},
                   map=None, state=state, searched=searched)


def _slots_of(program):
    from math_os_prototype.abstraction_correspondence import _slot_name

    name = _slot_name(program)
    if name is not None:
        return {name}
    found = set()
    for key in ("left", "right", "child"):
        if key in program:
            found |= _slots_of(program[key])
    return found


def transfer(iteration, recovery):
    """What the iteration theorem says once recovery is known, or not known."""
    if not iteration.get("found"):
        return {"transfers": False,
                "statement": None,
                "reason": "there is no iteration theorem to transfer"}
    if recovery.get("found"):
        return {"transfers": True,
                "scope": "the original state",
                "statement": ("S^n = r . T^n . alpha, with r . alpha = id proved, "
                              "so the n-th iterate of the concrete rearrangement is "
                              "recovered in full from the abstract iterate"),
                "recovery": recovery["expression"],
                "premises": ["alpha . S = T . alpha", "r . alpha = id",
                             iteration["parameter"]]}
    return {"transfers": False,
            "scope": "the abstract coordinates only",
            "statement": ("alpha . S^n = T^n . alpha with T^n known in closed form; "
                          "no map recovering the original state was proved, so the "
                          "theorem is kept about the abstract coordinates alone"),
            "reason": recovery.get("reason"),
            "premises": ["alpha . S = T . alpha", iteration["parameter"]]}
