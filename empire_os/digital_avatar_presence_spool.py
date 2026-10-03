"""Private idempotent spool for low-latency Presence transcript observations."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any

from empire_os.digital_avatar_presence_transcript import (
    PresenceTranscriptObservation,
)


@dataclass(frozen=True)
class PresenceTranscriptSpoolReceipt:
    spool_id: str
    observation_id: str
    duplicate: bool
    truth_class: str = "SESSION_OBSERVED"
    canonical_truth_written: bool = False
    commercial_truth_written: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class FilePresenceTranscriptSpool:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def _prepare(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)
        if self.root.is_symlink():
            raise RuntimeError("Presence transcript spool root cannot be symlink")

    @staticmethod
    def _validate(observation: PresenceTranscriptObservation) -> None:
        if observation.truth_class != "SESSION_OBSERVED":
            raise ValueError("Presence spool requires SESSION_OBSERVED truth")
        if observation.canonical_evidence:
            raise ValueError("Presence spool cannot accept canonical evidence")
        if observation.commercial_truth_allowed:
            raise ValueError("Presence spool cannot accept commercial truth")
        if observation.speech_execution_allowed:
            raise ValueError("Presence spool cannot accept speech authority")
        if observation.execution_authority != "none":
            raise ValueError("Presence spool cannot accept execution authority")

    def enqueue(
        self,
        observation: PresenceTranscriptObservation,
    ) -> PresenceTranscriptSpoolReceipt:
        self._validate(observation)
        self._prepare()
        spool_id = sha256(
            observation.observation_id.encode("utf-8")
        ).hexdigest()
        target = self.root / f"{spool_id}.json"
        receipt = PresenceTranscriptSpoolReceipt(
            spool_id=spool_id,
            observation_id=observation.observation_id,
            duplicate=target.exists(),
        )
        if target.exists():
            return receipt

        record = {
            "schema_version": "empire.avatar_presence_fast_observation.v1",
            "spool_id": spool_id,
            "observation": observation.as_dict(),
            "raw_audio_persisted": False,
            "canonical_truth_written": False,
            "commercial_truth_written": False,
            "execution_authority": "none",
        }
        tmp = self.root / f".{spool_id}.{os.getpid()}.tmp"
        encoded = (
            json.dumps(record, sort_keys=True, separators=(",", ":"))
            + "\n"
        ).encode("utf-8")
        fd = os.open(
            tmp,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, target)
            os.chmod(target, 0o600)
        finally:
            if tmp.exists():
                tmp.unlink()
        return receipt
