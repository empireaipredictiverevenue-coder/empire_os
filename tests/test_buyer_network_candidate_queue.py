from importlib.util import (
    module_from_spec,
    spec_from_file_location,
)
from pathlib import Path


PATH = Path(
    "scripts/materialize_buyer_network_candidate_queue.py"
)


def module():

    spec = spec_from_file_location(
        "buyer_candidate_queue",
        PATH,
    )

    mod = module_from_spec(
        spec
    )

    assert spec.loader is not None

    spec.loader.exec_module(
        mod
    )

    return mod


def test_file_exists():

    assert PATH.exists()


def test_domain_normalisation():

    mod = module()

    assert (
        mod.normalize_domain(
            "https://www.example.com/publishers"
        )
        == "example.com"
    )


def test_negative_evidence_rejects():

    mod = module()

    profile = {
        "verticals":
            {"roofing"},

        "queries":
            {"roofing buyers"},

        "runs":
            1,

        "evidence_lines": [
            "example.com publisher program closed",
        ],
    }

    result = mod.score_profile(
        "example.com",
        profile,
        set(),
    )

    assert (
        result["status"]
        == "REJECT"
    )


def test_search_presence_alone_not_ready():

    mod = module()

    profile = {
        "verticals":
            {"roofing"},

        "queries":
            {"roofing buyers"},

        "runs":
            1,

        "evidence_lines": [
            "https://example.com",
        ],
    }

    result = mod.score_profile(
        "example.com",
        profile,
        set(),
    )

    assert (
        result["status"]
        != "READY_TO_APPROACH"
    )


def test_strong_evidence_can_be_ready():

    mod = module()

    profile = {
        "verticals":
            {"roofing"},

        "queries":
            {
                "roofing publisher program",
                "buyer-network-active-verification",
            },

        "runs":
            1,

        "evidence_lines": [
            (
                "example.com publishers pay per call "
                "payout API TCPA contact"
            ),
        ],
    }

    result = mod.score_profile(
        "example.com",
        profile,
        set(),
    )

    assert (
        result["status"]
        == "READY_TO_APPROACH"
    )


def test_failed_search_cycle_never_erases_previous_queue(tmp_path):
    import json
    import pytest
    mod = module()
    broken = tmp_path / "discovery.json"
    broken.write_text(json.dumps({"schema_version":"buyer-network-discovery-v1",
                                  "runs":[{"query":"roofing publishers","status":"HOLD"}]}))
    prior = tmp_path / "candidate_queue_latest.json"
    previous = '{"known_good_queue":"preserved"}\n'
    prior.write_text(previous)
    mod.DISCOVERY = broken
    mod.OUTPUT = prior
    with pytest.raises(RuntimeError, match="DISCOVERY_UNAVAILABLE_PRESERVE_EXISTING_BUYER_QUEUE"):
        mod.main()
    assert prior.read_text() == previous


def test_exact_single_domain_first_party_run_recovers_evidence_without_domain_in_body():
    mod = module()
    verified = {
        "status": "PASS",
        "verification_source": "direct-site",
        "query": "buyer-network-active-verification",
        "vertical": "roofing",
        "domains": ["brokercalls.com"],
        "stdout_tail": (
            "Home Services | Pay Per Call Publisher Program. "
            "We buy roofing leads from publishers. "
            "Partner payout tracking, TCPA compliance, contact."
        ),
    }
    profiles = mod.collect_domain_context({"runs": [verified]})
    assert "brokercalls.com" in profiles
    profile = profiles["brokercalls.com"]
    assert "publisher program" in " ".join(profile["evidence_lines"]).lower()
    assert len(profile["evidence_lines"]) == 1
    assessed = mod.score_profile("brokercalls.com", profile, set())
    assert assessed["status"] in ("READY_TO_APPROACH", "VERIFY_REQUIREMENTS")
    assert "outbound_authorized" not in assessed  # contact gate owns that decision


def test_unbound_or_multi_domain_search_text_not_attributed_as_first_party():
    mod = module()
    base = {
        "status": "PASS",
        "query": "buyer-network-active-verification",
        "vertical": "roofing",
        "domains": ["vendor-a.com"],
        "stdout_tail": "Publisher program pay per call roofing leads contact",
    }
    for updates in (
        {"verification_source": "search-result"},
        {"verification_source": "direct-site", "domains": ["vendor-a.com", "vendor-b.com"]},
        {"verification_source": "direct-site", "status": "FAILED"},
        {"verification_source": "direct-site", "query": "unverified-query"},
    ):
        row = {**base, **updates}
        rows = mod.collect_domain_context({"runs": [row]})
        assert rows["vendor-a.com"]["evidence_lines"] == []
    official = {**base, "verification_source": "direct-site"}
    assert mod.collect_domain_context({"runs": [official]})["vendor-a.com"]["evidence_lines"]


def test_durable_first_party_site_snapshot_outlives_empty_discovery():
    from datetime import datetime,timezone
    mod=module()
    now=datetime.now(timezone.utc).timestamp()
    site={
        'schema_version':'buyer-direct-site-verification-v1',
        'authority':'OBSERVE',
        'generated_epoch':now,
        'governance':{'outbound':False,'traffic_activation':False,'commercial_terms':False},
        'results':[{
            'domain':'brokerresearch.com','corroborated':True,
            'buyer_role':True,'observed_epoch':now,
            'positive_category_count':4,'pages_successful':2,
            'verticals_detected':['roofing'],
            'evidence':{'publisher_program':True,'active_demand':True,'negative_program':False},
            'snippets':[{'url':'https://brokerresearch.com/publishers',
                'text':'We buy roofing calls. Publisher program. Compliance and contact.'}],
        }],
    }
    profiles=mod.collect_domain_context({'runs':[]},site)
    assert 'brokerresearch.com' in profiles
    profile=profiles['brokerresearch.com']
    assert 'buyer-network-active-verification' in profile['queries']
    assert 'roofing' in profile['verticals']
    assert len(profile['evidence_lines'])==1
    assert mod.score_profile('brokerresearch.com',profile,set())['status']!='REJECT'
    site['results'][0]['snippets']=[
        {'url':'https://othercompany.com','text':'Pay per call publisher programme'}]
    assert 'brokerresearch.com' not in mod.collect_domain_context({'runs':[]},site)


def test_durable_sites_require_current_source_owner_and_no_unrelated_snippets():
    from datetime import datetime,timezone
    from empire_os.buyer_network_research_rotation import (
        RESULT_TTL_SECONDS,verified_first_party_snapshot_results,
    )
    now=datetime.now(timezone.utc).timestamp()
    base={
        'schema_version':'buyer-direct-site-verification-v1',
        'authority':'OBSERVE',
        'generated_epoch':now,
        'governance':{'outbound':False,'traffic_activation':False,'commercial_terms':False},
        'results':[{'domain':'brokerresearch.com','corroborated':True,
           'buyer_role':True,'observed_epoch':now,
           'positive_category_count':3,'pages_successful':1,
           'evidence':{'active_demand':True,'negative_program':False}}],
    }
    assert 'brokerresearch.com' in verified_first_party_snapshot_results(base,now_epoch=now)
    assert not verified_first_party_snapshot_results(
        {**base,'generated_epoch':now-RESULT_TTL_SECONDS-1},now_epoch=now)
    assert not verified_first_party_snapshot_results(
        {**base,'governance':{**base['governance'],'outbound':True}},now_epoch=now)
    assert not verified_first_party_snapshot_results(
        {**base,'results':base['results']*2},now_epoch=now)
