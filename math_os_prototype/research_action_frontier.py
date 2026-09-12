"""Retain proposed actions, reserving periodic service for the oldest action.

This is fairness over offered actions, not completeness of the proposal grammar.
Payloads and admissibility are supplied by the existing domain adapter.
"""
from copy import deepcopy
from hashlib import sha256
import json


class ResearchActionFrontier:
    def __init__(self, reserve_every=4):
        if type(reserve_every) is not int or reserve_every < 1:
            raise ValueError("reserved service interval must be positive")
        self.reserve_every = reserve_every
        self.round = 0
        self.next_id = 0
        self.pending = []

    def _state(self):
        return {"schema": "mortra.research-action-frontier.v1",
                "reserve_every": self.reserve_every, "round": self.round,
                "next_id": self.next_id, "pending": self.pending}

    def snapshot(self):
        return deepcopy(self._state())

    def digest(self):
        return sha256(json.dumps(self._state(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def prepare(self, offered, rejection_reasons, *, readonly_keyed=False):
        """Check current admissibility, retaining independent copies of admissions.

        Trusted adapters may opt into a pure callback taking (key, payload).
        Such callbacks must not mutate payloads; adapters must supply keys
        identifying their contents. The default callback receives an isolated copy.
        """
        def reasons_for(entry):
            if readonly_keyed:
                return rejection_reasons(entry["key"], entry["payload"])
            return rejection_reasons(deepcopy(entry["payload"]))

        retired, rejected, admitted = [], [], []
        retained = []
        for entry in self.pending:
            reasons = reasons_for(entry)
            if reasons:
                retired.append({"id": entry["id"], "reasons": reasons})
            else:
                retained.append(entry)
        self.pending = retained
        keys = {entry["key"] for entry in self.pending}
        for index, item in enumerate(offered):
            reasons = reasons_for(item)
            if item["key"] in keys:
                reasons = [*reasons, "already_pending"]
            if reasons:
                rejected.append({"offered_index": index, "reasons": reasons})
                continue
            entry = {"id": self.next_id, "key": item["key"], "payload": deepcopy(item["payload"])}
            self.next_id += 1
            self.pending.append(entry)
            keys.add(item["key"])
            admitted.append({"offered_index": index, "id": entry["id"]})
        return {"retired": retired, "rejected": rejected, "admitted": admitted}

    def window(self, width, *, rng=None):
        if type(width) is not int or width < 1:
            raise ValueError("selection window must be positive")
        if rng is not None and not self.reserved and len(self.pending) > width:
            # Oldest service stays available without restricting every other slot.
            return deepcopy([self.pending[0], *rng.sample(self.pending[1:], width - 1)])
        return deepcopy(self.pending[:width])

    @property
    def reserved(self):
        return self.round % self.reserve_every == 0

    def commit(self, selected_id):
        if selected_id is None:
            if self.pending:
                raise ValueError("cannot idle while actions are pending")
        else:
            if self.reserved and (not self.pending or self.pending[0]["id"] != selected_id):
                raise ValueError("reserved service must select oldest action")
            index = next((i for i, entry in enumerate(self.pending) if entry["id"] == selected_id), None)
            if index is None:
                raise ValueError("selected action is not pending")
            self.pending.pop(index)
        self.round += 1
