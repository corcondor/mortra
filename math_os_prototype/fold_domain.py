"""The fold side of an acquisition session: generate, learn, generate again.

Every step is an existing function.

    candidates      `rigid_fold_problem_discovery.search_collision_free_fold_chain`
    kinematics      `rigid_fold_problem_discovery.build_square_fold_chain`
    term language   `fold_library_bridge.validate_fold` / `program` / `word`
    learning        `library_compression.learn_library` under `grammar(...)`
    calls           `library_compression.call_candidates`
    expansion       `library_compression.expand`

What is new here is only the wiring: which fold counts the generator is asked
for, that its output becomes the corpus, and that a learned call is expanded back
into a fold term and run on the same kinematics so that it becomes a candidate
the next cycle can learn from.

Nothing selects a candidate or a definition by hand. The fold counts come from a
schedule in the configuration, `call_candidates` offers every argument
combination its pool allows in a fixed order, and the objective decides which
definitions survive. A construction that fails to run is dropped with its reason
recorded, never repaired.

The cost model is untouched. An abstraction that only bundles the term spine is
kept and printed as it is.
"""
from __future__ import annotations

from copy import deepcopy

from math_os_prototype.fold_library_bridge import (
    length, program, run, validate_fold, word)
from math_os_prototype.library_compression import (
    call_candidates, cost, definition_table, expand_for_execution, grammar,
    search_bias)
from math_os_prototype.rigid_fold_problem_discovery import (
    search_collision_free_fold_chain)
from math_os_prototype.representation_progress import digest

NAME = "fold"
SCHEMA = "mortra.fold-domain.v1"


def _entry(text, source, index):
    """One construction, with what the existing kinematics says about it."""
    chain = run(program(text))
    return {"id": f"{source}-{index}-{len(text)}",
            "word": text,
            "program": program(text),
            "source": source,
            "folds": len(text),
            "panels": len(chain.panels),
            "intersecting_pairs": len(chain.proper_intersection_pairs),
            "doubled_corners": [list(map(list, panel.doubled_corners))
                                for panel in chain.panels],
            "proved": True}


