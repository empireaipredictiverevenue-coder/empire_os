from datetime import datetime, timedelta, timezone

from empire_os.permit_intelligence_runtime import PERMIT_SOURCES
from empire_os.permit_product_integration import build_permit_product_integration


def test_permit_signal_becomes_observed_opportunity_without_fake_demand():
    now = datetime.now(timezone.utc)
    source = sorted(PERMIT_SOURCES)[0]
    result = build_permit_product_integration(
        tenant_id="tenant-a",
        as_of=now,
        permit_signals=[{
            "source": source,
            "tenant_id": "tenant-a",
            "raw": {"id": "permit-1"},
            "last_seen_at": (now - timedelta(minutes=10)).isoformat(),
            "url": "https://example.com/permit/1",
            "metro": "Dallas, TX",
            "status": "filed",
            "evidence_class": "OBSERVED",
        }],
    )

    assert len(result.opportunities) == 1
    assert result.opportunities[0].source_record_id == "permit-1"
    assert result.buyer_product_matches == ()
    assert "buyer_demand_unknown" in result.blockers
    assert result.execution_authority == "none"
    assert result.actual_revenue is False
    assert result.live_delivery_enabled is False


def test_permit_cross_tenant_signal_fails_closed():
    now = datetime.now(timezone.utc)
    source = sorted(PERMIT_SOURCES)[0]
    result = build_permit_product_integration(
        tenant_id="tenant-a",
        as_of=now,
        permit_signals=[{
            "source": source,
            "tenant_id": "tenant-b",
            "raw": {"id": "permit-1"},
            "last_seen_at": now.isoformat(),
            "url": "https://example.com/permit/1",
            "metro": "Dallas, TX",
            "evidence_class": "OBSERVED",
        }],
    )

    assert result.opportunities == ()
    assert "permit_tenant_mismatch" in result.blockers
    assert "permit_evidence_missing" in result.blockers
