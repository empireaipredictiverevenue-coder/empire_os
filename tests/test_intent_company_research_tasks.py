from datetime import datetime, timezone
from empire_os.icp_intent_relevance import classify_icp_intent
from empire_os.intent_company_research_tasks import build_tasks
from empire_os.commercial_social_intent import build_social_intent_review

NOW = datetime(2026, 10, 9, 22, tzinfo=timezone.utc)


def item(url, kind, score=75, channel="reddit", company_matches=None):
    return {
        "public_post_url":url, "channel":channel, "observed_at":NOW.isoformat(),
        "niche":"roofing", "reported_intent_score":score,
        "icp_relevance":{
            "intent_class":kind,
            "candidate_offer_hypotheses":[{
                "offer_key":"predictive_revenue_demand_engine",
                "verified_product_fit":False,
            }],
        },
        "potential_company_matches":company_matches or [],
    }


def test_hiring_career_product_promotion_are_not_hot_buying_signals():
    examples = [
        ("[HIRING] Client Acquisition / Sales Partner for Video Editing Agency",
         "NON_COMMERCIAL_HIRING_OR_CAREER"),
        ("We're hiring an Inside Sales Representative. Send your resume",
         "NON_COMMERCIAL_HIRING_OR_CAREER"),
        ("Where should I take my sales career? Need advice",
         "NON_COMMERCIAL_HIRING_OR_CAREER"),
        ("Built a B2B SaaS last year. Turned out better than expected",
         "SELLER_PITCH"),
        ("We run a roofing company and need more qualified appointments",
         "EXPLICIT_REQUEST_UNVERIFIED"),
    ]
    for raw, expected in examples:
        assert classify_icp_intent({
            "title":raw,"pain_points":["lead_generation"],
        })["intent_class"] == expected


def test_only_business_requests_and_operator_problems_become_research_tasks():
    inputs=[
        item("https://reddit.com/r/roofing/x","EXPLICIT_REQUEST_UNVERIFIED",65),
        item("https://reddit.com/r/roofing/y","OPERATOR_PROBLEM_SELF_REPORTED",70),
        item("https://reddit.com/r/roofing/z","SELLER_PITCH",100),
        item("https://linkedin.com/posts/hiring","NON_COMMERCIAL_HIRING_OR_CAREER",100,channel="linkedin"),
        item("https://linkedin.com/posts/advice","UNATTRIBUTED_DISCUSSION",100,channel="linkedin"),
    ]
    report=build_tasks(inputs,now=NOW)
    assert report["created_or_preserved_task_count"]==2
    assert report["eligible_intent_observations"]==2
    assert report["excluded_unsupported_observations"]==3
    assert report["verified_buyer_count"]==0
    assert report["new_prospects_written"]==0
    assert report["outbound_authorized"] is False
    assert all(x["founder_outreach_authorized"] is False for x in report["identity_review_tasks"])


def test_same_post_retains_stable_task_id_and_first_seen():
    row=item("https://reddit.com/r/roofing/post","EXPLICIT_REQUEST_UNVERIFIED")
    a=build_tasks([row],now=NOW)
    later=datetime(2026,10,9,23,tzinfo=timezone.utc)
    b=build_tasks([row],now=later,
       previous_tasks=a["identity_review_tasks"])
    assert a["identity_review_tasks"][0]["task_id"]==b["identity_review_tasks"][0]["task_id"]
    assert a["identity_review_tasks"][0]["first_seen_at"]==b["identity_review_tasks"][0]["first_seen_at"]
    assert b["identity_review_tasks"][0]["last_evaluated_at"]!=a["identity_review_tasks"][0]["last_evaluated_at"]
    assert b["identity_review_tasks"][0]["commercial_outcome_verified"] is False


def test_explicit_link_is_not_proven_authorship():
    row=item("https://reddit.com/r/roofing/link","EXPLICIT_REQUEST_UNVERIFIED",
             company_matches=[{"entity_key":"roofco","evidence_website":"https://roofco.com"}])
    task=build_tasks([row],now=NOW)["identity_review_tasks"][0]
    assert task["task_status"]=="EVIDENCE_LINK_REVIEW"
    assert task["source_attribution_proven"] is False
    assert task["verified_buyer_intent"] is False
    assert task["person_contact_verified"] is False


def test_bounded_queue_is_not_driven_by_raw_scores_alone():
    rows=[]
    for n in range(30):
        channel="reddit" if n%2 else "linkedin"
        rows.append(item(f"https://{channel}.com/posts/{n}",
            "OPERATOR_PROBLEM_SELF_REPORTED",85,channel=channel))
    rows.append(item("https://reddit.com/r/roofing/direct",
             "EXPLICIT_REQUEST_UNVERIFIED",41))
    rows.append(item("https://reddit.com/r/roofing/marketing",
             "SELLER_PITCH",100))
    result=build_tasks(rows,now=NOW)
    assert len(result["identity_review_tasks"])==12
    assert result["review_backlog_truncated"] is True
    assert result["identity_review_tasks"][0]["intent_class"]=="EXPLICIT_REQUEST_UNVERIFIED"
    assert any(x["source"]=="reddit" for x in result["identity_review_tasks"])
    assert any(x["source"]=="linkedin" for x in result["identity_review_tasks"])


def test_existing_social_review_contains_bounded_research_tasks_not_contacts():
    data={
        "one":{
            "source":"reddit_intent","status":"unresolved",
            "url":"https://reddit.com/r/roofing/direct",
            "raw":{"community_intent":{
                "url":"https://reddit.com/r/roofing/direct",
                "observed_at":NOW.isoformat(),
                "title":"Need qualified roof leads",
                "text":"We run a roofing business and need more appointments",
                "intent_score":80,
                "niche":"roofing","pain_points":["lead_generation"],
            }},
        },
        "marketing":{
            "source":"linkedin_intent","status":"unresolved",
            "url":"https://linkedin.com/posts/job",
            "raw":{"community_intent":{
                "url":"https://linkedin.com/posts/job",
                "observed_at":NOW.isoformat(),
                "title":"We're hiring a sales manager",
                "text":"Join our team. Send your resume",
                "intent_score":100,
            }},
        },
    }
    review=build_social_intent_review(data,[],now=NOW)
    tasks=review["company_identity_research"]
    assert tasks["created_or_preserved_task_count"]==1
    assert tasks["identity_review_tasks"][0]["task_status"]=="INDEPENDENT_COMPANY_IDENTITY_RESEARCH"
    assert tasks["outbound_authorized"] is False
