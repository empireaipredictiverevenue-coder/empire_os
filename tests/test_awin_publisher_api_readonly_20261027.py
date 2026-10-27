"""Independent Awin publisher API safety tests. Never contact Awin."""
from datetime import datetime, timezone
import json
from pathlib import Path
import stat
from urllib.parse import urlsplit, parse_qs

import pytest

from empire_os.awin_publisher_api import (
    AwinAPIHold, _normalise, _private_token, review,
)

NOW=datetime(2026,10,27,14,15,tzinfo=timezone.utc)


def token(path: Path):
    path.write_text("eyJhbGciOiJIUzI1NiJ9.mocked.safeTestToken")
    path.chmod(0o600)
    return path


def response(id, status):
    return {"programmeInfo":{
        "id":int(id),"membershipStatus":status,
        "clickThroughUrl":"https://example.net/not-allowed-to-publish",
        "name":"untrusted_provider_string",
    },"kpi":{"epc":42.5}}


def transport(statuses, count):
    def fetch(url, secret):
        count.append(url)
        assert secret.startswith("eyJ")
        parts=urlsplit(url)
        assert parts.scheme=="https" and parts.netloc=="api.awin.com"
        assert parts.path=="/publishers/3136281/programmedetails"
        q=parse_qs(parts.query)
        assert q["relationship"]==["any"]
        assert set(q)=={"advertiserId","relationship"}
        advertiser_id=q["advertiserId"][0]
        return response(advertiser_id,statuses[advertiser_id])
    return fetch


def test_no_token_fail_closed_without_external_calls(tmp_path):
    calls=[]
    r=review(token_path=tmp_path/"missing",output=tmp_path/"output.json",
             transport=lambda *_:calls.append(1),write=True,now=NOW)
    assert r["status"].startswith("HELD")
    assert r["requests_made"]==0
    assert not r["snapshot_written"]
    assert not calls
    assert not (tmp_path/"output.json").exists()


def test_two_pending_programmes_and_no_secrets_in_snapshot(tmp_path):
    calls=[]
    cred=token(tmp_path/"token")
    output=tmp_path/"snapshot"
    statuses={"122556":"Pending","73922":"Pending"}
    r=review(token_path=cred, output=output, now=NOW,write=True,
             transport=transport(statuses,calls))
    assert r["status"]=="AWIN_API_MEMBERSHIP_REVIEW_VERIFIED"
    assert r["requests_made"]==2 and len(calls)==2
    assert r["publisher_id"]=="3136281"
    assert [x["membership_status"] for x in r["programmes"]]==["PENDING","PENDING"]
    assert r["api_live_verified"]
    assert not r["commission_earned_verified"]
    assert not r["affiliate_publication_authorized"]
    assert stat.S_IMODE(output.stat().st_mode)==0o600
    text=output.read_text()
    assert "safeTestToken" not in text
    assert "untrusted_provider_string" not in text
    assert "not-allowed-to-publish" not in text


def test_joined_emits_review_action_but_never_activates(tmp_path):
    calls=[]
    r=review(token_path=token(tmp_path/"token"),
             output=tmp_path/"snap",now=NOW,write=False,
             transport=transport({"122556":"Joined","73922":"Rejected"},calls))
    assert r["programmes"][0]["action"]=="REVIEW_JOINED_PROGRAMME_TERMS_AND_TRACKING_AUTHORISATION"
    assert r["programmes"][1]["action"]=="REVIEW_REJECTION"
    assert r["any_joined"] is True
    assert r["tracking_links_generated"] is False
    assert not r["affiliate_publication_authorized"]
    assert not r["commission_paid_verified"]


@pytest.mark.parametrize("bad",["","Approved","cancelled",None,1])
def test_unknown_status_never_accepted(bad):
    with pytest.raises(AwinAPIHold):
        _normalise(response("122556",bad),"122556")


def test_wrong_programme_id_blocks_entire_cycle(tmp_path):
    calls=[]
    def wrong(url,token):
        calls.append(url)
        return response("99999","Joined")
    r=review(token_path=token(tmp_path/"token"),
             output=tmp_path/"out",now=NOW,write=True,transport=wrong)
    assert r["status"].startswith("HELD")
    assert len(calls)==1
    assert not (tmp_path/"out").exists()


