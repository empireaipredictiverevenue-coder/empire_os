<?php
/**
 * Repair-slot conflict prevention for isolated administrator QA only.
 *
 * THIS DOES NOT TAKE CUSTOMER BOOKINGS OR CONTACT DATA. All REST endpoints
 * are admin-only, and disabled unless a developer explicitly sets
 * EACY_DEMO_ADMIN_SLOT_TEST_ENABLED=true on an authorised disposable WP site.
 */
if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

final class EACY_Repair_Slots {
    private const MAX_DAYS_AHEAD = 14;

    private static function table_name(): string {
        global $wpdb;
        // WordPress prefixes are validated by core configuration.
        return $wpdb->prefix . 'eacy_repair_slot_locks';
    }

    public static function activate_schema(): void {
        global $wpdb;
        require_once ABSPATH . 'wp-admin/includes/upgrade.php';

        $table = self::table_name();
        $collate = $wpdb->get_charset_collate();
        // Unique slot_start_utc is the concurrency/duplicate reservation
        // invariant. A SELECT-then-INSERT check is deliberately not used.
        $sql = "CREATE TABLE {$table} (
            id bigint(20) unsigned NOT NULL AUTO_INCREMENT,
            slot_start_utc datetime NOT NULL,
            status varchar(20) NOT NULL,
            created_at_utc datetime NOT NULL,
            PRIMARY KEY  (id),
            UNIQUE KEY unique_slot_start (slot_start_utc)
        ) {$collate};";
        dbDelta( $sql );
    }

    public static function admin_test_enabled(): bool {
        return defined( 'EACY_DEMO_ADMIN_SLOT_TEST_ENABLED' )
            && EACY_DEMO_ADMIN_SLOT_TEST_ENABLED === true;
    }

    public static function can_test_slot(): bool {
        // WP REST cookie authentication requires a valid REST nonce,
        // plus this explicit capability and administrator demo opt-in.
        return self::admin_test_enabled() && current_user_can( 'manage_options' );
    }

    public static function register_routes(): void {
        register_rest_route(
            'empire-caryard-demo/v1',
            '/admin-slot-hold',
            array(
                'methods' => 'POST',
                'callback' => array( __CLASS__, 'hold_slot' ),
                'permission_callback' => array( __CLASS__, 'can_test_slot' ),
                'args' => array(
                    'slot_start_utc' => array(
                        'required' => true,
                        'type' => 'string',
                        'sanitize_callback' => 'sanitize_text_field',
                    ),
                ),
            )
        );
        register_rest_route(
            'empire-caryard-demo/v1',
            '/admin-slot-count',
            array(
                'methods' => 'GET',
                'callback' => array( __CLASS__, 'slot_count' ),
                'permission_callback' => array( __CLASS__, 'can_test_slot' ),
            )
        );
    }

    /**
     * Accept YYYY-MM-DD HH:MM:SS strictly in UTC; no client locale/DST
     * ambiguity. These are invented administrator-held test slots, not a
     * real workshop calendar or promises of dealer availability.
     */
    public static function validate_test_slot( $raw ) {
        if ( ! is_string( $raw ) ||
            ! preg_match( '/^\\d{4}-\\d{2}-\\d{2} (?:0[9]|1[0-6]):(?:00|30):00$/D', $raw )
        ) {
            return new WP_Error( 'eacy_slot_format', 'Invalid UTC demo slot.', array( 'status' => 400 ) );
        }

        $zone = new DateTimeZone( 'UTC' );
        $slot = DateTimeImmutable::createFromFormat( '!Y-m-d H:i:s', $raw, $zone );
        if ( false === $slot || $slot->format( 'Y-m-d H:i:s' ) !== $raw ) {
            return new WP_Error( 'eacy_slot_date', 'Invalid UTC demo date.', array( 'status' => 400 ) );
        }

        $now = new DateTimeImmutable( 'now', $zone );
        // Testing only in the future, within fourteen days. No on-site
        // working hours or workshop time-zone are implied by UTC.
        if ( $slot <= $now->modify( '+30 minutes' ) ||
            $slot > $now->modify( '+' . self::MAX_DAYS_AHEAD . ' days' )
        ) {
            return new WP_Error( 'eacy_slot_horizon', 'Outside permitted demo horizon.', array( 'status' => 400 ) );
        }
        return $slot;
    }

    public static function hold_slot( WP_REST_Request $request ) {
        if ( ! self::can_test_slot() ) {
            return new WP_Error( 'eacy_disabled', 'Demo slot tests are disabled.', array( 'status' => 403 ) );
        }
        $slot = self::validate_test_slot( $request->get_param( 'slot_start_utc' ) );
        if ( is_wp_error( $slot ) ) {
            return $slot;
        }

        global $wpdb;
        $table = self::table_name();
        $utc = $slot->format( 'Y-m-d H:i:s' );
        $created = gmdate( 'Y-m-d H:i:s' );

        // Atomic UNIQUE KEY enforces one slot even under concurrent admin
        // test requests. Does not read/store contact names or emails.
        $affected = $wpdb->query(
            $wpdb->prepare(
                "INSERT IGNORE INTO {$table} (slot_start_utc, status, created_at_utc) VALUES (%s, %s, %s)",
                $utc,
                'admin_demo_hold',
                $created
            )
        );

        if ( false === $affected ) {
            return new WP_Error( 'eacy_db_unavailable', 'Demo storage not available.', array( 'status' => 503 ) );
        }
        if ( 0 === $affected ) {
            return new WP_Error( 'eacy_conflict', 'Demo slot already held.', array( 'status' => 409 ) );
        }
        if ( 1 !== $affected ) {
            return new WP_Error( 'eacy_db_unknown', 'Unexpected slot result.', array( 'status' => 503 ) );
        }
        return new WP_REST_Response(
            array(
                'slot_start_utc' => $utc,
                'admin_demo_hold_recorded' => true,
                'customer_booking_accepted' => false,
                'contact_data_stored' => false,
                'real_availability_proven' => false,
            ),
            201
        );
    }

    public static function slot_count() {
        if ( ! self::can_test_slot() ) {
            return new WP_Error( 'eacy_disabled', 'Demo slot tests are disabled.', array( 'status' => 403 ) );
        }
        global $wpdb;
        $table = self::table_name();
        // Admin-only aggregate observation without exporting row identity.
        $count = $wpdb->get_var( "SELECT COUNT(*) FROM {$table}" );
        if ( null === $count ) {
            return new WP_Error( 'eacy_db_unavailable', 'Demo database not available.', array( 'status' => 503 ) );
        }
        return new WP_REST_Response(
            array(
                'admin_demo_slot_holds' => absint( $count ),
                'customer_bookings' => 0,
                'public_booking_endpoint_enabled' => false,
            ),
            200
        );
    }
}
