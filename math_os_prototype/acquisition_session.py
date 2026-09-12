"""One start, many cycles: search, learn from the search, search with what was learned.

Everything this runs already existed. `Driver` accepts or refuses, `Proposer`
enumerates and proposes, `learn_library` abstracts, `definition_table` seals what
was abstracted, `call_candidates` offers calls of it and `expand` drives them
out. What did not exist is the thing that puts them in a loop without a person
between the steps, and that is all this module is.

Two facts made it necessary, and both were measured rather than assumed:

* `Driver.state()` saves the certificates, tasks, history, memory and spend --
  and **nothing of the proposer**. Restoring from it alone silently discards the
  learned library, the candidate queue, the enumeration cursor and the sweep
  counter, so a resumed session would start proposing from the beginning with no
  library. `proposer_state` / `restore_proposer` here are the missing half.

* A learned library has to reach the proposer *without* rebuilding it, because
  rebuilding is what loses the queue. `adopt_library` sets the three fields
  `Proposer.__init__` would have set and touches nothing else.

The objective function is not changed anywhere in this module. Cost is
`library_compression.cost` exactly as it stands.

Stopping is operational, never epistemic. Two caps are mandatory -- wall time and
traced lines -- and the barren-cycle and compression-floor conditions are
settings. A session that stops has stopped; `stop_reason` says which condition
fired, and `pending` carries what was never tried so the next start resumes it.
"""
from __future__ import annotations

import json
import time
from copy import deepcopy
from pathlib import Path

from math_os_prototype.library_compression import (
    call_candidates, cost, definition_table, expand_for_execution, grammar,
    learn_library, search_bias)
from math_os_prototype.holonomic_route_discovery import validate as _series_grammar
from math_os_prototype.holonomic_route_discovery import key
from math_os_prototype.powerplay_driver import Driver
from math_os_prototype.powerplay_proposer import Proposer
from math_os_prototype.representation_progress import digest

SCHEMA = "mortra.acquisition-session.v1"

#: what the caller may set, and what it means. Anything absent takes this value.
DEFAULTS = {
    # --- which search this session drives -----------------------------------
    "domain": "holonomic",             # "holonomic" | "fold" | "fold_observable"
    # --- the fold domain, when it is the one selected -----------------------
    "fold_min": 6,                     # smallest fold count asked of the generator
    "fold_counts_per_cycle": 5,
    "fold_beam_width": 64,
    "call_scan": 400,                  # expansions a cycle may examine per call set
    # --- the fold observable domain, when it is the one selected ------------
    "observable_degree": 2,            # how far the candidate enumeration goes
    "observables_per_cycle": 6,
    "observable_dimension_cap": 120,
    "block_order_cap": 32,
    "prediction_repeats": 5,
    "observable_terms": 1,             # 1 = monomials only; >1 enumerates sums
    "observable_coefficients": [1],
    "frame_depth": 4,
    "sum_length": 3,
    "fold_seed": 20260904,
    # --- the search, handed straight to Proposer / Driver -------------------
    "seeds": [],                       # programs; at least one
    "tasks": [],                       # driver tasks
    "certificates": [],                # driver certificates, already built
    "certify_pairs": [],               # [{"left": program, "right": program}] the
                                       # existing certifier is asked to certify
    "state_names": [],
    "parameter_names": [],
    "abstraction_witnesses": [],
    "degree_x": 1, "derivatives": 1, "product_degree": 1,
    "holdout": 16, "proof_backend": "closure",
    "conservation_degree": 2, "span_degree": 2, "span_derivatives": 0,
    "morphism_derivatives": 0,
    "library_weight": 2, "library_calls": 6, "library_share": 0.34,
    "share_jobs": False,
    "budget": 4, "criterion": "final_output",
    # --- one cycle ----------------------------------------------------------
    "sweeps_per_cycle": 4,
    "allowance": 15_000_000,
    "growth": 2,
    "draft_count": 3,
    # --- learning, with the objective left alone ----------------------------
    "learn_rounds": 3, "learn_pairs": 20000, "learn_limit": 6, "learn_keep": 8,
    # --- stopping: the first two are required, the rest are settings --------
    "max_seconds": 900,                # hard cap, wall clock
    "max_traced_lines": 400_000_000,   # hard cap, compute
    "max_cycles": 12,                  # hard cap, cycles
    "barren_cycles": 2,                # stop after this many with no acceptance
    "min_compression_bits": 1,         # a cycle learning less than this is barren
}