def test_missing_programme_status_holds():
    with pytest.raises(AwinAPIHold):
        _normalise({"programmeInfo":{"id":73922}},"73922")


def test_symlink_or_insecure_credential_holds(tmp_path):
    src=token(tmp_path/"secret")
    src.chmod(0o644)
    with pytest.raises(AwinAPIHold):
        _private_token(src)
    src.chmod(0o600)
    link=tmp_path/"link"
    link.symlink_to(src)
    with pytest.raises(AwinAPIHold):
        _private_token(link)


def test_tampered_old_snapshot_prevents_write(tmp_path):
    dest=tmp_path/"snapshot"
    dest.write_text("earlier")
    dest.chmod(0o644)
    r=review(token_path=token(tmp_path/"token"),
             output=dest,now=NOW,write=True,
             transport=transport({"122556":"Joined","73922":"Pending"},[]))
    assert r["status"].startswith("HELD")
    assert dest.read_text()=="earlier"


def test_failed_second_call_does_not_write_partial_state(tmp_path):
    calls=[]
    def fail(url,secret):
        calls.append(1)
        if len(calls)==2:
            raise AwinAPIHold("controlled")
        return response("122556","Joined")
    r=review(token_path=token(tmp_path/"token"),output=tmp_path/"out",
             now=NOW,write=True,transport=fail)
    assert r["status"].startswith("HELD")
    assert len(calls)==2
    assert not (tmp_path/"out").exists()


def test_idempotent_private_snapshot(tmp_path):
    cred=token(tmp_path/"token")
    output=tmp_path/"out"
    supplier=transport({"122556":"Pending","73922":"Joined"},[])
    a=review(token_path=cred,output=output,now=NOW,write=True,transport=supplier)
    previous=output.read_bytes()
    b=review(token_path=cred,output=output,now=NOW,write=True,transport=supplier)
    assert a["status"]==b["status"]=="AWIN_API_MEMBERSHIP_REVIEW_VERIFIED"
    assert output.read_bytes()==previous
    assert all(not x["publisher_authorised_to_use_tracking_link"] for x in b["programmes"])



def test_first_membership_snapshot_is_baseline_not_transition(tmp_path):
    path=tmp_path/"membership.json"
    supplier=transport({"122556":"Pending","73922":"Pending"},[])
    first=review(token_path=token(tmp_path/"secret"),output=path,write=True,
                 transport=supplier,now=NOW)
    assert first["status"]=="AWIN_API_MEMBERSHIP_REVIEW_VERIFIED"
    assert first["new_status_transition_count"]==0
    assert first["historical_status_transition_count"]==0
    assert first["status_transitions"]==[]


def test_real_joined_change_once_and_retained_on_repeat(tmp_path):
    path=tmp_path/"snapshot"
    cred=token(tmp_path/"secret")
    first=review(token_path=cred,output=path,write=True,now=NOW,
                 transport=transport({"122556":"Pending","73922":"Pending"},[]))
    assert first["new_status_transition_count"]==0
    joined={"122556":"Joined","73922":"Pending"}
    changed=review(token_path=cred,output=path,write=True,now=NOW,
                   transport=transport(joined,[]))
    assert changed["new_status_transition_count"]==1
    assert changed["historical_status_transition_count"]==1
    assert changed["transition_review_required"] is True
    event=changed["status_transitions"][0]
    assert event["advertiser_id"]=="122556"
    assert event["from_status"]=="PENDING" and event["to_status"]=="JOINED"
    assert event["required_action"]=="REVIEW_JOINED_PROGRAMME_TERMS_AND_TRACKING_AUTHORISATION"
    assert event["review_status"]=="REVIEW_NOT_YET_ADMITTED"
    assert not event["affiliate_publication_authorized"]
    again=review(token_path=cred,output=path,write=True,now=NOW,
                 transport=transport(joined,[]))
    assert again["new_status_transition_count"]==0
    assert again["historical_status_transition_count"]==1
    assert again["status_transitions"]==changed["status_transitions"]
    assert not again["affiliate_publication_authorized"]


