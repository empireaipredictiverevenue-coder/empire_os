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


def _ssh_live():
    from scripts.review_founder_research_live_release_20261021 import EXPECTED_RELEASE
    return {
        "api": {
            "active": True,
            "working_directory": "/srv/empire_os",
            "exec_start": "uvicorn --app-dir " + EXPECTED_RELEASE + "/api empire_os.founder_dashboard_service:app",
            "ssh_gate_key_names_present": True,
            "identity_key_presence": {k: False for k in IDENTITY_KEYS},
        },
        "web": {"active": True,
                "working_directory": EXPECTED_RELEASE + "/web",
                "origin_config_present": False},
        "tunnel": {"active": True},
        "api_catalog_http": 401,
        "web_research_http": 200,
        "public_research_http": 404,
        "production_head": "example",
        "production_dirty_paths_count": 0,
    }


def test_live_ssh_private_release_reports_deployment_but_not_independent_operator_attestation():
    r = evaluate(_ssh_live())
    assert r["schema_version"] == "empire.research.founder_release_truth.v2"
    assert r["status"] == "LIVE_SSH_PRIVATE_RESEARCH_OPERATOR_LOGIN_NOT_INDEPENDENTLY_ATTESTED"
    assert r["ssh_private_release_currently_active"] is True
    assert r["release_performed"] is True
    assert r["research_api_route_deployed"] is True
    assert r["runtime_key_configuration_present"] is True
    assert r["api_identity_key_names_present"] is False
    assert r["cloudflare_access_edge_rule_verified"] is False
    assert r["real_access_session_verified"] is False
    assert r["scoped_production_change_approved"] is False
    assert r["source_rights_granted"] is False
    assert r["outbound_sent"] is False
    assert r["database_writes"] is False
    assert r["money_moved"] is False


def test_ssh_release_does_not_claim_full_live_readiness_without_private_boundary():
    for field, value in (
        ("api_catalog_http", 404),
        ("web_research_http", 404),
        ("public_research_http", 200),
    ):
        scenario = _ssh_live()
        scenario[field] = value
        r = evaluate(scenario)
        assert r["status"].startswith("HOLD_"), field
        assert r["ssh_private_release_currently_active"] is False, field


def test_ssh_release_denies_wrong_root_and_unreadable_gate_keys():
    for unit, field, value in (
        ("api", "exec_start", "uvicorn --app-dir /other/release/api"),
        ("web", "working_directory", "/other/release/web"),
        ("api", "ssh_gate_key_names_present", None),
        ("api", "ssh_gate_key_names_present", False),
        ("web", "active", False),
    ):
        scenario = _ssh_live()
        scenario[unit][field] = value
        r = evaluate(scenario)
        assert r["status"].startswith("HOLD_"), (unit, field)
        assert r["ssh_private_release_currently_active"] is False


def test_ssh_release_does_not_claim_real_ssh_operator_session_even_with_known_gates():
    scenario = _ssh_live()
    scenario["api"]["ssh_gate_key_names_present"] = True
    r = evaluate(scenario)
    assert r["real_access_session_verified"] is False
    assert r["cloudflare_tunnel_is_access_authorisation"] is False
