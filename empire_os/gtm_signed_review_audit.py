"""Prepared first-party durable GTM signed-review replay/audit ledger.

Local *protected file* ledger, not another database, service, or timer.
Provisions nothing in production: the caller must supply a pre-existing
private (0700) directory owned by the current process. SQLite not used;
JSONL is append-only under POSIX flock with a hash chain and fsync.
Records are non-PII fingerprints of already signature-verified review claims.
Any corrupt, partial, replaced, or insecure audit state FAILS CLOSED.

Cryptographic hash chains expose internal edits but NOT full-log rollback to
an attacker with file-system ownership; production requires separately
anchored checkpoints, immutable storage/permissions and trusted key issuance.
"""
from __future__ import annotations

import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
from typing import Any, Mapping
from datetime import datetime
from uuid import UUID

from empire_os.gtm_signed_reviewer_gate import (
    GtmReviewerAttestationVerifier, _payload_bytes,
)

SCHEMA = "empire.gtm_reviewer_file_audit.v1"
REC = frozenset((
    "schema_version", "tenant_fingerprint", "reviewer_fingerprint",
    "key_fingerprint", "nonce_fingerprint", "signed_review_sha256",
    "source_url_sha256", "source_content_version_sha256",
    "cohort_evidence_sha256", "decision",
))
LINE = frozenset(("sequence", "previous_sha256", "record", "chain_sha256"))
ZERO = "0" * 64
MAX_BYTES = 8_000_000
MAX_ROWS = 3000
FILENAME = "gtm_signed_review_audit.v1.jsonl"
PREFIX = b"empire-gtm-review-ledger-chain-v1:"


def _encoded(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=True,
                      separators=(",", ":"), allow_nan=False).encode("ascii")


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _line_hash(row: Mapping[str, Any]) -> str:
    return sha256(PREFIX + _encoded(row)).hexdigest()


def _check_snapshot(manifest: Mapping[str, Any], source: str) -> Mapping[str, Any]:
    if (not isinstance(manifest, Mapping)
            or manifest.get("schema_version") != "empire.gtm_review_manifest.v1"
            or manifest.get("mode") != "OBSERVE"
            or manifest.get("authenticated_research_labels") != 0
            or manifest.get("execution_authority") != "NONE"
            or not isinstance(source, str)):
        raise ValueError("trusted_observe_review_manifest_required")
    requests = manifest.get("requests")
    if not isinstance(requests, list) or len(requests) > 25:
        raise ValueError("bounded_source_evidence_manifest_required")
    matches = [
        x for x in requests if isinstance(x, Mapping)
        and x.get("source_url_sha256") == source
    ]
    if len(matches) != 1:
        raise ValueError("unique_current_source_evidence_required")
    fingerprint = matches[0].get("source_content_version_sha256")
    cohort = manifest.get("cohort_evidence_sha256")
    if any(
        not isinstance(value, str) or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
        for value in (source, fingerprint, cohort)
    ):
        raise ValueError("signed_source_and_cohort_fingerprints_required")
    return matches[0]


