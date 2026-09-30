"""Run one persistent MORTRA until the real Mario engine reports WIN.

The stopping objective is game completion, not a fixed training budget. Optional
limits exist only for infrastructure that cannot run indefinitely; every such
exit writes a resumable checkpoint.  Death/time-out starts a new episode without
resetting predictive memory, evidence, tools, or learned goal structure.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import json
import pickle
from pathlib import Path
import time

from experiments.accelerator import device_info
from experiments.continual_tools import ProgramLibrary
from experiments.continual_tools.conditional import (
    ConditionalProgramModel, PREDICTED, UNRESOLVED as CONDITIONAL_UNRESOLVED)
from experiments.mario_continual.evidence import LiveRGBRegistry
from experiments.mario_continual.port import MarioRGBPort
from experiments.mario_continual.predictive import PredictiveRegistry
from experiments.task_agent.core import ExactState, ProductPlanner, SequenceTask
from experiments.task_agent.virtual_frontier import VirtualFrontierPolicy


@dataclass
class NullTask:
    initial_memory: int = 0
    def advance(self, memory, world_state): return 0
    def accepting(self, memory): return False
    def progress(self, memory): return 0.0


class GoalTask:
    def __init__(self, goals):
        self.goals = frozenset(goals)
        self.initial_memory = 0

    def advance(self, memory, world_state):
        return 1 if memory or world_state in self.goals else 0

    def accepting(self, memory):
        return bool(memory)

    def progress(self, memory):
        return float(bool(memory))


def resolved_observation(belief):
    if belief.resolved_state is None:
        return None
    return int(belief.resolved_state)


def atomic_write(path, payload):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(payload)
    tmp.replace(path)


def save_checkpoint(path, state):
    atomic_write(path, pickle.dumps(state, protocol=pickle.HIGHEST_PROTOCOL))


def load_checkpoint(path):
    with Path(path).open("rb") as handle:
        return pickle.load(handle)


class ContinualMario:
    def __init__(self, args):
        self.args = args
        self.output = args.output.resolve()
        self.output.mkdir(parents=True, exist_ok=True)
        self.checkpoint_path = self.output / "checkpoint.pkl"
        self.events_path = self.output / "events.jsonl"

        if args.resume and self.checkpoint_path.exists():
            saved = load_checkpoint(self.checkpoint_path)
            self.vision = saved["vision"]
            self.vision.device = args.device
            self.memory = saved["memory"]
            self.tools = saved["tools"]
            self.sequence_counts = saved["sequence_counts"]
            self.recent = saved["recent"]
            self.episodes = saved["episodes"]
            self.decisions = saved["decisions"]
            self.primitive_actions = saved["primitive_actions"]
            self.replay_frames = saved["replay_frames"]
            self.replays = saved["replays"]
            self.first_clear = saved.get("first_clear")
            self.program_context_counts = saved.get("program_context_counts", Counter())
            self.program_use_counts = saved.get("program_use_counts", Counter())
            self.program_complete_counts = saved.get("program_complete_counts", Counter())
            self.conditional_model = saved.get("conditional_model", ConditionalProgramModel())
            self.conditional_stats = saved.get("conditional_stats", Counter())
        else:
            self.vision = LiveRGBRegistry(device=args.device)
            self.memory = PredictiveRegistry(12)
            self.tools = ProgramLibrary(12)
            self.sequence_counts = Counter()
            self.recent = []
            self.episodes = 0
            self.decisions = 0
            self.primitive_actions = 0
            self.replay_frames = 0
            self.replays = 0
            self.first_clear = None
            self.program_context_counts = Counter()
            self.program_use_counts = Counter()
            self.program_complete_counts = Counter()
            self.conditional_model = ConditionalProgramModel()
            self.conditional_stats = Counter()

        self.frontier = VirtualFrontierPolicy(task_aware=False, task_source=False)
        self.planner = ProductPlanner(q=.90)
        self._frontier_cache = {}
        self._goal_cache = {}
        self.started = time.monotonic()
        self._event_handle = self.events_path.open("a", encoding="utf8", buffering=1)

    def emit(self, event, **values):
        row = dict(event=event, time=time.time(), decisions=self.decisions,
                   primitive_actions=self.primitive_actions, episode=self.episodes, **values)
        self._event_handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")

    def checkpoint(self, reason):
        state = dict(
            vision=self.vision, memory=self.memory, tools=self.tools,
            sequence_counts=self.sequence_counts, recent=self.recent,
            episodes=self.episodes, decisions=self.decisions,
            primitive_actions=self.primitive_actions,
            replay_frames=self.replay_frames, replays=self.replays,
            first_clear=self.first_clear,
            program_context_counts=self.program_context_counts,
            program_use_counts=self.program_use_counts,
            program_complete_counts=self.program_complete_counts,
            conditional_model=self.conditional_model,
            conditional_stats=self.conditional_stats,
        )
        save_checkpoint(self.checkpoint_path, state)
        summary = self.summary(reason)
        (self.output / "status.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n", encoding="utf8")
        self.emit("checkpoint", reason=reason, summary=summary)

    def summary(self, reason="status"):
        return dict(
            reason=reason,
            episodes=self.episodes,
            decisions=self.decisions,
            primitive_actions=self.primitive_actions,
            replay_frames=self.replay_frames,
            replays=self.replays,
            predictive_states=len(self.memory.id_to_state),
            known_state_action_pairs=len(self.memory.counts),
            observation_classes=len(self.vision.prototypes),
            goal_states=sorted(self.memory.goal_states),
            learned_tools=len(self.tools.records),
            reused_tools=sum(e["event"] == "tool_reused" for e in self.tools.events),
            refuted_tools=sum(e["event"] == "tool_counterexample" for e in self.tools.events),
            unique_programs=len(self.learned_programs()),
            portable_programs=len(self.portable_programs()),
            transferred_programs=sum(count > 0 for count in self.program_use_counts.values()),
            program_transfer_invocations=sum(self.program_use_counts.values()),
            program_transfer_completions=sum(self.program_complete_counts.values()),
            tool_policy=self.args.tool_policy,
            conditional_prediction_attempts=self.conditional_stats["attempts"],
            conditional_predictions=self.conditional_stats["predicted"],
            conditional_prediction_correct=self.conditional_stats["correct"],
            conditional_prediction_wrong=self.conditional_stats["wrong"],
            conditional_unresolved=self.conditional_stats["unresolved"],
            conditional_precision=(
                self.conditional_stats["correct"] /
                max(1, self.conditional_stats["correct"] + self.conditional_stats["wrong"])
            ),
            first_clear=self.first_clear,
            accelerator=device_info(self.args.device),
            wall_seconds=time.monotonic() - self.started,
        )

    def replay_samples(self, history, samples):
        """Reset/replay an exact action history in a separate real game process."""
        replay_id = self.replays
        self.replays += 1
        directory = self.output / "replays" / f"replay_{replay_id:07d}"
        port = MarioRGBPort(
            self.args.game_dir, self.args.build_dir, self.args.bridge_source,
            self.args.level, directory, seconds=self.args.seconds,
            frames_per_action=self.args.frames_per_action)
        try:
            _, packet = port.start()
            if packet["kind"] != "observation":
                raise RuntimeError("replay failed at initial observation")
            for action in history:
                _, packet = port.step(action)
                if packet["kind"] != "observation":
                    raise RuntimeError(
                        f"replay history terminated early with {packet.get('status')}")
            images, _ = port.repeated_observation(samples)
            self.replay_frames += port.primitive_frames
            return images
        finally:
            port.close()

    def observe(self, port, history):
        return self.vision.observe(
            port, history,
            replay=lambda prototype_history, n: self.replay_samples(prototype_history, n),
            allow_new=True)

    def initial_predictive_belief(self, observation_belief, history):
        observation = resolved_observation(observation_belief)
        if observation is None:
            # Vision itself has not resolved membership.  Do not invent a
            # predictive state from an ambiguous percept.
            return None
        return self.memory.belief(observation, history)

    def choose_primitive(self, belief):
        if belief is None:
            # This should be rare because exact blocked-frame capture normally
            # gives a unique visual class.  Use least-used primitive globally
            # rather than materialising the unresolved percept as a state.
            visits = [sum(self.memory.action_visits.get((q, a), 0)
                          for q in range(len(self.memory.id_to_state)))
                      for a in range(self.memory.num_actions)]
            return min(range(self.memory.num_actions), key=lambda a: (visits[a], a)), "unresolved_visual"

        if len(belief.candidates) > 1:
            action = self.memory.choose_identifying_action(belief)
            if action is not None:
                return int(action), "active_identification"

        q = belief.resolved_state
        if q is not None:
            token = self.memory.state_token(q)
            version = getattr(self.memory, "structure_version", 0)
            if self.memory.goal_states:
                goal_ids = tuple(sorted(self.memory.goal_states))
                cache_key = (version, q, goal_ids)
                if cache_key in self._goal_cache:
                    return self._goal_cache[cache_key], "goal_field_cached"
                goals = {self.memory.state_token(g) for g in goal_ids}
                task = GoalTask(goals)
                action = self.planner.choose_action(
                    self.memory, task, token, task.initial_memory)
                if action is not None:
                    action = int(action)
                    self._goal_cache[cache_key] = action
                    return action, "goal_field"

            cache_key = (version, q)
            if cache_key in self._frontier_cache:
                return self._frontier_cache[cache_key], "virtual_frontier_cached"
            decision = self.frontier.choose(
                self.memory, token, NullTask(), 0)
            action = int(decision.action)
            telemetry = getattr(self.frontier, "last_telemetry", None) or {}
            if telemetry.get("virtual_field_decision"):
                self._frontier_cache[cache_key] = action
            return action, "virtual_frontier"

        # Candidate uncertainty with no currently separating action: explore the
        # least observed primitive over all candidates.
        visits = []
        for action in range(self.memory.num_actions):
            total = sum(self.memory.action_visits.get((q, action), 0)
                        for q in belief.candidates)
            visits.append(total)
        return min(range(self.memory.num_actions), key=lambda a: (visits[a], a)), "belief_frontier"

    def learn_tools(self):
        # A tool candidate must be a repeated *resolved* transition word. This
        # does not invent state identity and does not require reward.
        max_len = 6
        chain = self.recent[-max_len:]
        for length in range(2, min(max_len, len(chain)) + 1):
            segment = chain[-length:]
            if any(segment[i][2] != segment[i+1][0] for i in range(len(segment)-1)):
                continue
            start = segment[0][0]
            actions = tuple(item[1] for item in segment)
            expected = tuple(item[2] for item in segment)
            key = (start, actions, expected)
            self.sequence_counts[key] += 1
            if self.sequence_counts[key] == 2:
                token = self.tools.register(
                    actions, guard=start, expected_states=expected,
                    source="repeated_resolved_transition",
                    metadata={"observations": 2})
                self.emit("tool_learned", tool=token, guard=start,
                          actions=list(actions), expected_states=list(expected))

    def matching_tool(self, belief, preferred_action):
        q = None if belief is None else belief.resolved_state
        if q is None:
            return None
        choices = []
        for token, record in self.tools.records.items():
            if record["status"] == "refuted" or record["guard"] != q:
                continue
            expansion = self.tools.flatten_token(token)
            if not expansion or expansion[0] != preferred_action:
                continue
            choices.append((len(expansion), token))
        return max(choices)[1] if choices else None

    def learned_programs(self):
        """Return one canonical token per distinct executable primitive word.

        Program identity is the primitive action word.  Exact-state tool records
        remain context-specific certificates about where that word was observed.
        This separation is invariant under predictive-state ID renaming.
        """
        programs = {}
        for token in sorted(self.tools.records):
            actions = tuple(self.tools.flatten_token(token))
            if len(actions) < 2:
                continue
            programs.setdefault(actions, token)
        return programs

    def program_support(self):
        """Observed independent contexts supporting each executable word.

        One exact context cannot distinguish a genuinely reusable program from a
        state-specific coincidence.  Two distinct guards are the minimum direct
        evidence of cross-context recurrence, so only words with support >=2 are
        admitted to the portable program frontier.
        """
        support = {}
        for token, record in self.tools.records.items():
            actions = tuple(self.tools.flatten_token(token))
            if len(actions) < 2:
                continue
            support.setdefault(actions, set()).add(record["guard"])
        return support

    def portable_programs(self):
        programs = self.learned_programs()
        support = self.program_support()
        return {
            actions: (token, len(support.get(actions, ())))
            for actions, token in programs.items()
            if len(support.get(actions, ())) >= 2
        }

    def choose_transfer_program(self, belief, preferred_action):
        """Choose a learned macro frontier option.

        program_frontier transfers any independently recurrent executable word
        after its first primitive edge is known.

        conditional_frontier adds the missing P=>R layer: it transfers only
        when structural evidence from prior contexts predicts one unambiguous
        effect relation.  Missing evidence is UNRESOLVED and does not count as
        a failure or counterexample.
        """
        if self.args.tool_policy not in ("program_frontier", "conditional_frontier") or belief is None:
            return None
        q = belief.resolved_state
        if q is None:
            return None
        if (q, int(preferred_action)) not in self.memory.counts:
            return None

        candidates = []
        saw_unresolved = False
        for actions, (token, support_count) in self.portable_programs().items():
            if actions[0] != int(preferred_action):
                continue
            if self.program_context_counts[(q, actions)] != 0:
                continue

            prediction = None
            if self.args.tool_policy == "conditional_frontier":
                self.conditional_stats["attempts"] += 1
                prediction = self.conditional_model.predict(
                    self.tools, self.memory, q, actions)
                if prediction.status != PREDICTED:
                    saw_unresolved = True
                    self.conditional_stats["unresolved"] += 1
                    continue

            global_uses = self.program_use_counts[actions]
            predicted_support = 0 if prediction is None else prediction.support
            candidates.append((
                global_uses, -predicted_support, -support_count,
                -len(actions), actions, token))

        if not candidates:
            return None
        _, _, _, _, actions, token = min(candidates)
        return token, actions

    def run_transfer_program(self, token, actions, port, history, belief):
        """Execute a program in a new context and update conditional evidence."""
        q = None if belief is None else belief.resolved_state
        if q is None:
            return None, belief, False
        actions = tuple(int(a) for a in actions)
        prediction = None
        if self.args.tool_policy == "conditional_frontier":
            prediction = self.conditional_model.predict(
                self.tools, self.memory, q, actions)
            if prediction.status != PREDICTED:
                # Selection should already have filtered this.  Preserve the
                # three-valued semantics if graph evidence changed meanwhile.
                return None, belief, False
            self.conditional_stats["predicted"] += 1

        self.program_context_counts[(q, actions)] += 1
        self.program_use_counts[actions] += 1
        support_count = len(self.program_support().get(actions, ()))
        self.emit("program_transfer_invoked", tool=token, source_state=q,
                  actions=list(actions), global_uses=self.program_use_counts[actions],
                  support_contexts=support_count,
                  predicted_effect=None if prediction is None else prediction.effect,
                  prediction_support=0 if prediction is None else prediction.support)

        current = belief
        packet = None
        executed = []
        state_path = [q]
        for action in actions:
            packet, target = self.one_primitive(
                port, history, current, action, "learned_program_transfer")
            executed.append(int(action))
            if target is None or target.resolved_state is None:
                self.emit("program_transfer_stopped", tool=token, source_state=q,
                          actions=list(actions), executed=executed,
                          status="UNRESOLVED_VISUAL")
                return packet, current, True
            current = target
            state_path.append(int(target.resolved_state))
            if packet["kind"] == "terminal":
                break

        completed = len(executed) == len(actions)
        actual_effect = None
        if completed:
            self.program_complete_counts[actions] += 1
            actual_effect = self.conditional_model.observe_transfer(
                self.memory, q, actions, state_path)
            if prediction is not None and actual_effect is not None:
                if actual_effect == prediction.effect:
                    self.conditional_stats["correct"] += 1
                    prediction_result = "CORRECT"
                else:
                    self.conditional_stats["wrong"] += 1
                    prediction_result = "COUNTEREXAMPLE"
            else:
                prediction_result = None
        else:
            prediction_result = None

        self.emit("program_transfer_completed" if completed else "program_transfer_stopped",
                  tool=token, source_state=q, actions=list(actions),
                  executed=executed, status=packet.get("status") if packet else None,
                  target_state=current.resolved_state if current is not None else None,
                  actual_effect=actual_effect,
                  prediction_result=prediction_result)
        return packet, current, True

    def one_primitive(self, port, history, belief, action, reason):
        source_history = tuple(history)
        _, packet = port.step(action)
        self.primitive_actions += 1
        history.append(int(action))

        terminal = packet["kind"] == "terminal"
        status = packet.get("status") if terminal else None
        if terminal:
            target_observation = ("terminal", status)
            target, source_resolved = self.memory.update(
                belief, action, target_observation,
                source_history, tuple(history), terminal_status=status)
        else:
            observation_belief = self.observe(port, tuple(history))
            observation = resolved_observation(observation_belief)
            if observation is None:
                # Preserve uncertainty without declaring a counterexample.
                target = None
                source_resolved = None
            else:
                target, source_resolved = self.memory.update(
                    belief, action, observation,
                    source_history, tuple(history))

        if source_resolved is not None and target is not None and target.resolved_state is not None:
            self.recent.append((source_resolved, int(action), target.resolved_state))
            if len(self.recent) > 64:
                del self.recent[:-64]
            self.learn_tools()

        self.emit("primitive_step", action=int(action), reason=reason,
                  terminal=status, source_candidates=[] if belief is None else list(belief.candidates),
                  target_candidates=[] if target is None else list(target.candidates))
        return packet, target

    def run_tool(self, token, port, history, belief):
        running = self.tools.begin(token, belief)
        if not hasattr(running, "next_action"):
            return None, belief, False
        self.emit("tool_invoked", tool=token,
                  actions=list(self.tools.flatten_token(token)))
        current = belief
        while not running.done:
            action = running.next_action()
            packet, target = self.one_primitive(port, history, current, action, "learned_tool")
            if target is None:
                self.emit("tool_stopped", tool=token, status="UNRESOLVED_VISUAL")
                return packet, current, True
            evidence = running.observe(target)
            current = target
            if evidence is not None and evidence.status != "SAME":
                self.emit("tool_stopped", tool=token, status=evidence.status)
                return packet, current, True
            if packet["kind"] == "terminal":
                return packet, current, True
        return packet, current, True

    def limits_reached(self):
        if self.args.max_primitive_actions and self.primitive_actions >= self.args.max_primitive_actions:
            return "infrastructure_primitive_action_limit"
        if self.args.max_decisions and self.decisions >= self.args.max_decisions:
            return "infrastructure_decision_limit"
        if self.args.max_episodes and self.episodes >= self.args.max_episodes:
            return "infrastructure_episode_limit"
        if self.args.max_wall_seconds and time.monotonic()-self.started >= self.args.max_wall_seconds:
            return "infrastructure_wall_limit"
        return None

    def run(self):
        self.emit("run_started", resume=bool(self.args.resume),
                  objective="Mario engine status WIN")
        while self.first_clear is None:
            limit = self.limits_reached()
            if limit:
                self.checkpoint(limit)
                return self.summary(limit)

            episode = self.episodes
            self.episodes += 1
            directory = self.output / "episodes" / f"episode_{episode:07d}"
            port = MarioRGBPort(
                self.args.game_dir, self.args.build_dir, self.args.bridge_source,
                self.args.level, directory, seconds=self.args.seconds,
                frames_per_action=self.args.frames_per_action)
            history = []
            try:
                _, packet = port.start()
                observation_belief = self.observe(port, ())
                belief = self.initial_predictive_belief(observation_belief, ())
                self.emit("episode_started",
                          visual_status=observation_belief.status,
                          predictive_candidates=[] if belief is None else list(belief.candidates))

                while packet["kind"] == "observation":
                    limit = self.limits_reached()
                    if limit:
                        self.checkpoint(limit)
                        return self.summary(limit)

                    action, reason = self.choose_primitive(belief)
                    self.decisions += 1

                    transfer = self.choose_transfer_program(belief, action)
                    if transfer is not None:
                        token, actions = transfer
                        packet, belief, used = self.run_transfer_program(
                            token, actions, port, history, belief)
                    else:
                        # Keep the exact-context certified path as exploitation
                        # in both modes. program_frontier is a strict extension:
                        # it adds untried cross-context program options before it.
                        token = self.matching_tool(belief, action)
                        if token is not None:
                            packet, belief, used = self.run_tool(token, port, history, belief)
                        else:
                            packet, belief = self.one_primitive(
                                port, history, belief, action, reason)

                    if self.primitive_actions % self.args.checkpoint_every == 0:
                        self.checkpoint("periodic")
                        print(json.dumps(self.summary("RUNNING")), flush=True)

                status = packet.get("status")
                self.emit("episode_terminal", status=status,
                          episode_primitive_frames=port.primitive_frames,
                          completion_audit_only=packet.get("completion_audit_only"))
                if status == "WIN":
                    self.first_clear = dict(
                        episode=episode,
                        decisions=self.decisions,
                        primitive_actions=self.primitive_actions,
                        engine_frames=port.primitive_frames,
                        history=list(history),
                        wall_seconds=time.monotonic()-self.started,
                        predictive_states=len(self.memory.id_to_state),
                        learned_tools=len(self.tools.records),
                    )
                    self.checkpoint("FIRST_CLEAR")
                    (self.output / "FIRST_CLEAR.json").write_text(
                        json.dumps(self.first_clear, indent=2) + "\n", encoding="utf8")
                    print(json.dumps(dict(event="FIRST_CLEAR", **self.first_clear)), flush=True)
                    return self.summary("FIRST_CLEAR")
            finally:
                port.close()

            self.checkpoint("episode_end")
            print(json.dumps(self.summary("RUNNING")), flush=True)

        return self.summary("FIRST_CLEAR")


def parse_args():
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--game-dir", type=Path, default=root/"game")
    parser.add_argument("--build-dir", type=Path, default=root/"build")
    parser.add_argument("--bridge-source", type=Path, default=root/"java"/"MortraBridge.java")
    parser.add_argument("--level", default="levels/notch/lvl-1.txt")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--frames-per-action", type=int, default=8)
    parser.add_argument("--checkpoint-every", type=int, default=100)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto",
                        help="CUDA accelerates RGB statistics/FFT only; core graph reasoning remains CPU")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--tool-policy",
        choices=("legacy", "program_frontier", "conditional_frontier"),
        default="legacy",
        help="exact-state tools, unconditional cross-context programs, or learned P=>R transfer")
    # Zero means no algorithmic stop. These are infrastructure escape hatches.
    parser.add_argument("--max-primitive-actions", type=int, default=0)
    parser.add_argument("--max-decisions", type=int, default=0)
    parser.add_argument("--max-episodes", type=int, default=0)
    parser.add_argument("--max-wall-seconds", type=float, default=0.)
    args = parser.parse_args()
    if args.checkpoint_every < 1:
        parser.error("--checkpoint-every must be positive")
    return args


def main():
    args = parse_args()
    runner = ContinualMario(args)
    try:
        result = runner.run()
        print(json.dumps(result, indent=2, default=str))
    finally:
        runner._event_handle.close()


if __name__ == "__main__":
    main()
