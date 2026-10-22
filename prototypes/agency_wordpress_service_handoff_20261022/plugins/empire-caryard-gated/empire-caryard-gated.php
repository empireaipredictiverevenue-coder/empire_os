<?php
/**
 * Plugin Name: Empire Car-Yard Capability Demo
 * Description: Development-only inventory and administrator-held repair slots. Does not accept public customer bookings.
 * Version: 0.1.0
 * Requires at least: 6.5
 * Requires PHP: 8.1
 * License: GPL-2.0-or-later
 * Text Domain: empire-caryard-gated
 *
 * CRITICAL: Research prototype ONLY. Installation, activation and all
 * plugin database migrations need separate owner approval on a disposable
 * WordPress test instance. Never install this on production Empire AI.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

define( 'EACY_DEMO_VERSION', '0.1.0' );
define( 'EACY_DEMO_PLUGIN_FILE', __FILE__ );

require_once __DIR__ . '/includes/class-eacy-vehicles.php';
require_once __DIR__ . '/includes/class-eacy-repair-slots.php';

add_action( 'init', array( 'EACY_Vehicles', 'register' ) );
add_action( 'init', array( 'EACY_Vehicles', 'register_meta' ) );
add_action( 'init', array( 'EACY_Vehicles', 'register_shortcode' ) );
add_action( 'rest_api_init', array( 'EACY_Repair_Slots', 'register_routes' ) );
register_activation_hook( __FILE__, array( 'EACY_Repair_Slots', 'activate_schema' ) );
