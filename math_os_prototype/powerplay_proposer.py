"""Where (task, modification) pairs come from: the generators that already exist.

Nothing here generates mathematics. The repository already has the pieces and
they are used as they stand:

    extend_seeds        acquired constructions re-enter the seed set, so a later
                        proposal is built from what an earlier one won
    make_features       the closure: x-multiples, derivatives, products
    guess_relations     candidate linear relations among those features
    certify_relation    the proof, which on the closure backend is exactly a
                        `certify_equal` certificate against zero
    build_memory        proved records become constructions for the next round

What this adds is only the part that was missing: giving each candidate a search
allowance it is actually stopped at, and handing the survivor to the acceptance
gate. A relation is a modification because its certificate names a program that
must reduce to zero, and the task is that the controller can do it.

The proposer never decides whether a relation holds. `certify_relation` does,
and on the abstract side `prove_identity` does.

Acquisitions keep their parts together
    An acquisition carries the body, the names its arguments have, the domain it
    runs on and a reference to the proof that admitted it, and hands all of that
    to whatever the type table says comes next. Two routes that arrive at the
    same body are one object, but both routes are kept on it, because which
    rearrangement induced it and which proof admitted it are not the same fact
    as what the body is.
"""
from __future__ import annotations

from copy import deepcopy

from math_os_prototype.abstraction_correspondence import (
    abstract_signature, compose_operations, composition_law, conserved_quantities,
    correspondence, fill, is_identity_operation, normal_form, prove_identity,
    record_image_condition, slot)
from math_os_prototype.acquisition_followups import (
    abstraction_candidates, follow_ups, morphism_candidates)
from math_os_prototype.holonomic_construction_memory import build_memory, extend_seeds
from math_os_prototype.library_compression import (
    call_candidates, canonical_literals, definition_table, expand, matches_bias,
    search_bias)
from math_os_prototype.job_sharing import JobStore
from math_os_prototype.holonomic_joint_action_control import canonical_relation
from math_os_prototype.holonomic_route_discovery import key, validate
from math_os_prototype.holonomic_joint_relations import (
    ZERO as RELATION_TARGET, _wrap_certificate, certify_relation, guess_relations,
    make_features, relation_program)
from math_os_prototype.holonomic_route_discovery import certify_equal
from math_os_prototype.representation_progress import digest
from math_os_prototype.search_budget import run_within

SCHEMA = "mortra.powerplay-proposer.v3"
SCOPE = ("candidates from the existing feature closure and relation guesser; "
         "generation and proof are not reimplemented here")
ZERO = {"op": "poly", "coefficients": [0]}
# `make_features` takes at most this many programs. The limit belongs to the
# feature builder, so it is enforced where the list is handed over rather than
# guessed at when seeds are collected: widening the grammar makes more things
# acquirable, and the seed set then grows past a cap that was never checked here.
FEATURE_PROGRAM_LIMIT = 32


