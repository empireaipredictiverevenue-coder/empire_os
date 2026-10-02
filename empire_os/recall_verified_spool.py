"""Private atomic spool for verified Recall realtime envelopes."""
from __future__ import annotations

import base64
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any

from empire_os.recall_webhook_api import VerifiedRecallEnvelope


@dataclass(frozen=True)
class RecallSpoolReceipt:
    queue_id: str
    duplicate: bool
    payload_sha256: str
    queued: bool = True
    canonical_truth_written: bool = False
    execution_authority: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class FileRecallVerifiedSpool:
    def __init__(
        self,
        root: str | Path,
        *,
        max_payload_bytes: int = 512_000,
    ) -> None:
        self.root = Path(root)
        self.max_payload_bytes = int(max_payload_bytes)
        if self.max_payload_bytes <= 0:
            raise ValueError("max_payload_bytes must be positive")


    def _prepare_root(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)
        if self.root.is_symlink():
            raise RuntimeError("Recall spool root cannot be a symlink")

    @staticmethod
    def _queue_id(envelope: VerifiedRecallEnvelope) -> str:
        material = (
            envelope.verification.webhook_id
            + "|"
            + envelope.verification.webhook_timestamp
            + "|"
            + envelope.verification.payload_sha256
        ).encode("utf-8")
        return sha256(material).hexdigest()

    def enqueue(self, envelope: VerifiedRecallEnvelope) -> RecallSpoolReceipt:
        payload = envelope.raw_payload
        if len(payload) > self.max_payload_bytes:
            raise ValueError("verified Recall payload exceeds spool limit")
        if (
            sha256(payload).hexdigest()
            != envelope.verification.payload_sha256
        ):
            raise ValueError("verified Recall payload hash mismatch")

        self._prepare_root()
        queue_id = self._queue_id(envelope)
        target = self.root / f"{queue_id}.json"
        if target.exists():
            return RecallSpoolReceipt(
                queue_id=queue_id,
                duplicate=True,
                payload_sha256=envelope.verification.payload_sha256,
            )


        record = {
            "schema_version": "empire.recall_verified_spool.v1",
            "queue_id": queue_id,
            "verification": envelope.verification.as_dict(),
            "received_at": envelope.received_at,
            "raw_payload_base64": base64.b64encode(payload).decode("ascii"),
            "canonical_truth_written": False,
            "execution_authority": "none",
        }
        tmp = self.root / f".{queue_id}.{os.getpid()}.tmp"
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

        return RecallSpoolReceipt(
            queue_id=queue_id,
            duplicate=False,
            payload_sha256=envelope.verification.payload_sha256,
        )
