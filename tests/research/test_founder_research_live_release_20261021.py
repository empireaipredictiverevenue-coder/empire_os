"""No backend process or Cloudflare tunnel alone grants Founder research."""
from scripts.review_founder_research_live_release_20261021 import (
    IDENTITY_KEYS, evaluate,
)


def _runtime():
    return {
        "api": {"active": True, "working_directory": "/srv/empire_os",
                "identity_key_presence": {k: True for k in IDENTITY_KEYS}},
        "web": {"active": True, "working_directory": "/isolated/founder",
                "origin_config_present": True},
        "tunnel": {"active": True},
        "api_catalog_http": 401,
        "production_head": "example", "production_dirty_paths_count": 0,
    }


def test_even_fully_configured_runtime_needs_independent_edge_proof():
    r = evaluate(_runtime())
    assert r["api_identity_key_names_present"] is True
    assert r["web_origin_key_name_present"] is True
    assert r["runtime_key_configuration_present"] is True
    assert r["research_api_route_deployed"] is True
    assert r["status"].startswith("HOLD_")
    assert r["real_access_session_verified"] is False
    assert r["cloudflare_access_edge_rule_verified"] is False
    assert r["scoped_production_change_approved"] is False
    assert r["release_performed"] is False
    assert r["money_moved"] is False


def test_missing_api_configuration_stays_held():
    d = _runtime()
    d["api"]["identity_key_presence"].pop(IDENTITY_KEYS[0])
    d["api_catalog_http"] = 404
    r = evaluate(d)
    assert r["api_identity_key_names_present"] is False
    assert r["research_api_route_deployed"] is False
    assert r["runtime_key_configuration_present"] is False
    assert r["status"].startswith("HOLD_")


def test_unreadable_process_env_never_becomes_approved():
    d = _runtime()
    d["web"]["origin_config_present"] = None
    d["api"]["identity_key_presence"] = None
    r = evaluate(d)
    assert r["runtime_key_configuration_present"] is False
    assert r["status"].startswith("HOLD_")
