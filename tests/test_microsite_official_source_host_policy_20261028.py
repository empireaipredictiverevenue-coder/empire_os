"""Government source link host allowlist across original non-Chicago market anchors."""
import json
from pathlib import Path

import pytest

from empire_os.predictive_microsite_factory import build_candidate


def original_uk_candidate():
    sample=Path(__file__).parent / "fixtures/predictive_microsite_factory_sample_20261026.json"
    spec=json.loads(sample.read_text())["candidates"][1]
    assert spec["geography"]["market_id"]=="GB-MAN"
    return spec


@pytest.mark.parametrize("url", [
    "https://www.gov.uk/energy-efficiency",
    "https://www.manchester.gov.uk/",
    "https://find-energy-certificate.service.gov.uk/",
    "https://www.ofgem.gov.uk/",
])
def test_genuine_uk_government_hosts_allowed_for_uk_research_drafts(url):
    spec=original_uk_candidate()
    spec["local_facts"][0]["official_url"]=url
    packet,html=build_candidate(spec)
    assert packet["market"]["country_code"]=="GB"
    assert packet["linked_official_source_count"]==1
    assert url in html
    assert packet["publishing_enabled"] is False
    assert packet["source_claims_independently_confirmed_by_site_owner"] is False
    assert packet["indexation_enabled"] is False
    assert packet["outbound_enabled"] is False


@pytest.mark.parametrize("url", [
    "https://www.gov.uk.evil.example/guide",
    "https://manchester.gov.uk.fake.example/research",
    "https://notgov.uk/guide",
    "https://www.gov.com/guide",
    "https://example.com/guide",
    "http://www.gov.uk/research",
    "https://www.gov.uk:444/research",
    "https://user@www.gov.uk/research",
    "https://www.gov.uk/research?utm_source=bad",
    "https://www.gov.uk/research#fake",
    "javascript:alert(1)",
])
def test_fake_or_unbounded_uk_official_sources_rejected(url):
    spec=original_uk_candidate()
    spec["local_facts"][0]["official_url"]=url
    with pytest.raises(ValueError,match="approved government host"):
        build_candidate(spec)


def test_cross_country_government_sources_rejected():
    spec=original_uk_candidate()
    spec["local_facts"][0]["official_url"]="https://www.energy.gov/"
    with pytest.raises(ValueError,match="approved government host"):
        build_candidate(spec)


def test_other_us_markets_accept_gov_but_not_uk_domains():
    spec=original_uk_candidate()
    spec["geography"]={
        "market_id":"US-CO","kind":"metro","area":"Denver, CO",
        "evidence_refs":["geo_registry:US-CO"]
    }
    spec["keyword_opportunity"]["territory_key"]="US-CO"
    spec["local_facts"][0]["official_url"]="https://www.energy.gov/"
    packet,_=build_candidate(spec)
    assert packet["linked_official_source_count"]==1
    assert packet["market"]["country_code"]=="US"
    spec["local_facts"][0]["official_url"]="https://www.gov.uk/"
    with pytest.raises(ValueError,match="approved government host"):
        build_candidate(spec)
