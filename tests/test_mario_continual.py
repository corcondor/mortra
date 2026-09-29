from pathlib import Path

import numpy as np

from experiments.mario_continual.port import BUTTON_MASKS, MarioRGBPort


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
