"""Original V4 microsite ranking: public alternatives are evidence, not a gap."""
from datetime import date, datetime, timezone
from pathlib import Path
import copy
import json

import pytest

from empire_os.microsite_ranked_production_queue_v4 import build_ranked_microsite_queue
from empire_os.microsite_commercial_intelligence_v3 import build_microsite_commercial_review
from empire_os.predictive_microsite_factory import build_candidate
from tests.test_microsite_executive_research_screen_20261028 import manchester

NOW=datetime(2026,10,28,19,0,tzinfo=timezone.utc)


def dossier(spec):
    packet,_=build_candidate(spec)
    return {
        "schema_version":"empire.microsite.competitive_desk.v1",
        "mode":"OBSERVE",
        "execution_authority":"none",
        "custody":"RESEARCHER_DESK_OBSERVATIONS_UNVERIFIED",
        "candidates":[{
            "candidate_id":packet["id"],
            "market_id":packet["market"]["market_id"],
            "keyword":packet["keyword"]["record"]["keyword"],
            "observed_at":"2026-10-28T19:00:00Z",
            "sources":[
                {"url":"https://www.gov.uk/check-heat-pump",
                 "publisher":"GOV.UK","kind":"government_service",
                 "covered_jobs":["home_suitability","cost_comparison"]},
                {"url":"https://www.moneysavingexpert.com/utilities/heat-pumps-grant/",
                 "publisher":"MoneySavingExpert","kind":"consumer_guide",
                 "covered_jobs":["grant_eligibility","funding_amount","installer_selection"]},
                {"url":"https://www.manchester.gov.uk/homes-and-property/energy-efficiency/get-support-for-your-energy-improvements",
                 "publisher":"Manchester City Council","kind":"public_local_authority",
                 "covered_jobs":["local_support","funding_amount"]},
            ],
        }],
    }


def queue(spec,doc=None):
    commercial=build_microsite_commercial_review([spec],now=NOW)
    return build_ranked_microsite_queue(
        [spec],commercial=commercial,competitive=doc,as_of=date(2026,10,28))


def test_existing_public_guides_stop_generic_differentiation_claim():
    spec=manchester()
    result=queue(spec,dossier(spec))
    row=result["rows"][0]
    comp=row["competitive_screen"]
    assert comp["source_count"]==3
    assert comp["status"]=="ESTABLISHED_ALTERNATIVES_OBSERVED_DESK_ONLY"
    assert comp["competitive_gap_verified"] is False
    assert comp["independently_verified_competitor_claims"] is False
    assert "home_suitability" in comp["covered_public_reader_jobs"]
    assert "local_support" in comp["covered_public_reader_jobs"]
    assert row["executive_screen"]["decision"]=="VALIDATE_DIFFERENTIATED_READER_JOB"
    assert row["executive_screen"]["next_action_owner"]=="Marketing Research"
    assert result["publishable_count"]==0
    assert comp["customer_willingness_to_pay_verified"] is False
    assert comp["underwritten_contribution_margin_minor"] is None
    assert comp["break_even_leads"] is None
    economics=row["commercial_underwriting"]
    assert economics["independently_verified_payout_minor"] is None
    assert economics["customer_acquisition_cost_minor"] is None
    assert economics["net_contribution_minor"] is None
    assert economics["buyer_contract_accepted_for_exact_page"] is False
    assert economics["budget_authorized"] is False


def test_old_queue_remains_backward_compatible_without_competitors():
    spec=manchester()
    row=queue(spec)["rows"][0]
    assert row["executive_screen"]["decision"]=="MEASURE_FIRST_PARTY_INTENT"
    assert row["competitive_screen"]["source_count"]==0
    assert row["competitive_screen"]["status"]=="COMPETITOR_COVERAGE_UNKNOWN"
    assert row["competitive_screen"]["competitive_gap_verified"] is False


