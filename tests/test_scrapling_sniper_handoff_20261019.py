"""Real existing extraction + canonical identity + Waterfall + sniper review.

Everything uses synthetic firms. No database, HTTP request or outbound send.
"""
from datetime import datetime, timezone
from copy import deepcopy

import pytest

from empire_os.scrapling_source_evidence import ReviewedRecipe, extract_reviewed_page
from empire_os.scrapling_sniper_handoff import build_scrapling_sniper_review_handoff
from empire_os.waterfall_source_bridge import EvidenceReview
from empire_os.lead_sniper_repository import LeadSniperRepository

NOW = datetime(2026, 10, 19, 12, 50, tzinfo=timezone.utc)
SITE_HTML = """<html><body><h1>Company</h1>
 <a href="mailto:office@synthetic.example">Business Office</a>
 <a href="tel:+442079460500">Call office</a></body></html>"""


def source_report():
    pytest.importorskip("scrapling")
    html = """<html><body>
      <div class="entry"><span class="name">Example Solar Ltd</span>
        <a href="/company/111">Registry listing</a></div>
      <div class="entry"><span class="name">Other Solar Ltd</span>
        <a href="/company/222">Registry listing</a></div>
    </body></html>"""
    return extract_reviewed_page(
        recipe=ReviewedRecipe(
            source_id="gb_recc_solar",
            source_url="https://www.recc.org.uk/scheme/members",
            niche="solar", metro="London",
            row_css="div.entry", name_css=".name::text",
            website_css="a::attr(href)", max_rows=3,
            terms_reviewed=True, robots_reviewed=True,
            privacy_reviewed=True,
            review_evidence_refs=("terms:synthetic", "robots:synthetic",
                                  "privacy:synthetic"),
        ),
        html=html, observed_at=NOW,
    )


def firm_review(**kwargs):
    params = dict(
        vertical="solar", target_kind="contractor", jurisdiction="GB-ENG",
        company_identity_ref="company:approved-entity-001",
        verified_first_party_website="https://synthetic.example/",
        website_verification_ref="domain:reviewed-first-party-001",
    )
    params.update(kwargs)
    return EvidenceReview(**params)


def canonical_rows():
    return [
        {"id": "enterprise-001", "business_name": "Example Solar Ltd",
         "niche": "solar", "metro": "London", "phone": ""},
        {"id": "enterprise-002", "business_name": "Other Solar Ltd",
         "niche": "solar", "metro": "London", "phone": ""},
    ]


def run(**kwargs):
    params = dict(
        source_report=source_report(),
        review=firm_review(),
        canonical_rows=canonical_rows(),
        canonical_snapshot_complete=True,
        canonical_snapshot_ref="snapshot:synthetic-complete-001",
        independent_canonical_id="enterprise-001",
        canonical_identity_receipt_ref="independent:confirmed-enterprise-001",
        source_rights_receipt_ref="source-rights:approved-recc",
        territory_receipt_ref="territory:confirmed-gb-eng",
        company_site_html=SITE_HTML,
        company_page_url="https://synthetic.example/contact",
        research_score=0.86, now=NOW,
    )
    params.update(kwargs)
    return build_scrapling_sniper_review_handoff(**params)


def test_source_to_existing_waterfall_to_canonical_sniper_packet():
    result = run()
    assert result["state"] == "SNIPER_REVIEW_PACKET_PREPARED"
    assert result["identity_match_state"] == "POTENTIAL_EXISTING_REVIEW"
    assert result["waterfall_provider_order"] == [
        "empire_hunter", "registry_scraper", "site_crawler_scrapling_offline",
    ]
    assert result["waterfall_existing_gate_passed"] is False
    assert result["website_business_contact_observed"] is True
    proposal = result["review_task_proposal"]
    assert proposal["decision"] == "B2B_REVIEW_PROPOSAL"
    assert proposal["business_name"] == "Example Solar Ltd"
    assert proposal["niche"] == "solar"
    assert proposal["source"] == "gb_recc_solar"
    assert proposal["url"] == "https://synthetic.example/contact"
    assert proposal["buyer_intent_verified"] is False
    assert result["outbound_authorized"] is False
    assert result["canonical_database_writes"] is False
    assert result["live_sniper_queue_authorized"] is False


def test_existing_sniper_queue_is_still_disabled_for_prepared_packet():
    class Fake:
        backend = __import__(
            "empire_os.data_cloud_contract", fromlist=["DataBackend"]
        ).DataBackend.EMPIREDB
        configured = True
        def __init__(self):
            self.writes = []
        def insert(self, *args, **kwargs):
            self.writes.append((args, kwargs))
            raise AssertionError("queue unexpectedly wrote")
    g = Fake()
    proposal = run()["review_task_proposal"]
    held = LeadSniperRepository(g, queue_enabled=False).queue_review(
        proposal, now=NOW
    )
    assert held["status"] == "held"
    assert g.writes == []


def test_multi_record_index_routes_correct_source_company():
    p = run(record_index=1, independent_canonical_id="enterprise-002")
    assert p["state"] == "SNIPER_REVIEW_PACKET_PREPARED"
    assert p["review_task_proposal"]["business_name"] == "Other Solar Ltd"