class Proposer:
    """Rations the existing generators. It adds no mathematics of its own."""

    def __init__(self, seeds, *, degree_x=1, derivatives=1, product_degree=1,
                 holdout=16, proof_backend="closure", state_names=(),
                 parameter_names=(), abstraction_witnesses=(), conservation_degree=2,
                 span_degree=2, span_derivatives=0, morphism_derivatives=0,
                 library=(), library_weight=2, library_calls=6,
                 library_share=0.34, share_jobs=False):
        if not seeds:
            raise ValueError("the proposer needs at least one seed program")
        self.seeds = [deepcopy(p) for p in seeds]
        self.degree_x = degree_x
        self.derivatives = derivatives
        self.product_degree = product_degree
        self.holdout = holdout
        self.proof_backend = proof_backend
        self.state_names = list(state_names)
        self.parameter_names = list(parameter_names)
        self.witnesses = [dict(b) for b in abstraction_witnesses]
        self.conservation_degree = conservation_degree
        # The declared span the complete solve is complete in, and how far the
        # morphism grammar differentiates. Both are configuration, not a target:
        # widening them changes what may be searched, never what is expected.
        self.span_degree = span_degree
        self.span_derivatives = span_derivatives
        self.morphism_derivatives = morphism_derivatives
        # A learned library changes two things and nothing else: there are calls
        # to propose, and a candidate that already contains a learned shape is
        # looked at earlier. Nothing is added to the controller, so what may be
        # derived is exactly what could be derived before.
        self.library = [dict(entry) for entry in library]
        self.definitions = definition_table({entry["index"]: entry["template"]
                                             for entry in self.library})
        self.bias = search_bias({"library": [
            {"id": entry["id"], "template": entry["template"],
             "utility_bits": entry.get("utility_bits", 1)}
            for entry in self.library]}, weight=library_weight)
        self.library_calls = library_calls
        # One allowance, split between the two routes by a declared fraction, so
        # the macro route is work taken out of the same budget rather than work
        # added on top of it. An empty group hands its share back.
        if not 0.0 <= library_share < 1.0:
            raise ValueError("the library share must be a fraction below one")
        self.library_share = library_share
        self.reweighted = []
        # Two roads reach the same program; the expensive part does not care
        # which. A job is shared only when the operation, the terms, the
        # premises and the versions all agree. Measured on this loop no job was
        # ever asked for twice -- every residual reached was distinct -- so the
        # store is off unless a caller asks for it, and its phase accounting
        # runs either way.
        import sympy
        self.jobs = JobStore(
            {"prover": f"sympy {sympy.__version__}",
             "certificate_schema": "mortra.joint-series-relation.v1",
             "definitions": self.definitions["sha256"],
             "closure": [degree_x, derivatives, product_degree, holdout,
                         proof_backend]},
            enabled=share_jobs)
        self.presentations = {}
        self.repeat_tasks = []
        # make_features takes at most 32 programs; leave room for the base seeds.
        self.seed_ceiling = 24
        self.declared_bounds = []
        self.candidates = []
        self.records = []
        self.acquisitions = []
        self.repeats = []
        self.extra_seeds = []
        self._sweeps = 0
        self._enumerated = (abstraction_candidates(self.state_names)
                            if self.state_names else [])
        self._drafted = set()
        # Bounds are reported with every sweep, because one that is not stated
        # reads as full coverage.

    # ---- generation, entirely by existing functions ------------------------

    def features(self, memory=None):
        """Seeds, widened by whatever has already been acquired.

        `extend_seeds` puts the base seeds first, then what the follow-up table
        produced, then the constructions in memory. When there are more than the
        feature builder accepts, the tail is left out and that is recorded: a
        bound nobody states reads as full coverage.
        """
        programs = self.jobs.timed(
            "generation", lambda: extend_seeds(self.seeds + self.extra_seeds,
                                               memory))
        if len(programs) > FEATURE_PROGRAM_LIMIT:
            dropped = len(programs) - FEATURE_PROGRAM_LIMIT
            note = (f"the feature builder accepts at most {FEATURE_PROGRAM_LIMIT} "
                    f"programs; the last {dropped} of the widened seeds were left "
                    "out of this sweep")
            if note not in self.declared_bounds:
                self.declared_bounds.append(note)
            programs = programs[:FEATURE_PROGRAM_LIMIT]
        return self._features_of(programs, representation="seeds")

    def _features_of(self, programs, *, representation):
        """The feature closure of these programs, computed once per job."""
        built, _ = self.jobs.run(
            operation="make_features",
            terms=[key(program) for program in programs],
            premises={"degree_x": self.degree_x, "derivatives": self.derivatives,
                      "product_degree": self.product_degree},
            representation=representation, phase="closure",
            work=lambda: make_features(programs, degree_x=self.degree_x,
                                       derivatives=self.derivatives,
                                       product_degree=self.product_degree))
        return built

    def _certify(self, features, terms, *, representation):
        """The certificate for this relation, with the proof shared by residual.

        What costs is `certify_equal(residual, zero)`: a common annihilator, a
        remainder replay, a uniqueness bound and the initial coefficients. That
        depends on the residual program and on nothing else, so it is the unit
        two routes can share -- the same term written as a call and written out
        in full reduce to the same residual.

        The wrapper cannot be shared. It records which features and which term
        indices the relation was stated over, and `replay_relation` recomputes
        it against the features it is handed, so a certificate carried across
        from a different feature set would fail to replay. It is rebuilt here,
        which is hashing and no more.
        """
        residual = relation_program(features, terms)
        proof, _ = self.jobs.run(
            operation="certify_equal_against_zero",
            terms=[key(canonical_literals(residual))],
            premises={"target": "zero", "backend": self.proof_backend,
                      "scope": "Q[[x]] at zero; analytic germs only"},
            representation=representation, phase="proof",
            work=lambda: certify_equal(residual, RELATION_TARGET))
        if proof.get("status") != "exact_formal_series_equality":
            return {"status": proof.get("status"), "proof_attempt": proof}
        return self.jobs.timed(
            "wrapping",
            lambda: _wrap_certificate(features, terms, proof, self.proof_backend))

    def acquisition(self, identity):
        for entry in self.acquisitions:
            if entry["id"] == identity:
                return entry
        return None

    def _content_key(self, acquisition):
        """What the acquisition is, ignoring which route reached it.

        The same body can be induced by more than one rearrangement, and the
        same quantity solved for from more than one operation. It is one object
        however many routes find it, so counting each arrival again would
        inflate the total and spawn duplicate follow-ups. The routes themselves
        are not thrown away; they are kept on the object.
        """
        payload = {"kind": acquisition["kind"]}
        if acquisition["kind"] in ("observable", "domain_condition",
                                   "constant_observation"):
            # The same spelling on two abstract objects is two quantities: a1 on
            # the pair (u, v) and a1 on the pair (u, 2v) are not the same thing.
            payload["expression"] = acquisition.get("expression")
            payload["coordinate_names"] = acquisition.get("coordinate_names")
            payload["domain"] = self._domain_key(acquisition.get("signature"))
        elif acquisition["kind"] == "operation":
            operation = acquisition["operation"]
            payload["body"] = operation.get("body")
            payload["names"] = [operation.get("coordinate_names"),
                                operation.get("parameter_names")]
            payload["domain"] = normal_form(
                (operation.get("domain") or {}).get("abstraction_map") or [])
        elif acquisition["kind"] == "abstraction":
            payload["alpha"] = normal_form(acquisition["record"]["abstraction_map"])
        else:
            payload["program"] = acquisition.get("program")
        return digest(payload)

    @staticmethod
    def _domain_key(signature):
        """Which abstract object a quantity lives on, as a normalised key."""
        if not signature:
            return None
        return normal_form(signature.get("alpha") or [])

    @staticmethod
    def _route(acquisition):
        """How this arrival reached the object, kept even when the body repeats."""
        return {"from_candidate": acquisition.get("from_candidate"),
                "morphism": acquisition.get("morphism"),
                "abstraction": acquisition.get("abstraction"),
                "from_operation": acquisition.get("from_operation"),
                "argument_correspondence": acquisition.get("argument_correspondence"),
                "proofs": acquisition.get("proof_reference")}

    def _register(self, acquisition):
        """Record an acquisition and queue whatever its type allows next."""
        content = self._content_key(acquisition)
        existing = next((a for a in self.acquisitions if a["content"] == content), None)
        if existing is not None:
            route = self._route(acquisition)
            existing.setdefault("routes", []).append(route)
            self.repeats.append({"kind": acquisition["kind"], "content": content,
                                 "reached": existing["id"], "route": route})
            return {"seeds": [], "candidates": [],
                    "reason": f"already acquired as {existing['id']}; route kept"}
        acquisition["content"] = content
        acquisition.setdefault("id", digest(acquisition)[:16])
        acquisition.setdefault("routes", [self._route(acquisition)])
        self.acquisitions.append(acquisition)
        context = {"known_operations": [a for a in self.acquisitions
                                        if a["kind"] == "operation"
                                        and a["id"] != acquisition["id"]]}
        produced = follow_ups(acquisition, context)
        for bound in produced.get("bounds", []):
            if bound not in self.declared_bounds:
                self.declared_bounds.append(bound)
        # `make_features` refuses a repeated input, and the seed list is a set in
        # spirit. Follow-ups from different acquisitions often land on the same
        # program, so they are folded in rather than appended blindly.
        known = {key(p) for p in self.seeds + self.extra_seeds}
        for program in produced["seeds"]:
            try:
                validate(program)
                encoded = key(program)
            except Exception:                       # noqa: BLE001 - wrong type here
                continue
            if encoded not in known and len(self.extra_seeds) < self.seed_ceiling:
                known.add(encoded)
                self.extra_seeds.append(program)
        for entry in produced["candidates"]:
            entry = dict(entry)
            entry["id"] = digest(entry)[:16]
            if entry["id"] not in {c["id"] for c in self.candidates}:
                entry.update(weight=1, attempts=0, state="pending", spent_lines=0,
                             derivation={"source": "follow-up of an acquisition",
                                         "parent": acquisition["id"],
                                         "kind": entry["kind"],
                                         "reads": entry.get("with")
                                                  or entry.get("against")})
                self.candidates.append(entry)
        return produced

    def _signature(self, alpha):
        return abstract_signature(
            alpha, coordinate_names=[f"a{i}" for i in range(len(alpha))],
            parameter_names=list(self.parameter_names))

    def _abstraction_drafts(self, draft_count):
        """Offer abstractions enumerated from the shared grammar."""
        if not (self.state_names and self.witnesses):
            return 0
        known = {c["id"] for c in self.candidates}
        morphisms = morphism_candidates(self.state_names, self.parameter_names,
                                        derivatives=self.morphism_derivatives)
        added = 0
        for candidate in self._enumerated:
            if added >= draft_count:
                break
            identity = digest({"abstraction": candidate["id"]})[:16]
            if identity in known:
                continue
            known.add(identity)
            self._drafted.add(candidate["id"])
            self.candidates.append(
                {"id": identity, "kind": "abstraction", "alpha": candidate["alpha"],
                 "morphisms": {m["id"]: m["morphism"] for m in morphisms},
                 "weight": 1, "attempts": 0, "state": "pending", "spent_lines": 0,
                 "derivation": {"source": "abstraction_candidates over the shared grammar",
                                "state_names": list(self.state_names),
                                "enumerated": candidate["id"]}})
            added += 1
        return added

    def undrafted(self):
        """Enumerated abstractions that have not been offered yet.

        The queue running dry is not the same as the enumeration running out,
        and reporting one as the other would claim the search had been exhausted
        when it had barely started.
        """
        return [c["id"] for c in self._enumerated if c["id"] not in self._drafted]

    def _library_drafts(self, draft_count, memory=None):
        """Calls of the learned definitions, with arguments this search has.

        The argument pool is the search's own seeds and whatever it has already
        acquired; the rationals come from those same programs. A combination
        whose expansion is already among them is not offered, so what reaches
        the queue is the combinations nobody has written down yet.
        """
        if not self.library or draft_count < 1:
            return 0
        pool = extend_seeds(self.seeds + self.extra_seeds, memory)
        known = {key(program) for program in pool}
        # Calls already offered join the pool, so a call may take a call. What
        # the arguments are is still drawn from what the search has; nothing
        # about which combination is worth trying is supplied.
        argument_pool = pool + [c["call"] for c in self.candidates
                                if c.get("kind") == "library_call"]
        offered = self.jobs.timed(
            "generation",
            lambda: call_candidates(self.library, argument_pool,
                                    limit=draft_count * 4, exclude=known,
                                    table=self.definitions))
        present = {c["id"] for c in self.candidates}
        added = 0
        for entry in offered:
            if added >= draft_count or entry["id"] in present:
                continue
            self.candidates.append(
                {"id": entry["id"], "kind": "library_call", "call": entry["call"],
                 "definition": entry["definition"],
                 "weight": 1, "attempts": 0, "state": "pending", "spent_lines": 0,
                 "derivation": {"source": "call_candidates over the learned library",
                                "definition": entry["definition"],
                                "call_bits": entry["call_bits"],
                                "expanded_bits": entry["expanded_bits"]}})
            added += 1
        return added

    def _apply_bias(self, candidate, program):
        """Look at a candidate earlier when it already contains a learned shape.

        Applied once, where the candidate is created. Re-applying it every sweep
        would compound into a weight nothing else could catch up with, which is
        a different mechanism from being looked at earlier.
        """
        if not self.bias["entries"] or program is None:
            return
        hits = self.jobs.timed("matching",
                               lambda: matches_bias(self.bias, program))
        if not hits:
            return
        multiplier = max(hit["weight_multiplier"] for hit in hits)
        candidate["weight"] *= multiplier
        candidate["derivation"]["library_bias"] = {
            "multiplier": multiplier,
            "abstractions": [hit["id"] for hit in hits],
            "sites": sum(hit["sites"] for hit in hits)}
        self.reweighted.append({"candidate": candidate["id"],
                                "multiplier": multiplier,
                                "abstractions": [hit["id"] for hit in hits]})

    def refresh(self, *, draft_count, memory=None):
        self._abstraction_drafts(max(1, draft_count // 2))
        self._library_drafts(min(self.library_calls, max(1, draft_count)), memory)
        features = self.features(memory)
        guessed = guess_relations(features, holdout=self.holdout)["candidates"]
        known = {c["id"] for c in self.candidates}
        added = 0
        for candidate in guessed:
            if added >= draft_count:
                break
            terms = candidate["terms"]
            residual = relation_program(features, terms)
            identity = digest({"schema": SCHEMA, "residual": residual})[:16]
            if identity in known:
                continue
            known.add(identity)
            self.candidates.append(
                {"id": identity, "terms": deepcopy(terms),
                 "residual": deepcopy(residual), "weight": 1, "attempts": 0,
                 "state": "pending", "spent_lines": 0,
                 "derivation": {"source": "guess_relations over make_features",
                                "feature_count": len(features),
                                "arity": len(terms),
                                "seeds_extended_by_memory": memory is not None}})
            self._apply_bias(self.candidates[-1], residual)
            added += 1
        return features

    def live(self):
        return [c for c in self.candidates if c["state"] in ("pending", "suspended")]

    def _work(self, candidate, features):
        """The computation this candidate stands for, whatever kind it is.

        An existing routine that cannot handle a program the widened search
        produced is recorded as unsupported. That is a different outcome from a
        relation being disproved and from a budget running out, and collapsing
        the three would hide which of them stopped the search.
        """
        try:
            return self._dispatch(candidate, features)
        except Exception as exc:                      # noqa: BLE001 - reported, not hidden
            return {"kind": candidate.get("kind", "relation"), "value": None,
                    "unsupported": f"{type(exc).__name__}: {exc}"[:200]}

    def _dispatch(self, candidate, features):
        kind = candidate.get("kind", "relation")
        if kind == "relation":
            # The existing store refuses a relation whose canonical key is zero:
            # it certifies but says nothing, and the certifier is not built to be
            # asked about it. Ask first rather than crash inside the proof.
            if canonical_relation(features, candidate["terms"]) == "zero":
                return {"kind": kind, "value": None, "empty": True}
            return {"kind": kind,
                    "value": self._certify(features, candidate["terms"],
                                           representation=f"relation:{candidate['id']}")}
        if kind == "library_call":
            # The boundary: the call is expanded to an ordinary program before
            # anything else sees it, so the feature closure, the guesser and the
            # certifier are handed exactly what they were always handed, with
            # the same types, premises and domain.
            program = self.jobs.timed(
                "expansion", lambda: expand(candidate["call"], self.definitions))
            validate(program)
            pool = [program] + [p for p in self.seeds + self.extra_seeds
                                if key(p) != key(program)]
            built = self._features_of(pool[:8],
                                      representation=f"library_call:{candidate['id']}")
            for guess in guess_relations(built, holdout=self.holdout)["candidates"]:
                terms = guess["terms"]
                if canonical_relation(built, terms) == "zero":
                    continue
                certificate = self._certify(
                    built, terms, representation=f"library_call:{candidate['id']}")
                if isinstance(certificate, dict) and "proof_attempt" not in certificate:
                    return {"kind": kind, "value": {
                        "certificate": certificate, "terms": deepcopy(terms),
                        "residual": relation_program(built, terms),
                        "features": built, "program": program}}
            return {"kind": kind, "value": None, "program": program}
        if kind == "abstraction":
            signature = self._signature(candidate["alpha"])
            record = correspondence(
                signature, candidate["morphisms"], self.witnesses, degree_x=0,
                span_degree=self.span_degree,
                span_derivatives=self.span_derivatives,
                abstract_domain="enumerated abstraction",
                source_type="tuple of holonomic programs", checks=1)
            return {"kind": kind, "value": record, "signature": signature}
        if kind == "operation_acquired":
            return {"kind": kind, "value": candidate["operation"]}
        if kind == "conservation":
            return {"kind": kind,
                    "value": conserved_quantities(
                        candidate["operation"], degree=self.conservation_degree,
                        signature=candidate.get("signature"))}
        if kind == "composition":
            composed = compose_operations(candidate["outer"], candidate["inner"])
            law = composition_law(candidate["inner"], composed)
            return {"kind": kind, "value": composed, "law": law}
        if kind == "invariance":
            operation = candidate["operation"]
            program = candidate["observable"]
            moved = dict({name: operation["body"][index] for index, name
                          in enumerate(operation["coordinate_names"])},
                         **{name: slot(name)
                            for name in operation["parameter_names"]})
            return {"kind": kind,
                    "value": prove_identity(fill(program, moved), program)}
        return {"kind": kind, "value": None}

    def _settle(self, candidate, produced, driver, features):
        """Did the computation give something, and what does it become?"""
        kind, value = produced["kind"], produced["value"]
        if produced.get("unsupported"):
            return {"outcome": "unsupported", "reason": produced["unsupported"]}
        if kind == "relation":
            if produced.get("empty"):
                return {"outcome": "disproved",
                        "reason": "the relation is structurally empty"}
            certificate = value.get("proof") if isinstance(value, dict) else None
            if certificate is None or "proof_attempt" in value:
                return {"outcome": "disproved"}
            return {"outcome": "proved", "certificate": certificate, "wrapped": value}
        if kind == "library_call":
            if value is None:
                return {"outcome": "disproved",
                        "reason": "the expanded call entered no certified relation"}
            candidate["residual"] = value["residual"]
            candidate["terms"] = value["terms"]
            candidate["features"] = value["features"]
            candidate["expanded"] = value["program"]
            return {"outcome": "proved", "certificate": value["certificate"]["proof"],
                    "wrapped": value["certificate"]}
        if kind == "abstraction":
            if not value or not value.get("supported_morphisms"):
                return {"outcome": "disproved",
                        "reason": "no operation descended to this abstraction"}
            signature = produced["signature"]
            witness = self.witnesses[0]
            concrete = {name: fill(signature["alpha"][index], witness)
                        for index, name in enumerate(signature["coordinate_names"])}
            concrete.update({name: witness[name] for name in self.parameter_names
                             if name in witness})
            self._register({"kind": "abstraction", "record": value,
                            "signature": signature, "coordinates": concrete,
                            "from_candidate": candidate["id"]})
            return {"outcome": "acquired", "detail":
                    f'{len(value["supported_morphisms"])} operations descended'}
        if kind == "operation_acquired":
            self._register({"kind": "operation", "operation": value,
                            "morphism": candidate.get("morphism"),
                            "abstraction": candidate.get("abstraction"),
                            "signature": candidate.get("signature"),
                            "argument_correspondence":
                                candidate.get("argument_correspondence"),
                            "proof_reference": [p.get("residual")
                                                for p in value.get("proofs", [])],
                            "coordinates": candidate.get("coordinates", {}),
                            "from_candidate": candidate["id"]})
            detail = "operation is callable"
            if is_identity_operation(value):
                detail += "; it moves nothing on the abstract side"
            return {"outcome": "acquired", "detail": detail}
        if kind == "conservation":
            return self._settle_conservation(candidate, value)
        if kind == "composition":
            if value is None:
                return {"outcome": "disproved"}
            law = produced.get("law") or {}
            self._register({"kind": "operation", "operation": value,
                            "morphism": "composed",
                            "abstraction": candidate.get("abstraction"),
                            "signature": candidate.get("signature"),
                            "coordinates": candidate.get("coordinates", {}),
                            "composed_of": value.get("composed_of"),
                            "self_composition": candidate.get("self_composition"),
                            "composition_law": law,
                            "proof_reference": {"inherited": True,
                                                "rule": value["inherited_proofs"]["rule"]},
                            "from_candidate": candidate["id"]})
            detail = "composition is callable, correctness inherited"
            if law.get("proved"):
                detail += (f"; composition law proved at parameter {law['parameter']}"
                           + ("" if not law.get("parameter_free_base")
                              else " (the base ignores its parameter, so this says nothing)"))
            else:
                detail += f"; no composition law found ({law.get('searched', 0)} tried)"
            return {"outcome": "acquired", "detail": detail}
        if kind == "invariance":
            if not value or not value.get("proved"):
                return {"outcome": "disproved",
                        "reason": (value or {}).get("reason", "not invariant")}
            parent = self.acquisition(candidate.get("parent"))
            if parent is not None:
                parent.setdefault("also_invariant_under", []).append(
                    {"operation": candidate.get("against"), "residual": "0"})
            return {"outcome": "acquired",
                    "detail": f'{candidate.get("expression")} is also left alone by '
                              f'{candidate.get("against")}'}
        return {"outcome": "disproved", "reason": f"unknown candidate kind {kind!r}"}

    def _settle_conservation(self, candidate, value):
        """Sort what the operation preserves by what it is on the image of alpha."""
        if not value or not value.get("quantities"):
            return {"outcome": "disproved",
                    "reason": value.get("reason") if value else "nothing found"}
        abstraction = self.acquisition(candidate.get("abstraction"))
        signature = candidate.get("signature") or {}
        names = signature.get("coordinate_names")
        registered, details = 0, []
        for entry in value["quantities"]:
            common = {"expression": entry["expression"], "program": entry["program"],
                      "coordinate_names": names,
                      "parameter_names": signature.get("parameter_names"),
                      "on_image": entry.get("on_image"),
                      "class": entry["class"],
                      "signature": signature,
                      "abstraction": candidate.get("abstraction"),
                      "coordinates": candidate.get("coordinates", {}),
                      "from_operation": candidate.get("parent"),
                      "proof_reference": entry.get("invariance", {}).get("residual"),
                      "from_candidate": candidate["id"]}
            if entry["class"] == "domain_relation":
                if abstraction is not None:
                    if record_image_condition(abstraction["record"], entry):
                        self._carry_image_conditions(abstraction)
                self._register(dict(common, kind="domain_condition"))
                details.append(f'{entry["expression"]} = 0 on the image (domain relation)')
            elif entry["class"] == "constant":
                self._register(dict(common, kind="constant_observation"))
                details.append(f'{entry["expression"]} = {entry["on_image"]} on the '
                               f'image (constant)')
            else:
                self._register(dict(common, kind="observable"))
                details.append(f'{entry["expression"]} varies on the image')
            registered += 1
        if not registered:
            return {"outcome": "disproved", "reason": value["reason"]}
        return {"outcome": "acquired", "detail": "; ".join(details)}

    def _carry_image_conditions(self, abstraction):
        """Give the operations on this object the relations just found on it.

        An operation was handed its domain when it was acquired, before anything
        was known about what the image satisfies. Leaving the copy behind would
        mean the operation states a domain the abstract object no longer has.
        """
        conditions = deepcopy(abstraction["record"]["image_conditions"])
        for entry in self.acquisitions:
            if entry["kind"] != "operation":
                continue
            if entry.get("abstraction") != abstraction["id"]:
                continue
            entry["operation"].setdefault("domain", {})["image_conditions"] =                 deepcopy(conditions)
        return conditions

    # ---- one update search -------------------------------------------------

    def sweep(self, driver, *, allowance, draft_count=4):
        if type(allowance) is not int or allowance < 1:
            raise ValueError("a sweep allowance must be a positive exact integer")
        context = driver.context()
        features = self.refresh(draft_count=draft_count, memory=driver.memory)
        live = self.live()
        undrafted = self.undrafted()
        record = {"schema": SCHEMA, "sweep": self._sweeps, "allowance": allowance,
                  "controller": context["controller"].sha256,
                  "feature_count": len(features),
                  "stored_task_ids": [t["id"] for t in context["tasks"]],
                  "attempted": [], "accepted": None, "spent_lines": 0,
                  "undrafted_abstractions": len(undrafted),
                  "enumerated_abstractions": len(self._enumerated),
                  "candidates_exhausted": not live and not undrafted,
                  "declared_bounds": list(self.declared_bounds),
                  "jobs": self.jobs.report(),
                  "library": {"definitions": len(self.library),
                              "reweighted": len(self.reweighted),
                              "effect": self.bias["effect"],
                              "not_done": self.bias["not_done"]},
                  "interrupt_scope": ("the allowance counts executed Python lines; "
                                      "work inside a native extension is not "
                                      "interrupted by it and is only charged when "
                                      "control returns"),
                  "scope": SCOPE}
        self._sweeps += 1
        if not live:
            return record

        macro = [c for c in live if c.get("kind") == "library_call"]
        plain = [c for c in live if c.get("kind") != "library_call"]
        macro_allowance = int(allowance * self.library_share) if macro else 0
        plain_allowance = allowance - macro_allowance if plain else 0
        if not plain:
            macro_allowance = allowance
        budgets = {"library_call": macro_allowance, "other": plain_allowance,
                   "share": self.library_share}
        record["allowance_split"] = budgets
        weights = {"library_call": sum(c["weight"] for c in macro) or 1,
                   "other": sum(c["weight"] for c in plain) or 1}
        proved = None
        for candidate in sorted(live, key=lambda c: (-c["weight"], c["id"])):
            group = ("library_call" if candidate.get("kind") == "library_call"
                     else "other")
            share = max(1, budgets[group] * candidate["weight"] // weights[group])
            outcome = run_within(share, lambda: self._work(candidate, features))
            candidate["attempts"] += 1
            candidate["spent_lines"] += outcome["cost"]["used"]
            record["spent_lines"] += outcome["cost"]["used"]
            entry = {"id": candidate["id"], "kind": candidate.get("kind", "relation"),
                     "allowance": share, "used": outcome["cost"]["used"],
                     "attempts": candidate["attempts"],
                     "derivation": candidate["derivation"]}
            if not outcome["completed"]:
                # Slow is not wrong. Raise the weight so the next sweep gives it
                # a larger share rather than thinning it as new drafts arrive.
                candidate["state"] = "suspended"
                candidate["weight"] *= 2
                entry["outcome"] = "interrupted"
                record["attempted"].append(entry)
                continue
            settled = self._settle(candidate, outcome["value"], driver, features)
            entry["outcome"] = settled["outcome"]
            if settled.get("detail"):
                entry["detail"] = settled["detail"]
            record["attempted"].append(entry)
            if settled["outcome"] in ("disproved", "unsupported"):
                candidate["state"] = "rejected"
                candidate["reason"] = settled.get("reason", "did not certify")
                entry["reason"] = candidate["reason"]
                continue
            if settled["outcome"] == "acquired":
                # Acquisitions that are not relations do not go to the gate; they
                # change what can be proposed, not what the controller can reduce.
                candidate["state"] = "accepted"
                continue
            proved = (candidate, settled["certificate"], settled["wrapped"])
            break

        # A candidate can fail to finish two ways: its allowance ran out, or its
        # turn never came because a cheaper one settled the sweep first. Both
        # leave it unresolved, so the same revisit rule applies and it comes back
        # with a larger share. Without this a cheap kind that always succeeds
        # keeps the queue to itself for ever.
        attempted = {entry["id"] for entry in record["attempted"]}
        for candidate in live:
            if candidate["id"] not in attempted and candidate["state"] == "pending":
                candidate["weight"] *= 2
                candidate["state"] = "suspended"

        if proved is None:
            return record
        candidate, certificate, wrapped = proved
        task = {"id": f"task-{candidate['id']}",
                "program": deepcopy(candidate["residual"]), "target": deepcopy(ZERO),
                "derivation": deepcopy(candidate["derivation"])}
        shape = digest(canonical_literals(task["program"]))
        earlier = self.presentations.get(shape)
        if earlier is not None:
            self.repeat_tasks.append({"task": task["id"], "same_shape_as": earlier,
                                      "route": candidate.get("kind", "relation")})
        attempt = driver.attempt(task, [certificate], proposal_reductions=0)
        candidate["state"] = "accepted" if attempt["accepted"] else "rejected"
        if not attempt["accepted"]:
            candidate["reason"] = "refused by the acceptance gate"
        if attempt["accepted"] and earlier is None:
            self.presentations[shape] = task["id"]
        record["accepted"] = attempt if attempt["accepted"] else None
        record["repeat_tasks"] = list(self.repeat_tasks)
        record["gate"] = {"accepted": attempt["accepted"],
                          "conditions": attempt["acceptance"]["conditions"],
                          "task_id": task["id"]}
        if attempt["accepted"]:
            # Without this the loop keeps one feature set for ever: it acquires a
            # rule, then proposes out of the same six features and starves. The
            # proved record becomes a construction, and `extend_seeds` puts that
            # construction back among the seeds, so the next sweep generates from
            # a wider set than this one did.
            used = candidate.get("features", features)
            proved_record = {"features": used, "certificate": wrapped,
                             "multi_origin": False,
                             "canonical": canonical_relation(used,
                                                             candidate["terms"])}
            self.records.append(proved_record)
            driver.adopt_memory(build_memory(
                self.records, None, list(self.seeds),
                {"acquired_by": SCHEMA, "sweeps": self._sweeps}))
            record["memory_constructions"] = len(driver.constructions())
        return record

    def run(self, driver, *, sweeps, allowance, growth=2, draft_count=4):
        """Repeat sweeps, doubling the allowance so suspended candidates return."""
        if type(sweeps) is not int or sweeps < 1:
            raise ValueError("a sweep count must be a positive exact integer")
        records, current = [], allowance
        for _ in range(sweeps):
            records.append(self.sweep(driver, allowance=current,
                                      draft_count=draft_count))
            current *= growth
        return records