@pytest.mark.parametrize("mutation",[
    lambda x:x.update(execution_authority="publish"),
    lambda x:x.update(custody="INDEPENDENTLY_VERIFIED"),
    lambda x:x["candidates"][0].update(keyword="unrelated"),
    lambda x:x["candidates"][0].update(market_id="GB-LON"),
    lambda x:x["candidates"][0].update(observed_at="2026-01-01T18:00:00Z"),
    lambda x:x["candidates"][0].update(sources="not-list"),
    lambda x:x["candidates"][0]["sources"].append(
        copy.deepcopy(x["candidates"][0]["sources"][0])),
])
def test_injected_competitor_dossier_rejected(mutation):
    spec=manchester()
    doc=dossier(spec)
    mutation(doc)
    with pytest.raises(ValueError):
        queue(spec,doc)


@pytest.mark.parametrize("url",[
    "http://www.gov.uk/check-heat-pump",
    "https://www.gov.uk.evil.example/check-heat-pump?x=1",
    "https://localhost/internal",
    "https://127.0.0.1/private",
    "https://user:secret@www.gov.uk/check-heat-pump",
    "https://www.gov.uk:8443/check-heat-pump",
    "https://www.gov.uk/check-heat-pump#fragment",
    "https://www.gov.uk/check-heat-pump?x=1",
])
def test_invalid_or_unbounded_competitor_urls_rejected(url):
    spec=manchester()
    doc=dossier(spec)
    doc["candidates"][0]["sources"][0]["url"]=url
    with pytest.raises(ValueError):
        queue(spec,doc)


def test_no_public_competitor_dossier_is_not_proof_of_market_gap():
    spec=manchester()
    doc=dossier(spec)
    doc["candidates"][0]["sources"]=[]
    row=queue(spec,doc)["rows"][0]
    assert row["competitive_screen"]["status"]=="NO_ALTERNATIVES_RECORDED_NOT_PROOF_OF_GAP"
    assert row["competitive_screen"]["competitive_gap_verified"] is False
    assert row["executive_screen"]["commercial_investment_authorized"] is False


def test_original_queue_cli_consumes_optional_desk_evidence(tmp_path):
    from scripts.review_ranked_microsite_outcomes_v4_20261027 import run
    spec=manchester()
    sources=tmp_path/"source.json"
    commercial=tmp_path/"commercial.json"
    comparison=tmp_path/"comparison.json"
    sources.write_text(json.dumps({"candidates":[spec]}))
    commercial.write_text(json.dumps(build_microsite_commercial_review([spec],now=NOW)))
    comparison.write_text(json.dumps(dossier(spec)))
    out=tmp_path/"review"
    result=run(candidate_source=sources,commercial_source=commercial,
               competitive_source=comparison,weekly_source=None,output=out)
    assert result["status"]=="PRIVATE_RANKED_RESEARCH_QUEUE"
    saved=json.loads((out/"ranked_research_queue.json").read_text())
    assert saved["rows"][0]["competitive_screen"]["source_count"]==3
    assert saved["rows"][0]["executive_screen"]["decision"]=="VALIDATE_DIFFERENTIATED_READER_JOB"
    assert saved["publishable_count"]==0
    assert result["production_changed"] is False


def test_competitor_dossier_file_cannot_be_symlinked(tmp_path):
    from scripts.review_ranked_microsite_outcomes_v4_20261027 import run
    source=tmp_path/"origin.json"
    target=tmp_path/"competitor.json"
    link=tmp_path/"competitor-link.json"
    source.write_text("{}")
    target.write_text("{}")
    link.symlink_to(target)
    with pytest.raises(ValueError,match="symlink"):
        run(candidate_source=source,commercial_source=source,
            competitive_source=link,weekly_source=None,
            output=tmp_path/"never")
    assert not (tmp_path/"never").exists()


def test_unhashable_or_unknown_job_lists_rejected_without_type_errors():
    spec=manchester()
    for jobs in ([{"fake":"job"}], ["made_up_customer_job"], ["local_support","local_support"]):
        doc=dossier(spec)
        doc["candidates"][0]["sources"][0]["covered_jobs"]=jobs
        with pytest.raises(ValueError,match="reader job/category"):
            queue(spec,doc)
