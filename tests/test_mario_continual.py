from pathlib import Path
from collections import Counter
from types import MethodType, SimpleNamespace

import numpy as np

from experiments.continual_tools import ProgramLibrary
from experiments.mario_continual.evidence import LiveRGBRegistry
from experiments.mario_continual.port import BUTTON_MASKS, MarioRGBPort
from experiments.mario_continual.predictive import PredictiveBelief, PredictiveRegistry
from experiments.mario_continual.run import ContinualMario


def test_mario_action_alphabet_is_the_existing_twelve_button_masks():
    assert BUTTON_MASKS == (0, 1, 2, 16, 17, 18, 8, 9, 10, 24, 25, 26)
    assert len(set(BUTTON_MASKS)) == 12


def test_repeated_observation_batches_without_steps(monkeypatch, tmp_path):
    port = MarioRGBPort(tmp_path, tmp_path, tmp_path/"bridge.java", "level", tmp_path/"run")
    port.last_packet = {"kind": "observation", "frame": 7}
    writes = []

    class Stdin:
        def write(self, value): writes.append(value)
        def flush(self): pass

    class Process:
        stdin = Stdin()
        def poll(self): return None

    port.process = Process()

    def read():
        packet = {"kind": "observation_batch", "frame": 7,
                  "_batch": np.zeros((4, 2, 2, 3), dtype=np.uint8)}
        port.last_packet = packet
        return packet

    monkeypatch.setattr(port, "_read", read)
    images, packets = port.repeated_observation(4)
    assert images.shape == (4, 2, 2, 3)
    assert writes == ["SNAPN 4\n"]
    assert packets[0]["frame"] == 7
    assert port.primitive_frames == 0
    assert port.actions == []


def test_java_bridge_has_nonadvancing_snap_protocol():
    source = (Path(__file__).parents[1] / "experiments" / "mario_continual" /
              "java" / "MortraBridge.java").read_text(encoding="utf8")
    assert 'line.equals("SNAP")' in source
    assert "capture()" in source
    assert "Expected SNAP, DUMP, SNAPN n, or STEP" in source
    assert "MappedByteBuffer" in source
    assert "SHA-256" in source
    assert "ImageIO" not in source
    assert "runGame(" in source and ", 0, visuals, 0, 1f)" in source
    # Repeated capture happens inside the command loop before STEP returns held
    # buttons to MarioGame.
    assert source.index('line.equals("SNAP")') < source.index('parts[0].equals("STEP")')


def test_one_step_counterexample_splits_visual_alias_and_becomes_active_probe():
    memory = PredictiveRegistry(2)

    first = memory.belief("A", ())
    assert first.candidates == (0,)
    target, source = memory.update(first, 0, "B", (), (0,))
    assert source == 0 and target.resolved_state == 1

    # A later context has the same current observation A, so it is not assigned
    # a new graph node merely because its history is different.
    alias = memory.belief("A", (1, 1))
    assert alias.candidates == (0,) and alias.new_state_possible

    # Its action-0 future is C, contradicting q0's already observed A--0-->B.
    target2, split = memory.update(alias, 0, "C", (1, 1), (1, 1, 0))
    assert split not in (None, 0)
    assert memory.state_observation[split] == "A"
    assert target2.resolved_state is not None
    # The discriminating action is inferred from the learned successor
    # observations rather than a fixed action name.
    # Exact histories now resolve their previously evidenced context directly;
    # a genuinely unseen history still exposes the visual aliases and therefore
    # has an identifying action.
    assert memory.belief("A", ()).resolved_state == 0
    unseen = memory.belief("A", (2, 2))
    assert set(unseen.candidates) == {0, split}
    assert memory.choose_identifying_action(unseen) == 0


def test_noisy_rgb_path_uses_batched_remeasurement_and_replay():
    class FakePort:
        def __init__(self):
            self.last_hash = "current-a"
            self.last_packet = {"frame": 3}
            self.calls = []
        def snap_hash(self):
            self.last_hash = "current-b"
            return self.last_hash, {"kind": "observation", "frame": 3}
        def repeated_observation(self, samples):
            self.calls.append(("repeat", samples))
            return np.zeros((samples, 2, 2, 3), dtype=np.uint8), [{"frame": 3}]

    replays = []
    def replay(history, samples):
        replays.append((history, samples))
        return np.full((samples, 2, 2, 3), 255, dtype=np.uint8)

    registry = LiveRGBRegistry(stages=(8,16,32), device="cpu")
    registry.prototypes.append({"history": (1,), "exact_hash": None})
    port = FakePort()
    belief = registry.observe(port, (2,), replay=replay, allow_new=True)
    assert belief.resolved_state == 1
    assert registry.prototypes[1]["history"] == (2,)
    assert port.calls == [("repeat",16),("repeat",32),("repeat",64)]
    assert replays == [((1,),16),((1,),32),((1,),64)]


def test_runner_learns_matches_and_executes_tool_without_bypassing_evidence():
    runner = object.__new__(ContinualMario)
    runner.tools = ProgramLibrary(3)
    runner.sequence_counts = Counter()
    runner.recent = []
    runner.events = []
    runner.emit = lambda event, **values: runner.events.append((event, values))
    runner.memory = PredictiveRegistry(3)

    # Repeating the same resolved path twice is the current admission rule.
    chain = [(0,0,1),(1,1,2)]
    runner.recent = chain.copy()
    ContinualMario.learn_tools(runner)
    assert not runner.tools.records
    runner.recent.extend(chain)
    ContinualMario.learn_tools(runner)
    assert len(runner.tools.records) == 1

    belief0 = PredictiveBelief("A", (0,), False)
    token = ContinualMario.matching_tool(runner, belief0, 0)
    assert token is not None
    # A multi-step program may only substitute for control when its complete
    # primitive expansion is a prefix of the planner's current route.
    assert ContinualMario.matching_tool(
        runner, belief0, 0, planned_actions=(0, 2)) is None
    assert ContinualMario.matching_tool(
        runner, belief0, 0, planned_actions=(0, 1, 2)) == token

    outcomes = [
        ({"kind":"observation","frame":1}, PredictiveBelief("B",(1,),False)),
        ({"kind":"observation","frame":2}, PredictiveBelief("C",(2,),False)),
    ]
    def one_primitive(self, port, history, belief, action, reason):
        history.append(action)
        return outcomes.pop(0)
    runner.one_primitive = MethodType(one_primitive, runner)

    packet, final_belief, used = ContinualMario.run_tool(
        runner, token, object(), [], belief0)
    assert used
    assert packet["frame"] == 2
    assert final_belief.resolved_state == 2
    assert runner.tools.records[token]["status"] == "reused"
    assert any(event == "tool_invoked" for event, _ in runner.events)
    assert any(e["event"] == "tool_reused" for e in runner.tools.events)
