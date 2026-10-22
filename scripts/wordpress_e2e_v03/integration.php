<?php
/** Genuine WordPress Playground + synthetic V0.3 tests. No HTTP listener. */
declare(strict_types=1);
define('WP_ADMIN', true);
define('EMPIRE_YARD_STAGING_STAFF_UI_ENABLED', true);
$_SERVER['REQUEST_URI'] = '/demo-stock/';
require_once '/wordpress/wp-load.php';
require_once '/wordpress/wp-admin/includes/plugin.php';
$activated = activate_plugin('empire-car-yard/empire-car-yard.php');
$checks = [];
function yard_prove(bool $ok, string $name): void {
    global $checks;
    $checks[$name] = $ok;
    if (!$ok) { fwrite(STDERR, 'V03_CHECK_FAILED: ' . $name . "\n"); exit(3); }
}
yard_prove(!is_wp_error($activated), 'plugin_activation_success');
yard_prove(is_plugin_active('empire-car-yard/empire-car-yard.php'), 'plugin_active_wordpress');
empire_yard_register_inventory();
yard_prove(post_type_exists('empire_vehicle'), 'wordpress_cpt_registered');
$t = get_post_type_object('empire_vehicle');
yard_prove($t->public === false && !$t->publicly_queryable, 'vehicle_nonpublic');
yard_prove($t->show_in_rest === false && $t->exclude_from_search, 'vehicle_private_rest_search');
yard_prove(wp_get_theme('empire-local-services')->exists(), 'theme_discovered');
switch_theme('empire-local-services');
yard_prove(wp_get_theme()->get_stylesheet() === 'empire-local-services', 'theme_activated');
$admins = get_users(['role' => 'administrator', 'number' => 1]);
$admin = $admins[0] ?? null;
yard_prove($admin instanceof WP_User, 'disposable_admin_exists');
wp_set_current_user(0);
yard_prove(!current_user_can('manage_options'), 'anonymous_not_admin');
wp_set_current_user((int) $admin->ID);
yard_prove(current_user_can('manage_options'), 'admin_authorised');
yard_prove(current_user_can($t->cap->edit_posts), 'admin_vehicle_write_capability');
$editor_id = wp_insert_user([
    'user_login' => 'fictional_v03_editor',
    'user_pass' => wp_generate_password(24),
    'role' => 'editor',
]);
yard_prove(!is_wp_error($editor_id) && $editor_id > 0, 'synthetic_editor_created');
wp_set_current_user((int) $editor_id);
yard_prove(!current_user_can($t->cap->edit_posts), 'editor_vehicle_write_denied');
wp_set_current_user((int) $admin->ID);
$id = wp_insert_post([
    'post_type' => 'empire_vehicle', 'post_status' => 'publish',
    'post_title' => 'SYNTHETIC 2020 TEST VEHICLE',
    'post_content' => 'Fictional demo vehicle. No customer details.',
], true);
yard_prove(!is_wp_error($id) && $id > 0, 'vehicle_created_wordpress');
update_post_meta($id, 'yard_make', 'Ford');
update_post_meta($id, 'yard_year', 2020);
update_post_meta($id, 'yard_status', 'available');
yard_prove((int)get_post_meta($id, 'yard_year', true) === 2020, 'vehicle_year_roundtrip');
yard_prove(get_post_meta($id, 'yard_status', true) === 'available', 'vehicle_status_roundtrip');
wp_set_current_user(0);
$html = empire_yard_inventory_shortcode();
yard_prove(str_contains($html, 'SYNTHETIC 2020 TEST VEHICLE'), 'anonymous_inventory_demo_visible');
yard_prove(str_contains($html, 'Fictional demonstration inventory'), 'fictional_disclosure_present');
wp_set_current_user((int)$admin->ID);
update_post_meta($id, 'yard_status', 'archived');
yard_prove(!str_contains(empire_yard_inventory_shortcode(), 'SYNTHETIC 2020 TEST VEHICLE'), 'archived_hidden');
update_post_meta($id, 'yard_status', 'available');
$_GET['yard_vehicle'] = (string)$id;
wp_set_current_user(0);
yard_prove(str_contains(empire_yard_inventory_shortcode(), 'SYNTHETIC 2020 TEST VEHICLE'), 'vehicle_detail_visible');
unset($_GET['yard_vehicle']);
wp_set_current_user((int)$admin->ID);
yard_prove(class_exists('Empire_Yard_Booking_Store'), 'booking_store_loaded');
yard_prove(class_exists('Empire_Yard_Staff_UI'), 'staff_ui_loaded');
yard_prove(has_action('admin_post_empire_yard_staff_hold', [Empire_Yard_Staff_UI::class, 'hold']) !== false, 'staging_admin_hold_hook');
yard_prove(has_action('admin_post_empire_yard_staff_transition', [Empire_Yard_Staff_UI::class, 'transition']) !== false, 'staging_admin_transition_hook');
yard_prove(!has_action('admin_post_nopriv_empire_yard_staff_hold'), 'anonymous_submission_hook_absent');
global $wpdb;
$store = new Empire_Yard_Booking_Store($wpdb);
yard_prove($store->ready() === false, 'sqlite_innodb_gate_denied');
ob_start();
Empire_Yard_Staff_UI::page();
$screen = (string)ob_get_clean();
yard_prove(str_contains($screen, 'Changes disabled'), 'staff_screen_fail_closed_warning');
yard_prove(!str_contains($screen, 'Create staff-only hold'), 'staff_form_hidden_without_mysql');
yard_prove(str_contains($screen, 'Database not verified'), 'staff_no_unverified_db_query');
echo json_encode([
    'status' => 'EMPIRE_V03_WORDPRESS_REAL_PHP_PASS',
    'wordpress' => get_bloginfo('version'), 'php' => PHP_VERSION,
    'theme' => wp_get_theme()->get_stylesheet(),
    'checks' => $checks, 'count' => count($checks),
    'mysql_concurrency_tested' => false,
    'browser_rendered' => false, 'production_changes' => false
], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES), "\n";
