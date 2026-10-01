from datetime import datetime, timedelta, timezone

from empire_os.buyer_deferred_enrichment import BuyerDeferredEnrichmentQueue


def _queue(tmp_path):
    return BuyerDeferredEnrichmentQueue(
        deferred_path=tmp_path / "deferred.json",
        call_ready_path=tmp_path / "calls.json",
    )


def test_due_prefers_explicit_commercial_priority(tmp_path):
    q = _queue(tmp_path)
    q.enqueue({"prospect_id":"normal","reason":"no_contact_evidence","priority_score":50})
    q.enqueue({"prospect_id":"enterprise","reason":"no_contact_evidence","priority_score":95})
    due = q.due(limit=2)
    assert [row["prospect_id"] for row in due] == ["enterprise", "normal"]


def test_due_age_boost_prevents_starvation(tmp_path):
    q = _queue(tmp_path)
    q.enqueue({"prospect_id":"old-low","reason":"no_contact_evidence","priority_score":10})
    q.enqueue({"prospect_id":"new-high","reason":"no_contact_evidence","priority_score":95})
    now = datetime.now(timezone.utc)
    import json
    data = json.loads((tmp_path / "deferred.json").read_text())
    data["old-low"]["created_at"] = (now - timedelta(hours=100)).isoformat()
    data["old-low"]["next_retry_at"] = (now - timedelta(minutes=1)).isoformat()
    data["new-high"]["created_at"] = now.isoformat()
    data["new-high"]["next_retry_at"] = (now - timedelta(minutes=1)).isoformat()
    (tmp_path / "deferred.json").write_text(json.dumps(data))
    due = q.due(limit=2, now=now)
    assert [row["prospect_id"] for row in due] == ["old-low", "new-high"]


def test_reenqueue_never_lowers_existing_priority(tmp_path):
    q = _queue(tmp_path)
    q.enqueue({"prospect_id":"p1","reason":"no_contact_evidence","priority_score":95})
    q.enqueue({"prospect_id":"p1","reason":"outreach_not_ready","priority_score":20})
    row = q.due(limit=1)[0]
    assert row["priority_score"] == 95
