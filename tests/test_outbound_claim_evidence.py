from datetime import datetime, timezone

from empire_os.outbound_claim_evidence import evaluate_claim_evidence


NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)


def test_verified_observed_claim_passes():
    result = evaluate_claim_evidence(
        [{
            "text": "Acme has 114 public reviews",
            "kind": "observed_fact",
            "evidence_ref": "proof:1",
        }],
        {
            "proof:1": {
                "verified": True,
                "source_kind": "official_site_current",
                "canonical": False,
                "expires_at": "2026-10-04T12:00:00+00:00",
            }
        },
        now=NOW,
    )
    assert result["decision"] == "VERIFIED"
    assert result["claims"][0]["status"] == "VERIFIED"


def test_claim_without_evidence_ref_is_hold():
    result = evaluate_claim_evidence(
        [{"text": "Acme is expanding", "kind": "observed_fact"}],
        {},
        now=NOW,
    )
    assert result["decision"] == "HOLD"
    assert "claim_evidence_ref_missing" in result["hard_holds"]


def test_expired_claim_evidence_is_hold():
    result = evaluate_claim_evidence(
        [{
            "text": "Acme is hiring",
            "kind": "observed_fact",
            "evidence_ref": "proof:old",
        }],
        {
            "proof:old": {
                "verified": True,
                "source_kind": "public_record",
                "expires_at": "2026-10-02T12:00:00+00:00",
            }
        },
        now=NOW,
    )
    assert result["decision"] == "HOLD"
    assert "claim_evidence_expired" in result["hard_holds"]


def test_sensitive_pricing_claim_requires_canonical_evidence():
    result = evaluate_claim_evidence(
        [{
            "text": "The plan is £5,000 per month",
            "kind": "pricing",
            "evidence_ref": "price:1",
        }],
        {
            "price:1": {
                "verified": True,
                "source_kind": "official_site_current",
                "canonical": False,
            }
        },
        now=NOW,
    )
    assert result["decision"] == "HOLD"
    assert "sensitive_claim_requires_canonical_evidence" in result["hard_holds"]


def test_sensitive_claim_passes_with_canonical_commercial_evidence():
    result = evaluate_claim_evidence(
        [{
            "text": "The approved plan is £5,000 per month",
            "kind": "pricing",
            "evidence_ref": "price:canonical",
        }],
        {
            "price:canonical": {
                "verified": True,
                "source_kind": "canonical_commercial_evidence",
                "canonical": True,
            }
        },
        now=NOW,
    )
    assert result["decision"] == "VERIFIED"


def test_unverified_evidence_escalates_not_silently_passes():
    result = evaluate_claim_evidence(
        [{
            "text": "Acme has active demand",
            "kind": "observed_fact",
            "evidence_ref": "signal:1",
        }],
        {
            "signal:1": {
                "verified": False,
                "source_kind": "public_record",
            }
        },
        now=NOW,
    )
    assert result["decision"] == "ESCALATE"
    assert "claim_evidence_unverified" in result["evidence_holds"]
