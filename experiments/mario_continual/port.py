"""Live Mario RGB transport using raw RGB batches.

The Java bridge writes uncompressed RGB bytes.  This avoids PNG encode/decode
and allows repeated observations to cross the Java/Python boundary in one batch.
SNAP/SNAPN never advance game time; STEP is the only advancing command.
"""
from __future__ import annotations

import json
import queue
import subprocess
import threading
from pathlib import Path

import numpy as np

BUTTON_MASKS = (0, 1, 2, 16, 17, 18, 8, 9, 10, 24, 25, 26)


class MarioProtocolError(RuntimeError):
    pass


class MarioRGBPort:
    action_count = len(BUTTON_MASKS)

    def __init__(self, game_dir, build_dir, bridge_source, level, output, *,
                 seconds=60, frames_per_action=8, keep_frames=False):
        self.game_dir = Path(game_dir).resolve()
        self.build_dir = Path(build_dir).resolve()
        self.bridge_source = Path(bridge_source).resolve()
        self.level = str(level)
        self.output = Path(output).resolve()
        self.seconds = int(seconds)
        self.frames_per_action = int(frames_per_action)
        self.keep_frames = bool(keep_frames)
        self.process = None
        self.last_packet = None
        self.last_image = None
        self.last_batch = None
        self.primitive_frames = 0
        self.snapshots = 0
        self.batch_commands = 0
        self.actions = []

    def _pump(self):
        try:
            for line in self.process.stdout:
                self.lines.put(line)
        finally:
            self.lines.put(None)

    def _load_raw(self, packet):
        image_path = Path(packet["rgb_file"]).resolve()
        if self.output not in image_path.parents:
            raise MarioProtocolError("RGB path outside run directory")
        width = int(packet["width"])
        height = int(packet["height"])
        count = int(packet.get("count", 1))
        expected = count * height * width * 3
        data = np.fromfile(image_path, dtype=np.uint8, count=expected)
        if data.size != expected:
            raise MarioProtocolError(
                f"RGB byte count mismatch: expected {expected}, got {data.size}")
        batch = data.reshape(count, height, width, 3)
        # Detach from any temporary file-backed lifetime before deleting the file.
        batch = np.ascontiguousarray(batch)
        if not self.keep_frames:
            image_path.unlink(missing_ok=True)
        self.snapshots += count
        self.last_batch = batch
        self.last_image = batch[-1]
        return batch

    def _read(self):
        try:
            line = self.lines.get(timeout=120)
        except queue.Empty as exc:
            raise MarioProtocolError("Mario bridge timeout") from exc
        if line is None:
            raise MarioProtocolError("Mario bridge EOF")
        packet = json.loads(line)
        kind = packet["kind"]
        if kind in ("observation", "observation_batch"):
            self._load_raw(packet)
            if kind == "observation_batch":
                self.batch_commands += 1
        elif kind in ("terminal", "aborted"):
            # Terminal messages do not fabricate a new RGB observation.
            pass
        else:
            raise MarioProtocolError(f"unknown bridge packet {kind}")
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
        """Recapture one blocked game frame without stepping."""
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
        """Return N same-frame captures with one Java round-trip.

        The current observation already counts as sample 0.  One SNAPN command
        obtains the remaining N-1 captures in a single raw file.
        """
        samples = int(samples)
        if samples < 1:
            raise ValueError("samples must be positive")
        if self.last_image is None:
            raise MarioProtocolError("no current observation")
        if samples == 1:
            return self.last_image[None, ...].copy(), [dict(self.last_packet)]

        frame = int(self.last_packet["frame"])
        first = self.last_image.copy()
        self.process.stdin.write(f"SNAPN {samples-1}\n")
        self.process.stdin.flush()
        packet = self._read()
        if packet["kind"] != "observation_batch" or int(packet["frame"]) != frame:
            raise MarioProtocolError("SNAPN advanced or lost the source frame")
        if self.last_batch is None or len(self.last_batch) != samples-1:
            raise MarioProtocolError("SNAPN returned wrong batch size")
        images = np.concatenate((first[None, ...], self.last_batch), axis=0)
        packets = [dict(self.last_packet, kind="observation", count=1)] + [
            dict(packet, batch_index=i) for i in range(samples-1)
        ]
        # Keep the semantic current observation as the most recent captured frame.
        self.last_image = images[-1]
        return images, packets

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
        return dict(
            primitive_frames=self.primitive_frames,
            snapshots=self.snapshots,
            batch_commands=self.batch_commands,
            primitive_actions=len(self.actions))
