"""Private Quora release guard tests, without service changes."""
from scripts import review_quora_founder_release_20261021 as review


def test_existing_candidate_manifest_matches_release_source():
    record = review.verify_manifest()
    assert record["active_agency_source_preserved"] is True
    assert set(record["scoped_source_changes"]) == review.EXPECTED
    assert len(record["candidate_manifest_sha256"]) == 64


def test_readiness_requires_correct_private_running_release(monkeypatch):
    monkeypatch.setattr(review, "verify_manifest", lambda: {
        "candidate_manifest_sha256": "a" * 64,
        "candidate_build_id": "staged-build",
        "scoped_source_changes": sorted(review.EXPECTED),
        "active_agency_source_preserved": True,
    })
    state = {
        "ActiveState": "active",
        "WorkingDirectory": str(review.BASE),
        "Environment": "EMPIRE_PRIVATE_FOUNDER_INGRESS_REVIEWED=1",
    }
    monkeypatch.setattr(review, "_unit_property", lambda key: state[key])
    monkeypatch.setattr(review, "_get_json", lambda url: {
        "schema_version": "empire.search_intelligence.quora_research.v1",
        "mode": "OBSERVE",
        "topic_count": 56,
        "verified_quora_questions": 0,
        "execution_authority": "NONE",
    })
    monkeypatch.setattr(review, "_public_code", lambda _: 404)
    result = review.review()
    assert result["status"] == "IMMUTABLE_PRIVATE_CANDIDATE_VERIFIED_RESTART_APPROVAL_REQUIRED"
    assert result["founder_service_restart_performed"] is False
    assert result["founder_app_level_identity_independently_verified"] is False
    assert result["execution_authority"] == "NONE"
    state["WorkingDirectory"] = "/srv/another-release"
    assert review.review()["status"] == "HELD_ACTIVE_RELEASE_OR_PRIVACY_GATE_DRIFT"
    state["WorkingDirectory"] = str(review.BASE)
    monkeypatch.setattr(review, "_public_code", lambda _: 200)
    assert review.review()["status"] == "HELD_ACTIVE_RELEASE_OR_PRIVACY_GATE_DRIFT"
