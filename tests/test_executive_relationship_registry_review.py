from datetime import datetime, timedelta, timezone

import pytest

from empire_os.executive_relationship_registry_review import summarize_relationship_registry

NOW = datetime(2026, 10, 15, 12, 45, tzinfo=timezone.utc)


def fixture():
    return {
        "schema_version": "empire.commercial_relationship_registry.v1",
        "mode": "OBSERVE", "outbound_authorized": False,
        "outbound_sent": False, "execution_authority": "NONE",
        "generated_at": NOW.isoformat(),
        "gmail_snapshot_captured_at": "2026-10-09T20:47:26Z",
        "gmail_snapshot_fresh": False,
        "automatic_live_gmail_ingest_configured": False,
        "relationships": [
            {"company": "RVNU", "entity_key": "rvnu.com",
             "stage": "CONTACTED_AWAITING_RESPONSE",
             "last_outbound_at": "2026-10-10T21:22:31Z",
             "do_not_pursue": False, "bounced_addresses": []},
            {"company": "Suppressed Co", "entity_key": "suppressed.example",
             "stage": "AWAITING_BUYER", "do_not_pursue": True,
             "bounced_addresses": ["private@example.org"]},
            {"company": "New Research", "entity_key": "research.example",
             "stage": "RESEARCH_ONLY", "bounced_addresses": []},
        ],
    }


def review(payload):
    return summarize_relationship_registry(payload, as_of=NOW)


def test_old_gmail_snapshot_blocks_any_fresh_reply_claim():
    result = review(fixture())
    assert result["status"] == "GMAIL_SNAPSHOT_HOLD"
    assert result["mailbox_current"] is False
    assert result["new_replies_verified"] is False
    assert result["total_relationships"] == 3
    assert result["counts_by_stage"]["RESEARCH_ONLY"] == 1
    assert result["send_authority"] is False
    assert result["revenue_verified"] is False


def test_sent_partner_not_fresh_and_suppression_dominates():
    result = review(fixture())
    cases = {case["entity_key"]: case for case in result["review_queue"]}
    assert cases["rvnu.com"]["prior_outbound_observed"] is True
    assert cases["rvnu.com"]["external_action_authorized"] is False
    assert cases["suppressed.example"]["next_review"] == "NO_CONTACT"
    assert cases["suppressed.example"]["suppression_or_bounce_hold"] is True
    assert "private@example.org" not in str(result)


def test_invalid_source_and_duplicate_company_fail_closed():
    d = fixture()
    d["relationships"].append(dict(d["relationships"][0]))
    assert review(d)["status"] == "INVALID_HELD"
    d = fixture()
    d["outbound_authorized"] = True
    assert review(d)["status"] == "INVALID_HELD"


def test_snapshot_timestamp_and_size_bounds():
    d = fixture()
    d["generated_at"] = (NOW-timedelta(hours=3)).isoformat()
    assert review(d)["status"] == "STALE_HELD"
    d = fixture()
    d["relationships"] = d["relationships"] * 500
    assert review(d)["status"] == "INVALID_HELD"


def test_missing_stays_unknown():
    result = review(None)
    assert result["status"] == "UNAVAILABLE"
    assert result["total_relationships"] is None
    assert result["mailbox_current"] is False


def test_snapshot_requires_timezone():
    with pytest.raises(ValueError):
        summarize_relationship_registry(fixture(), as_of=datetime(2026, 10, 15))


def test_readonly_observer_attaches_registry_without_writes(tmp_path):
    import json
    from empire_os.executive_commercial_observer import observe_executive_commercial_roles
    path = tmp_path / "runtime/buyer_network_intelligence/commercial_relationship_registry_latest.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(fixture()))
    result = observe_executive_commercial_roles(tmp_path, as_of=NOW, service_evidence={})
    reg = result["existing_relationship_registry"]
    assert reg["status"] == "GMAIL_SNAPSHOT_HOLD"
    assert reg["counts_by_stage"]["CONTACTED_AWAITING_RESPONSE"] == 1
    assert reg["suppression_review_count"] == 1
    assert result["external_network_requests"] is False
    assert result["production_changes"] is False