def test_two_independent_rejections_and_suspensions(tmp_path):
    path=tmp_path/"snapshot"
    cred=token(tmp_path/"secret")
    review(token_path=cred,output=path,write=True,now=NOW,
           transport=transport({"122556":"Pending","73922":"Pending"},[]))
    new=review(token_path=cred,output=path,write=True,now=NOW,
               transport=transport({"122556":"Rejected","73922":"Suspended"},[]))
    assert new["new_status_transition_count"]==2
    assert [(x["advertiser_id"],x["required_action"]) for x in new["status_transitions"]]==[
        ("122556","REVIEW_REJECTION"),("73922","REVIEW_SUSPENSION")]
    assert new["commission_earned_verified"] is False


def test_old_v1_snapshot_migrates_without_fabricated_events(tmp_path):
    path=tmp_path/"snapshot"
    cred=token(tmp_path/"secret")
    review(token_path=cred,output=path,write=True,now=NOW,
           transport=transport({"122556":"Pending","73922":"Pending"},[]))
    legacy=json.loads(path.read_text())
    legacy.pop("status_transitions")
    legacy.pop("new_status_transition_count")
    legacy.pop("historical_status_transition_count")
    legacy.pop("transition_review_required")
    path.write_text(json.dumps(legacy));path.chmod(0o600)
    newest=review(token_path=cred,output=path,write=True,now=NOW,
                  transport=transport({"122556":"Pending","73922":"Pending"},[]))
    assert newest["new_status_transition_count"]==0
    assert newest["historical_status_transition_count"]==0
    assert len(newest["programmes"])==2


def test_corrupt_existing_history_kept_unchanged(tmp_path):
    path=tmp_path/"snapshot"
    cred=token(tmp_path/"secret")
    review(token_path=cred,output=path,write=True,now=NOW,
           transport=transport({"122556":"Pending","73922":"Pending"},[]))
    existing=json.loads(path.read_text())
    existing["affiliate_publication_authorized"]=True
    path.write_text(json.dumps(existing)); path.chmod(0o600)
    original=path.read_bytes()
    r=review(token_path=cred,output=path,write=True,now=NOW,
             transport=transport({"122556":"Joined","73922":"Pending"},[]))
    assert r["status"].startswith("HELD_")
    assert r["requests_made"]==0
    assert path.read_bytes()==original


def test_rejects_future_previous_observation(tmp_path):
    path=tmp_path/"snapshot"
    cred=token(tmp_path/"secret")
    review(token_path=cred,output=path,write=True,now=NOW,
           transport=transport({"122556":"Pending","73922":"Pending"},[]))
    existing=json.loads(path.read_text())
    existing["observed_at"]="2026-10-29T00:00:00+00:00"
    path.write_text(json.dumps(existing));path.chmod(0o600)
    r=review(token_path=cred,output=path,write=True,now=NOW,
             transport=transport({"122556":"Joined","73922":"Pending"},[]))
    assert r["status"].startswith("HELD_")
    assert r["requests_made"]==0


def test_history_capacity_fails_without_data_loss(tmp_path):
    path=tmp_path/"snapshot"
    cred=token(tmp_path/"secret")
    review(token_path=cred,output=path,write=True,now=NOW,
           transport=transport({"122556":"Pending","73922":"Pending"},[]))
    previous=json.loads(path.read_text())
    previous["status_transitions"]=[
        {"event_id":f"{i:024x}","advertiser_id":"122556",
         "from_status":"PENDING","to_status":"JOINED",
         "review_required":True,"review_status":"REVIEW_NOT_YET_ADMITTED"}
        for i in range(80)]
    path.write_text(json.dumps(previous));path.chmod(0o600)
    old=path.read_bytes()
    r=review(token_path=cred,output=path,write=True,now=NOW,
             transport=transport({"122556":"Joined","73922":"Pending"},[]))
    assert r["status"].startswith("HELD_")
    assert path.read_bytes()==old


def test_missing_old_snapshot_when_no_write_does_not_create_event(tmp_path):
    p=tmp_path/"snapshot"
    cred=token(tmp_path/"secret")
    r=review(token_path=cred,output=p,write=False,now=NOW,
             transport=transport({"122556":"Joined","73922":"Joined"},[]))
    assert r["new_status_transition_count"]==0
    assert r["status_transitions"]==[]
    assert not p.exists()
