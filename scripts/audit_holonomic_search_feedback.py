"""Replay generation choices, certified replacements, and pool admissions."""
from collections import Counter
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from math_os_prototype.holonomic_route_discovery import coefficients, key
from math_os_prototype.holonomic_relation_reuse import digest
from math_os_prototype.holonomic_parametric_learning import learn_templates, DEFINITION_LEARNING_STRATEGIES
from math_os_prototype.holonomic_online_library import OnlineLibrary
from math_os_prototype.holonomic_action_control import (
    feature_names, environment_fingerprint, parameter_domain, select_composition, record_outcome,
    selection_state, search_domain,
)
from math_os_prototype.research_action_policy import ResearchActionPolicy
from math_os_prototype.research_action_frontier import ResearchActionFrontier
from math_os_prototype.holonomic_definition_screening import certify_definition_equal, replay_definition_certificate
from math_os_prototype.holonomic_search_pool import SeriesSearchPool, draw_composition, primitive_seeds
from scripts.run_holonomic_route_discovery import nodes, depth, order_bound
from math_os_prototype.holonomic_construction_memory import replay_memory, initial_certificates, extend_seeds
from math_os_prototype.holonomic_systematic_proposals import SystematicSeriesProposals
from math_os_prototype.holonomic_learned_proposals import LearnedSeriesProposals
from math_os_prototype.holonomic_source_proposals import SeriesSourceProposals
from math_os_prototype.holonomic_representation_progress import RepresentationProgress
from math_os_prototype.representation_progress import TARGET as PROGRESS_TARGET


def decisions_match(actual, recorded):
    if actual is None or recorded is None:
        return actual == recorded
    left, right = deepcopy(actual), deepcopy(recorded)
    a, b = left.pop("scores"), right.pop("scores")
    # BLAS reduction order can change last bits; choices and evidence stay exact.
    return left == right and len(a) == len(b) and all(abs(x-y) <= 1e-12 for x, y in zip(a, b))


