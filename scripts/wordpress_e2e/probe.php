<?php
declare(strict_types=1);
require_once '/wordpress/wp-load.php';
require_once '/wordpress/wp-content/plugins/empire-car-yard-private/empire-car-yard-private.php';
empire_car_yard_register_types();
empire_car_yard_register_meta();
$theme = wp_get_theme( 'empire-local-services' );
$valid_slot = empire_car_yard_validate_interval(
    '2026-11-02T10:00:00+11:00',
    '2026-11-02T11:00:00+11:00'
);
echo json_encode( array(
    'wp_version' => get_bloginfo( 'version' ),
    'php_version' => PHP_VERSION,
    'theme_found' => $theme->exists(),
    'theme_name' => $theme->get('Name'),
    'vehicle_type_registered' => post_type_exists( 'empire_vehicle' ),
    'booking_type_registered' => post_type_exists( 'empire_repair' ),
    'slot_validation_passed' => ! is_wp_error( $valid_slot ),
    'no_public_bookings' => ! defined( 'EMPIRE_CAR_YARD_SYNTHETIC_TEST' ),
), JSON_UNESCAPED_SLASHES ), "\n";
