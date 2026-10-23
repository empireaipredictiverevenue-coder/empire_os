"""Public first-party company source check is non-sending, cached and gated."""
from datetime import datetime, timedelta, timezone
import json

import pytest

from empire_os.founder_acquisition_source_refresh import (
    EvidenceHeld, refresh_pending, verify_profile, _safe_url,
)
from scripts.run_founder_acquisition_review import refresh_unsent_sources
from tests.test_founder_acquisition_autopilot import fixture_ledger, CLOCK

ROWS = [
    {"company": "LunaBill", "published_contact": "founders@lunabill.com",
     "yc_original_source": "https://www.ycombinator.com/companies/lunabill",
     "public_request_target": "hospital revenue-cycle directors"},
    {"company": "ProhostAI", "published_contact": "bill@prohost.ai",
     "yc_original_source": "https://www.ycombinator.com/companies/prohostai",
     "public_request_target": "short-term rental managers"},
    {"company": "Qlo", "published_contact": "founders@getqlo.com",
     "yc_original_source": "https://www.ycombinator.com/companies/qlo",
     "public_request_target": "insurance programme managers"},
]


def source(row, *, ask=True, email=True, name=True, content_type="text/html"):
    title = row["company"] if name else "Different Startup"
    address = row["published_contact"] if email else "no-contact-present"
    body = f'<html><head><title>{title}: Public company profile | Y Combinator</title></head><body>{address} {"Our Ask: we would love warm intros" if ask else "Company description"}</body></html>'
    return {
        "status_code": 200, "final_url": row["yc_original_source"],
        "content_type": content_type, "body": body.encode(),
    }


def test_exact_yc_page_contact_and_ask_gated():
    r = ROWS[0]
    proof = verify_profile(r["company"],r["yc_original_source"],r["published_contact"],fetched=source(r),observed_at=CLOCK)
    assert proof["profile_source_status"] == "FIRST_PARTY_PROFILE_AND_ADDRESS_OBSERVED"
    assert proof["public_ask_marker_observed"] is True
    assert proof["outbound_authorized"] is False
    assert "published_contact" not in proof
    assert not _safe_url("https://www.ycombinator.com.evil.com/companies/lunabill")
    assert not _safe_url("https://www.ycombinator.com/companies/lunabill?open=admin")


@pytest.mark.parametrize("changes,reason", [
    ({"email":False},"PUBLISHED_ADDRESS_NOT_CORROBORATED"),
    ({"name":False},"COMPANY_TITLE_IDENTITY_MISMATCH"),
    ({"content_type":"application/json"},"ORIGINAL_SOURCE_HTTP_NOT_VERIFIED"),
])
def test_wrong_original_source_evidence_fails_closed(changes, reason):
    r=ROWS[0]
    with pytest.raises(EvidenceHeld,match=reason):
        verify_profile(r["company"],r["yc_original_source"],r["published_contact"],fetched=source(r,**changes),observed_at=CLOCK)


def test_two_per_cycle_then_cached_no_duplicate_drafts():
    visited=[]
    def fake(url):
        row=next(x for x in ROWS if x["yc_original_source"]==url)
        visited.append(url)
        return source(row)
    first=refresh_pending(ROWS,previous=None,now=CLOCK,fetch=fake)
    assert len(visited)==2 and first["source_fetches_this_cycle"]==2
    assert first["verified_public_profiles"]==2
    assert len(first["unsent_review_drafts"])==2
    assert first["prospects_waiting_for_source_check"]==1
    assert all(d["status"]=="UNSENT_FOUNDER_REVIEW_REQUIRED" for d in first["unsent_review_drafts"])
    assert all("warm introductions" in d["body"] for d in first["unsent_review_drafts"])
    second=refresh_pending(ROWS,previous=first,now=CLOCK+timedelta(minutes=5),fetch=fake)
    assert len(visited)==3 and second["source_fetches_this_cycle"]==1
    assert len(second["unsent_review_drafts"])==3
    third=refresh_pending(ROWS,previous=second,now=CLOCK+timedelta(minutes=10),fetch=fake)
    assert len(visited)==3 and third["source_fetches_this_cycle"]==0
    assert third["buyer_interest_verified"] is False and third["outbound_sent"] is False


