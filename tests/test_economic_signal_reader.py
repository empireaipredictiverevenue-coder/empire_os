
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from empire_os.economic_signal_reader import (
    EconomicSignalReaderError, read_economic_signals,
)

NOW = datetime(2026, 10, 6, 10, tzinfo=timezone.utc)
TENANT, ENTITY, SOURCE, ROW = [str(UUID(int=i)) for i in range(1, 5)]
PERSISTED = "economic_signal_" + "a" * 64


def signal_row(kind="revenue_leak"):
    metadata = {
        "schema_version": "empire.economic-signal.v1",
        "signal_id": PERSISTED,
        "tenant_id": TENANT,
        "tenant_binding_ref": "lab:binding",
        "evidence_refs": ["lab:observed"],
        "truth_class": "OBSERVED",
        "execution_authority": "none",
    }
    return [
        ROW, ENTITY, kind, "revenue",
        NOW - timedelta(hours=1), NOW + timedelta(hours=1),
        0.8, 0.9, SOURCE, f"empire.{kind}.observed.v1",
        "observed", 0.5, {"_economic_signal": metadata}, "lab:binding",
    ]


class Cursor:
    def __init__(self, rows=None, tenant=TENANT, error=None):
        self.rows = rows if rows is not None else [signal_row()]
        self.tenant = tenant
        self.error = error
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))
        if "empire_read_economic_signals" in sql and self.error:
            raise self.error

    def fetchone(self):
        return (self.tenant,)

    def fetchall(self):
        return deepcopy(self.rows)


def read(cursor):
    return read_economic_signals(cursor, entity_id=ENTITY, as_of=NOW)


def test_uses_only_resolver_and_governed_rpc():
    cursor = Cursor()
    result = read(cursor)
    assert result["accepted_count"] == 1
    assert len(cursor.calls) == 2
    assert cursor.calls[0][0] == "SELECT public.empire_current_tenant_id()"
    assert "FROM public.empire_read_economic_signals(" in cursor.calls[1][0]
    assert cursor.calls[1][1] == (ENTITY, NOW)
    assert "tenant_business_entity_bindings" not in repr(cursor.calls)
    assert "FROM public.intelligence_signals" not in repr(cursor.calls)


def test_nested_evidence_and_both_identities_preserved():
    row = signal_row()
    row[12]["evidence_refs"] = ["untrusted:top-level"]
    item = read(Cursor([row]))["accepted"][0]
    assert item["evidence_refs"] == ["lab:observed"]
    assert item["persisted_signal_id"] == PERSISTED
    assert item["signal_row_id"] == ROW
    assert item["signal_id"].startswith("economic_signal_")


def test_no_top_level_evidence_fallback():
    row = signal_row()
    del row[12]["_economic_signal"]["evidence_refs"]
    row[12]["evidence_refs"] = ["untrusted:top-level"]
    result = read(Cursor([row]))
    assert result["accepted_count"] == 0
    assert result["rejected_count"] == 1


@pytest.mark.parametrize("field,value", [
    ("tenant_id", str(UUID(int=99))),
    ("tenant_binding_ref", "wrong:binding"),
    ("truth_class", "PREDICTED"),
    ("execution_authority", "execute"),
    ("signal_id", "invalid"),
    ("schema_version", "unknown"),
])
def test_metadata_contract_fails_closed(field, value):
    row = signal_row()
    row[12]["_economic_signal"][field] = value
    with pytest.raises(EconomicSignalReaderError):
        read(Cursor([row]))


@pytest.mark.parametrize("index,value", [
    (1, str(UUID(int=99))),
    (9, "wrong:source"),
    (12, {}),
    (13, ""),
])
def test_rpc_scope_contract_fails_closed(index, value):
    row = signal_row()
    row[index] = value
    with pytest.raises(EconomicSignalReaderError):
        read(Cursor([row]))


def test_missing_tenant_stops_before_rpc():
    cursor = Cursor(tenant=None)
    with pytest.raises(EconomicSignalReaderError, match="authenticated_tenant_required"):
        read(cursor)
    assert len(cursor.calls) == 1


def test_database_denial_propagates_without_fallback():
    cursor = Cursor(error=PermissionError("denied"))
    with pytest.raises(PermissionError):
        read(cursor)
    assert len(cursor.calls) == 2


def test_empty_result_does_not_invent_binding():
    result = read(Cursor([]))
    assert result["accepted_count"] == 0
    assert result["tenant_binding_ref"] is None
    assert result["binding_kind"] is None


@pytest.mark.parametrize("kind", [
    "revenue_leak", "idle_asset", "market_gap", "idle_waste",
])
def test_all_four_families(kind):
    assert read(Cursor([signal_row(kind)]))["accepted_count"] == 1


@pytest.mark.parametrize("index,value", [
    (4, NOW - timedelta(hours=25)),
    (4, NOW + timedelta(seconds=1)),
    (5, NOW),
    (6, float("nan")),
    (7, 2),
])
def test_fabric_validation_still_applies(index, value):
    row = signal_row()
    row[index] = value
    result = read(Cursor([row]))
    assert result["accepted_count"] == 0
    assert result["rejected_count"] == 1


def test_duplicate_rows_collapse():
    row = signal_row()
    assert read(Cursor([row, row]))["accepted_count"] == 1


def test_persisted_identity_collision_stops_read():
    first = signal_row()
    second = signal_row()
    second[0] = str(UUID(int=99))
    with pytest.raises(EconomicSignalReaderError, match="collision"):
        read(Cursor([first, second]))


def test_authorities_remain_none():
    result = read(Cursor())
    for key in (
        "execution_authority", "outreach_authority", "calls_authority",
        "traffic_authority", "commercial_authority", "payment_authority",
        "revenue_recognition_authority",
    ):
        assert result[key] == "none"
        assert result["accepted"][0][key] == "none"
    assert result["automatic_external_execution_allowed"] is False
