"""Raw-image benchmark adapters for the frozen OLD/NEW comparison.

Environment internals are used exclusively to generate frames and score tasks.
The fitting functions receive saved raw episodes, never hidden state tuples.
"""
from collections import Counter, defaultdict
import copy
import json
import time

import numpy as np

from scripts import evaluate_adaptive_refinement as old
from scripts import integrated_predictive_evaluation as ev
from mortra_predictive_perception.adapters import load_legacy_visual


def train_old(domain, train, heldout, legacy):
    started = time.process_time()
    if domain == "MicroGame":
        classify, prototypes, proto_counts = old.make_classifier()
        streams, online = [], []
        for obs, acts in train:
            labels = [int(classify(frame.reshape(24,24))) for frame in obs]
            streams.append([(None,labels[0])] + list(zip(acts,labels[1:])))
            online.append(labels)
        assert len(streams) == 1
        perception_cpu = time.process_time()-started
        model = old.replay_stream(streams[0],5,"split_merge")
        encode_obs = lambda obs: int(classify(obs.reshape(24,24),eval_mode=True))
        def encode_state(observations, actions):
            # OLD uses its existing bounded context; NEW never receives this bound.
            indices = range(max(0,len(observations)-model.max_depth-1), len(observations))
            context = []
            for i in indices:
                if context: context.append(int(actions[i-1]))
                context.append(encode_obs(observations[i]))
            return model.encode(tuple(context))
        training_labels = [(np.asarray(labels,dtype=float).reshape(-1,1),acts)
                           for labels,(_,acts) in zip(online,train,strict=True)]
        train_states = ev.old_contexts(training_labels,model)
        test_states = [[encode_state(obs[:t+1],acts[:t]) for t in range(len(obs))] for obs,acts in heldout]
        view = ev.NeutralModel(model.actions,dict(enumerate(model.labels)),model.model["rows"],{train_states[0][0]})
        K = old.dense(model.model["K"])
        labels = [None]*len(model.leaf_keys)
        for i,s in enumerate(model.mapping): labels[s] = model.contexts[i][-1]
        audit = ev.audit_operator(labels,[model.actions]*len(labels),model.leaf_counts,
                                  model.model["blocks"],model.model["rows"])
        state_labels = model.labels
        goal_projection = lambda flags: {i for i,label in enumerate(state_labels)
                                         if any(flag and raw_label == label for flag,raw_label in zip(flags,online[0]))}
        return {"model":model,"view":view,"train_states":train_states,"test_states":test_states,
                "encode_obs":encode_obs,"encode_state":encode_state,"K":K,"rows":model.model["rows"],
                "symbols":len(prototypes),"states":len(model.labels),"heap":ev.heap_bytes((vars(model),prototypes,proto_counts)),
                "fit_cpu":time.process_time()-started,"perception_cpu":perception_cpu,"audit":audit,"goal_projection":goal_projection,
                "classifier":classify,"kind":"history"}
    constructor = legacy.VisualStateConstructor(num_actions=5)
    online = []
    for obs,acts in train:
        seq = [constructor.map_observation_to_cluster(obs[0].reshape(24,24))]
        for a,frame in zip(acts,obs[1:],strict=True):
            nxt = constructor.map_observation_to_cluster(frame.reshape(24,24))
            constructor.record_transition(seq[-1],int(a),nxt)
            seq.append(nxt)
        online.append(seq)
    counts_before = copy.deepcopy(constructor.transitions)
    perception_cpu = time.process_time()-started
    constructor.run_behavioral_merge()
    all_states = set(s for seq in online for s in seq)
    K,canonical,index,destinations = constructor.build_k_support(all_states)
    rows = {key:{value:1} for key,value in destinations.items()}
    def encode_obs(obs):
        desc = legacy.extract_visual_descriptor(obs.reshape(24,24))
        distances = [np.linalg.norm(desc-p) for p in constructor.prototypes]
        nearest = int(np.argmin(distances))
        if not distances[nearest] < constructor.vis_dist_thresh: return None
        return index.get(constructor.get_canonical(nearest))
    train_states = [[index[constructor.get_canonical(s)] for s in seq] for seq in online]
    test_states = [[encode_obs(o) for o in obs] for obs,_ in heldout]
    view = ev.NeutralModel(tuple(range(5)),dict(enumerate(canonical)),rows,{train_states[0][0]})
    def neutral_symbol(obs):
        s = encode_obs(obs)
        return canonical[s] if s is not None else None
    blocks = [index[constructor.get_canonical(s)] for s in range(len(constructor.prototypes))]
    # Here the quotient is OLD's modal visual graph, not a certified NEW quotient.
    # Missing quotient rows are compared with zero, rather than fabricated.
    completed_rows = {(blocks[s],a):rows.get((blocks[s],a),{}) for s,a in counts_before}
    audit = ev.audit_operator(list(range(len(blocks))),[tuple(range(5))]*len(blocks),
                             counts_before,blocks,completed_rows)
    goal_projection = lambda flags: {index[constructor.get_canonical(s)] for flag,s in zip(flags,online[0]) if flag}
    return {"model":constructor,"view":view,"train_states":train_states,"test_states":test_states,
            "encode_obs":neutral_symbol,"encode_state":lambda obs,acts:encode_obs(obs[-1]),"K":K,"rows":rows,
            "symbols":len(constructor.prototypes),"states":len(canonical),"heap":ev.heap_bytes(vars(constructor)),
            "fit_cpu":time.process_time()-started,"perception_cpu":perception_cpu,"audit":audit,"goal_projection":goal_projection,
            "kind":"visual","index":index,"canonical":canonical}


