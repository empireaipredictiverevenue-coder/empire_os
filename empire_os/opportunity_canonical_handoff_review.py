"""Exact-record read-only handoff review for the existing Opportunity Factory.

An Opportunity Factory research key is NOT a canonical GTM opportunity UUID.
A source URL, guessed name, projected value or tenant ID supplied inside a
candidate is NOT a database-backed relationship or commercial authorization.
This emits bounded next work for the existing EmpireOS supervisor only.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from pathlib import Path
from typing import Any, Mapping
from uuid import UUID

BATCH_SCHEMA = "empire.opportunity_factory_intake_batch.v1"
RECORD_SCHEMA = "empire.opportunity_factory_intake.v1"
RESULT_SCHEMA = "empire.opportunity.canonical_handoff_review.v1"
KEY = re.compile(r"^[a-zA-Z0-9][-a-zA-Z0-9:_.\\/, ]{1,179}$")
MAX_ROWS = 200
MAX_BYTES = 1_000_000
MAX_AGE_MINUTES = 180

def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo is not None else None
    except ValueError:
        return None

def _uuid(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return str(UUID(value)) if str(UUID(value)) == value.lower() else None
    except (ValueError, AttributeError, TypeError):
        return None

def _hold(message: str, *, status: str = "BLOCKED") -> dict[str, Any]:
    return {"schema_version": RESULT_SCHEMA, "status": status,
            "source_reviewed": False, "records_reviewed": 0,
            "factory_ready_count": None, "handoff_ready_count": 0,
            "holds": [message], "items": [],
            "canonical_database_binding_verified": False,
            "crm_tenant_binding_verified": False,
            "outbound_authorized": False, "database_writes": False,
            "execution_authority": "NONE"}

def _candidate(row: Mapping[str, Any]) -> dict[str, Any]:
    key = row.get("opportunity_key")
    if (row.get("schema_version") != RECORD_SCHEMA
            or row.get("mode") != "OBSERVE"
            or str(row.get("execution_authority", "")).lower() != "none"
            or not isinstance(key, str) or not KEY.fullmatch(key)):
        raise ValueError("UNTRUSTED_OR_UNKEYED_OPPORTUNITY")
    refs = row.get("evidence_refs")
    if (not isinstance(refs, list) or not 1 <= len(refs) <= 80
            or any(not isinstance(x, str) or not x.strip()
                   or len(x) > 2000 for x in refs)
            or len(refs) != len(set(refs))):
        raise ValueError("UNTRUSTED_SOURCE_REFERENCES")
    if row.get("revenue_verified") is not False:
        raise ValueError("UNVERIFIED_REVENUE_CLAIM")
    if type(row.get("factory_ready")) is not bool:
        raise ValueError("AMBIGUOUS_FACTORY_READINESS")
    count = row.get("evidence_count")
    if type(count) is not int or count < 0 or count > 2000:
        raise ValueError("INVALID_EVIDENCE_COUNT")
    # A coarse table name like canonical:prospect_acquisitions is only a
    # reference to a source family, not provenance for a specific source row.
    row_receipts = [
        ref for ref in refs if ref.startswith("empiredb:")
        and ref.count(":") >= 2 and bool(ref.rsplit(":", 1)[-1])
    ]
    blockers = []
    if not row_receipts:
        blockers.append("SOURCE_ROW_RECEIPT_NOT_BOUND")
    else:
        blockers.append("SOURCE_ROW_RECEIPT_CLAIM_UNVERIFIED_IN_EMPIREDB")
    if row.get("factory_ready") is not True:
        blockers.append("FACTORY_NOT_READY")
    if not _uuid(row.get("opportunity_id")):
        blockers.append("CANONICAL_GTM_OPPORTUNITY_UUID_NOT_PRESENT")
    if not _uuid(row.get("tenant_id")):
        blockers.append("AUTHENTICATED_TENANT_ID_NOT_ATTESTED")
    blockers.extend([
        "CANONICAL_OPPORTUNITY_TO_ENTITY_LINK_NOT_ATTESTED",
        "TENANT_BUSINESS_ENTITY_BINDING_NOT_ATTESTED",
        "BUYER_ACCEPTANCE_AND_TERMS_NOT_ATTESTED",
    ])
    # The research-key fingerprint is for deterministic review idempotency,
    # NOT a generated GTM opportunity identity or a claim of authorisation.
    review_id = "research_review:" + sha256(key.encode("utf-8")).hexdigest()[:24]
    owner = ("OpportunityFactory" if "FACTORY_NOT_READY" in blockers
             else "CanonicalIdentity / SmartCRM")
    return {"review_id": review_id, "opportunity_key": key,
            "opportunity_class": row.get("opportunity_class"),
            "evidence_ref_count": len(refs),
            "claimed_source_row_receipts": len(row_receipts),
            "factory_ready_reported": row["factory_ready"],
            "research_evidence_count": count,
            "canonical_opportunity_id": None,
            "tenant_id": None,
            "next_owner": owner,
            "next_action": ("COMPLETE_REAL_FACTORY_VALIDATION"
                            if owner == "OpportunityFactory"
                            else "VERIFY_EXISTING_EMPIREDB_GTM_ENTITY_TENANT_LINK"),
            "blockers": blockers, "handoff_ready": False,
            "commercial_authority": False, "db_writes": False}

def review_factory_handoffs(raw: Mapping[str, Any] | None, *, now: datetime) -> dict[str, Any]:
    if now.tzinfo is None:
        raise ValueError("NAIVE_HANDOFF_CLOCK")
    if not isinstance(raw, Mapping):
        return _hold("FACTORY_SOURCE_UNAVAILABLE", status="UNAVAILABLE")
    if (raw.get("schema_version") != BATCH_SCHEMA
            or raw.get("mode") != "OBSERVE"
            or str(raw.get("execution_authority", "")).lower() != "none"
            or raw.get("automatic_external_execution_allowed") is not False):
        return _hold("UNSAFE_FACTORY_SOURCE")
    stamped = _timestamp(raw.get("generated_at"))
    age = (now.astimezone(timezone.utc)-stamped).total_seconds()/60 if stamped else None
    if age is None or age < -5 or age > MAX_AGE_MINUTES:
        return _hold("STALE_OR_UNDATED_FACTORY_SOURCE", status="STALE")
    rows = raw.get("items")
    count = raw.get("candidate_count")
    if (not isinstance(rows, list) or len(rows) > MAX_ROWS
            or type(count) is not int or count != len(rows)):
        return _hold("FACTORY_BATCH_COUNT_OR_SCOPE_MISMATCH")
    try:
        reviewed = [_candidate(row) for row in rows]
    except (ValueError, TypeError, AttributeError):
        return _hold("INVALID_CANONICAL_HANDOFF_CANDIDATE")
    keys = [r["opportunity_key"] for r in reviewed]
    if len(set(keys)) != len(keys):
        return _hold("DUPLICATE_RESEARCH_OPPORTUNITY_KEY")
    if type(raw.get("factory_ready_count")) is not int or raw["factory_ready_count"] != sum(
        x["factory_ready_reported"] for x in reviewed
    ):
        return _hold("FACTORY_READY_COUNT_MISMATCH")
    return {"schema_version": RESULT_SCHEMA, "status": "RESEARCH_HANDOFF_HOLD",
            "source_reviewed": True, "records_reviewed": len(reviewed),
            "factory_ready_count": raw["factory_ready_count"],
            "handoff_ready_count": 0,
            "holds": ["NO_INDEPENDENT_CANONICAL_OPPORTUNITY_ENTITY_TENANT_JOIN"],
            "items": sorted(reviewed, key=lambda x: (-x["research_evidence_count"], x["opportunity_key"])),
            "generated_at": now.astimezone(timezone.utc).isoformat(),
            "canonical_database_binding_verified": False,
            "crm_tenant_binding_verified": False,
            "outbound_authorized": False, "database_writes": False,
            "execution_authority": "NONE"}

def from_existing_factory(root: Path, *, now: datetime) -> dict[str, Any]:
    path = root / "runtime/opportunity_factory/intake_latest.json"
    try:
        if path.is_symlink() or not path.is_file():
            return _hold("FACTORY_SOURCE_UNAVAILABLE", status="UNAVAILABLE")
        if path.stat().st_size > MAX_BYTES:
            return _hold("OVERSIZED_FACTORY_SOURCE")
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return _hold("FACTORY_SOURCE_UNAVAILABLE", status="UNAVAILABLE")
    return review_factory_handoffs(value, now=now)
