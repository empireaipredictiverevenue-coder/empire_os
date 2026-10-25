"""V4.9 production additive read-only API contract and baseline preservation."""
from __future__ import annotations

from pathlib import Path
import subprocess

from fastapi.testclient import TestClient

from empire_os.predictive_cloud_v49_readiness_api import (
    PATH, SCHEMA, build_v49_shadow_readiness, create_v49_shadow_readiness_router,
)

ROOT = Path(__file__).resolve().parents[1]


def test_v49_no_source_admission_or_execution_claims():
    result = build_v49_shadow_readiness()
    assert result["schema_version"] == SCHEMA
    assert result["mode"] == "OBSERVE"
    assert result["status"] == "SHADOW_CODE_LOADED_NON_EXECUTING"
    assert result["local_shadow_modules_importable"] is True
    assert result["original_smart_crm_reader_reused"] is True
    assert result["read_only"] is True
    assert result["recognized_revenue_cents"] is None
    for key in (
        "real_source_rights_verified", "production_tenant_source_admitted",
        "empiredb_migrations_064_065_applied_by_this_release",
        "redis_cloud_producer_activated", "live_consumer_activated",
        "commercial_prediction_authorized", "outbound_authorized",
        "paid_traffic_authorized", "trading_authorized", "treasury_authorized",
    ):
        assert result[key] is False


def test_v49_only_get_not_post_put_delete():
    from fastapi import FastAPI

    app = FastAPI(docs_url=None, openapi_url=None)
    app.include_router(create_v49_shadow_readiness_router())
    route = [r for r in app.routes[0].original_router.routes if r.path == PATH]
    assert len(route) == 1
    assert route[0].methods == {"GET"}
    client = TestClient(app)
    res = client.get(PATH)
    assert res.status_code == 200
    assert res.headers["cache-control"] == "no-store, private"
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.json() == build_v49_shadow_readiness()
    for method in ("post", "put", "delete", "patch"):
        assert getattr(client, method)(PATH).status_code == 405


def test_wrapper_preserves_existing_jev_founder_api_app():
    src = (ROOT / "scripts/predictive_cloud_v49_existing_api_overlay_20261025.py").read_text()
    assert "from composite_property_jev_overlay import app" in src
    assert 'empire_os.__path__.append(str(CANONICAL_MODULES))' in src
    assert 'after != before + Counter({expected: 1})' in src
    assert 'V49_EXISTING_FOUNDER_ROUTING_CHANGED' in src
    assert "create_v49_shadow_readiness_router()" in src
    assert "from empire_os.hub" not in src
    assert "app = FastAPI(" not in src


def test_v49_no_network_or_database_clients():
    src = (ROOT / "empire_os/predictive_cloud_v49_readiness_api.py").read_text()
    for disallowed in (
        "requests.", "httpx.", "psycopg.", "redis.Redis", ".execute(",
        "smtp", "os.system", "subprocess", "router.post(", "router.put(",
        "router.delete(", "include_router(create_outbound",
    ):
        assert disallowed not in src


def test_v49_compiles_without_creating_live_state():
    for name in (
        "empire_os/predictive_cloud_v49_readiness_api.py",
        "scripts/predictive_cloud_v49_existing_api_overlay_20261025.py",
    ):
        text = (ROOT / name).read_text()
        compile(text, name, "exec")