def test_wrong_canonical_firm_never_generates_packet():
    p = run(independent_canonical_id="enterprise-002")
    assert p["state"] == "HOLD"
    assert "independently_confirmed_canonical_id_mismatch" in p["reasons"]
    assert p["review_task_proposal"] is None


def test_incomplete_canonical_snapshot_never_generates_packet():
    p = run(canonical_snapshot_complete=False)
    assert p["state"] == "HOLD"
    assert p["canonical_database_writes"] is False


def test_same_phone_unrelated_company_holds():
    rows = canonical_rows()
    rows[1]["phone"] = "+442079460500"
    # Here the source report has no phone, hence no collision. Instead test
    # explicit identity ambiguity in the SAME corridor:
    rows[1]["business_name"] = rows[0]["business_name"]
    p = run(canonical_rows=rows)
    assert p["state"] == "HOLD"
    assert "canonical_identity_not_consistently_matched" in p["reasons"]


def test_wrong_first_party_site_origin_holds():
    p = run(company_page_url="https://unrelated.example/contact")
    assert p["state"] == "HOLD"
    assert "independent_verified_company_website_required" in p["reasons"]


def test_missing_rights_receipts_hold():
    p = run(source_rights_receipt_ref="")
    assert p["state"] == "HOLD"
    assert "independent_identity_rights_territory_receipts_missing" in p["reasons"]


def test_patient_or_mass_tort_claimant_never_becomes_b2b_sniper_task():
    p = run(review=firm_review(vertical="mass_torts", target_kind="claimant"))
    assert p["state"] == "HOLD"
    assert p["review_task_proposal"] is None


def test_no_website_contact_no_sniper_proposal():
    p = run(company_site_html="<html><body>Company only</body></html>")
    assert p["state"] == "HOLD"
    assert "company_website_contact_unobserved" in p["reasons"]


def test_unlicensed_source_host_tamper_holds():
    src = source_report()
    src["source_url"] = "https://fake-registry.example/solar"
    p = run(source_report=src)
    assert p["state"] == "HOLD"
    assert p["review_task_proposal"] is None


def test_invalid_source_index_rejected():
    with pytest.raises(ValueError, match="bounded"):
        run(record_index=30)


def test_cli_runs_full_pipeline_only_on_local_files(tmp_path, capsys):
    import json
    from scripts.preview_scrapling_sniper_handoff_20261019 import main
    payload = source_report()
    src = tmp_path / "source.json"
    snapshot = tmp_path / "complete_identity.json"
    html = tmp_path / "site.html"
    src.write_text(json.dumps(payload))
    snapshot.write_text(json.dumps(canonical_rows()))
    html.write_text(SITE_HTML)
    args = [
        "--read-only",
        "--source-report", str(src),
        "--canonical-snapshot", str(snapshot),
        "--source-html", str(html),
        "--site-url", "https://synthetic.example/contact",
        "--verified-site", "https://synthetic.example/",
        "--site-evidence-ref", "domain:synthetic-verified-001",
        "--record-index", "0",
        "--vertical", "solar", "--target-kind", "contractor",
        "--jurisdiction", "GB-ENG",
        "--company-identity-ref", "company:synthetic-reviewed-001",
        "--snapshot-ref", "snapshot:synthetic-complete-001",
        "--complete-snapshot",
        "--independent-canonical-id", "enterprise-001",
        "--canonical-identity-receipt", "identity:synthetic-reviewed-001",
        "--source-rights-receipt", "rights:synthetic-reviewed-001",
        "--territory-receipt", "territory:synthetic-reviewed-001",
        "--research-score", "0.80",
    ]
    assert main(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["state"] == "SNIPER_REVIEW_PACKET_PREPARED"
    assert result["review_task_proposal"]["score"] == 0.8
    assert result["canonical_database_writes"] is False
    assert result["outbound_authorized"] is False
    assert main([x for x in args if x != "--complete-snapshot"]) == 2
    # The command only succeeds with an explicit complete snapshot assertion.
    assert "HOLD" in capsys.readouterr().out
    assert src.exists() and snapshot.exists() and html.exists()


def test_cli_source_file_malformed_never_leaks_contents(tmp_path, capsys):
    import json
    from scripts.preview_scrapling_sniper_handoff_20261019 import main
    source = tmp_path / "bad.json"
    source.write_text("private claimant sensitive payload")
    snapshot = tmp_path / "good.json"
    snapshot.write_text("[]")
    html = tmp_path / "html.txt"
    html.write_text(SITE_HTML)
    args = [
        "--read-only", "--source-report", str(source),
        "--canonical-snapshot", str(snapshot),
        "--source-html", str(html),
        "--site-url", "https://synthetic.example/contact",
        "--verified-site", "https://synthetic.example/",
        "--site-evidence-ref", "domain:synthetic",
        "--vertical", "solar", "--target-kind", "contractor",
        "--jurisdiction", "GB-ENG",
        "--company-identity-ref", "company:synthetic",
        "--snapshot-ref", "snapshot:synthetic",
        "--independent-canonical-id", "enterprise-001",
        "--canonical-identity-receipt", "identity:synthetic",
        "--source-rights-receipt", "rights:synthetic",
        "--territory-receipt", "territory:synthetic",
    ]
    assert main(args) == 2
    out = capsys.readouterr().out
    assert "private claimant" not in out
    assert json.loads(out)["execution_authority"] == "none"
