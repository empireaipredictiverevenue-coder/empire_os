from empire_os.lead_qualification_tiers import qualify, PROOFS


def test_missing_evidence_fail_closed():
    assert qualify(None)['qualification_tier']=='BASIC'
    assert qualify({'company_identity_verified':'true'})['qualification_tier']=='BASIC'


def test_prequalified_requires_all_proofs():
    evidence={key:True for key in PROOFS['PRE_QUALIFIED']}
    assert qualify(evidence)['qualification_tier']=='PRE_QUALIFIED'
    evidence.pop('demand_verified')
    assert qualify(evidence)['qualification_tier']=='BASIC'


def test_premium_requires_commercial_evidence():
    evidence={key:True for key in PROOFS['PREMIUM']}
    assert qualify(evidence)['qualification_tier']=='PREMIUM'
    evidence['compliance_verified']=False
    assert qualify(evidence)['qualification_tier']=='PRE_QUALIFIED'


def test_executive_requires_decision_maker_and_value():
    evidence={key:True for key in PROOFS['EXECUTIVE']}
    assert qualify(evidence)['qualification_tier']=='EXECUTIVE'
    evidence.pop('decision_maker_verified')
    assert qualify(evidence)['qualification_tier']=='PREMIUM'


def test_tier_never_grants_outbound_authority():
    evidence={key:True for key in PROOFS['EXECUTIVE']}
    assert qualify(evidence)['commercial_activation_authorized'] is False
