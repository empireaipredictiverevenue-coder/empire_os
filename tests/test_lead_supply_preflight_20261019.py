"""Read-only census deployment preflight: no secret or authority escalation."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json

from scripts.preflight_lead_supply_census_20261019 import (
    preflight, validate_reader_identity,
)

NOW = datetime(2026, 10, 19, 11, 0, tzinfo=timezone.utc)


def tree(tmp_path, *, observed="2026-10-19T10:55:00Z", canonical=True):
    for filename in (
        "empire_os/lead_supply_intelligence.py",
        "empire_os/lead_territory_mrr_bridge.py",
        "empire_os/lead_territory_supply_join.py",
        "empire_os/lead_scoring_inventory_bridge.py",
        "scripts/report_niche_lead_supply_empiredb.py",
    ):
        p = tmp_path / filename
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# code")
    path = tmp_path / "runtime/commercial_exchange/latest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "canonical_backend": "empiredb" if canonical else "legacy",
        "source": "canonical_empiredb_projection",
        "observed_at": observed,
    }))
    return tmp_path


class AuthorizedLease:
    def count(self, table):
        return 0

    def query(self, table, columns, **kwargs):
        assert kwargs["limit"] == 0
        assert columns
        return []


class DeniedLease(AuthorizedLease):
    def count(self, table):
        if table == "prospect_acquisitions":
            raise PermissionError("insufficient_privilege")
        return 0


class Provider:
    def __init__(self, lease):
        self.lease = lease
        self.opens = 0

    @contextmanager
    def read_only_snapshot(self):
        self.opens += 1
        yield self.lease


def test_preflight_default_never_opens_database(tmp_path):
    report = preflight(tree(tmp_path), now=NOW)
    assert report["source_tree_ready"]
    assert report["exchange_snapshot_canonical"]
    assert report["exchange_snapshot_age_seconds"] == 300
    assert report["release_readiness"] == "CODE_ONLY_DB_ACCESS_NOT_CHECKED"
    assert not report["database_reader_role_verified"]


def test_readonly_capability_probe_checks_exact_columns(tmp_path):
    provider = Provider(AuthorizedLease())
    report = preflight(
        tree(tmp_path), now=NOW, provider=provider, probe_database=True,
        security_audit={"proven": True},
    )
    assert report["release_readiness"] == (
        "READONLY_READER_CAPABILITY_READY_FOR_FOUNDER_REVIEW"
    )
    assert provider.opens == 7
    assert all(report["required_table_readable"].values())
    assert all(report["optional_table_readable"].values())
    assert not report["census_execution_authorized"]
    assert not report["database_mutation"]
    assert not report["secret_material_printed"]


def test_required_privilege_denial_fails_preflight(tmp_path):
    report = preflight(
        tree(tmp_path), now=NOW,
        provider=Provider(DeniedLease()), probe_database=True,
        security_audit={"proven": True},
    )
    assert report["missing_required_privilege"]
    assert not report["database_reader_role_verified"]
    assert report["reader_error_classes"]["prospect_acquisitions"] == "PermissionError"
    assert report["release_readiness"] == "HOLD_REVIEW_FAILED_PRECONDITION"


def test_stale_exchange_fails_probe_without_any_financial_change(tmp_path):
    report = preflight(
        tree(tmp_path, observed="2026-09-22T00:00:00Z"),
        now=NOW, provider=Provider(AuthorizedLease()), probe_database=True,
        security_audit={"proven": True},
    )
    assert not report["exchange_snapshot_fresh_30min"]
    assert report["release_readiness"] == "HOLD_REVIEW_FAILED_PRECONDITION"


def test_legacy_backend_snapshot_is_not_accepted(tmp_path):
    report = preflight(tree(tmp_path, canonical=False), now=NOW)
    assert not report["exchange_snapshot_canonical"]


def test_dedicated_reader_identity_rejects_admin_and_nonlocal_connections():
    good = ("host=127.0.0.1 dbname=empiredb "
            "user=empire_lead_supply_reader_login password=secret")
    assert validate_reader_identity(good)[0] is True
    assert validate_reader_identity(good.replace(
        "empire_lead_supply_reader_login", "postgres"
    )) == (False, "NONDEDICATED_READER_LOGIN")
    assert validate_reader_identity(good.replace(
        "127.0.0.1", "remote.example"
    )) == (False, "NONLOCAL_DATABASE_ENDPOINT")
    assert validate_reader_identity(good.replace(
        "dbname=empiredb", "dbname=wrong_database"
    )) == (False, "NONCANONICAL_DATABASE")
    assert validate_reader_identity("not valid conn info")[0] is False


def test_rls_reader_scope_not_proven_holds_release(tmp_path):
    report = preflight(
        tree(tmp_path), now=NOW, provider=Provider(AuthorizedLease()),
        probe_database=True, security_audit={"proven": False},
    )
    assert report["database_reader_role_verified"] is True
    assert report["dedicated_reader_rls_and_write_scope_verified"] is False
    assert report["release_readiness"] == "HOLD_REVIEW_FAILED_PRECONDITION"
