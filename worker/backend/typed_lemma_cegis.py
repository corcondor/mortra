"""Typed CEGIS loop for local intermediate-lemma discovery.

This module never accepts a mathematical claim by ranking or numerical fit.
It turns open proof frontiers into finite typed obligations, asks an optional
counterexample oracle to refute them, and promotes only obligations carrying
an exact verifier certificate.  The accepted objects are local lemmas in the
ambient problem context, not memorized universal theorem schemas.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from itertools import product
from typing import Callable, Iterable, Literal, Mapping, Sequence

from worker.backend.geometry_proof_hypergraph import Atom


VerificationStatus = Literal["proved", "counterexample", "unknown"]


def _is_hole(value: str) -> bool:
    return value.startswith("?")


def _render_atom(atom: Atom) -> str:
    canonical = atom.canonical()
    return f"{canonical.predicate}({','.join(canonical.arguments)})"


@dataclass(frozen=True)
class PredicateSignature:
    name: str
    argument_sorts: tuple[str, ...]


@dataclass(frozen=True)
class LocalLemmaObligation:
    conclusion: Atom
    support_hints: tuple[Atom, ...]
    hole_bindings: tuple[tuple[str, str], ...]
    source_frontier: str

    @property
    def key(self) -> str:
        payload = "|".join(
            (
                _render_atom(self.conclusion),
                *(_render_atom(item) for item in self.support_hints),
                *(f"{left}={right}" for left, right in self.hole_bindings),
            )
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "conclusion": _render_atom(self.conclusion),
            "support_hints": [_render_atom(item) for item in self.support_hints],
            "hole_bindings": dict(self.hole_bindings),
            "source_frontier": self.source_frontier,
        }


@dataclass(frozen=True)
class LemmaVerification:
    status: VerificationStatus
    verifier: str
    certificate_sha256: str | None = None
    counterexample: str | None = None
    detail: str | None = None

    @property
    def certified(self) -> bool:
        return self.status == "proved" and bool(self.certificate_sha256)


@dataclass(frozen=True)
class CertifiedLocalLemma:
    obligation: LocalLemmaObligation
    verification: LemmaVerification

    def to_dict(self) -> dict[str, object]:
        return {
            "obligation": self.obligation.to_dict(),
            "verification": {
                "status": self.verification.status,
                "verifier": self.verification.verifier,
                "certificate_sha256": self.verification.certificate_sha256,
                "counterexample": self.verification.counterexample,
                "detail": self.verification.detail,
            },
        }


@dataclass(frozen=True)
class LemmaCEGISResult:
    proposed: tuple[LocalLemmaObligation, ...]
    accepted: tuple[CertifiedLocalLemma, ...]
    rejected_counterexamples: tuple[CertifiedLocalLemma, ...]
    unknown: tuple[CertifiedLocalLemma, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "proposed": len(self.proposed),
            "accepted": [item.to_dict() for item in self.accepted],
            "rejected_counterexamples": [
                item.to_dict() for item in self.rejected_counterexamples
            ],
            "unknown": [item.to_dict() for item in self.unknown],
        }


def _hole_sorts(
    atom: Atom,
    signature: PredicateSignature,
) -> dict[str, str] | None:
    if len(atom.arguments) != len(signature.argument_sorts):
        return None
    result: dict[str, str] = {}
    for argument, sort in zip(atom.arguments, signature.argument_sorts, strict=True):
        if not _is_hole(argument):
            continue
        previous = result.get(argument)
        if previous is not None and previous != sort:
            return None
        result[argument] = sort
    return result


def _instantiate_atom(atom: Atom, bindings: Mapping[str, str]) -> Atom:
    return Atom(
        atom.predicate,
        tuple(bindings.get(argument, argument) for argument in atom.arguments),
    ).canonical()


def enumerate_local_lemma_obligations(
    facts: Iterable[Atom],
    frontier_atoms: Iterable[Atom],
    signatures: Mapping[str, PredicateSignature],
    entity_sorts: Mapping[str, str],
    *,
    support_hint_limit: int = 4,
    max_hole_instantiations: int = 64,
    max_obligations: int = 128,
) -> tuple[LocalLemmaObligation, ...]:
    """Compile open atoms into a finite, type-correct local lemma language.

    Holes are instantiated only with visible entities of the declared sort.
    Support hints are ranked by shared entities; they guide decomposition but
    are not treated as proof.  No benchmark identifier or expected answer is
    an input to this function.
    """

    canonical_facts = tuple(sorted({item.canonical() for item in facts}, key=_render_atom))
    entities_by_sort: dict[str, tuple[str, ...]] = {}
    for sort in sorted(set(entity_sorts.values())):
        entities_by_sort[sort] = tuple(
            sorted(name for name, entity_sort in entity_sorts.items() if entity_sort == sort)
        )

    obligations: dict[str, LocalLemmaObligation] = {}
    for frontier_index, raw_frontier in enumerate(frontier_atoms):
        frontier = raw_frontier.canonical()
        signature = signatures.get(frontier.predicate)
        if signature is None:
            continue
        hole_sorts = _hole_sorts(frontier, signature)
        if hole_sorts is None:
            continue
        holes = tuple(sorted(hole_sorts))
        domains = tuple(entities_by_sort.get(hole_sorts[hole], ()) for hole in holes)
        if any(not domain for domain in domains):
            continue
        assignments = product(*domains) if holes else ((),)
        for assignment_index, values in enumerate(assignments):
            if assignment_index >= max_hole_instantiations:
                break
            binding = dict(zip(holes, values, strict=True))
            conclusion = _instantiate_atom(frontier, binding)
            if any(_is_hole(argument) for argument in conclusion.arguments):
                continue
            if conclusion in canonical_facts:
                continue
            conclusion_entities = set(conclusion.arguments)
            support = tuple(
                sorted(
                    (
                        fact
                        for fact in canonical_facts
                        if conclusion_entities.intersection(fact.arguments)
                    ),
                    key=lambda fact: (
                        -len(conclusion_entities.intersection(fact.arguments)),
                        _render_atom(fact),
                    ),
                )[:support_hint_limit]
            )
            item = LocalLemmaObligation(
                conclusion=conclusion,
                support_hints=support,
                hole_bindings=tuple(sorted(binding.items())),
                source_frontier=f"frontier:{frontier_index}",
            )
            obligations.setdefault(item.key, item)
            if len(obligations) >= max_obligations:
                return tuple(obligations.values())
    return tuple(obligations.values())


def run_typed_lemma_cegis(
    obligations: Sequence[LocalLemmaObligation],
    *,
    verifier: Callable[[LocalLemmaObligation], LemmaVerification],
    counterexample_oracle: Callable[
        [LocalLemmaObligation], LemmaVerification | None
    ]
    | None = None,
    max_verifications: int = 32,
) -> LemmaCEGISResult:
    """Refute first, then accept only exact replayable lemma certificates."""

    accepted: list[CertifiedLocalLemma] = []
    rejected: list[CertifiedLocalLemma] = []
    unknown: list[CertifiedLocalLemma] = []
    for obligation in obligations[:max_verifications]:
        refutation = (
            counterexample_oracle(obligation)
            if counterexample_oracle is not None
            else None
        )
        if refutation is not None and refutation.status == "counterexample":
            rejected.append(CertifiedLocalLemma(obligation, refutation))
            continue
        verification = verifier(obligation)
        item = CertifiedLocalLemma(obligation, verification)
        if verification.certified:
            accepted.append(item)
        elif verification.status == "counterexample":
            rejected.append(item)
        else:
            unknown.append(item)
    return LemmaCEGISResult(
        proposed=tuple(obligations),
        accepted=tuple(accepted),
        rejected_counterexamples=tuple(rejected),
        unknown=tuple(unknown),
    )
