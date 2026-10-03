"""Strict producer contract for the local Ringleader evidence bundle."""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from empire_os.outbound_evidence_bundle import SUPPORTED_SOURCES
from empire_os.outbound_evidence_bundle_auth import sign_evidence_bundle


def build_evidence_bundle(
    sources: Mapping[str, Any],
    *,
    generated_at: datetime | None = None,
    signing_key: str | None = None,
) -> dict[str, Any]:
    if not isinstance(sources, Mapping):
        raise ValueError("evidence_sources_must_be_mapping")

    normalized: dict[str, Any] = {}
    unknown = sorted(
        str(key)
        for key in sources
        if str(key) not in SUPPORTED_SOURCES
    )
    if unknown:
        raise ValueError(
            "unsupported_evidence_sources:" + ",".join(unknown)
        )

    for raw_name, payload in sources.items():
        name = str(raw_name)
        if name in {"dnscontrol_preview", "evidence_fusion"}:
            if not isinstance(payload, list):
                raise ValueError(f"{name}_must_be_list")
            normalized[name] = [
                dict(item)
                for item in payload
                if isinstance(item, Mapping)
            ]
        else:
            if not isinstance(payload, Mapping):
                raise ValueError(f"{name}_must_be_mapping")
            normalized[name] = dict(payload)

    timestamp = (generated_at or datetime.now(timezone.utc))
    if timestamp.tzinfo is None:
        raise ValueError("generated_at_requires_timezone")
    timestamp = timestamp.astimezone(timezone.utc)

    bundle: dict[str, Any] = {
        "schema_version": "1",
        "generated_at": timestamp.isoformat(),
        "sources": normalized,
        "mutation_authorized": False,
    }

    if signing_key:
        bundle = sign_evidence_bundle(bundle, key=signing_key)

    return bundle


def atomic_write_evidence_bundle(
    path: Path,
    bundle: Mapping[str, Any],
    *,
    file_mode: int = 0o640,
) -> dict[str, Any]:
    """Atomically replace one local bundle without creating parent directories."""

    target = Path(path)
    parent = target.parent

    if not parent.is_dir():
        raise RuntimeError("evidence_bundle_parent_missing")
    if target.is_symlink():
        raise RuntimeError("evidence_bundle_target_symlink_forbidden")
    if bundle.get("mutation_authorized") is True:
        raise RuntimeError("evidence_bundle_cannot_authorize_mutation")

    serialized = json.dumps(
        dict(bundle),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    ) + "\n"

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())

        os.chmod(temp_path, file_mode)
        os.replace(temp_path, target)
        temp_path = None

        # Best-effort directory sync so rename durability follows file durability.
        try:
            directory_fd = os.open(parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            pass

        return {
            "path": str(target),
            "bytes_written": len(serialized.encode("utf-8")),
            "mutation_authorized": False,
        }
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
