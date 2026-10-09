from datetime import datetime, timezone
from empire_os.okf_adapter import documents_from_scout

NOW = datetime(2026, 10, 9, 17, tzinfo=timezone.utc)


def test_no_evidence_is_draft():
    d = documents_from_scout({"candidates": [
        {"website": "https://buyer.example", "domain": "buyer.example"},
    ]}, now=NOW)
    assert len(d) == 1
    assert "status: draft" in next(iter(d.values()))

from pathlib import Path
import yaml
from empire_os.okf_adapter import export_private_bundle


def test_okf_export_round_trip(tmp_path):
    import json
    source = tmp_path / "scout.json"
    source.write_text(json.dumps({"candidates": [
        {"website": "https://buyer.example", "domain": "buyer.example"}
    ]}))
    receipt = export_private_bundle(source, tmp_path / "okf", now=NOW)
    dest = Path(receipt["bundle_path"])
    concept = (dest / "buyers" / "buyer.example.md").read_text()
    assert yaml.safe_load(concept.split("---", 2)[1])["status"] == "draft"
    assert "verified:" not in concept
    assert "first_party" not in concept
    assert receipt["db_writes"] == 0
    assert (dest / "manifest.json").is_file()

from empire_os.okf_adapter import verify_bundle_files, catalogue_summary


def test_integrity_failure_is_not_trusted(tmp_path):
    import json
    import pytest
    source = tmp_path / "scout.json"
    source.write_text(json.dumps({"candidates": [
        {"website": "https://buyer.example", "domain": "buyer.example"}
    ]}))
    path = Path(export_private_bundle(source, tmp_path / "private", now=NOW)["bundle_path"])
    assert verify_bundle_files(path) == 1
    assert catalogue_summary(path)["execution_authority"] == "none"
    (path / "buyers" / "buyer.example.md").write_text("tampered")
    with pytest.raises(ValueError):
        verify_bundle_files(path)

def test_capped_export():
    sample = []
    for i in range(35):
        domain = f"entity-{i}.example"
        sample.append({"website": f"https://{domain}", "domain": domain})
    records = documents_from_scout({"candidates": sample}, now=NOW)
    assert len(records) == 30

def test_incorrect_domain_is_skipped():
    doc = documents_from_scout({"candidates": [
        {"website": "https://correct.example", "domain": "wrong.example"}
    ]}, now=NOW)
    assert not doc


def test_outbound_flag_cannot_create_verified_knowledge():
    doc = documents_from_scout({"candidates": [
        {"website": "https://buyer.example", "domain": "buyer.example",
         "explicit_direct_buyer_evidence": True},
    ]}, now=NOW)
    content = next(iter(doc.values()))
    metadata = yaml.safe_load(content.split("---", 2)[1])
    assert "verified" not in metadata
    assert metadata["empire_purchase_statement_observed"] is False

from empire_os.buyer_claim_provenance import classify_buyer_source_pages


def test_first_party_claim_preserves_source_and_expiry():
    claim = classify_buyer_source_pages([
        {"url": "https://buyer.example/partners",
         "visible_text": "We buy leads from qualified publishers."}
    ], company_website="https://buyer.example", observed_at=NOW.isoformat())
    docs = documents_from_scout({"candidates": [
        {"website": "https://buyer.example", "domain": "buyer.example",
         "buyer_claim_provenance": claim}
    ]}, now=NOW)
    concept = docs["buyers/buyer.example.md"]
    metadata = yaml.safe_load(concept.split("---", 2)[1])
    assert metadata["sources"][0]["resource"] == "https://buyer.example/partners"
    assert metadata["stale_after"].startswith("2026-11-08")
    assert metadata["empire_purchase_statement_observed"] is True
    assert "verified" not in metadata

def test_source_url_with_embedded_contact_is_not_exported():
    from empire_os.okf_adapter import public_url
    assert public_url(
        "https://buyer.example/staff/jane@buyer.example",
        "buyer.example",
    ) is None
    assert public_url(
        "https://buyer.example/people/jane-smith",
        "buyer.example",
    ) is None


def test_bad_clock_and_incorrect_schema_fail_closed():
    import pytest
    with pytest.raises(ValueError):
        documents_from_scout({"candidates": []}, now=datetime(2026, 10, 9))
    with pytest.raises(ValueError):
        documents_from_scout({"candidates": {}}, now=NOW)


def test_readonly_agent_research_has_no_commercial_authority(tmp_path):
    import json
    from empire_os.okf_adapter import list_private_research
    source = tmp_path / "scout.json"
    source.write_text(json.dumps({"candidates": [
        {"website": "https://buyer.example", "domain": "buyer.example"}
    ]}))
    path = Path(export_private_bundle(source, tmp_path / "okf", now=NOW)["bundle_path"])
    research = list_private_research(path, now=NOW)
    assert research["concept_count"] == 1
    assert research["execution_authority"] == "none"
    assert research["results"][0]["trust"] == "unverified"
    assert research["results"][0]["fresh"] is False
    assert research["results"][0]["sources"] == []


def test_contact_details_redacted_in_commercial_excerpt():
    from empire_os.okf_adapter import EMAIL, PHONE
    evidence = "Call +44 7777 123456 or email jane@buyer.example"
    assert EMAIL.search(evidence)
    assert PHONE.search(evidence)
    assert not EMAIL.search(EMAIL.sub("[email redacted]", evidence))
