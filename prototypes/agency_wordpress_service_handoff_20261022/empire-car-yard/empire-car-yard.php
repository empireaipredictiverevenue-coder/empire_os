<?php
/**
 * Plugin Name: Empire Car Yard — Private Capability Demo
 * Description: Admin-only synthetic vehicle inventory and booking-rules prototype. No public bookings or notifications.
 * Version: 0.3.0
 * Requires at least: 6.5
 * Requires PHP: 8.0
 * License: Proprietary prototype — do not deploy to customer sites
 * Text Domain: empire-car-yard
 */
declare(strict_types=1);

if (!defined('ABSPATH')) {
    exit;
}

require_once __DIR__ . '/includes/class-empire-yard-booking-rules.php';
require_once __DIR__ . '/includes/class-empire-yard-booking-store.php';

// Disabled by default. Only an explicitly configured staging site may register
// the authenticated WordPress administrator workbench and admin-post handlers.
if (defined('EMPIRE_YARD_STAGING_STAFF_UI_ENABLED') &&
    EMPIRE_YARD_STAGING_STAFF_UI_ENABLED === true && is_admin()) {
    require_once __DIR__ . '/includes/class-empire-yard-staff-ui.php';
}


const EMPIRE_YARD_VEHICLE_FIELDS = ['yard_make', 'yard_model', 'yard_year', 'yard_odometer_km', 'yard_fuel', 'yard_status'];
const EMPIRE_YARD_STATUSES = ['available', 'reserved', 'sold', 'archived'];

/** All inventory writes require administrator authority; no custom roles added. */
function empire_yard_capabilities(): array {
    return [
        'edit_post' => 'manage_options',
        'read_post' => 'read',
        'delete_post' => 'manage_options',
        'edit_posts' => 'manage_options',
        'edit_others_posts' => 'manage_options',
        'publish_posts' => 'manage_options',
        'read_private_posts' => 'manage_options',
        'delete_posts' => 'manage_options',
        'delete_private_posts' => 'manage_options',
        'delete_published_posts' => 'manage_options',
        'delete_others_posts' => 'manage_options',
        'edit_private_posts' => 'manage_options',
        'edit_published_posts' => 'manage_options',
        'create_posts' => 'manage_options',
    ];
}

function empire_yard_register_inventory(): void {
    register_post_type('empire_vehicle', [
        'labels' => ['name' => 'Demo Vehicles', 'singular_name' => 'Demo Vehicle'],
        'public' => false,
        'publicly_queryable' => false,
        'show_ui' => true,
        'show_in_rest' => false,
        'exclude_from_search' => true,
        'has_archive' => false,
        'supports' => ['title', 'editor', 'thumbnail', 'custom-fields'],
        'map_meta_cap' => false,
        'capabilities' => empire_yard_capabilities(),
    ]);

    foreach (EMPIRE_YARD_VEHICLE_FIELDS as $field) {
        $number = in_array($field, ['yard_year', 'yard_odometer_km'], true);
        register_post_meta('empire_vehicle', $field, [
            'type' => $number ? 'integer' : 'string',
            'single' => true,
            'default' => $field === 'yard_status' ? 'archived' : ($number ? 0 : ''),
            'show_in_rest' => false,
            'sanitize_callback' => static function ($value) use ($field) {
                return empire_yard_sanitize($field, $value);
            },
            'auth_callback' => static function (): bool {
                return current_user_can('manage_options');
            },
        ]);
    }
}
add_action('init', 'empire_yard_register_inventory');

/** Invalid visibility always falls back to archived (fail closed). */
function empire_yard_sanitize(string $field, $value) {
    if ($field === 'yard_status') {
        $status = sanitize_key((string) $value);
        return in_array($status, EMPIRE_YARD_STATUSES, true) ? $status : 'archived';
    }
    if ($field === 'yard_year') {
        $year = absint($value);
        return ($year >= 1900 && $year <= 2100) ? $year : 0;
    }
    if ($field === 'yard_odometer_km') {
        return min(absint($value), 9999999);
    }
    return sanitize_text_field((string) $value);
}

function empire_yard_metabox(): void {
    add_meta_box('empire_yard_details', 'Vehicle inventory (fictional demo)', 'empire_yard_render_metabox', 'empire_vehicle', 'normal', 'high');
}
add_action('add_meta_boxes', 'empire_yard_metabox');

function empire_yard_render_metabox(WP_Post $post): void {
    wp_nonce_field('empire_yard_save_vehicle', 'empire_yard_vehicle_nonce');
    $labels = [
        'yard_make' => 'Make', 'yard_model' => 'Model', 'yard_year' => 'Year',
        'yard_odometer_km' => 'Odometer (km)', 'yard_fuel' => 'Fuel / specification',
    ];
    echo '<p>Fictional inventory only. Do not enter real customer or personal data.</p>';
    foreach ($labels as $key => $label) {
        $value = (string) get_post_meta($post->ID, $key, true);
        $type = in_array($key, ['yard_year', 'yard_odometer_km'], true) ? 'number' : 'text';
        echo '<p><label for="' . esc_attr($key) . '">' . esc_html($label) . '</label> ';
        echo '<input id="' . esc_attr($key) . '" name="' . esc_attr($key) . '" type="' . esc_attr($type) . '" value="' . esc_attr($value) . '" /></p>';
    }
    $selected = get_post_meta($post->ID, 'yard_status', true) ?: 'archived';
    echo '<p><label for="yard_status">Inventory status</label> <select id="yard_status" name="yard_status">';
    foreach (EMPIRE_YARD_STATUSES as $status) {
        echo '<option value="' . esc_attr($status) . '" ' . selected($selected, $status, false) . '>' . esc_html(ucfirst($status)) . '</option>';
    }
    echo '</select></p>';
}

