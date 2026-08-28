"""Hash-chained machine protocol for MORTRA/Codex research iterations.

The protocol deliberately carries typed observations and experiment records,
not conversational prose.  MORTRA may propose evidence, and Codex may propose
an intervention, but neither may mark it successful.  A governor entry records
the decision derived from frozen control/treatment results and proof hashes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any


PROTOCOL_VERSION = "mortra-codex-research-dialogue-v1"
GENESIS_SHA256 = "0" * 64
_ROLES = frozenset({"mortra", "codex", "governor"})
_KINDS = frozenset(
    {
        "cohort_observation",
        "typed_hypothesis",
        "controlled_experiment",
        "decision",
    }
)


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )


def payload_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ResearchDialogueEntry:
    sequence: int
    role: str
    kind: str
    cycle_fingerprint: str
    payload: dict[str, Any]
    previous_sha256: str
    entry_sha256: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _entry_digest(
    *,
    sequence: int,
    role: str,
    kind: str,
    cycle_fingerprint: str,
    payload: dict[str, Any],
    previous_sha256: str,
) -> str:
    return payload_sha256(
        {
            "sequence": sequence,
            "role": role,
            "kind": kind,
            "cycle_fingerprint": cycle_fingerprint,
            "payload": payload,
            "previous_sha256": previous_sha256,
        }
    )


@dataclass
class ResearchDialogueLedger:
    objective_code: str
    frozen_cohort_sha256: str
    entries: list[ResearchDialogueEntry]
    protocol_version: str = PROTOCOL_VERSION

    @classmethod
    def create(
        cls,
        *,
        objective_code: str,
        frozen_cohort_sha256: str,
    ) -> "ResearchDialogueLedger":
        return cls(
            objective_code=objective_code,
            frozen_cohort_sha256=frozen_cohort_sha256,
            entries=[],
        )

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "ResearchDialogueLedger":
        ledger = cls(
            protocol_version=str(value["protocol_version"]),
            objective_code=str(value["objective_code"]),
            frozen_cohort_sha256=str(value["frozen_cohort_sha256"]),
            entries=[
                ResearchDialogueEntry(
                    sequence=int(item["sequence"]),
                    role=str(item["role"]),
                    kind=str(item["kind"]),
                    cycle_fingerprint=str(item["cycle_fingerprint"]),
                    payload=dict(item["payload"]),
                    previous_sha256=str(item["previous_sha256"]),
                    entry_sha256=str(item["entry_sha256"]),
                )
                for item in value.get("entries", [])
            ],
        )
        ledger.verify()
        return ledger

    @classmethod
    def load(cls, path: Path) -> "ResearchDialogueLedger":
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def to_dict(self) -> dict[str, object]:
        return {
            "protocol_version": self.protocol_version,
            "objective_code": self.objective_code,
            "frozen_cohort_sha256": self.frozen_cohort_sha256,
            "head_sha256": (
                self.entries[-1].entry_sha256 if self.entries else GENESIS_SHA256
            ),
            "entries": [entry.to_dict() for entry in self.entries],
        }

    def append(
        self,
        *,
        role: str,
        kind: str,
        cycle_fingerprint: str,
        payload: dict[str, Any],
    ) -> ResearchDialogueEntry:
        if role not in _ROLES:
            raise ValueError(f"unsupported dialogue role: {role}")
        if kind not in _KINDS:
            raise ValueError(f"unsupported dialogue kind: {kind}")
        previous = (
            self.entries[-1].entry_sha256 if self.entries else GENESIS_SHA256
        )
        sequence = len(self.entries)
        digest = _entry_digest(
            sequence=sequence,
            role=role,
            kind=kind,
            cycle_fingerprint=cycle_fingerprint,
            payload=payload,
            previous_sha256=previous,
        )
        entry = ResearchDialogueEntry(
            sequence=sequence,
            role=role,
            kind=kind,
            cycle_fingerprint=cycle_fingerprint,
            payload=payload,
            previous_sha256=previous,
            entry_sha256=digest,
        )
        self.entries.append(entry)
        return entry

    def verify(self) -> None:
        if self.protocol_version != PROTOCOL_VERSION:
            raise ValueError(f"unsupported protocol: {self.protocol_version}")
        previous = GENESIS_SHA256
        for expected_sequence, entry in enumerate(self.entries):
            if entry.sequence != expected_sequence:
                raise ValueError("dialogue sequence is not contiguous")
            if entry.role not in _ROLES or entry.kind not in _KINDS:
                raise ValueError("dialogue entry has an unsupported role or kind")
            if entry.previous_sha256 != previous:
                raise ValueError("dialogue hash chain is broken")
            expected = _entry_digest(
                sequence=entry.sequence,
                role=entry.role,
                kind=entry.kind,
                cycle_fingerprint=entry.cycle_fingerprint,
                payload=entry.payload,
                previous_sha256=entry.previous_sha256,
            )
            if entry.entry_sha256 != expected:
                raise ValueError("dialogue entry digest does not match its payload")
            previous = entry.entry_sha256

    def completed_cycle(self, cycle_fingerprint: str) -> bool:
        return any(
            entry.cycle_fingerprint == cycle_fingerprint
            and entry.role == "governor"
            and entry.kind == "decision"
            for entry in self.entries
        )

    def cycle_entries(
        self,
        cycle_fingerprint: str,
    ) -> tuple[ResearchDialogueEntry, ...]:
        return tuple(
            entry
            for entry in self.entries
            if entry.cycle_fingerprint == cycle_fingerprint
        )

    def save(self, path: Path) -> None:
        self.verify()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)


__all__ = [
    "GENESIS_SHA256",
    "PROTOCOL_VERSION",
    "ResearchDialogueEntry",
    "ResearchDialogueLedger",
    "canonical_json",
    "payload_sha256",
]
