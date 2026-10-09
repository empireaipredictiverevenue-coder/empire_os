"""Trusted canonical Economic Signal Fabric reader.

Trust boundary:

authenticated PostgreSQL session
    -> empire_current_tenant_id()
    -> empire_read_economic_signals() governed database boundary
    -> Economic Signal Fabric validation

The reader performs no writes and grants no execution authority.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from empire_os.economic_signal_fabric import (
    SUPPORTED_SIGNAL_TYPES,
    normalize_economic_signals,
)


ECONOMIC_SIGNAL_SOURCE_KEYS = {
    "revenue_leak": "empire.revenue_leak.observed.v1",
    "idle_asset": "empire.idle_asset.observed.v1",
    "market_gap": "empire.market_gap.observed.v1",
    "idle_waste": "empire.idle_waste.observed.v1",
}


class EconomicSignalReaderError(RuntimeError):
    pass


def _uuid(value: Any, *, field: str) -> str:
    text = str(value or "").strip()
    try:
        return str(UUID(text))
    except (ValueError, TypeError, AttributeError) as exc:
        raise EconomicSignalReaderError(
            f"invalid_{field}"
        ) from exc


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise EconomicSignalReaderError(
            "aware_as_of_required"
        )
    return value.astimezone(timezone.utc)


def _authenticated_tenant_id(cursor: Any) -> str:
    cursor.execute(
        "SELECT public.empire_current_tenant_id()"
    )
    row = cursor.fetchone()

    if row is None or row[0] is None:
        raise EconomicSignalReaderError(
            "authenticated_tenant_required"
        )

    return _uuid(row[0], field="authenticated_tenant")


def _rows(cursor: Any) -> list[Any]:
    result = cursor.fetchall()
    return list(result or [])



def read_economic_signals(
    cursor: Any, *, entity_id: str, as_of: datetime,
) -> dict[str, Any]:
    """Read through 039; callers cannot supply tenant identity.

    Empty results do not prove whether an entity binding exists.
    Binding kind is unknown because 039 does not return it.
    Fabric identity and persisted writer identity remain explicit.
    """
    import re

    instant = _aware(as_of)
    entity = _uuid(entity_id, field="entity_id")
    tenant = _authenticated_tenant_id(cursor)
    cursor.execute(
        """SELECT signal_id, entity_id, signal_type, signal_domain,
                  observed_at, expires_at, strength, confidence,
                  source_id, source_key, source_type,
                  source_authority_score, payload, tenant_binding_ref
           FROM public.empire_read_economic_signals(%s::uuid, %s::timestamptz)""",
        (entity, instant),
    )

    candidates = []
    quarantined = []
    stored_rows = {}

    for index, row in enumerate(_rows(cursor)):
        try:
            (
                row_id, row_entity, signal_type, domain,
                observed, expires, strength, confidence,
                source_id, source_key, source_type,
                source_authority, payload, binding_ref,
            ) = row
            row_id = _uuid(row_id, field="signal_row_id")
            if _uuid(row_entity, field="entity_id") != entity:
                raise EconomicSignalReaderError("entity_scope_mismatch")
            if (
                signal_type not in SUPPORTED_SIGNAL_TYPES
                or source_key != ECONOMIC_SIGNAL_SOURCE_KEYS[signal_type]
            ):
                raise EconomicSignalReaderError("source_signal_type_mismatch")
            if not isinstance(payload, dict):
                raise EconomicSignalReaderError("economic_metadata_required")
            metadata = payload.get("_economic_signal")
            if not isinstance(metadata, dict):
                raise EconomicSignalReaderError("economic_metadata_required")
            if metadata.get("tenant_id") != tenant:
                raise EconomicSignalReaderError("tenant_scope_mismatch")
            if (
                not isinstance(binding_ref, str)
                or not binding_ref.strip()
                or metadata.get("tenant_binding_ref") != binding_ref
            ):
                raise EconomicSignalReaderError("binding_scope_mismatch")
            if (
                metadata.get("schema_version") != "empire.economic-signal.v1"
                or metadata.get("truth_class") != "OBSERVED"
                or metadata.get("execution_authority") != "none"
            ):
                raise EconomicSignalReaderError("economic_metadata_invalid")
            persisted_id = metadata.get("signal_id")
            if (
                not isinstance(persisted_id, str)
                or re.fullmatch(r"economic_signal_[0-9a-f]{64}", persisted_id) is None
            ):
                raise EconomicSignalReaderError("persisted_signal_id_invalid")
            if persisted_id in stored_rows and stored_rows[persisted_id] != row_id:
                raise EconomicSignalReaderError("persisted_signal_id_collision")
            stored_rows[persisted_id] = row_id
            candidates.append({
                "tenant_id": tenant,
                "tenant_binding_ref": binding_ref,
                "entity_id": entity,
                "source_id": _uuid(source_id, field="source_id"),
                "signal_type": signal_type,
                "signal_domain": domain,
                "observed_at": observed.isoformat(),
                "expires_at": expires.isoformat() if expires is not None else None,
                "strength": float(strength),
                "confidence": float(confidence),
                "evidence_refs": metadata.get("evidence_refs"),
                "payload": payload,
                "truth_class": "OBSERVED",
                "data_backend": "empiredb",
            })
        except EconomicSignalReaderError as exc:
            # Contract/scope failures stop the complete read.
            raise EconomicSignalReaderError(f"row_{index}:{exc}") from exc
        except (TypeError, ValueError, AttributeError) as exc:
            raise EconomicSignalReaderError(
                f"row_{index}:invalid_rpc_row"
            ) from exc

    normalized = normalize_economic_signals(
        candidates, expected_tenant_id=tenant, as_of=instant,
    )
    accepted = normalized["accepted"]
    for item in accepted:
        persisted_id = item["payload"]["_economic_signal"]["signal_id"]
        item["persisted_signal_id"] = persisted_id
        item["signal_row_id"] = stored_rows[persisted_id]

    refs = {item["tenant_binding_ref"] for item in accepted}
    if len(refs) > 1:
        raise EconomicSignalReaderError("tenant_entity_binding_ambiguous")

    return {
        "schema_version": "empire.economic-signal-reader.v2",
        "tenant_id": tenant,
        "entity_id": entity,
        "tenant_binding_ref": next(iter(refs)) if refs else None,
        "binding_kind": None,
        "accepted": accepted,
        "rejected": normalized["rejected"],
        "quarantined": quarantined,
        "accepted_count": normalized["accepted_count"],
        "rejected_count": normalized["rejected_count"],
        "quarantined_count": 0,
        "conflicting_signal_ids": normalized["conflicting_signal_ids"],
        "execution_authority": "none",
        "outreach_authority": "none",
        "calls_authority": "none",
        "traffic_authority": "none",
        "commercial_authority": "none",
        "payment_authority": "none",
        "revenue_recognition_authority": "none",
        "automatic_external_execution_allowed": False,
    }
