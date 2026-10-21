"""The private Quora overlay must not replace the concurrently deployed Research owner."""
from scripts import review_quora_research_compatible_release_20261021 as review


def test_compatible_candidate_keeps_original_research_bytes():
    packet = review.verify_staged_release()
    assert packet["preserved_research_sources"] is True
    assert set(packet["three_additive_source_paths"]) == review.EXPECTED
    assert len(packet["manifest_sha256"]) == 64


def test_research_owner_root_and_public_boundary_are_release_gates(monkeypatch):
    monkeypatch.setattr(review, "verify_staged_release", lambda: {
        "manifest_sha256": "a" * 64,
        "build_id": "candidate-build",
        "preserved_research_sources": True,
    })
    live = {
        "ActiveState": "active",
        "WorkingDirectory": str(review.BASE_RELEASE / "web"),
        "Environment": "EMPIRE_PRIVATE_FOUNDER_INGRESS_REVIEWED=1",
    }
    monkeypatch.setattr(review, "_unit_property", lambda key: live[key])
    monkeypatch.setattr(review, "_get_json", lambda _: {
        "schema_version": "empire.search_intelligence.quora_research.v1",
        "topic_count": 56,
        "mode": "OBSERVE",
        "execution_authority": "NONE",
        "verified_quora_questions": 0,
    })
    monkeypatch.setattr(review, "_public_code", lambda _: 404)
    safe = review.review()
    assert safe["status"] == "RESEARCH_COMPATIBLE_CANDIDATE_STAGED_APPROVAL_REQUIRED"
    assert safe["founder_restart_performed"] is False
    assert safe["founder_app_identity_independently_verified"] is False
    live["WorkingDirectory"] = "/opt/newer-concurrent-release"
    assert review.review()["status"] == "HELD_RELEASE_OR_PRIVATE_BOUNDARY_CHANGED"
    live["WorkingDirectory"] = str(review.BASE_RELEASE / "web")
    monkeypatch.setattr(review, "_public_code", lambda _: 200)
    assert review.review()["status"] == "HELD_RELEASE_OR_PRIVATE_BOUNDARY_CHANGED"
