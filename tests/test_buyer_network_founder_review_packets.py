from importlib.util import (
    module_from_spec,
    spec_from_file_location,
)
from pathlib import Path


PATH = Path(
    "scripts/materialize_buyer_network_founder_review_packets.py"
)


def module():

    spec = spec_from_file_location(
        "buyer_review",
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


def test_real_domain():

    assert module().valid_domain(
        "leadsmartinc.com"
    )


def test_internal_domain():

    assert not module().valid_domain(
        "empire.buyer"
    )


def test_search_tool():

    assert not module().valid_domain(
        "semrush.com"
    )


def test_genuine_buyer_role():

    mod = module()

    assert mod.genuine(
        {
            "evidence": {
                "publisher_program":
                    True,

                "active_demand":
                    True,

                "integration":
                    True,

                "negative_program":
                    False,
            }
        }
    )


def test_tooling_only_not_genuine():

    mod = module()

    assert not mod.genuine(
        {
            "evidence": {
                "integration":
                    True,

                "economics":
                    True,

                "contactable":
                    True,
            }
        }
    )


def test_report_packet_domain_gate_does_not_admit_placeholder_or_telemetry():
    mod = module()
    for domain in ("yoursite.com", "company.com", "insider.com",
                   "o4509242520240129.ingest.us.sentry.io"):
        assert mod.valid_domain(domain) is False


def test_durable_first_party_evidence_survives_transient_discovery_refresh():
    from datetime import datetime,timezone
    from empire_os.buyer_network_research_rotation import RESULT_TTL_SECONDS
    mod=module()
    now=datetime(2026,10,26,16,30,tzinfo=timezone.utc).timestamp()
    site={
        "schema_version":"buyer-direct-site-verification-v1",
        "authority":"OBSERVE",
        "generated_epoch":now,
        "governance":{"outbound":False,"traffic_activation":False,"commercial_terms":False},
        "results":[{
            "domain":"polyares.com",
            "observed_epoch":now-10,
            "corroborated":True,"buyer_role":True,
            "pages_successful":2,"positive_category_count":4,
            "evidence":{"publisher_program":True,"active_demand":True,"negative_program":False},
        }],
    }
    assert mod.active_verified_domains({"runs":[]},site,now_epoch=now)=={"polyares.com"}
    assert mod.active_verified_domains({"runs":[]},site,now_epoch=now+RESULT_TTL_SECONDS+1)==set()
    bad={**site,"governance":{"outbound":True,"traffic_activation":False,"commercial_terms":False}}
    assert mod.active_verified_domains({"runs":[]},bad,now_epoch=now)==set()
    bad={**site,"results":[{**site["results"][0],"corroborated":False}]}
    assert mod.active_verified_domains({"runs":[]},bad,now_epoch=now)==set()
    bad={**site,"results":[{**site["results"][0],"buyer_role":False}]}
    assert mod.active_verified_domains({"runs":[]},bad,now_epoch=now)==set()
    bad={**site,"results":[{**site["results"][0],"observed_epoch":now-RESULT_TTL_SECONDS-1}]}
    assert mod.active_verified_domains({"runs":[]},bad,now_epoch=now)==set()
    bad={**site,"results":site["results"]*2}
    assert mod.active_verified_domains({"runs":[]},bad,now_epoch=now)==set()


def test_temporary_discovery_entries_require_real_approved_first_party_owner():
    mod=module()
    good={"status":"PASS","verification_source":"direct-site",
          "query":"buyer-network-active-verification",
          "domains":["verifiedpublisher.com"]}
    assert mod.active_verified_domains({"runs":[good]})=={"verifiedpublisher.com"}
    for bad in [
        {**good,"verification_source":"search"},
        {**good,"status":"HOLD"},
        {**good,"domains":["verifiedpublisher.com","unknownbuyer.com"]},
    ]:
        assert mod.active_verified_domains({"runs":[bad]})==set()
