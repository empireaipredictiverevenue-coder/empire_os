"""Intent/research originality gate must not masquerade as Google rank scoring."""
from __future__ import annotations
import copy
import json
import pytest
from scripts.review_search_editorial_quality_20261016 import (BRIEF,DRAFT,review_article)

@pytest.fixture
def review_sample():
    return json.loads(BRIEF.read_text(encoding='utf-8')),DRAFT.read_text(encoding='utf-8')

def test_positive_full_research_article_has_natural_headings_and_owner_holds(review_sample):
    result=review_article(*review_sample)
    assert result['status']=='EDITORIAL_STRUCTURE_PASS_HUMAN_REVIEW_REQUIRED'
    assert result['main_keyword']=='AI readiness assessment UK'
    assert result['h2_count']>=4 and result['question_headings']>=3
    assert result['exact_main_keyword_repeated_in_h2_h3']==0
    assert result['visible_original_sources']>=2
    assert result['body_word_count']>=550
    assert not result['editorial_release_authorized']
    assert not result['production_writes']
    assert not result['external_requests']
    assert not result['outbound_sent']
    assert result['unverified_search_volume']

@pytest.mark.parametrize('key,value',[
    ('parent_department','parallel_new_department'),
    ('status','APPROVED'),('execution_authority','PUBLISH'),
    ('site_owner','random_agent'),('campaign_id','GROWTH-999')
])
def test_refuses_parallel_department_and_unapproved_scope(review_sample,key,value):
    brief,text=review_sample
    brief[key]=value
    with pytest.raises(ValueError):review_article(brief,text)

@pytest.mark.parametrize('key',[
    'publication_authorized','indexing_submission_authorized',
    'outbound_authorized','new_page_proposal_authorized'
])
def test_refuses_unauthorized_live_actions(review_sample,key):
    brief,text=review_sample
    brief[key]=True
    with pytest.raises(ValueError,match='authority_not_fail_closed'):
        review_article(brief,text)

def test_holds_keyword_absent_seo_title(review_sample):
    brief,text=review_sample
    brief['seo_title']='Everything About Marketing | Empire AI'
    with pytest.raises(ValueError,match='seo_title_does_not_target_primary_topic'):
        review_article(brief,text)

def test_holds_title_keyword_stuffing(review_sample):
    brief,text=review_sample
    brief['seo_title']='AI readiness assessment UK | AI readiness assessment UK'
    with pytest.raises(ValueError,match='seo_title_repeats_keyword'):
        review_article(brief,text)

def test_repeating_target_phrase_in_all_subheadings_fails(review_sample):
    brief,text=review_sample
    text=text.replace('## What governance and risks should an assessment cover?',
                      '## AI readiness assessment UK: What governance risks matter?')
    text=text.replace('## What happens after an AI readiness review?',
                      '## AI readiness assessment UK: What happens after a review?')
    with pytest.raises(ValueError,match='repeated_keyword_stuffed_subheadings'):
        review_article(brief,text)

def test_missing_original_source_citation_fails(review_sample):
    brief,text=review_sample
    text=text.replace('https://www.gov.uk/government/publications/ai-adoption-research/ai-adoption-research',
                      '/not-an-approved-source')
    with pytest.raises(ValueError,match='fewer_than_two_visible_original_sources'):
        review_article(brief,text)

def test_missing_internal_commercial_link_fails(review_sample):
    brief,text=review_sample
    text=text.replace('](/commercial)','](/wrong-destination)')
    with pytest.raises(ValueError,match='verified_internal_destination_missing'):
        review_article(brief,text)

def test_missing_price_disclosure_or_fulfilment_truth_fails(review_sample):
    brief,text=review_sample
    text=text.replace('£2,500','£50,000')
    with pytest.raises(ValueError,match='price_and_nonbinding_qualifications_missing'):
        review_article(brief,text)
    brief,text=review_sample
    brief['first_party_offer']['delivery_scope_verified']=True
    with pytest.raises(ValueError,match='founder_offer_scope_not_preserved'):
        review_article(brief,text)

def test_fabricated_search_volume_or_revenue_fails(review_sample):
    brief,text=review_sample
    brief['commercial_evidence']['query_search_volume']=100000
    with pytest.raises(ValueError,match='unsupported_demand_or_revenue_claim'):
        review_article(brief,text)
    brief,text=review_sample
    brief['commercial_evidence']['revenue_generated_gbp']=9999
    with pytest.raises(ValueError,match='unsupported_demand_or_revenue_claim'):
        review_article(brief,text)

