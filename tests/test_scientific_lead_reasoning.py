import pytest
from empire_os.scientific_lead_reasoning import reason


def test_correlated_sources_count_once():
    rows=[{'source_id':'https://example.com','source_type':'public_first_party_claim','direction':'support'}]*3
    x=reason(hypothesis='demand exists',observations=rows)
    assert x['weighted_support']==0.3
    assert x['rejection_reasons']==['correlated_duplicate','correlated_duplicate']


def test_contradictory_evidence_reduces_indicator():
    rows=[{'source_id':'a','source_type':'verified_first_party','direction':'support'},
          {'source_id':'b','source_type':'authenticated_commercial','direction':'contradict'}]
    x=reason(hypothesis='demand exists',observations=rows)
    assert x['research_priority_indicator']==-0.15


def test_no_invented_probability_even_with_prior():
    x=reason(hypothesis='demand exists',observations=[],prior=0.5)
    assert x['posterior_probability'] is None
    assert x['commercial_activation_authorized'] is False


def test_invalid_prior_rejected():
    with pytest.raises(ValueError):reason(hypothesis='demand exists',observations=[],prior=1)
