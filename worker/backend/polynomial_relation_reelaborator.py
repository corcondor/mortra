"""Recover typed geometry atoms from certified polynomial lemmas.

The bridge is intentionally bidirectional.  It does not classify a polynomial
from its printed shape.  Instead it enumerates a finite, typed relation
language over the points in the polynomial's construction boundary, lowers
every candidate through the existing JGEX coordinate semantics, and accepts
only exact polynomial associates (or powers of one irreducible associate).

This makes every recovered atom replayable and prevents products containing
unrelated or degenerate branches from being mistaken for a geometric fact.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
import hashlib
from itertools import combinations
import json
from typing import Any, Iterable, Mapping

import sympy as sp

from worker.backend.geometry_proof_hypergraph import Atom
from worker.backend.bounded_macaulay_membership import (
    BoundedMacaulayCertificate,
    certify_bounded_macaulay_membership,
    verify_bounded_macaulay_certificate,
)
from worker.backend.jgex_exact_constraint_bridge import (
    JGEXExactSystemAnalysis,
    inspect_jgex_exact_system,
    inspect_jgex_relation_polynomials,
)


@dataclass(frozen=True)
class TypedRelationReelaborationCertificate:
    """Exact witness that one polynomial denotes one typed relation."""

    predicate: str
    arguments: tuple[str, ...]
    atom: str
    lemma_polynomial: str
    forward_polynomial: str
    equivalence_mode: str
    lemma_normal_form: str
    forward_normal_form: str
    candidate_points: tuple[str, ...]
    nonzero_conditions: tuple[str, ...]
    exact_replay: bool
    certificate_sha256: str


@dataclass(frozen=True)
class PolynomialLemmaReelaboration:
    lemma_polynomial: str
    support_variables: tuple[str, ...]
    candidate_points: tuple[str, ...]
    candidates_considered: int
    certificates: tuple[TypedRelationReelaborationCertificate, ...]
    status: str


@dataclass(frozen=True)
class TypedRelationIdealCertificate:
    """A typed relation proved by an exact combination of polynomial lemmas."""

    predicate: str
    arguments: tuple[str, ...]
    atom: str
    forward_polynomial: str
    source_polynomials: tuple[str, ...]
    macaulay_certificate: BoundedMacaulayCertificate
    exact_replay: bool
    certificate_sha256: str


def _hash(payload: dict[str, object]) -> str:
    material = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _ideal_certificate_hash(
    predicate: str,
    arguments: tuple[str, ...],
    forward_polynomial: str,
    source_polynomials: tuple[str, ...],
    macaulay_sha256: str,
) -> str:
    return _hash(
        {
            "predicate": predicate,
            "arguments": arguments,
            "forward_polynomial": forward_polynomial,
            "source_polynomials": source_polynomials,
            "macaulay_certificate_sha256": macaulay_sha256,
        }
    )


def _render(atom: Atom) -> str:
    return f"{atom.predicate}({','.join(atom.arguments)})"


def _nondegenerate(atom: Atom) -> bool:
    atom = atom.canonical()
    args = atom.arguments
    if atom.predicate in {"para", "perp", "cong"}:
        return len(args) == 4 and args[0] != args[1] and args[2] != args[3]
    if atom.predicate in {"eqangle", "eqratio"}:
        return len(args) == 8 and all(
            args[index] != args[index + 1] for index in range(0, 8, 2)
        )
    if atom.predicate == "coll":
        return len(args) == 3 and len(set(args)) == 3
    if atom.predicate == "cyclic":
        return len(args) == 4 and len(set(args)) == 4
    if atom.predicate == "midp":
        return len(args) == 3 and args[1] != args[2]
    if atom.predicate == "lequation":
        return len(args) >= 4
    return False


def _informative(atom: Atom) -> bool:
    atom = atom.canonical()
    args = atom.arguments
    if atom.predicate in {"para", "perp", "cong"}:
        if frozenset(args[:2]) == frozenset(args[2:]):
            return False
        if atom.predicate == "para" and set(args[:2]) & set(args[2:]):
            return False
        return True
    if atom.predicate in {"eqangle", "eqratio"}:
        left = tuple(frozenset(args[index : index + 2]) for index in (0, 2))
        right = tuple(frozenset(args[index : index + 2]) for index in (4, 6))
        return left != right
    return True


def _candidate_atoms(
    points: tuple[str, ...],
    *,
    max_candidates: int,
    include_high_arity: bool,
    required_points: frozenset[str] = frozenset(),
) -> tuple[Atom, ...]:
    """Enumerate a bounded typed language, independent of problem identity."""

    records: dict[Atom, None] = {}

    def emit(predicate: str, arguments: tuple[str, ...]) -> None:
        if not required_points <= set(arguments):
            return
        atom = Atom(predicate, arguments).canonical()
        if _nondegenerate(atom) and _informative(atom):
            records.setdefault(atom, None)

    for triple in combinations(points, 3):
        emit("coll", triple)
    for quadruple in combinations(points, 4):
        emit("cyclic", quadruple)

    segments = tuple(combinations(points, 2))
    for left, right in combinations(segments, 2):
        arguments = (*left, *right)
        emit("para", arguments)
        emit("perp", arguments)
        emit("cong", arguments)

    for midpoint in points:
        others = tuple(point for point in points if point != midpoint)
        for left, right in combinations(others, 2):
            emit("midp", (midpoint, left, right))

    if include_high_arity and len(records) < max_candidates:
        line_pairs = tuple(combinations(segments, 2))
        remaining = max_candidates - len(records)
        per_predicate = max(1, remaining // 2)
        emitted = 0
        for left, right in combinations(line_pairs, 2):
            emit("eqangle", (*left[0], *left[1], *right[0], *right[1]))
            emitted += 1
            if emitted >= per_predicate or len(records) >= max_candidates:
                break
        emitted = 0
        for left, right in combinations(line_pairs, 2):
            emit("eqratio", (*left[0], *left[1], *right[0], *right[1]))
            emitted += 1
            if emitted >= per_predicate or len(records) >= max_candidates:
                break

    return tuple(records)[:max_candidates]


@lru_cache(maxsize=131_072)
def _sympify(value: str) -> sp.Expr:
    return sp.expand(sp.sympify(value))


@lru_cache(maxsize=65_536)
def _monic_form(expression: sp.Expr) -> str | None:
    if expression == 0 or not expression.free_symbols:
        return None
    variables = tuple(sorted(expression.free_symbols, key=str))
    polynomial = sp.Poly(expression, *variables, domain=sp.QQ)
    return sp.sstr(polynomial.monic().as_expr())


@lru_cache(maxsize=65_536)
def _square_free_form(expression: sp.Expr) -> str | None:
    """Return a monic square-free polynomial without full factorization."""

    if expression == 0 or not expression.free_symbols:
        return None
    variables = tuple(sorted(expression.free_symbols, key=str))
    polynomial = sp.Poly(expression, *variables, domain=sp.QQ)
    return sp.sstr(polynomial.sqf_part().monic().as_expr())


@lru_cache(maxsize=65_536)
def _strip_certified_nonzero_factors(
    expression: sp.Expr,
    known_nonzero_factors: frozenset[str],
) -> sp.Expr:
    """Divide only factors whose non-zeroness is already certified."""

    reduced = sp.expand(expression)
    for raw_factor in sorted(known_nonzero_factors):
        factor = _sympify(raw_factor)
        if factor == 0 or not factor.free_symbols:
            continue
        while True:
            variables = tuple(
                sorted(reduced.free_symbols | factor.free_symbols, key=str)
            )
            quotient, remainder = sp.div(
                sp.Poly(reduced, *variables, domain=sp.QQ),
                sp.Poly(factor, *variables, domain=sp.QQ),
            )
            if not remainder.is_zero:
                break
            reduced = sp.expand(quotient.as_expr())
    return reduced


@lru_cache(maxsize=8_192)
def _condition_factor_keys(conditions: tuple[str, ...]) -> frozenset[str]:
    keys: set[str] = set()
    for condition in conditions:
        expression = _sympify(condition.rsplit("!=", 1)[0].strip())
        if expression == 0 or not expression.free_symbols:
            continue
        variables = tuple(sorted(expression.free_symbols, key=str))
        _, factors = sp.factor_list(
            sp.Poly(expression, *variables, domain=sp.QQ).as_expr()
        )
        for factor, _ in factors:
            factor_variables = tuple(sorted(factor.free_symbols, key=str))
            keys.add(
                sp.sstr(
                    sp.Poly(
                        factor,
                        *factor_variables,
                        domain=sp.QQ,
                    ).monic().as_expr()
                )
            )
    return frozenset(keys)


def _equivalence(
    lemma: sp.Expr,
    forward: sp.Expr,
    *,
    known_nonzero_factors: frozenset[str] = frozenset(),
) -> tuple[str, str, str] | None:
    reduced_lemma = _strip_certified_nonzero_factors(
        lemma,
        known_nonzero_factors,
    )
    reduced_forward = _strip_certified_nonzero_factors(
        forward,
        known_nonzero_factors,
    )
    lemma_normal = _monic_form(reduced_lemma)
    forward_normal = _monic_form(reduced_forward)
    if lemma_normal is None or forward_normal is None:
        return None
    if lemma_normal == forward_normal:
        mode = (
            "associate"
            if reduced_lemma == lemma and reduced_forward == forward
            else "regularity_associate"
        )
        return mode, lemma_normal, forward_normal
    if reduced_lemma.free_symbols != reduced_forward.free_symbols:
        return None
    lemma_factor = _square_free_form(reduced_lemma)
    forward_factor = _square_free_form(reduced_forward)
    if (
        lemma_factor is not None
        and forward_factor is not None
        and lemma_factor == forward_factor
    ):
        return "radical_associate", lemma_factor, forward_factor
    return None


@lru_cache(maxsize=131_072)
def _expression_symbols(value: str) -> frozenset[str]:
    return frozenset(map(str, _sympify(value).free_symbols))


def _candidate_point_boundary(
    analysis: JGEXExactSystemAnalysis,
    lemma: sp.Expr,
    *,
    max_points: int,
) -> tuple[str, ...]:
    support = frozenset(map(str, lemma.free_symbols))
    scores: dict[str, int] = {
        point: 0 for point, _ in analysis.point_coordinates
    }
    for point, coordinates in analysis.point_coordinates:
        coordinate_support = set().union(
            *(_expression_symbols(value) for value in coordinates)
        )
        scores[point] += 8 * len(support & coordinate_support)

    for block in analysis.construction_blocks:
        block_support = set().union(
            *(_expression_symbols(value) for value in block.surviving_equations)
        ) if block.surviving_equations else set()
        overlap = len(support & block_support)
        if not overlap:
            continue
        for point in (*block.outputs, *block.inputs):
            if point in scores:
                scores[point] += 3 * overlap + (2 if point in block.outputs else 1)

    for point in analysis.points:
        if point in scores:
            scores[point] += 1

    ranked = tuple(
        point
        for point, _ in sorted(
            scores.items(),
            key=lambda item: (-item[1], item[0]),
        )
    )
    positive = tuple(point for point in ranked if scores[point] > 0)
    if len(positive) >= min(3, len(ranked)):
        selected = positive[:max_points]
    else:
        selected = ranked[:max_points]
    return tuple(selected)


def _direct_support_points(
    analysis: JGEXExactSystemAnalysis,
    lemma: sp.Expr,
) -> frozenset[str]:
    """Points whose coordinate terms own variables occurring in the lemma."""

    support = frozenset(map(str, lemma.free_symbols))
    return frozenset(
        point
        for point, coordinates in analysis.point_coordinates
        if support
        & set().union(*(_expression_symbols(value) for value in coordinates))
    )


def _relation_point_arguments(atom: Atom) -> frozenset[str]:
    """Return point tokens while excluding lequation syntax and scalars."""

    if atom.predicate != "lequation":
        return frozenset(atom.arguments)
    points: set[str] = set()
    tokens = atom.arguments[:-1]
    index = 0
    while index < len(tokens):
        if tokens[index] != "*":
            index += 1
        if index + 1 >= len(tokens):
            return frozenset()
        points.update((tokens[index], tokens[index + 1]))
        index += 2
    return frozenset(points)


def _evaluate_relations(
    text: str,
    atoms: tuple[Atom, ...],
    *,
    chunk_size: int = 20_000,
) -> dict[Atom, tuple[str, tuple[str, ...]]]:
    output: dict[Atom, tuple[str, tuple[str, ...]]] = {}
    for offset in range(0, len(atoms), chunk_size):
        chunk = atoms[offset : offset + chunk_size]
        relations = tuple((atom.predicate, atom.arguments) for atom in chunk)
        try:
            evaluated = inspect_jgex_relation_polynomials(
                text,
                relations,
                representation="relational",
            )
            for atom, item in zip(chunk, evaluated, strict=True):
                output[atom] = (item.polynomial, item.nonzero_conditions)
        except ValueError:
            # Some typed relations (notably odd products of lengths) need a
            # branch choice and therefore have no polynomial image in this
            # chart. Reject only that candidate, not the complete demand set.
            for atom in chunk:
                try:
                    item = inspect_jgex_relation_polynomials(
                        text,
                        ((atom.predicate, atom.arguments),),
                        representation="relational",
                    )[0]
                except ValueError:
                    continue
                output[atom] = (item.polynomial, item.nonzero_conditions)
    return output


def reelaborate_polynomial_lemmas(
    text: str,
    lemma_polynomials: Iterable[str],
    *,
    max_points: int = 6,
    max_candidates_per_lemma: int = 12_000,
    max_certificates_per_lemma: int = 16,
    include_high_arity: bool = True,
    candidate_atoms: Iterable[Atom] | None = None,
) -> tuple[PolynomialLemmaReelaboration, ...]:
    """Recover typed atoms for a batch of replayed polynomial lemmas."""

    if max_points < 3 or max_candidates_per_lemma < 1:
        raise ValueError("invalid reverse-elaboration search bound")
    analysis = inspect_jgex_exact_system(text, representation="relational")
    lemma_values = tuple(dict.fromkeys(map(str, lemma_polynomials)))
    parsed = tuple(_sympify(value) for value in lemma_values)
    points_by_lemma = tuple(
        _candidate_point_boundary(analysis, lemma, max_points=max_points)
        for lemma in parsed
    )
    required_points_by_lemma = tuple(
        _direct_support_points(analysis, lemma) for lemma in parsed
    )
    if candidate_atoms is None:
        candidates_by_lemma = tuple(
            _candidate_atoms(
                points,
                max_candidates=max_candidates_per_lemma,
                include_high_arity=include_high_arity,
                required_points=required_points,
            )
            for points, required_points in zip(
                points_by_lemma,
                required_points_by_lemma,
                strict=True,
            )
        )
    else:
        chart_points = {point for point, _ in analysis.point_coordinates}
        supplied = tuple(
            dict.fromkeys(
                atom.canonical()
                for atom in candidate_atoms
                if _relation_point_arguments(atom) <= chart_points
                and _nondegenerate(atom)
                and _informative(atom)
            )
        )[:max_candidates_per_lemma]
        # A constructed point's coordinate expression can contain symbols
        # introduced by several ancestor points. Therefore symbol ownership is
        # not a necessary condition on the arguments of a demanded relation.
        # In demand-directed mode the supplied atoms are already the finite
        # search boundary; exact forward-polynomial replay is the sound filter.
        candidates_by_lemma = tuple(supplied for _ in parsed)
    all_candidates = tuple(
        dict.fromkeys(atom for candidates in candidates_by_lemma for atom in candidates)
    )
    evaluated = _evaluate_relations(text, all_candidates) if all_candidates else {}
    system_conditions = analysis.executable_regularity_conditions
    system_nonzero_factors = _condition_factor_keys(system_conditions)

    results: list[PolynomialLemmaReelaboration] = []
    for raw, lemma, points, candidates in zip(
        lemma_values,
        parsed,
        points_by_lemma,
        candidates_by_lemma,
        strict=True,
    ):
        certificates: list[TypedRelationReelaborationCertificate] = []
        for atom in candidates:
            if atom not in evaluated:
                continue
            forward_raw, nonzero_conditions = evaluated[atom]
            forward = _sympify(forward_raw)
            all_conditions = tuple(
                dict.fromkeys((*system_conditions, *nonzero_conditions))
            )
            match = _equivalence(
                lemma,
                forward,
                known_nonzero_factors=(
                    system_nonzero_factors
                    | _condition_factor_keys(nonzero_conditions)
                ),
            )
            if match is None:
                continue
            mode, lemma_normal, forward_normal = match
            provisional = TypedRelationReelaborationCertificate(
                predicate=atom.predicate,
                arguments=atom.arguments,
                atom=_render(atom),
                lemma_polynomial=raw,
                forward_polynomial=forward_raw,
                equivalence_mode=mode,
                lemma_normal_form=lemma_normal,
                forward_normal_form=forward_normal,
                candidate_points=points,
                nonzero_conditions=all_conditions,
                exact_replay=True,
                certificate_sha256="",
            )
            certificate = TypedRelationReelaborationCertificate(
                **{
                    **asdict(provisional),
                    "certificate_sha256": _hash(asdict(provisional)),
                }
            )
            certificates.append(certificate)
            if len(certificates) >= max_certificates_per_lemma:
                break
        results.append(
            PolynomialLemmaReelaboration(
                lemma_polynomial=raw,
                support_variables=tuple(sorted(map(str, lemma.free_symbols))),
                candidate_points=points,
                candidates_considered=len(candidates),
                certificates=tuple(certificates),
                status="reelaborated" if certificates else "no_exact_typed_match",
            )
        )
    return tuple(results)


def certified_atoms(
    results: Iterable[PolynomialLemmaReelaboration],
) -> tuple[Atom, ...]:
    """Return canonical atoms carried by replayed reverse-elaboration proofs."""

    return tuple(
        dict.fromkeys(
            Atom(certificate.predicate, certificate.arguments).canonical()
            for result in results
            for certificate in result.certificates
            if certificate.exact_replay
        )
    )


def _connected_generators(
    generators: tuple[sp.Expr, ...],
    target: sp.Expr,
) -> tuple[sp.Expr, ...]:
    """Keep the polynomial factor-graph component touching the target."""

    active_symbols = set(target.free_symbols)
    selected: set[int] = set()
    changed = True
    while changed:
        changed = False
        for index, generator in enumerate(generators):
            if index in selected or not (generator.free_symbols & active_symbols):
                continue
            selected.add(index)
            active_symbols.update(generator.free_symbols)
            changed = True
    return tuple(generators[index] for index in sorted(selected))


def certify_polynomial_ideal_relations(
    text: str,
    generator_polynomials: Iterable[str],
    candidate_atoms: Iterable[Atom],
    *,
    max_multiplier_degree: int = 0,
    max_matrix_columns: int = 1_024,
    max_matrix_rows: int = 4_096,
) -> tuple[TypedRelationIdealCertificate, ...]:
    """Prove demanded typed relations from a set of replayed polynomial lemmas."""

    generator_text = tuple(dict.fromkeys(map(str, generator_polynomials)))
    generators = tuple(_sympify(item) for item in generator_text)
    atoms = tuple(dict.fromkeys(atom.canonical() for atom in candidate_atoms))
    evaluated = _evaluate_relations(text, atoms) if atoms else {}
    output: list[TypedRelationIdealCertificate] = []
    for atom in atoms:
        if atom not in evaluated:
            continue
        forward_raw, _ = evaluated[atom]
        forward = _sympify(forward_raw)
        connected = _connected_generators(generators, forward)
        if not connected:
            continue
        variables = tuple(
            sorted(
                set(forward.free_symbols).union(
                    *(item.free_symbols for item in connected)
                ),
                key=str,
            )
        )
        certificate = certify_bounded_macaulay_membership(
            connected,
            variables,
            forward,
            max_multiplier_degree=max_multiplier_degree,
            max_matrix_columns=max_matrix_columns,
            max_matrix_rows=max_matrix_rows,
        )
        if not certificate.proved or not verify_bounded_macaulay_certificate(certificate):
            continue
        source_polynomials = certificate.generator_polynomials
        certificate_hash = _ideal_certificate_hash(
            atom.predicate,
            atom.arguments,
            forward_raw,
            source_polynomials,
            certificate.certificate_sha256,
        )
        output.append(
            TypedRelationIdealCertificate(
                predicate=atom.predicate,
                arguments=atom.arguments,
                atom=_render(atom),
                forward_polynomial=forward_raw,
                source_polynomials=source_polynomials,
                macaulay_certificate=certificate,
                exact_replay=True,
                certificate_sha256=certificate_hash,
            )
        )
    return tuple(output)


def verify_typed_relation_ideal_certificate(
    text: str,
    raw_certificate: Mapping[str, Any] | TypedRelationIdealCertificate,
) -> bool:
    """Replay a set-level polynomial-to-relation certificate."""

    payload = (
        asdict(raw_certificate)
        if isinstance(raw_certificate, TypedRelationIdealCertificate)
        else dict(raw_certificate)
    )
    try:
        atom = Atom(
            str(payload["predicate"]), tuple(map(str, payload["arguments"]))
        ).canonical()
        evaluated = inspect_jgex_relation_polynomials(
            text,
            ((atom.predicate, atom.arguments),),
            representation="relational",
        )[0]
        if _monic_form(_sympify(str(payload["forward_polynomial"]))) != _monic_form(
            _sympify(evaluated.polynomial)
        ):
            return False
        macaulay = payload["macaulay_certificate"]
        if not isinstance(macaulay, Mapping) or not verify_bounded_macaulay_certificate(macaulay):
            return False
        source_polynomials = tuple(map(str, payload["source_polynomials"]))
        if source_polynomials != tuple(map(str, macaulay["generator_polynomials"])):
            return False
        expected_hash = _ideal_certificate_hash(
            atom.predicate,
            atom.arguments,
            str(payload["forward_polynomial"]),
            source_polynomials,
            str(macaulay["certificate_sha256"]),
        )
    except (KeyError, TypeError, ValueError, sp.PolynomialError):
        return False
    return bool(
        payload.get("exact_replay") is True
        and payload.get("certificate_sha256") == expected_hash
    )


def verify_typed_relation_certificate(
    text: str,
    raw_certificate: Mapping[str, Any] | TypedRelationReelaborationCertificate,
) -> bool:
    """Replay a serialized certificate at an agent/process boundary."""

    payload = (
        asdict(raw_certificate)
        if isinstance(raw_certificate, TypedRelationReelaborationCertificate)
        else dict(raw_certificate)
    )
    expected_hash = str(payload.get("certificate_sha256", ""))
    hash_payload = {**payload, "certificate_sha256": ""}
    if len(expected_hash) != 64 or _hash(hash_payload) != expected_hash:
        return False
    if payload.get("exact_replay") is not True:
        return False
    try:
        atom = Atom(
            str(payload["predicate"]),
            tuple(map(str, payload["arguments"])),
        ).canonical()
        evaluated = inspect_jgex_relation_polynomials(
            text,
            ((atom.predicate, atom.arguments),),
            representation="relational",
        )[0]
        analysis = inspect_jgex_exact_system(text, representation="relational")
        replayed_conditions = tuple(
            dict.fromkeys(
                (
                    *analysis.executable_regularity_conditions,
                    *evaluated.nonzero_conditions,
                )
            )
        )
        stored_conditions = tuple(map(str, payload.get("nonzero_conditions", ())))
        if stored_conditions != replayed_conditions:
            return False
        stored_forward = _sympify(str(payload["forward_polynomial"]))
        replayed_forward = _sympify(evaluated.polynomial)
        if _monic_form(stored_forward) != _monic_form(replayed_forward):
            return False
        match = _equivalence(
            _sympify(str(payload["lemma_polynomial"])),
            replayed_forward,
            known_nonzero_factors=_condition_factor_keys(replayed_conditions),
        )
    except (KeyError, TypeError, ValueError, sp.PolynomialError):
        return False
    return bool(
        match is not None
        and match[0] == payload.get("equivalence_mode")
        and match[1] == payload.get("lemma_normal_form")
        and match[2] == payload.get("forward_normal_form")
    )
