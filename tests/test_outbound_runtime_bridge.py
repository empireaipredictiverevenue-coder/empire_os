import inspect

import empire_os.autonomous_commercial_progression_runtime as runtime
from empire_os.outbound_runtime_bridge import outbound_advisory_from_progression


def receipt(*, evidence=()):
    return {
        "schema_version": "empire.autonomous-commercial-progression.v1",
        "action": "prepare_buyer_review",
        "selected_action": "prepare_buyer_review",
        "prospect_id": "p1",
        "company_name": "Intercept Roofing & Construction",
        "mode": "AUTO_INTERNAL",
        "status": "ADVANCED_REVIEW_PROPOSED",
        "execution_authority": "none",
        "internal_mutation_authorized": False,
        "internal_mutation_performed": True,
        "external_execution_authorized": False,
        "external_execution_performed": False,
        "outbound_sent": False,
        "call_placed": False,
        "payment_action": False,
        "binding_terms_action": False,
        "result": {
            "status": "ADVANCED_REVIEW_PROPOSED",
            "outbound_evidence": list(evidence),
            "materializer": {
                "outcomes": [
                    {
                        "prospect_id": "p1",
                        "business_name": "Intercept Roofing & Construction",
                        "status": "proposed",
                        "review_ready": True,
                        "outreach_ready": True,
                        "decision_name": "Trace Finch",
                        "decision_title": "Owner",
                        "preferred_email": "info@interceptroofing.com",
                        "contact_route": "company_routed",
                        "person_bound": False,
                    }
                ]
            },
        },
    }


def verified_evidence():
    return {
        "evidence_ref": "first_party:commercial-roofing",
        "summary": (
            "Intercept Roofing & Construction publishes a commercial roofing "
            "service page."
        ),
        "verified": True,
        "fresh": True,
        "account_bound": True,
    }


def test_bridge_ignores_non_review_actions():
    assert outbound_advisory_from_progression({
        "action": "research_more",
        "result": {},
    }) is None


def test_precanonical_receipt_has_explicit_null_advisory():
    """Buyer Scout admission is not a canonical review-ready ACP event."""
    payload = runtime._normalise_precanonical_receipt(
        {"status": "ADVANCED", "canonical_prospect_id": "test-prospect"},
        mode="AUTO_INTERNAL",
        execution_authority=None,
    )
    assert "outbound_advisory" in payload
    assert payload["outbound_advisory"] is None
    assert payload["outbound_sent"] is False
    assert payload["external_execution_performed"] is False


def test_review_without_explicit_copy_evidence_fails_closed_to_research():
    advisory = outbound_advisory_from_progression(receipt())
    assert advisory is not None
    assert advisory["advisory_only"] is True
    assert advisory["execution_authority"] == "none"
    assert advisory["send_enabled"] is False
    assert advisory["explicit_outbound_evidence_count"] == 0
    assert advisory["plan"]["action_type"] == "RESEARCH"
    assert advisory["plan"]["execution_authority"] == "none"


def test_review_with_verified_copy_evidence_enters_rapport_first():
    advisory = outbound_advisory_from_progression(
        receipt(evidence=[verified_evidence()])
    )
    assert advisory is not None
    assert advisory["explicit_outbound_evidence_count"] == 1
    assert advisory["plan"]["relationship_stage"] == "COLD_VERIFIED"
    assert advisory["plan"]["action_type"] == "DRAFT_RAPPORT_TOUCH"
    assert advisory["plan"]["cta_allowed"] is False
    assert advisory["plan"]["price_allowed"] is False
    assert advisory["plan"]["execution_authority"] == "none"
    assert advisory["plan"]["person_bound"] is False


def test_bridge_source_has_no_io_sender_or_database_dependencies():
    import empire_os.outbound_runtime_bridge as bridge

    source = inspect.getsource(bridge)
    for forbidden in (
        "requests.",
        "psycopg",
        "subprocess.",
        "smtplib",
        "socket.",
        "send_message(",
        "request_json(",
    ):
        assert forbidden not in source


class FakeReceipt:
    def as_dict(self):
        return receipt(evidence=[verified_evidence()])


def test_acp_cycle_attaches_outbound_advisory_without_changing_authority(monkeypatch):
    monkeypatch.setattr(runtime, "filter_cooldowns", lambda snapshot: snapshot)

    def fake_build_progression_plan(
        snapshot,
        *,
        mode,
        execution_authority,
    ):
        assert snapshot == {}
        assert mode == "AUTO_INTERNAL"
        assert execution_authority is None
        return {
            "selected_action": "prepare_buyer_review",
            "safe_internal_action_available": True,
        }

    monkeypatch.setattr(
        runtime,
        "build_progression_plan",
        fake_build_progression_plan,
    )
    monkeypatch.setattr(runtime, "write_progression_plan", lambda _plan: None)
    monkeypatch.setattr(
        runtime,
        "execute_one_internal_progression",
        lambda *_args, **_kwargs: FakeReceipt(),
    )
    monkeypatch.setattr(runtime, "build_handlers", lambda **_kwargs: {})
    monkeypatch.setattr(runtime, "_write_json", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(runtime, "_append_attempt", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(runtime, "refresh_strategy_memory", lambda: {})

    output = runtime.run_internal_cycle({}, execute=True)

    advisory = output["receipt"]["outbound_advisory"]
    assert advisory["plan"]["action_type"] == "DRAFT_RAPPORT_TOUCH"
    assert advisory["execution_authority"] == "none"
    assert advisory["send_enabled"] is False
    assert output["receipt"]["result"]["status"] == "ADVANCED_REVIEW_PROPOSED"


def test_acp_bridge_exception_fails_closed_without_corrupting_receipt(monkeypatch):
    monkeypatch.setattr(runtime, "filter_cooldowns", lambda snapshot: snapshot)
    monkeypatch.setattr(
        runtime,
        "build_progression_plan",
        lambda *_args, **_kwargs: {
            "selected_action": "prepare_buyer_review",
            "safe_internal_action_available": True,
        },
    )
    monkeypatch.setattr(runtime, "write_progression_plan", lambda _plan: None)
    monkeypatch.setattr(runtime, "build_handlers", lambda **_kwargs: {})
    monkeypatch.setattr(
        runtime,
        "execute_one_internal_progression",
        lambda *_args, **_kwargs: FakeReceipt(),
    )
    monkeypatch.setattr(runtime, "_write_json", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(runtime, "_append_attempt", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(runtime, "refresh_strategy_memory", lambda: {})

    def raise_bridge_error(_receipt):
        raise ValueError("isolated bridge failure")

    monkeypatch.setattr(runtime, "outbound_advisory_from_progression", raise_bridge_error)
    original = FakeReceipt().as_dict()
    actual = runtime.run_internal_cycle({}, execute=True)["receipt"]
    advisory = actual.pop("outbound_advisory")

    assert actual == original
    assert advisory["status"] == "BLOCKED"
    assert advisory["blocker"] == "outbound_advisory_bridge_error"
    assert advisory["error_type"] == "ValueError"
    assert advisory["advisory_only"] is True
    assert advisory["send_enabled"] is False
    assert advisory["outbound_sent"] is False
    assert advisory["execution_authority"] == "none"
