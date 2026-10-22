<?php
/** Real WordPress Playground/PHP/SQLite integration contract, isolated fictional fixtures. */
declare(strict_types=1);
define('WP_ENVIRONMENT_TYPE', 'local');
define('EMPIRE_AGENCY_STAGING_INTEGRATIONS_ENABLED', true);
define('EMPIRE_AGENCY_SYNTHETIC_INVENTORY_ONLY', true);
$_SERVER['REQUEST_URI'] = '/wp-json/empire-agency/v1/capabilities';

require_once '/wordpress/wp-load.php';
require_once '/wordpress/wp-admin/includes/plugin.php';

$checks = [];
function verify_bridge(bool $ok, string $label): void {
    global $checks;
    $checks[$label] = $ok;
    if (!$ok) { fwrite(STDERR, "BRIDGE_CHECK_FAILED: $label\n"); exit(5); }
}

$original = activate_plugin('empire-car-yard/empire-car-yard.php');
$bridge = activate_plugin('empire-agency-integration-bridge/empire-agency-integration-bridge.php');
verify_bridge(!is_wp_error($original), 'vehicle_plugin_activation');
verify_bridge(!is_wp_error($bridge), 'bridge_plugin_activation');
verify_bridge(is_plugin_active('empire-agency-integration-bridge/empire-agency-integration-bridge.php'), 'companion_plugin_active');

empire_yard_register_inventory();
verify_bridge(post_type_exists('empire_vehicle'), 'vehicle_cpt_real_wordpress');
verify_bridge(empire_agency_integration_enabled(), 'local_explicit_synthetic_gates');

$admins = get_users(['role' => 'administrator', 'number' => 1]);
$admin = $admins[0] ?? null;
verify_bridge($admin instanceof WP_User, 'synthetic_site_administrator_exists');
wp_set_current_user((int) $admin->ID);

$addVehicle = static function (string $title, string $status, string $postStatus): int {
    $id = wp_insert_post([
        'post_type' => 'empire_vehicle', 'post_title' => $title,
        'post_status' => $postStatus,
        'post_content' => 'Sensitive message that MUST NEVER be in the REST output: private@example.invalid',
    ], true);
    if (is_wp_error($id)) { throw new RuntimeException('Fixture insert failed'); }
    update_post_meta((int)$id, 'yard_make', 'Fictional Motors');
    update_post_meta((int)$id, 'yard_model', 'Test Concept');
    update_post_meta((int)$id, 'yard_year', 2026);
    update_post_meta((int)$id, 'yard_status', $status);
    update_post_meta((int)$id, 'customer_email', 'forbidden@example.invalid');
    return (int)$id;
};
$allowedId = $addVehicle('SYNTHETIC CONNECTOR VEHICLE', 'available', 'publish');
$addVehicle('SYNTHETIC ARCHIVED SECRET', 'archived', 'publish');
$addVehicle('SYNTHETIC DRAFT SECRET', 'available', 'draft');

$routes = rest_get_server()->get_routes();
verify_bridge(isset($routes['/empire-agency/v1/capabilities']), 'capabilities_route_registered');
verify_bridge(isset($routes['/empire-agency/v1/vehicles']), 'inventory_route_registered');

wp_set_current_user(0);
$unauth = rest_do_request(new WP_REST_Request('GET', '/empire-agency/v1/vehicles'));
verify_bridge($unauth->get_status() === 401, 'anonymous_inventory_401');

$editor = wp_insert_user([
    'user_login' => 'fictional_bridge_editor',
    'user_pass' => wp_generate_password(20),
    'role' => 'editor',
]);
verify_bridge(!is_wp_error($editor), 'editor_fixture_created');
wp_set_current_user((int) $editor);
$denied = rest_do_request(new WP_REST_Request('GET', '/empire-agency/v1/vehicles'));
verify_bridge($denied->get_status() === 403, 'editor_inventory_403');

wp_set_current_user((int) $admin->ID);
$get = new WP_REST_Request('GET', '/empire-agency/v1/vehicles');
$get->set_param('limit', 5);
$read = rest_do_request($get);
verify_bridge($read->get_status() === 200, 'admin_inventory_200');
$data = $read->get_data();
verify_bridge(($data['schema'] ?? '') === 'empire.agency.inventory.v1', 'inventory_schema_version');
verify_bridge(count($data['items'] ?? []) === 1, 'only_one_eligible_fictional_vehicle');
$item = $data['items'][0] ?? [];
verify_bridge(($item['id'] ?? 0) === $allowedId, 'correct_vehicle_id');
verify_bridge(($item['fictional'] ?? false) === true, 'fictional_flag_present');
verify_bridge(!array_key_exists('customer_email', $item) && !array_key_exists('content', $item),
    'field_allowlist_excludes_customer_meta_content');
verify_bridge(!str_contains(wp_json_encode($data), 'private@example.invalid')
    && !str_contains(wp_json_encode($data), 'forbidden@example.invalid'),
    'no_synthetic_secret_leak');
verify_bridge(!str_contains(wp_json_encode($data), 'ARCHIVED SECRET')
    && !str_contains(wp_json_encode($data), 'DRAFT SECRET'),
    'no_archived_or_draft_inventory');

$cap = rest_do_request(new WP_REST_Request('GET', '/empire-agency/v1/capabilities'));
verify_bridge($cap->get_status() === 200, 'capabilities_200');
$capData = $cap->get_data();
verify_bridge($capData['writes_available'] === false && $capData['mcp_endpoint_live'] === false,
    'no_mcp_or_write_claim');
verify_bridge($capData['crm_connected'] === false && $capData['payments_connected'] === false,
    'no_live_commercial_connector_claim');

$post = rest_do_request(new WP_REST_Request('POST', '/empire-agency/v1/vehicles'));
verify_bridge($post->get_status() === 404 || $post->get_status() === 405, 'write_http_method_rejected');

$limit = new WP_REST_Request('GET', '/empire-agency/v1/vehicles');
$limit->set_param('limit', 1000);
$invalid = rest_do_request($limit);
verify_bridge($invalid->get_status() === 400 || $invalid->get_status() === 200,
    'unbounded_limit_denied_or_bounded');
if ($invalid->get_status() === 200) {
    verify_bridge((int)$invalid->get_data()['limit'] <= 20, 'limit_capped_to_20');
}

verify_bridge($read->get_headers()['Cache-Control'] === 'private, no-store, max-age=0',
    'private_no_store_cache_header');
verify_bridge($read->get_headers()['X-Robots-Tag'] === 'noindex, nofollow, noarchive',
    'noindex_header');

echo wp_json_encode([
    'status' => 'EMPIRE_AGENCY_WORDPRESS_INTEGRATION_STAGING_PASS',
    'wordpress' => get_bloginfo('version'),
    'php' => PHP_VERSION,
    'checks' => $checks,
    'checks_passed' => count($checks),
    'rest_api_authenticated_only' => true,
    'real_data' => false,
    'mcp_server_live' => false,
    'public_write_route' => false,
    'production_changes' => false,
], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES), "\n";
