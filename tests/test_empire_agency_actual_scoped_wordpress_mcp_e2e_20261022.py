"""Read-only verification of integrated WordPress/MariaDB authenticated MCP and secret lifecycle."""
from pathlib import Path
import json
from hashlib import sha256

ROOT=Path(__file__).resolve().parents[1]
MCP=ROOT/'prototypes/agency_wordpress_service_handoff_20261022/empire-agency-mcp-stdio'
RECEIPT=ROOT/'docs/commercial/EMPIRE_AGENCY_REAL_WP_MYSQL_MCP_AUTH_E2E_20261022.json'
DOC=ROOT/'docs/commercial/EMPIRE_AGENCY_REAL_WP_MCP_CONNECTOR_HANDOFF_20261022.md'

def receipt():
    return json.loads(RECEIPT.read_text())

def test_actual_wordpress_mariadb_mcp_credential_lifecycle_evidence():
    r=receipt()
    assert r['status']=='REAL_WORDPRESS_MARIADB_SCOPED_MCP_APP_PASSWORD_LIFECYCLE_PASS'
    assert r['native_mariadb_database'] is True
    assert r['native_wordpress_plugin_enabled'] is True
    assert r['loopback_http_only'] is True
    assert r['wordpress_real_application_password_authentication'] is True
    assert r['credential_revoked_after_test'] is True
    assert r['post_revocation_http_status']==401
    assert r['mcp_checks_passed']==len(r['mcp_checks'])==12
    assert all(r['mcp_checks'].values())
    assert r['scope']=={
        'connector_id':'wp-synthetic-inventory-read-v1',
        'site_id':'car-yard-synthetic',
        'tenant_id':'empire-agency-demo'
    }
    assert r['production_changes'] is False
    assert r['crm_payments_outbound_activated'] is False
    assert r['secret_values_in_receipt'] is False

def test_pinned_immutable_credential_stage_sources():
    for path,digest in receipt()['source_sha256'].items():
        src=ROOT/path
        assert src.is_file(),path
        assert sha256(src.read_bytes()).hexdigest()==digest,path

def test_staging_registry_exposes_no_write_tools_and_no_secret_material():
    j=json.loads((MCP/'connector-registry.staging.json').read_text())
    assert j['environment']=='synthetic_staging'
    assert len(j['connectors'])==1
    entry=j['connectors'][0]
    assert entry['allow_writes'] is False
    assert entry['enabled_by_default'] is False
    assert entry['allowed_operations']==['capabilities:read','vehicles:read']
    assert entry['credential_binding']=='runtime_environment_only'
    assert all(key not in entry for key in ('password','token','client_secret','credential_value'))
    policy=(MCP/'scoped-server.mjs').read_text()
    assert 'EMPIRE_AGENCY_MCP_TENANT_ID' in policy
    assert 'EMPIRE_AGENCY_MCP_SITE_ID' in policy
    assert 'EMPIRE_AGENCY_MCP_CONNECTOR_ID' in policy
    assert "url.hostname !== '127.0.0.1'" in policy
    assert 'registerTool(' not in policy
    assert 'writeFileSync' not in policy

def test_full_stage_is_local_and_no_production_write_claim():
    script=(ROOT/'scripts/agency_mcp_live_wp_e2e/run_auth_e2e.sh').read_text()
    assert 'mktemp -d /tmp/empire_agency_mcp_wordpress_' in script
    assert '--skip-networking' in script
    assert 'php_safe -S "127.0.0.1:$port"' in script
    assert 'trap cleanup EXIT' in script
    assert 'rm -f -- "$YARD_MCP_SECRET_FILE"' in script
    assert 'YARD_MCP_APP_PASSWORD=' in script
    assert 'sudo ' not in script
    assert "empiredb" not in script.lower()
    doc=DOC.read_text()
    assert 'production credential vault' in doc.lower()
    assert 'No real vehicle feed' in doc