def test_no_ask_no_draft_even_when_contact_public():
    r=ROWS[0]
    packet=refresh_pending([r],previous=None,now=CLOCK,fetch=lambda url: source(r,ask=False))
    assert packet["verified_public_profiles"]==1
    assert packet["unsent_review_drafts"]==[]


def test_fetch_failure_is_hold_and_delays_retry():
    calls=[]
    def broken(url):
        calls.append(url)
        raise RuntimeError("offline")
    v=refresh_pending(ROWS[:1],previous=None,now=CLOCK,fetch=broken)
    assert v["profiles"][0]["profile_source_status"]=="HELD_SOURCE_NOT_VERIFIED"
    assert v["source_fetches_this_cycle"]==1
    v2=refresh_pending(ROWS[:1],previous=v,now=CLOCK+timedelta(minutes=5),fetch=broken)
    assert len(calls)==1 and v2["source_fetches_this_cycle"]==0
    assert not v2["unsent_review_drafts"]


def test_prior_research_source_deletion_holds():
    first=refresh_pending(ROWS[:2],previous=None,now=CLOCK,fetch=lambda u: source(next(r for r in ROWS if r["yc_original_source"]==u)))
    with pytest.raises(EvidenceHeld,match="UNEXPLAINED_SOURCE_PROSPECT_REMOVAL"):
        refresh_pending(ROWS[1:2],previous=first,now=CLOCK+timedelta(minutes=5))


def test_snapshot_persisted_private_no_email_body_or_password(tmp_path):
    ledger=fixture_ledger(tmp_path)
    lookup={}
    with (tmp_path/"research_reviews/data/VC_FUNDED_FOUNDER_OUTREACH_BATCH_16_20261023.csv").open() as f:
        import csv
        for row in csv.DictReader(f):
            lookup[row["yc_original_source"]]=row
    result=refresh_unsent_sources(tmp_path,ledger=ledger,now=CLOCK,fetch=lambda u:source(lookup[u]))
    assert result["source_refresh_status"]=="PUBLIC_SOURCES_REVIEW_ONLY"
    assert result["source_profiles_reviewed"]==2
    assert result["source_profiles_verified"]==2
    out=tmp_path/"runtime/founder_acquisition/public_source_review_latest.json"
    assert out.stat().st_mode & 0o077==0
    content=json.loads(out.read_text())
    assert content["outbound_sent"] is False
    assert content["paid_pilot_authorized"] is False
    assert "published_contact" not in out.read_text()
    assert "password" not in out.read_text().lower()


def test_two_exact_contacted_public_profiles_are_archived_not_resent():
    source_rows=ROWS[:2]
    source_rows=list(source_rows)
    assert {r['company'] for r in source_rows}=={'LunaBill','ProhostAI'}
    initial=refresh_pending(source_rows,previous=None,now=CLOCK,
                            fetch=lambda url:source(next(r for r in source_rows if r['yc_original_source']==url)))
    assert initial['verified_public_profiles']==2
    extra=ROWS[2]
    moved=refresh_pending([extra],previous=initial,
                          contacted_verified={
                            'LunaBill':'1a169d6472ef70f1',
                            'ProhostAI':'1a169d67e9260fe6',
                          },
                          now=CLOCK+timedelta(minutes=5),fetch=lambda url:source(extra))
    assert len(moved['contacted_profile_history'])==2
    assert len(moved['profiles'])==1
    assert all(x['company'] not in {'LunaBill','ProhostAI'} for x in moved['unsent_review_drafts'])
    again=refresh_pending([extra],previous=moved,
                          now=CLOCK+timedelta(minutes=10),fetch=lambda url:source(extra))
    assert again['contacted_profile_history']==moved['contacted_profile_history']
    assert again['source_fetches_this_cycle']==0


def test_contacted_profile_migration_cannot_use_unverified_sent_id():
    originals=ROWS[:2]
    old=refresh_pending(originals,previous=None,now=CLOCK,
                        fetch=lambda url:source(next(r for r in originals if r['yc_original_source']==url)))
    with pytest.raises(EvidenceHeld,match='UNEXPLAINED_SOURCE_PROSPECT_REMOVAL'):
        refresh_pending([ROWS[2]],previous=old,now=CLOCK+timedelta(minutes=5),
                        contacted_verified={'LunaBill':'0000000000000000',
                                            'ProhostAI':'1a169d67e9260fe6'})
