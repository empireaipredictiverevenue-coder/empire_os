"""Pin real native WP/MySQL + Chromium + restore evidence to committed source/screenshots."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs/commercial'
RECEIPT = DOCS / 'EMPIRE_CAR_YARD_V03_NATIVE_WP_MYSQL_BROWSER_RESTORE_20261022.json'
CAPTURES = DOCS / 'car_yard_v03_browser_evidence'

def receipt() -> dict:
    return json.loads(RECEIPT.read_text(encoding='utf8'))

def test_real_wp_mysql_browser_e2e_requires_all_successes():
    r = receipt()
    assert r['status'] == 'NATIVE_WORDPRESS_MYSQL_BROWSER_BACKUP_RESTORE_PASS'
    assert r['wordPress_mysql_same_runtime'] is True
    assert r['loopback_only_http'] is True
    assert r['mariadb_unix_socket_only'] is True
    assert r['wordpress_version'] == '6.8.11'
    assert r['php_version'] == '8.5.4'
    assert r['browser_check_count'] == len(r['browser_checks']) == 22
    assert all(value is True for value in r['browser_checks'].values())
    for item in (
        'desktop_home_200','mobile_home_200','desktop_no_horizontal_overflow',
        'mobile_no_horizontal_overflow','mobile_inventory_200','inventory_image_present',
        'admin_login_success','staff_workbench_200','staff_form_present',
        'staff_hold_receipt','staff_hold_listed','staff_confirmation_receipt',
        'staff_cancel_receipt','all_external_browser_requests_blocked',
    ):
        assert r['browser_checks'][item] is True, item
    assert r['responsive']['desktop']['document'] <= r['responsive']['desktop']['window']
    assert r['responsive']['mobile']['window'] == 390
    assert r['responsive']['mobile']['document'] <= 390
    assert r['external_requests_blocked'] == 6
    assert r['synthetic_data_only'] is True
    assert r['production_changes'] is False
    assert r['customer_bookings_enabled'] is False
    assert r['outbound_or_payments_enabled'] is False

def test_database_and_files_backup_restore_independently_read_back():
    r = receipt()
    boot,restored = r['bootstrap'],r['restore_verified']
    assert boot['status'] == 'NATIVE_WP_MYSQL_STAGE_BOOTSTRAP_PASS'
    assert boot['plugin_active'] is True
    assert boot['theme'] == 'empire-local-services'
    assert boot['pages_created'] == 6
    assert boot['native_wpdb_innodb_ready'] is True
    assert restored['status'] == 'NATIVE_WP_MYSQL_RESTORE_PASS'
    assert restored['pages'] >= 6
    assert restored['vehicles'] == 1
    assert restored['booking_rows'] == 1
    assert restored['booking_audit_events'] == 3
    assert len(restored['attachment_sha256']) == 64
    assert restored['active_theme'] == 'empire-local-services'
    assert len(r['backup_sql_sha256']) == len(r['backup_site_tar_sha256']) == 64

def test_screenshots_have_matching_hashes_and_expected_names():
    r = receipt()
    expected = {'home-desktop.png','home-mobile.png','stock-mobile.png','staff-desktop.png'}
    assert set(r['screenshots']) == expected
    for filename,record in r['screenshots'].items():
        path = CAPTURES / filename
        assert path.is_file()
        assert path.stat().st_size == record['bytes']
        assert sha256(path.read_bytes()).hexdigest() == record['sha256']

def test_source_manifest_still_matches_exact_code_that_was_tested():
    r = receipt()
    assert len(r['source_manifest_sha256']) == 4
    for rel,checksum in r['source_manifest_sha256'].items():
        path = ROOT / rel
        assert path.is_file(),rel
        assert sha256(path.read_bytes()).hexdigest() == checksum

def test_disposable_runner_is_explicitly_loopback_and_private():
    script=(ROOT/'scripts/native_wp_v03/run_disposable_native_wp.sh').read_text()
    assert 'mktemp -d /tmp/empire_wp_v03_browser_' in script
    assert 'php_safe -S "127.0.0.1:$port"' in script
    assert '--skip-networking' in script
    assert "trap cleanup EXIT" in script
    assert 'DISABLE_WP_CRON' in script
    assert 'WP_HTTP_BLOCK_EXTERNAL' in script
    assert "rm -rf -- \"$T\"" in script
    assert "test \"$(id -un)\" = ubuntu" in script
    assert 'sudo ' not in script
    assert 'docker ' not in script
    assert 'https://wordpress.org/wordpress-6.8.11.tar.gz' in script
    assert 'wp-config.php' in script
    assert 'mariadb-dump' in script
    assert 'tar -xzf "$T/site-files.tar.gz"' in script

def test_handoff_preserves_design_and_commercial_holds():
    handoff=(DOCS/'EMPIRE_CAR_YARD_V03_NATIVE_BROWSER_RESTORE_HANDOFF_20261022.md').read_text()
    assert 'visually minimal' in handoff
    assert 'client-ready website' in handoff
    assert 'No public repair booking' in handoff
    assert 'No marketplace bid' in handoff
