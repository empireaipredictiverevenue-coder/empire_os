"""Existing PR research and public source-index observations remain distinct from buyers."""
import json
from pathlib import Path
import pytest

from empire_os.earned_media_leadgen_review import REQUESTS
from empire_os.earned_media_sales_actionability import PUBLIC_PROBE_DOC, _public_probe
from scripts.review_earned_media_advisory_bridge_20261025 import main
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
PR_SOURCE = Path("/home/ubuntu/empire_agents/empire_pr_consultancy_20261011")
CANONICAL = Path("/srv/empire_os")


def test_new_real_public_search_observation_never_promotes_a_buyer():
    path = ROOT / PUBLIC_PROBE_DOC
    d=json.loads(path.read_text())
    assert path.name == "PR_CONSULTANCY_MARKETPLACE_PUBLIC_OBSERVATION_20261027.json"
    assert d["method"] == "PUBLIC_WEB_SEARCH_OBSERVATION_NOT_AUTHENTICATED_UPWORK_SESSION"
    observed, status=_public_probe(d, as_of=datetime(2026,10,27,13,0,tzinfo=timezone.utc))
    assert status == "PUBLIC_INDEX_OBSERVATIONS_REVIEWED"
    assert len(observed)==2
    assert set(observed)==set(s["url"] for s in REQUESTS[:2])
    assert all(e["authenticated_listing_available"] is False
               and e["identified_buying_organisation"] is False
               and e["supplier_eligibility_verified"] is False
               and e["outreach_authorized"] is False for e in d["observations"])
    assert REQUESTS[2]["url"] not in observed


def test_existing_original_sources_are_connected_only_when_present(capsys):
    if not ((PR_SOURCE/"docs/commercial/PR_CONSULTANCY_FOUNDER_PRICING_20261011.json").is_file()
            and (CANONICAL/"runtime/revenue_distribution/latest.json").is_file()):
        pytest.skip("Original EmpireOS source trees are not mounted in this environment")
    rc=main(["--review-only", "--with-leadgen", "--existing-original-source-map", "--summary"])
    report=json.loads(capsys.readouterr().out)
    assert rc==0
    assert report["bridge_state"]=="REVIEW_CONNECTED_NOT_PRODUCTION_ACTIVATION"
    assert report["lead_counts"]["qualified_buyer"]==0
    assert report["lead_counts"]["total"]>=3
    assert report["sales_actionability_state"]=="REVIEW_PRIORITIES_NOT_EXECUTABLE_SALES_PIPELINE"
    assert report["public_source_observation_state"]=="PUBLIC_INDEX_OBSERVATIONS_REVIEWED"
    assert report["eligible_for_contact"]==0
    assert report["eligible_for_proposal"]==0
    assert report["outbound_authorized"] is False
    assert report["empiredb_writes"] is False
    assert report["revenue_verified"] is False


def test_cannot_combine_source_alias_with_explicit_roots(capsys):
    with pytest.raises(SystemExit,match="2"):
        main(["--review-only","--existing-original-source-map","--pr-root","/tmp/override"])
    assert "cannot override explicit source roots" in capsys.readouterr().err
