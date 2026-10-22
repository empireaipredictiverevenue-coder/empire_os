<?php
/**
 * Disposable WordPress Playground integration proof.
 * No real client, person data, public booking, email or payment.
 */
define( 'EMPIRE_CAR_YARD_SYNTHETIC_TEST', true );
require_once '/wordpress/wp-load.php';
require_once '/wordpress/wp-content/plugins/empire-car-yard-private/empire-car-yard-private.php';
empire_car_yard_register_types();
empire_car_yard_register_meta();

$checks = array();
function empire_probe( $condition, $description ) {
    global $checks;
    $checks[ $description ] = (bool) $condition;
    if ( ! $condition ) {
        fwrite( STDERR, "INTEGRATION FAILED: {$description}\n" );
        exit( 2 );
    }
}

empire_probe( post_type_exists( 'empire_vehicle' ), 'wp_vehicle_registered' );
empire_probe( post_type_exists( 'empire_repair' ), 'wp_repair_registered' );
empire_probe( get_post_type_object( 'empire_vehicle' )->public === false, 'wp_vehicle_nonpublic' );
empire_probe( get_post_type_object( 'empire_repair' )->public === false, 'wp_repair_nonpublic' );
empire_probe( get_post_type_object( 'empire_repair' )->show_in_rest === false, 'repair_cpt_rest_disabled' );

$theme = wp_get_theme( 'empire-local-services' );
empire_probe( $theme->exists(), 'wordpress_theme_discovered' );
switch_theme( 'empire-local-services' );
empire_probe( wp_get_theme()->get_stylesheet() === 'empire-local-services', 'wordpress_theme_activated' );

$admin = get_user_by( 'login', 'admin' );
if ( ! $admin ) {
    $users = get_users( array( 'role' => 'administrator', 'number' => 1 ) );
    $admin = $users[0] ?? false;
}
empire_probe( $admin instanceof WP_User, 'disposable_wp_administrator_exists' );

function empire_request( $method, $route, $data = array() ) {
    $request = new WP_REST_Request( $method, $route );
    $request->set_header( 'X-WP-Nonce', wp_create_nonce( 'wp_rest' ) );
    foreach ( $data as $name => $value ) {
        $request->set_param( $name, $value );
    }
    return rest_do_request( $request );
}

wp_set_current_user( 0 );
empire_probe( empire_car_yard_staff_authorized() === false, 'anonymous_permission_denied' );
$no_inventory = empire_request( 'GET', '/empire-car-yard/v1/inventory' );
empire_probe( $no_inventory->get_status() === 401 || $no_inventory->get_status() === 403, 'anonymous_inventory_rest_denied' );
$no_booking = empire_request( 'POST', '/empire-car-yard/v1/repair-slots', array(
    'start' => '2026-11-02T10:00:00+11:00', 'end' => '2026-11-02T11:00:00+11:00',
) );
empire_probe( $no_booking->get_status() === 401 || $no_booking->get_status() === 403, 'anonymous_book_rest_denied' );

wp_set_current_user( (int) $admin->ID );
empire_probe( empire_car_yard_staff_authorized() === true, 'admin_permission_allowed' );
$editor_id = wp_insert_user( array(
    'user_login' => 'fictional_staff_editor',
    'user_pass' => wp_generate_password( 32 ),
    'role' => 'editor',
) );
empire_probe( ! is_wp_error( $editor_id ) && $editor_id > 0, 'fictional_editor_created' );
wp_set_current_user( (int) $editor_id );
empire_probe( current_user_can( 'edit_posts' ) && ! current_user_can( 'manage_options' ), 'editor_role_lacks_admin_authority' );
empire_probe( ! current_user_can( get_post_type_object( 'empire_vehicle' )->cap->create_posts ), 'editor_cannot_create_private_vehicle' );
$editor_request = empire_request( 'GET', '/empire-car-yard/v1/inventory' );
empire_probe( in_array( $editor_request->get_status(), array(401,403), true ), 'editor_cannot_view_private_vehicle_api' );
wp_set_current_user( (int) $admin->ID );
$vehicle_id = wp_insert_post( array(
    'post_type' => 'empire_vehicle',
    'post_status' => 'private',
    'post_title' => 'SYNTHETIC DEMO — 2020 Vehicle',
    'post_content' => 'No real inventory. No customer details.',
), true );
empire_probe( ! is_wp_error( $vehicle_id ) && $vehicle_id > 0, 'synthetic_vehicle_persisted' );
update_post_meta( $vehicle_id, 'empire_year', 2020 );
update_post_meta( $vehicle_id, 'empire_price_aud', 12500 );
update_post_meta( $vehicle_id, 'empire_stock_status', 'available' );
$inv = empire_request( 'GET', '/empire-car-yard/v1/inventory' );
empire_probe( $inv->get_status() === 200, 'private_inventory_rest_200' );
$inventory = $inv->get_data();
empire_probe( count( $inventory['vehicles'] ) === 1, 'vehicle_inventory_contains_one' );
empire_probe( $inventory['vehicles'][0]['year'] === 2020, 'vehicle_meta_year_roundtrip' );
empire_probe( $inventory['vehicles'][0]['stock_status'] === 'available', 'vehicle_stock_status_roundtrip' );