class GtmSignedReviewAuditLedger:
    """Atomic POSIX file audit, never instantiated by production automatically.

    Requirement: caller-provisioned 0700 dir, owned by the effective UID.
    Only tests may create the directory themselves. Never use a shared /tmp
    path or the source tree as a deployed ledger.
    """

    def __init__(self, directory: Path | str) -> None:
        target = Path(directory)
        if not target.is_absolute() or target.name in (".", ".."):
            raise ValueError("absolute_preprovisioned_private_audit_dir_required")
        self._dir = target

    def _open_dir(self) -> int:
        # O_NOFOLLOW on leaf and check resolved descriptor; no symlinks at
        # the ledger file itself. Do not accept broad/shared directory modes.
        try:
            fd = os.open(self._dir, os.O_RDONLY | os.O_DIRECTORY |
                         os.O_NOFOLLOW | os.O_CLOEXEC)
        except OSError as exc:
            raise ValueError("protected_audit_directory_unavailable") from exc
        info = os.fstat(fd)
        if (not stat.S_ISDIR(info.st_mode)
                or stat.S_IMODE(info.st_mode) != 0o700
                or info.st_uid != os.geteuid()):
            os.close(fd)
            raise ValueError("audit_directory_must_be_owned_private_0700")
        return fd

    @staticmethod
    def _open_log(directory_fd: int, *, create: bool) -> int:
        flags = os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC
        if create:
            flags |= os.O_CREAT
        try:
            fd = os.open(FILENAME, flags, 0o600, dir_fd=directory_fd)
        except FileNotFoundError:
            if not create:
                raise
            raise ValueError("audit_log_unavailable_or_unsafe")
        except OSError as exc:
            raise ValueError("audit_log_unavailable_or_unsafe") from exc
        meta = os.fstat(fd)
        if (not stat.S_ISREG(meta.st_mode)
                or stat.S_IMODE(meta.st_mode) != 0o600
                or meta.st_uid != os.geteuid()
                or meta.st_nlink != 1):
            os.close(fd)
            raise ValueError("audit_log_must_be_owned_private_regular_file")
        return fd

    @staticmethod
    def _read_checked(fd: int) -> list[dict[str, Any]]:
        length = os.fstat(fd).st_size
        if length > MAX_BYTES:
            raise ValueError("audit_log_exceeds_bounded_capacity")
        os.lseek(fd, 0, os.SEEK_SET)
        data = b""
        while len(data) < length:
            block = os.read(fd, min(65536, length - len(data)))
            if not block:
                raise ValueError("audit_log_short_read")
            data += block
        if not data:
            return []
        if not data.endswith(b"\n"):
            raise ValueError("audit_log_partial_or_uncommitted_record")
        raw_lines = data.splitlines()
        if len(raw_lines) > MAX_ROWS:
            raise ValueError("audit_log_exceeds_bounded_event_count")
        rows = []
        previous = ZERO
        replay: set[tuple[str, str, str]] = set()
        per_source: set[tuple[str, str, str, str]] = set()
        for pos, raw in enumerate(raw_lines, 1):
            if len(raw) > 4000:
                raise ValueError("oversized_audit_record")
            try:
                row = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("corrupt_audit_event") from exc
            if not isinstance(row, dict) or set(row) != LINE:
                raise ValueError("wrong_audit_event_fields")
            event = row.get("record")
            if (not isinstance(event, dict) or set(event) != REC
                    or event.get("schema_version") != SCHEMA
                    or type(row.get("sequence")) is not int
                    or row["sequence"] != pos
                    or row.get("previous_sha256") != previous):
                raise ValueError("audit_record_sequence_or_shape_invalid")
            for field in REC - {"schema_version", "decision"}:
                value = event[field]
                if (not isinstance(value, str) or len(value) != 64 or
                        any(char not in "0123456789abcdef" for char in value)):
                    raise ValueError("audit_record_fingerprint_invalid")
            if event["decision"] not in (
                "PUBLIC_ASSOCIATION_RESEARCH_ONLY",
                "UNRESOLVED_AUTHOR_COMPANY_LINK",
                "PARTNERSHIP_NOT_A_BUYER_PROOF",
                "EXTERNAL_EVIDENCE_INSUFFICIENT",
                "REJECT_SOURCE_EVIDENCE",
            ):
                raise ValueError("forbidden_audit_verdict")
            expected = _line_hash({
                "sequence":pos, "previous_sha256":previous,
                "record":event,
            })
            if row.get("chain_sha256") != expected:
                raise ValueError("audit_chain_integrity_failure")
            nonce_key = (
                event["tenant_fingerprint"], event["key_fingerprint"],
                event["nonce_fingerprint"],
            )
            source_reviewer = (
                event["tenant_fingerprint"], event["source_url_sha256"],
                event["cohort_evidence_sha256"], event["reviewer_fingerprint"],
            )
            if nonce_key in replay or source_reviewer in per_source:
                raise ValueError("audited_nonce_or_reviewer_reuse")
            replay.add(nonce_key)
            per_source.add(source_reviewer)
            rows.append(row)
            previous = expected
        return rows

    @staticmethod
    def _check_anchor(rows: list[dict[str, Any]], checkpoint: Mapping[str, Any] | None) -> None:
        if checkpoint is None:
            return
        if (not isinstance(checkpoint, Mapping)
                or set(checkpoint) != {
                    "schema_version", "sequence", "chain_sha256",
                }
                or checkpoint.get("schema_version") !=
                    "empire.gtm_external_audit_checkpoint.v1"
                or type(checkpoint.get("sequence")) is not int
                or checkpoint["sequence"] < 0
                or checkpoint["sequence"] > len(rows)):
            raise ValueError("audit_rollback_against_trusted_checkpoint")
        expected = (rows[checkpoint["sequence"] - 1]["chain_sha256"]
                    if checkpoint["sequence"] else ZERO)
        if checkpoint.get("chain_sha256") != expected:
            raise ValueError("audit_history_diverges_from_trusted_checkpoint")

    def checkpoint(self) -> dict[str, Any]:
        """Export local head for independently secured storage/anchoring.

        Merely returning a digest DOES NOT make it an external checkpoint.
        Do not trust checkpoints from the same writable filesystem alone.
        """
        parent = self._open_dir()
        try:
            try:
                fd = self._open_log(parent, create=False)
            except FileNotFoundError:
                rows = []
            else:
                try:
                    fcntl.flock(fd, fcntl.LOCK_SH)
                    rows = self._read_checked(fd)
                finally:
                    os.close(fd)
        finally:
            os.close(parent)
        return {
            "schema_version":"empire.gtm_external_audit_checkpoint.v1",
            "sequence":len(rows),
            "chain_sha256":rows[-1]["chain_sha256"] if rows else ZERO,
        }

    def append_verified(
        self, *, manifest: Mapping[str, Any],
        source_url_sha256: str, envelope: Mapping[str, Any],
        verifier: GtmReviewerAttestationVerifier,
        tenant_id: str, now: datetime,
        trusted_checkpoint: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(verifier, GtmReviewerAttestationVerifier):
            raise ValueError("trusted_signed_reviewer_verifier_required")
        source = _check_snapshot(manifest, source_url_sha256)
        # Caller has to source tenant from authenticated session/issuer;
        # neither a reviewed post nor a LLM provides tenant authority.
        try:
            canonical = str(UUID(tenant_id))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("canonical_tenant_scope_required") from exc
        if canonical != tenant_id:
            raise ValueError("canonical_tenant_scope_required")
        verified = verifier.verify(
            envelope, source=source,
            cohort_sha256=manifest["cohort_evidence_sha256"],
            tenant_id=tenant_id, now=now,
        )
        record = {
            "schema_version":SCHEMA,
            "tenant_fingerprint":_digest("tenant:" + tenant_id),
            "reviewer_fingerprint":_digest(
                "reviewer:" + tenant_id + ":" + verified["reviewer_id"]
            ),
            "key_fingerprint":_digest("key:" + verified["key_id"]),
            "nonce_fingerprint":_digest("nonce:" + verified["nonce"]),
            "signed_review_sha256":sha256(
                _payload_bytes(envelope["payload"]) +
                envelope["signature"].encode("ascii")
            ).hexdigest(),
            "source_url_sha256":verified["source_url_sha256"],
            "source_content_version_sha256":
                verified["source_content_version_sha256"],
            "cohort_evidence_sha256":manifest["cohort_evidence_sha256"],
            "decision":verified["decision"],
        }
        parent = self._open_dir()
        try:
            fd = self._open_log(parent, create=True)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
                rows = self._read_checked(fd)
                self._check_anchor(rows, trusted_checkpoint)
                # Fresh membership + signature revalidation occurs *after*
                # obtaining the durable lock, not only when the request
                # entered the queue. The issuer must provide fresh scope.
                latest = verifier.verify(
                    envelope, source=source,
                    cohort_sha256=manifest["cohort_evidence_sha256"],
                    tenant_id=tenant_id, now=now,
                )
                if (latest["reviewer_id"] != verified["reviewer_id"]
                        or latest["key_id"] != verified["key_id"]
                        or latest["nonce"] != verified["nonce"]
                        or latest["decision"] != verified["decision"]):
                    raise ValueError("review_identity_changed_before_audit_commit")
                if len(rows) >= MAX_ROWS:
                    raise ValueError("audit_log_full_requires_authorized_rotation")
                for row in rows:
                    existing = row["record"]
                    if (existing["tenant_fingerprint"] == record["tenant_fingerprint"]
                            and existing["key_fingerprint"] == record["key_fingerprint"]
                            and existing["nonce_fingerprint"] == record["nonce_fingerprint"]):
                        raise ValueError("durable_review_replay_blocked")
                    if (existing["tenant_fingerprint"] == record["tenant_fingerprint"]
                            and existing["source_url_sha256"] == record["source_url_sha256"]
                            and existing["cohort_evidence_sha256"] ==
                                record["cohort_evidence_sha256"]
                            and existing["reviewer_fingerprint"] ==
                                record["reviewer_fingerprint"]):
                        raise ValueError("one_independent_review_per_reviewer_per_case")
                seq = len(rows) + 1
                prev = rows[-1]["chain_sha256"] if rows else ZERO
                partial = {"sequence":seq, "previous_sha256":prev, "record":record}
                line = partial | {"chain_sha256":_line_hash(partial)}
                encoded = _encoded(line) + b"\n"
                if os.fstat(fd).st_size + len(encoded) > MAX_BYTES:
                    raise ValueError("audit_log_exceeds_bounded_capacity")
                os.lseek(fd, 0, os.SEEK_END)
                remaining = encoded
                while remaining:
                    wrote = os.write(fd, remaining)
                    if wrote <= 0:
                        raise OSError("audit_append_failed")
                    remaining = remaining[wrote:]
                os.fsync(fd)
                # Persist newly created directory entry.
                os.fsync(parent)
                return {
                    "schema_version":"empire.gtm_durable_review_append.v1",
                    "mode":"OBSERVE",
                    "audit_sequence":seq,
                    "audit_chain_sha256":line["chain_sha256"],
                    "stored_authenticated_review":True,
                    "source_content_proven":False,
                    "reviewer_claim_promoted_to_ground_truth":False,
                    "outbound_authorized":False,
                    "database_writes":False,
                    "execution_authority":"NONE",
                }
            finally:
                os.close(fd)
        finally:
            os.close(parent)

    def read_case(self, *, manifest: Mapping[str, Any],
                  source_url_sha256: str, tenant_id: str,
                  trusted_checkpoint: Mapping[str, Any] | None = None) -> dict[str, Any]:
        source = _check_snapshot(manifest, source_url_sha256)
        try:
            if str(UUID(tenant_id)) != tenant_id:
                raise ValueError()
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError("canonical_tenant_scope_required") from exc
        parent = self._open_dir()
        try:
            try:
                fd = self._open_log(parent, create=False)
            except FileNotFoundError:
                # Only a genuinely absent file counts as zero; broken
                # symlinks and rejected permissions must fail closed.
                self._check_anchor([], trusted_checkpoint)
                return self._summary([], source_url_sha256)
            try:
                fcntl.flock(fd, fcntl.LOCK_SH)
                rows = self._read_checked(fd)
                self._check_anchor(rows, trusted_checkpoint)
            finally:
                os.close(fd)
        finally:
            os.close(parent)
        tenant_hash = _digest("tenant:" + tenant_id)
        matching = [
            row["record"] for row in rows
            if row["record"]["tenant_fingerprint"] == tenant_hash
            and row["record"]["source_url_sha256"] == source_url_sha256
            and row["record"]["source_content_version_sha256"] ==
                source["source_content_version_sha256"]
            and row["record"]["cohort_evidence_sha256"] ==
                manifest["cohort_evidence_sha256"]
        ]
        return self._summary(matching, source_url_sha256)

    @staticmethod
    def _summary(records: list[dict[str, Any]], source_url_sha256: str) -> dict[str, Any]:
        agreement = len(records) >= 2 and len({r["decision"] for r in records}) == 1
        return {
            "schema_version":"empire.gtm_durable_signed_review_summary.v1",
            "mode":"OBSERVE",
            "source_url_sha256":source_url_sha256,
            "durably_authenticated_review_count":len(records),
            "distinct_reviewer_count":len({r["reviewer_fingerprint"] for r in records}),
            "signed_reviewers_agree_research_only":agreement,
            "status":(
                "SIGNED_RESEARCH_AGREEMENT_NOT_PLATFORM_PROOF"
                if agreement else "SIGNED_REVIEW_HOLD_OR_CONFLICT"
            ),
            "accepted_real_research_label_count":0,
            "signed_review_is_not_source_authentication":True,
            "buyer_verified":False,
            "model_retrained":False,
            "outbound_authorized":False,
            "source_attributed_revenue_cents":None,
            "database_writes":False,
            "execution_authority":"NONE",
        }
