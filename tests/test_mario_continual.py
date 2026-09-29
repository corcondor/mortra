from pathlib import Path

import numpy as np

from experiments.mario_continual.port import BUTTON_MASKS, MarioRGBPort
from experiments.mario_continual.predictive import PredictiveRegistry


def test_mario_action_alphabet_is_the_existing_twelve_button_masks():
    assert BUTTON_MASKS == (0, 1, 2, 16, 17, 18, 8, 9, 10, 24, 25, 26)
    assert len(set(BUTTON_MASKS)) == 12


def test_repeated_observation_uses_snapshots_not_steps(monkeypatch, tmp_path):
    port = MarioRGBPort(tmp_path, tmp_path, tmp_path/"bridge.java", "level", tmp_path/"run")
    port.last_image = np.zeros((2, 2, 3), dtype=np.uint8)
    port.last_packet = {"kind": "observation", "frame": 7}
    calls = []

    def snap():
        calls.append("snap")
        return port.last_image.copy(), {"kind": "observation", "frame": 7}

    monkeypatch.setattr(port, "snap", snap)
    images, packets = port.repeated_observation(4)
    assert images.shape == (4, 2, 2, 3)
    assert calls == ["snap", "snap", "snap"]
    assert all(packet["frame"] == 7 for packet in packets)
    assert port.primitive_frames == 0
    assert port.actions == []


def test_java_bridge_has_nonadvancing_snap_protocol():
    source = (Path(__file__).parents[1] / "experiments" / "mario_continual" /
              "java" / "MortraBridge.java").read_text(encoding="utf8")
    assert 'line.equals("SNAP")' in source
    assert "capture()" in source
    assert "Expected SNAP or STEP" in source
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
    assert set(memory.belief("A", ()).candidates) == {0, split}

    # The discriminating action is inferred from the learned successor
    # observations rather than a fixed action name.
    assert memory.choose_identifying_action(memory.belief("A", ())) == 0
