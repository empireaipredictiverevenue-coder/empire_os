"""Reproducible, create-only receipt from disposable real WordPress + local MCP tests."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "prototypes/agency_wordpress_service_handoff_20261022"
WP_PLUGIN = BASE / "empire-agency-integration-bridge"
WP_VEHICLE = BASE / "empire-car-yard"
MCP = BASE / "empire-agency-mcp-stdio"
FIXTURES = ROOT / "scripts/integration_wp_e2e"
RECEIPT = ROOT / "docs/commercial/EMPIRE_AGENCY_REST_MCP_STAGING_RUNTIME_20261022.json"

def parse_payload(output: str, expected: str) -> dict:
    decoder = json.JSONDecoder()
    for pos, value in enumerate(output):
        if value != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(output[pos:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("status") == expected:
            return obj
    raise RuntimeError("Expected verified WordPress success marker not present")

def wordPress(fixture: str, status: str) -> dict:
    cmd = [
        "npx", "--yes", "@wp-playground/cli@3.1.60", "php",
        "--wp=6.8", "--php=8.3",
        f"--mount={WP_VEHICLE}:/wordpress/wp-content/plugins/empire-car-yard",
        f"--mount={WP_PLUGIN}:/wordpress/wp-content/plugins/empire-agency-integration-bridge",
        f"--mount={FIXTURES}:/wordpress/wp-content/empire-integration-e2e",
        "--", f"/wordpress/wp-content/empire-integration-e2e/{fixture}"
    ]
    completed = subprocess.run(cmd, cwd=ROOT, capture_output=True,
                               text=True, timeout=140, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            f"Disposable WordPress integration fixture {fixture} failed: "
            + completed.stderr[-800:] + completed.stdout[-800:]
        )
    return parse_payload(completed.stdout, status)

def run() -> dict:
    if RECEIPT.exists() or RECEIPT.is_symlink():
        raise FileExistsError("Immutable runtime receipt exists; refusing overwrite")

    disabled = wordPress("integration_disabled.php",
                         "EMPIRE_AGENCY_INTEGRATIONS_DISABLED_BY_DEFAULT_PASS")
    assert disabled["endpoint_registered"] is False
    assert disabled["status_code"] == 404
    assert disabled["production_changes"] is False

    enabled = wordPress("integration_enabled.php",
                        "EMPIRE_AGENCY_WORDPRESS_INTEGRATION_STAGING_PASS")
    required = {
        "anonymous_inventory_401", "editor_inventory_403",
        "admin_inventory_200", "write_http_method_rejected",
        "no_synthetic_secret_leak", "no_archived_or_draft_inventory",
        "private_no_store_cache_header", "no_mcp_or_write_claim",
        "limit_capped_to_20"
    }
    assert enabled["checks_passed"] == 27
    assert required.issubset(enabled["checks"])
    assert all(enabled["checks"].values())
    assert enabled["wordpress"].startswith("6.8.")
    assert enabled["real_data"] is False
    assert enabled["mcp_server_live"] is False
    assert enabled["public_write_route"] is False
    assert enabled["production_changes"] is False

    test = subprocess.run(["npm", "test"], cwd=MCP, text=True,
                          capture_output=True, timeout=60, check=False)
    if test.returncode != 0 or "# pass 6" not in test.stdout:
        raise RuntimeError("MCP v2 test suite did not verify six checks: "
                           + test.stdout[-650:] + test.stderr[-500:])

    sources = [
        "prototypes/agency_wordpress_service_handoff_20261022/empire-agency-integration-bridge/empire-agency-integration-bridge.php",
        "prototypes/agency_wordpress_service_handoff_20261022/empire-agency-integration-bridge/integration-contract.json",
        "prototypes/agency_wordpress_service_handoff_20261022/empire-agency-mcp-stdio/server.mjs",
        "prototypes/agency_wordpress_service_handoff_20261022/empire-agency-mcp-stdio/test.mjs",
        "prototypes/agency_wordpress_service_handoff_20261022/empire-agency-mcp-stdio/package-lock.json",
        "scripts/integration_wp_e2e/integration_disabled.php",
        "scripts/integration_wp_e2e/integration_enabled.php",
        "scripts/integration_wp_e2e/run_contract.py"
    ]

    return {
        "status": "EMPIRE_AGENCY_REAL_WP_STAGING_AND_LOCAL_MCP_PROTOCOL_PASS",
        "observed_utc": datetime.now(timezone.utc).isoformat(),
        "wordpress_version": enabled["wordpress"],
        "php_version": enabled["php"],
        "disabled_default_status": disabled["status"],
        "disabled_default_http_status": 404,
        "enabled_staging_checks_passed": enabled["checks_passed"],
        "enabled_staging_checks": enabled["checks"],
        "local_mcp_v2_protocol_tests_passed": 6,
        "mcp_public_endpoint_live": False,
        "production_wordpress_modified": False,
        "real_crm_or_personal_data_used": False,
        "real_third_party_connector_activated": False,
        "booking_email_payment_writes_enabled": False,
        "source_sha256": {rel: sha256((ROOT / rel).read_bytes()).hexdigest()
                          for rel in sources},
        "limitations": "WordPress REST and MCP integration separately tested; MCP-to-real-WordPress authenticated bridge and tenant-bound remote OAuth pending",
    }

if __name__ == "__main__":
    if sys.argv[1:] != ["--execute-isolated"]:
        raise SystemExit("Explicit --execute-isolated is required")
    value = run()
    with RECEIPT.open("x", encoding="utf8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps({"status":value["status"],
                      "wordpress_checks":value["enabled_staging_checks_passed"],
                      "mcp_checks":value["local_mcp_v2_protocol_tests_passed"],
                      "production_changes":value["production_wordpress_modified"]}))
