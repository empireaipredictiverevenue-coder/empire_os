"""Offline static/security checks; never claim these simulate live WordPress."""
from pathlib import Path
import subprocess
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'prototypes/agency_wordpress_service_handoff_20261022/empire-car-yard'
MAIN = SOURCE / 'empire-car-yard.php'
RULES = SOURCE / 'includes/class-empire-yard-booking-rules.php'


def test_plugin_structure_and_api_contract():
    text = MAIN.read_text()
    assert 'Plugin Name: Empire Car Yard' in text
    assert "register_post_type('empire_vehicle'" in text
    assert "'public' => false" in text
    assert "'publicly_queryable' => false" in text
    assert "'show_in_rest' => false" in text
    assert "'exclude_from_search' => true" in text
    assert "'capabilities' => empire_yard_capabilities()" in text
    assert "'auth_callback'" in text
    assert "current_user_can('manage_options')" in text
    assert "wp_verify_nonce(" in text
    assert "wp_unslash(" in text
    assert "sanitize_text_field(" in text
    assert "esc_html(" in text and "esc_attr(" in text and "esc_url(" in text
    assert "add_shortcode('empire_car_yard_inventory'" in text
    assert "'post_status' => 'publish'" in text
    assert "'compare' => 'IN'" in text
    assert "'yard_status'" in text


def test_booking_is_pure_offline_rules_not_activated_publicly():
    main = MAIN.read_text()
    rules = RULES.read_text()
    for forbidden in ('admin_post_', 'wp_ajax_', 'rest_api_init', 'register_rest_route', 'wp_mail(', 'wp_insert_post(', '$wpdb->insert', 'wp_remote_post(', 'payment', 'stripe', 'usdt'):
        assert forbidden not in main.lower(), forbidden
    assert 'No customer-submission endpoint exists' in main
    assert 'not wired to public or admin writes' in main
    assert 'getTransitions' in rules
    assert 'Ambiguous DST local time' in rules
    assert 'ACTIVE' in rules
    assert 'canTransition' in rules


def test_php_is_parseable_where_cli_is_authorised_and_available():
    import shutil
    php = shutil.which('php')
    if php is None:
        return  # reported as not run separately; never assert PHP execution took place
    for path in (MAIN, RULES):
        run = subprocess.run([php, '-l', str(path)], text=True, capture_output=True)
        assert run.returncode == 0, run.stderr


def test_package_is_small_and_contains_only_non_executable_source_files(tmp_path):
    from scripts.package_empire_car_yard_20261022 import package
    output = tmp_path / 'empire-car-yard.zip'
    manifest = package(SOURCE, output)
    assert manifest['status'] == 'OFFLINE_CAR_YARD_PLUGIN_SOURCE_ONLY'
    assert manifest['booking_persistence_implemented'] is False
    assert manifest['live_wordpress_verified'] is False
    assert manifest['production_changes'] is False
    with ZipFile(output) as z:
        assert set(z.namelist()) == {
            'empire-car-yard/empire-car-yard.php',
            'empire-car-yard/includes/class-empire-yard-booking-rules.php',
        }
    assert package(SOURCE, tmp_path / 'second.zip')['sha256'] == manifest['sha256']


def test_packager_denies_duplicate_destination(tmp_path):
    import pytest
    from scripts.package_empire_car_yard_20261022 import package
    destination = tmp_path / 'vehicle.zip'
    package(SOURCE, destination)
    with pytest.raises(ValueError, match='overwrite'):
        package(SOURCE, destination)
