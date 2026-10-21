"""Additive staging preserves existing private Founder builds, not deploying them."""
from hashlib import sha256
from pathlib import Path

import pytest

from scripts.stage_founder_research_api_20261021 import (
    IMPORT_ANCHOR, ROUTER_ANCHOR, NEW_IMPORT, NEW_ROUTER, stage_additive_api,
)
from scripts.stage_founder_research_console_20261021 import (
    BASE_FILES, NAV_ANCHOR, NAV_NEW, ROUTES, stage_console,
)
from scripts.verify_founder_research_api_stage_20261021 import evaluate


def test_smoke_result_requires_all_original_routers_and_fail_closed():
    original = {"routers": ["old_reader_one", "old_reader_two"] * 11,
                "health_http": 200, "research_catalog_http": 404}
    updated = {
        "routers": original["routers"] + ["create_founder_research_products_router"],
        "health_http": 200, "research_catalog_http": 503,
        "research_get_preview_http": 405, "research_post_preview_http": 503,
    }
    result = evaluate(original, updated)
    assert result["status"] == "ISOLATED_FOUNDER_API_ROUTE_PARITY_AND_FAIL_CLOSED_PASS"
    assert result["preserved_baseline_routers"]
    assert not result["production_modified"]
    for broken in (
        {**updated, "routers": updated["routers"][1:]},
        {**updated, "research_post_preview_http": 200},
        {**updated, "research_catalog_http": 200},
        {**updated, "health_http": 500},
    ):
        assert evaluate(original, broken)["status"].startswith("HOLD_")


def test_historical_api_stage_adds_one_router_without_editing_owner(tmp_path):
    api_root = tmp_path / "original_api"
    package = api_root / "empire_os"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    old = ("from __future__ import annotations\n"
           + "from fake import fake\n"
           + IMPORT_ANCHOR
           + "READ_ONLY_ROUTER_FACTORIES = (\n"
           + ROUTER_ANCHOR
           + ")\n"
           + "APP_CONFIG = dict(docs_url=None,openapi_url=None)\n")
    service = package / "founder_dashboard_service.py"
    service.write_text(old)
    original_digest = sha256(service.read_bytes()).hexdigest()
    stage = stage_additive_api(live_root=api_root, stage_parent=tmp_path)
    new = Path(stage["stage_root"])
    patched = (new / "empire_os/founder_dashboard_service.py").read_text()
    assert patched.count(NEW_IMPORT) == 1
    assert patched.count(NEW_ROUTER) == 1
    assert patched.count(IMPORT_ANCHOR) == 1
    assert patched.count(ROUTER_ANCHOR) == 1
    assert sha256(service.read_bytes()).hexdigest() == original_digest
    assert (new / "scripts/run_brokerage_deep_research_20261021.py").is_file()
    assert (new / "empire_os/research/research_products.py").is_file()
    assert stage["original_api_service_sha256"] == original_digest
    assert stage["production_root_modified"] is False
    assert stage["existing_api_root_modified"] is False


def test_historical_api_stage_rejects_collision(tmp_path):
    api_root = tmp_path / "api"
    package = api_root / "empire_os"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    (package / "founder_dashboard_service.py").write_text(
        IMPORT_ANCHOR + ROUTER_ANCHOR + "docs_url=None\nopenapi_url=None\n"
        + NEW_IMPORT)
    with pytest.raises(ValueError, match="HISTORICAL_API_ROUTER_BASELINE_CHANGED"):
        stage_additive_api(live_root=api_root, stage_parent=tmp_path)


def test_next_stage_preserves_existing_page_source_and_only_adds_research(tmp_path):
    live = tmp_path / "existing_next"
    candidate = Path(__file__).resolve().parents[2] / "apps/search-command-centre"
    live.mkdir()
    for rel in BASE_FILES:
        (live / rel).write_text("test fixture")
    (live / "src/app/founder").mkdir(parents=True)
    (live / "src/lib").mkdir()
    (live / "public").mkdir()
    nav = live / "src/app/founder/page.tsx"
    nav.write_text("EXISTING_NAV\n" + NAV_ANCHOR + "EXISTING_CONTENT_END\n")
    before = nav.read_bytes()
    stage = stage_console(live=live, candidate=candidate, stage_parent=tmp_path)
    new = Path(stage["stage_root"])
    assert nav.read_bytes() == before
    built = (new / "src/app/founder/page.tsx").read_text()
    assert NAV_ANCHOR + NAV_NEW in built
    assert built.endswith("EXISTING_CONTENT_END\n")
    assert all((new / rel).is_file() for rel in ROUTES)
    assert stage["live_release_modified"] is False
    assert stage["production_root_modified"] is False


def test_next_stage_fails_closed_when_research_is_already_present(tmp_path):
    live = tmp_path / "already_has_research"
    live.mkdir()
    for rel in BASE_FILES:
        (live / rel).write_text("fixture")
    (live / "src/app/founder/research").mkdir(parents=True)
    (live / "src/lib").mkdir(parents=True)
    (live / "src/app/founder/page.tsx").write_text(NAV_ANCHOR)
    (live / "public").mkdir()
    with pytest.raises(ValueError, match="EXISTING_PRIVATE_NEXT_RESEARCH_ROUTE_COLLISION"):
        stage_console(live=live, stage_parent=tmp_path)
