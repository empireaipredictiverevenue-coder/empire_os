from empire_os.offer_contact_holding_bridge import build_holding_candidates


def _recovery(domain="acme.test", email="jane@acme.test"):
    return {
        "generated_at": "2026-10-02T20:00:00+00:00",
        "items": [{
            "company": "Acme",
            "domain": domain,
            "ready_product_codes": ["managed_service"],
            "person_bound_candidates": [{
                "person_name": "Jane Smith",
                "person_title": "CEO",
                "email": email,
                "source_url": f"https://{domain}/team/jane",
                "source": "first_party_site",
                "person_explicitly_named": True,
                "email_directly_bound_to_person": True,
            }],
        }],
    }


def _mx(email="jane@acme.test"):
    return [{
        "email": email,
        "is_valid": True,
        "has_mx": True,
        "is_role_address": False,
        "is_disposable": False,
        "confidence": 0.75,
        "smtp_status": "not_run",
    }]


def test_same_domain_mx_valid_contact_builds_holding_candidate():
    result = build_holding_candidates(_recovery(), mx_rows=_mx())
    assert result["candidate_count"] == 1
    assert result["verified_contact_count"] == 1
    row = result["candidates"][0]
    assert row["direct_buyer_score"] == 0
    assert row["provenance"]["buy_signal_score_state"] == "UNKNOWN"
    assert row["site_evidence"]["first_party_people"][0]["name"] == "Jane Smith"
    assert result["canonical_promotion_performed"] is False
    assert result["outbound_authorized"] is False


def test_cross_domain_email_is_blocked():
    result = build_holding_candidates(
        _recovery(domain="growth.test", email="jane@parent.test"),
        mx_rows=_mx("jane@parent.test"),
    )
    assert result["candidate_count"] == 0
    assert result["blocked"][0]["reasons"] == ["email_domain_mismatch"]


def test_suppressed_email_is_blocked():
    result = build_holding_candidates(
        _recovery(),
        mx_rows=_mx(),
        suppressed_emails={"jane@acme.test"},
    )
    assert result["candidate_count"] == 0
    assert "recipient_suppressed" in result["blocked"][0]["reasons"]


def test_invalid_mx_is_blocked():
    mx = _mx()
    mx[0]["has_mx"] = False
    mx[0]["is_valid"] = False
    result = build_holding_candidates(_recovery(), mx_rows=mx)
    assert result["candidate_count"] == 0
    assert "mx_verification_failed" in result["blocked"][0]["reasons"]
