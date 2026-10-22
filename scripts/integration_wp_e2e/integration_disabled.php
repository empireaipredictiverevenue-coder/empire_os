<?php
/** Real WordPress default: companion endpoints must not even be registered. */
declare(strict_types=1);
define('WP_ENVIRONMENT_TYPE','local');
$_SERVER['REQUEST_URI'] = '/wp-json/';
require_once '/wordpress/wp-load.php';
require_once '/wordpress/wp-admin/includes/plugin.php';
$result = activate_plugin('empire-agency-integration-bridge/empire-agency-integration-bridge.php');
if (is_wp_error($result) || empire_agency_integration_enabled()) {
    fwrite(STDERR, "BRIDGE_DISABLED_GATE_FAILURE\n"); exit(4);
}
$routes = rest_get_server()->get_routes();
if (isset($routes['/empire-agency/v1/capabilities']) ||
    isset($routes['/empire-agency/v1/vehicles'])) {
    fwrite(STDERR, "BRIDGE_DISABLED_ROUTE_EXPOSED\n"); exit(5);
}
$attempt = rest_do_request(new WP_REST_Request('GET','/empire-agency/v1/capabilities'));
if ($attempt->get_status() !== 404) {
    fwrite(STDERR, "BRIDGE_DISABLED_REQUEST_NOT_404\n"); exit(6);
}
echo json_encode([
    'status'=>'EMPIRE_AGENCY_INTEGRATIONS_DISABLED_BY_DEFAULT_PASS',
    'wordPress_real'=>true,'endpoint_registered'=>false,'status_code'=>404,
    'network_access'=>false,'production_changes'=>false
]),"\n";
