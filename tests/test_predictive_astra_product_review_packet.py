"""ASTRA review input must not mint price, tenant, science or revenue approval."""
from __future__ import annotations
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from empire_os.predictive_astra_product_review_packet import (
    AstraReviewPacketHold, build_astra_product_review_packet, REVIEW_TASKS,
)
from empire_os.predictive_catalogue_price_comparison import review_catalogue_price_comparison
import scripts.review_predictive_comparison_20261021 as cli

SOURCE=Path("/srv/empire_os/runtime/commercial_catalog/latest.json")


def setup():
    raw=SOURCE.read_bytes()
    original=json.loads(raw)
    return original, review_catalogue_price_comparison(original), sha256(raw).hexdigest()


def build(*, original=None, report=None, digest=None):
    o,r,s=setup()
    return build_astra_product_review_packet(
        o if original is None else original,
        r if report is None else report,
        snapshot_sha256=s if digest is None else digest,
    )


def test_original_86_review_packet_and_critical_operating_counts():
    p=build()
    assert p["schema_version"]=="empire.predictive_revenue.astra_gpt6_review_input.v1"
    assert p["status"]=="ASTRA_GPT6_INDEPENDENT_REVIEW_INPUT_READY_NOT_EXECUTED"
    assert p["source_inventory_count"]==86
    assert p["reviewed_source_counts"]=={
        "active_but_unverified_catalogue":9,
        "catalogue_or_version_unverified":60,
        "founder_price_source":35,
        "inactive":51,
        "missing_vendor_reference":25,
        "price_conflicts":5,
        "scenario_cost_policies":26,
        "source_reported_binding_terms_ready":26,
    }
    assert len(p["products"])==86
    assert len(p["challenge_requirements"])==len(REVIEW_TASKS)==8
    assert p["independent_astra_gpt6_invocation_executed"] is False
    assert p["independent_reviewer_signature_verified"] is False
    assert p["prices_approved_by_this_packet"] is False
    assert p["customer_forecasts_or_revenue_verified"] is False
    assert p["database_writes"] is False
    assert p["execution_authority"]=="none"


def test_five_original_price_conflicts_never_resolved_or_promoted():
    p=build()
    records={x["product_code"]:x for x in p["products"]}
    for code in ("meetily_enterprise","meetily_pro","scraper_enterprise","scraper_pro","scraper_starter"):
        x=records[code]
        assert x["listed_price_minor_units"] is None
        assert x["conflicting_historical_prices_research_only"]["either_candidate_approved"] is False
        assert x["review_disposition"]=="EVIDENCE_HOLD_NO_CUSTOMER_APPROVAL"
        assert x["original_terms_ready_flag_not_legal_acceptance"] is False
        assert x["original_forecast_outcome_pair_verified"] is False
    assert records["meetily_pro"]["conflicting_historical_prices_research_only"]["candidate_difference_minor_units"]==5000
    assert records["meetily_enterprise"]["conflicting_historical_prices_research_only"]["candidate_difference_minor_units"]==50000


def test_pinned_source_digest_and_packet_canonical_fingerprint():
    p=build()
    fingerprint=p.pop("review_packet_sha256")
    body=json.dumps(p,sort_keys=True,separators=(",",":"),allow_nan=False)
    assert sha256(body.encode()).hexdigest()==fingerprint
    q=build()
    assert q["review_packet_sha256"]==fingerprint


def test_root_snapshot_is_unmodified_by_review():
    o,r,s=setup()
    first=deepcopy(o)
    review=build_astra_product_review_packet(o,r,snapshot_sha256=s)
    assert o==first
    assert review["not_proof_of_db_source_authenticity"] is True


@pytest.mark.parametrize("change",[
    "tampered_currency", "false_customer_economics", "premature_review",
    "wrong_source_count","duplicate_row","missing_original",
    "invalid_conflict", "unexpected_true_revenue", "price_mutation",
    "unverified_flag_change",
])
def test_forgery_or_missing_original_source_refused(change):
    o,r,s=setup()
    o=deepcopy(o)
    r=deepcopy(r)
    if change=="tampered_currency":
        r["products"][0]["catalogue_currency"]="JPY"
    elif change=="false_customer_economics":
        r["products"][0]["economic_delivery_cost_verified"]=True
    elif change=="premature_review":
        r["astra_gpt6_independent_review"]="APPROVED"
    elif change=="wrong_source_count":
        r["catalogue_product_count"]=85
    elif change=="duplicate_row":
        r["products"][0]=deepcopy(r["products"][1])
    elif change=="missing_original":
        o["products"].pop()
    elif change=="invalid_conflict":
        row=next(x for x in o["products"] if x["product_code"]=="meetily_pro")
        row["price_basis"]["pricing_candidate_cents"]=row["price_basis"]["metadata_candidate_cents"]
    elif change=="unexpected_true_revenue":
        o["products"][0]["actual_revenue"]=True
    elif change=="price_mutation":
        o["products"][0]["price_basis"]["amount_cents"]=123456
    elif change=="unverified_flag_change":
        r["products"][0]["terms_independently_authenticated"]=True
    with pytest.raises(AstraReviewPacketHold):
        build_astra_product_review_packet(o,r,snapshot_sha256=s)


def test_cli_summary_and_complete_packet_agree(capsys):
    assert cli.main(["--read-only","--astra-review"])==0
    small=json.loads(capsys.readouterr().out)
    assert "products" not in small
    assert small["review_product_details_omitted_count"]==86
    assert small["reviewed_source_counts"]["active_but_unverified_catalogue"]==9
    assert small["source_original_empiredb_issuer_authenticated"] is False
    assert cli.main(["--read-only","--astra-review-all"])==0
    full=json.loads(capsys.readouterr().out)
    assert len(full["products"])==86
    assert small["review_packet_sha256"]==full["review_packet_sha256"]
    assert full["independent_astra_gpt6_invocation_executed"] is False


def test_immutable_launcher_source_and_read_only_modes():
    src=(Path(__file__).resolve().parents[1] /
         "scripts/prepare_predictive_readonly_release_20261020.sh").read_text()
    assert "empire_os/predictive_astra_product_review_packet.py" in src
    assert 'if [[ "$command" == "comparison-astra" ]]' in src
    assert 'if [[ "$command" == "comparison-astra-all" ]]' in src
    assert '--read-only --astra-review-all' in src
    assert '--read-only --astra-review' in src