class FoldDomain:
    """Search state for the fold side, carried across cycles like any other."""

    def __init__(self, config, *, constructions=(), library=(), offered=(),
                 searched_counts=()):
        self.config = config
        self.constructions = [dict(c) for c in constructions]
        self.library = [dict(e) for e in library]
        self.definitions = definition_table(
            {entry["index"]: entry["template"] for entry in self.library})
        self.offered = list(offered)
        self.searched_counts = list(searched_counts)
        # candidates that reached something the corpus already held: another
        # route to the same construction, kept apart from new constructions
        self.revisits = []

    # -- the grammar this domain hands to the learner ---------------------

    @staticmethod
    def grammar():
        return validate_fold

    # -- generation --------------------------------------------------------

    def _schedule(self, index):
        """Which fold counts to ask the existing generator for, this cycle."""
        low = int(self.config.get("fold_min", 6))
        span = int(self.config.get("fold_counts_per_cycle", 5))
        start = low + index * span
        return list(range(start, start + span))

    def search(self, config, index):
        """Ask the existing generator, then run every learned call it can."""
        records = []
        beam = int(config.get("fold_beam_width", 64))
        seed = int(config.get("fold_seed", 20260904))
        found, rejected = [], []
        for count in self._schedule(index):
            if count in self.searched_counts:
                continue
            self.searched_counts.append(count)
            result = search_collision_free_fold_chain(
                count, beam_width=beam, seed=seed)
            text = result.chain.word
            if not text or any(c["word"] == text for c in self.constructions):
                continue
            found.append(text)
            self.constructions.append(
                _entry(text, "search_collision_free_fold_chain", len(self.constructions)))
        records.append({"sweep": index, "route": "existing fold generator",
                        "asked_for": self._schedule(index),
                        "attempted": found, "attempted_kinds": ["beam"] * len(found),
                        "accepted": found[-1] if found else None,
                        "candidates_exhausted": not found,
                        "undrafted": 0, "spent_lines": 0})

        # every call the library offers, expanded and run on the kinematics
        built, failed = [], []
        for call in self.offered:
            text = call.get("word")
            if not text or any(c["word"] == text for c in self.constructions):
                continue
            try:
                self.constructions.append(
                    _entry(text, f"call-{call['id']}", len(self.constructions)))
                built.append(text)
            except (ValueError, TypeError) as exc:
                failed.append({"call": call["id"], "reason": str(exc)[:80]})
        records.append({"sweep": index, "route": "learned calls, expanded and run",
                        "asked_for": [c["id"] for c in self.offered],
                        "attempted": built,
                        "attempted_kinds": ["library_call"] * len(built),
                        "accepted": built[-1] if built else None,
                        "candidates_exhausted": not built and bool(self.offered),
                        "undrafted": len(failed), "spent_lines": 0,
                        "failed": failed})
        self.offered = []
        return records

    # -- what the cycle learns from ---------------------------------------

    def corpus(self):
        """Every construction this session produced, and its proper prefixes.

        A beam reaches a long chain through its prefixes and each is a
        collision-free construction it actually held; a call's expansion is
        likewise a construction the kinematics ran. Each appears once.
        """
        corpus, seen = [], set()
        for entry in self.constructions:
            for cut in range(2, entry["folds"] + 1):
                piece = entry["word"][:cut]
                if piece in seen:
                    continue
                seen.add(piece)
                corpus.append({"id": f"c{len(corpus)}", "program": program(piece),
                               "source": entry["id"], "proved": True,
                               "word": piece})
        return corpus

    # -- calls of what was learned ----------------------------------------

    def follow_ups(self, config, corpus):
        """Offer calls, expand them, and keep the ones the kinematics accepts."""
        if not self.library:
            return []
        pool = [entry["program"] for entry in corpus]
        revisits = []
        with grammar(validate_fold):
            from math_os_prototype.holonomic_route_discovery import key

            def flatten(term):
                """The same fold word, written the one way the corpus writes it.

                An expansion splices whole terms into a body, so the same word
                comes back nested; a corpus entry is flat. Comparing the two as
                written makes every already-held word look new.
                """
                try:
                    return program(word(term))
                except (ValueError, TypeError):
                    return term

            offered = call_candidates(
                self.library, pool, limit=int(config.get("library_calls", 6)),
                exclude=[key(entry["program"]) for entry in corpus],
                table=self.definitions, normalise=flatten,
                scan=int(config.get("call_scan", 400)), revisits=revisits)
        self.revisits = [{"id": r["id"], "definition": r["definition"],
                          "reason": r["reason"]} for r in revisits]
        calls = []
        for call in offered:
            try:
                expansion = expand_for_execution(call["call"], self.definitions)
                text = word(expansion)
            except (ValueError, TypeError, KeyError) as exc:
                calls.append(dict(call, expands_to=None, word=None,
                                  reason=str(exc)[:80]))
                continue
            calls.append(dict(call, expands_to=expansion, word=text,
                              folds=length(expansion)))
        self.offered = [c for c in calls if c.get("word")]
        return calls

    # -- library, carried without rebuilding anything ---------------------

    def adopt(self, library, weight=2):
        self.library = [dict(entry) for entry in library]
        self.definitions = definition_table(
            {entry["index"]: entry["template"] for entry in self.library})
        search_bias({"library": [
            {"id": e["id"], "template": e["template"],
             "utility_bits": e.get("utility_bits", 1)} for e in self.library]},
            weight=weight)
        return self

    def pending(self):
        """Fold counts the schedule will reach but the generator has not."""
        upcoming = self._schedule(len(self.searched_counts) //
                                  max(1, int(self.config.get(
                                      "fold_counts_per_cycle", 5))))
        return [c for c in upcoming if c not in self.searched_counts]

    # -- persistence -------------------------------------------------------

    def state(self):
        payload = {"schema": SCHEMA,
                   "constructions": deepcopy(self.constructions),
                   "library": deepcopy(self.library),
                   "offered": deepcopy(self.offered),
                   "searched_counts": list(self.searched_counts),
                   "revisits": deepcopy(self.revisits)}
        payload["sha256"] = digest(payload)
        return payload

    @classmethod
    def restore(cls, config, payload):
        stored = dict(payload)
        if stored.pop("sha256", None) != digest(stored):
            raise ValueError("fold domain state digest does not match its contents")
        domain = cls(config, constructions=payload["constructions"],
                     library=payload["library"], offered=payload["offered"],
                     searched_counts=payload["searched_counts"])
        domain.revisits = list(payload.get("revisits", []))
        return domain
