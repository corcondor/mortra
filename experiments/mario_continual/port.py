"""Low-overhead live Mario RGB transport.

Fast path: the Java bridge sends only a SHA-256 digest of the current exact
frame.  Pixels cross into Python only on DUMP/SNAPN through one persistent mmap.
This removes PNG encode/decode, per-frame file creation, and most pixel transfer.
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import tempfile
import threading
import uuid
from pathlib import Path

import numpy as np

BUTTON_MASKS = (0, 1, 2, 16, 17, 18, 8, 9, 10, 24, 25, 26)
MAX_BATCH = 256


class MarioProtocolError(RuntimeError):
    pass


def _shared_file(output):
    if os.name != "nt":
        candidate = Path("/dev/shm")
        if candidate.exists() and os.access(candidate, os.W_OK):
            return candidate / f"mortra-rgb-{uuid.uuid4().hex}.mmap"
    return Path(output) / "rgb.mmap"


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
        self.shared_file = _shared_file(self.output).resolve()

        self.process = None
        self.last_packet = None
        self.last_hash = None
        self.last_shape = None
        self.primitive_frames = 0
        self.snapshots = 0
        self.batch_commands = 0
        self.pixel_bytes_read = 0
        self.actions = []

    def _pump(self):
        try:
            for line in self.process.stdout:
                self.lines.put(line)
        finally:
            self.lines.put(None)

    def _read_batch(self, packet):
        image_path = Path(packet["rgb_file"]).resolve()
        if image_path != self.shared_file:
            raise MarioProtocolError("bridge returned unexpected mmap path")
        width = int(packet["width"])
        height = int(packet["height"])
        count = int(packet["count"])
        expected = count * height * width * 3
        # Mapping the already-shared pages avoids an extra file decode and lets
        # NumPy copy one contiguous block before the next Java write.
        mapped = np.memmap(image_path, dtype=np.uint8, mode="r",
                           shape=(count, height, width, 3))
        batch = np.array(mapped, copy=True, order="C")
        del mapped
        self.pixel_bytes_read += expected
        self.snapshots += count
        self.batch_commands += 1
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
        if kind == "observation":
            self.last_hash = str(packet["rgb_sha256"])
            self.last_shape = (int(packet["height"]), int(packet["width"]), 3)
            self.snapshots += 1
        elif kind == "observation_batch":
            packet["_batch"] = self._read_batch(packet)
        elif kind in ("terminal", "aborted"):
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
            str(self.shared_file),
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
            raise MarioProtocolError("episode did not produce an initial observation")
        return None, packet

    def snap_hash(self):
        """Recapture only a digest of the exact blocked frame."""
        if self.process is None or self.process.poll() is not None:
            raise MarioProtocolError("episode is not running")
        frame = int(self.last_packet["frame"])
        self.process.stdin.write("SNAP\n")
        self.process.stdin.flush()
        packet = self._read()
        if packet["kind"] != "observation" or int(packet["frame"]) != frame:
            raise MarioProtocolError("SNAP advanced or lost the source frame")
        return self.last_hash, packet

    def dump(self):
        """Read the current already-captured frame through mmap without recapture."""
        if self.process is None or self.process.poll() is not None:
            raise MarioProtocolError("episode is not running")
        frame = int(self.last_packet["frame"])
        self.process.stdin.write("DUMP\n")
        self.process.stdin.flush()
        packet = self._read()
        if packet["kind"] != "observation_batch" or int(packet["frame"]) != frame:
            raise MarioProtocolError("DUMP advanced or lost the source frame")
        batch = packet.pop("_batch")
        if len(batch) != 1:
            raise MarioProtocolError("DUMP returned wrong batch size")
        return batch[0], packet

    def repeated_observation(self, samples):
        """Get N same-state RGB captures in contiguous mmap chunks."""
        samples = int(samples)
        if samples < 1:
            raise ValueError("samples must be positive")
        if self.process is None or self.process.poll() is not None:
            raise MarioProtocolError("episode is not running")
        source_frame = int(self.last_packet["frame"])
        parts = []
        packets = []
        remaining = samples
        while remaining:
            count = min(remaining, MAX_BATCH)
            self.process.stdin.write(f"SNAPN {count}\n")
            self.process.stdin.flush()
            packet = self._read()
            if packet["kind"] != "observation_batch" or int(packet["frame"]) != source_frame:
                raise MarioProtocolError("SNAPN advanced or lost the source frame")
            batch = packet.pop("_batch")
            if len(batch) != count:
                raise MarioProtocolError("SNAPN returned wrong batch size")
            parts.append(batch)
            packets.append(packet)
            remaining -= count
        return np.concatenate(parts, axis=0), packets

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
        return None, packet

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
        try:
            self.shared_file.unlink(missing_ok=True)
        except OSError:
            pass

    def metrics(self):
        return dict(
            primitive_frames=self.primitive_frames,
            snapshots=self.snapshots,
            batch_commands=self.batch_commands,
            pixel_bytes_read=self.pixel_bytes_read,
            primitive_actions=len(self.actions),
            transport="sha256-fastpath+persistent-mmap")
