import empire_os.hunter.enrichment_worker as worker


class FakeReport:
    pages_checked = 3
    evidence_score = 0.9
    contacts = ()
    confirmed_contacts = ()
    outreach_ready = False


def test_enrichment_cycle_is_bounded_and_internal(monkeypatch, tmp_path):
    monkeypatch.setattr(
        worker,
        "build_priority_queue",
        lambda limit: {
            "items": [
                {
                    "entity_id": "e1",
                    "contact_ready": False,
                    "depth": "shallow",
                    "priority_score": 60,
                }
            ]
        },
    )
    monkeypatch.setattr(
        worker,
        "_entity",
        lambda eid: {
            "id": eid,
            "canonical_name": "Acme",
            "canonical_website": "https://acme.test",
        },
    )
    monkeypatch.setattr(
        worker,
        "analyze_domain",
        lambda *args, **kwargs: FakeReport(),
    )
    monkeypatch.setattr(
        worker,
        "build_evidence_plan",
        lambda report, entity_id: object(),
    )

    class Materializer:
        def materialize(self, plan, *, write_authorized):
            return {
                "write_authorized": write_authorized,
                "outbound_actions": False,
            }

    monkeypatch.setattr(
        worker,
        "SupabaseHunterMaterializer",
        lambda: Materializer(),
    )

    result = worker.run_hunter_enrichment_cycle(
        limit=1,
        write_authorized=True,
        state_path=tmp_path / "state.json",
    )

    assert result["processed"] == 1
    assert result["failed"] == 0
    assert result["outbound_actions"] is False
    assert result["payment_actions"] is False
    assert result["revenue_actions"] is False


def test_recent_entity_is_skipped_for_cooldown(monkeypatch, tmp_path):
    from datetime import datetime, timezone
    import json

    state_path = tmp_path / "state.json"
    now = datetime(2026, 9, 20, 15, 0, tzinfo=timezone.utc)
    state_path.write_text(json.dumps({
        "e1": {
            "last_attempt_at": "2026-09-20T14:30:00+00:00",
            "status": "processed",
        }
    }))

    monkeypatch.setattr(
        worker,
        "build_priority_queue",
        lambda limit: {
            "items": [
                {
                    "entity_id": "e1",
                    "contact_ready": False,
                    "depth": "shallow",
                    "priority_score": 70,
                },
                {
                    "entity_id": "e2",
                    "contact_ready": False,
                    "depth": "shallow",
                    "priority_score": 60,
                },
            ]
        },
    )
    monkeypatch.setattr(
        worker,
        "_entity",
        lambda eid: {
            "id": eid,
            "canonical_name": eid,
            "canonical_website": f"https://{eid}.test",
        },
    )
    monkeypatch.setattr(
        worker,
        "analyze_domain",
        lambda *args, **kwargs: FakeReport(),
    )
    monkeypatch.setattr(
        worker,
        "build_evidence_plan",
        lambda report, entity_id: object(),
    )

    class Materializer:
        def materialize(self, plan, *, write_authorized):
            return {"ok": True, "write_authorized": write_authorized}

    monkeypatch.setattr(
        worker,
        "SupabaseHunterMaterializer",
        lambda: Materializer(),
    )

    result = worker.run_hunter_enrichment_cycle(
        limit=1,
        write_authorized=True,
        state_path=state_path,
        cooldown_hours=6,
        now=now,
    )

    assert result["processed"] == 1
    assert result["skipped_cooldown"] == 1
    assert result["results"][0]["entity_id"] == "e2"
