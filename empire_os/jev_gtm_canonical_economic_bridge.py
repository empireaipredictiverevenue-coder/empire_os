"""JEV GTM read-only bridge to Empire's existing authenticated Economic Signal Fabric.

Never substitutes an economic observation for a qualified buyer, and never
takes tenant_id from caller input. Caller must supply a restricted read-only
session cursor; Economic Signal Reader gets the tenant from the database.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping
from uuid import UUID

from empire_os.economic_signal_reader import read_economic_signals
from empire_os.economic_signal_fabric import SUPPORTED_SIGNAL_TYPES

SCHEMA_VERSION = "empire.jev.canonical_economic_research_bridge.v1"
MAX_SIGNALS = 100


def _canonical_uuid(value: Any) -> str:
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("canonical entity UUID required") from exc


def _safe_source(row: Mapping[str, Any], *, entity_id: str, tenant_id: str, as_of: datetime) -> dict[str, Any]:
    if row.get("tenant_id") != tenant_id or row.get("entity_id") != entity_id:
        raise ValueError("economic evidence crossed canonical scope")
    if (row.get("truth_class") != "OBSERVED"
            or row.get("signal_type") not in SUPPORTED_SIGNAL_TYPES
            or row.get("execution_authority") != "none"
            or row.get("outreach_authority") != "none"):
        raise ValueError("economic evidence attempted authority escalation")
    identifier = row.get("persisted_signal_id")
    refs = row.get("evidence_refs")
    source = row.get("source_id")
    stamp = row.get("observed_at")
    binding = row.get("tenant_binding_ref")
    if (not isinstance(identifier, str) or not identifier.startswith("economic_signal_")
            or not isinstance(refs, (tuple, list)) or not refs
            or any(not isinstance(ref, str) or not ref.strip() for ref in refs)
            or not isinstance(source, str) or not source.strip()
            or not isinstance(binding, str) or not binding.strip()
            or not isinstance(stamp, str)):
        raise ValueError("economic evidence incomplete")
    try:
        observed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("economic evidence timestamp invalid") from exc
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError("economic evidence timezone missing")
    age = (as_of - observed.astimezone(timezone.utc)).total_seconds()
    if age < 0 or age > 86400:
        raise ValueError("economic evidence freshness failure")
    return {
        "signal_id": identifier,
        "signal_type": row["signal_type"],
        "source_id": source,
        "source_key": row["signal_type"],
        "entity_id": entity_id,
        "tenant_id": tenant_id,
        "tenant_binding_ref": binding,
        "truth_class": "OBSERVED",
        "observed_at": observed.astimezone(timezone.utc).isoformat(),
        "evidence_refs": list(dict.fromkeys(refs)),
        "modelled_buying_intent": False,
        "source_revision": str(row.get("signal_row_id") or ""),
    }


def read_jev_canonical_economic_research(
    cursor: Any, *, entity_id: str, as_of: datetime
) -> dict[str, Any]:
    """Read only canonical, independently scoped signal metadata.

    The cursor's database session and READ ONLY transaction must be
    authenticated/established by the existing session owner. No role escalation,
    new DB login, SQL joins, evidence materialization or contact access here.
    """
    entity = _canonical_uuid(entity_id)
    if not isinstance(as_of, datetime) or as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("timezone-aware as_of required")
    instant = as_of.astimezone(timezone.utc)
    # A caller-supplied cursor is NOT, on its own, proof of a read-only DB
    # transaction. Check the active server transaction state first.
    cursor.execute("SHOW transaction_read_only")
    transaction = cursor.fetchone()
    if (not isinstance(transaction, (tuple, list)) or len(transaction) != 1
            or transaction[0] not in ("on", True)):
        raise ValueError("dedicated read-only transaction required")
    source = read_economic_signals(cursor, entity_id=entity, as_of=instant)
    if (source.get("schema_version") != "empire.economic-signal-reader.v2"
            or source.get("entity_id") != entity
            or source.get("execution_authority") != "none"
            or source.get("outreach_authority") != "none"
            or source.get("automatic_external_execution_allowed") is not False):
        raise ValueError("untrusted canonical economic reader contract")
    tenant = _canonical_uuid(source.get("tenant_id"))
    accepted = source.get("accepted")
    if not isinstance(accepted, list) or len(accepted) > MAX_SIGNALS:
        raise ValueError("unbounded canonical evidence")
    if source.get("accepted_count") != len(accepted):
        raise ValueError("canonical evidence count mismatch")
    binding = source.get("tenant_binding_ref")
    if accepted and (not isinstance(binding, str) or not binding.strip()):
        raise ValueError("canonical tenant binding missing")
    signals = [_safe_source(s, entity_id=entity, tenant_id=tenant, as_of=instant) for s in accepted]
    if signals and any(s["tenant_binding_ref"] != binding for s in signals):
        raise ValueError("mixed tenant binding evidence")
    if len({s["signal_id"] for s in signals}) != len(signals):
        raise ValueError("duplicate canonical economic signal")
    # No entity binding can be asserted for empty sources. No buyer identity
    # nor contact consent can ever be inferred from this economic reader.
    fingerprint = sha256("|".join(sorted(s["signal_id"] + ":" + s["source_revision"] for s in signals)).encode()).hexdigest()
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "OBSERVE",
        "tenant_id": tenant,
        "entity_id": entity,
        "tenant_binding_ref": binding if signals else None,
        "entity_binding_from_observed_signal": bool(signals and binding),
        "economic_signal_count": len(signals),
        "signal_types": sorted({s["signal_type"] for s in signals}),
        "signals": signals,
        "signal_fingerprint": fingerprint,
        "quarantined_source_count": source.get("rejected_count"),
        "commercial_prospect_verified": False,
        "buyer_intent_verified": False,
        "contact_identity_verified": False,
        "suppression_clearance_verified": False,
        "canonical_opportunity_id": None,
        "next_action": "RESEARCH_REQUIRED",
        "outbound_approved": False,
        "execution_authority": "none",
        "database_write": False,
        "source_reader": "empire_os.economic_signal_reader",
    }
