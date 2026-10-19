"""Read-only Twenty CRM recovery checks. Never restart or import data."""
from __future__ import annotations
from pathlib import Path
import subprocess
import urllib.request
import urllib.error
from typing import Any

SCHEMA = "empire.twenty_crm_recovery.v1"

def probe_local_health() -> dict:
    """Port 3000 alone does not prove Twenty is running."""
    request = urllib.request.Request("http://127.0.0.1:3000/healthz")
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            response.read(1024)
            code = response.status
    except urllib.error.HTTPError as exc:
        code = exc.code
    except (urllib.error.URLError, OSError, TimeoutError):
        code = None
    return {
        "twenty_health_http_status": code,
        "twenty_health_endpoint_responding": code == 200,
        "authenticated_twenty_workspace_verified": False,
    }

def inspect_twenty(repo_root: Path, *, plugin_path: Path,
                   health_probe=None, commit_probe=None) -> dict:
    if not repo_root.is_dir():
        raise ValueError("canonical_repository_unavailable")
    marker = bool(commit_probe(repo_root)) if commit_probe else False
    plugin = plugin_path.is_file()
    probe = health_probe() if health_probe else probe_local_health()
    if (not isinstance(probe, dict)
            or type(probe.get("twenty_health_endpoint_responding")) is not bool):
        raise ValueError("untrusted_twenty_health_probe")
    return {
        "schema_version": SCHEMA,
        "mode": "READ_ONLY_ORIGINAL_INSTANCE_RECOVERY",
        "state": "HISTORICAL_CODE_PRESENT_ORIGINAL_DATA_UNVERIFIED"
                 if marker or plugin else "NO_ORIGINAL_INSTANCE_EVIDENCE",
        "old_git_startup_reference_found": marker,
        "hermes_catalog_definition_found": plugin,
        "historical_runtime": "LXD/Incus (twenty-crm)",
        "current_lxd_original_instance_verified": False,
        "docker_inventory_not_original_runtime": True,
        "hermes_plugin_installed_or_connected_verified": False,
        "local_health": probe,
        "docker_container_inventory_verified": False,
        "postgres_data_volume_verified": False,
        "original_twenty_database_restored": False,
        "original_customer_records_verified": False,
        "running_original_instance_verified": False,
        "canonical_crm_database": "EmpireDB PostgreSQL",
        "isolated_restoration_required": True,
        "new_services_started": False,
        "twenty_data_imported": False,
        "outbound_authorized": False,
        "canonical_empiredb_writes": False,
        "execution_authority": "none",
    }

def compare_twenty_business_export(rows: list[dict], *, tenant: str) -> dict:
    """Company-only offline identity proposal; no person, contact or DB sync."""
    if not isinstance(tenant, str) or not 1 <= len(tenant) <= 80:
        raise ValueError("tenant_required")
    if not isinstance(rows, list) or len(rows) > 250:
        raise ValueError("unbounded_twenty_export")
    import re
    valid_domain = re.compile(r"^(?:[a-z0-9-]+[.])+[a-z]{2,24}$")
    seen, counted = set(), {"other_tenant": 0, "invalid_company_domain": 0,
                            "source_unverified": 0, "duplicate": 0}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("malformed_company_export")
        domain = row.get("company_domain")
        if row.get("tenant") != tenant:
            counted["other_tenant"] += 1
        elif not isinstance(domain, str) or not valid_domain.fullmatch(domain):
            counted["invalid_company_domain"] += 1
        elif row.get("company_source_verified") is not True:
            counted["source_unverified"] += 1
        elif domain in seen:
            counted["duplicate"] += 1
        else:
            seen.add(domain)
    return {
        "schema_version": "empire.twenty_b2b_offline_compare.v1",
        "reviewed_rows": len(rows),
        "businesses_for_future_canonical_identity_review": len(seen),
        "held_rows": sum(counted.values()), "hold_counts": counted,
        "tenant_scope_enforced": True,
        "canonical_identity_matching_performed": False,
        "contacts_or_people_exported": False,
        "twenty_records_imported": 0, "canonical_empiredb_writes": False,
        "outbound_authorized": False, "execution_authority": "none",
    }
