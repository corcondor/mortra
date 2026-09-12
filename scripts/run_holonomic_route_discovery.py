"""Compose a declared series grammar, then discover and replay route equalities."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from math_os_prototype.holonomic_route_discovery import (
    certify_equal, coefficients, key, replay_certificate,
)
from scripts.benchmark_hageo409_auxiliary import run_command_with_process_tree_timeout
from math_os_prototype.holonomic_parametric_learning import load_library, learn_templates
from math_os_prototype.holonomic_online_library import OnlineLibrary
from math_os_prototype.holonomic_relation_reuse import build_library
from math_os_prototype.holonomic_search_pool import SeriesSearchPool, draw_composition, primitive_seeds
from math_os_prototype.research_events import emit as emit_event
from math_os_prototype.holonomic_action_control import (
    feature_names, make_policy, parameter_domain, select_composition, record_outcome, environment_fingerprint,
    nodes, depth, order_bound, selection_state, search_domain,
)
from math_os_prototype.research_action_policy import ResearchActionPolicy
from math_os_prototype.research_action_frontier import ResearchActionFrontier
from math_os_prototype.holonomic_definition_screening import certify_definition_equal, replay_definition_certificate
from math_os_prototype.holonomic_construction_memory import load_memory, initial_certificates, extend_seeds
from math_os_prototype.holonomic_systematic_proposals import SystematicSeriesProposals
from math_os_prototype.holonomic_learned_proposals import LearnedSeriesProposals
from math_os_prototype.holonomic_source_proposals import SeriesSourceProposals
from math_os_prototype.holonomic_representation_progress import RepresentationProgress
from math_os_prototype.representation_progress import TARGET as PROGRESS_TARGET
from math_os_prototype.shared_json import read as read_artifact, write as write_artifact


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def compare_bounded(left, right, directory, index, seconds, definition_screen=False, shared_artifacts=False):
    path = directory/f"comparison-{index:04d}.json"
    write_artifact(path, {"left": left, "right": right, "definition_screen": definition_screen}, shared=shared_artifacts)
    try:
        result = run_command_with_process_tree_timeout(
            [sys.executable, "-X", "utf8", str(Path(__file__).resolve()), "--worker", str(path.resolve())],
            cwd=ROOT, timeout_seconds=seconds, env={**os.environ, "PYTHONUTF8": "1"})
        if result.returncode:
            return {"status": "error", "diagnostic": result.stderr[-2000:]}
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "seconds": seconds}


def learn_epoch(relations, proposal, memory=None, *, proof_backend="coefficient_ratio", template_strategy="paired",
                definition_certificates=()):
    """Use only replayed current or provenance-linked inherited equalities."""
    certificates = initial_certificates(memory)+[r["certificate"] for r in relations]+list(definition_certificates)
    provenance = {"source": "current_search_exact_comparisons", "after_proposal": proposal}
    if memory is not None:
        provenance["construction_memory"] = memory["sha256"]
    ground = build_library(certificates, provenance)
    data, candidates = learn_templates(ground, proof_backend=proof_backend, template_strategy=template_strategy)
    library = OnlineLibrary(data)
    return library, {"status": "replayed", "after_proposal": proposal,
                     "input_certificate_hashes": [c["sha256"] for c in certificates],
                     "library": data, "candidates": candidates}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260906)
    parser.add_argument("--programs", type=int, default=160)
    parser.add_argument("--max-depth", type=int, default=6)
    parser.add_argument("--max-certificates", type=int, default=32)
    parser.add_argument("--certificate-seconds", type=float, default=15)
    parser.add_argument("--max-order", type=int, default=4)
    parser.add_argument("--parameters", nargs="+")
    parser.add_argument("--learned-library", type=Path)
    parser.add_argument("--ode-sources", type=Path,
                        help="frozen exact ODE objects with source provenance; no default hypergeometric seeds")
    parser.add_argument("--shared-artifacts", action="store_true",
                        help="losslessly share repeated JSON containers in artifacts")
    parser.add_argument("--construction-memory", type=Path)
    parser.add_argument("--online-learning", action="store_true")
    parser.add_argument("--learning-batch-size", type=int, default=2)
    parser.add_argument("--parameter-proof-backend", choices=["coefficient_ratio", "uniform_ode", "formal_function", "typed_dispatch"], default="coefficient_ratio")
    parser.add_argument("--parameter-template-strategy", choices=["paired", "paired_and_rays", "abstract_functions", "abstract_subexpressions", "typed_union"], default="paired")
    parser.add_argument("--pool-policy", choices=["raw", "certified"], default="raw")
    parser.add_argument("--max-proposals", type=int)
    parser.add_argument("--with-add", action="store_true")
    parser.add_argument("--pullback-degree", type=int, choices=[1, 2, 3], default=1)
    parser.add_argument("--compound-operands", action="store_true")
    parser.add_argument("--action-selection", choices=["legacy", "uniform", "learn", "frozen"], default="legacy")
    parser.add_argument("--action-reward", choices=["new_verified_relation", PROGRESS_TARGET], default="new_verified_relation")
    parser.add_argument("--progress-probe-items", type=int, default=64)
    parser.add_argument("--action-choice-width", type=int, default=8)
    parser.add_argument("--action-policy", type=Path)
    parser.add_argument("--action-observation", choices=["syntax", "state"], default="syntax")
    parser.add_argument("--action-frontier-every", type=int, default=0,
                        help="retain offered actions; serve oldest every N rounds (0 disables)")
    parser.add_argument("--action-frontier-window", choices=["oldest", "sampled"], default="oldest")
    parser.add_argument("--systematic-proposal-every", type=int, default=0,
                        help="offer one enumerated composition every N selection rounds (0 disables)")
    parser.add_argument("--learned-proposal-every", type=int, default=0,
                        help="offer a compound construction from certified parameter rules every N rounds")
    parser.add_argument("--source-proposal-every", type=int, default=0,
                        help="start empty and offer new hypergeometric arities and rational parameters every N rounds")
    parser.add_argument("--source-height", type=int, default=5,
                        help="maximum numerator + denominator for positive reduced source parameters (2..8)")
    parser.add_argument("--definition-screen", action=argparse.BooleanOptionalAction, default=None,
                        help="do not reward identities already implied by arithmetic and formal calculus")
    args = parser.parse_args()
    def write(path, data):
        write_artifact(path, data, shared=args.shared_artifacts)
    def emit(component, event, **data):
        emit_event(component, event,
                   _payload_directory=args.output.resolve()/"event-payloads" if args.shared_artifacts else None,
                   **data)
    from math_os_prototype.holonomic_parametric_learning import DEFINITION_LEARNING_STRATEGIES, validate_learning_mode
    try:
        validate_learning_mode(args.parameter_proof_backend, args.parameter_template_strategy)
    except ValueError as exc:
        parser.error(str(exc))
    function_learning = args.parameter_template_strategy in DEFINITION_LEARNING_STRATEGIES
    if function_learning and not args.online_learning:
        parser.error("function abstraction needs online learning")
    if args.ode_sources and (args.parameters is not None or args.source_proposal_every or args.construction_memory
                            or (args.online_learning and not function_learning) or args.learned_library):
        parser.error("ODE sources require fixed sources; online learning supports function abstraction only")
    if args.source_proposal_every < 0 or (args.source_proposal_every and (
            args.parameters is not None or args.learned_library or
            args.action_selection not in {"learn", "uniform"} or not args.action_frontier_every or
            not args.compound_operands or not 2 <= args.source_height <= 8 or not 1 <= args.max_order <= 5 or
            args.action_choice_width < 2 + int(bool(args.learned_proposal_every)))):
        parser.error("source selection requires no supplied parameters/library, learn or uniform retained selection, compound operands, height 2..8, order 1..5, and sufficient choice width")
    args.parameters = [] if args.source_proposal_every or args.ode_sources else (args.parameters or ["1/2", "1", "3/2"])
    if args.learned_proposal_every < 0 or (args.learned_proposal_every and
            (not args.online_learning or args.action_selection == "legacy" or
             not args.action_frontier_every or args.action_choice_width < 2)):
        parser.error("learned proposals require online learning, retained non-legacy selection, and width >= 2")
    if args.action_reward == PROGRESS_TARGET and (args.action_selection == "legacy" or
            not args.online_learning or args.learning_batch_size != 1 or args.progress_probe_items < 1):
        parser.error("description progress needs non-legacy online selection, learning batch size 1, and a positive probe size")
    if args.definition_screen is None:
        args.definition_screen = args.action_selection != "legacy"
    if args.online_learning and args.learned_library:
        parser.error("online learning starts from this run, not an externally supplied library")
    if args.construction_memory and (not args.online_learning or args.learned_library):
        parser.error("construction memory requires online learning and no separate library")
    if args.learning_batch_size < 1:
        parser.error("learning batch size must be positive")
    if args.action_choice_width < 1:
        parser.error("action choice width must be positive")
    if args.max_depth < 1 or args.max_order < 1:
        parser.error("construction bounds must be positive")
    if args.action_observation == "state" and args.action_selection == "legacy":
        parser.error("state observation requires an action selector")
    if args.action_frontier_every < 0 or (args.action_frontier_every and args.action_observation != "state"):
        parser.error("retained frontier requires state observation and a positive service interval")
    if args.action_frontier_window == "sampled" and not args.action_frontier_every:
        parser.error("sampled window requires a retained frontier")
    if args.systematic_proposal_every < 0 or (args.systematic_proposal_every and
            (not args.action_frontier_every or args.action_selection == "legacy")):
        parser.error("systematic proposals require non-legacy selection with a retained frontier")
    if (args.action_selection == "frozen") != (args.action_policy is not None):
        parser.error("frozen selection requires a policy; other modes start without one")
    args.output.mkdir(parents=True, exist_ok=False)
    if args.shared_artifacts:
        payloads = args.output.resolve()/"event-payloads"
        payloads.mkdir()
    paths = [Path(__file__), ROOT/"math_os_prototype/holonomic_route_discovery.py",
             ROOT/"scripts/benchmark_hageo409_auxiliary.py",
             ROOT/"math_os_prototype/holonomic_relation_reuse.py",
             ROOT/"math_os_prototype/holonomic_parametric_learning.py",
             ROOT/"math_os_prototype/holonomic_parameter_ode.py",
             ROOT/"math_os_prototype/holonomic_online_library.py",
             ROOT/"math_os_prototype/holonomic_action_control.py",
             ROOT/"math_os_prototype/research_action_policy.py",
             ROOT/"math_os_prototype/representation_progress.py",
             ROOT/"math_os_prototype/holonomic_representation_progress.py",
             ROOT/"math_os_prototype/research_action_frontier.py",
             ROOT/"math_os_prototype/research_indexed_agenda.py",
             ROOT/"math_os_prototype/holonomic_systematic_proposals.py",
             ROOT/"math_os_prototype/holonomic_learned_proposals.py",
             ROOT/"math_os_prototype/holonomic_source_proposals.py",
             ROOT/"math_os_prototype/holonomic_definition_screening.py",
             ROOT/"math_os_prototype/holonomic_joint_relations.py",
             ROOT/"math_os_prototype/holonomic_search_pool.py",
             ROOT/"math_os_prototype/research_events.py"]
    paths.extend([ROOT/"math_os_prototype"/name for name in (
        "holonomic_construction_memory.py", "holonomic_joint_action_control.py",
        "holonomic_joint_screening.py", "holonomic_shared_module.py", "certified_polynomial_ideal.py")])
    paths.extend([ROOT/"math_os_prototype/holonomic_ode_source.py", ROOT/"math_os_prototype/ordinary_period_germ.py",
                  ROOT/"math_os_prototype/shared_json.py"])
    hashes = {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in paths}
    from math_os_prototype.holonomic_ode_source import load_corpus
    ode_sources = load_corpus(args.ode_sources) if args.ode_sources else None
    policy = {**vars(args), "output": str(args.output.resolve()), "prefix_terms": 12,
              "learned_library": str(args.learned_library.resolve()) if args.learned_library else None,
              "action_policy": str(args.action_policy.resolve()) if args.action_policy else None,
              "action_policy_sha256": sha256(args.action_policy.read_bytes()).hexdigest() if args.action_policy else None,
              "raw_proposal_pool_is_shared_across_policies": args.pool_policy == "raw" and args.action_selection == "legacy",
              "proposal_cap": args.max_proposals if args.max_proposals is not None else args.programs*20,
              "library_sha256": sha256(args.learned_library.read_bytes()).hexdigest() if args.learned_library else None,
              "operators": ["hyper", "poly", "diff", "mul", "pullback", "scale"]+(["add"] if args.with_add else []),
              "certificate_backend": "SymPy holonomic; rational Ore remainder and uniqueness replay",
              "target_identity_supplied": False, "special_points_supplied": False,
              "literature_identities_loaded": False, "parameter_grid_is_human_declared": not bool(args.source_proposal_every),
              "source_grammar_and_budgets_are_human_declared": True,
              "online_pool_refresh": "prospective_only; old entries retained; comparison operands rechecked",
              "source_hashes": hashes, "started_utc": datetime.now(timezone.utc).isoformat()}
    policy["construction_memory"] = str(args.construction_memory.resolve()) if args.construction_memory else None
    policy["construction_memory_file_sha256"] = sha256(args.construction_memory.read_bytes()).hexdigest() if args.construction_memory else None
    policy["ode_sources"] = str(args.ode_sources.resolve()) if args.ode_sources else None
    if ode_sources is not None:
        policy["ode_sources_sha256"] = ode_sources["sha256"]
        policy["operators"].append("ode")
        policy["parameter_grid_is_human_declared"] = False
        write(args.output/"ode-sources.json", ode_sources)
    write(args.output/"pre-run-seal.json", policy)
    emit("holonomic-search", "search_started", operators=policy["operators"],
         selection_scope="algorithmic_composition_within_declared_grammar",
         target_identity_supplied=False, parameter_grid_is_human_declared=policy["parameter_grid_is_human_declared"],
         output=str(args.output.resolve()), seed=args.seed, maximum_depth=args.max_depth)
    for path in paths:
        (args.output/(path.name+".source")).write_bytes(path.read_bytes())
    load_started = time.perf_counter()
    library = load_library(args.learned_library) if args.learned_library else None
    memory = load_memory(args.construction_memory) if args.construction_memory else None
    if memory:
        write(args.output/"construction-memory.json", memory)
    learning_epochs = []
    learning_options = ({"proof_backend": args.parameter_proof_backend}
                        if args.parameter_proof_backend != "coefficient_ratio" else {})
    if args.parameter_template_strategy != "paired":
        learning_options["template_strategy"] = args.parameter_template_strategy
    if args.online_learning:
        library, initial_epoch = learn_epoch([], 0, memory, **learning_options) if memory else learn_epoch([], 0, **learning_options)
        learning_epochs.append(initial_epoch)
        write(args.output/"learning-epochs.json", learning_epochs)
    if args.learned_library:
        (args.output/"frozen-library.json").write_bytes(args.learned_library.read_bytes())
    library_replay_seconds = time.perf_counter()-load_started
    emit("holonomic-search", "library_checked", supplied=args.learned_library is not None,
         online_learning=args.online_learning,
         library_sha256=policy["library_sha256"], elapsed_seconds=library_replay_seconds)
    rng = random.Random(args.seed)
    action_environment = environment_fingerprint(policy)
    controller = None
    if args.action_selection != "legacy":
        controller = (ResearchActionPolicy.load(args.action_policy, environment_fingerprint=action_environment)
                      if args.action_policy else make_policy(action_environment, args.action_observation, args.action_reward))
        if controller.feature_names != feature_names(args.action_observation) or controller.reward_target != args.action_reward:
            raise ValueError("incompatible action policy objective or features")
        if args.action_selection == "frozen":
            controller.assert_holdout(search_domain(policy))
    initial_controller = controller.to_dict() if controller else None
    write(args.output/"action-policy-initial.json", initial_controller)
    primitives = [] if args.source_proposal_every else primitive_seeds(args.parameters)
    if ode_sources is not None:
        primitives = ode_sources["programs"]
    primitive_keys = {key(p) for p in primitives}
    seeds = extend_seeds(primitives, memory)
    pool = SeriesSearchPool(args.pool_policy)
    seen, buckets, rows, relations, attempts = set(), {}, [], [], []
    raw_seen = set()
    learned_descendants = set()
    learned = LearnedSeriesProposals(args.learned_proposal_every) if args.learned_proposal_every else None
    source = SeriesSourceProposals(every=args.source_proposal_every, height=args.source_height,
                                   max_order=args.max_order) if args.source_proposal_every else None
    frontier = ResearchActionFrontier(args.action_frontier_every) if args.action_frontier_every else None
    systematic = SystematicSeriesProposals(every=args.systematic_proposal_every,
        with_add=args.with_add, pullback_degree=args.pullback_degree,
        compound_operands=args.compound_operands) if args.systematic_proposal_every else None
    reduced_seen = {}
    started = time.perf_counter()
    proposals, comparisons = 0, 0
    learned_through = 0
    definition_certificates = []
    progress = RepresentationProgress(controller, source_domain=search_domain(policy), seed=args.seed,
                                      probe_items=args.progress_probe_items, learn=args.action_selection == "learn") \
               if args.action_reward == PROGRESS_TARGET else None

    def feedback(attempt, row=None, before_library=None, after_library=None):
        if progress is not None:
            outcome = progress.record(attempt, row, before_library, after_library)
            if outcome is not None:
                attempt["control_feedback"] = outcome
                emit("holonomic-search", "representation_action_outcome", proposal=attempt["index"], **outcome)
            for event in progress.advance(row):
                emit("holonomic-search", "representation_probe_completed", origin_proposal=event["origin_proposal"],
                     observed_after_proposal=event["observed_after_proposal"],
                     receipt_sha256=event["receipt"]["sha256"], **event["feedback"])
            write(args.output/"representation-progress.json", progress.snapshot())
            return
        if controller is None or "decision" not in attempt:
            return
        row = row or {}
        outcome = record_outcome(controller, attempt["decision"],
            status=row.get("comparison_status", attempt["status"]),
            certificate_hash=row.get("certificate_sha256"), source_domain=search_domain(policy),
            pair_id=f"seed-{args.seed}:proposal-{attempt['index']}", learn=args.action_selection == "learn")
        attempt["control_feedback"] = outcome
        emit("holonomic-search", "action_outcome_observed", proposal=attempt["index"], **outcome)

    while len(rows) < args.programs and proposals < policy["proposal_cap"]:
        proposals += 1
        is_seed, parent_ids, decision = bool(seeds), [], None
        if seeds:
            p = seeds.pop(0)
        else:
            if not pool.entries and source is None:
                break
            p, parent_ids, decision = select_composition(pool, rng, controller, args.action_choice_width,
                learned=learned, library=library, source=source,
                frontier=frontier,
                systematic=systematic,
                frontier_window=args.action_frontier_window,
                state=selection_state(seen | raw_seen, args.max_depth, args.max_order)
                      if args.action_observation == "state" else None,
                uniform=args.action_selection == "uniform", with_add=args.with_add,
                pullback_degree=args.pullback_degree, compound_operands=args.compound_operands)
        attempt = {"index": proposals, "program": p, "parents": parent_ids, "seed": is_seed}
        if decision is not None:
            attempt["decision"] = decision
            emit("holonomic-search", "action_selected_from_alternatives", proposal=proposals,
                 selection=args.action_selection, decision=decision)
        attempts.append(attempt)
        if p is None:
            attempt["status"] = "no_admissible_alternative"
            emit("holonomic-search", "action_batch_skipped", proposal=proposals, reason=attempt["status"])
            feedback(attempt)
            continue
        emit("holonomic-search", "operation_selected", proposal=proposals,
             program=p, parents=parent_ids, primitive_seed=is_seed and key(p) in primitive_keys,
             proof_derived_seed=is_seed and key(p) not in primitive_keys)
        if depth(p) > args.max_depth or nodes(p) > 32 or order_bound(p) > args.max_order:
            attempt["status"] = "construction_budget"
            emit("holonomic-search", "proposal_rejected", proposal=proposals,
                 reason=attempt["status"])
            feedback(attempt)
            continue
        try:
            prefix = coefficients(p, 12)
            if not any(prefix):
                attempt["status"] = "zero_prefix"
                emit("holonomic-search", "proposal_rejected", proposal=proposals,
                     reason=attempt["status"], zero_series_proved=False)
                feedback(attempt)
                continue
            if prefix[0] not in (0, 1):
                p = {"op": "scale", "factor": str(1/prefix[0]), "child": p}
                prefix = coefficients(p, 12)
            if depth(p) > args.max_depth:
                attempt["status"] = "normalization_depth_budget"
                emit("holonomic-search", "proposal_rejected", proposal=proposals,
                     reason=attempt["status"])
                feedback(attempt)
                continue
            encoded = key(p)
            raw_seen.add(key(attempt["program"]))
            if encoded in seen:
                attempt["status"] = "same_syntax"
                emit("holonomic-search", "proposal_rejected", proposal=proposals,
                     reason=attempt["status"])
                feedback(attempt)
                continue
            seen.add(encoded)
            row = {"id": sha256(encoded.encode()).hexdigest()[:20], "program": p,
                   "depth": depth(p), "nodes": nodes(p), "prefix": list(map(str, prefix)),
                   "proposal_index": proposals, "parents": parent_ids, "seed": is_seed}
            if learned is not None:
                selected = decision["alternatives"][decision["selected"]] if decision else {}
                row["uses_learned_construction"] = (selected.get("proposal_origin") in {"learned_parameter_template", "learned_function_template"}
                                                     or bool(set(parent_ids) & learned_descendants))
                if row["uses_learned_construction"]:
                    learned_descendants.add(row["id"])
            attempt.update({"status": "candidate", "candidate_id": row["id"]})
            reduced = p
            if library:
                reduced, trace = library.reduce(p)
                if not library.replay(trace):
                    raise ValueError("context rewrite replay failed")
                row.update({"reduced_program": reduced, "rewrite": trace,
                            "reduced_nodes": nodes(reduced), "reduced_depth": depth(reduced)})
                emit("holonomic-search", "learned_rewrite_replayed", candidate=row["id"],
                     steps=trace.get("steps", []), reduced_program=reduced)
            signature = tuple(prefix)
            previous = buckets.get(signature)
            previous_reduced = previous.get("reduced_program", previous["program"]) if previous else None
            if args.online_learning and previous:
                previous_reduced, previous_trace = library.reduce(previous["program"])
                if not library.replay(previous_trace):
                    raise ValueError("previous candidate rewrite failed replay")
                row["comparison_left_rewrite"] = previous_trace
                reduced_seen.setdefault(key(previous_reduced), previous)
            reduced_key = key(reduced)
            equal_to = None
            if library and reduced_key in reduced_seen:
                row["comparison_status"] = "equality_via_learned_library"
                row["equal_to"] = reduced_seen[reduced_key]["id"]
                equal_to = row["equal_to"]
                if args.online_learning:
                    left, trace = library.reduce(reduced_seen[reduced_key]["program"])
                    if left != reduced or not library.replay(trace):
                        raise ValueError("online equality operands do not share a certified reduction")
                    row["equality_left_rewrite"] = trace
            elif signature in buckets and comparisons < args.max_certificates:
                comparisons += 1
                write(args.output/"checkpoint.json", {"programs": rows, "relations": relations,
                    "pending_comparison": [previous["id"], row["id"]], "pending_program": p})
                emit("holonomic-search", "proof_started", left=previous["id"], right=row["id"],
                     evidence="12_exact_coefficients_match_not_yet_an_identity",
                     comparison=comparisons, seconds=args.certificate_seconds)
                comparison_started = time.perf_counter()
                result = compare_bounded(previous_reduced, reduced,
                                         args.output, comparisons, args.certificate_seconds, args.definition_screen,
                                         **({"shared_artifacts": True} if args.shared_artifacts else {}))
                row["comparison_seconds"] = time.perf_counter()-comparison_started
                write(args.output/f"comparison-{comparisons:04d}-result.json", result)
                row["comparison_status"] = result["status"]
                row["comparison_index"] = comparisons
                emit("holonomic-search", "proof_finished", left=previous["id"], right=row["id"],
                     status=result["status"], certificate_sha256=result.get("sha256"),
                     artifact=str((args.output/f"comparison-{comparisons:04d}-result.json").resolve()),
                     elapsed_seconds=row["comparison_seconds"], new_formula_claimed=False)
                if result["status"] == "exact_formal_series_equality":
                    relations.append({"program_ids": [previous["id"], row["id"]], "certificate": result})
                    equal_to = previous["id"]
                    row["equal_to"] = equal_to
                    row["certificate_sha256"] = result["sha256"]
                elif result["status"] == "definition_only_equality":
                    if not args.definition_screen:
                        raise ValueError("unexpected definition-only proof without screening")
                    equal_to = previous["id"]
                    row.update(equal_to=equal_to, definition_certificate=result)
                    if function_learning:
                        definition_certificates.append(result)
            elif signature in buckets:
                row["comparison_status"] = "certificate_budget"
            else:
                buckets[signature] = row
                row["comparison_status"] = "no_prefix_match"
            reduced_seen.setdefault(reduced_key, row)
            row["pool"] = pool.admit(row, reduced, is_seed=is_seed, equal_to=equal_to)
            rows.append(row)
            emit("holonomic-search", "candidate_recorded", candidate=row["id"],
                 comparison_status=row["comparison_status"], depth=row["depth"],
                 nodes=row["nodes"], active_pool=len(pool.entries),
                 equal_to=equal_to, exact_route_equalities=len(relations))
            if progress is None:
                feedback(attempt, row)
            before_library = library
            if args.online_learning and len(relations)+len(definition_certificates)-learned_through >= args.learning_batch_size:
                learned_through = len(relations)+len(definition_certificates)
                learning_started = time.perf_counter()
                emit("holonomic-search", "lemma_learning_started", after_proposal=proposals,
                     exact_examples=len(relations), target_lemma_supplied=False)
                try:
                    function_options = {"definition_certificates": definition_certificates} if function_learning else {}
                    updated, epoch = (learn_epoch(relations, proposals, memory, **learning_options, **function_options)
                                      if memory else learn_epoch(relations, proposals, **learning_options, **function_options))
                except Exception as exc:
                    epoch = {"status": "error", "after_proposal": proposals,
                             "error": f"{type(exc).__name__}: {exc}"}
                else:
                    library = updated
                    # Cached normal forms belong to a library version, not to a prefix.
                    reduced_seen.clear()
                epoch["seconds"] = time.perf_counter()-learning_started
                learning_epochs.append(epoch)
                write(args.output/"learning-epochs.json", learning_epochs)
                for candidate in epoch.get("candidates", []):
                    emit("holonomic-search", "lemma_candidate_checked", after_proposal=proposals,
                         candidate=candidate, mathematical_novelty_claimed=False)
                emit("holonomic-search", "lemma_learning_finished", status=epoch["status"],
                     after_proposal=proposals, seconds=epoch["seconds"],
                     library_sha256=library.sha256,
                     accepted_rules=len(epoch.get("library", {}).get("rules", [])),
                     candidate_status_counts=dict(Counter(c["status"] for c in epoch.get("candidates", []))))
            if progress is not None:
                feedback(attempt, row, before_library, library)
        except Exception as exc:
            attempt.update({"status": "error", "error": f"{type(exc).__name__}: {exc}"})
            rows.append({"program": p, "comparison_status": "error", "error": f"{type(exc).__name__}: {exc}"})
            emit("holonomic-search", "operation_failed", proposal=proposals,
                 error=f"{type(exc).__name__}: {exc}")
            if "control_feedback" not in attempt:
                feedback(attempt)
        if len(rows) % 20 == 0:
            write(args.output/"checkpoint.json", {"programs": rows, "relations": relations,
                                                "attempts": attempts, "active_pool": pool.entries,
                                                "action_frontier": frontier.snapshot() if frontier else None,
                                                "systematic_proposals": systematic.snapshot() if systematic else None})
            print(json.dumps({"programs": len(rows), "exact_route_equalities": len(relations)}), flush=True)
            if controller:
                controller.save(args.output/"action-policy-checkpoint.json")
    if controller:
        controller.save(args.output/"action-policy-final.json")
    if args.online_learning:
        final_epoch = next(e for e in reversed(learning_epochs) if e["status"] == "replayed")
        write(args.output/"learned-library-final.json", final_epoch["library"])
    result = {"policy": policy, "programs": rows, "relations": relations, "attempts": attempts,
              "ode_sources": ode_sources,
              "action_frontier": frontier.snapshot() if frontier else None,
              "systematic_proposals": systematic.snapshot() if systematic else None,
              "learned_proposals": learned.snapshot() if learned else None,
              "source_proposals": source.snapshot() if source else None,
              "action_control": {"initial": initial_controller,
                                 "final": controller.to_dict() if controller else None,
                                 "environment": action_environment,
                                 "parameter_holdout_is_not_source_domain_holdout": True},
              "learning_epochs": learning_epochs,
              "representation_progress": progress.snapshot() if progress else None,
              "active_pool": pool.entries,
              "summary": {"programs": len(rows), "status_counts": dict(Counter(r["comparison_status"] for r in rows)),
                          "exact_route_equalities": len(relations), "new_special_value_identities": 0,
                          "definition_only_equalities": sum(r["comparison_status"] == "definition_only_equality" for r in rows),
                          "comparison_attempts": comparisons,
                          "action_updates": sum(a.get("control_feedback", {}).get("updated", False) for a in attempts)
                              + sum(e["feedback"]["updated"] for e in progress.events) if progress else
                              sum(a.get("control_feedback", {}).get("updated", False) for a in attempts),
                          "action_alternatives_inspected": sum(len(a.get("decision", {}).get("alternatives", [])) for a in attempts),
                          "action_offers": sum(len(a.get("decision", {}).get("frontier", {}).get("offered", a.get("decision", {}).get("alternatives", []))) for a in attempts),
                          "action_frontier_pending": len(frontier.pending) if frontier else 0,
                          "action_frontier_reserved_services": sum(a.get("decision", {}).get("frontier", {}).get("reserved", False) and a["decision"]["selected"] is not None for a in attempts),
                          "action_positive_feedback": sum(a.get("control_feedback", {}).get("reward") or 0 for a in attempts)
                              + sum(e["feedback"]["reward"] for e in progress.events) if progress else
                              sum(a.get("control_feedback", {}).get("reward") or 0 for a in attempts),
                          "completed_representation_probes": len(progress.events) if progress else 0,
                          "pending_representation_probes": len(progress.pending) if progress else 0,
                          "learned_construction_candidates": sum(r.get("uses_learned_construction", False) for r in rows),
                          "selected_source_constructions": sum(a.get("status") == "candidate" and
                              a.get("decision", {}).get("selected") is not None and
                              a["decision"]["alternatives"][a["decision"]["selected"]].get("proposal_origin") == "enumerated_source"
                              for a in attempts),
                          "nonseed_comparison_attempts": sum("comparison_index" in r and not r.get("seed", True) for r in rows),
                          "nonseed_exact_equalities": sum(r["comparison_status"] == "exact_formal_series_equality" and not r.get("seed", True) for r in rows),
                          "online_learning_seconds": sum(e.get("seconds", 0) for e in learning_epochs),
                          "online_accepted_rules": len(library.rules) if args.online_learning else 0,
                          "proposals": proposals, "proposal_status_counts": dict(Counter(a["status"] for a in attempts)),
                          "active_pool_entries": len(pool.entries), "seed_pool_entries": len(pool.roots),
                          "pool_merges": sum(not r.get("pool", {"admitted": True})["admitted"] for r in rows),
                          "distinct_prefixes": len(buckets),
                          "library_replay_seconds": library_replay_seconds,
                          "rewritten_programs": sum(bool(r.get("rewrite", {}).get("steps")) for r in rows),
                          "rewrite_steps": sum(len(r.get("rewrite", {}).get("steps", [])) for r in rows),
                          "comparison_seconds": sum(r.get("comparison_seconds", 0) for r in rows),
                          "accepted_hard_problems": 0, "unknown_benchmark_measured": False,
                          "structural_novelty_evaluated": False, "seconds": time.perf_counter()-started},
              "source_unchanged": all(sha256((ROOT/path).read_bytes()).hexdigest() == digest for path, digest in hashes.items()),
              "library_unchanged": not args.learned_library or sha256(args.learned_library.read_bytes()).hexdigest() == policy["library_sha256"]}
    if memory:
        result["construction_memory"] = memory
        result["construction_memory_unchanged"] = sha256(args.construction_memory.read_bytes()).hexdigest() == policy["construction_memory_file_sha256"]
    result["action_policy_unchanged"] = not args.action_policy or sha256(args.action_policy.read_bytes()).hexdigest() == policy["action_policy_sha256"]
    write(args.output/"discovery.json", result)
    emit("holonomic-search", "search_finished", summary=result["summary"],
         source_unchanged=result["source_unchanged"], library_unchanged=result["library_unchanged"],
         artifact=str((args.output/"discovery.json").resolve()))
    print(json.dumps(result["summary"]), flush=True)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--worker":
        pair = read_artifact(Path(sys.argv[2]))
        result = certify_definition_equal(pair["left"], pair["right"]) if pair.get("definition_screen") else None
        if result is not None:
            if not replay_definition_certificate(result):
                raise ValueError("definition-only certificate replay failed")
        else:
            result = certify_equal(pair["left"], pair["right"])
        if result["status"] == "exact_formal_series_equality" and not replay_certificate(result):
            raise ValueError("certificate replay failed")
        print(json.dumps(result), flush=True)
    else:
        main()
