"""Cross-check genuine runtime receipts, hash pins, and safety boundaries."""
from pathlib import Path
from hashlib import sha256
import json

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs/commercial"

def read(name):
    return json.loads((DOCS / name).read_text())

def test_wordpress_playground_real_runtime_receipt_source_pins():
    receipt = read("EMPIRE_CAR_YARD_V03_PLAYGROUND_RUNTIME_20261022.json")
    assert receipt["wordpress_checks_passed"] == 29
    assert len(receipt["checks"]) == 29
    assert all(value is True for value in receipt["checks"].values())
    assert receipt["actual_plugin_activated"] is True
    assert receipt["actual_theme_activated"] is True
    assert receipt["browser_site_editor_mobile_tested"] is False
    assert receipt["mysql_concurrency_tested_in_this_run"] is False
    assert receipt["production_changes"] is False
    assert receipt["crm_or_customer_data_used"] is False
    assert receipt["wordpress"].startswith("6.8.")
    for rel, digest in receipt["source_sha256"].items():
        assert sha256((ROOT / rel).read_bytes()).hexdigest() == digest

def test_real_mysql_two_process_receipt_separate_from_wordpress_integration():
    r = read("EMPIRE_CAR_YARD_V03_MARIADB_CONCURRENCY_20261022.json")
    assert r["status"] == "REAL_MARIADB_TWO_PROCESS_INNODB_CONCURRENCY_PASS"
    assert r["independent_simultaneous_php_processes"] == 2
    assert (r["accepted_attempts"], r["denied_conflicting_attempts"]) == (1, 1)
    assert (r["bookings_after_concurrency"], r["occupied_quarter_hour_slots"]) == (1, 4)
    assert r["audit_events_after_concurrency"] == 1
    assert r["audits_after_cancel_rebook"] == 3
    assert r["cancel_rebook_passed"] is True
    assert r["mysql_tcp_enabled"] is False
    assert r["synthetic_only"] is True
    assert r["production_changes"] is False
    assert r["wordpress_with_mysql_tested"] is False
    assert r["browser_tested"] is False
    for rel, digest in r["source_sha256"].items():
        assert sha256((ROOT / rel).read_bytes()).hexdigest() == digest

def test_mysql_runner_no_privilege_bypass_or_production_socket():
    src = (ROOT / "scripts/run_empire_yard_disposable_mysql_v03_20261022.sh").read_text()
    assert "mktemp -d /tmp/empire_yard_mysql_v03_" in src
    assert "--skip-networking" in src
    assert "--no-defaults" in src
    assert "trap cleanup EXIT" in src
    assert "rm -rf -- \"$T\"" in src
    assert "sudo " not in src
    assert "docker " not in src
    assert "/var/run/docker.sock" not in src
    assert "empiredb" not in src.lower()
    assert "CREATE DATABASE empire_yard_synthetic" in src

def test_release_notes_preserve_commercial_and_browser_holds():
    content = (DOCS / "EMPIRE_CAR_YARD_V03_WORDPRESS_MYSQL_ACCEPTANCE_20261022.md").read_text()
    assert "separate and complementary" in content
    assert "complete WordPress-on-MySQL staff UI has NOT been browser-tested" in content
    assert "backup/export and restore" in content
    assert "No EmpireDB" in content