REQUIRED_CAPS = ("max_seconds", "max_traced_lines", "max_cycles")

STOP_NOTE = (
    "a stop is an operational condition, not a proof that nothing further can be "
    "found: `pending` lists what was enumerated and never drafted, and resuming "
    "continues from it"
)


def seed_certificates(pairs):
    """Certify the declared starting pairs with the certifier that already exists.

    A configuration file cannot hold a certificate, and inventing one would be a
    new claim. Declaring the pair and letting `certify_equal` decide is the same
    thing the loop does for everything else.
    """
    if not pairs:
        return []
    from math_os_prototype.holonomic_route_discovery import certify_equal

    built = []
    for pair in pairs:
        certificate = certify_equal(pair["left"], pair["right"])
        if not isinstance(certificate, dict) or "proof_attempt" in certificate:
            raise ValueError(f"the declared starting pair did not certify: {pair}")
        built.append(certificate)
    return built


def configure(payload):
    """Fill in the defaults and refuse a configuration with no cap."""
    config = dict(DEFAULTS)
    config.update({k: deepcopy(v) for k, v in dict(payload).items()})
    unknown = sorted(set(config) - set(DEFAULTS))
    if unknown:
        raise ValueError(f"unknown configuration keys: {unknown}")
    if not config["seeds"]:
        raise ValueError("a session needs at least one seed program")
    for cap in REQUIRED_CAPS:
        value = config[cap]
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise ValueError(f"{cap} must be a positive integer; a session may not "
                             "run without every cap set")
    return config


# ---- the half of the state that `Driver.state()` does not carry -----------

PROPOSER_CARRIED = ("candidates", "records", "acquisitions", "repeats",
                    "extra_seeds", "reweighted", "repeat_tasks", "presentations",
                    "declared_bounds", "witnesses", "library")


def proposer_state(proposer):
    """Everything a resumed proposer would otherwise lose.

    Checked against `Proposer.__init__`: the fields below are the ones assigned
    after configuration, plus the enumeration cursor. `definitions` and `bias`
    are derived from `library` and are rebuilt rather than stored.
    """
    payload = {"schema": SCHEMA + ".proposer",
               "sweeps": proposer._sweeps,
               "drafted": sorted(proposer._drafted),
               "enumerated_ids": [c["id"] for c in proposer._enumerated],
               "seeds": deepcopy(proposer.seeds)}
    for field in PROPOSER_CARRIED:
        payload[field] = deepcopy(getattr(proposer, field))
    payload["sha256"] = digest(payload)
    return payload


def restore_proposer(config, payload=None):
    """Build the proposer, then put back what `Driver.restore` cannot."""
    proposer = Proposer(
        config["seeds"],
        degree_x=config["degree_x"], derivatives=config["derivatives"],
        product_degree=config["product_degree"], holdout=config["holdout"],
        proof_backend=config["proof_backend"],
        state_names=config["state_names"],
        parameter_names=config["parameter_names"],
        abstraction_witnesses=config["abstraction_witnesses"],
        conservation_degree=config["conservation_degree"],
        span_degree=config["span_degree"],
        span_derivatives=config["span_derivatives"],
        morphism_derivatives=config["morphism_derivatives"],
        library=config.get("library", ()),
        library_weight=config["library_weight"],
        library_calls=config["library_calls"],
        library_share=config["library_share"],
        share_jobs=config["share_jobs"])
    if payload is None:
        return proposer
    stored = dict(payload)
    if stored.pop("sha256", None) != digest(stored):
        raise ValueError("proposer state digest does not match its contents")
    for field in PROPOSER_CARRIED:
        setattr(proposer, field, deepcopy(payload[field]))
    proposer._sweeps = payload["sweeps"]
    proposer._drafted = set(payload["drafted"])
    proposer.seeds = deepcopy(payload["seeds"])
    adopt_library(proposer, proposer.library, weight=config["library_weight"])
    missing = [i for i in payload["enumerated_ids"]
               if i not in {c["id"] for c in proposer._enumerated}]
    if missing:
        raise ValueError(f"{len(missing)} enumerated candidates no longer exist; "
                         "the configuration changed under a stored session")
    return proposer


