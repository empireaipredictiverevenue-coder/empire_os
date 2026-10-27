"""HELD Empire AI first-party collection admission, no route/DB connection.

Only the ORIGINAL acquisition authority and ORIGINAL consent/CMP authority
may sign claims using SEPARATE Ed25519 private keys. Public-key verification
proves signature authenticity, NOT that legally valid consent occurred. This module
never issues claims, mints cookies, opens a database, or enables collection.

The resulting parameter tuples are permitted only for reviewed writer
code, AFTER tenant identity and retention/CMP authority have been independently
bound and the original EmpireDB administrator has granted scoped privileges.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import hmac
import json
import re
from typing import Any
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from empire_os.analytics.first_party_event_contract import ALLOWED_EVENTS
from empire_os.analytics.acquisition_source_v2_candidate import ORIGINAL_EVIDENCE

SCHEMA = "empire.analytics.signed_admission_candidate.v1"
PROPERTY = "empire-ai.co.uk"
PURPOSE = "website_analytics_measurement"
MAX_SOURCE_AGE_SECONDS = 300
MAX_CONSENT_AGE_SECONDS = 120
MAX_SKEW_SECONDS = 30
_HEX64 = re.compile(r"^[a-f0-9]{64}$")
_HEX128 = re.compile(r"^[a-f0-9]{128}$")
_NONCE = re.compile(r"^[a-f0-9]{32}$")
_POLICY = re.compile(r"^[a-z][a-z0-9._-]{3,47}$")
_PAGE = re.compile(r"^[a-z][a-z0-9_]{0,47}$")

# Exact SQL from the ORIGINAL 054 ledger, never data concatenation.
SESSION_SQL = """INSERT INTO public.empire_analytics_sessions
 (tenant_id,property_key,session_digest,acquisition_channel,
  source_evidence_kind,policy_revision,opened_at,expires_at)
 VALUES (%s,%s,%s,%s,%s,%s,clock_timestamp(),
         clock_timestamp()+interval '20 minutes')"""
CONSENT_SQL = """INSERT INTO public.empire_analytics_consent_decisions
 (tenant_id,property_key,session_digest,revision,decision,
  policy_revision,evidence_sha256,evidence_class)
 VALUES (%s,%s,%s,%s,%s,%s,%s,'SERVER_VERIFIED_CMP_DECISION')"""
EVENT_SQL = """INSERT INTO public.empire_analytics_event_receipts
 (tenant_id,property_key,event_digest,session_digest,event_kind,
  page_key,occurred_at)
 VALUES (%s,%s,%s,%s,%s,%s,%s)"""

SOURCE_FIELDS = frozenset({
    "schema", "tenant_id", "property_key", "session_digest",
    "policy_revision", "channel", "evidence_kind", "issued_at",
    "signature",
})
CONSENT_FIELDS = frozenset({
    "schema", "tenant_id", "property_key", "session_digest",
    "policy_revision", "purpose", "decision", "revision",
    "evidence_digest", "issued_at", "signature",
})


class AdmissionHeld(ValueError):
    """No partial evidence, claims, or identifiers are returned on failure."""


def _tenant(value: Any) -> str:
    if type(value) is not str:
        raise AdmissionHeld("TENANT_AUTHORITY_MISSING")
    try:
        parsed = UUID(value)
    except ValueError:
        raise AdmissionHeld("TENANT_AUTHORITY_INVALID") from None
    if str(parsed) != value or parsed.version not in (4, 7):
        raise AdmissionHeld("TENANT_AUTHORITY_INVALID")
    return value


def _digest(value: Any, label: str) -> str:
    if type(value) is not str or not _HEX64.fullmatch(value):
        raise AdmissionHeld(label + "_INVALID")
    return value


def _key(value: Any, label: str) -> bytes:
    if type(value) is not bytes or len(value) < 32:
        raise AdmissionHeld(label + "_KEY_NOT_PROVISIONED")
    return value


def _timestamp(value: Any, *, now: datetime, max_age: int) -> None:
    if type(value) is not int or value <= 0:
        raise AdmissionHeld("EVIDENCE_TIMESTAMP_INVALID")
    if (value > int(now.timestamp()) + MAX_SKEW_SECONDS
            or value < int(now.timestamp()) - max_age):
        raise AdmissionHeld("EVIDENCE_EXPIRED_OR_FUTURE")


def _now(value: Any) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise AdmissionHeld("TRUSTED_SERVER_CLOCK_REQUIRED")
    return value.astimezone(timezone.utc)


def _verify(
    record: Any, *, fields: frozenset[str], purpose: bytes,
    public_key: Ed25519PublicKey, now: datetime, max_age: int,
) -> dict[str, Any]:
    if not isinstance(record, Mapping) or set(record) != fields:
        raise AdmissionHeld("EXACT_SIGNED_RECEIPT_REQUIRED")
    if (record.get("schema") != SCHEMA
            or record.get("property_key") != PROPERTY
            or type(record.get("signature")) is not str):
        raise AdmissionHeld("WRONG_RECEIPT_SCHEMA_OR_PROPERTY")
    sig = record["signature"]
    if not _HEX128.fullmatch(sig):
        raise AdmissionHeld("SIGNATURE_INVALID")
    _tenant(record.get("tenant_id"))
    _digest(record.get("session_digest"), "SESSION_DIGEST")
    if type(record.get("policy_revision")) is not str or not _POLICY.fullmatch(
            record["policy_revision"]):
        raise AdmissionHeld("POLICY_REVISION_INVALID")
    _timestamp(record.get("issued_at"), now=now, max_age=max_age)
    payload = {name: record[name] for name in fields if name != "signature"}
    # Stable JSON encoding binds EVERY field into signature, including tenant.
    try:
        raw = json.dumps(payload, separators=(",", ":"), sort_keys=True,
                         ensure_ascii=True, allow_nan=False).encode("ascii")
    except (TypeError, ValueError, UnicodeError):
        raise AdmissionHeld("UNENCODABLE_SIGNED_RECEIPT") from None
    try:
        public_key.verify(bytes.fromhex(sig), purpose + b":" + raw)
    except InvalidSignature:
        raise AdmissionHeld("OWNER_SIGNATURE_INVALID") from None
    return dict(payload)


class TrustedCollectionAdmission:
    """Signer-independent verifier for the original Analytics054 SQL rows.

    Public keys and current server-authorised tenant identity must come from
    independently authenticated first-party owner controls outside this module.
    The owning CMP must sign decisions, never the browser or this class.
    """

    def __init__(
        self, *, tenant_id: str, acquisition_verify_public_key: bytes,
        consent_verify_public_key: bytes, event_digest_key: bytes,
        session_digest_key: bytes, approved_page_keys: frozenset[str],
        policy_revision: str, verified_owner_config: bool = False,
    ) -> None:
        if verified_owner_config is not True:
            raise AdmissionHeld("ORIGINAL_OWNER_CONFIG_AUTHORITY_UNVERIFIED")
        self._tenant = _tenant(tenant_id)
        source_bytes = acquisition_verify_public_key
        consent_bytes = consent_verify_public_key
        if (type(source_bytes) is not bytes or len(source_bytes) != 32
                or type(consent_bytes) is not bytes or len(consent_bytes) != 32):
            raise AdmissionHeld("ORIGINAL_OWNER_PUBLIC_KEYS_UNVERIFIED")
        self._source_key = Ed25519PublicKey.from_public_bytes(source_bytes)
        self._consent_key = Ed25519PublicKey.from_public_bytes(consent_bytes)
        self._event_key = _key(event_digest_key, "EVENT")
        self._session_key = _key(session_digest_key, "SESSION")
        if len({source_bytes, consent_bytes,
                self._event_key, self._session_key}) != 4:
            raise AdmissionHeld("SEPARATE_OWNER_KEY_DOMAINS_REQUIRED")
        if (type(approved_page_keys) is not frozenset
                or not 1 <= len(approved_page_keys) <= 32
                or any(type(page) is not str or not _PAGE.fullmatch(page)
                       for page in approved_page_keys)):
            raise AdmissionHeld("ORIGINAL_OWNER_PAGE_REGISTRY_UNVERIFIED")
        self._pages = approved_page_keys
        if type(policy_revision) is not str or not _POLICY.fullmatch(policy_revision):
            raise AdmissionHeld("POLICY_REVISION_INVALID")
        self._policy = policy_revision

    def _scope(self, data: Mapping[str, Any]) -> None:
        if (data["tenant_id"] != self._tenant
                or data["property_key"] != PROPERTY
                or data["policy_revision"] != self._policy):
            raise AdmissionHeld("TENANT_PROPERTY_OR_POLICY_MISMATCH")

    def derive_session_digest(self, session_token: bytes) -> str:
        """Derive tenant-scoped HMAC identifier; raw token is never persisted."""
        if type(session_token) is not bytes or len(session_token) != 32:
            raise AdmissionHeld("SERVER_SESSION_TOKEN_UNVERIFIED")
        message = b"empire-session-054|" + self._tenant.encode("ascii") \
            + b"|" + PROPERTY.encode("ascii") + b"|" + session_token
        return hmac.new(self._session_key, message, hashlib.sha256).hexdigest()

    def prepare_session(self, receipt: Mapping[str, Any], *,
                        session_token: bytes, now: datetime) -> tuple[Any, ...]:
        data = _verify(
            receipt, fields=SOURCE_FIELDS, purpose=b"empire-source-054",
            public_key=self._source_key, now=_now(now),
            max_age=MAX_SOURCE_AGE_SECONDS,
        )
        self._scope(data)
        if not hmac.compare_digest(
                data["session_digest"], self.derive_session_digest(session_token)):
            raise AdmissionHeld("SESSION_PROOF_NOT_BOUND_TO_SERVER_ISSUER")
        channel, evidence = data.get("channel"), data.get("evidence_kind")
        if (type(channel) is not str or channel not in ORIGINAL_EVIDENCE
                or type(evidence) is not str
                or ORIGINAL_EVIDENCE[channel] != evidence):
            raise AdmissionHeld("V1_SOURCE_PROOF_INVALID_OR_075_NOT_AUTHORISED")
        return (
            self._tenant, PROPERTY, data["session_digest"], channel,
            evidence, self._policy,
        )

    def prepare_consent(self, receipt: Mapping[str, Any], *,
                        now: datetime) -> tuple[Any, ...]:
        data = _verify(
            receipt, fields=CONSENT_FIELDS, purpose=b"empire-cmp-054",
            public_key=self._consent_key, now=_now(now),
            max_age=MAX_CONSENT_AGE_SECONDS,
        )
        self._scope(data)
        if data.get("purpose") != PURPOSE:
            raise AdmissionHeld("CMP_PURPOSE_UNVERIFIED")
        if type(data.get("decision")) is not str or data["decision"] not in (
                "granted", "denied", "revoked"):
            raise AdmissionHeld("CMP_DECISION_INVALID")
        if type(data.get("revision")) is not int or not 1 <= data["revision"] <= 1_000_000:
            raise AdmissionHeld("CMP_REVISION_INVALID")
        _digest(data.get("evidence_digest"), "CMP_EVIDENCE")
        return (
            self._tenant, PROPERTY, data["session_digest"],
            data["revision"], data["decision"], self._policy,
            data["evidence_digest"],
        )

    def prepare_event(
        self, *, session_digest: str, event_nonce: str, event_kind: str,
        page_key: str, occurred_at: datetime, now: datetime,
    ) -> tuple[Any, ...]:
        session = _digest(session_digest, "SESSION_DIGEST")
        if type(event_nonce) is not str or not _NONCE.fullmatch(event_nonce):
            raise AdmissionHeld("EVENT_NONCE_INVALID")
        if type(event_kind) is not str or event_kind not in ALLOWED_EVENTS:
            raise AdmissionHeld("UNAPPROVED_EVENT_KIND")
        if (type(page_key) is not str or not _PAGE.fullmatch(page_key)
                or page_key not in self._pages):
            raise AdmissionHeld("RAW_URL_OR_UNAPPROVED_PAGE_KEY")
        event_time = _now(occurred_at)
        now_time = _now(now)
        if not (now_time.timestamp()-180 <= event_time.timestamp()
                <= now_time.timestamp()+MAX_SKEW_SECONDS):
            raise AdmissionHeld("EVENT_TIME_OUT_OF_BOUNDS")
        # Server-keyed HMAC; even identical browser nonce is unique to
        # tenant/property/session, with SQL's unique event_digest enforcement.
        message = b"empire-event-054|" + b"|".join(
            v.encode("ascii") for v in (
                self._tenant, PROPERTY, session, event_nonce,
            )
        )
        event_digest = hmac.new(self._event_key, message,
                                hashlib.sha256).hexdigest()
        return (
            self._tenant, PROPERTY, event_digest, session,
            event_kind, page_key, event_time,
        )

    @staticmethod
    def readiness() -> dict[str, Any]:
        return {
            "schema_version": SCHEMA,
            "status": "ORIGINAL_OWNER_AUTHORITY_AND_DB_WRITER_HELD",
            "mode": "CANDIDATE_VERIFICATION_ONLY",
            "database_connection_created": False,
            "website_collector_active": False,
            "runtime_writer_provisioned": False,
            "independent_cmp_legal_consent_proven": False,
            "source_signer_production_integrated": False,
            "consent_signer_production_integrated": False,
            "authenticated_tenant_owner_production_bound": False,
            "only_existing_054_sources_allowed": True,
            "analytics075_activated": False,
            "crm_leads_created": False,
            "finance_settlement_claimed": False,
            "execution_authority": "NONE",
        }
