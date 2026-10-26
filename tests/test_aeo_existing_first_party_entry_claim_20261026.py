"""Original approved AEO source hints: consented claims, not verified SEO."""
from pathlib import Path
from datetime import datetime,timezone
from subprocess import check_output
from importlib.util import spec_from_file_location,module_from_spec
import pytest
from empire_os.first_party_sales_interest import (
    REVIEWED_ENTRY_PATHS, CommercialInterestError, record_founder_led_interest,
)
ROOT=Path(__file__).resolve().parents[1]
AEO={
    ("general_contractor","NYC"):"/aeo/general_contractor/NYC/",
    ("hvac","DFW"):"/aeo/hvac/DFW/",
    ("roofing","DFW"):"/aeo/roofing/DFW/",
}

def test_exact_source_allowlist_only_three_original_aeo_guides():
    assert {r for r in REVIEWED_ENTRY_PATHS if r.startswith('/aeo/')}==set(AEO.values())
    for s in ('/aeo/general_contractor/SF/','/aeo/roofing/NYC/','/aeo/roofing/DFW',
              '/aeo/hvac/DFW/?utm_source=google','https://empire-ai.co.uk/aeo/hvac/DFW/',
              '/aeo/roofing/DFW/#other'):
        assert s not in REVIEWED_ENTRY_PATHS

def test_founder_enquiry_exact_claim_still_unverified_and_consent_bounded(tmp_path):
    for path in AEO.values():
        calls=[]
        def capture(verb,endpoint,*,payload):
            calls.append(payload)
            return {"decision":"created","prospect":{"id":"stub-only"}}
        record=record_founder_led_interest(
            root=tmp_path,request=capture,
            product_code="consultancy_opportunity_assessment",
            business_name="Business Ltd",email="test@example.test",
            domain="example.test",industry="Professional services",
            geography="United Kingdom",desired_outcome="Review qualified B2B opportunities.",
            contact_consent=True,idempotency_key="a-test-unique-id-20261026",
            claimed_entry_page=path,now=datetime(2026,10,26,tzinfo=timezone.utc),
        )
        assert record["decision"]=="commercial_enquiry_recorded"
        assert record["actual_revenue"] is False
        assert len(calls)==1
        proof=calls[0]["p_evidence"]["claimed_entry_page_review"]
        assert proof["path"]==path
        assert proof["source"]=="UNVERIFIED_BROWSER_SUBMITTED"
        for key in ("organic_search_attributed","search_click_proven",
                    "qualified_buyer_proven","recognized_revenue_proven"):
            assert proof[key] is False
        assert calls[0]["p_evidence"]["outreach_authority"]=="none"

def test_no_consent_does_not_record_or_accept_source(tmp_path):
    for path in AEO.values():
        with pytest.raises(CommercialInterestError,match="specific_contact_consent_required"):
            record_founder_led_interest(
                root=tmp_path, request=lambda *args,**kwargs: pytest.fail("unexpected database"),
                product_code="consultancy_opportunity_assessment",
                business_name="Example Ltd",email="test@example.test",domain="example.test",
                industry="Professional services",geography="UK",
                desired_outcome="Need a scoped consultation on inbound revenue.",
                contact_consent=False,idempotency_key="unique-key-20261026",
                claimed_entry_page=path,
            )

def test_exact_three_original_generator_changes_and_no_mass_replication(tmp_path):
    target=ROOT/"scripts/aeo_metro_gen.py"
    newest=spec_from_file_location("new_aeo",target)
    new=module_from_spec(newest);newest.loader.exec_module(new)
    git=check_output(["git","-C",str(ROOT),"log","-1","--format=%H",
                      "--", "scripts/aeo_metro_gen.py"],text=True).strip()
    prev=check_output(["git","-C",str(ROOT),"show",git+":scripts/aeo_metro_gen.py"])
    p=tmp_path/"previous_aeo.py";p.write_bytes(prev)
    old_spec=spec_from_file_location("old_aeo",p)
    old=module_from_spec(old_spec);old_spec.loader.exec_module(old)
    changed=[]
    for niche in old.NICHE_INFO:
        for metro in old.METROS:
            before=old.generate_page(niche,metro)
            after=new.generate_page(niche,metro)
            if before!=after:
                assert (niche,metro) in AEO
                original='href="/commercial"'
                replacement='href="/commercial?entry=%2Faeo%2F'+niche+'%2F'+metro+'%2F#commercial-enquiry"'
                assert before.count(original)==1
                assert after.count(replacement)==1
                assert after.replace(replacement,original,1)==before
                changed.append((niche,metro))
    assert set(changed)==set(AEO)
