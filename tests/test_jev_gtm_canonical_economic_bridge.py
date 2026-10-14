"""Existing authenticated Economic Signal Fabric is the only trust source for JEV bridge."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from empire_os.economic_signal_reader import EconomicSignalReaderError
from empire_os.jev_gtm_canonical_economic_bridge import (
    read_jev_canonical_economic_research,
)

NOW = datetime(2026, 10, 14, 9, tzinfo=timezone.utc)
TENANT, ENTITY, SOURCE, ROW = [str(UUID(int=i)) for i in range(1, 5)]
PERSISTED = "economic_signal_" + "a" * 64
SOURCE_KEYS = {
    "revenue_leak": "empire.revenue_leak.observed.v1",
    "idle_asset": "empire.idle_asset.observed.v1",
    "market_gap": "empire.market_gap.observed.v1",
    "idle_waste": "empire.idle_waste.observed.v1",
}


def economic_row(*, kind="market_gap"):
    meta = {
        "schema_version": "empire.economic-signal.v1",
        "signal_id": PERSISTED,
        "tenant_id": TENANT,
        "tenant_binding_ref": "binding:official:1",
        "evidence_refs": ["source:record:1"],
        "truth_class": "OBSERVED",
        "execution_authority": "none",
    }
    return [
        ROW, ENTITY, kind, "research", NOW - timedelta(hours=1),
        NOW + timedelta(hours=2), 0.8, 0.9, SOURCE,
        SOURCE_KEYS[kind], "observed", 0.8,
        {"_economic_signal": meta}, "binding:official:1",
    ]


class Cursor:
    def __init__(self, *, rows=None, tenant=TENANT):
        self.rows = [economic_row()] if rows is None else rows
        self.tenant = tenant
        self.calls = []

    def execute(self, sql, values=None):
        self.calls.append((sql.strip(), values))

    def fetchone(self):
        if self.calls and self.calls[-1][0].strip() == "SHOW transaction_read_only":
            return ("on",)
        return (self.tenant,)

    def fetchall(self):
        return deepcopy(self.rows)


def read(cursor=None):
    return read_jev_canonical_economic_research(
        cursor or Cursor(), entity_id=ENTITY, as_of=NOW,
    )


def test_auth_tenant_obtained_by_existing_db_reader():
    cur = Cursor()
    result = read(cur)
    assert cur.calls[0][0] == "SHOW transaction_read_only"
    assert cur.calls[1][0] == "SELECT public.empire_current_tenant_id()"
    assert "public.empire_read_economic_signals" in cur.calls[2][0]
    assert cur.calls[2][1] == (ENTITY, NOW)
    assert len(cur.calls) == 3
    assert result["tenant_id"] == TENANT
    assert result["entity_binding_from_observed_signal"] is True
    assert result["signal_types"] == ["market_gap"]
    assert result["signals"][0]["signal_type"] == "market_gap"
    assert result["signals"][0]["evidence_refs"] == ["source:record:1"]


def test_observation_not_qualified_as_buyer_or_contact():
    result = read()
    assert result["commercial_prospect_verified"] is False
    assert result["buyer_intent_verified"] is False
    assert result["contact_identity_verified"] is False
    assert result["suppression_clearance_verified"] is False
    assert result["outbound_approved"] is False
    assert result["canonical_opportunity_id"] is None
    assert result["next_action"] == "RESEARCH_REQUIRED"
    assert result["execution_authority"] == "none"
    assert result["database_write"] is False


@pytest.mark.parametrize("kind", SOURCE_KEYS)
def test_four_economic_families_retained_without_semantic_upgrade(kind):
    row = economic_row(kind=kind)
    result = read(Cursor(rows=[row]))
    assert result["signals"][0]["signal_type"] == kind


def test_empty_source_does_not_invent_entity_binding():
    result = read(Cursor(rows=[]))
    assert result["entity_binding_from_observed_signal"] is False
    assert result["tenant_binding_ref"] is None
    assert result["economic_signal_count"] == 0
    assert result["commercial_prospect_verified"] is False


def test_missing_tenant_fails_before_economic_rpc():
    cur = Cursor(tenant=None)
    with pytest.raises(EconomicSignalReaderError, match="authenticated_tenant_required"):
        read(cur)
    assert len(cur.calls) == 2


def test_cross_tenant_signal_rejected_by_source_reader():
    row = economic_row()
    row[12]["_economic_signal"]["tenant_id"] = str(UUID(int=99))
    with pytest.raises(EconomicSignalReaderError):
        read(Cursor(rows=[row]))


def test_cross_entity_signal_rejected_by_source_reader():
    row = economic_row()
    row[1] = str(UUID(int=99))
    with pytest.raises(EconomicSignalReaderError):
        read(Cursor(rows=[row]))


def test_missing_provenance_never_falls_back_to_claimed_caller_ref():
    row = economic_row()
    del row[12]["_economic_signal"]["evidence_refs"]
    output = read(Cursor(rows=[row]))
    assert output["signals"] == []
    assert output["commercial_prospect_verified"] is False


def test_future_signal_does_not_become_observed_window():
    row = economic_row()
    row[4] = NOW + timedelta(seconds=1)
    result = read(Cursor(rows=[row]))
    assert result["economic_signal_count"] == 0


def test_wrong_identifier_fails_closed():
    with pytest.raises(ValueError, match="entity UUID"):
        read_jev_canonical_economic_research(Cursor(), entity_id="not-a-uuid", as_of=NOW)


def test_unauthorised_sql_raises_without_fallback():
    class Denied(Cursor):
        def execute(self, sql, values=None):
            if "empire_read_economic_signals" in sql:
                raise PermissionError("role denied")
            return super().execute(sql, values)
    with pytest.raises(PermissionError):
        read(Denied())


def test_fingerprint_same_canonical_evidence():
    assert read()["signal_fingerprint"] == read()["signal_fingerprint"]


def test_invalid_clock_fails_before_query():
    cur = Cursor()
    with pytest.raises(ValueError, match="timezone-aware"):
        read_jev_canonical_economic_research(
            cur, entity_id=ENTITY, as_of=NOW.replace(tzinfo=None),
        )
    assert cur.calls == []


def test_bounded_provenance_no_raw_contact_fields():
    result = read()
    assert "email" not in repr(result)
    assert "phone" not in repr(result)
    assert "body_text" not in repr(result)


def test_write_enabled_transaction_holds_before_source_read():
    class NotReadOnly(Cursor):
        def fetchone(self):
            if self.calls and self.calls[-1][0].strip() == "SHOW transaction_read_only":
                return ("off",)
            return super().fetchone()

    cursor = NotReadOnly()
    with pytest.raises(ValueError, match="read-only transaction"):
        read(cursor)
    assert len(cursor.calls) == 1
