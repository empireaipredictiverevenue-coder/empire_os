"""Governed affiliate attribution — signed source tokens and offline revenue review.

Salvages the ref/slug idea from legacy affiliate.py. This has NO SQLite,
network, consumer-PII, live endpoint, commission-write or payout dependencies.
EmpireDB remains the sole canonical money/evidence authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import json
import re
from typing import Any, Iterable, Mapping

SCHEMA_VERSION = "empire.affiliate_tracking_review.v1"
TOKEN_VERSION = "af1"
MAX_LINK_TTL = timedelta(days=30)
FORMATS = frozenset({"PUBLISHER_PPL", "PUBLISHER_PPC", "SAAS_REFERRAL"})
EVENT_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,190}$")
SOURCE_DOMAIN = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{1,245})[a-z0-9]$")
NONCE = re.compile(r"^[A-Za-z0-9_-]{12,64}$")


def _ref(value: Any, label: str) -> str:
    if not isinstance(value, str) or not EVENT_REF.fullmatch(value):
        raise ValueError(f"{label} invalid")
    return value


def _when(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("timezone aware datetime required")
    return value.astimezone(timezone.utc)


def _secret(value: bytes) -> bytes:
    if not isinstance(value, bytes) or len(value) < 32:
        raise ValueError("explicit 32-byte minimum HMAC key required")
    return value


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,1500}", value):
        raise ValueError("invalid referral token encoding")
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


@dataclass(frozen=True)
class AffiliateBinding:
    """A single publisher/program/offer/country combination; not approval."""
    tenant_ref: str
    source_ref: str
    source_domain: str
    programme_ref: str
    offer_format: str
    country_code: str
    source_owner_verified: bool = False
    terms_approved: bool = False
    source_and_subaffiliate_approved: bool = False
    consent_and_privacy_approved: bool = False
    founder_live_authorized: bool = False
    commission_bps: int | None = None

    def validate(self) -> None:
        _ref(self.tenant_ref, "tenant_ref")
        _ref(self.source_ref, "source_ref")
        _ref(self.programme_ref, "programme_ref")
        if (not isinstance(self.source_domain, str)
                or not SOURCE_DOMAIN.fullmatch(self.source_domain)
                or self.source_domain.startswith(("www.", "."))
                or ".." in self.source_domain):
            raise ValueError("verified canonical source domain required")
        if self.offer_format not in FORMATS:
            raise ValueError("unsupported affiliate offer format")
        if self.country_code not in {"US", "UK"}:
            raise ValueError("explicit supported market required")
        for key in ("source_owner_verified", "terms_approved",
                    "source_and_subaffiliate_approved",
                    "consent_and_privacy_approved", "founder_live_authorized"):
            if type(getattr(self, key)) is not bool:
                raise ValueError(f"{key} must be boolean")
        if self.commission_bps is not None and (
            type(self.commission_bps) is not int
            or not 0 <= self.commission_bps <= 10_000
        ):
            raise ValueError("agreed commission basis points invalid")

    def blockers(self) -> tuple[str, ...]:
        self.validate()
        missing = []
        for key in ("source_owner_verified", "terms_approved",
                    "source_and_subaffiliate_approved",
                    "consent_and_privacy_approved", "founder_live_authorized"):
            if not getattr(self, key):
                missing.append(key + "_missing")
        if self.commission_bps is None:
            missing.append("commission_terms_unverified")
        return tuple(missing)


def mint_tracking_token(
    binding: AffiliateBinding,
    *,
    hmac_key: bytes,
    issued_at: datetime,
    expires_at: datetime,
    nonce: str,
) -> str:
    """Pure signing; ONLY a separately approved server adapter can publish it.

    Never use this function as evidence of activated routing or payable revenue.
    """
    binding.validate()
    key = _secret(hmac_key)
    start, end = _when(issued_at), _when(expires_at)
    if not timedelta(0) < end - start <= MAX_LINK_TTL:
        raise ValueError("tracking token lifetime out of bounds")
    if not isinstance(nonce, str) or not NONCE.fullmatch(nonce):
        raise ValueError("opaque nonce required")
    payload = {
        "v": 1, "t": binding.tenant_ref, "s": binding.source_ref, "p": binding.programme_ref,
        "f": binding.offer_format, "c": binding.country_code,
        "d": binding.source_domain,
        "iat": int(start.timestamp()), "exp": int(end.timestamp()),
        "n": nonce,
    }
    encoded = _b64(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
    body = f"{TOKEN_VERSION}.{encoded}"
    signature = _b64(hmac.new(key, body.encode(), hashlib.sha256).digest())
    return f"{body}.{signature}"


def verify_tracking_token(
    token: str,
    binding: AffiliateBinding,
    *,
    hmac_key: bytes,
    now: datetime,
) -> dict[str, Any]:
    binding.validate()
    key = _secret(hmac_key)
    if not isinstance(token, str) or len(token) > 1550:
        raise ValueError("invalid tracking token")
    segments = token.split(".")
    if len(segments) != 3 or segments[0] != TOKEN_VERSION:
        raise ValueError("invalid tracking token version")
    body = ".".join(segments[:2])
    expected = _b64(hmac.new(key, body.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(segments[2], expected):
        raise ValueError("tracking signature mismatch")
    try:
        data = json.loads(_unb64(segments[1]))
    except (ValueError, UnicodeDecodeError, TypeError) as exc:
        raise ValueError("invalid tracking token payload") from exc
    if not isinstance(data, dict) or set(data) != {"v", "t", "s", "p", "f", "c", "d", "iat", "exp", "n"}:
        raise ValueError("invalid tracking token fields")
    if (type(data["v"]) is not int or data["v"] != 1
            or type(data["iat"]) is not int or type(data["exp"]) is not int
            or not 0 < data["exp"] - data["iat"] <= int(MAX_LINK_TTL.total_seconds())
            or data["t"] != binding.tenant_ref
            or data["s"] != binding.source_ref
            or data["p"] != binding.programme_ref
            or data["f"] != binding.offer_format
            or data["c"] != binding.country_code
            or data["d"] != binding.source_domain
            or not isinstance(data["n"], str) or not NONCE.fullmatch(data["n"])):
        raise ValueError("token source, offer or lifetime mismatch")
    current = int(_when(now).timestamp())
    if current < data["iat"] or current >= data["exp"]:
        raise ValueError("tracking token not currently valid")
    return {
        "tenant_ref": data["t"],
        "source_ref": data["s"], "programme_ref": data["p"],
        "offer_format": data["f"], "country_code": data["c"],
        "source_domain": data["d"],
        "issued_at": data["iat"], "expires_at": data["exp"],
        "tracking_token_verified": True,
        "traffic_or_payout_authorized": False,
    }


def _canonical(value: Any, field: str, collection: str) -> str:
    ref = _ref(value, field)
    if not ref.startswith(f"canonical:{collection}:"):
        raise ValueError(f"{field} must reference canonical {collection}")
    return ref


def review_affiliate_outcomes(
    binding: AffiliateBinding,
    outcomes: Iterable[Mapping[str, Any]],
    *,
    hmac_key: bytes,
    now: datetime,
) -> dict[str, Any]:
    """Inspect source-bound event claims; NO reads, payments or ledger mutations.

    Canonical-prefixed references are *pointers*, not independent verification
    that those rows exist. A future least-privilege EmpireDB reader must join
    the underlying immutable events before any commission liability is booked.
    """
    binding.validate()
    _secret(hmac_key)
    _when(now)
    rows = list(outcomes)
    if len(rows) > 100 or any(not isinstance(row, Mapping) for row in rows):
        raise ValueError("bounded structured affiliate event records required")
    blockers: set[str] = set(binding.blockers())
    blockers.add("canonical_payment_event_join_not_performed")
    blockers.add("durable_global_event_idempotency_not_verified")
    blockers.add("publisher_payout_authority_not_granted")
    event_ids: dict[str, str] = {}
    subject_ids: set[str] = set()
    buyer_refs: set[str] = set()
    claims = []
    duplicates = 0
    for raw in rows:
        row = dict(raw)
        reasons = []
        try:
            required_fields = {
                "event_id", "tracking_token", "source_ref", "offer_format",
                "opaque_enquiry_ref", "buyer_acceptance_ref",
                "collected_payment_ref", "fulfilment_ref", "approved_terms_ref",
                "currency", "claimed_collected_cents", "claimed_reversed_cents",
            }
            if set(row) != required_fields:
                raise ValueError("unexpected or missing conversion fields")
            event_id = _ref(row.get("event_id"), "event_id")
            token = verify_tracking_token(
                row.get("tracking_token"), binding,
                hmac_key=hmac_key, now=now,
            )
            assert token["tracking_token_verified"]
            subject_ref = row.get("opaque_enquiry_ref")
            # Canonical upstream privacy controller supplies HMAC-only
            # subject keys, never unhashed phone, email, IP or contact data.
            if (not isinstance(subject_ref, str)
                    or not re.fullmatch(r"subject-hmac-sha256:[0-9a-f]{64}", subject_ref)):
                raise ValueError("opaque privacy-safe subject digest required")
            accepted_ref = _canonical(
                row.get("buyer_acceptance_ref"),
                "buyer_acceptance_ref", "commercial_events",
            )
            money_ref = _canonical(
                row.get("collected_payment_ref"),
                "collected_payment_ref", "verified_payments",
            )
            fulfilment_ref = _canonical(
                row.get("fulfilment_ref"),
                "fulfilment_ref", "fulfilment_orders",
            )
            terms_ref = _canonical(
                row.get("approved_terms_ref"),
                "approved_terms_ref", "commercial_events",
            )
            if row.get("offer_format") != binding.offer_format:
                raise ValueError("conversion offer mismatch")
            if row.get("source_ref") != binding.source_ref:
                raise ValueError("conversion source mismatch")
            claimed_amount = row.get("claimed_collected_cents")
            claimed_reversal = row.get("claimed_reversed_cents")
            if (type(claimed_amount) is not int or claimed_amount <= 0
                    or type(claimed_reversal) is not int
                    or not 0 <= claimed_reversal <= claimed_amount):
                raise ValueError("invalid claimed payment/reversal amounts")
            if row.get("currency") != ("GBP" if binding.country_code == "UK" else "USD"):
                raise ValueError("currency/market mismatch")
            if claimed_reversal == claimed_amount:
                raise ValueError("claimed payment fully reversed")
            fingerprint = hashlib.sha256(json.dumps(
                {k: v for k, v in row.items() if k != "tracking_token"},
                sort_keys=True, default=str, separators=(",", ":"),
            ).encode()).hexdigest()
            if event_id in event_ids:
                duplicates += 1
                if event_ids[event_id] != fingerprint:
                    blockers.add("conflicting_duplicate_event_id")
                continue
            event_ids[event_id] = fingerprint
            if subject_ref in subject_ids:
                duplicates += 1
                blockers.add("duplicate_subject_across_attributed_events")
                continue
            if accepted_ref in buyer_refs:
                duplicates += 1
                blockers.add("buyer_acceptance_reused_by_multiple_events")
                continue
            subject_ids.add(subject_ref)
            buyer_refs.add(accepted_ref)
            claims.append({
                "event_ref": event_id,
                "source_ref": token["source_ref"],
                "offer_format": token["offer_format"],
                "accepted_event_ref": accepted_ref,
                "fulfilment_ref": fulfilment_ref,
                "collected_payment_evidence_pointer": money_ref,
                "approved_terms_evidence_pointer": terms_ref,
                # Don't expose identities, tokens or amount as verified money.
                "collected_amount_independently_verified": False,
                "payable_commission": False,
                "reconciliation_state": "UNVERIFIED_CANONICAL_REFERENCES",
                "provisional_commission_review_cents": (
                    (claimed_amount - claimed_reversal) * binding.commission_bps // 10_000
                    if binding.commission_bps is not None and not binding.blockers()
                    else None
                ),
            })
        except (ValueError, AssertionError, TypeError) as exc:
            reasons.append(str(exc))
        if reasons:
            blockers.add("affiliate_event_evidence_invalid")
    if duplicates:
        blockers.add("duplicate_events_require_canonical_review")
    invalid_count = len(rows) - len(claims) - duplicates
    # A claimed amount must not survive any conflicting, duplicated or
    # invalid item within the same review batch.
    if duplicates or invalid_count:
        for claim in claims:
            claim["provisional_commission_review_cents"] = None
            claim["reconciliation_state"] = "HOLD_BATCH_DUPLICATE_OR_INVALID"
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "OBSERVE",
        "tenant_ref": binding.tenant_ref,
        "source_ref": binding.source_ref,
        "programme_ref": binding.programme_ref,
        "offer_format": binding.offer_format,
        "source_domain": binding.source_domain,
        "source_status": ("PROPOSED_REVIEW_ONLY" if binding.blockers()
                          else "ALL_APPROVAL_FLAGS_CLAIMED_UNVERIFIED"),
        "events_received": len(rows),
        "unique_reviewable_event_count": len(claims),
        "duplicate_event_count": duplicates,
        "invalid_event_count": len(rows) - len(claims) - duplicates,
        "claims": claims,
        "blockers": sorted(blockers),
        "tracked_link_publicly_enabled": False,
        "consumer_data_processed": False,
        "canonical_database_read_performed": False,
        "durable_tracking_event_written": False,
        "recognized_revenue_cents": None,
        "commission_payable_cents": None,
        "publisher_liability_written": False,
        "publisher_payment_authorized": False,
        "affiliate_onboarded": False,
        "traffic_authorized": False,
        "execution_authority": "none",
    }


def affiliate_tracking_readiness(binding: AffiliateBinding) -> dict[str, Any]:
    """No-key diagnostic that can be included in the existing founder review."""
    blockers = list(binding.blockers())
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "OBSERVE",
        "source_ref": binding.source_ref,
        "offer_format": binding.offer_format,
        "source_domain": binding.source_domain,
        "blocking_evidence": blockers + [
            "canonical_payment_event_join_not_performed",
            "durable_global_event_idempotency_not_verified",
        ],
        "tracking_link_live": False,
        "public_signup_enabled": False,
        "buyer_event_postback_enabled": False,
        "payout_authorized": False,
        "publisher_revenue_verified": False,
        "execution_authority": "none",
    }


def affiliate_tracking_capability(*, researched_sources: int | None = None) -> dict[str, Any]:
    """Existing Founder Revenue Distribution handoff, not a running service."""
    if researched_sources is not None and (
        type(researched_sources) is not int or not 0 <= researched_sources <= 1000
    ):
        raise ValueError("bounded researched source count required")
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "OBSERVE",
        "supported_referral_products": sorted(FORMATS),
        "researched_publishers_not_enabled_affiliates": researched_sources,
        "signed_expiring_source_bound_token_codec_testable": True,
        "duplicate_outcome_review_available": True,
        "existing_commercial_event_candidate_builder_available": True,
        "strict_idempotency_readback_comparator_available": True,
        "legacy_sqlite_commission_engine_in_use": False,
        "canonical_empiredb_event_reader_connected": False,
        "durable_global_idempotency_verified": False,
        "public_tracking_link_endpoint_enabled": False,
        "signup_endpoint_enabled": False,
        "click_ingestion_enabled": False,
        "conversion_ingestion_enabled": False,
        "approved_programmes_count": None,
        "commission_payout_authorized": False,
        "actual_revenue_recognized_by_tracking_module": False,
        "execution_authority": "none",
    }


def prepare_canonical_attribution_event(
    binding: AffiliateBinding,
    *,
    tracking_token: str,
    external_event_ref: str,
    opaque_enquiry_ref: str,
    hmac_key: bytes,
    occurred_at: datetime,
) -> dict[str, Any]:
    """Build a deterministic, NON-EXECUTABLE existing-ledger event candidate.

    Uses existing EmpireDB public.commercial_events, not a new affiliate DB.
    Actual append and post-write equality verification remain separately gated.
    """
    import uuid

    observed = _when(occurred_at)
    verified = verify_tracking_token(
        tracking_token, binding, hmac_key=hmac_key, now=observed,
    )
    provider = _ref(external_event_ref, "external_event_ref")
    if (not isinstance(opaque_enquiry_ref, str)
            or not re.fullmatch(r"subject-hmac-sha256:[0-9a-f]{64}", opaque_enquiry_ref)):
        raise ValueError("opaque privacy-safe subject digest required")
    key = "|".join((
        "empire:affiliate:observed:v1", binding.tenant_ref,
        binding.source_ref, binding.programme_ref, binding.offer_format,
        binding.country_code, provider,
    ))
    event_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, key))
    # The canonical ledger already has a unique idempotency_key index.
    # Bind its key and UUID to the same tenant/source/programme/event identity.
    idempotency_key = "affiliate:attribution:v1:" + hashlib.sha256(
        key.encode("utf-8")
    ).hexdigest()
    row = {
        "id": event_uuid,
        "idempotency_key": idempotency_key,
        "event_type": "affiliate_attribution_observed",
        "channel": "affiliate_source_review",
        "actor": "empire_affiliate_tracking",
        "amount_cents": None,
        "cost_cents": None,
        "margin_cents": None,
        "occurred_at": observed.isoformat(),
        "payload": {
            "schema_version": SCHEMA_VERSION,
            "tenant_ref": verified["tenant_ref"],
            "source_ref": verified["source_ref"],
            "programme_ref": verified["programme_ref"],
            "source_domain": verified["source_domain"],
            "offer_format": verified["offer_format"],
            "country_code": verified["country_code"],
            "provider_event_ref": provider,
            "opaque_subject_hmac": opaque_enquiry_ref,
            "token_sha256": hashlib.sha256(tracking_token.encode()).hexdigest(),
            "tracking_signature_checked": True,
            "commercial_terms_verified": False,
            "buyer_event_accepted": False,
            "funds_received": False,
            "actual_revenue": False,
            "execution_authority": "none",
        },
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "OBSERVE",
        "canonical_table": "public.commercial_events",
        "candidate_record": row,
        "deterministic_event_id": event_uuid,
        "canonical_idempotency_key": idempotency_key,
        "database_connection_used": False,
        "insert_performed": False,
        "idempotent_insert_and_exact_readback_required": True,
        "payment_or_payout_authorized": False,
        "execution_authority": "none",
    }



def compare_canonical_attribution_readback(
    candidate: Mapping[str, Any],
    observed_rows: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Pure exact-row comparator for a FUTURE authenticated EmpireDB reader.

    Caller-supplied rows are never treated as independently DB-authenticated.
    No connector, transaction, write, accepted revenue or payment authority.
    In particular, an existing idempotency KEY alone is NOT successful replay.
    """
    import uuid

    if not isinstance(candidate, Mapping):
        raise ValueError("bounded canonical event candidate required")
    payload = candidate.get("payload")
    if (not isinstance(payload, dict)
            or payload.get("schema_version") != SCHEMA_VERSION):
        raise ValueError("not an affiliate attribution candidate")
    required_fields = (
        "id", "idempotency_key", "event_type", "channel", "actor",
        "occurred_at", "payload", "amount_cents", "cost_cents", "margin_cents",
    )
    if any(field not in candidate for field in required_fields):
        raise ValueError("incomplete canonical affiliate event candidate")
    if (candidate.get("event_type") != "affiliate_attribution_observed"
            or candidate.get("channel") != "affiliate_source_review"
            or candidate.get("actor") != "empire_affiliate_tracking"
            or any(candidate.get(k) is not None
                   for k in ("amount_cents", "cost_cents", "margin_cents"))
            or payload.get("actual_revenue") is not False
            or payload.get("funds_received") is not False
            or payload.get("execution_authority") != "none"):
        raise ValueError("invalid nonfinancial attribution event")
    key_parts = (
        "empire:affiliate:observed:v1",
        payload.get("tenant_ref"), payload.get("source_ref"),
        payload.get("programme_ref"), payload.get("offer_format"),
        payload.get("country_code"), payload.get("provider_event_ref"),
    )
    if any(not isinstance(part, str) or not part for part in key_parts):
        raise ValueError("missing affiliate source or tenant identity")
    material = "|".join(key_parts)
    required_id = str(uuid.uuid5(uuid.NAMESPACE_URL, material))
    required_key = ("affiliate:attribution:v1:"
                    + hashlib.sha256(material.encode("utf-8")).hexdigest())
    if (str(candidate["id"]) != required_id
            or candidate["idempotency_key"] != required_key):
        raise ValueError("canonical event identity tampered")
    rows = list(observed_rows)
    if len(rows) > 2 or any(not isinstance(row, Mapping) for row in rows):
        raise ValueError("bounded canonical result required")
    match = False
    if len(rows) == 1:
        actual = rows[0]
        try:
            expected_time = _when(datetime.fromisoformat(
                str(candidate["occurred_at"]).replace("Z", "+00:00")
            ))
            actual_time = actual.get("occurred_at")
            if isinstance(actual_time, str):
                actual_time = datetime.fromisoformat(
                    actual_time.replace("Z", "+00:00")
                )
            match = (
                isinstance(actual_time, datetime)
                and _when(actual_time) == expected_time
                and all(
                    str(actual[k]) == str(candidate[k])
                    if k == "id" else actual[k] == candidate[k]
                    for k in required_fields if k != "occurred_at"
                )
            )
        except (KeyError, ValueError, TypeError):
            match = False
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "OBSERVE",
        "exact_row_shape_matches": match,
        "candidate_key_collision_or_missing": not match,
        "independent_canonical_session_verified": False,
        "readback_was_performed_here": False,
        "durable_event_written_here": False,
        "attribution_or_payment_approved": False,
        "execution_authority": "none",
    }
