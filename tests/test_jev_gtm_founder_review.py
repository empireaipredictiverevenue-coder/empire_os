from datetime import datetime, timedelta, timezone
from uuid import UUID
from copy import deepcopy

from empire_os.jev_gtm_founder_review import build_jev_founder_economic_review

NOW = datetime(2026, 10, 14, 9, tzinfo=timezone.utc)
TENANT, ENTITY, SOURCE, ROW = [str(UUID(int=i)) for i in range(1, 5)]


class FakeCursor:
    def __init__(self, rows=None):
        self.tenant = TENANT
        self.rows = rows if rows is not None else [self.fixture()]
        self.calls = []

    def fixture(self):
        return [
            ROW, ENTITY, "revenue_leak", "revenue",
            NOW - timedelta(hours=1), NOW + timedelta(hours=1),
            0.8, 0.9, SOURCE, "empire.revenue_leak.observed.v1",
            "observed", 0.5, {
                "_economic_signal": {
                    "schema_version": "empire.economic-signal.v1",
                    "signal_id": "economic_signal_" + "c" * 64,
                    "tenant_id": TENANT,
                    "tenant_binding_ref": "binding:1",
                    "evidence_refs": ["source:1"],
                    "truth_class": "OBSERVED",
                    "execution_authority": "none",
                }
            }, "binding:1",
        ]

    def execute(self, statement, params=None):
        self.calls.append((statement, params))

    def fetchone(self):
        if self.calls and self.calls[-1][0].strip() == "SHOW transaction_read_only":
            return ("on",)
        return (self.tenant,)

    def fetchall(self):
        return deepcopy(self.rows)


def test_founder_summary_reports_typed_economic_counts():
    cursor = FakeCursor()
    result = build_jev_founder_economic_review(cursor, entity_id=ENTITY, as_of=NOW)
    assert result["signal_count"] == 1
    assert result["signals_by_type"]["revenue_leak"] == 1
    assert result["execution_authority"] == "none"
    assert result["contact_clearance_available"] is False
    assert result["buyer_conversations_verified"] is False
    assert "tenant_id" not in result
    assert len(cursor.calls) == 3


def test_empty_economic_source_is_unavailable():
    result = build_jev_founder_economic_review(
        FakeCursor(rows=[]), entity_id=ENTITY, as_of=NOW,
    )
    assert result["status"] == "NO_CANONICAL_ECONOMIC_EVIDENCE"
    assert result["entity_binding_from_observed_signal"] is False
