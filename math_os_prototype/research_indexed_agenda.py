"""Fairly interleave finite indexed streams, including streams admitted later.

A stream's item k has priority (stream_id + k, stream_id). Only finitely
many items can precede it, even if new streams continue to arrive. This is
an enumeration guarantee, not a claim that any item is useful or provable.
"""
from copy import deepcopy
from hashlib import sha256
import heapq
import json


class ResearchIndexedAgenda:
    def __init__(self):
        self.streams = []
        self._keys = set()
        self._heap = []

    def admit(self, key, length):
        if not isinstance(key, str) or key in self._keys:
            raise ValueError("stream key must be a new string")
        if type(length) is not int or length < 1:
            raise ValueError("stream length must be positive")
        index = len(self.streams)
        self.streams.append({"key": key, "length": length, "next": 0})
        self._keys.add(key)
        heapq.heappush(self._heap, (index, index))
        return index

    def pop(self):
        if not self._heap:
            return None
        priority, index = heapq.heappop(self._heap)
        stream = self.streams[index]
        offset = stream["next"]
        if priority != index + offset:
            raise ValueError("corrupt agenda priority")
        stream["next"] += 1
        if stream["next"] < stream["length"]:
            heapq.heappush(self._heap, (index + stream["next"], index))
        return {"stream_id": index, "stream_key": stream["key"],
                "offset": offset, "priority": priority}

    def snapshot(self):
        return deepcopy({"schema": "mortra.indexed-agenda.v1", "streams": self.streams})

    def digest(self):
        return sha256(json.dumps(self.snapshot(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()
