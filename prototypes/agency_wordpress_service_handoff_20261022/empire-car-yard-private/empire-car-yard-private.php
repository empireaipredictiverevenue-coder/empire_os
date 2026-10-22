<?php
/**
 * Plugin Name: Empire Car Yard — Private Capability Prototype
 * Description: Private vehicle inventory and synthetic repair-slot gate. No public booking, payment, mail or contact collection.
 * Version: 0.1.0
 * Requires at least: 6.5
 * Requires PHP: 8.1
 * License: Proprietary research prototype
 * Text Domain: empire-car-yard-private
 */
if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

const EMPIRE_CAR_YARD_RESEARCH_ONLY = true;
const EMPIRE_CAR_YARD_RESOURCE = 'repair-bay-1';

add_action( 'init', 'empire_car_yard_register_types' );
add_action( 'init', 'empire_car_yard_register_meta' );
add_action( 'rest_api_init', 'empire_car_yard_register_routes' );

/**
 * Private administrative post types; the visitor-facing routes remain OFF.
 */
function empire_car_yard_admin_capabilities() {
    $names = array(
        // Keep WordPress meta caps (edit_post/read_post/delete_post) distinct.
        // Mapping those to manage_options overwrites the primitive cap map.
        'edit_posts', 'edit_others_posts',
        'publish_posts', 'read_private_posts', 'delete_posts', 'delete_others_posts',
        'delete_private_posts', 'delete_published_posts', 'edit_private_posts',
        'edit_published_posts', 'create_posts',
    );
    return array_fill_keys( $names, 'manage_options' );
}

function empire_car_yard_register_types() {
    register_post_type( 'empire_vehicle', array(
        'labels'              => array( 'name' => 'Car Yard Vehicles', 'singular_name' => 'Vehicle' ),
        'description'         => 'Research-only vehicle inventory. No customer records.',
        'public'              => false,
        'show_ui'             => true,
        'show_in_rest'        => true,
        'publicly_queryable'  => false,
        'exclude_from_search' => true,
        'supports'            => array( 'title', 'editor', 'thumbnail' ),
        'capability_type'     => 'post',
        'capabilities'        => empire_car_yard_admin_capabilities(),
        'map_meta_cap'        => true,
        'menu_icon'           => 'dashicons-car',
    ) );
    register_post_type( 'empire_repair', array(
        'labels'              => array( 'name' => 'Private Repair Slots', 'singular_name' => 'Repair Slot' ),
        'description'         => 'Synthetic staff-only repair slots; no customer booking.',
        'public'              => false,
        'show_ui'             => true,
        'show_in_rest'        => false,
        'publicly_queryable'  => false,
        'exclude_from_search' => true,
        'supports'            => array( 'title' ),
        'capability_type'     => 'post',
        'capabilities'        => empire_car_yard_admin_capabilities(),
        'map_meta_cap'        => true,
    ) );
}

function empire_car_yard_register_meta() {
    $fields = array(
        'empire_year'         => array( 'type' => 'integer', 'sanitize_callback' => 'absint' ),
        'empire_price_aud'    => array( 'type' => 'number', 'sanitize_callback' => 'empire_car_yard_sanitize_price' ),
        'empire_stock_status' => array(
            'type' => 'string',
            'sanitize_callback' => 'empire_car_yard_sanitize_stock_status',
        ),
    );
    foreach ( $fields as $name => $field ) {
        register_post_meta( 'empire_vehicle', $name, array(
            'single'            => true,
            'show_in_rest'      => true,
            'type'              => $field['type'],
            'sanitize_callback' => $field['sanitize_callback'],
            'auth_callback'     => static function () {
                return current_user_can( 'manage_options' );
            },
        ) );
    }
}

function empire_car_yard_sanitize_price( $value, $meta_key = null, $object_type = null, $object_subtype = null ) {
    if ( ! is_numeric( $value ) ) {
        return 0.0;
    }
    $amount = (float) $value;
    return is_finite( $amount ) && $amount >= 0 && $amount <= 100000000 ? $amount : 0.0;
}

function empire_car_yard_sanitize_stock_status( $value ) {
    $allowed = array( 'available', 'reserved', 'sold', 'archived' );
    return is_string( $value ) && in_array( $value, $allowed, true ) ? $value : 'archived';
}

/**
 * Pure strict date + availability validation.
 *
 * Only a fictional one-bay Australian business schedule is modeled.
 * Actual holidays, real staff availability and customer acceptance are OFF.
 *
 * @return array|WP_Error UTC second timestamps or a validation error.
 */
