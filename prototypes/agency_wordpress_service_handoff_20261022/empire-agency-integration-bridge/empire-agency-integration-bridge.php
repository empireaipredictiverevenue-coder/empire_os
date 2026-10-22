<?php
/**
 * Plugin Name: Empire Agency — Integration Contract (Staging Only)
 * Description: Synthetic, read-only agency API contract for authorised development tests. No MCP listener or production connector.
 * Version: 0.1.0
 * Requires at least: 6.5
 * Requires PHP: 8.0
 * License: Proprietary prototype — no production/customer installation
 * Text Domain: empire-agency-integration-bridge
 */
declare(strict_types=1);

if (!defined('ABSPATH')) { exit; }

/**
 * Three independent gates: explicit enable, synthetic-only, and WP local/dev.
 * A connector does not get production/customer records merely from installing.
 */
function empire_agency_integration_enabled(): bool {
    return defined('EMPIRE_AGENCY_STAGING_INTEGRATIONS_ENABLED')
        && EMPIRE_AGENCY_STAGING_INTEGRATIONS_ENABLED === true
        && defined('EMPIRE_AGENCY_SYNTHETIC_INVENTORY_ONLY')
        && EMPIRE_AGENCY_SYNTHETIC_INVENTORY_ONLY === true
        && function_exists('wp_get_environment_type')
        && in_array(wp_get_environment_type(), ['local', 'development'], true);
}

/** WordPress REST handles cookie nonces or HTTPS application passwords. Never roll our own tokens. */
function empire_agency_integration_permission() {
    if (!is_user_logged_in()) {
        return new WP_Error('empire_agency_unauthorized', 'Authentication required.', ['status' => 401]);
    }
    if (!current_user_can('manage_options')) {
        return new WP_Error('empire_agency_forbidden', 'Administrator permission required.', ['status' => 403]);
    }
    return true;
}

function empire_agency_integration_response(array $payload): WP_REST_Response {
    $response = rest_ensure_response($payload);
    $response->header('Cache-Control', 'private, no-store, max-age=0');
    $response->header('X-Robots-Tag', 'noindex, nofollow, noarchive');
    return $response;
}

/** A predictable, bounded GET-only descriptor suitable for a future separate MCP gateway. */
function empire_agency_integration_capabilities(WP_REST_Request $request): WP_REST_Response {
    return empire_agency_integration_response([
        'schema' => 'empire.agency.integration.capabilities.v1',
        'environment' => 'synthetic_staging',
        'site_scope' => 'single_wordpress_site',
        'data_classification' => 'fictional_demonstration_only',
        'authentication' => 'wordpress_rest_authenticated_admin',
        'resource_paths' => [
            '/empire-agency/v1/capabilities',
            '/empire-agency/v1/vehicles',
        ],
        'operations' => ['capabilities:read', 'vehicles:read'],
        'writes_available' => false,
        'mcp_endpoint_live' => false,
        'webhooks_live' => false,
        'crm_connected' => false,
        'payments_connected' => false,
    ]);
}

/** Explicit field allowlist. No email, phone, buyer ID, pricing, arbitrary meta or content. */
function empire_agency_integration_vehicles(WP_REST_Request $request): WP_REST_Response {
    if (!post_type_exists('empire_vehicle')) {
        return empire_agency_integration_response([
            'schema' => 'empire.agency.inventory.v1',
            'environment' => 'synthetic_staging',
            'items' => [],
            'page' => 1,
            'limit' => 10,
            'has_more' => false,
        ]);
    }

    $limit = max(1, min(20, absint($request->get_param('limit') ?: 10)));
    $page = max(1, min(100, absint($request->get_param('page') ?: 1)));

    $query = new WP_Query([
        'post_type' => 'empire_vehicle',
        'post_status' => 'publish',
        'posts_per_page' => $limit,
        'paged' => $page,
        'orderby' => 'ID',
        'order' => 'DESC',
        'no_found_rows' => false,
        'meta_query' => [[
            'key' => 'yard_status',
            'value' => ['available', 'reserved', 'sold'],
            'compare' => 'IN',
        ]],
    ]);

    $items = [];
    foreach ($query->posts as $vehicle) {
        if (!$vehicle instanceof WP_Post) { continue; }
        $id = (int) $vehicle->ID;
        $status = (string) get_post_meta($id, 'yard_status', true);
        if (!in_array($status, ['available', 'reserved', 'sold'], true)) { continue; }
        $items[] = [
            'id' => $id,
            'title' => sanitize_text_field(wp_strip_all_tags($vehicle->post_title)),
            'make' => sanitize_text_field((string) get_post_meta($id, 'yard_make', true)),
            'model' => sanitize_text_field((string) get_post_meta($id, 'yard_model', true)),
            'year' => absint(get_post_meta($id, 'yard_year', true)),
            'odometer_km' => absint(get_post_meta($id, 'yard_odometer_km', true)),
            'fuel' => sanitize_text_field((string) get_post_meta($id, 'yard_fuel', true)),
            'status' => $status,
            'fictional' => true,
        ];
    }
    wp_reset_postdata();

    return empire_agency_integration_response([
        'schema' => 'empire.agency.inventory.v1',
        'environment' => 'synthetic_staging',
        'items' => $items,
        'page' => $page,
        'limit' => $limit,
        'has_more' => $page < (int) $query->max_num_pages,
    ]);
}

function empire_agency_register_integration_routes(): void {
    if (!empire_agency_integration_enabled()) { return; }

    register_rest_route('empire-agency/v1', '/capabilities', [
        'methods' => WP_REST_Server::READABLE,
        'callback' => 'empire_agency_integration_capabilities',
        'permission_callback' => 'empire_agency_integration_permission',
    ]);
    register_rest_route('empire-agency/v1', '/vehicles', [
        'methods' => WP_REST_Server::READABLE,
        'callback' => 'empire_agency_integration_vehicles',
        'permission_callback' => 'empire_agency_integration_permission',
        'args' => [
            'limit' => [
                'default' => 10, 'type' => 'integer',
                'minimum' => 1, 'maximum' => 20,
                'sanitize_callback' => 'absint',
            ],
            'page' => [
                'default' => 1, 'type' => 'integer',
                'minimum' => 1, 'maximum' => 100,
                'sanitize_callback' => 'absint',
            ],
        ],
    ]);
}
add_action('rest_api_init', 'empire_agency_register_integration_routes');
