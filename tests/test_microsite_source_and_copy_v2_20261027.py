"""Source bridge + optional local model tests; all calls faked, no network."""
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import runpy

import pytest

from empire_os.microsite_first_party_gsc_bridge import (
    connect_factory_to_gsc, read_existing_weekly_receipt,
)
from empire_os.microsite_copy_revision import (
    review_copy_revision, offline_rewrite_instructions,
)
from empire_os.microsite_local_copy_adapter import (
    generate_local_copy_revision,
)


def source():
    return runpy.run_path(
        str(Path(__file__).with_name("test_predictive_microsite_factory_20261026.py")))["candidate"]()


def receipt():
    return {
        "schema_version": "empire.search.weekly_keyword_intent_evidence.v1",
        "owner": "empire_os.search_intelligence.search_console",
        "mode": "READ_ONLY",
        "execution_authority": "none",
        "database_writes": False,
        "outbound_sent": False,
        "publishing_authorized": False,
        "market_search_volume": None,
        "customer_leads_qualified": None,
        "sale_or_revenue_verified": False,
        "as_of": "2026-10-26",
        "source_status": "FIRST_PARTY_GSC_QUERY_PAGE_OBSERVED",
        "original_query_page_rows_returned": 2,
        "market_reviews": [{
            "market_key": "us-commercial-roofing",
            "first_party_exact_query_matches": 0,
            "observed_exact_query_page_evidence": [],
            "real_market_keyword_volume": None,
            "buyer_willingness_to_pay_verified": False,
        }],
    }


def test_realistic_empty_weekly_gsc_never_becomes_fake_local_volume():
    report = connect_factory_to_gsc([source()], receipt())
    assert report["candidates_with_exact_first_party_query"] == 0
    assert report["candidates"][0]["market_search_volume"] is None
    assert report["candidates"][0]["geo_demand_from_gsc_proven"] is False
    assert report["publication_authorized"] is False


def test_first_party_exact_query_only_proves_owned_page_query_match():
    data = receipt()
    data["market_reviews"][0]["first_party_exact_query_matches"] = 1
    data["market_reviews"][0]["observed_exact_query_page_evidence"] = [{
        "keyword": "chicago roof replacement research",
        "page_evidence": [{
            "page_url": "https://empire-ai.co.uk/roofing/",
            "impressions": 3,
            "evidence_ref": "sample_first_party_gsc_query_page",
        }],
    }]
    report = connect_factory_to_gsc([source()], data)
    row = report["candidates"][0]
    assert row["first_party_query_observed"] is True
    assert row["observed_owned_query_page_pairs"] == 1
    assert row["buyer_accepted"] is False
    assert row["geo_demand_from_gsc_proven"] is False
    assert row["market_search_volume"] is None


@pytest.mark.parametrize("field,value", [
    ("execution_authority", "write"), ("database_writes", True),
    ("publishing_authorized", True), ("market_search_volume", 200),
    ("customer_leads_qualified", 10), ("sale_or_revenue_verified", True),
])
def test_forged_gsc_authority_and_claims_rejected(field, value):
    data = receipt()
    data[field] = value
    with pytest.raises(ValueError):
        connect_factory_to_gsc([source()], data)


def test_read_receipt_rejects_symlink_and_handles_real_input(tmp_path):
    path = tmp_path / "gsc.json"
    path.write_text(json.dumps(receipt()))
    result, digest = read_existing_weekly_receipt(path)
    assert result["as_of"] == "2026-10-26" and len(digest) == 64
    link = tmp_path / "shortcut.json"
    link.symlink_to(path)
    with pytest.raises(ValueError):
        read_existing_weekly_receipt(link)


def test_rewrite_reduces_slop_without_touching_evidence():
    spec = source()
    spec["headline"] = "Our seamless, game-changing roofing research journey"
    proposed = {
        "headline": "Chicago roof replacement research, evidence and next steps",
        "subhead": spec["subhead"],
        "summary": spec["summary"],
    }
    review, after = review_copy_revision(spec, proposed)
    assert review["original_score"] <= review["proposed_score"]
    assert review["status"] == "DRAFT_EDITORIAL_REVIEW"
    assert after["local_facts"] == spec["local_facts"]
    assert review["independent_factual_verification_complete"] is False
    assert review["publication_authorized"] is False


@pytest.mark.parametrize("bad", [
    "Guaranteed 2,000 new customers for every roofing firm today!",
    "<script>alert(1)</script> Roofing research for your business.",
    "Our certified, best rated contractors provide free quotes today.",
    "Visit https://external.invalid to book roofing jobs today.",
])
def test_rewrite_claims_and_html_cannot_be_auto_accepted(bad):
    spec = source()
    proposal = {key: spec[key] for key in ("headline", "subhead", "summary")}
    proposal["headline"] = bad
    review, _ = review_copy_revision(spec, proposal)
    assert review["status"] == "HOLD_CLAIM_OR_STYLE"
    assert review["blockers"]


def test_rewrite_rejects_changes_to_commercial_or_source_keys():
    spec = source()
    proposed = {key: spec[key] for key in ("headline", "subhead", "summary")}
    proposed["local_facts"] = []
    with pytest.raises(ValueError):
        review_copy_revision(spec, proposed)


def test_optional_model_mock_output_rejected_or_held_not_published():
    spec = source()
    proposed = {
        "headline": "Chicago roof replacement research, evidence and next steps",
        "subhead": spec["subhead"], "summary": spec["summary"],
    }
    def mocked_transport(payload):
        body = json.loads(payload)
        assert body["model"] == "qwen2.5-coder:1.5b"
        assert body["stream"] is False
        return json.dumps({
            "choices": [{"message": {"content": json.dumps(proposed)}}]
        }).encode()
    result = generate_local_copy_revision(spec, transport=mocked_transport)
    assert result["status"] in {"DRAFT_EDITORIAL_REVIEW", "HOLD_CLAIM_OR_STYLE"}
    assert result["external_model_calls"] == 0
    assert result["publication_authorized"] is False
    assert result["model_calls"] == 1


def test_invalid_local_model_response_fails_held_not_accepted():
    result = generate_local_copy_revision(source(), transport=lambda _: b"bad json")
    assert result["status"] == "HOLD_INVALID_LOCAL_MODEL_RESPONSE"
    assert result["publication_authorized"] is False


def test_prompt_excludes_raw_local_facts_and_evidence_documents():
    spec = source()
    instruction = offline_rewrite_instructions(spec)
    assert "local_facts" not in instruction["model_input"]
    assert "source_copy" in instruction["model_input"]
    assert instruction["auto_publish"] is False
