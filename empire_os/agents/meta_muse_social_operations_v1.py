"""Muse organic Facebook/Instagram Page operations: draft-only content factory.

Produces page/account onboarding checklists, contextual keyword clusters,
post/Reel/story drafts, structured fourteen-day calendar, measurement contract
and future Meta ads proposal WITHOUT creating accounts or publishing media.
No Meta credentials, OAuth, network, page/IG API calls, paid traffic, third
party source text, consumer profiles, personal email or customer lead sale.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from typing import Any
import re

SCHEMA = "empire.meta_muse_social_operations.v1"
MEASUREMENT_SCHEMA = "empire.meta_muse_organic_aggregate_metrics.v1"
NICHES:dict[str,dict[str,Any]] = {
    "roofing": {
        "head":"Roofing", "audience":"property owners", "topic":"roof condition",
        "topics":("roof inspection questions","storm damage warning signs",
                  "repair versus replacement","contractor credentials",
                  "roofing quote comparison","maintenance priorities"),
        "keywords":("roof repair","roof inspection","roof replacement",
                    "roofing contractor","storm damage roof","roof maintenance"),
    },
    "hvac":{
        "head":"Heating & Cooling","audience":"homeowners",
        "topic":"heating and cooling performance",
        "topics":("heating maintenance","air conditioning efficiency",
                  "repair versus replacement","seasonal maintenance",
                  "technician credentials","comparing HVAC quotes"),
        "keywords":("HVAC repair","air conditioning service","heating maintenance",
                    "HVAC contractor","air filter replacement","HVAC quote"),
    },
    "plumbing":{
        "head":"Plumbing","audience":"property owners","topic":"plumbing maintenance",
        "topics":("leak warning signs","water heater questions",
                  "emergency plumbing preparation","contractor credentials",
                  "quote scope comparison","preventative plumbing checks"),
        "keywords":("plumbing repair","water leak","water heater",
                    "plumbing contractor","drain maintenance","plumber quote"),
    },
    "dental":{
        "head":"Dental Care","audience":"patients and families",
        "topic":"dental appointment planning",
        "topics":("questions for a dental visit","choosing a qualified dentist",
                  "appointment preparation","routine preventive care",
                  "dental consultation questions","understanding fees"),
        "keywords":("dental checkup","dentist appointment","dental consultation",
                    "preventive dentistry","dental practice","dental fees"),
    },
    "electrical":{
        "head":"Electrical Safety","audience":"property owners",
        "topic":"electrical service planning",
        "topics":("electrical inspection questions","finding a licensed electrician",
                  "renovation electrical planning","safety warning signs",
                  "choosing a contractor","quote comparison"),
        "keywords":("electrician","electrical inspection","electrical repair",
                    "electrical contractor","electrical safety","electrical quote"),
    },
}
MARKET = re.compile(r"^[a-z0-9][a-z0-9 ,.'()-]{1,95}$")
BRAND = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 &'.,-]{1,65}$")
PERIOD_DAYS = 14
TYPES=("facebook_post","instagram_carousel","instagram_reel","facebook_post",
       "instagram_story","instagram_reel","facebook_post",
       "instagram_carousel","instagram_reel","facebook_post",
       "instagram_story","instagram_reel","facebook_post","instagram_carousel")
# Do not make location-specific codes, laws, weather or provider claims without evidence.


def _hold(reason: str) -> dict[str, Any]:
    return {
        "schema_version":SCHEMA,"state":"HOLD","reason":reason,
        "content_drafts":[],"draft_count":0,
        "facebook_page_created":False,"instagram_account_created":False,
        "pages_connected":False,"posts_published":0,"reels_published":0,
        "ads_campaigns_created":0,"ad_spend_cents":0,
        "external_actions":0,"database_writes":False,
    }


def build_muse_social_operations(
    *, niche: str, market: str, brand: str = "Empire AI",
    start_date: date | None = None, verified_brand_owner: bool = False,
    page_connection_authorized: bool = False,
    future_ads_brief: bool = True,
) -> dict[str,Any]:
    """Draft organic assets. Owner approval is never inferred from inputs."""
    if (type(niche) is not str or niche not in NICHES
            or type(market) is not str or not MARKET.fullmatch(market)
            or type(brand) is not str or not BRAND.fullmatch(brand)):
        return _hold("unsupported_or_unverified_content_scope")
    if start_date is None:
        start_date = date.today()
    if type(start_date) is not date:
        return _hold("date_required_not_a_timestamp")
    if verified_brand_owner is not True and brand!="Empire AI":
        return _hold("no_proof_of_third_party_brand_authority")
    if page_connection_authorized:
        # A self-asserted flag cannot grant credential or publishing access.
        return _hold("real_platform_account_authority_not_authenticated")

    cfg=NICHES[niche]
    public_label=f"{brand} | {cfg['head']} — {market.title()}"
    topic_list=cfg["topics"]
    keywords=[*cfg["keywords"], f"{niche} {market}",f"{niche} questions {market}"]
    calendar=[]
    for i,kind in enumerate(TYPES):
        topic=topic_list[i%len(topic_list)]
        day=start_date+timedelta(days=i)
        hook=(
            f"{market.title()}: what should you ask about {topic}?"
            if i%2==0 else
            f"Before you book: a quick guide to {topic}."
        )
        # Real user input not collected: educational CTA only.
        cta="Save these questions and check local provider credentials before booking."
        caption=(f"{hook}\n\n"
                 f"Use written scopes, compare independently verified credentials "
                 f"and ask providers to explain their process. "
                 f"This is general guidance, not proof that any business "
                 f"serves this area.\n\n{cta}")
        hashtag_base=niche.replace(" ","")
        tag=f"#{hashtag_base} #{'LocalBusiness'} #ConsumerGuide"
        draft={
            "id":sha256(f"muse-social-v1:{brand}:{niche}:{market}:{day.isoformat()}:{kind}".encode()).hexdigest()[:20],
            "date":day.isoformat(),
            "platform":"facebook" if kind.startswith("facebook") else "instagram",
            "format":kind,
            "topic":topic,
            "content_pillar":(
                "educational_checklist" if i%3==0 else
                "buyer_questions" if i%3==1 else "provider_selection"
            ),
            "hook":hook,
            "caption_draft":caption,
            "hashtags_draft":tag,
            "recommended_keywords":[keywords[i%len(keywords)],keywords[(i+2)%len(keywords)]],
            "call_to_action":cta,
            "creative_asset_status":"NOT_CREATED",
            "verified_local_claims_embedded":False,
            "source_data_reproduced":False,
            "publish_state":"DRAFT_REQUIRES_EDITORIAL_AND_PLATFORM_APPROVAL",
            "scheduled_on_meta":False,
            "external_platform_submission":False,
            "metrics_observed":False,
        }
        if kind=="instagram_reel":
            draft["video_brief"]={
                "duration_seconds_target":30,
                "aspect_ratio":"9:16",
                "opening_overlay":hook,
                "storyboard":[
                    "0–4s: Title and niche-related original visual",
                    "4–14s: Two evidence-based questions about "+topic,
                    "14–25s: What to verify before choosing a provider",
                    "25–30s: Educational save/share CTA",
                ],
                "voiceover_draft":(
                    f"Considering {topic} in {market.title()}? "
                    "Ask what work is included and which qualifications matter. "
                    "Compare written estimates and check the provider yourself. "
                    "Save this for your next conversation."
                ),
                "audio_rights":"ORIGINAL_OR_SEPARATELY_LICENSED_ONLY",
                "generated_video_file_exists":False,
            }
        elif kind=="instagram_carousel":
            draft["carousel_brief"]={
                "slides":[
                    hook,
                    "What to check before contacting a provider",
                    "How to compare scope and credentials",
                    "Questions to ask about costs and timing",
                    "Save the checklist before booking",
                ],
                "asset_design_status":"NOT_RENDERED",
            }
        elif kind=="instagram_story":
            draft["story_brief"]={
                "prompt":"What is your biggest question about "+topic+"?",
                "poll":"What would be most useful? | Checklists | Questions",
                "personal_response_collection_authorized":False,
            }
        calendar.append(draft)
    return {
        "schema_version":SCHEMA,
        "state":"EDITORIAL_SOCIAL_OPERATIONS_DRAFT_ONLY",
        "source_video":"https://www.youtube.com/watch?v=tpZOU1ugODQ",
        "market_research_verified":False,
        "niche":niche,"market":market,
        "brand_display_name_candidate":public_label,
        "brand_owner_authenticated_by_meta":False,
        "page_setup":{
            "facebook_page":{
                "suggested_page_name":public_label,
                "category":"Educational local service information",
                "about_draft":(
                    f"Plain-language {cfg['head'].lower()} information for "
                    f"{cfg['audience']} in {market.title()}. "
                    "We help people prepare questions and independently "
                    "verify providers. No endorsement or service availability "
                    "is implied."
                ),
                "creation_action":"HUMAN_AUTHORISED_META_BUSINESS_SUITE_OR_SUPPORTED_API_ONLY",
                "created":False,
            },
            "instagram_professional":{
                "bio_draft":f"{cfg['head']} questions and local guides | {market.title()} | Independent verification first.",
                "account_type":"professional_business_when_eligible",
                "linked_facebook_page_verified":False,
                "created":False,
            },
            "prerequisites":[
                "prove_brand_and_admin_authority_for_both_platforms",
                "create_or_select_existing_meta_business_portfolio",
                "require_two_factor_admin_security_and_recovery",
                "confirm_facebook_page_and_instagram_business_access",
                "link_business_assets_and_verify_domain_and_privacy_url",
                "obtain_app_review_and_correct_publishing_permissions_if_api_used",
                "define moderation_disclosure_suppression_and_retention_policy",
                "require_founder_approved_editorial_and_release_window",
            ],
        },
        "keyword_clusters":{
            "service_and_questions":keywords,
            "intent_source":"STATIC_RESEARCH_STARTERS_NOT_SEARCH_VOLUME_DATA",
            "search_demand_measured":False,
            "live_competitor_or_serp_data_used":False,
        },
        "organic_calendar_days":PERIOD_DAYS,
        "content_drafts":calendar,
        "draft_count":len(calendar),
        "reels_with_storyboards":sum(d["format"]=="instagram_reel" for d in calendar),
        "content_editorial_guardrails":[
            "no_fake_local_reviews_certifications_prices_or_guarantees",
            "no_unverified_business_availability_or_lead_results",
            "all_visuals_audio_and_music_require_ownership_or_licence",
            "human_review_before_publish_or_schedule",
            "no_personal_profiles_comments_or_group_member_harvesting",
            "published_links_require_actual_first_party_consent_and_privacy",
        ],
        "measurement_spec":{
            "aggregate_only":True,
            "channels":["facebook_page","instagram_professional"],
            "metrics":["posts_published","reach","impressions","saves","shares",
                       "engaged_sessions","first_party_opt_ins","consented_enquiries",
                       "buyer_accepted_events","independently_settled_revenue_cents"],
            "no_clicks_or_reach_count_as_proven_revenue":True,
            "baseline":"NOT_CONNECTED",
        },
        "future_meta_ads":{
            "state":"FUTURE_RESEARCH_ONLY_NOT_SPEND_AUTHORIZED",
            "brief_included":bool(future_ads_brief),
            "objective_candidate":"lead_generation_after_first_party_consent_proven",
            "test_budget_usd":None,
            "approved_spend_usd":0,
            "conversions_api_and_pixel_need_privacy_consent":True,
            "business_manager_and_ads_account_authenticated":False,
            "billing_identity_and_authorised_payment_method_verified":False,
            "audience": "nonpersonal contextual/permissioned target definition only",
            "require_explicit_separate_founder_approval":True,
            "campaign_created":False,
            "spend_cents":0,
        },
        "facebook_page_created":False,
        "instagram_account_created":False,
        "pages_connected":False,
        "posts_published":0,
        "reels_published":0,
        "ads_campaigns_created":0,
        "ad_spend_cents":0,
        "external_actions":0,
        "database_writes":False,
        "execution_authority":"NONE",
    }


def review_organic_metrics(metrics:Mapping[str,Any]|None) -> dict[str,Any]:
    """Bounded aggregate feedback; no self-reported value is authenticated."""
    if not isinstance(metrics,Mapping) or metrics.get("schema_version")!=MEASUREMENT_SCHEMA:
        return {"state":"HOLD","reason":"no_approved_metrics_shape","revenue_verified_cents":0}
    allowed=("reach","impressions","saves","shares","posts_published",
             "engaged_sessions","first_party_opt_ins")
    if set(metrics)-{"schema_version",*allowed,"connected_provider_attested"}:
        return {"state":"HOLD","reason":"unsupported_or_personal_metric","revenue_verified_cents":0}
    if any(type(metrics.get(k)) is not int or not 0<=metrics[k]<=100000000 for k in allowed):
        return {"state":"HOLD","reason":"bad_aggregate_metrics","revenue_verified_cents":0}
    impressions=metrics["impressions"]
    saves=metrics["saves"]
    shares=metrics["shares"]
    if saves+shares>impressions or metrics["first_party_opt_ins"]>metrics["engaged_sessions"]:
        return {"state":"HOLD","reason":"inconsistent_aggregate_metrics","revenue_verified_cents":0}
    rate=round((saves+shares)/impressions,4) if impressions else None
    return {
        "state":"UNAUTHENTICATED_AGGREGATE_FEEDBACK",
        "engagement_rate_from_supplied_counts":rate,
        "optimization_hypothesis":(
            "PRIORITISE_EDUCATIONAL_SAVES_CONTENT" if rate is not None and rate>=0.02
            else "TEST_NEW_HOOKS_WITH_ORIGINAL_CREATIVE" if rate is not None
            else "NO_MEASURED_IMPRESSIONS"
        ),
        "provider_data_independently_authenticated":False,
        "revenue_verified_cents":0,
        "new_leads_sold":0,
        "ads_spend_cents":0,
        "external_actions":0,
    }
