"""Fail-closed validation of OBSERVE-only control proof before binding promotion.

Aggregate runtime proof does not establish tenant-specific or commercial outcomes.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from collections.abc import Mapping


class PromotionProofError(ValueError):
    pass


def validate_control_proof(proof: Mapping, *, lane: str, allowed: set[str], now: datetime | None = None) -> set[str]:
    if not isinstance(proof, Mapping) or proof.get('lane') != lane:
        raise PromotionProofError('lane mismatch')
    if proof.get('mode') != 'OBSERVE' or proof.get('status') != 'VERIFIED_RUNTIME':
        raise PromotionProofError('not verified observe-only evidence')
    if any(proof.get(key) is True for key in ('outbound', 'db_write', 'action_authority_granted', 'campaign_state_mutated')):
        raise PromotionProofError('consequential authority detected')
    stamp = proof.get('generated_at')
    if not isinstance(stamp, str):
        raise PromotionProofError('missing timestamp')
    try:
        observed = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
    except ValueError as exc:
        raise PromotionProofError('invalid timestamp') from exc
    current = now or datetime.now(timezone.utc)
    if observed.tzinfo is None or current.tzinfo is None:
        raise PromotionProofError('naive timestamp')
    age = current.astimezone(timezone.utc) - observed.astimezone(timezone.utc)
    if not timedelta(0) <= age <= timedelta(days=7):
        raise PromotionProofError('stale or future proof')
    controls = proof.get('runtime_verified_controls')
    if not isinstance(controls, list) or not controls or any(not isinstance(c, str) for c in controls):
        raise PromotionProofError('invalid control list')
    if len(controls) != len(set(controls)) or not set(controls) <= allowed:
        raise PromotionProofError('duplicate or unexpected controls')
    return set(controls)


class PromotionWriteError(RuntimeError):
    """Binding write was refused or could not be made durable."""


def atomic_binding_write(path, payload: str, *, expected_bytes: bytes) -> None:
    """Fail closed on a changed source; write via unique, synced sibling temp."""
    import os
    import tempfile
    from pathlib import Path

    target = Path(path)
    if target.read_bytes() != expected_bytes:
        raise PromotionWriteError('binding changed since read')
    fd, name = tempfile.mkstemp(prefix=f'.{target.name}.', suffix='.tmp', dir=target.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            out.write(payload)
            out.flush()
            os.fsync(out.fileno())
        if target.read_bytes() != expected_bytes:
            raise PromotionWriteError('binding changed before replace')
        os.replace(name, target)
        directory_fd = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def binding_writer_lock(path):
    """Advisory lock for cooperating promotion writers, held across read/modify/write."""
    import fcntl
    from contextlib import contextmanager
    from pathlib import Path

    @contextmanager
    def locked():
        lock_path = Path(str(path) + '.promotion.lock')
        with lock_path.open('a+b') as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return locked()