$good = empire_car_yard_validate_interval( '2026-11-02T10:00:00+11:00', '2026-11-02T11:00:00+11:00' );
empire_probe( is_array( $good ), 'sydney_daylight_time_valid' );
$bad_offset = empire_car_yard_validate_interval( '2026-11-02T10:00:00+10:00', '2026-11-02T11:00:00+10:00' );
empire_probe( is_wp_error( $bad_offset ) && $bad_offset->get_error_code() === 'empire_offset', 'incorrect_sydney_offset_rejected' );
$bad_time = empire_car_yard_validate_interval( '2026-11-02T19:00:00+11:00', '2026-11-02T20:00:00+11:00' );
empire_probe( is_wp_error( $bad_time ), 'out_of_hours_rejected' );
$bad_calendar = empire_car_yard_validate_interval( '2026-02-30T10:00:00+11:00', '2026-02-30T11:00:00+11:00' );
empire_probe( is_wp_error( $bad_calendar ), 'invalid_calendar_date_rejected' );
$past = empire_request( 'POST', '/empire-car-yard/v1/repair-slots', array(
    'start' => '2026-10-20T10:00:00+11:00',
    'end' => '2026-10-20T11:00:00+11:00',
) );
empire_probe( $past->get_status() === 400, 'past_booking_rejected' );
$bad_duration = empire_car_yard_validate_interval( '2026-11-02T10:00:00+11:00', '2026-11-02T10:20:00+11:00' );
empire_probe( is_wp_error( $bad_duration ), 'short_slot_rejected' );

$first = empire_request( 'POST', '/empire-car-yard/v1/repair-slots', array(
    'start' => '2026-11-02T10:00:00+11:00',
    'end' => '2026-11-02T11:00:00+11:00',
) );
empire_probe( $first->get_status() === 201, 'synthetic_booking_created_201' );
$id1 = $first->get_data()['id'];
empire_probe( get_post_type( $id1 ) === 'empire_repair', 'synthetic_booking_wp_post_persisted' );
$overlap = empire_request( 'POST', '/empire-car-yard/v1/repair-slots', array(
    'start' => '2026-11-02T10:30:00+11:00',
    'end' => '2026-11-02T11:30:00+11:00',
) );
empire_probe( $overlap->get_status() === 409, 'overlap_conflict_409' );
$adjacent = empire_request( 'POST', '/empire-car-yard/v1/repair-slots', array(
    'start' => '2026-11-02T11:00:00+11:00',
    'end' => '2026-11-02T11:30:00+11:00',
) );
empire_probe( $adjacent->get_status() === 201, 'adjacent_nonoverlap_created' );
$cancel = empire_request( 'POST', "/empire-car-yard/v1/repair-slots/{$id1}/cancel" );
empire_probe( $cancel->get_status() === 200, 'staff_cancel_rest_200' );
empire_probe( get_post_meta( $id1, 'empire_slot_status', true ) === 'cancelled', 'cancelled_status_persisted' );
$rebook = empire_request( 'POST', '/empire-car-yard/v1/repair-slots', array(
    'start' => '2026-11-02T10:00:00+11:00',
    'end' => '2026-11-02T11:00:00+11:00',
) );
empire_probe( $rebook->get_status() === 201, 'cancelled_slot_can_be_reallocated' );
empire_probe( get_option( 'empire_car_yard_private_repair_bay_lock', false ) === false, 'booking_lock_released' );
add_option( 'empire_car_yard_private_repair_bay_lock', 'fictional-concurrent-holder', '', false );
$locked = empire_request( 'POST', '/empire-car-yard/v1/repair-slots', array(
    'start' => '2026-11-02T13:00:00+11:00',
    'end' => '2026-11-02T14:00:00+11:00',
) );
empire_probe( $locked->get_status() === 409, 'concurrent_booking_lock_blocks_second_request' );
delete_option( 'empire_car_yard_private_repair_bay_lock' );

echo json_encode( array(
    'status' => 'WORDPRESS_PLAYGROUND_REAL_INTEGRATION_PASS',
    'php_version' => PHP_VERSION,
    'wordpress_version' => get_bloginfo( 'version' ),
    'theme_activated' => wp_get_theme()->get_stylesheet(),
    'wordpress_checks_passed' => count( $checks ),
    'checks' => $checks,
    'all_data_synthetic' => true,
    'public_customer_bookings_allowed' => false,
    'public_contact_collection_allowed' => false,
    'customer_deliveries' => 0,
    'crm_writes' => false,
    'production_changes' => false,
), JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES ), "\n";
