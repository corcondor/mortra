"""Live Mario RGB transport.

SNAP is a true repeated screen capture while the Java agent callback is blocked;
it does not advance the game.  STEP is the only command that advances game time.
No position, tile grid, enemy list, completion percentage or forward-model clone
is exposed to the learner.
"""
from __future__ import annotations

import json
import queue
import subprocess
import threading
from pathlib import Path

import numpy as np
from PIL import Image

BUTTON_MASKS = (0, 1, 2, 16, 17, 18, 8, 9, 10, 24, 25, 26)


class MarioProtocolError(RuntimeError):
    pass


class MarioRGBPort:
    action_count = len(BUTTON_MASKS)

    def __init__(self, game_dir, build_dir, bridge_source, level, output, *,
                 seconds=60, frames_per_action=8):
        self.game_dir = Path(game_dir).resolve()
        self.build_dir = Path(build_dir).resolve()
        self.bridge_source = Path(bridge_source).resolve()
        self.level = str(level)
        self.output = Path(output).resolve()
        self.seconds = int(seconds)
        self.frames_per_action = int(frames_per_action)
        self.process = None
        self.last_packet = None
        self.last_image = None
        self.primitive_frames = 0
        self.snapshots = 0
        self.actions = []

    def _pump(self):
        try:
            for line in self.process.stdout:
                self.lines.put(line)
        finally:
            self.lines.put(None)

    def _read(self):
        try:
            line = self.lines.get(timeout=120)
        except queue.Empty as exc:
            raise MarioProtocolError("Mario bridge timeout") from exc
        if line is None:
            raise MarioProtocolError("Mario bridge EOF")
        packet = json.loads(line)
        if packet["kind"] == "observation":
            image_path = Path(packet["rgb_file"]).resolve()
            if self.output not in image_path.parents:
                raise MarioProtocolError("RGB path outside run directory")
            self.last_image = np.asarray(Image.open(image_path).convert("RGB"), dtype=np.uint8)
            self.snapshots += 1
        elif packet["kind"] == "terminal":
            # Terminal messages do not fabricate a new RGB observation.
            pass
        elif packet["kind"] == "aborted":
            pass
        else:
            raise MarioProtocolError(f"unknown bridge packet {packet['kind']}")
        self.last_packet = packet
        return packet

    def start(self):
        if self.process is not None:
            raise MarioProtocolError("episode already started")
        self.output.mkdir(parents=True, exist_ok=False)
        self.stderr = (self.output / "stderr.log").open("w", encoding="utf8")
        level_path = self.game_dir / self.level
        command = [
            "java", "-cp", str(self.build_dir), "MortraBridge",
            str(level_path), str(self.seconds), str(self.output), "true",
        ]
        self.process = subprocess.Popen(
            command, cwd=self.game_dir, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=self.stderr,
            text=True, bufsize=1)
        self.lines = queue.Queue()
        self.reader = threading.Thread(target=self._pump, daemon=True)
        self.reader.start()
        packet = self._read()
        if packet["kind"] != "observation":
            raise MarioProtocolError("episode did not produce an initial RGB observation")
        return self.last_image.copy(), packet

    def snap(self):
        """Recapture the exact currently blocked game state without stepping."""
        if self.process is None or self.process.poll() is not None:
            raise MarioProtocolError("episode is not running")
        frame = self.last_packet["frame"]
        self.process.stdin.write("SNAP\n")
        self.process.stdin.flush()
        packet = self._read()
        if packet["kind"] != "observation" or packet["frame"] != frame:
            raise MarioProtocolError("SNAP advanced or lost the source frame")
        return self.last_image.copy(), packet

    def repeated_observation(self, samples):
        if samples < 1:
            raise ValueError("samples must be positive")
        images = [self.last_image.copy()]
        packets = [dict(self.last_packet)]
        while len(images) < samples:
            image, packet = self.snap()
            images.append(image)
            packets.append(packet)
        return np.stack(images), packets

    def step(self, action, frames=None):
        if self.process is None or self.process.poll() is not None:
            raise MarioProtocolError("episode is not running")
        action = int(action)
        if not 0 <= action < self.action_count:
            raise ValueError("action outside Mario action alphabet")
        frames = self.frames_per_action if frames is None else int(frames)
        if not 1 <= frames <= 12:
            raise ValueError("bridge permits 1..12 frames per primitive action")
        self.process.stdin.write(f"STEP {BUTTON_MASKS[action]} {frames}\n")
        self.process.stdin.flush()
        self.actions.append(action)
        self.primitive_frames += frames
        packet = self._read()
        if packet["kind"] == "observation":
            return self.last_image.copy(), packet
        return None if self.last_image is None else self.last_image.copy(), packet

    def close(self):
        if self.process is None:
            return
        if self.process.poll() is None:
            try:
                self.process.stdin.write("STOP\n")
                self.process.stdin.flush()
                self.process.wait(timeout=3)
            except (OSError, subprocess.TimeoutExpired):
                self.process.kill()
                self.process.wait()
        self.stderr.close()

    def metrics(self):
        return dict(primitive_frames=self.primitive_frames,
                    snapshots=self.snapshots, primitive_actions=len(self.actions))
