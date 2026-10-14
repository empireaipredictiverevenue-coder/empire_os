"""Existing founder API reads Workspace only when explicitly selected."""

from scripts import verify_owned_imap_mailbox as verifier


def test_workspace_read_probe_returns_only_aggregate_and_never_send(monkeypatch):
    def get(path, **kwargs):
        if path == "/v1/founder-mailbox/readiness":
            return {"provider": "google_workspace", "configured": True,
                    "execution_authority": "none", "canonical_identity_verified": False,
                    "suppression_evidence_complete": False}
        if path == "/v1/founder-mailbox/summary?limit=1":
            return {"provider": "google_workspace", "execution_authority": "none",
                    "canonical_buyer_conversation_verified": False,
                    "suppression_evidence_complete": False,
                    "summary": {"all": 2},
                    "thread_subjects": ["PRIVATE_NOT_ALLOWED_IN_REPORT"]}
        raise AssertionError(path)
    monkeypatch.setattr(verifier, "_local_json", get)
    result = verifier.service_readiness_report(probe=True, expected_provider="google_workspace")
    assert result["status"] == "READ_PROBE_SUCCESS"
    assert result["provider"] == "google_workspace"
    assert result["threads_observed_in_sample"] == 2
    assert result["canonical_buyer_conversation_verified"] is False
    assert result["outbound_sent"] is False
    assert "PRIVATE_NOT_ALLOWED_IN_REPORT" not in str(result)


def test_mailbox_provider_mismatch_fails_closed(monkeypatch):
    monkeypatch.setattr(verifier, "_local_json", lambda path, **kwargs: {
        "provider": "owned_imap", "configured": True,
        "execution_authority": "none", "canonical_identity_verified": False,
        "suppression_evidence_complete": False})
    result = verifier.service_readiness_report(probe=True, expected_provider="google_workspace")
    assert result["status"] == "SERVICE_CONTRACT_UNVERIFIED"
    assert result["outbound_sent"] is False
