<?php
/**
 * Plugin Name: Empire Car Yard Internal Prototype
 * Description: Private vehicle inventory and staff-only synthetic booking proof. NOT public/customer ready.
 * Version: 0.1.0
 * Requires at least: 6.5
 * Requires PHP: 8.1
 * Text Domain: empire-car-yard-internal
 */
defined( 'ABSPATH' ) || exit;

if ( ! defined( 'EMPIRE_CAR_YARD_ENABLE_INTERNAL_BOOKINGS' ) ) {
    define( 'EMPIRE_CAR_YARD_ENABLE_INTERNAL_BOOKINGS', false );
}
define( 'EMPIRE_CAR_YARD_SCHEMA_VERSION', '0.1.0' );

/**
 * Only site administrators are granted the custom inventory post capabilities.
 * No customer accounts, public status updates or payments.
 */
function empire_yard_register_vehicle_type() {
    register_post_type(
        'empire_vehicle',
        array(
            'label'               => 'Demo Yard Vehicles',
            'description'         => 'Internal prototype vehicle inventory; not public stock.',
            'public'              => false,
            'publicly_queryable'  => false,
            'exclude_from_search' => true,
            'show_ui'             => true,
            'show_in_menu'        => true,
            'show_in_rest'        => true,
            'has_archive'         => false,
            'rewrite'             => false,
            'capability_type'     => array( 'empire_vehicle', 'empire_vehicles' ),
            'map_meta_cap'        => true,
            'supports'            => array( 'title', 'editor', 'thumbnail', 'revisions' ),
        )
    );
    register_post_meta(
        'empire_vehicle',
        '_empire_stock_status',
        array(
            'single'            => true,
            'type'              => 'string',
            'default'           => 'draft',
            'show_in_rest'      => array(
                'schema' => array(
                    'type' => 'string',
                    'enum' => array( 'draft', 'available', 'reserved', 'sold', 'archived' ),
                    'context' => array( 'edit' ),
                ),
            ),
            'sanitize_callback' => 'sanitize_key',
            'auth_callback'     => static function() { return current_user_can( 'manage_options' ); },
        )
    );
    // Business-only inventory fields; WordPress validates REST schema types.
    foreach ( array(
        '_empire_make' => 'make',
        '_empire_model' => 'model',
        '_empire_stock_code' => 'stock code',
    ) as $key => $description ) {
        register_post_meta( 'empire_vehicle', $key, array(
            'single' => true,
            'type' => 'string',
            'default' => '',
            'show_in_rest' => array(
                'schema' => array(
                    'type' => 'string', 'maxLength' => 80,
                    'context' => array( 'edit' ),
                ),
            ),
            'sanitize_callback' => 'sanitize_text_field',
            'auth_callback' => static function() { return current_user_can( 'manage_options' ); },
        ) );
    }
    register_post_meta( 'empire_vehicle', '_empire_mileage_km', array(
        'single' => true, 'type' => 'integer', 'default' => 0,
        'show_in_rest' => array( 'schema' => array(
            'type' => 'integer', 'minimum' => 0, 'maximum' => 3000000,
            'context' => array( 'edit' ),
        ) ),
        'auth_callback' => static function() { return current_user_can( 'manage_options' ); },
    ) );
    register_post_meta( 'empire_vehicle', '_empire_price_aud_cents', array(
        'single' => true, 'type' => 'integer', 'default' => 0,
        'show_in_rest' => array( 'schema' => array(
            'type' => 'integer', 'minimum' => 0, 'maximum' => 100000000,
            'context' => array( 'edit' ),
        ) ),
        'auth_callback' => static function() { return current_user_can( 'manage_options' ); },
    ) );
    register_post_meta(
        'empire_vehicle',
        '_empire_model_year',
        array(
            'single' => true, 'type' => 'integer', 'default' => 2024,
            'show_in_rest' => array(
                'schema' => array(
                    'type' => 'integer',
                    'minimum' => 1950,
                    'maximum' => 2100,
                    'context' => array( 'edit' ),
                ),
            ),
            'auth_callback' => static function() { return current_user_can( 'manage_options' ); },
        )
    );
}
add_action( 'init', 'empire_yard_register_vehicle_type' );

function empire_yard_activate() {
    empire_yard_register_vehicle_type();
    $admin = get_role( 'administrator' );
    if ( ! $admin ) {
        return;
    }
    foreach ( array(
        'edit_empire_vehicles', 'edit_others_empire_vehicles',
        'edit_private_empire_vehicles', 'edit_published_empire_vehicles',
        'publish_empire_vehicles', 'read_private_empire_vehicles',
        'delete_empire_vehicles', 'delete_others_empire_vehicles',
        'delete_private_empire_vehicles', 'delete_published_empire_vehicles',
    ) as $cap ) {
        $admin->add_cap( $cap );
    }
    require_once ABSPATH . 'wp-admin/includes/upgrade.php';
    global $wpdb;
    $charset = $wpdb->get_charset_collate();
    $bookings = $wpdb->prefix . 'empire_yard_bookings';
    $slots = $wpdb->prefix . 'empire_yard_slots';
    dbDelta( "CREATE TABLE {$bookings} (
id bigint(20) unsigned NOT NULL AUTO_INCREMENT,
resource_key varchar(32) NOT NULL,
start_utc datetime NOT NULL,
end_utc datetime NOT NULL,
status varchar(20) NOT NULL,
service_code varchar(20) NOT NULL,
vehicle_id bigint(20) unsigned NOT NULL,
created_by bigint(20) unsigned NOT NULL,
created_at_utc datetime NOT NULL,
PRIMARY KEY  (id),
KEY resource_start (resource_key,start_utc)
) ENGINE=InnoDB {$charset};" );
    dbDelta( "CREATE TABLE {$slots} (
id bigint(20) unsigned NOT NULL AUTO_INCREMENT,
booking_id bigint(20) unsigned NOT NULL,
resource_key varchar(32) NOT NULL,
slot_utc datetime NOT NULL,
PRIMARY KEY  (id),
UNIQUE KEY resource_slot (resource_key,slot_utc),
KEY booking_id (booking_id)
) ENGINE=InnoDB {$charset};" );
}
register_activation_hook( __FILE__, 'empire_yard_activate' );

require_once __DIR__ . '/includes/class-empire-yard-bookings.php';
add_action( 'rest_api_init', array( 'Empire_Yard_Bookings', 'register_private_routes' ) );