def adopt_library(proposer, library, *, weight=2):
    """Hand a learned library to a *running* proposer.

    Exactly the three fields `Proposer.__init__` derives from `library`, and no
    other field, so the candidate queue, the enumeration cursor, the acquired
    records and the sweep counter all survive. Rebuilding the proposer instead is
    what loses them.
    """
    proposer.library = [dict(entry) for entry in library]
    proposer.definitions = definition_table(
        {entry["index"]: entry["template"] for entry in proposer.library})
    proposer.bias = search_bias({"library": [
        {"id": entry["id"], "template": entry["template"],
         "utility_bits": entry.get("utility_bits", 1)}
        for entry in proposer.library]}, weight=weight)
    proposer.jobs.versions["definitions"] = proposer.definitions["sha256"]
    return proposer


# ---- the corpus a cycle learns from --------------------------------------

def corpus_from_history(driver, proposer):
    """What this run itself produced, each program once.

    Not a replay and not the seeds: the feature programs of every relation the
    run proved, and the programs of the tasks it accepted. A program the run
    never touched is not here.
    """
    corpus, seen = [], set()

    def offer(program, source, proved):
        encoded = json.dumps(program, sort_keys=True, separators=(",", ":"))
        if encoded in seen:
            return
        seen.add(encoded)
        corpus.append({"id": f"c{len(corpus)}", "program": deepcopy(program),
                       "source": source, "proved": proved})

    for index, record in enumerate(proposer.records):
        for feature in record.get("features", []):
            if "program" in feature:
                offer(feature["program"], f"proved-relation-{index}", True)
    for task in driver.tasks:
        for side in ("program", "target"):
            if isinstance(task.get(side), dict):
                offer(task[side], f"task-{task.get('id')}", True)
    return corpus


def follow_up_calls(proposer, corpus, *, limit=12):
    """Calls of the learned definitions, offered against this corpus.

    `call_candidates` is the existing generator; the pool is the run's own
    programs and the exclusion is the corpus itself, so what comes back is the
    argument combinations the run has *not* already reached.
    """
    if not proposer.library:
        return []
    pool = [entry["program"] for entry in corpus]
    offered = call_candidates(
        proposer.library, pool, limit=limit,
        exclude=[key(entry["program"]) for entry in corpus],
        table=proposer.definitions)
    for call in offered:
        call["expands_to"] = expand_for_execution(call["call"],
                                                  proposer.definitions)
    return offered


class HolonomicDomain:
    """The search this session already drove: a Driver and a Proposer."""

    name = "holonomic"

    def __init__(self, config, *, driver=None, proposer=None):
        self.config = config
        self.driver = driver or Driver(
            {"source": SCHEMA, "config_sha256": digest(config)},
            budget=config["budget"], criterion=config["criterion"],
            certificates=list(deepcopy(config["certificates"]))
                         + seed_certificates(config["certify_pairs"]),
            tasks=deepcopy(config["tasks"]))
        self.proposer = proposer or restore_proposer(config)

    @staticmethod
    def grammar():
        return _series_grammar

    def search(self, config, index):
        allowance = int(config["allowance"] * config["growth"] ** min(index, 8))
        sweeps = self.proposer.run(
            self.driver, sweeps=config["sweeps_per_cycle"], allowance=allowance,
            growth=config["growth"], draft_count=config["draft_count"])
        return [{"sweep": s.get("sweep"),
                 "route": "powerplay sweep",
                 "attempted": [a.get("id") for a in s.get("attempted", [])],
                 "attempted_kinds": [a.get("kind") for a in s.get("attempted", [])],
                 "accepted": (s["accepted"] or {}).get("task_id")
                             if isinstance(s.get("accepted"), dict) else None,
                 "candidates_exhausted": s.get("candidates_exhausted"),
                 "undrafted": s.get("undrafted_abstractions"),
                 "spent_lines": s.get("spent_lines", 0)} for s in sweeps]

    def corpus(self):
        return corpus_from_history(self.driver, self.proposer)

    def follow_ups(self, config, corpus):
        return follow_up_calls(self.proposer, corpus,
                               limit=config["library_calls"])

    def adopt(self, library, weight=2):
        return adopt_library(self.proposer, library, weight=weight)

    def pending(self):
        return self.proposer.undrafted()

    def state(self):
        return {"schema": SCHEMA + ".holonomic",
                "driver": self.driver.state(),
                "proposer": proposer_state(self.proposer)}

    @classmethod
    def restore(cls, config, payload):
        return cls(config, driver=Driver.restore(payload["driver"]),
                   proposer=restore_proposer(config, payload["proposer"]))


