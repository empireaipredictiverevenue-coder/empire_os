from empire_os.hunter.outcome_worker import HunterOutcomeWorker


def test_observe_mode_never_writes():
    calls = []

    def request(method, path, payload=None, *, prefer=None):
        calls.append((method, path, payload, prefer))
        if path.startswith("/rest/v1/outbound_events"):
            return [{
                "id": "event-1",
                "intent_id": "intent-1",
                "event_type": "delivered",
                "provider_message_id": "msg-1",
                "payload": {},
                "occurred_at": "2026-09-20T14:00:00Z",
            }]
        if path.startswith("/rest/v1/outbound_intents"):
            return [{
                "id": "intent-1",
                "entity_id": "entity-1",
                "normalized_recipient": "jane@acme.com",
                "channel": "email",
                "status": "delivered",
            }]
        if path.startswith("/rest/v1/intelligence_contact_points"):
            return [{
                "id": "contact-1",
                "person_id": "person-1",
                "entity_id": "entity-1",
                "verification_state": "observed",
                "confidence": 0.62,
                "verified_at": None,
                "last_seen_at": "2026-09-19T10:00:00Z",
            }]
        raise AssertionError(path)

    result = HunterOutcomeWorker(request_factory=request).run(
        write_authorized=False
    )

    assert result["contacts_matched"] == 1
    assert result["contacts_updated"] == 0
    assert result["outcomes_written"] == 0
    assert not any(call[0] in {"PATCH", "POST"} for call in calls)


def test_verified_bounce_marks_existing_contact_invalid_and_records_outcome():
    calls = []

    def request(method, path, payload=None, *, prefer=None):
        calls.append((method, path, payload, prefer))
        if method == "GET" and path.startswith("/rest/v1/outbound_events"):
            return [{
                "id": "event-1",
                "intent_id": "intent-1",
                "event_type": "failed",
                "provider_message_id": "msg-1",
                "payload": {"provider_event": "bounced"},
                "occurred_at": "2026-09-20T14:00:00Z",
            }]
        if method == "GET" and path.startswith("/rest/v1/outbound_intents"):
            return [{
                "id": "intent-1",
                "entity_id": "entity-1",
                "normalized_recipient": "jane@acme.com",
                "channel": "email",
                "status": "failed",
            }]
        if method == "GET" and path.startswith("/rest/v1/intelligence_contact_points"):
            return [{
                "id": "contact-1",
                "person_id": "person-1",
                "entity_id": "entity-1",
                "verification_state": "observed",
                "confidence": 0.62,
                "verified_at": None,
                "last_seen_at": "2026-09-19T10:00:00Z",
            }]
        if method == "GET" and path.startswith("/rest/v1/intelligence_outcomes"):
            return []
        if method == "PATCH":
            return [{"id": "contact-1", **payload}]
        if method == "POST" and path == "/rest/v1/intelligence_outcomes":
            return [{"id": "outcome-1", **payload}]
        raise AssertionError((method, path))

    result = HunterOutcomeWorker(request_factory=request).run(
        write_authorized=True
    )

    assert result["contacts_updated"] == 1
    assert result["outcomes_written"] == 1
    patch = next(call for call in calls if call[0] == "PATCH")
    assert patch[2]["verification_state"] == "invalid"
    assert patch[2]["confidence"] == 0.05
    outcome = next(
        call for call in calls
        if call[0] == "POST"
        and call[1] == "/rest/v1/intelligence_outcomes"
    )
    assert outcome[2]["outcome_type"] == "contact_bounced"
    assert outcome[2]["outcome_value"]["commercial_revenue"] is False


def test_unmatched_verified_bounce_records_learning_without_fake_contact():
    calls = []

    def request(method, path, payload=None, *, prefer=None):
        calls.append((method, path, payload, prefer))
        if method == "GET" and path.startswith("/rest/v1/outbound_events"):
            return [{
                "id": "event-bounce",
                "intent_id": "intent-1",
                "event_type": "bounced",
                "provider_message_id": "msg-1",
                "payload": {"provider": "resend"},
                "occurred_at": "2026-09-20T14:00:00Z",
            }]
        if method == "GET" and path.startswith("/rest/v1/outbound_intents"):
            return [{
                "id": "intent-1",
                "prospect_id": "prospect-1",
                "entity_id": None,
                "normalized_recipient": "jane@acme.com",
                "channel": "email",
                "status": "failed",
            }]
        if method == "GET" and path.startswith("/rest/v1/intelligence_contact_points"):
            return []
        if method == "GET" and path.startswith("/rest/v1/intelligence_outcomes"):
            return []
        if method == "POST" and path == "/rest/v1/intelligence_outcomes":
            return [{"id": "outcome-1", **payload}]
        raise AssertionError((method, path))

    result = HunterOutcomeWorker(request_factory=request).run(
        write_authorized=True
    )

    assert result["contacts_matched"] == 0
    assert result["contacts_updated"] == 0
    assert result["outcomes_written"] == 1
    assert not any(call[0] == "PATCH" for call in calls)
    outcome = next(
        call for call in calls
        if call[0] == "POST"
        and call[1] == "/rest/v1/intelligence_outcomes"
    )
    assert outcome[2]["entity_id"] is None
    assert outcome[2]["person_id"] is None
    assert outcome[2]["outcome_type"] == "contact_bounced"
    assert outcome[2]["outcome_value"]["prospect_id"] == "prospect-1"
    assert outcome[2]["outcome_value"]["contact_graph_match"] is False
