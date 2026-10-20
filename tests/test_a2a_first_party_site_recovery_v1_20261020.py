"""External public website fetcher is strictly allowlisted, bounded and observe-only."""
from copy import deepcopy
from datetime import datetime, timezone

import pytest
from empire_os.a2a_first_party_site_recovery_v1 import (
    collect_approved_first_party_sites, _parse_site, _public_dns_only,
)
from empire_os.a2a_first_party_site_recovery_v1 import SCHEMA


NOW = datetime(2026,10,20,12,tzinfo=timezone.utc)
def sample():
    return {
        "schema_version":"empire.a2a.approved_first_party_business_sites.v1",
        "mode":"OBSERVE","activation":"LIVE_READONLY_BY_EXPLICIT_OPERATOR_ACTION",
        "send_messages":False,"assume_buyer_intent":False,
        "no_private_contacts":True,"budget_usd":0,
        "sites":[{"market":"tampa, fl","niche":"roofing","url":"https://roofer.example/","source_type":"FIRST_PARTY_PUBLIC_SITE"}],
    }

class Response:
    def __init__(self,status_code,body=b"",mime="text/html"):
        self.status_code=status_code
        self.body=body
        self.headers={"Content-Type":mime}
    def iter_content(self,chunk_size=16384):
        yield self.body
    def close(self):pass

class Session:
    def __init__(self,robot=404,body=b"Roofing contractor proudly serving Tampa Bay Florida"):
        self.robot=robot;self.body=body;self.calls=[]
    def get(self,url,**kwargs):
        self.calls.append((url,kwargs))
        if url.endswith("/robots.txt"):
            return Response(self.robot, b"User-agent: *\nDisallow: /\n" if self.robot==200 else b"")
        return Response(200,self.body)

def fake_dns(*a,**k):
    return [(None,None,None,None,("93.184.215.14",443))]

def test_real_shape_reads_one_company_site_without_contact_or_buyer():
    ss=Session()
    v=collect_approved_first_party_sites(sample(),session=ss,dns_resolve=fake_dns,now=NOW)
    assert v["schema_version"]==SCHEMA
    assert v["websites_http_200"]==1
    assert v["self_described_sector_and_region_matches"]==1
    assert len(ss.calls)==2
    assert all(x[1]["allow_redirects"] is False and x[1]["stream"] is True for x in ss.calls)
    row=v["records"][0]
    assert row["source_body_sha256"] is not None
    assert not row["actual_buyer_intent"]
    assert not row["contact_authorised"]
    assert v["buyers_verified"]==0


def test_robots_disallow_blocks_page_fetch():
    ss=Session(robot=200)
    v=collect_approved_first_party_sites(sample(),session=ss,dns_resolve=fake_dns,now=NOW)
    assert len(ss.calls)==1
    assert v["websites_http_200"]==0
    assert v["records"][0]["site_fetch_status"]=="ROBOTS_POLICY_HOLD"


def test_redirect_or_network_error_is_hold():
    ss=Session()
    ss.get=lambda *args,**kwargs: Response(302)
    v=collect_approved_first_party_sites(sample(),session=ss,dns_resolve=fake_dns,now=NOW)
    assert v["records"][0]["robots_policy"]=="ROBOTS_UNAVAILABLE_HOLD"
    assert not v["records"][0]["self_described_sector_matched"]


def test_private_dns_and_malicious_host_rejected():
    with pytest.raises(ValueError,match="NON_PUBLIC"):
        _public_dns_only("roofer.example",
            lambda *a: [(None,None,None,None,("127.0.0.1",443))])
    assert _parse_site("https://roofer.example/")==("roofer.example","https://roofer.example/")
    for bad in ("http://roofer.example/","https://roofer.example:8080/",
                "https://u:pass@roofer.example/","https://localhost/",
                "https://roofer.example/contact","https://roofer.example/?x=1"):
        with pytest.raises(ValueError,match="UNSAFE"):
            _parse_site(bad)


def test_authority_and_scope_modification_rejected():
    for k,v in (("send_messages",True),("assume_buyer_intent",True),
                ("budget_usd",5),("activation","UNRESTRICTED")):
        spec=sample();spec[k]=v
        with pytest.raises(ValueError,match="UNTRUSTED"):
            collect_approved_first_party_sites(spec,session=Session(),
                                               dns_resolve=fake_dns,now=NOW)
    spec=sample();spec["sites"][0]["market"]="miami, fl"
    with pytest.raises(ValueError,match="UNAPPROVED"):
        collect_approved_first_party_sites(spec,session=Session(),
                                           dns_resolve=fake_dns,now=NOW)


def test_dedupe_and_max_sites_enforced():
    spec=sample()
    spec["sites"].append(deepcopy(spec["sites"][0]))
    with pytest.raises(ValueError,match="DUPLICATE"):
        collect_approved_first_party_sites(spec,session=Session(),
                                           dns_resolve=fake_dns,now=NOW)
    with pytest.raises(ValueError,match="LIMIT"):
        collect_approved_first_party_sites(sample(),session=Session(),
                                           dns_resolve=fake_dns,now=NOW,max_sites=80)
