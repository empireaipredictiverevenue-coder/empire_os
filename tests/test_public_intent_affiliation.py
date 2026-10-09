import json
from datetime import datetime, timezone
import pytest

from empire_os.public_intent_affiliation import (
    SCHEMA, load_evidence, validate_evidence,
)
from empire_os.intent_company_research_tasks import build_tasks
from empire_os.commercial_social_intent import build_social_intent_review

NOW=datetime(2026,10,9,23,0,tzinfo=timezone.utc)
MANNING_POST=("https://www.linkedin.com/posts/chase-manning-24712353_"
              "looking-for-a-freelance-seo-specialist-share-7431795613647745024-zZ4E")
SHIVYA_POST=("https://www.linkedin.com/posts/sahil-aggarwal-2b1a99221_"
             "looking-for-an-seo-team-agency-were-looking-activity-7475907789199003648-EKq0")


def reviewed(source=MANNING_POST, domain="manningpestservices.com",
             first_party="https://www.manningpestservices.com/about"):
    return {
        "source_post_url":source,
        "company_name":"Manning Pest Services",
        "company_domain":domain,
        "person_name":"Chase Manning",
        "social_profile_url":"https://www.linkedin.com/in/chase-manning-24712353",
        "official_company_evidence_url":first_party,
        "review_note":"Owner name appears independently on the company's About page.",
    }


def document(rows=None):
    return {
        "schema_version":SCHEMA,"origin":"manual_public_evidence_review",
        "records":rows if rows is not None else [reviewed()],
    }


def task(url=MANNING_POST):
    return {
        "public_post_url":url,
        "channel":"linkedin","niche":"pest control",
        "reported_intent_score":28,
        "observed_at":NOW.isoformat(),
        "potential_company_matches":[],
        "icp_relevance":{
            "intent_class":"EXPLICIT_REQUEST_UNVERIFIED",
            "candidate_offer_hypotheses":[{"offer_key":"search_growth_command"}],
        },
    }


def test_inspected_first_party_evidence_enters_review_but_never_outbound():
    notes=validate_evidence(document())
    out=build_tasks([task()],now=NOW,public_affiliation_evidence=notes)
    t=out["identity_review_tasks"][0]
    assert out["first_party_affiliation_evidence_tasks"]==1
    assert t["task_status"]=="FIRST_PARTY_AFFILIATION_REVIEW"
    assert t["public_affiliation_evidence"]["company_domain"]=="manningpestservices.com"
    assert t["source_attribution_proven"] is False
    assert t["verified_buyer_intent"] is False
    assert t["founder_outreach_authorized"] is False
    assert t["commercial_outcome_verified"] is False
    assert out["verified_buyer_count"]==0
    assert out["new_prospects_written"]==0


def test_other_url_does_not_inherit_owners_evidence():
    notes=validate_evidence(document())
    out=build_tasks([task("https://www.linkedin.com/posts/other/123")],
                    now=NOW,public_affiliation_evidence=notes)
    t=out["identity_review_tasks"][0]
    assert t["public_affiliation_evidence"] is None
    assert t["task_status"]=="INDEPENDENT_COMPANY_IDENTITY_RESEARCH"


@pytest.mark.parametrize("bad",[
    document([reviewed(domain="evil.com")]),
    document([reviewed(first_party="https://evil.com/about")]),
    document([reviewed(first_party="https://manningpestservices.com.evil.com/about")]),
    document([reviewed(source="https://attack.invalid/posts/a")]),
    document([reviewed()]*2),
    {**document(), "origin":"unknown"},
])
def test_untrusted_manual_evidence_fails_closed(bad):
    with pytest.raises(ValueError):
        validate_evidence(bad)


def test_first_party_file_requires_private_permissions(tmp_path):
    p=tmp_path/"manual-review.json"
    p.write_text(json.dumps(document()))
    p.chmod(0o644)
    with pytest.raises(ValueError):
        load_evidence(p)
    p.chmod(0o600)
    assert len(load_evidence(p))==1


def test_no_fake_approval_on_repeat_reviews():
    notes=validate_evidence(document())
    first=build_tasks([task()],now=NOW,public_affiliation_evidence=notes)
    later=datetime(2026,10,9,23,30,tzinfo=timezone.utc)
    second=build_tasks([task()],now=later,public_affiliation_evidence=notes,
                       previous_tasks=first["identity_review_tasks"])
    a=first["identity_review_tasks"][0]
    b=second["identity_review_tasks"][0]
    assert a["task_id"]==b["task_id"]
    assert a["first_seen_at"]==b["first_seen_at"]
    assert b["founder_outreach_authorized"] is False
    assert b["person_contact_verified"] is False


def test_existing_social_review_carries_public_evidence_only_in_research_task():
    notes=validate_evidence(document())
    signals={
        "one":{
            "source":"linkedin_intent","status":"unresolved",
            "url":MANNING_POST,"raw":{"community_intent":{
                "url":MANNING_POST,"observed_at":NOW.isoformat(),
                "title":"Looking for a Freelance SEO Specialist",
                "text":"I need SEO help with my local pest company",
                "intent_score":60,"niche":"pest control",
                "pain_points":["search_visibility"],
            }},
        },
    }
    out=build_social_intent_review(signals,[],now=NOW,
                                   public_affiliation_evidence=notes)
    research=out["company_identity_research"]
    assert research["created_or_preserved_task_count"]==1
    assert research["first_party_affiliation_evidence_tasks"]==1
    assert out["verified_poster_to_company_identity_count"]==0
    assert out["verified_commercial_buying_intent_count"]==0
    assert out["outbound_sent"] is False


def test_country_specific_linkedin_profile_is_valid_but_lookalikes_blocked():
    record=reviewed()
    record["social_profile_url"]="https://in.linkedin.com/in/chase-manning-24712353"
    result=validate_evidence(document([record]))
    assert len(result)==1
    record["social_profile_url"]="https://in.linkedin.com.evil.example/in/chase-manning"
    with pytest.raises(ValueError,match="unsupported_social_profile"):
        validate_evidence(document([record]))