def goal_flags(game, actions):
    state = game.get_initial_state()
    flags = [game.is_goal(state)]
    for action in actions:
        state = game.step(state,int(action))
        flags.append(game.is_goal(state))
    return flags


def pure_targets(states, flags):
    truth = defaultdict(set)
    for state,flag in zip(states,flags,strict=True):
        if state is not None: truth[state].add(bool(flag))
    return {s for s,values in truth.items() if values=={True}}, sum(len(v)>1 for v in truth.values())


def noise_schedule(seed, trials, horizon):
    rng = np.random.RandomState(seed+900000)
    result = []
    for _ in range(trials):
        row = []
        for _ in range(horizon+1):
            row.append(rng.get_state())
            rng.normal(0,.02,(24,24))
        result.append(row)
    return result


def rollout(game, render, domain, condition, mode, learned, targets, trials, horizon, schedule):
    """Shared reset/noise/budget. Hidden tuples never enter a policy call."""
    successes = initial_successes = 0
    cpu, trace = 0.0, []
    if condition == "OLD" and mode == "complete" and learned["kind"] == "visual":
        # Legacy evaluation updates prototypes across trials, not just within one.
        constructor = copy.deepcopy(learned["model"])
    psi = None
    if condition == "OLD" and mode == "complete" and targets:
        start = time.process_time()
        psi = old.base.solve_fixed_field(learned["K"],sorted(targets),q=.90)[0]
        cpu += time.process_time()-start
    for trial in range(trials):
        state = game.get_initial_state()
        observations, actions, statuses = [], [], []
        neutral_plan = None
        for t in range(horizon+1):
            if game.is_goal(state):
                successes += 1
                initial_successes += t == 0
                break
            if t == horizon: break
            np.random.set_state(schedule[trial][t])
            frame = render(game,state,t if domain=="MicroGame" else trial*100+t).reshape(-1)
            observations.append(frame)
            if mode == "neutral":
                symbol = learned["encode_obs"](frame) if condition=="OLD" else learned["perception"].encode_history(observations,actions)
                if t==0:
                    belief = learned["view"].begin(symbol)
                    neutral_plan = learned["view"].solve(belief,targets)
                    cpu += neutral_plan["cpu_seconds"]
                else:
                    belief = learned["view"].advance(belief,actions[-1],symbol)
                if belief not in neutral_plan["policy"]: break
                action = neutral_plan["policy"][belief]
            elif condition=="OLD":
                if learned["kind"]=="history":
                    z = learned["encode_state"](observations,actions)
                    choices = {a:row for (s,a),row in learned["rows"].items() if s==z}
                    if psi is None or not choices: break
                    action = max(sorted(choices),key=lambda a:sum(float(p)*psi[v] for v,p in choices[a].items()))
                else:
                    cluster = constructor.get_canonical(constructor.map_observation_to_cluster(frame.reshape(24,24)))
                    z = learned["index"].get(cluster,-1)
                    best, value = None, -1e9
                    field = psi if psi is not None else np.zeros(len(learned["K"]))
                    for a in range(5):
                        row = learned["rows"].get((z,a))
                        if not row: continue
                        score = field[next(iter(row))]
                        if score>value:
                            best,value = a,score
                        elif abs(score-value)<1e-12 and best is not None and (trial+a)%2==0:
                            best = a
                    action = trial%5 if best is None or value<=1e-8 else best
            else:
                perception, world = learned["perception"], learned["world"]
                symbol = perception.encode_history(observations,actions)
                belief = world.begin(symbol) if t==0 else world.update(belief,actions[-1],symbol)
                start = time.process_time()
                plan = world.plan(belief,targets)
                if not plan.actions and plan.guaranteed_steps is None: plan = world.identify(belief)
                cpu += time.process_time()-start
                statuses.append(plan.status)
                if not plan.actions: break
                action = min(plan.actions)
            state = game.step(state,int(action))
            actions.append(int(action))
        trace.append({"trial":trial,"success":game.is_goal(state),"actions":actions,"statuses":statuses})
    return {"trials":trials,"successes":successes,"success":successes/trials,
            "success_at_reset":initial_successes,"reasoning_cpu":cpu,"tasks":trace,
            "goal_scope":"post-fit observed task labels; empirical guarantees are not environment proofs"}


