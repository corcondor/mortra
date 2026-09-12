"""A session domain that acquires observation representations of the fold action.

The acquisition is a pair: an observation map `Phi` and, for every letter `g`,
a matrix `B_g` with

    Phi(T_g(x)) = B_g Phi(x)

checked as a polynomial identity by the prover that already existed
(`finite_generator_problem_dna.discover_action_observable_basis`). What is stored
is the basis and those matrices, and what the downstream computation reads back
is the same basis and the same matrices.

The cycle:

    search       take the next candidates off the stated enumeration; ask the
                 closure prover for `Phi` and the `B_g`; where the premises fit,
                 additionally ask the existing word law whether the space is
                 affine in the repeats of a block the fold search chose. A law
                 that does not hold never demotes a closure that does.
    follow_ups   load an acquisition back from its record and compute three
                 different things with it -- a named word, a block power, and the
                 total over every word of a length -- each checked afterwards
                 against the original kinematics, never before.

The one-step correspondence `encode(apply_fold_generator(x, g)) = M_g encode(x)`
is verified once per session over every reachable frame with a symbolic centre,
and that verdict is stored as the premise the rest rests on.
"""
from __future__ import annotations

from copy import deepcopy

import sympy as sp

from math_os_prototype import fold_observable_system as observables
from math_os_prototype import representation_benchmarks as benchmarks
from math_os_prototype import representation_evaluation as evaluation
from math_os_prototype.representation_progress import digest
from math_os_prototype.rigid_fold_problem_discovery import (
    build_square_fold_chain, search_collision_free_fold_chain)

NAME = "fold_observable"
SCHEMA = "mortra.fold-observable-domain.v1"


