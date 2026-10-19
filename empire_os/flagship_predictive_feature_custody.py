"""Explicit single-snapshot original market feature custody (feature-only).

This private filesystem receipt is NOT a canonical EmpireDB prediction
registry write, authenticated historical proof, signed timestamp or payment
evidence. It is a strict local prior-feature preservation primitive.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat
from typing import Any, Mapping

from empire_os.flagship_predictive_market_features import (
    review_market_feature_prediction_gap,
)

SCHEMA="empire.flagship.predictive_feature_local_custody.v1"
MAX_PACKET_BYTES=48000

class FeatureCustodyHold(ValueError):
    pass


def _serialized(packet: Mapping[str, Any]) -> bytes:
    # Shape/digest validated upstream; local caller cannot claim that a
    # forged self-consistent packet was produced by the canonical source.
    try:
        review_market_feature_prediction_gap(packet)
        raw=json.dumps(packet,sort_keys=True,separators=(",",":"),
                       allow_nan=False,ensure_ascii=True).encode()+b"\n"
    except (TypeError,ValueError,OverflowError) as exc:
        raise FeatureCustodyHold("untrusted predictive feature payload") from exc
    if len(raw)>MAX_PACKET_BYTES:
        raise FeatureCustodyHold("predictive feature exceeds maximum custody size")
    return raw


def _secure_existing(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise FeatureCustodyHold("unsafe feature receipt path")
    info=path.stat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink!=1
            or info.st_mode&0o077!=0 or info.st_size>MAX_PACKET_BYTES):
        raise FeatureCustodyHold("unsafe feature receipt custody")
    return path.read_bytes()


def preserve_prospective_market_features(
    folder: Path, packet: Mapping[str, Any], *, apply: bool=False,
) -> dict[str, Any]:
    """One explicit file; repeat identical bytes idempotent, differing held.

    File is under caller-selected *isolated* storage. Production issuer must
    use a separately authorised registry, NOT this local receipt.
    """
    raw=_serialized(packet)
    folder=Path(folder)
    name=packet["feature_packet_sha256"]+".json"
    path=folder/name
    if folder.is_symlink() or path.is_symlink():
        raise FeatureCustodyHold("unsafe feature path or directory")
    present=path.exists()
    if present:
        previous=_secure_existing(path)
        if previous!=raw:
            raise FeatureCustodyHold("conflicting feature custody digest")
        return {
            "schema_version":SCHEMA,
            "status":"EXACT_PRIOR_FEATURE_REPLAY",
            "written":False,
            "feature_packet_sha256":packet["feature_packet_sha256"],
            "authenticated_production_registry":False,
            "external_timestamp_anchor":False,
            "database_writes":False,
            "execution_authority":"none",
        }
    if not apply:
        return {
            "schema_version":SCHEMA,
            "status":"PRIVATE_FEATURE_RECEIPT_PREVIEW_ONLY",
            "written":False,
            "feature_packet_sha256":packet["feature_packet_sha256"],
            "authenticated_production_registry":False,
            "external_timestamp_anchor":False,
            "database_writes":False,
            "execution_authority":"none",
        }
    folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    if folder.is_symlink() or folder.stat().st_mode & 0o077:
        raise FeatureCustodyHold("unsafe private feature folder permissions")
    try:
        fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    except FileExistsError:
        if _secure_existing(path)!=raw:
            raise FeatureCustodyHold("concurrent feature receipt conflict")
        return {
            "schema_version":SCHEMA,"status":"EXACT_PRIOR_FEATURE_REPLAY",
            "written":False,"feature_packet_sha256":packet["feature_packet_sha256"],
            "authenticated_production_registry":False,
            "external_timestamp_anchor":False,
            "database_writes":False,"execution_authority":"none",
        }
    try:
        with os.fdopen(fd,"wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        directory_fd=os.open(folder,os.O_RDONLY|os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception:
        try:
            path.unlink()
        except OSError:
            pass
        raise
    return {
        "schema_version":SCHEMA,
        "status":"PRIVATE_ORIGINAL_FEATURE_SNAPSHOT_RECORDED",
        "written":True,
        "feature_packet_sha256":packet["feature_packet_sha256"],
        "authenticated_production_registry":False,
        "external_timestamp_anchor":False,
        "database_writes":False,
        "execution_authority":"none",
    }


def read_local_prospective_features(
    folder: Path, sha256_digest: str,
) -> Mapping[str, Any]:
    if (not isinstance(sha256_digest,str)
            or len(sha256_digest)!=64
            or any(c not in "0123456789abcdef" for c in sha256_digest)):
        raise FeatureCustodyHold("invalid feature content address")
    folder=Path(folder)
    if folder.is_symlink():
        raise FeatureCustodyHold("unsafe feature folder")
    path=folder/(sha256_digest+".json")
    try:
        original=_secure_existing(path)
        packet=json.loads(original)
        if packet.get("feature_packet_sha256")!=sha256_digest or _serialized(packet)!=original:
            raise FeatureCustodyHold("feature readback digest mismatch")
    except (ValueError,TypeError,UnicodeError,OSError) as exc:
        raise FeatureCustodyHold("original feature readback held") from exc
    return packet
