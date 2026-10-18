"""First-party founder-content origin receipts and immutable revision checking.

A SHA-256 receipt documents bytes and a *founder's own assertion* of
authorship/rights. It is NOT a verified copyright chain, C2PA signature,
AI-detector result, permission to use third-party content or a licence.
This module NEVER removes/edits metadata, watermarks or source content.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import os
import re
import stat
from typing import Any, Mapping

from empire_os.media_rights_provenance import synthetic_media_disclosure

SCHEMA = "empire.media.founder_origin_provenance.v1"
MAX_BYTES = 256 * 1024 * 1024
ALLOWED_SUFFIXES = frozenset({
    ".png", ".jpg", ".jpeg", ".webp", ".svg", ".mp4", ".mov",
    ".wav", ".mp3", ".pdf", ".md", ".txt", ".json",
})
ORIGIN_CLASSES = frozenset({
    "FOUNDER_ORIGINAL",
    "FOUNDER_DIRECTED_AI_ASSISTED",
    "THIRD_PARTY_LICENSED",
    "UNKNOWN",
})
AI_ASSISTANCE = frozenset({"NONE_DECLARED", "AI_ASSISTED_DECLARED", "UNKNOWN"})
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[a-z0-9][a-z0-9_.-]{2,95}\Z")


def _sha_file(path: Path) -> tuple[str, int]:
    """Read an existing regular file once, with no symlinks or mutation."""
    if path.suffix.lower() not in ALLOWED_SUFFIXES or path.is_symlink():
        raise ValueError("unsupported_or_symlink_asset")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= MAX_BYTES:
            raise ValueError("unsupported_asset_size_or_file_kind")
        digest = sha256()
        count = 0
        with os.fdopen(os.dup(fd), "rb") as handle:
            while block := handle.read(1024 * 1024):
                count += len(block)
                if count > MAX_BYTES:
                    raise ValueError("asset_exceeds_bounded_read")
                digest.update(block)
        after = os.fstat(fd)
        if (before.st_size != count or after.st_size != count
                or before.st_mtime_ns != after.st_mtime_ns
                or before.st_ino != after.st_ino):
            raise ValueError("asset_mutated_during_review")
        return digest.hexdigest(), count
    finally:
        os.close(fd)


def build_founder_asset_receipt(
    path: str | Path, *, asset_id: str, origin_class: str,
    ai_assistance: str, founder_ownership_declared: bool = False,
    third_party_components_declared: bool | None = None,
    parent_file_sha256: str | None = None,
    transformation_label: str | None = None,
    synthetic_person: bool = False,
    synthetic_event_or_place: bool = False,
    altered_real_footage: bool = False,
) -> dict[str, Any]:
    """Describe exact supplied bytes with a *self-declared* authorship trail.

    A fully founder-created original may be packaged internally while source
    licences for downloaded datasets or embedded third-party assets remain
    separate. AI-assisted origins are transparently labelled, not disguised.
    """
    asset = Path(path).expanduser()
    if not _ID.fullmatch(asset_id):
        raise ValueError("invalid_asset_identifier")
    if origin_class not in ORIGIN_CLASSES or ai_assistance not in AI_ASSISTANCE:
        raise ValueError("unsupported_asset_origin_or_ai_assistance")
    if type(founder_ownership_declared) is not bool:
        raise ValueError("ownership_declaration_must_be_boolean")
    if third_party_components_declared not in (None, True, False):
        raise ValueError("third_party_components_state_invalid")
    if origin_class.startswith("FOUNDER") and not founder_ownership_declared:
        raise ValueError("founder_origin_requires_explicit_owner_declaration")
    if origin_class == "THIRD_PARTY_LICENSED" and founder_ownership_declared:
        raise ValueError("third_party_source_cannot_be_declared_first_party")
    if origin_class == "FOUNDER_DIRECTED_AI_ASSISTED" and ai_assistance != "AI_ASSISTED_DECLARED":
        raise ValueError("ai_assisted_lineage_requires_disclosure")
    if parent_file_sha256 is not None and not _SHA.fullmatch(parent_file_sha256):
        raise ValueError("invalid_parent_asset_sha256")
    if parent_file_sha256 is not None and not (transformation_label or "").strip():
        raise ValueError("revision_requires_transform_description")
    if transformation_label is not None and (
        len(transformation_label) > 120
        or re.fullmatch(r"[a-zA-Z0-9 .,()_+-]{3,120}", transformation_label) is None
    ):
        raise ValueError("unsafe_or_empty_transformation_label")
    digest, size = _sha_file(asset)
    if parent_file_sha256 == digest:
        raise ValueError("revision_cannot_claim_unmodified_parent_as_modified")
    disclosure = synthetic_media_disclosure(
        synthetic_person=synthetic_person,
        synthetic_event_or_place=synthetic_event_or_place,
        altered_real_footage=altered_real_footage,
    )
    first_party = origin_class.startswith("FOUNDER")
    return {
        "schema_version": SCHEMA,
        "asset_id": asset_id,
        "file_sha256": digest,
        "file_bytes": size,
        "file_extension": asset.suffix.lower(),
        "origin_class": origin_class,
        "origin_assertion": "FOUNDER_SELF_DECLARED_NOT_INDEPENDENTLY_AUTHENTICATED"
            if first_party else "SOURCE_LICENCE_REQUIRED_OR_UNKNOWN",
        "founder_ownership_declared": founder_ownership_declared,
        "founder_ownership_independently_verified": False,
        "ai_assistance": ai_assistance,
        "third_party_components_declared": third_party_components_declared,
        "third_party_component_rights_verified": False,
        "input_parent_sha256": parent_file_sha256,
        "transformation": transformation_label,
        "lineage_mode": "FIRST_PARTY_SELF_DECLARED_LOCAL_DIGEST_NOT_SIGNED",
        "c2pa_content_credentials_validated": False,
        "c2pa_validation_state": "NOT_AVAILABLE_NOT_CHECKED",
        "watermark_removed_or_obscured": "NOT_ATTESTED_NO_REMOVAL_OPERATION_PERFORMED",
        "synthetic_media_disclosure": disclosure,
        "commercial_use_preflight": (
            "FOUNDER_ORIGINAL_RIGHTS_REVIEW_RECOMMENDED"
            if first_party and third_party_components_declared is False
            else "HOLD_SOURCE_OR_EMBEDDED_COMPONENT_RIGHTS"
        ),
        "provenance_integrity_current_asset": "LOCAL_SHA256_CAPTURED",
        "public_release_authorized": False,
        "third_party_resale_authorized": False,
        "provenance_evidence_is_detection_proof": False,
        "production_asset_modified": False,
        "paid_service_used": False,
        "execution_authority": "none",
    }


def verify_founder_asset_receipt(
    path: str | Path, receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify byte integrity without claiming origin authenticity."""
    if (not isinstance(receipt, Mapping)
            or receipt.get("schema_version") != SCHEMA
            or not isinstance(receipt.get("asset_id"), str)
            or _ID.fullmatch(receipt["asset_id"]) is None
            or not isinstance(receipt.get("file_sha256"), str)
            or _SHA.fullmatch(receipt["file_sha256"]) is None
            or type(receipt.get("file_bytes")) is not int):
        raise ValueError("malformed_origin_receipt")
    new_sha, size = _sha_file(Path(path).expanduser())
    matched = new_sha == receipt["file_sha256"] and size == receipt["file_bytes"]
    return {
        "schema_version": "empire.media.founder_origin_integrity_check.v1",
        "asset_id": receipt["asset_id"],
        "hash_and_length_match": matched,
        "receipt_origin_independently_verified": False,
        "c2pa_signature_verified": False,
        "watermark_changed": "NOT_ANALYZED",
        "source_bytes_modified_by_verifier": False,
        "public_release_authorized": False,
        "execution_authority": "none",
    }