class FoldObservableDomain:
    def __init__(self, config, *, cursor=0, acquisitions=(), blocks=(), checks=(),
                 step_verification=None):
        self.config = config
        self.cursor = int(cursor)
        self.acquisitions = [dict(a) for a in acquisitions]
        self.blocks = list(blocks)
        self.checks = [dict(c) for c in checks]
        self.step_verification = deepcopy(step_verification)
        self.premise_cost = None
        self._system = None

    @property
    def system(self):
        if self._system is None:
            self._system = observables.fold_system()
            if self.step_verification is None:
                depth = int(self.config.get("frame_depth", 4))
                measured = evaluation.measure(
                    lambda: {"value": observables.verify_step(
                        self._system, depth=depth)})
                self.step_verification = measured["value"]
                # the premise is paid once and licenses every representation
                # acquired in this session, so it is recorded apart from the
                # per-representation cost rather than charged to each of them
                self.premise_cost = {
                    "shared_premise_time": measured["wall_time"],
                    "shared_premise_primitive_calls": measured["primitive_calls"],
                    "shared_premise_fold_step_calls": measured["fold_step_calls"],
                    "paid": "once per session, for every representation below"}
        return self._system

    @staticmethod
    def grammar():
        from math_os_prototype.holonomic_route_discovery import validate
        return validate

    # -- what the enumeration offers ---------------------------------------

    def _enumeration(self):
        return observables.candidate_observables(
            degree=int(self.config.get("observable_degree", 2)),
            max_terms=int(self.config.get("observable_terms", 1)),
            coefficients=tuple(self.config.get("observable_coefficients", (1,))))

    def _next_blocks(self, index):
        low = int(self.config.get("fold_min", 3))
        span = int(self.config.get("fold_counts_per_cycle", 2))
        found = []
        for count in range(low + index * span, low + (index + 1) * span):
            result = search_collision_free_fold_chain(
                count, beam_width=int(self.config.get("fold_beam_width", 32)),
                seed=int(self.config.get("fold_seed", 20260904)))
            word = result.chain.word
            if word and word not in self.blocks:
                self.blocks.append(word)
                found.append(word)
        return found

    # -- acquisition --------------------------------------------------------

    def search(self, config, index):
        verification = self.step_verification or {}
        if not verification.get("exact", False):
            self.system  # forces the verification
            verification = self.step_verification
        records = []
        offered = self._enumeration()
        taken = offered[self.cursor:self.cursor
                        + int(config.get("observables_per_cycle", 6))]
        self.cursor += len(taken)

        acquired, refused = [], []
        cap = int(config.get("observable_dimension_cap", 120))
        for candidate in taken:
            measured = evaluation.measure(
                lambda: {"value": observables.acquire_closure(
                    self.system, candidate, maximum_dimension=cap)})
            found = measured["value"]
            if not found["closed"]:
                refused.append({"observable": found["observable"],
                                "reason": found["reason"]})
                continue
            record = {
                "observable": found["observable"],
                "dimension": found["dimension"],
                "basis": found["basis"],
                "action_matrices": found["action_matrices"],
                "identity_residuals_all_zero": found["identity_residuals_all_zero"],
                "closure_scope": found["scope"],
                "minimality": ("smallest generator-invariant linear space "
                               "containing this observable; not a claim of "
                               "minimality over all representations"),
                "step_premise": {"exact": verification.get("exact"),
                                 "frames_checked": verification.get("frames_checked"),
                                 "identities_checked": verification.get(
                                     "identities_checked"),
                                 "scope": verification.get("scope")},
                "acquisition_cost": {
                    "acquisition_time": measured["wall_time"],
                    "acquisition_primitive_calls": measured["primitive_calls"],
                    "acquisition_proof_calls": measured["proof_calls"],
                    "acquisition_peak_memory": measured["peak_memory"],
                    "acquisition_search_nodes": self.cursor,
                    "acquisition_search_note": ("candidates drawn from the "
                                                "stated enumeration so far"),
                    "shared_premise": self.premise_cost or {
                        "paid": ("in an earlier session; this run restored the "
                                 "verdict rather than re-checking it")}},
                "repeat_laws": []}
            if config.get("evaluate_representations", True):
                record["evaluation"] = self.evaluate_representation(config, record)
            self.acquisitions.append(record)
            acquired.append(record)

        records.append({
            "sweep": index, "route": "observation representation",
            "asked_for": [str(c) for c in taken],
            "attempted": [a["observable"] for a in acquired],
            "attempted_kinds": ["closure"] * len(acquired),
            "accepted": acquired[-1]["observable"] if acquired else None,
            "candidates_exhausted": not taken,
            "undrafted": len(offered) - self.cursor,
            "spent_lines": 0, "refused": refused,
            "dimensions": {a["observable"]: a["dimension"] for a in acquired}})

        # an optional extra: a law about repeating one block, where it holds.
        # Its failure is recorded on the acquisition and changes nothing else.
        blocks = self._next_blocks(index)
        proved = []
        for record in acquired:
            usable = observables.closure_from_record(record)
            for word in blocks:
                law = observables.prove_repeat_law(
                    usable, word, cap=int(config.get("block_order_cap", 32)))
                entry = {"block": word, "block_order": law.get("block_order"),
                         "proved": bool(law.get("proved")),
                         "reason": law.get("reason"), "scope": law.get("scope"),
                         "feature_states": law.get("feature_states"),
                         "base_case_exact": law.get("base_case_exact"),
                         "generator_steps": law.get("generator_steps"),
                         "all_steps_exact": law.get("all_steps_exact"),
                         "fit_used_as_proof": law.get("fit_used_as_proof"),
                         "formulas": law.get("formulas")}
                # the other prover, where its premises fit. A block the affine
                # law refuses can still have an exact recurrence.
                entry["recurrence"] = observables.prove_repeat_recurrence(
                    usable, word)
                record["repeat_laws"].append(entry)
                if entry["proved"]:
                    proved.append((record["observable"], word))
        records.append({
            "sweep": index, "route": "repeat law, where the premises fit",
            "asked_for": blocks,
            "attempted": [f"{o} on {w}" for o, w in proved],
            "attempted_kinds": ["repeat_law"] * len(proved),
            "accepted": f"{proved[-1][0]} on {proved[-1][1]}" if proved else None,
            "candidates_exhausted": not blocks,
            "undrafted": 0, "spent_lines": 0,
            "note": ("a repeat law that does not hold leaves its closure "
                     "untouched; not every candidate is affine in length")})
        return records

    def evaluate_representation(self, config, record):
        """How much computation this representation actually removed, and where.

        Two tasks against the routes it replaces. Each task is run once per rung
        of the ladder -- naive, memoised, an existing mathematical route where
        one exists, a standard search improvement where the task is a search,
        and the representation -- so the saving is split between the four causes
        by measurement instead of being credited wholesale to the
        representation.

        The counting task is only run with the representation if a certificate
        admits it. The collision-constrained variant of the SAME task is
        certified too, and is expected to be refused: self-intersection is a
        property of the word, not of the state it ends in, so no observation of
        the state can decide it. The refusal is recorded rather than worked
        around.
        """
        from math_os_prototype import fold_tasks
        from math_os_prototype import representation_certificate as certificates

        cost = dict(record["acquisition_cost"])
        block = str(config.get("evaluation_block", "GCC"))
        repeats = int(config.get("evaluation_repeats", 16))
        length = int(config.get("evaluation_search_length", 6))
        depth = int(config.get("certificate_depth", 5))
        usable = {"observable": record["observable"], "basis": record["basis"],
                  "action_matrices": record["action_matrices"],
                  "identity_residuals_all_zero":
                      record["identity_residuals_all_zero"],
                  "closure_scope": record["closure_scope"]}

        open_task = fold_tasks.displacement_task(axis=0)
        constrained = fold_tasks.displacement_task(axis=0, collision_free=True)
        premise = record.get("step_premise")
        open_certificate = certificates.certify(usable, open_task, depth=depth,
                                                premise=premise)
        constrained_certificate = certificates.certify(
            usable, constrained, depth=depth, premise=premise)

        return {
            "repeat": benchmarks.fold_repeat_comparison(
                f"{record['observable']}: {block} x {repeats}", usable, cost,
                block=block, repeats=repeats, certificate=open_certificate),
            "search": benchmarks.fold_search_comparison(
                f"{record['observable']}: every word of length {length}",
                usable, cost, task=open_task, length=length,
                certificate=open_certificate),
            "search_with_legality_constraint":
                benchmarks.fold_search_comparison(
                    f"{record['observable']}: collision-free words of length "
                    f"{length}", usable, cost, task=constrained, length=length,
                    certificate=constrained_certificate),
            "certificates": {"unconstrained": open_certificate,
                             "collision_free": constrained_certificate},
            "scope": ("two tasks and one constrained variant, not a claim about "
                      "every task; what is recorded is what these runs cost and "
                      "which of them the certificate allowed at all")}

    def corpus(self):
        return []

    def adopt(self, library, weight=2):
        return self

    # -- using an acquisition, read back from its record --------------------

    def follow_ups(self, config, corpus):
        """Three different computations, each from the stored basis and matrices.

        The predicted value is computed first, from the acquisition alone. Only
        afterwards is the kinematics run, and it is run as an independent check.
        """
        length = int(config.get("sum_length", 3))
        repeats = int(config.get("prediction_repeats", 4))
        rows = []
        for record in self.acquisitions:
            usable = observables.closure_from_record(record)   # read the record
            for law in record["repeat_laws"]:
                block = law["block"]

                # (a) one named word, letters multiplied in word order
                word = block + block[::-1]
                if not any(c["word"] == word and c["mode"] == "word"
                           for c in self.checks):
                    predicted = observables.apply_word(usable, word)
                    chain = build_square_fold_chain(word)
                    seen = observables.observed(usable, word)
                    rows.append({"observable": record["observable"],
                                 "mode": "word", "word": word,
                                 "predicted": str(predicted), "observed": str(seen),
                                 "agree": predicted == seen,
                                 "panels": len(chain.panels),
                                 "intersecting_pairs":
                                     len(chain.proper_intersection_pairs)})

                # (b1) the proved recurrence, unrolled from its own coefficients
                rec = law.get("recurrence") or {}
                if rec.get("proved"):
                    for count in range(1, repeats + 1):
                        repeated = block * count
                        key = f"{repeated}#rec"
                        if any(c["word"] == key for c in self.checks):
                            continue
                        predicted = observables.recurrence_values(
                            rec, usable, block, count)
                        seen = observables.observed(usable, repeated)
                        rows.append({"observable": record["observable"],
                                     "mode": "recurrence", "word": key,
                                     "repeats": count, "order": rec["order"],
                                     "predicted": str(predicted),
                                     "observed": str(seen),
                                     "agree": predicted == seen})

                # (b) one block repeated, as a matrix power
                for count in range(1, repeats + 1):
                    repeated = block * count
                    if any(c["word"] == repeated and c["mode"] == "block_power"
                           for c in self.checks):
                        continue
                    predicted = observables.apply_block_power(usable, block, count)
                    chain = build_square_fold_chain(repeated)
                    seen = observables.observed(usable, repeated)
                    rows.append({"observable": record["observable"],
                                 "mode": "block_power", "word": repeated,
                                 "repeats": count,
                                 "predicted": str(predicted), "observed": str(seen),
                                 "agree": predicted == seen,
                                 "panels": len(chain.panels),
                                 "intersecting_pairs":
                                     len(chain.proper_intersection_pairs)})
                break   # one block is enough to exercise all three modes

            # (c) the total over EVERY word of a length, as a matrix-sum power
            key = f"all-words-{length}"
            if not any(c["word"] == key for c in self.checks):
                predicted = observables.sum_over_all_words(usable, length)
                seen = observables.brute_force_sum(usable, length)
                rows.append({"observable": record["observable"],
                             "mode": "sum_over_all_words", "word": key,
                             "length": length,
                             "predicted": str(predicted), "observed": str(seen),
                             "agree": predicted == seen,
                             "note": ("every word of this length, collision-free "
                                      "or not; not a sum over collision-free words")})
        self.checks.extend(rows)
        return [{"id": digest(row)[:16], "call": None, "definition": None,
                 "word": row["word"], "call_bits": None, "expanded_bits": None,
                 "expands_to": None, "prediction": row} for row in rows]

    def pending(self):
        return list(range(self.cursor, len(self._enumeration())))

    # -- persistence --------------------------------------------------------

    def state(self):
        payload = {"schema": SCHEMA, "cursor": self.cursor,
                   "step_verification": deepcopy(self.step_verification),
                   "acquisitions": deepcopy(self.acquisitions),
                   "blocks": list(self.blocks),
                   "checks": deepcopy(self.checks)}
        payload["sha256"] = digest(payload)
        return payload

    @classmethod
    def restore(cls, config, payload):
        stored = dict(payload)
        if stored.pop("sha256", None) != digest(stored):
            raise ValueError("fold observable state digest does not match")
        return cls(config, cursor=payload["cursor"],
                   acquisitions=payload["acquisitions"],
                   blocks=payload["blocks"], checks=payload["checks"],
                   step_verification=payload.get("step_verification"))
