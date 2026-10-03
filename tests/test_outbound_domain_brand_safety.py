from empire_os.outbound_domain_brand_safety import evaluate_domain_brand_safety


def base(**overrides):
    value = {
        "domain": "empire-revenue.co.uk",
        "purpose": "prospecting",
        "primary_brand_domain": "empire-ai.co.uk",
        "empire_owned": True,
        "registrar_controlled": True,
        "third_party_impersonation": False,
        "deceptive_typo_variant": False,
        "brand_disclosure_present": True,
        "relationship_to_empire_disclosed": True,
        "idn_reviewed": False,
    }
    value.update(overrides)
    return value


def test_owned_disclosed_outreach_domain_is_safe():
    result = evaluate_domain_brand_safety(base())
    assert result["posture"] == "SAFE"
    assert result["mutation_authorized"] is False


def test_unowned_domain_is_hold():
    result = evaluate_domain_brand_safety(base(empire_owned=False))
    assert result["posture"] == "HOLD"
    assert "domain_not_empire_owned" in result["hard_holds"]


def test_typo_variant_is_forbidden():
    result = evaluate_domain_brand_safety(base(deceptive_typo_variant=True))
    assert result["posture"] == "HOLD"
    assert "deceptive_typo_variant_forbidden" in result["hard_holds"]


def test_third_party_impersonation_is_forbidden():
    result = evaluate_domain_brand_safety(base(third_party_impersonation=True))
    assert result["posture"] == "HOLD"
    assert "third_party_impersonation_forbidden" in result["hard_holds"]


def test_unreviewed_idn_is_hold():
    result = evaluate_domain_brand_safety(
        base(domain="xn--empire-9za.example")
    )
    assert result["posture"] == "HOLD"
    assert "idn_domain_requires_manual_review" in result["hard_holds"]


def test_missing_empire_relationship_disclosure_requires_remediation():
    result = evaluate_domain_brand_safety(
        base(relationship_to_empire_disclosed=False)
    )
    assert result["posture"] == "REMEDIATE"
    assert (
        "outreach_domain_empire_relationship_not_disclosed"
        in result["warnings"]
    )


def test_primary_brand_domain_warns_reputation_exposure():
    result = evaluate_domain_brand_safety(
        base(
            domain="empire-ai.co.uk",
            primary_brand_domain="empire-ai.co.uk",
        )
    )
    assert result["posture"] == "REMEDIATE"
    assert "primary_brand_domain_reputation_exposure" in result["warnings"]
