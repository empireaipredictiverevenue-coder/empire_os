"""New staging integration extension: fail-closed, read-only and pinned evidence."""
import json
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'prototypes/agency_wordpress_service_handoff_20261022'
PHP = BASE / 'empire-agency-integration-bridge/empire-agency-integration-bridge.php'
CONTRACT = BASE / 'empire-agency-integration-bridge/integration-contract.json'
MCP = BASE / 'empire-agency-mcp-stdio'
DOC = ROOT / 'docs/commercial/EMPIRE_AGENCY_API_MCP_CONNECTOR_FOUNDATION_20261022.md'
RECEIPT = ROOT / 'docs/commercial/EMPIRE_AGENCY_REST_MCP_STAGING_RUNTIME_20261022.json'

def test_wordpress_companion_registration_requires_three_local_synthetic_gates():
    src = PHP.read_text()
    for phrase in (
        "EMPIRE_AGENCY_STAGING_INTEGRATIONS_ENABLED",
        "EMPIRE_AGENCY_SYNTHETIC_INVENTORY_ONLY",
        "wp_get_environment_type()",
        "'local', 'development'",
        "register_rest_route('empire-agency/v1', '/capabilities'",
        "register_rest_route('empire-agency/v1', '/vehicles'",
        "'methods' => WP_REST_Server::READABLE",
        "'permission_callback' => 'empire_agency_integration_permission'",
        "current_user_can('manage_options')",
        "is_user_logged_in()",
        "post_status' => 'publish'",
        "'status' => $status",
        "Cache-Control', 'private, no-store, max-age=0'",
        "X-Robots-Tag', 'noindex, nofollow, noarchive'",
    ):
        assert phrase in src, phrase
    assert "register_activation_hook" not in src
    assert "POST" not in src
    assert "WP_REST_Server::CREATABLE" not in src
    assert "register_rest_field" not in src
    assert "wp_mail(" not in src
    assert "update_post_meta(" not in src
    assert "wp_insert_post(" not in src
    assert "payment" not in src.lower().split("function empire_agency_integration_vehicles")[1].split("function empire_agency_register_integration_routes")[0]

def test_mcp_manifest_has_no_live_remote_services_or_credentials():
    c = json.loads(CONTRACT.read_text())
    assert c['schema'] == 'empire.agency.connectivity.contract.v1'
    assert c['status'] == 'STAGING_ONLY_NOT_PRODUCTION_CONNECTED'
    assert c['mcp']['endpoint_live'] is False
    assert c['mcp']['tools_active'] is False
    assert c['guarantees']['no_public_customer_api'] is True
    assert c['guarantees']['no_live_mcp_server'] is True
    assert c['guarantees']['production_changed'] is False
    assert c['wordpress']['methods'] == ['GET']
    assert all(not t['enabled'] for t in c['mcp']['tool_descriptors'])
    assert all('write' not in op['id'] for op in c['wordpress']['resource_allowlist'])
    text = CONTRACT.read_text()
    assert "sk-" not in text
    assert "-----BEGIN" not in text
    assert 'api_key' not in text.lower()
    assert "http://127.0.0.1:" not in text

def test_official_mcp_stdio_source_limited_to_loopback_reads():
    src = (MCP / 'server.mjs').read_text()
    for expected in (
        "from '@modelcontextprotocol/server'",
        "from '@modelcontextprotocol/server/stdio'",
        "from 'zod/v4'",
        "serveStdio(", "server.registerTool('agency_get_capabilities'",
        "server.registerTool('agency_list_demo_vehicles'",
        "EMPIRE_AGENCY_MCP_STAGING_ENABLED", "wordpress_loopback",
        "base.hostname !== '127.0.0.1'",
        "env.EMPIRE_AGENCY_MCP_APP_PASSWORD",
        "redirect: 'error'", "method: 'GET'",
        "AbortSignal.timeout(5000)", "fetch(uri",
        "writes_available: false", "untrusted_synthetic_wordpress_staging"
    ):
        assert expected in src, expected
    assert "app.listen(" not in src
    assert "registerTool('agency_create_booking'" not in src
    assert "writeFileSync" not in src
    assert "POST" not in src
    assert "mcp.example" not in src
    assert (MCP / 'package-lock.json').exists()
    assert "node_modules/" in (MCP / '.gitignore').read_text()
    pkg = json.loads((MCP / 'package.json').read_text())
    assert pkg['private'] is True
    assert '@modelcontextprotocol/server' in pkg['dependencies']
    assert '@modelcontextprotocol/client' in pkg['dependencies']

def test_real_wordpress_and_mcp_receipt_pinned_to_source():
    r = json.loads(RECEIPT.read_text())
    assert r['status'] == 'EMPIRE_AGENCY_REAL_WP_STAGING_AND_LOCAL_MCP_PROTOCOL_PASS'
    assert r['disabled_default_http_status'] == 404
    assert r['enabled_staging_checks_passed'] == len(r['enabled_staging_checks']) == 27
    assert all(r['enabled_staging_checks'].values())
    assert r['local_mcp_v2_protocol_tests_passed'] == 6
    assert r['mcp_public_endpoint_live'] is False
    assert r['production_wordpress_modified'] is False
    assert r['real_crm_or_personal_data_used'] is False
    assert r['real_third_party_connector_activated'] is False
    assert r['booking_email_payment_writes_enabled'] is False
    for name, digest in r['source_sha256'].items():
        assert sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
    assert "NOT YET" in DOC.read_text()