function empire_yard_save_vehicle(int $post_id): void {
    if (!isset($_POST['empire_yard_vehicle_nonce']) ||
        !is_string($_POST['empire_yard_vehicle_nonce']) ||
        !wp_verify_nonce(sanitize_text_field(wp_unslash($_POST['empire_yard_vehicle_nonce'])), 'empire_yard_save_vehicle') ||
        (defined('DOING_AUTOSAVE') && DOING_AUTOSAVE) ||
        wp_is_post_revision($post_id) ||
        !current_user_can('manage_options')) {
        return;
    }
    foreach (EMPIRE_YARD_VEHICLE_FIELDS as $field) {
        if (!isset($_POST[$field]) || !is_scalar($_POST[$field])) {
            continue;
        }
        update_post_meta($post_id, $field, empire_yard_sanitize($field, wp_unslash($_POST[$field])));
    }
}
add_action('save_post_empire_vehicle', 'empire_yard_save_vehicle');

/** No customer-submission endpoint exists. Public inventory is read-only. */
function empire_yard_inventory_shortcode(): string {
    $make = isset($_GET['yard_make']) && is_string($_GET['yard_make'])
        ? sanitize_text_field(wp_unslash($_GET['yard_make'])) : '';
    $search = isset($_GET['yard_search']) && is_string($_GET['yard_search'])
        ? sanitize_text_field(wp_unslash($_GET['yard_search'])) : '';
    $detail = isset($_GET['yard_vehicle']) && is_scalar($_GET['yard_vehicle'])
        ? absint($_GET['yard_vehicle']) : 0;
    if ($detail !== 0) {
        $vehicle = get_post($detail);
        if (!$vehicle instanceof WP_Post || $vehicle->post_type !== 'empire_vehicle' ||
            $vehicle->post_status !== 'publish' ||
            !in_array(get_post_meta($detail, 'yard_status', true), ['available', 'reserved', 'sold'], true)) {
            return '<p>Vehicle unavailable.</p>';
        }
        $specs = [];
        foreach (['yard_make', 'yard_model', 'yard_year', 'yard_odometer_km', 'yard_fuel', 'yard_status'] as $field) {
            $specs[] = esc_html((string) get_post_meta($detail, $field, true));
        }
        $photo = has_post_thumbnail($detail) ? wp_kses_post(get_the_post_thumbnail($detail, 'large')) : '';
        return '<article class="empire-yard-detail"><p>Fictional demo vehicle — not for sale.</p><h2>' .
            esc_html(get_the_title($detail)) . '</h2>' . $photo . '<p>' . implode(' · ', $specs) .
            '</p>' . wp_kses_post(wpautop($vehicle->post_content)) . '</article>';
    }
    $page = isset($_GET['yard_page']) && is_scalar($_GET['yard_page'])
        ? max(1, min(100, absint($_GET['yard_page']))) : 1;
    $filters = [[
        'key' => 'yard_status',
        'value' => ['available', 'reserved', 'sold'],
        'compare' => 'IN',
    ]];
    if ($make !== '') {
        $filters[] = ['key' => 'yard_make', 'value' => substr($make, 0, 80), 'compare' => '='];
    }
    $query = new WP_Query([
        'post_type' => 'empire_vehicle',
        'post_status' => 'publish',
        'posts_per_page' => 12,
        'paged' => $page,
        's' => substr($search, 0, 80),
        'meta_query' => $filters,
    ]);
    ob_start();
    echo '<section class="empire-yard-inventory" aria-label="Demo vehicle inventory">';
    echo '<p><strong>Fictional demonstration inventory — not real vehicles for sale.</strong></p>';
    echo '<form method="get"><label>Make <input name="yard_make" value="' . esc_attr($make) . '" /></label> ';
    echo '<label>Search <input name="yard_search" value="' . esc_attr($search) . '" /></label> ';
    echo '<button type="submit">Filter vehicles</button></form>';
    if (!$query->have_posts()) {
        echo '<p>No matching demonstration vehicles.</p>';
    }
    while ($query->have_posts()) {
        $query->the_post();
        $post_id = get_the_ID();
        $fields = [];
        foreach (EMPIRE_YARD_VEHICLE_FIELDS as $field) {
            $fields[$field] = (string) get_post_meta($post_id, $field, true);
        }
        echo '<article><h3><a href="' . esc_url(add_query_arg('yard_vehicle', $post_id)) . '">' . esc_html(get_the_title()) . '</a></h3>';
        if (has_post_thumbnail($post_id)) {
            echo wp_kses_post(get_the_post_thumbnail($post_id, 'medium', ['loading' => 'lazy']));
        }
        echo '<p>' . esc_html(trim($fields['yard_make'] . ' ' . $fields['yard_model'])) . ' — ';
        echo esc_html($fields['yard_year']) . ' — ' . esc_html(ucfirst($fields['yard_status'])) . '</p></article>';
    }
    wp_reset_postdata();
    if ($page > 1) {
        echo '<a href="' . esc_url(add_query_arg('yard_page', $page - 1)) . '">Previous</a> ';
    }
    if ($page < (int) $query->max_num_pages) {
        echo '<a href="' . esc_url(add_query_arg('yard_page', $page + 1)) . '">Next</a>';
    }
    echo '</section>';
    return (string) ob_get_clean();
}
add_shortcode('empire_car_yard_inventory', 'empire_yard_inventory_shortcode');

/** Booking persistence is dormant: no routes, schema install, or UI writes until WP/MySQL staging verification. */