def build_domain(config, payload=None):
    """The search this configuration selects. Adding one is adding a class."""
    name = config["domain"]
    if name == "holonomic":
        return (HolonomicDomain.restore(config, payload) if payload
                else HolonomicDomain(config))
    if name == "fold":
        from math_os_prototype.fold_domain import FoldDomain
        return (FoldDomain.restore(config, payload) if payload
                else FoldDomain(config))
    if name == "fold_observable":
        from math_os_prototype.fold_observable_domain import FoldObservableDomain
        return (FoldObservableDomain.restore(config, payload) if payload
                else FoldObservableDomain(config))
    raise ValueError(f"unknown domain {name!r}")


def uses_in(node, found=None):
    """Every `use` node inside a term, by the abstraction index it names."""
    found = [] if found is None else found
    if isinstance(node, dict):
        if node.get("op") == "use":
            found.append(node["abstraction"])
        for value in node.values():
            uses_in(value, found)
    elif isinstance(node, list):
        for value in node:
            uses_in(value, found)
    return found


def definition_depths(library):
    """Depth 1 for a body of primitives; one more for each learned layer.

    Read mechanically off the bodies: a definition whose body calls a depth-n
    definition is depth n+1. A reference the library does not contain, and a
    reference that would close a cycle, both contribute nothing.
    """
    by_index = {entry["index"]: entry for entry in library}
    memo = {}

    def depth(index, seen=()):
        if index in memo:
            return memo[index]
        if index in seen or index not in by_index:
            return 1
        refs = [r for r in uses_in(by_index[index]["template"]) if r in by_index]
        value = 1 + max((depth(r, seen + (index,)) for r in refs), default=0)
        memo[index] = value
        return value

    return {index: depth(index) for index in by_index}


# ---- the session ----------------------------------------------------------