function empire_car_yard_validate_interval( $start, $end, $time_zone = 'Australia/Sydney' ) {
    if ( ! is_string( $start ) || ! is_string( $end ) ||
         ! preg_match( '/^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(Z|[+-]\\d{2}:\\d{2})$/', $start ) ||
         ! preg_match( '/^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(Z|[+-]\\d{2}:\\d{2})$/', $end ) ) {
        return new WP_Error( 'empire_datetime', 'ISO-8601 timestamps with explicit UTC offset required.', array( 'status' => 400 ) );
    }
    if ( $time_zone !== 'Australia/Sydney' ) {
        return new WP_Error( 'empire_zone', 'Prototype supports Australia/Sydney only.', array( 'status' => 400 ) );
    }
    try {
        $a = new DateTimeImmutable( $start );
        $b = new DateTimeImmutable( $end );
        $zone = new DateTimeZone( $time_zone );
    } catch ( Exception $e ) {
        return new WP_Error( 'empire_datetime', 'Invalid calendar dates.', array( 'status' => 400 ) );
    }
    $local_a = $a->setTimezone( $zone );
    $local_b = $b->setTimezone( $zone );
    if ( $a->getOffset() !== $local_a->getOffset() || $b->getOffset() !== $local_b->getOffset() ) {
        return new WP_Error( 'empire_offset', 'Requested offset does not match Sydney daylight-saving rules.', array( 'status' => 400 ) );
    }
    if ( $a->format( 'Y-m-d\TH:i:sP' ) !== str_replace( 'Z', '+00:00', $start ) ||
         $b->format( 'Y-m-d\TH:i:sP' ) !== str_replace( 'Z', '+00:00', $end ) ) {
        return new WP_Error( 'empire_calendar', 'Invalid or normalised calendar timestamp.', array( 'status' => 400 ) );
    }
    $diff = $b->getTimestamp() - $a->getTimestamp();
    if ( $diff < 1800 || $diff > 10800 || $diff % 900 !== 0 ) {
        return new WP_Error( 'empire_duration', 'Slots must be 30–180 minutes, in 15-minute increments.', array( 'status' => 400 ) );
    }
    if ( $local_a->format( 'Y-m-d' ) !== $local_b->format( 'Y-m-d' ) ||
         (int) $local_a->format( 'H' ) < 8 ||
         $local_a->format( 'i' ) % 15 !== 0 ||
         (int) $local_b->format( 'H' ) > 18 ||
         ( $local_b->format( 'H:i' ) > '18:00' ) ) {
        return new WP_Error( 'empire_hours', 'Slot must be within fictional 08:00–18:00 local opening hours.', array( 'status' => 400 ) );
    }
    return array(
        'start_ts' => $a->getTimestamp(),
        'end_ts'   => $b->getTimestamp(),
        'time_zone' => $time_zone,
        'resource' => EMPIRE_CAR_YARD_RESOURCE,
    );
}

/** Returns true if any non-cancelled existing booking overlaps the slot. */
function empire_car_yard_slot_conflict( array $candidate, array $existing ) {
    foreach ( $existing as $booking ) {
        if ( ! is_array( $booking ) ) {
            return true; // Fail closed on corrupt booking evidence.
        }
        if ( ( $booking['status'] ?? null ) === 'cancelled' ) {
            continue;
        }
        if ( ! isset( $booking['start_ts'], $booking['end_ts'] ) ||
             ! is_numeric( $booking['start_ts'] ) || ! is_numeric( $booking['end_ts'] ) ) {
            return true;
        }
        if ( $candidate['start_ts'] < (int) $booking['end_ts'] &&
             (int) $booking['start_ts'] < $candidate['end_ts'] ) {
            return true;
        }
    }
    return false;
}

/** No endpoints are public. Staff-only by explicit capability. */
function empire_car_yard_staff_authorized() {
    return current_user_can( 'manage_options' );
}

function empire_car_yard_register_routes() {
    register_rest_route( 'empire-car-yard/v1', '/inventory', array(
        'methods'             => WP_REST_Server::READABLE,
        'permission_callback' => 'empire_car_yard_staff_authorized',
        'callback'            => 'empire_car_yard_inventory',
    ) );
    register_rest_route( 'empire-car-yard/v1', '/repair-slots', array(
        'methods'             => WP_REST_Server::CREATABLE,
        'permission_callback' => 'empire_car_yard_staff_authorized',
        'callback'            => 'empire_car_yard_book_slot',
        'args'                => array(
            'start' => array( 'required' => true, 'type' => 'string' ),
            'end' => array( 'required' => true, 'type' => 'string' ),
        ),
    ) );
    register_rest_route( 'empire-car-yard/v1', '/repair-slots/(?P<id>\\d+)/cancel', array(
        'methods'             => WP_REST_Server::CREATABLE,
        'permission_callback' => 'empire_car_yard_staff_authorized',
        'callback'            => 'empire_car_yard_cancel_slot',
    ) );
}