def test_thin_sections_block_publication_review(review_sample):
    brief,text=review_sample
    start='## What is an AI readiness assessment, and who needs one?'
    after='## How much can an AI assessment cost in the UK?'
    assert start in text and after in text
    section=text[text.index(start):text.index(after)]
    text=text.replace(section,start+'\n\nThis is a thin unsupported answer.\n\n')
    with pytest.raises(ValueError,match='thin_or_unanswered_h2_section'):
        review_article(brief,text)

def test_unsafe_source_url_and_empty_meta_are_rejected(review_sample):
    brief,text=review_sample
    brief['sources'][0]['url']='http://localhost:8443/private'
    with pytest.raises(ValueError,match='noncanonical_external_source'):
        review_article(brief,text)
    brief,text=review_sample
    brief['meta_description']=''
    with pytest.raises(ValueError,match='keyword_title_or_meta_missing'):
        review_article(brief,text)

def test_no_h1_or_duplicate_h1_are_rejected(review_sample):
    brief,text=review_sample
    text=text.replace('# AI Readiness Assessment for UK Businesses',
                      '## AI Readiness Assessment for UK Businesses',1)
    with pytest.raises(ValueError,match='one_descriptive_h1_required'):
        review_article(brief,text)
    brief,text=review_sample
    text=text.replace('## What happens after an AI readiness review?',
                      '# Extra root title\n\n## What happens after an AI readiness review?')
    with pytest.raises(ValueError,match='one_descriptive_h1_required'):
        review_article(brief,text)

def test_business_specific_offers_are_visible_and_unbound(review_sample):
    brief,text=review_sample
    result=review_article(brief,text)
    assert result['first_party_service_catalogue_reviewed'] is True
    assert result['company_specific_service_descriptions']==3
    assert '## Which Empire AI service can help with an AI readiness decision?' in text
    assert '£2,500' in text and '£7,500' in text and '£3,000' in text


def test_erasing_company_offer_section_rejects_generic_keyword_article(review_sample):
    brief,text=review_sample
    first='## Which Empire AI service can help with an AI readiness decision?'
    last='## What is an AI readiness assessment, and who needs one?'
    assert first in text and last in text
    text=text[:text.index(first)]+text[text.index(last):]
    with pytest.raises(ValueError,match='real_business_service_or_starting_price_not_explained'):
        review_article(brief,text)


def test_changed_services_and_fake_price_fail(review_sample):
    brief=copy.deepcopy(review_sample[0]);text=review_sample[1]
    brief['verified_service_catalogue']['offers'][1]['starting_gbp']=9999
    with pytest.raises(ValueError,match='service_price_or_billing_not_catalogue_verified'):
        review_article(brief,text)
    brief=copy.deepcopy(review_sample[0]);text=review_sample[1]
    text=text.replace('£7,500','£9,999')
    with pytest.raises(ValueError,match='real_business_service_or_starting_price_not_explained'):
        review_article(brief,text)


def test_fake_immediate_checkout_in_catalogue_fails(review_sample):
    brief,text=review_sample
    brief['verified_service_catalogue']['checkout_enabled']=True
    with pytest.raises(ValueError,match='first_party_business_scope_unverified'):
        review_article(brief,text)

@pytest.mark.parametrize('hype',[
    'Unlock the power of AI',
    'Revolutionize your business',
    'Cutting-edge solutions',
    'Guaranteed results',
])
def test_ai_sounding_fluff_is_not_a_real_product_description(review_sample,hype):
    brief,text=review_sample
    text=text.replace('## What is an AI readiness assessment, and who needs one?',
                      hype+'\n\n## What is an AI readiness assessment, and who needs one?')
    with pytest.raises(ValueError,match='unsubstantiated_ai_marketing_hype'):
        review_article(brief,text)


def test_fake_client_case_study_is_rejected(review_sample):
    brief,text=review_sample
    text=text.replace('## What is an AI readiness assessment, and who needs one?',
                      'Our clients saved £200,000 on AI last year.\n\n## What is an AI readiness assessment, and who needs one?')
    with pytest.raises(ValueError,match='unverified_customer_or_performance_claim'):
        review_article(brief,text)