class Session:
    """Initialise, cycle, stop, save. Nothing is reset between cycles."""

    def __init__(self, config, *, domain=None, cycles=(), elapsed_seconds=0.0):
        self.config = configure(config)
        self.domain = domain or build_domain(self.config)
        self.cycles = list(cycles)
        # What is carried across a restart is the compute this session actually
        # spent, not when it first started. Storing an absolute start stamp made
        # the wall-clock cap count the time the session sat on disk, so a resume
        # could stop before running a single cycle. Deltas inside one process are
        # taken from `time.monotonic`, which no clock adjustment can move.
        self.elapsed_seconds = float(elapsed_seconds)
        self.stop_reason = None

    # the two the holonomic domain owns, kept reachable where they always were
    @property
    def driver(self):
        return getattr(self.domain, "driver", None)

    @property
    def proposer(self):
        return getattr(self.domain, "proposer", None)

    # -- one cycle ---------------------------------------------------------

    def cycle(self):
        """Search under a budget, learn from what the search produced, adopt it."""
        began = time.perf_counter()
        index = len(self.cycles)
        allowance = int(self.config["allowance"]
                        * self.config["growth"] ** min(index, 8))
        # a call offered last cycle is consumed by this cycle's search; record
        # what became of it, from the domain's own constructions
        produced = getattr(self.domain, "constructions", None)
        sweeps = self.domain.search(self.config, index)
        if self.cycles and produced is not None:
            by_source = {c["source"]: c for c in self.domain.constructions}
            for call in self.cycles[-1]["follow_up_calls"]:
                entry = by_source.get(f"call-{call.get('id')}")
                call["entered_corpus"] = bool(entry)
                call["panels"] = entry["panels"] if entry else None
                call["intersecting_pairs"] = (entry["intersecting_pairs"]
                                              if entry else None)
        spent_lines = sum(s.get("spent_lines", 0) for s in sweeps)
        accepted = [s for s in sweeps if s.get("accepted")]

        corpus = self.domain.corpus()
        learned, compression = None, 0
        with grammar(self.domain.grammar()):
            if len(corpus) >= 2:
                learned = learn_library(
                    corpus, rounds=self.config["learn_rounds"],
                    pairs=self.config["learn_pairs"],
                    limit=self.config["learn_limit"],
                    keep=self.config["learn_keep"])
                compression = learned["net_compression_bits"]
                if learned["library"]:
                    self.domain.adopt(learned["library"],
                                      weight=self.config["library_weight"])
            calls = self.domain.follow_ups(self.config, corpus)
        kept = learned["library"] if learned else []
        depths = definition_depths(kept)
        definition_ids = {e["index"]: e["id"] for e in kept}

        record = {
            "cycle": index,
            "allowance": allowance,
            "seconds": round(time.perf_counter() - began, 3),
            "spent_lines": spent_lines,
            "sweeps": sweeps,
            "accepted_count": len(accepted),
            "corpus_programs": len(corpus),
            "corpus_bits": sum(cost(e["program"]) for e in corpus),
            "compression_bits": compression,
            "library": [{"index": e["index"], "id": e["id"],
                         "utility_bits": e["utility_bits"],
                         "definition_bits": e["definition_bits"],
                         "programs_touched": e["programs_touched"],
                         "template": e["template"]}
                        for e in (learned["library"] if learned else [])],
            "learn_rounds": (learned or {}).get("rounds", []),
            "follow_up_calls": [{"id": c.get("id"), "call": c.get("call"),
                                 "definition_index": c.get("definition"),
                                 "definition_id": definition_ids.get(c.get("definition")),
                                 "definition_depth": depths.get(c.get("definition")),
                                 "call_bits": c.get("call_bits"),
                                 "expanded_bits": c.get("expanded_bits"),
                                 "expands_to": c.get("expands_to"),
                                 "word": c.get("word"),
                                 "reason": c.get("reason")}
                                for c in calls],
            "pending": self.domain.pending(),
            # another route to a construction already held; counted separately
            # from the new constructions this cycle produced
            "revisited_calls": list(getattr(self.domain, "revisits", [])),
        }
        self.cycles.append(record)
        return record

    # -- the loop ----------------------------------------------------------

    def should_stop(self, elapsed, lines):
        config = self.config
        if elapsed >= config["max_seconds"]:
            return f"wall-clock cap reached ({config['max_seconds']}s)"
        if lines >= config["max_traced_lines"]:
            return f"compute cap reached ({config['max_traced_lines']} traced lines)"
        if len(self.cycles) >= config["max_cycles"]:
            return f"cycle cap reached ({config['max_cycles']})"
        barren = 0
        for record in reversed(self.cycles):
            if (record["accepted_count"] == 0
                    and record["compression_bits"] < config["min_compression_bits"]):
                barren += 1
            else:
                break
        if barren >= config["barren_cycles"]:
            return (f"{barren} consecutive cycles accepted nothing and learned "
                    f"under {config['min_compression_bits']} bits")
        return None

    def run(self, *, progress=None):
        began = time.monotonic()
        lines = sum(c["spent_lines"] for c in self.cycles)
        while True:
            elapsed = self.elapsed_seconds + (time.monotonic() - began)
            reason = self.should_stop(elapsed, lines)
            if reason:
                self.stop_reason = reason
                break
            record = self.cycle()
            lines += record["spent_lines"]
            if progress:
                progress(f"cycle {record['cycle']}: "
                         f"{record['accepted_count']} accepted, "
                         f"{record['corpus_programs']} programs, "
                         f"{record['compression_bits']:+d} bits, "
                         f"{len(record['library'])} definitions, "
                         f"{len(record['follow_up_calls'])} calls offered, "
                         f"{len(record['pending'])} pending")
        self.elapsed_seconds += time.monotonic() - began
        return self.cycles

    # -- persistence -------------------------------------------------------

    def state(self):
        payload = {"schema": SCHEMA,
                   "config": deepcopy(self.config),
                   "domain": self.domain.state(),
                   "cycles": deepcopy(self.cycles),
                   "elapsed_seconds": round(self.elapsed_seconds, 3),
                   "stop_reason": self.stop_reason,
                   "stop_note": STOP_NOTE}
        payload["sha256"] = digest(payload)
        return payload

    @classmethod
    def restore(cls, payload):
        stored = dict(payload)
        if stored.pop("sha256", None) != digest(stored):
            raise ValueError("session state digest does not match its contents")
        config = stored["config"]
        session = cls(config,
                      domain=build_domain(config, stored["domain"]),
                      cycles=stored["cycles"],
                      elapsed_seconds=stored.get("elapsed_seconds", 0.0))
        session.stop_reason = stored["stop_reason"]
        return session

    def save(self, directory):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "session.json").write_text(
            json.dumps(self.state(), indent=1, ensure_ascii=False), encoding="utf-8")
        return directory / "session.json"

    @classmethod
    def load(cls, directory):
        path = Path(directory) / "session.json"
        return cls.restore(json.loads(path.read_text(encoding="utf-8")))