/** Admin-only preview of inventory; never expose internal vehicle detail on a public route. */
function empire_car_yard_inventory() {
    $posts = get_posts( array(
        'post_type' => 'empire_vehicle',
        'post_status' => array( 'publish', 'draft', 'private' ),
        'numberposts' => 50,
        'orderby' => 'ID',
        'order' => 'ASC',
    ) );
    $result = array();
    foreach ( $posts as $post ) {
        $result[] = array(
            'id' => (int) $post->ID,
            'title' => $post->post_title,
            'stock_status' => empire_car_yard_sanitize_stock_status( get_post_meta( $post->ID, 'empire_stock_status', true ) ),
            'year' => absint( get_post_meta( $post->ID, 'empire_year', true ) ),
            'price_aud' => (float) get_post_meta( $post->ID, 'empire_price_aud', true ),
        );
    }
    return rest_ensure_response( array( 'mode' => 'PRIVATE_RESEARCH_ONLY', 'vehicles' => $result ) );
}

function empire_car_yard_book_slot( WP_REST_Request $request ) {
    $valid = empire_car_yard_validate_interval( $request['start'], $request['end'] );
    if ( is_wp_error( $valid ) ) {
        return $valid;
    }
    if ( $valid['start_ts'] <= time() || $valid['start_ts'] > time() + ( 366 * 86400 ) ) {
        return new WP_Error( 'empire_booking_window', 'Synthetic slot must be future and within 366 days.', array( 'status' => 400 ) );
    }
    // The automatic approval is disabled on the public site. A private
    // admin may create only an internal synthetic bay allocation.
    if ( ! defined( 'EMPIRE_CAR_YARD_SYNTHETIC_TEST' ) || EMPIRE_CAR_YARD_SYNTHETIC_TEST !== true ) {
        return new WP_Error( 'empire_test_only', 'Bookings are disabled outside a synthetic test.', array( 'status' => 403 ) );
    }
    $lock = 'empire_car_yard_private_repair_bay_lock';
    if ( ! add_option( $lock, wp_generate_uuid4(), '', false ) ) {
        return new WP_Error( 'empire_booking_locked', 'An inventory booking check is in progress.', array( 'status' => 409 ) );
    }
    try {
        $posts = get_posts( array(
            'post_type' => 'empire_repair',
            'post_status' => 'private',
            'numberposts' => 201,
        ) );
        if ( count( $posts ) > 200 ) {
            return new WP_Error( 'empire_capacity', 'Maximum bounded synthetic booking count reached.', array( 'status' => 409 ) );
        }
        $existing = array();
        foreach ( $posts as $post ) {
            $existing[] = array(
                'start_ts' => get_post_meta( $post->ID, 'empire_start_utc', true ),
                'end_ts' => get_post_meta( $post->ID, 'empire_end_utc', true ),
                'status' => get_post_meta( $post->ID, 'empire_slot_status', true ),
            );
        }
        if ( empire_car_yard_slot_conflict( $valid, $existing ) ) {
            return new WP_Error( 'empire_slot_conflict', 'Bay is already allocated for this period.', array( 'status' => 409 ) );
        }
        $id = wp_insert_post( array(
            'post_type' => 'empire_repair',
            'post_status' => 'private',
            'post_title' => 'FICTIONAL TEST SLOT '.gmdate( 'Y-m-d H:i', $valid['start_ts'] ),
        ), true );
        if ( is_wp_error( $id ) || ! $id ) {
            return new WP_Error( 'empire_booking_write', 'Could not create synthetic test allocation.', array( 'status' => 500 ) );
        }
        update_post_meta( $id, 'empire_start_utc', $valid['start_ts'] );
        update_post_meta( $id, 'empire_end_utc', $valid['end_ts'] );
        update_post_meta( $id, 'empire_slot_status', 'held' );
        return new WP_REST_Response( array(
            'mode' => 'SYNTHETIC_ADMIN_TEST_ONLY',
            'id' => (int) $id,
            'status' => 'held',
        ), 201 );
    } finally {
        delete_option( $lock );
    }
}

function empire_car_yard_cancel_slot( WP_REST_Request $request ) {
    if ( ! defined( 'EMPIRE_CAR_YARD_SYNTHETIC_TEST' ) || EMPIRE_CAR_YARD_SYNTHETIC_TEST !== true ) {
        return new WP_Error( 'empire_test_only', 'Public bookings are disabled.', array( 'status' => 403 ) );
    }
    $id = absint( $request['id'] );
    if ( ! $id || get_post_type( $id ) !== 'empire_repair' ) {
        return new WP_Error( 'empire_not_found', 'Unknown synthetic slot.', array( 'status' => 404 ) );
    }
    update_post_meta( $id, 'empire_slot_status', 'cancelled' );
    return rest_ensure_response( array( 'id' => $id, 'status' => 'cancelled', 'mode' => 'SYNTHETIC_ADMIN_TEST_ONLY' ) );
}
