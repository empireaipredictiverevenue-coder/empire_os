"""Legacy Twenty/Listmonk fleet really lived in LXD, not Docker."""
import json
from scripts.audit_legacy_crm_lxd_20261019 import audit
from scripts.audit_legacy_crm_lxd_backups_20261019 import inspect_backup_metadata


class Result:
    returncode = 0
    def __init__(self, obj):
        self.stdout = json.dumps(obj)


def runner_with(instances, pools=None, projects=None):
    data = [instances, pools or [], projects or [{"name": "default"}]]
    def run(*args, **kwargs):
        return Result(data.pop(0))
    return run


def test_empty_lxd_inventory_does_not_mean_original_data_erased():
    d = audit(runner=runner_with([]))
    assert d["state"] == "CURRENT_LXD_HAS_NO_HISTORICAL_INSTANCES"
    assert d["instance_count_all_projects"] == 0
    assert d["storage_pool_count"] == 0
    assert d["unregistered_offline_backup_may_still_exist"] is True
    assert d["historic_containers"]["twenty-crm"]["currently_registered"] is False
    assert d["historic_containers"]["listmonk-mail"]["currently_registered"] is False
    assert d["services_started"] is False


def test_lxd_instance_names_report_only_not_as_recovered_database():
    d = audit(runner=runner_with([
        {"name": "twenty-crm", "status": "Stopped"},
        {"name": "listmonk-mail", "status": "Stopped"},
    ], [{"name": "default"}]))
    assert d["state"] == "NAMED_INSTANCES_REQUIRE_ORIGINAL_DATA_REVIEW"
    assert d["historic_containers"]["twenty-crm"]["currently_registered"] is True
    assert d["original_database_backup_restored"] is False
    assert d["original_customer_records_verified"] is False
    assert d["outbound_authorized"] is False


def test_lxd_permission_error_fails_closed_without_secrets():
    class Fail:
        returncode = 1
        stdout = ""
        stderr = "do-not-expose-secret"
    d = audit(runner=lambda *args, **kwargs: Fail())
    assert d["state"] == "HOLD_LXD_METADATA_UNAVAILABLE"
    assert "secret" not in json.dumps(d)
    assert d["canonical_empiredb_writes"] is False


def test_backup_inventory_only_names_not_database_contents(tmp_path):
    (tmp_path / "twenty-crm.tar.gz").write_bytes(b"SIMULATED-PRIVATE")
    (tmp_path / "listmonk-mail.tar.zst").write_bytes(b"SIMULATED-PRIVATE")
    r = inspect_backup_metadata(roots=(tmp_path,))
    assert r["state"] == "BACKUP_NAMES_REVIEWED_NO_CONTENT_VERIFICATION"
    assert {x["matched_basename"] for x in r["matched_names"]} == {
        "twenty-crm.tar.gz", "listmonk-mail.tar.zst"
    }
    assert r["old_db_backup_content_verified"] is False
    assert "SIMULATED-PRIVATE" not in json.dumps(r)
    assert r["restoration_authorized"] is False


def test_missing_backup_root_does_not_prove_deleted(tmp_path):
    r = inspect_backup_metadata(roots=(tmp_path / "missing",))
    assert r["sources"][0]["present"] is False
    assert r["old_twenty_workspace_verified"] is False
    assert r["old_listmonk_subscribers_verified"] is False
