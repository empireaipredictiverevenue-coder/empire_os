"""Read-only relationship-history guards: prior contact is never new outreach."""
from datetime import datetime, timedelta, timezone
import pytest
from empire_os.leadgen_contact_history_bridge import build_contact_history_review
from empire_os.leadgen_revenue_activation_queue import build_leadgen_revenue_queue
from tests.test_leadgen_revenue_activation_queue_20261019 import snapshots

NOW = datetime(2026, 10, 19, 15, 55, tzinfo=timezone.utc)

def registry():
    return {
        "schema_version": "empire.commercial_relationship_registry.v1",
        "generated_at": (NOW - timedelta(minutes=5)).isoformat(),
        "execution_authority": "NONE",
        "outbound_authorized": False,
        "gmail_snapshot_fresh": False,
        "relationships": [
            {"identity_domains": ["acme-roofing-buyers.com"],
             "last_outbound_at": (NOW - timedelta(days=2)).isoformat(),
             "last_inbound_at": (NOW - timedelta(days=1)).isoformat(),
             "do_not_pursue": False},
            {"identity_domains": ["dental-partners.co.uk"],
             "last_outbound_at": None, "last_inbound_at": None,
             "do_not_pursue": True},
        ],
    }

def test_historical_contact_and_suppression_keep_no_send():
    out = build_contact_history_review(
        registry(), ["acme-roofing-buyers.com", "dental-partners.co.uk",
                     "roofing-network.com", "o123.ingest.us.sentry.io"],
        now=NOW,
    )
    assert out["counts"]["existing_thread_review"] == 1
    assert out["counts"]["history_unverified"] == 1
    assert out["counts"]["do_not_pursue"] == 1
    assert out["counts"]["technical_host_hold"] == 1
    assert out["counts"]["inbound_review"] == 1
    assert out["mailbox_snapshot_fresh"] is False
    assert out["history_coverage_complete"] is False
    assert out["by_domain"]["acme-roofing-buyers.com"]["contact_state"] == "EXISTING_THREAD_REVIEW"
    assert out["by_domain"]["dental-partners.co.uk"]["contact_state"] == "DO_NOT_PURSUE"
    assert out["by_domain"]["roofing-network.com"]["contact_state"] == "HISTORY_UNVERIFIED"
    assert out["by_domain"]["o123.ingest.us.sentry.io"]["contact_state"] == "NON_BUYER_TECHNICAL_HOST"
    assert all(x["new_first_touch_authorized"] is False for x in out["by_domain"].values())

def test_history_principle_orders_existing_thread_without_permission():
    e, b = snapshots()
    out = build_leadgen_revenue_queue(
        exchange=e, buyer_actions=b, relationship_history=registry(), now=NOW
    )
    assert out["state"] == "FOUNDER_RESEARCH_QUEUE_READY"
    assert out["known_existing_contact_count"] == 1
    assert out["contact_history_unverified_count"] == 1
    assert out["do_not_pursue_count"] == 1
    assert out["founder_research_queue"][0]["domain"] == "acme-roofing-buyers.com"
    assert out["ready_for_outbound"] == 0
    assert out["buyer_outreach_authorized"] is False

@pytest.mark.parametrize("field,value", [
    ("execution_authority", "SEND"),
    ("outbound_authorized", True),
    ("schema_version", "untrusted"),
    ("relationships", [{}] * 3001),
])
def test_invalid_relationship_receipt_fails_closed(field, value):
    r = registry()
    r[field] = value
    with pytest.raises(ValueError):
        build_contact_history_review(r, ["acme-roofing-buyers.com"], now=NOW)

def test_false_or_future_timestamps_fail_closed():
    r = registry()
    r["relationships"][0]["last_outbound_at"] = (
        NOW + timedelta(days=1)
    ).isoformat()
    with pytest.raises(ValueError):
        build_contact_history_review(r, ["acme-roofing-buyers.com"], now=NOW)
