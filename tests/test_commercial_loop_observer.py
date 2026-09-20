import json
from datetime import datetime, timezone

from empire_os.commercial_loop_observer import (
    CommercialLoopObservation,
    assess_commercial_loop,
    fetch_canonical_commercial_observations,
    observations_from_cycle,
    read_latest_acquisition_accepted,
    write_commercial_loop_snapshot,
)


NOW = datetime(2026, 9, 20, 13, 0, tzinfo=timezone.utc)


def test_first_false_stage_is_highest_priority_blocker():
    status = assess_commercial_loop(
        {
            "real_acquisition": CommercialLoopObservation(
                "real_acquisition", True
            ),
            "qualification_v2": CommercialLoopObservation(
                "qualification_v2", True
            ),
            "omega_projection": CommercialLoopObservation(
                "omega_projection", True
            ),
            "buyer_candidate_approved": CommercialLoopObservation(
                "buyer_candidate_approved", True
            ),
            "outbound_authorized": CommercialLoopObservation(
                "outbound_authorized", True
            ),
            "outbound_sent": CommercialLoopObservation(
                "outbound_sent", False
            ),
        }
    )

    assert status.highest_priority_blocker == "outbound_sent"
    assert status.blocker_state == "blocked"
    assert status.loop_complete is False
    assert status.outbound_execution is False
    assert status.payment_execution is False
    assert status.revenue_mutation is False


def test_unknown_downstream_stage_stays_unknown():
    status = assess_commercial_loop(
        {
            "real_acquisition": CommercialLoopObservation(
                "real_acquisition", True
            ),
            "qualification_v2": CommercialLoopObservation(
                "qualification_v2", True
            ),
            "omega_projection": CommercialLoopObservation(
                "omega_projection", True
            ),
        }
    )

    assert status.highest_priority_blocker == "buyer_candidate_approved"
    assert status.blocker_state == "unknown"


def test_cycle_observations_preserve_buyer_terms_and_capacity_truth():
    observations = observations_from_cycle(
        acquisition_accepted=10,
        qualification={"qualified": 10},
        omega={"scores_written": 2},
        buyer_readiness={
            "buyers_with_verified_terms": 0,
            "activated_buyers_with_capacity": 0,
        },
    )

    assert observations["real_acquisition"].observed is True
    assert observations["qualification_v2"].observed is True
    assert observations["omega_projection"].observed is True
    assert observations["commercial_terms"].observed is False
    assert observations["verified_buyer_capacity"].observed is False


def test_canonical_reader_surfaces_authorized_but_unsent_outbound():
    def reader(path, params):
        if path.endswith("buyer_candidate_reviews"):
            return [
                {
                    "id": "review-1",
                    "status": "approved",
                    "reviewed_at": "2026-09-20T12:00:00Z",
                    "evidence": {
                            "outreach_ready": True,
                            "verified_contacts": [{
                                "email": "buyer@example.com",
                                "is_valid": True,
                                "bound_to_decision_maker": True,
                            }],
                        },
                }
            ]
        if path.endswith("outbound_intents"):
            return [
                {
                    "id": "intent-1",
                    "status": "approved",
                    "approved_at": "2026-09-20T12:05:00Z",
                    "expires_at": "2026-09-20T22:00:00Z",
                }
            ]
        return []

    canonical = fetch_canonical_commercial_observations(
        reader,
        now=NOW,
    )
    observations = observations_from_cycle(
        acquisition_accepted=10,
        qualification={"qualified": 5},
        omega={"candidates_seen": 2},
        buyer_readiness={
            "buyers_with_verified_terms": 0,
            "activated_buyers_with_capacity": 0,
        },
        canonical_observations=canonical,
    )
    status = assess_commercial_loop(observations)

    assert canonical["buyer_candidate_approved"].observed is True
    assert canonical["outbound_authorized"].observed is True
    assert canonical["outbound_sent"].observed is False
    assert status.highest_priority_blocker == "outbound_sent"
    assert status.blocker_state == "blocked"


