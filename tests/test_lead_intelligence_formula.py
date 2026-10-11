from empire_os.lead_intelligence_formula import score


def test_weighted_opportunity_formula():
    x=score({'icp_fit':100,'demand':80,'potential_value':60,
             'freshness':40,'transaction_readiness':20}, {})
    assert x['opportunity_score']==66.0
    assert x['evidence_confidence_score']==0


def test_missing_components_do_not_create_score():
    x=score({'icp_fit':100}, {})
    assert x['opportunity_score'] is None
    assert len(x['missing_components'])==4


def test_invalid_or_fabricated_proofs_fail_closed():
    components={k:100 for k in ('icp_fit','demand','potential_value','freshness','transaction_readiness')}
    x=score(components,{'commercial_terms_verified':'true','compliance_verified':1})
    assert x['evidence_confidence_score']==0
    assert x['commercial_activation_authorized'] is False


def test_all_verified_proofs_do_not_authorize_outbound():
    from empire_os.lead_intelligence_formula import PROOF_WEIGHTS
    x=score({}, {k:True for k in PROOF_WEIGHTS})
    assert x['evidence_confidence_score']==100
    assert x['commercial_activation_authorized'] is False
