#!/usr/bin/env python3
"""Deterministic OBSERVE-only editorial acceptance for one existing campaign.

A useful title/H1 and relevant sections are checked; forcing a keyword into
EVERY heading is deliberately not a requirement. This is not Google's ranking
algorithm; passing means 'human review can begin', not publish-ready.

No network, credentials, live site, Google API, database, or output writes.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
BRIEF=ROOT/'docs/marketing/GROWTH_001_AI_READINESS_ARTICLE_BRIEF_20261016.json'
DRAFT=ROOT/'docs/marketing/GROWTH_001_AI_READINESS_ARTICLE_DRAFT_20261016.md'
DOC_SCHEME='empire.marketing_growth.editorial_quality.v1'
STOPWORDS={'for','and','the','of','a','an','in','to','on','with'}
EXACT_INTRO='**INTERNAL EDITORIAL NOTES — NOT PUBLIC COPY:**'
EXACT_HARD_APPROVALS=('publication_authorized','indexing_submission_authorized','outbound_authorized','new_page_proposal_authorized')


def tokens(value: str)->set[str]:
    return {x for x in re.findall(r"[a-z0-9]+",str(value).lower()) if x not in STOPWORDS}


def review_article(brief:dict, text:str)->dict:
    if not isinstance(brief,dict) or not isinstance(text,str):
        raise ValueError('invalid_article_review_input')
    if (brief.get('schema_version')!='empire.marketing_growth.editorial_brief.v1'
        or brief.get('parent_department')!='marketing_growth'
        or brief.get('status')!='DRAFT_ONLY'
        or brief.get('execution_authority')!='NONE'
        or brief.get('site_owner')!='ASTRA existing website owner'):
        raise ValueError('untrusted_campaign_or_owner')
    if any(brief.get(k) is not False for k in EXACT_HARD_APPROVALS):
        raise ValueError('authority_not_fail_closed')
    if (brief.get('campaign_id')!='GROWTH-001'
        or not isinstance(brief.get('publication_holds'),list)
        or len(brief['publication_holds'])<3):
        raise ValueError('unapproved_campaign_or_missing_holds')
    keyword=brief.get('primary_keyword')
    title=brief.get('seo_title')
    meta=brief.get('meta_description')
    if not all(isinstance(x,str) and x.strip() for x in (keyword,title,meta)):
        raise ValueError('keyword_title_or_meta_missing')
    if len(keyword)>100 or len(title)>140 or not (65<=len(meta)<=210):
        raise ValueError('title_or_meta_unhelpful_length_house_style')
    intent=brief.get('search_intent')
    if intent not in {'commercial_research_and_vendor_evaluation','informational_problem_solving','product_comparison'}:
        raise ValueError('unreviewed_user_search_intent')
    expected=brief.get('expected_h1')
    if not isinstance(expected,str) or not expected.strip():
        raise ValueError('expected_h1_missing')
    topical=tokens(keyword)
    if not topical or len(topical)<3:
        raise ValueError('primary_keyword_not_specific')
    if title.casefold().count(keyword.casefold())>1:
        raise ValueError('seo_title_repeats_keyword')
    if len(topical-tokens(title))>1:
        raise ValueError('seo_title_does_not_target_primary_topic')
    if len(topical-tokens(expected))>1:
        raise ValueError('brief_h1_does_not_target_primary_topic')
    if EXACT_INTRO not in text:
        raise ValueError('internal_editorial_section_missing')
    public=text.split(EXACT_INTRO)[0].split('\n---\n')[0]
    headings=[(len(m.group(1)),m.group(2).strip()) for m in re.finditer(r'^([#]{1,6})\s+(.+?)\s*$',public,re.M)]
    h1=[v for depth,v in headings if depth==1]
    h2=[v for depth,v in headings if depth==2]
    h3=[v for depth,v in headings if depth==3]
    if len(h1)!=1 or h1[0]!=expected:
        raise ValueError('one_descriptive_h1_required')
    if len(h2)<4 or len(h2)>14:
        raise ValueError('insufficient_or_excessive_section_headings')
    section_matches=list(re.finditer(r'^##\s+.+$',public,re.M))
    section_words=[]
    for idx,section in enumerate(section_matches):
        end=section_matches[idx+1].start() if idx+1<len(section_matches) else len(public)
        section_words.append(len(public[section.end():end].split()))
    if section_words and min(section_words)<35:
        raise ValueError('thin_or_unanswered_h2_section')
    if len({h.lower().strip(' ?') for h in h2})!=len(h2):
        raise ValueError('repeated_section_headings')
    if any(depth>3 for depth,_ in headings):
        raise ValueError('heading_hierarchy_unreviewed')
    previous_depth=0
    for depth,label in headings:
        if depth>previous_depth+1:
            raise ValueError('heading_level_skipped')
        if label.lower().strip().startswith('click here'):
            raise ValueError('meaningless_heading')
        previous_depth=depth
    # Four useful sections/questions are more valuable than a verbatim keyword
    # pasted into every H2. Allow ONE matching H2, but never require one.
    phrase=keyword.casefold().strip()
    phrase_repeated=sum(phrase in h.casefold() for h in h2+h3)
    if phrase_repeated>1:
        raise ValueError('repeated_keyword_stuffed_subheadings')
    if sum('?' in h for h in h2+h3)<2:
        raise ValueError('insufficient_real_buyer_questions')
    related=brief.get('secondary_topics')
    if not isinstance(related,list) or len(related)<4 or any(not isinstance(s,str) for s in related):
        raise ValueError('topical_research_missing')
    # Broad topical theme coverage rather than brittle exact-match phrase counts.
    lines=' '.join(h2).lower()
    theme_groups=({'cost','price','fees','£'}, {'roi','return','benefit','value'},
                  {'process','data','workflow','systems'}, {'risk','security','governance','privacy'},
                  {'scope','deliverable','assessment','quotation'})
    matched_groups=sum(any(term in lines for term in group) for group in theme_groups)
    if matched_groups<4:
        raise ValueError('essential_buyer_topic_questions_unanswered')
    if len(public.split())<550:
        raise ValueError('insufficient_original_explanatory_content')
    # Source declarations need real HTTPS publisher URLs and at least two
    # first-party independent public references visible in the draft body.
    sources=brief.get('sources')
    if not isinstance(sources,list) or len(sources)<2 or len(sources)>15:
        raise ValueError('missing_claim_sources')
    urls=set()
    for source in sources:
        if not isinstance(source,dict) or not source.get('fact_scope') or not source.get('type'):
            raise ValueError('unspecified_claim_scope')
        url=source.get('url')
        parsed=urlsplit(url if isinstance(url,str) else '')
        if (parsed.scheme!='https' or not parsed.hostname
                or parsed.username or parsed.password or parsed.fragment):
            raise ValueError('noncanonical_external_source')
        urls.add(url)
    referenced=[url for url in urls if url in public]
    if len(referenced)<2:
        raise ValueError('fewer_than_two_visible_original_sources')
    internal=brief.get('internal_links_required')
    if not isinstance(internal,list) or not internal or any(not isinstance(x,str) or not x.startswith('/') or x.startswith('//') for x in internal):
        raise ValueError('invalid_internal_link_contract')
    if any(']('+link+')' not in public for link in internal):
        raise ValueError('verified_internal_destination_missing_from_manuscript')
    if not isinstance(brief.get('planned_cta'),str) or not brief['planned_cta']:
        raise ValueError('no_consent_governed_conversion_path')
    offer=brief.get('first_party_offer')
    if (not isinstance(offer,dict)
        or offer.get('product_code')!='consultancy_opportunity_assessment'
        or type(offer.get('starting_price_gbp')) is not int
        or offer['starting_price_gbp']!=2500
        or offer.get('delivery_scope_verified') is not False
        or offer.get('binding_terms_ready') is not False
        or offer.get('checkout_enabled') is not False
        or offer.get('founder_price_approved') is not True):
        raise ValueError('founder_offer_scope_not_preserved')
    if ('£2,500' not in public or 'nonbinding' not in public.lower()
        or 'vat' not in public.lower()):
        raise ValueError('price_and_nonbinding_qualifications_missing')
    catalogue=brief.get('verified_service_catalogue')
    if (not isinstance(catalogue,dict)
        or catalogue.get('first_party_url')!='https://empire-ai.co.uk/v1/checkout/commercial/offers'
        or catalogue.get('claim_mode')!='FOUNDER_LED_PROPOSAL_ONLY'
        or catalogue.get('delivery_scope_verified') is not False
        or catalogue.get('binding_terms_ready') is not False
        or catalogue.get('checkout_enabled') is not False
        or catalogue.get('existing_customers_or_success_claim_verified') is not False):
        raise ValueError('first_party_business_scope_unverified')
    official={
        'consultancy_opportunity_assessment':('Opportunity Assessment',2500,'one_time'),
        'consultancy_strategy_blueprint':('Strategy Blueprint',7500,'one_time'),
        'consultancy_strategic_advisory':('Strategic Advisory',3000,'monthly'),
    }
    choices=catalogue.get('offers')
    if not isinstance(choices,list) or len(choices)!=len(official):
        raise ValueError('verified_service_catalogue_missing')
    present={}
    for item in choices:
        if not isinstance(item,dict):
            raise ValueError('verified_service_item_invalid')
        code=item.get('product_code')
        if code in present or code not in official:
            raise ValueError('unverified_service_name_or_duplicate')
        pair=(item.get('name'),item.get('starting_gbp'),item.get('interval'))
        if pair!=official[code]:
            raise ValueError('service_price_or_billing_not_catalogue_verified')
        present[code]=True
        amount=f"£{official[code][1]:,}"
        if item['name'] not in public or amount not in public:
            raise ValueError('real_business_service_or_starting_price_not_explained')
    if ('## Which Empire AI service can help with an AI readiness decision?'
            not in public or 'Empire AI develops Predictive Revenue' not in public):
        raise ValueError('company_specific_service_explanation_missing')
    expected_disclosures=('founder-led','starting prices','scope','deliverables','vat','nonbinding')
    if any(term not in public.lower() for term in expected_disclosures):
        raise ValueError('unscoped_or_binding_service_claim')
    overly_generic=(
        'unlock the power of ai','game-changing ai solutions',
        'revolutionize your business','cutting-edge solutions',
        'leverage ai to transform','skyrocket your revenue',
        'guaranteed results','unprecedented growth',
    )
    if any(hype in public.lower() for hype in overly_generic):
        raise ValueError('unsubstantiated_ai_marketing_hype')
    proof_claims=(r'(?i)our clients (?:saved|earned|generated)',
                  r'(?i)we (?:delivered|guaranteed) (?:an? )?(?:roi|revenue|increase)',
                  r'(?i)we (?:have )?(?:already )?completed hundreds of')
    if any(re.search(pattern,public) for pattern in proof_claims):
        raise ValueError('unverified_customer_or_performance_claim')
    commercial=brief.get('commercial_evidence')
    if (not isinstance(commercial,dict)
        or commercial.get('query_search_volume') is not None
        or commercial.get('revenue_generated_gbp') is not None
        or commercial.get('serp_top_ten_measured') is not False):
        raise ValueError('unsupported_demand_or_revenue_claim')
    if re.search(r'(?i)guarantee[ds]?\s+(?:a|the|\d+|#1|first)\s+(?:roi|ranking|revenue|return)',public):
        raise ValueError('unverified_guarantee_phrase')
    return {
        'schema_version': DOC_SCHEME,
        'status':'EDITORIAL_STRUCTURE_PASS_HUMAN_REVIEW_REQUIRED',
        'campaign_id':brief['campaign_id'],
        'main_keyword':keyword,
        'seo_title':title,
        'h1':h1[0],
        'h2_count':len(h2),'h3_count':len(h3),
        'question_headings':sum('?' in h for h in h2+h3),
        'related_theme_groups_covered':matched_groups,
        'exact_main_keyword_repeated_in_h2_h3':phrase_repeated,
        'body_word_count':len(public.split()),
        'visible_original_sources':len(referenced),
        'internal_destination_count':len(internal),
        'price_source':'founder_approved_offer_catalogue_readback',
        'first_party_service_catalogue_reviewed':True,
        'company_specific_service_descriptions':len(present),
        'source_quality_human_review_required':True,
        'human_commercial_delivery_review_required':True,
        'unverified_search_volume':True,
        'editorial_release_authorized':False,
        'production_writes':False,
        'external_requests':False,
        'outbound_sent':False,
        'new_campaign_or_timer_started':False,
        'next_owner':'existing_marketing_director_and_ASTRA_site_owner',
        'disclaimer':'Passing is on-page structure and declared evidence only; no ranking, indexation, external citation or real revenue is implied.'
    }


def main()->None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review-only',required=True,action='store_true')
    args=parser.parse_args()
    try:
        brief=json.loads(BRIEF.read_text(encoding='utf-8'))
        result=review_article(brief,DRAFT.read_text(encoding='utf-8'))
    except (ValueError,OSError,TypeError) as exc:
        print(json.dumps({'status':'EDITORIAL_REVIEW_HELD','reason_code':str(exc),
            'publishing_authorized':False,'production_writes':False},sort_keys=True))
        raise SystemExit(2)
    print(json.dumps(result,sort_keys=True,indent=2))


if __name__=='__main__':main()