def test_expired_approved_intent_is_not_current_authority():
    def reader(path, params):
        if path.endswith("buyer_candidate_reviews"):
            return [
                {
                    "id": "review-1",
                    "status": "approved",
                    "reviewed_at": "2026-09-20T11:00:00Z",
                    "evidence": {
                            "outreach_ready": True,
                            "verified_contacts": [{
                                "email": "buyer@example.com",
                                "is_valid": True,
                                "bound_to_decision_maker": True,
                            }],
                        },
                }
            ]
        if path.endswith("outbound_intents"):
            return [
                {
                    "id": "intent-1",
                    "status": "approved",
                    "approved_at": "2026-09-20T10:00:00Z",
                    "expires_at": "2026-09-20T12:00:00Z",
                }
            ]
        return []

    canonical = fetch_canonical_commercial_observations(
        reader,
        now=NOW,
    )

    assert canonical["buyer_candidate_approved"].observed is True
    assert canonical["outbound_authorized"].observed is False


def test_acquisition_parser_reads_real_accepted_count(tmp_path):
    path = tmp_path / "latest.json"
    path.write_text(
        json.dumps(
            {
                "stdout_tail": (
                    '{"msg":"source_run_done","accepted": 10,"errors": 0}\n'
                    '{"msg":"crawler_run_done","accepted": 10,"errors": 0}'
                )
            }
        )
    )

    assert read_latest_acquisition_accepted(path) == 10


def test_snapshot_is_local_observe_artifact(tmp_path):
    status = assess_commercial_loop(
        {
            "real_acquisition": CommercialLoopObservation(
                "real_acquisition", False
            )
        }
    )
    target = write_commercial_loop_snapshot(
        status,
        tmp_path / "commercial" / "latest.json",
    )

    saved = json.loads(target.read_text())
    assert saved["mode"] == "OBSERVE"
    assert saved["execution_authority"] == "none"
    assert saved["highest_priority_blocker"] == "real_acquisition"
    assert saved["allocation_execution"] is False


def test_existing_omega_proves_prior_v2_qualification_when_cycle_writes_zero():
    observations = observations_from_cycle(
        acquisition_accepted=10,
        qualification={"qualified": 0},
        omega={"candidates_seen": 5},
        buyer_readiness={
            "buyers_with_verified_terms": 0,
            "activated_buyers_with_capacity": 0,
        },
    )

    assert observations["qualification_v2"].observed is True


def test_failed_historical_send_does_not_count_as_current_outbound():
    def reader(path, params):
        if path.endswith("buyer_candidate_reviews"):
            return [{
                "id": "review-1",
                "status": "approved",
                "reviewed_at": "2026-09-20T12:00:00Z",
                "evidence": {
                            "outreach_ready": True,
                            "verified_contacts": [{
                                "email": "buyer@example.com",
                                "is_valid": True,
                                "bound_to_decision_maker": True,
                            }],
                        },
            }]
        if path.endswith("outbound_intents"):
            return []
        if path.endswith("outbound_replies"):
            return []
        return []

    canonical = fetch_canonical_commercial_observations(
        reader,
        now=NOW,
    )

    assert canonical["buyer_candidate_approved"].observed is True
    assert canonical["outbound_authorized"].observed is False
    assert canonical["outbound_sent"].observed is False


def test_bounced_hunter_contact_invalidates_approved_review():
    def reader(path, params):
        if path.endswith("buyer_candidate_reviews"):
            return [{
                "id": "review-1",
                "status": "approved",
                "reviewed_at": "2026-09-20T12:00:00Z",
                "evidence": {
                    "outreach_ready": True,
                    "verified_contacts": [{
                        "email": "dead@example.com",
                        "is_valid": True,
                        "bound_to_decision_maker": True,
                    }],
                },
            }]
        if path.endswith("intelligence_outcomes"):
            return [{
                "id": "outcome-1",
                "outcome_type": "contact_bounced",
                "outcome_value": {"email": "dead@example.com"},
                "occurred_at": "2026-09-20T12:10:00Z",
            }]
        return []

    canonical = fetch_canonical_commercial_observations(
        reader,
        now=NOW,
    )

    assert canonical["buyer_candidate_approved"].observed is False


def test_unsubscribe_reply_is_not_a_buyer_conversation():
    def reader(path, params):
        if path.endswith("outbound_replies"):
            return [{
                "id": "reply-unsub",
                "classification": "unsubscribe",
                "received_at": "2026-09-20T19:19:30Z",
            }]
        return []

    canonical = fetch_canonical_commercial_observations(
        reader,
        now=NOW,
    )

    conversation = canonical["buyer_conversation"]
    assert conversation.observed is False
    assert "0 commercial buyer reply" in conversation.detail
    assert "1 total reply" in conversation.detail
