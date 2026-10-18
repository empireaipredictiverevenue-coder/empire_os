"""Fail-closed evidence gates for a new campaign PORTFOLIO, not new agents."""
from __future__ import annotations
import copy
import json
import pytest
from scripts.review_search_growth_department_portfolio_20261016 import (MANIFEST,EvidenceHold,validate_and_prioritize)

@pytest.fixture
def manifest():
    return json.loads(MANIFEST.read_text())

def test_real_portfolio_is_research_only_with_eight_desks(manifest):
    result=validate_and_prioritize(manifest)
    assert result['desk_count']==8
    assert result['campaign_count']==9
    assert not result['production_write']
    assert not result['credentials_read']
    assert not result['external_requests']
    assert not result['outbound_or_publication_performed']
    assert not result['founder_gate_bypassed']
    assert result['budget_gbp']==0
    assert result['campaigns_approved_to_launch']==0
    assert all(x['status']=='RESEARCH_ONLY' for x in result['campaigns'])
    assert all(x['missing_evidence_gates'] for x in result['campaigns'])
    assert all(x['accepted_buyer_or_revenue_verified'] is False for x in result['campaigns'])

@pytest.mark.parametrize('path,value',[
    ('execution_authority','LIVE'),('mode','SEND'),('canonical_database','Supabase'),
    ('parent_department','parallel_growth'),('no_new_agent_server_timer_database_or_external_spend',False),
])
def test_no_duplicate_department_or_unguarded_execution(manifest,path,value):
    manifest[path]=value
    with pytest.raises(EvidenceHold):validate_and_prioritize(manifest)

def test_duplicate_campaign_id_halts(manifest):
    manifest['research_candidates'][1]['id']=manifest['research_candidates'][0]['id']
    with pytest.raises(EvidenceHold,match='duplicate'):validate_and_prioritize(manifest)

def test_auto_launch_cannot_be_smuggled_into_campaign(manifest):
    manifest['research_candidates'][0]['status']='LIVE_AND_PUBLISH_NOW'
    with pytest.raises(EvidenceHold,match='unreviewed_publication'):validate_and_prioritize(manifest)

def test_unverified_commercial_source_or_non_empire_url_halts(manifest):
    manifest['research_candidates'][0]['existing_url']='https://example.com/tracking'
    with pytest.raises(EvidenceHold,match='unapproved_public_url'):validate_and_prioritize(manifest)
    manifest['research_candidates'][0]['existing_url']='https://empire-ai.co.uk/commercial'
    manifest['research_candidates'][0]['data_sources']=['http://untrusted.example.com/']
    with pytest.raises(EvidenceHold,match='untrusted_source'):validate_and_prioritize(manifest)

def test_numeric_research_score_not_claim_of_rankings_or_leads(manifest):
    result=validate_and_prioritize(manifest)
    assert all(0<=v['research_priority_score_not_ranking_probability']<=100 for v in result['campaigns'])
    assert all(not v['search_position_verified'] and not v['demand_volume_verified'] for v in result['campaigns'])
    assert not result['rankings_or_organic_click_growth_claimed']
    scores=[x['research_priority_score_not_ranking_probability'] for x in result['campaigns']]
    assert scores==sorted(scores,reverse=True)

def test_missing_holds_refuse_launch_like_state(manifest):
    manifest['research_candidates'][0]['holds']=[]
    with pytest.raises(EvidenceHold):validate_and_prioritize(manifest)

def test_invalid_scores_and_biased_zero_probabilities_fail(manifest):
    manifest['research_candidates'][0]['fit']=10
    with pytest.raises(EvidenceHold,match='invalid_score'):validate_and_prioritize(manifest)

def test_specialist_owners_already_exist_in_canonical_marketing_agency(manifest):
    from empire_os.marketing_agency import ROLES
    owners={x['owner'] for x in manifest['specialist_desks']}
    assert owners.issubset(set(ROLES)),owners-set(ROLES)
    assert not any(x=='paid_acquisition_planner' for x in owners)
    assert manifest['parent_department']=='marketing_growth'