def evaluate(case, train, heldout, hidden_path, config, root, folder, fit_new, save, progress):
    legacy = load_legacy_visual(root/"scripts/evaluate_visual_state_construction.py")
    trained = {}
    progress("OLD raw training")
    trained["OLD"] = train_old(case["domain"],train,heldout,legacy)
    for condition,target in (("NEW-ABS","absolute"),("NEW-DELTA","delta")):
        progress(f"{condition} full raw reference/equality gate")
        perception,world,train_symbols,test_symbols,costs = fit_new(train,heldout,tuple(range(5)),target,folder)
        trained[condition] = {"perception":perception,"world":world,"train_symbols":train_symbols,
                              "test_symbols":test_symbols,"costs":costs,
                              "view":ev.NeutralModel(world.actions,world.emissions,world.operators,world.initial)}
    # Fit above did not receive a game, hidden labels or task goals.
    hidden = json.loads(hidden_path.read_text(encoding="utf-8"))
    environment = old.base if case["domain"]=="MicroGame" else legacy
    game = environment.MicroGame(seed=case["spec"]["seed"])
    game.generate_random(wall_density=.18)
    flags = goal_flags(game,train[0][1])
    truth = [tuple(s) for states in hidden for s in states]
    raw = [o for obs,_ in heldout for o in obs]
    schedule = noise_schedule(case["spec"]["seed"],case["evaluation_trials"],config["planning_horizon"])
    result = {}
    condition_assignments = {}
    for condition,learned in trained.items():
        if condition=="OLD":
            test_states = learned["test_states"]
            train_states = learned["train_states"]
            means = ev.old_response_means(train,train_states)
            quality = ev.response_error(heldout,test_states,lambda s,a:means[s,a],"delta")
            memory, _ = ev.ambiguity_diagnostics(raw,truth,[s for seq in test_states for s in seq])
            memory["recursive_full_history_agreement"] = None
            audit = learned["audit"]
            audit["old_visual_merge_is_not_assumed_congruent"] = True
            quality.update(states=learned["states"],symbols=learned["symbols"],fit_cpu=learned["fit_cpu"],
                           perception_cpu=learned["perception_cpu"],model_memory_bytes=learned["heap"],selected_history_depth_distribution=None)
            costs = {"old_perception_and_world_cpu":learned["fit_cpu"],"perception_cpu":learned["perception_cpu"]}
            complete_targets = learned["goal_projection"](flags)
        else:
            perception,world = learned["perception"],learned["world"]
            records,test_states,memory_costs = ev.memory_records(world,heldout,learned["test_symbols"])
            save(folder/f"{condition}_belief_records.json",records)
            assert all(r["agrees"] for r in records)
            train_states = [[world.certificate["blocks"][p] for p in path] for _,_,path in world.episodes]
            quality = ev.response_error(heldout,learned["test_symbols"],perception.predict_response,perception.target)
            quality.update(states=len(world.emissions),symbols=perception.report.generated_symbols,
                           fit_cpu=learned["costs"]["sweep"]["cpu_seconds"]+learned["costs"]["world_and_quotient_cpu"],
                           perception_cpu=learned["costs"]["sweep"]["cpu_seconds"],model_memory_bytes=ev.heap_bytes((vars(perception),vars(world))),
                           selected_history_depth_distribution=ev.available_depths(perception,heldout))
            memory,_ = ev.ambiguity_diagnostics(raw,truth,[s for seq in test_states for s in seq])
            symbol_ambiguity,_ = ev.ambiguity_diagnostics(raw,truth,[s for seq in learned["test_symbols"] for s in seq])
            memory.update(steps=len(records),agreement_count=sum(r["agrees"] for r in records),recursive_full_history_agreement=1.0,
                          unknown_steps=sum(r["unknown"] for r in records),contradiction_steps=sum(r["contradiction"] for r in records),
                          symbol_collision_pairs=symbol_ambiguity["collision_pairs"])
            memory.update(ev.memory_agreement_summary(records))
            counts = {(s,int(a)):c for (s,a),c in world.counts.items()}
            audit = ev.audit_operator(world.labels,[world.actions]*len(world.labels),counts,
                                      world.certificate["blocks"],world.certificate["rows"])
            assert audit["eps_action"]==0
            audit["new_world_contains_q"] = False
            costs = {"perception_cpu":learned["costs"]["sweep"]["cpu_seconds"],
                     "reference_validation_fit_cpu":learned["costs"]["reference"]["cpu_seconds"],
                     "equivalence_and_encoding_cpu":learned["costs"]["equivalence_and_encoding_cpu"],
                     "world_and_quotient_cpu":learned["costs"]["world_and_quotient_cpu"],**memory_costs}
            complete_targets,_ = pure_targets(train_states[0],flags)
        diagnostic = ev.common_partition([s for seq in test_states for s in seq],truth)
        quality.update(false_merge=diagnostic["false_merge"],false_split=diagnostic["false_split"],
                       predictive_violation=None,hidden_state_partition_diagnostic=diagnostic,
                       truth_scope="hidden simulator-state identity only; NOT the minimal predictive quotient of noisy time-dependent images")
        memory["same_observation_scope"] = "exact equality of raw pixel arrays; no rounding or hidden-state features used as an observation"
        neutral_targets,mixed = pure_targets(train_states[0],flags)
        neutral = rollout(game,environment.render_visual_frame,case["domain"],condition,"neutral",learned,
                          neutral_targets,case["evaluation_trials"],config["planning_horizon"],schedule)
        complete = rollout(game,environment.render_visual_frame,case["domain"],condition,"complete",learned,
                           complete_targets,case["evaluation_trials"],config["planning_horizon"],schedule)
        complete["training_trace_reuse"] = ev.trace_reuse_audit(complete["tasks"],train)
        neutral["mixed_goal_states"] = mixed
        costs.update(reasoning_cpu=complete["reasoning_cpu"],neutral_reasoning_cpu=neutral["reasoning_cpu"])
        result[condition] = {"status":"COMPLETE","world_model":quality,"memory":memory,"operator":audit,
                             "neutral":neutral,"complete_system":complete,"compute":costs}
        condition_assignments[condition] = [s for seq in test_states for s in seq]
    for condition, diagnostic in ev.paired_partitions(condition_assignments,truth).items():
        result[condition]["world_model"].update(
            false_merge=diagnostic["false_merge"],false_split=diagnostic["false_split"],
            known_assignment_fraction=diagnostic["known_assignment_fraction"],
            paired_evaluable_fraction=diagnostic["paired_evaluable_fraction"],
            hidden_state_partition_diagnostic=diagnostic)
    return result
