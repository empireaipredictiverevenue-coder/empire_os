from importlib.util import (
    module_from_spec,
    spec_from_file_location,
)
from pathlib import Path


PATH = Path(
    "scripts/probe_buyer_network_direct_sites.py"
)


def module():

    spec = spec_from_file_location(
        "direct_buyer_probe",
        PATH,
    )

    mod = module_from_spec(
        spec
    )

    assert spec.loader is not None

    spec.loader.exec_module(mod)

    return mod


def test_real_domains_allowed():

    mod = module()

    assert mod.valid_domain(
        "leadsmartinc.com"
    )

    assert mod.valid_domain(
        "callflowmarket.com"
    )


def test_pseudo_domains_rejected():

    mod = module()

    assert not mod.valid_domain(
        "revenue.erv"
    )

    assert not mod.valid_domain(
        "alan.nalle"
    )

    assert not mod.valid_domain(
        "revenue.lead"
    )


def test_internal_and_tooling_rejected():

    mod = module()

    assert not mod.valid_domain(
        "empire.buyer"
    )

    assert not mod.valid_domain(
        "semrush.com"
    )

    assert not mod.valid_domain(
        "aol.com"
    )


def test_buyer_evidence():

    mod = module()

    result = mod.evidence(
        "Become a publisher. "
        "We run pay-per-call campaigns. "
        "Contact us to get started."
    )

    assert result[
        "publisher_program"
    ]

    assert result[
        "active_demand"
    ]

    assert result[
        "contactable"
    ]


def test_generic_marketing_not_buyer_evidence():

    mod = module()

    result = mod.evidence(
        "We are a digital marketing agency "
        "helping companies grow online."
    )

    assert not result[
        "publisher_program"
    ]

    assert not result[
        "active_demand"
    ]


def test_probe_is_bounded():

    mod = module()

    assert mod.MAX_CANDIDATES <= 8
    assert len(mod.PATHS) <= 8
    assert mod.TIMEOUT <= 8


def test_publisher_first_site_probe_fetches_exact_official_page_without_sprawl():
    mod=module()
    from empire_os.buyer_public_research_seed import publisher_review_page_path
    expected={
        "elocal.com":"/affiliate-contact",
        "polyares.com":"/pay-per-call-affiliate-program",
        "homevantaleadgroup.com":"/for-affiliates",
        "joinglobalwiz.com":"/affiliates",
    }
    assert {domain:publisher_review_page_path(domain) for domain in expected}==expected
    assert publisher_review_page_path("leadsmartinc.com") is None
    assert publisher_review_page_path("in.linkedin.com") is None
    called=[]
    def fake_fetch(host,path):
        called.append((host,path))
        return {
            "url":f"https://{host}{path}",
            "final_url":f"https://{host}{path}",
            "status":"PASS","http_status":200,
            "text":"Become a publisher. Pay per call. Contact us. Roofing.",
        }
    mod.public_dns_only=lambda domain: True
    mod.fetch_one=fake_fetch
    for domain,path in expected.items():
        called.clear()
        out=mod.probe_candidate({"domain":domain,"status":"VERIFY_REQUIREMENTS"})
        assert out["pages_attempted"]==len(mod.PATHS)+1
        assert called.count((domain,path))==1
        assert len({p for _,p in called})==len(mod.PATHS)+1
        assert out["buyer_role"] is True
        assert out["corroborated"] is True
        assert out["evidence"]["publisher_program"] is True
    called.clear()
    out=mod.probe_candidate({"domain":"leadsmartinc.com","status":"VERIFY_REQUIREMENTS"})
    assert out["pages_attempted"]==len(mod.PATHS)
    assert len(called)==len(mod.PATHS)