def audit_search(data, library=None, *, prefix_only=False):
    policy, rows = data["policy"], data["programs"]
    if prefix_only:
        prefix = data.get("checkpoint_prefix", {})
        if (prefix.get("complete_run") is not False or prefix.get("through_proposal") != len(data["attempts"])
                or any(policy.get(k) for k in ("online_learning", "learned_library", "learned_proposal_every",
                                               "construction_memory", "source_proposal_every"))):
            raise ValueError("unsupported or unlabelled checkpoint prefix")
    ode_sources = None
    if policy.get("ode_sources"):
        from math_os_prototype.holonomic_ode_source import replay_corpus
        ode_sources = replay_corpus(data["ode_sources"])
        if (ode_sources["sha256"] != policy["ode_sources_sha256"] or policy["parameters"] or
                policy.get("source_proposal_every") or policy.get("construction_memory") or
                (policy.get("online_learning") and policy.get("parameter_template_strategy") not in DEFINITION_LEARNING_STRATEGIES)
                or policy.get("learned_library")):
            raise ValueError("invalid ODE source initialization")
    if policy.get("source_proposal_every") and (policy["parameters"] or
            policy.get("learned_library") or
            policy.get("action_selection") not in {"learn", "uniform"} or
            not policy.get("compound_operands") or policy.get("parameter_grid_is_human_declared") is not False):
        raise ValueError("invalid autonomous source initialization")
    memory = replay_memory(data["construction_memory"]) if policy.get("construction_memory") else None
    if memory and not policy.get("online_learning"):
        raise ValueError("construction memory needs an online knowledge history")
    controller = None
    mode = policy.get("action_selection", "legacy")
    if mode != "legacy":
        control = data["action_control"]
        environment = environment_fingerprint(policy)
        if control["environment"] != environment:
            raise ValueError("action environment failed replay")
        controller = ResearchActionPolicy.from_dict(control["initial"], environment_fingerprint=environment)
        if controller.feature_names != feature_names(policy.get("action_observation", "syntax")) or controller.reward_target != policy.get("action_reward", "new_verified_relation"):
            raise ValueError("invalid action controller semantics")
        if mode in {"learn", "uniform"} and controller.feedback:
            raise ValueError("non-frozen action control must start without outcomes")
        if mode == "frozen":
            controller.assert_holdout(search_domain(policy))
    progress = None
    if policy.get("action_reward") == PROGRESS_TARGET:
        if not policy.get("online_learning") or policy.get("learning_batch_size") != 1:
            raise ValueError("description progress has no per-action learning history")
        progress = RepresentationProgress(controller, source_domain=search_domain(policy),
                                          seed=policy["seed"], probe_items=policy["progress_probe_items"], learn=mode == "learn")

    def replay_feedback(attempt, row=None):
        if progress is not None:
            outcome = progress.record(attempt, row, library, epoch_libraries.get(attempt["index"], library))
            if outcome != attempt.get("control_feedback"):
                raise ValueError("representation action feedback failed replay")
            progress.advance(row)
            return
        if controller is None or attempt["seed"]:
            if "control_feedback" in attempt:
                raise ValueError("unexpected action feedback")
            return
        row = row or {}
        outcome = record_outcome(controller, attempt["decision"],
            status=row.get("comparison_status", attempt["status"]),
            certificate_hash=row.get("certificate_sha256"), source_domain=search_domain(policy),
            pair_id=f"seed-{policy['seed']}:proposal-{attempt['index']}", learn=mode == "learn")
        if outcome != attempt["control_feedback"]:
            raise ValueError("action outcome or policy update failed replay")
    epochs = data.get("learning_epochs", []) if policy.get("online_learning") else []
    epoch_libraries = {}
    if policy.get("online_learning"):
        if not epochs or epochs[0].get("after_proposal") != 0 or epochs[0].get("status") != "replayed":
            raise ValueError("online search has no empty initial library")
        last_proposal = -1
        for epoch in epochs:
            proposal = epoch["after_proposal"]
            if proposal <= last_proposal or proposal > len(data["attempts"]):
                raise ValueError("learning epoch ordering failed")
            last_proposal = proposal
            if epoch["status"] != "replayed":
                continue
            source = epoch["library"]["source_ground_library"]
            eligible = initial_certificates(memory)+[r["certificate"] for r in data["relations"]
                        if next(row for row in rows if row["id"] == r["program_ids"][1])["proposal_index"] <= proposal]
            if policy.get("parameter_template_strategy") in DEFINITION_LEARNING_STRATEGIES:
                eligible += [row["definition_certificate"] for row in rows
                             if row.get("proposal_index", proposal+1) <= proposal and "definition_certificate" in row]
            provenance = {"source": "current_search_exact_comparisons", "after_proposal": proposal}
            if memory:
                provenance["construction_memory"] = memory["sha256"]
            if (source["certificates"] != eligible
                    or epoch["input_certificate_hashes"] != [c["sha256"] for c in eligible]
                    or source["provenance"] != provenance):
                raise ValueError("online learning used evidence from outside the past of this run")
            restored = OnlineLibrary(epoch["library"])
            backend = policy.get("parameter_proof_backend", "coefficient_ratio")
            if epoch["library"].get("proof_backend", "coefficient_ratio") != backend:
                raise ValueError("parameter proof backend changed during learning")
            strategy = policy.get("parameter_template_strategy", "paired")
            if epoch["library"].get("template_strategy", "paired") != strategy:
                raise ValueError("parameter hypothesis strategy changed during learning")
            _, candidates = learn_templates(source, proof_backend=backend, template_strategy=strategy)
            if epoch["candidates"] != candidates:
                raise ValueError("lemma candidate outcomes failed replay")
            epoch_libraries[proposal] = restored
    if any("id" not in r for r in rows):
        raise ValueError("error rows require diagnosis, not a success audit")
    by_id, certificates = {}, {r["program_ids"][1]: r for r in data["relations"]}
    pool, rng = SeriesSearchPool(policy["pool_policy"]), random.Random(policy["seed"])
    primitives = [] if policy.get("source_proposal_every") else primitive_seeds(policy["parameters"])
    if ode_sources is not None:
        primitives = ode_sources["programs"]
    primitive_keys = {key(p) for p in primitives}
    seeds, seen, signatures = extend_seeds(primitives, memory), set(), set()
    memory_seed_ids = set()
    raw_seen = set()
    learned_descendants = set()
    learned = LearnedSeriesProposals(policy["learned_proposal_every"]) if policy.get("learned_proposal_every") else None
    source = SeriesSourceProposals(every=policy["source_proposal_every"], height=policy["source_height"],
                                   max_order=policy["max_order"]) if policy.get("source_proposal_every") else None
    frontier = ResearchActionFrontier(policy["action_frontier_every"]) if policy.get("action_frontier_every") else None
    systematic = SystematicSeriesProposals(every=policy["systematic_proposal_every"],
        with_add=policy.get("with_add", False), pullback_degree=policy.get("pullback_degree", 1),
        compound_operands=policy.get("compound_operands", False)) if policy.get("systematic_proposal_every") else None
    current_rows = {r["proposal_index"]: r for r in rows}
    ancestry, checked = {}, 0
    for index, attempt in enumerate(data["attempts"], 1):
        if epoch_libraries:
            library = epoch_libraries[max(p for p in epoch_libraries if p < index)]
        is_seed = bool(seeds)
        if is_seed:
            raw, parents, decision = seeds.pop(0), [], None
        else:
            raw, parents, decision = select_composition(pool, rng, controller,
                policy.get("action_choice_width", 8), uniform=mode == "uniform",
                learned=learned, library=library, source=source,
                frontier=frontier,
                systematic=systematic,
                frontier_window=policy.get("action_frontier_window", "oldest"),
                state=selection_state(seen | raw_seen, policy["max_depth"], policy["max_order"])
                      if policy.get("action_observation") == "state" else None,
                with_add=policy.get("with_add", False), pullback_degree=policy.get("pullback_degree", 1),
                compound_operands=policy.get("compound_operands", False))
        if not decisions_match(decision, attempt.get("decision")):
            raise ValueError("action alternatives, scores, or selection failed replay")
        if (attempt["index"] != index or attempt["program"] != raw
                or attempt["parents"] != parents or attempt["seed"] != is_seed):
            raise ValueError("generation draw failed replay")
        if raw is None:
            expected = "no_admissible_alternative"
        elif depth(raw) > policy["max_depth"] or nodes(raw) > 32 or order_bound(raw) > policy["max_order"]:
            expected = "construction_budget"
        else:
            prefix = coefficients(raw, 12)
            p = raw
            if not any(prefix):
                expected = "zero_prefix"
            else:
                if prefix[0] not in (0, 1):
                    p = {"op": "scale", "factor": str(1/prefix[0]), "child": raw}
                    prefix = coefficients(p, 12)
                if depth(p) > policy["max_depth"]:
                    expected = "normalization_depth_budget"
                else:
                    raw_seen.add(key(raw))
                    expected = "same_syntax" if key(p) in seen else "candidate"
        if expected != attempt["status"]:
            raise ValueError("proposal rejection failed replay")
        if expected != "candidate":
            replay_feedback(attempt)
            continue
        row = current_rows[index]
        selected = decision["alternatives"][decision["selected"]] if decision else {}
        uses_learned = (selected.get("proposal_origin") in {"learned_parameter_template", "learned_function_template"}
                        or bool(set(parents) & learned_descendants))
        if row.get("uses_learned_construction", False) != uses_learned:
            raise ValueError("learned construction ancestry failed replay")
        if uses_learned:
            learned_descendants.add(row["id"])
        if (row["program"] != p or row["id"] != sha256(key(p).encode()).hexdigest()[:20]
                or attempt["candidate_id"] != row["id"] or row["parents"] != parents
                or row["seed"] != is_seed or row["prefix"] != list(map(str, prefix))):
            raise ValueError("candidate metadata failed replay")
        if library:
            if not library.replay(row["rewrite"]) or row["rewrite"]["input"] != p:
                raise ValueError("invalid learned rewrite")
            reduced = row["reduced_program"]
            if row["rewrite"]["output"] != reduced:
                raise ValueError("reduced expression differs from proof output")
        else:
            reduced = p
            if "rewrite" in row or row.get("reduced_program", p) != p:
                raise ValueError("unproved rewrite without a library")

        def previous_reduction(previous_id, field):
            previous = by_id[previous_id]
            if epoch_libraries:
                trace = row[field]
                if trace["input"] != previous["program"] or not library.replay(trace):
                    raise ValueError("previous operand rewrite failed replay")
                return trace["output"]
            return previous.get("reduced_program", previous["program"])
        equal_to = None
        if row["comparison_status"] == "equality_via_learned_library":
            equal_to = row["equal_to"]
            if reduced != previous_reduction(equal_to, "equality_left_rewrite"):
                raise ValueError("unjustified identical-reduction claim")
        elif row["comparison_status"] == "exact_formal_series_equality":
            equal_to = row["equal_to"]
            relation, cert = certificates[row["id"]], certificates[row["id"]]["certificate"]
            payload = {k: v for k, v in cert.items() if k != "sha256"}
            if (relation["program_ids"] != [equal_to, row["id"]]
                    or cert["left"] != previous_reduction(equal_to, "comparison_left_rewrite") or cert["right"] != reduced
                    or cert["status"] != "exact_formal_series_equality"
                    or digest(payload) != cert["sha256"] or row["certificate_sha256"] != cert["sha256"]):
                raise ValueError("exact-certificate linkage failed")
            if policy.get("definition_screen") and certify_definition_equal(cert["left"], cert["right"]) is not None:
                raise ValueError("definition-only identity incorrectly rewarded as a fresh relation")
            checked += 1
        elif row["comparison_status"] == "definition_only_equality":
            cert = row["definition_certificate"]
            equal_to = row["equal_to"]
            if (not policy.get("definition_screen") or not replay_definition_certificate(cert)
                    or cert["left"] != previous_reduction(equal_to, "comparison_left_rewrite")
                    or cert["right"] != reduced):
                raise ValueError("definition-only equality failed replay")
        elif row["comparison_status"] not in ("no_prefix_match", "certificate_budget", "timeout",
                                                "initial_coefficient_budget", "refuted", "error"):
            raise ValueError("unknown proof outcome")
        admission = pool.admit(row, reduced, is_seed=is_seed, equal_to=equal_to)
        if admission != row["pool"]:
            raise ValueError("pool admission failed replay")
        ancestry[row["id"]] = {row["id"]}.union(*(ancestry[p] for p in parents))
        if is_seed and key(raw) not in primitive_keys and admission["admitted"]:
            memory_seed_ids.add(row["id"])
        by_id[row["id"]] = row
        signatures.add(tuple(prefix))
        seen.add(key(p))
        replay_feedback(attempt, row)
    if controller is not None and controller.to_dict() != data["action_control"]["final"]:
        raise ValueError("final action policy failed replay")
    if not prefix_only and data.get("representation_progress") != (progress.snapshot() if progress else None):
        raise ValueError("delayed representation probe or reward failed replay")
    if not prefix_only and data.get("action_frontier") != (frontier.snapshot() if frontier else None):
        raise ValueError("final retained frontier failed replay")
    if not prefix_only and data.get("systematic_proposals") != (systematic.snapshot() if systematic else None):
        raise ValueError("systematic proposal agenda failed replay")
    if not prefix_only and data.get("learned_proposals") != (learned.snapshot() if learned else None):
        raise ValueError("learned proposal agenda failed replay")
    if not prefix_only and data.get("source_proposals") != (source.snapshot() if source else None):
        raise ValueError("source proposal agenda failed replay")
    if (not prefix_only and data["active_pool"] != pool.entries) or len(current_rows) != len(by_id):
        raise ValueError("final pool or candidate count mismatch")
    if prefix_only and frontier is not None:
        decisions = [a["decision"] for a in data["attempts"] if "decision" in a]
        if decisions and frontier.digest() != decisions[-1]["frontier"]["after_sha256"]:
            raise ValueError("checkpoint frontier does not match the last logged decision")
    learned_counts = Counter(step["rule"] for r in rows for step in r.get("rewrite", {}).get("steps", []))
    systematic_choices = sum(a.get("decision", {}).get("selected") is not None and
        a["decision"]["alternatives"][a["decision"]["selected"]].get("proposal_origin") == "systematic"
        for a in data["attempts"])
    return {"generation_choices_replayed": len(data["attempts"]), "candidate_rewrites_replayed": len(rows),
            "definition_only_certificates_replayed": sum(r["comparison_status"] == "definition_only_equality" for r in rows),
            "pool_admissions_replayed": len(rows), "fresh_certificate_links_checked": checked,
            "online_learning_epochs_replayed": len(epoch_libraries),
            "action_feedback_replayed": sum("control_feedback" in a for a in data["attempts"]),
            "delayed_representation_probes_replayed": len(progress.events) if progress else 0,
            "fresh_mathematical_proofs_replayed_in_generation_workers": True,
            "this_audit_recomputes_fresh_ode_proofs": False,
            "distinct_functions_lower_bound": len(signatures),
            "max_syntax_depth": max(r["depth"] for r in rows), "max_syntax_nodes": max(r["nodes"] for r in rows),
            "max_recorded_ancestral_events": max(map(len, ancestry.values())),
            "ancestral_events_are_not_necessary_lemmas": True,
            "rewrite_rule_use_counts": dict(learned_counts),
            "proof_status_counts": dict(Counter(r["comparison_status"] for r in rows)),
            "summary": data["summary"], "new_mathematical_families_established": 0,
            "proof_derived_constructions_admitted": len(memory_seed_ids),
            "nonseed_candidates_using_proof_derived_constructions": sum(
                not row["seed"] and bool(ancestry[row["id"]] & memory_seed_ids) for row in rows),
            "systematic_offers_replayed": sum(a.get("decision", {}).get("systematic", {}).get("item") is not None
                                              for a in data["attempts"]),
            "systematic_choices_replayed": systematic_choices,
            "systematic_streams_registered": len(systematic.agenda.streams) if systematic else 0,
            "systematic_items_remaining": sum(s["length"]-s["next"] for s in systematic.agenda.streams) if systematic else 0,
            "accepted_hard_problems": 0,
            **({"complete_run_verified": False, "checkpoint_prefix": data["checkpoint_prefix"],
                "final_snapshot_comparison": False,
                "scope": "logged prefix decisions, coefficients, certificates and admissions; not a completed run"}
               if prefix_only else {})}
