"""Typed local relation stalks extracted from JGEX construction semantics.

The module keeps heavy constructions as finite relation atoms.  It does not
expand their coordinates and does not contain any benchmark problem name.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Mapping

from newclid.jgex.constructions import ALL_JGEX_CONSTRUCTIONS
from newclid.jgex.definition import JGEXDefinition
from newclid.jgex.formulation import JGEXFormulation

from worker.backend.geometry_local_lemma_certificate import (
    external_homothety_boundary_certificates,
    external_homothety_tangent_certificate,
)
from worker.backend.geometry_proof_hypergraph import Atom, Theorem
from worker.backend.jgex_gclc_translator import external_homothety_macros
from worker.backend.jgex_legacy_normalizer import normalize_legacy_formulation
from worker.backend.symbolic_sheaf_coordination import (
    AgentProposal,
    LocalCertificate,
)


@dataclass(frozen=True)
class JGEXStalkCertificate:
    rule_name: str
    premises: tuple[Atom, ...]
    conclusions: tuple[Atom, ...]
    hidden_points: tuple[str, ...]
    native_kind: str
    native_reference: str
    replayed: bool
    certificate_sha256: str


@dataclass(frozen=True)
class JGEXRelationStalk:
    source_atoms: tuple[Atom, ...]
    certificates: tuple[JGEXStalkCertificate, ...]
    relation_counts: Mapping[str, int] = field(compare=False)


def _atom(predicate: str, *arguments: str) -> Atom:
    return Atom(predicate, tuple(arguments)).canonical()


def _certificate(
    *,
    rule_name: str,
    premises: tuple[Atom, ...],
    conclusions: tuple[Atom, ...],
    hidden_points: tuple[str, ...] = (),
    native_kind: str,
    native_reference: str,
    replayed: bool,
) -> JGEXStalkCertificate:
    material = "|".join(
        (
            rule_name,
            *(f"{item.predicate}:{','.join(item.arguments)}" for item in premises),
            "=>",
            *(f"{item.predicate}:{','.join(item.arguments)}" for item in conclusions),
            *hidden_points,
            native_kind,
            native_reference,
            str(replayed),
        )
    )
    return JGEXStalkCertificate(
        rule_name=rule_name,
        premises=premises,
        conclusions=conclusions,
        hidden_points=hidden_points,
        native_kind=native_kind,
        native_reference=native_reference,
        replayed=replayed,
        certificate_sha256=hashlib.sha256(material.encode()).hexdigest(),
    )


def _on_aline_certificate(args: tuple[str, ...]) -> JGEXStalkCertificate:
    point, a, b, c, d, e = args
    premise = _atom("on_aline", point, a, b, c, d, e)
    conclusion = _atom("eqangle", a, point, a, b, d, c, d, e)
    return _certificate(
        rule_name="on_aline_definition_to_equal_angle",
        premises=(premise,),
        conclusions=(conclusion,),
        native_kind="jgex_definition",
        native_reference="on_aline:eqangle(a,p,a,b,d,c,d,e)",
        replayed=True,
    )


def _cc_tangent_certificate(args: tuple[str, ...]) -> JGEXStalkCertificate:
    first, second, third, fourth, center_a, radius_a, center_b, radius_b = args
    premise = _atom("cc_tangent", *args)
    conclusions = (
        _atom("cong", center_a, first, center_a, radius_a),
        _atom("cong", center_b, second, center_b, radius_b),
        _atom("perp", first, center_a, first, second),
        _atom("perp", second, center_b, second, first),
        _atom("cong", center_a, third, center_a, radius_a),
        _atom("cong", center_b, fourth, center_b, radius_b),
        _atom("perp", third, center_a, third, fourth),
        _atom("perp", fourth, center_b, fourth, third),
    )
    return _certificate(
        rule_name="cc_tangent_definition_to_metric_relations",
        premises=(premise,),
        conclusions=conclusions,
        native_kind="jgex_definition",
        native_reference="cc_tangent:2*(cong,cong,perp,perp)",
        replayed=True,
    )


def extract_jgex_relation_stalk(text: str) -> JGEXRelationStalk:
    definitions = JGEXDefinition.to_dict(list(ALL_JGEX_CONSTRUCTIONS))
    formulation, report = normalize_legacy_formulation(
        JGEXFormulation.from_text(text), definitions
    )
    if report.unresolved_constructions:
        raise ValueError("JGEX normalization left unresolved constructions")

    source_atoms: set[Atom] = set()
    certificates: list[JGEXStalkCertificate] = []
    for clause in formulation.setup_clauses:
        for construction in clause.constructions:
            args = tuple(str(argument) for argument in construction.args)
            source_atoms.add(_atom(construction.name, *args))
            if construction.name == "on_aline":
                certificates.append(_on_aline_certificate(args))
            elif construction.name == "cc_tangent":
                certificates.append(_cc_tangent_certificate(args))

    composition_certificate = external_homothety_tangent_certificate()
    for macro in external_homothety_macros(formulation):
        tangent = _atom(
            "cc_tangent",
            *macro.hidden_tangent_points,
            macro.center_a,
            macro.radius_a,
            macro.center_b,
            macro.radius_b,
        )
        intersection = _atom(
            "line_intersection",
            macro.output,
            *macro.hidden_tangent_points,
        )
        source_atoms.add(intersection)
        conclusion = _atom(
            "external_homothety",
            macro.output,
            macro.center_a,
            macro.radius_a,
            macro.center_b,
            macro.radius_b,
        )
        certificates.append(
            _certificate(
                rule_name="external_tangent_intersection_to_homothety",
                premises=(tangent, intersection),
                conclusions=(conclusion,),
                hidden_points=macro.hidden_tangent_points,
                native_kind="polynomial_ideal_identity",
                native_reference=composition_certificate.certificate_sha256,
                replayed=composition_certificate.replayed,
            )
        )
        collinear_certificate, ratio_certificate = (
            external_homothety_boundary_certificates()
        )
        certificates.extend(
            (
                _certificate(
                    rule_name="external_homothety_to_center_collinearity",
                    premises=(conclusion,),
                    conclusions=(
                        _atom(
                            "coll",
                            macro.output,
                            macro.center_a,
                            macro.center_b,
                        ),
                    ),
                    native_kind="polynomial_ideal_identity",
                    native_reference=collinear_certificate.certificate_sha256,
                    replayed=collinear_certificate.replayed,
                ),
                _certificate(
                    rule_name="external_homothety_to_radius_ratio",
                    premises=(conclusion,),
                    conclusions=(
                        _atom(
                            "eqratio",
                            macro.output,
                            macro.center_a,
                            macro.output,
                            macro.center_b,
                            macro.center_a,
                            macro.radius_a,
                            macro.center_b,
                            macro.radius_b,
                        ),
                    ),
                    native_kind="polynomial_ideal_identity",
                    native_reference=ratio_certificate.certificate_sha256,
                    replayed=ratio_certificate.replayed,
                ),
            )
        )

    relation_counts: dict[str, int] = {}
    for certificate in certificates:
        for conclusion in certificate.conclusions:
            relation_counts[conclusion.predicate] = (
                relation_counts.get(conclusion.predicate, 0) + 1
            )
    return JGEXRelationStalk(
        source_atoms=tuple(sorted(source_atoms)),
        certificates=tuple(certificates),
        relation_counts=relation_counts,
    )


class JGEXRelationStalkAdapter:
    """Expose verified JGEX construction sections to the exact coordinator."""

    agent_id = "jgex-relation-stalk"

    def __init__(self, stalk: JGEXRelationStalk) -> None:
        self.stalk = stalk
        self.imports = frozenset(
            premise.predicate
            for certificate in stalk.certificates
            for premise in certificate.premises
        )
        self.exports = frozenset(
            conclusion.predicate
            for certificate in stalk.certificates
            for conclusion in certificate.conclusions
        )
        self._certificates = {
            (certificate.rule_name, conclusion): certificate
            for certificate in stalk.certificates
            for conclusion in certificate.conclusions
        }
        self.theorems = tuple(
            Theorem(
                certificate.rule_name,
                certificate.premises,
                conclusion,
            )
            for certificate in stalk.certificates
            for conclusion in certificate.conclusions
        )

    def certificate_for_gate(
        self,
        gate: object,
        *,
        round_index: int,
    ) -> LocalCertificate:
        conclusion = getattr(gate, "conclusion").canonical()
        rule_name = str(getattr(gate, "theorem"))
        expected = self._certificates[(rule_name, conclusion)]
        return LocalCertificate(
            agent_id=self.agent_id,
            rule_name=rule_name,
            conclusion=conclusion,
            premises=expected.premises,
            native_payload={
                "round": round_index,
                "kind": expected.native_kind,
                "reference": expected.native_reference,
                "certificate_sha256": expected.certificate_sha256,
                "replayed": expected.replayed,
            },
        )

    def propose(
        self,
        facts: frozenset[Atom],
        goal: Atom,
        *,
        round_index: int,
    ) -> AgentProposal:
        canonical_facts = {item.canonical() for item in facts}
        proposals: list[LocalCertificate] = []
        for certificate in self.stalk.certificates:
            if not set(certificate.premises) <= canonical_facts:
                continue
            for conclusion in certificate.conclusions:
                if conclusion in canonical_facts:
                    continue
                proposals.append(
                    LocalCertificate(
                        agent_id=self.agent_id,
                        rule_name=certificate.rule_name,
                        conclusion=conclusion,
                        premises=certificate.premises,
                        native_payload={
                            "round": round_index,
                            "kind": certificate.native_kind,
                            "reference": certificate.native_reference,
                            "certificate_sha256": certificate.certificate_sha256,
                            "replayed": certificate.replayed,
                        },
                    )
                )
        return AgentProposal(
            certificates=tuple(proposals),
            open_obligations=() if goal.canonical() in canonical_facts else (goal,),
        )

    def verify(self, certificate: LocalCertificate, facts: frozenset[Atom]) -> bool:
        expected = self._certificates.get(
            (certificate.rule_name, certificate.conclusion.canonical())
        )
        if expected is None or not expected.replayed:
            return False
        if not set(expected.premises) <= {item.canonical() for item in facts}:
            return False
        return (
            certificate.agent_id == self.agent_id
            and certificate.premises == expected.premises
            and certificate.native_payload.get("certificate_sha256")
            == expected.certificate_sha256
            and certificate.native_payload.get("reference") == expected.native_reference
            and certificate.native_payload.get("replayed") is True
        )
