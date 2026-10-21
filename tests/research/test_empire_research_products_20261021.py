"""Internal product acceptance: actual mode budgets, work receipts, private API."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import stat

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI, Request

from empire_os.research.research_products import PRODUCTS, product_catalog, use_product
from empire_os.founder_research_products_api import (
    ResearchExecutionBudget, create_founder_research_products_router
)
from scripts.use_empire_research_products_20261021 import save_private_result


STAMP = datetime(2026, 10, 21, 13, tzinfo=timezone.utc)


def fake_founder(request: Request):
    return "verified-test-founder"


def inspector(url):
    return {
        "status": "ORIGINAL_HTML_HEADINGS_INSPECTED",
        "content_sha256": sha256(url.encode()).hexdigest(),
        "document_headings": ["Published original source"],
    }


def test_two_genuine_product_surfaces_have_unprivileged_catalog():
    c = product_catalog()
    assert set(PRODUCTS) == {"empire_research", "empire_agent"}
    assert all(PRODUCTS[p]["customer_release"] == "not_authorized" for p in PRODUCTS)
    assert c["default_niche"] == "dental"
    assert c["editorial_approval_required"] is True
    assert c["commercial_actions_authorized"] is False
    assert "US" in c["markets"] and "GB" in c["markets"]
    assert "property" in c["niches"] and "dental" in c["niches"]


@pytest.mark.parametrize("depth,expected", [
    ("speed", 1), ("balanced", 2), ("quality", 3)
])
def test_vane_inspired_depth_is_real_work_budget(depth, expected):
    result = use_product(
        "empire_research", country="US", niche="dental", depth=depth,
        inspect_fn=inspector, observed_at=STAMP
    )
    assert result["product_id"] == "empire_research"
    assert result["original_source_count"] == expected
    assert result["research"]["market_reports"][0]["original_pages_inspected"] == expected
    if expected == 3:
        assert result["status"] == "ORIGINAL_MARKET_SOURCES_OBSERVED_REVIEW_PENDING"
    else:
        assert result["status"] == "HELD_INCOMPLETE_MARKET_SOURCE_OBSERVATION"
    assert not result["editorial_approval_verified"]
    assert not result["customer_delivery_authorized"]
    assert not result["outbound_authorized"]
    assert not result["database_writes"]


def test_agent_product_actually_runs_bounded_evidence_pipeline():
    result = use_product(
        "empire_agent", country="both", niche="dental", depth="quality",
        inspect_fn=inspector, observed_at=STAMP,
    )
    assert result["product_title"] == "Empire Agent"
    assert result["original_source_count"] == 6
    assert result["status"] == "WORK_COMPLETED_FOR_EDITORIAL_REVIEW"
    steps = result["agent_workflow"]["step_receipts"]
    assert [s["step"] for s in steps] == [
        "scope", "discover_original_sources", "inspect_originals",
        "evidence_crosscheck", "independent_editorial_review",
        "customer_delivery_or_outbound",
    ]
    assert [s["state"] for s in steps] == [
        "DONE", "DONE", "DONE", "DONE_FOR_REVIEW", "AWAITING_OWNER", "BLOCKED"
    ]
    assert result["agent_workflow"]["unbounded_shell_or_browser_allowed"] is False
    assert not result["agent_workflow"]["independent_editorial_signoff"]


def test_non_dental_agent_refuses_to_fake_sources():
    result = use_product(
        "empire_agent", country="both", niche="roofing", depth="quality",
        inspect_fn=lambda url: (_ for _ in ()).throw(
            AssertionError("no dental original inspection may run for roofing")
        ),
    )
    assert result["status"] == "HELD_SOURCE_INTAKE_REQUIRED"
    assert result["original_source_count"] == 0
    assert result["agent_workflow"]["step_receipts"][2]["state"] == "HELD"
    assert not result["editorial_approval_verified"]


def test_private_receipt_exclusive_owner_only(tmp_path):
    report = use_product("empire_agent", country="US", inspect_fn=inspector,
                         observed_at=STAMP)
    private = tmp_path / "owner-receipts"
    saved = save_private_result(report, directory=private)
    assert stat.S_IMODE(private.stat().st_mode) == 0o700
    assert stat.S_IMODE(saved.stat().st_mode) == 0o600
    assert json.loads(saved.read_text())["product_id"] == "empire_agent"
    with pytest.raises(FileExistsError):
        save_private_result(report, directory=private)
    assert len(list(private.iterdir())) == 1


def test_private_router_catalog_and_readonly_agent_preview():
    app = FastAPI()
    app.include_router(create_founder_research_products_router(
        product_runner=lambda p, country, niche, depth, fresh_discovery: use_product(
            p, country=country, niche=niche, depth=depth,
            fresh_discovery=fresh_discovery, inspect_fn=inspector, observed_at=STAMP,
        ),
        require_founder=fake_founder,
        execution_budget=ResearchExecutionBudget(min_interval_seconds=0),
    ))
    with TestClient(app) as client:
        c = client.get("/v1/founder-research-products/catalog")
        assert c.status_code == 200
        assert len(c.json()["products"]) == 2
        agent = client.post("/v1/founder-research-products/preview", json={
            "product": "empire_agent", "country": "US",
            "niche": "dental", "depth": "quality",
        })
        assert agent.status_code == 200
        assert agent.json()["agent_workflow"]["status"] == \
            "WORK_COMPLETED_FOR_EDITORIAL_REVIEW"
        assert agent.json()["outbound_authorized"] is False
        assert agent.json()["database_writes"] is False
        invalid = client.post("/v1/founder-research-products/preview", json={
            "product": "empire_agent", "country": "FR",
        })
        assert invalid.status_code == 422


@pytest.mark.parametrize("bad", ["other_product", "", None])
def test_unregistered_product_rejected(bad):
    with pytest.raises(ValueError, match="UNKNOWN"):
        use_product(bad, country="US", inspect_fn=inspector)


def test_private_receipt_no_customer_data_injected():
    result = use_product("empire_research", country="US", inspect_fn=inspector)
    assert "buyer" not in result or result.get("buyer") is None
    assert result["finance_authorized"] is False
    assert result["customer_delivery_authorized"] is False


def test_fresh_discovery_is_explicit_and_never_admits_other_sector_pages():
    seen = []
    def candidate_search(query, **kwargs):
        seen.append((query, kwargs))
        return {
            "organic": [{"title": "UK solar installer public service description",
                         "link": "https://solar.example-business.co.uk/installer"}],
            "searchParameters": {"engine": "bing_html", "cache": False,
                                 "search_state": "RESULTS", "quality_gate": "lexical_v2"},
        }
    r = use_product("empire_agent", country="GB", niche="solar", depth="quality",
                    fresh_discovery=True, search_fn=candidate_search,
                    inspect_fn=lambda url: (_ for _ in ()).throw(
                        AssertionError("search candidates are not approved original sources")
                    ))
    assert r["status"] == "HELD_SOURCE_INTAKE_REQUIRED"
    assert r["fresh_discovery_requested"] is True
    assert r["original_source_count"] == 0
    assert r["fresh_discovery_candidates_admitted"] == 0
    assert len(seen) == 2
    assert all(kwargs["use_cache"] is False and kwargs["engine"] is None
               for _, kwargs in seen)
    assert r["research"]["niche_intake_plans"][0][
        "public_search_diagnostic"]["source_admissions"] == 0
    assert r["editorial_approval_verified"] is False
    assert r["outbound_authorized"] is False
