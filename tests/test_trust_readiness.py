from empire_os.trust_readiness import (
    TrustEvidence,
    assess_trust_readiness,
    build_public_trust_manifest,
)


def test_unknowns_do_not_inflate_trust():
    result = assess_trust_readiness({
        "identity_transparency": TrustEvidence(
            "identity_transparency",
            "verified",
            ("evidence:company_identity",),
        ),
    })

    assert result["internal_score"] == 15
    assert result["evidence_coverage"] == 0.15
    assert result["public_score_allowed"] is False
    assert result["public_trust_center_ready"] is False


def test_verified_without_evidence_is_blocked():
    result = assess_trust_readiness({
        "identity_transparency": TrustEvidence(
            "identity_transparency",
            "verified",
        ),
    })

    assert "identity_transparency:verified_without_evidence" in result["blockers"]


def test_public_manifest_exposes_only_verified_evidence():
    assessment = assess_trust_readiness({
        "identity_transparency": TrustEvidence(
            "identity_transparency",
            "verified",
            ("evidence:identity",),
        ),
        "security_privacy": TrustEvidence(
            "security_privacy",
            "failed",
            ("evidence:security-review",),
        ),
    })

    manifest = build_public_trust_manifest(assessment)

    assert manifest["self_awarded_score"] is None
    assert [row["key"] for row in manifest["verified_claims"]] == [
        "identity_transparency"
    ]
    assert manifest["fabricated_social_proof"] is False


def test_partial_evidence_counts_half_weight():
    result = assess_trust_readiness({
        "domain_email_authentication": TrustEvidence(
            "domain_email_authentication",
            "partial",
            ("dns:spf", "dns:dmarc-monitoring"),
        ),
    })

    assert result["internal_score"] == 5.0
    assert result["evidence_coverage"] == 0.10
