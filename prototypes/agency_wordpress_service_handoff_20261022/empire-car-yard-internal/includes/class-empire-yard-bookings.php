<?php
/**
 * Staff-only UTC appointment hold engine. No customers, contacts or payments.
 *
 * The reservation operations are DISABLED by default. A future approved
 * disposable WordPress instance must explicitly define
 * EMPIRE_CAR_YARD_ENABLE_INTERNAL_BOOKINGS=true after DB/InnoDB checks.
 */
defined( 'ABSPATH' ) || exit;

final class Empire_Yard_Bookings {
    private const REST = 'empire-yard/v1';
    private const INTERVAL_SECONDS = 1800;
    private const MAX_DURATION_SECONDS = 7200;

    public static function permission(): bool {
        return ( EMPIRE_CAR_YARD_ENABLE_INTERNAL_BOOKINGS === true
            && current_user_can( 'manage_options' ) );
    }

    public static function register_private_routes(): void {
        register_rest_route( self::REST, '/internal/reservations', array(
            array(
                'methods' => WP_REST_Server::READABLE,
                'callback' => array( self::class, 'list_private' ),
                'permission_callback' => array( self::class, 'permission' ),
            ),
            array(
                'methods' => WP_REST_Server::CREATABLE,
                'callback' => array( self::class, 'reserve_private' ),
                'permission_callback' => array( self::class, 'permission' ),
                'args' => array(
                    'resource_key' => array(
                        'required' => true, 'type' => 'string',
                        'validate_callback' => static function( $v ) {
                            return is_string( $v )
                                && (bool) preg_match( '/^bay-[a-z0-9]{1,12}$/D', $v );
                        },
                    ),
                    'service_code' => array(
                        'required' => true, 'type' => 'string',
                        'enum' => array( 'inspection', 'servicing', 'repair' ),
                    ),
                    'starts_at_utc' => array(
                        'required' => true, 'type' => 'string',
                        'validate_callback' => static function( $v ) {
                            return is_string( $v )
                                && (bool) preg_match( '/^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:00Z$/D', $v );
                        },
                    ),
                    'duration_minutes' => array(
                        'required' => true, 'type' => 'integer',
                        'minimum' => 30, 'maximum' => 120,
                    ),
                    'vehicle_id' => array(
                        'required' => false, 'type' => 'integer',
                        'minimum' => 0, 'default' => 0,
                    ),
                ),
            ),
        ) );
        register_rest_route( self::REST, '/internal/reservations/(?P<id>[0-9]+)/cancel', array(
            'methods' => WP_REST_Server::CREATABLE,
            'callback' => array( self::class, 'cancel_private' ),
            'permission_callback' => array( self::class, 'permission' ),
            'args' => array(
                'id' => array( 'required' => true, 'type' => 'integer', 'minimum' => 1 ),
            ),
        ) );
    }

    private static function tables(): array {
        global $wpdb;
        return array(
            $wpdb->prefix . 'empire_yard_bookings',
            $wpdb->prefix . 'empire_yard_slots',
        );
    }

    private static function transactional_engine_ready(): bool {
        global $wpdb;
        foreach ( self::tables() as $table ) {
            $query = $wpdb->prepare(
                'SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s',
                $table
            );
            if ( 'InnoDB' !== $wpdb->get_var( $query ) ) {
                return false;
            }
        }
        return true;
    }

    private static function no_store( $payload, int $http = 200 ) {
        $response = rest_ensure_response( $payload );
        $response->set_status( $http );
        $response->header( 'Cache-Control', 'private, no-store, max-age=0' );
        return $response;
    }

    public static function list_private() {
        global $wpdb;
        if ( ! self::transactional_engine_ready() ) {
            return new WP_Error( 'empire_yard_db_not_ready', 'Internal booking tables unavailable.', array( 'status' => 503 ) );
        }
        list( $bookings ) = self::tables();
        // Return only staff-created internal reservations; no customer PII.
        $rows = $wpdb->get_results(
            "SELECT id, resource_key, start_utc, end_utc, status, service_code, vehicle_id
             FROM {$bookings} ORDER BY start_utc DESC LIMIT 50",
            ARRAY_A
        );
        if ( null === $rows ) {
            return new WP_Error( 'empire_yard_query_failed', 'Internal schedule unavailable.', array( 'status' => 503 ) );
        }
        return self::no_store( array(
            'mode' => 'INTERNAL_ONLY',
            'customer_booking_enabled' => false,
            'reservations' => $rows,
        ) );
    }

    private static function validate_request( WP_REST_Request $request ) {
        $service = $request->get_param( 'service_code' );
        $duration = $request->get_param( 'duration_minutes' );
        $resource = $request->get_param( 'resource_key' );
        $text = $request->get_param( 'starts_at_utc' );
        $vehicle = $request->get_param( 'vehicle_id' );
        if ( ! is_string( $resource ) || ! preg_match( '/^bay-[a-z0-9]{1,12}$/D', $resource )
            || ! in_array( $service, array( 'inspection', 'servicing', 'repair' ), true )
            || ! is_int( $duration ) || $duration < 30 || $duration > 120
            || 0 !== $duration % 30 || ! is_int( $vehicle ) || $vehicle < 0
            || ! is_string( $text ) ) {
            return new WP_Error( 'empire_yard_invalid_slot', 'Invalid internal schedule request.', array( 'status' => 400 ) );
        }
        $tz = new DateTimeZone( 'UTC' );
        $start = DateTimeImmutable::createFromFormat( '!Y-m-d\\TH:i:s\\Z', $text, $tz );
        if ( false === $start || $start->format( 'Y-m-d\\TH:i:s\\Z' ) !== $text ) {
            return new WP_Error( 'empire_yard_invalid_time', 'Invalid strict UTC time.', array( 'status' => 400 ) );
        }
        $seconds = $start->getTimestamp();
        if ( $seconds % self::INTERVAL_SECONDS !== 0
            || $seconds < time() + 1800
            || $seconds > time() + 90 * DAY_IN_SECONDS
            || $duration * 60 > self::MAX_DURATION_SECONDS ) {
            return new WP_Error( 'empire_yard_invalid_time', 'Slot must be aligned and within the 90-day internal horizon.', array( 'status' => 400 ) );
        }
        if ( $vehicle > 0 ) {
            $post = get_post( $vehicle );
            if ( ! $post || 'empire_vehicle' !== $post->post_type ) {
                return new WP_Error( 'empire_yard_vehicle_not_found', 'Internal vehicle record unavailable.', array( 'status' => 400 ) );
            }
        }
        return array(
            'resource' => $resource, 'service' => $service,
            'start' => $seconds, 'duration' => $duration,
            'vehicle' => $vehicle,
        );
    }

    public static function reserve_private( WP_REST_Request $request ) {
        global $wpdb;
        $entry = self::validate_request( $request );
        if ( is_wp_error( $entry ) ) {
            return $entry;
        }
        if ( ! self::transactional_engine_ready() ) {
            return new WP_Error( 'empire_yard_db_not_ready', 'InnoDB internal tables not available.', array( 'status' => 503 ) );
        }
        list( $bookings, $slots ) = self::tables();
        if ( false === $wpdb->query( 'START TRANSACTION' ) ) {
            return new WP_Error( 'empire_yard_tx_failed', 'No transactional booking authority.', array( 'status' => 503 ) );
        }
        $inserted = $wpdb->insert( $bookings, array(
            'resource_key' => $entry['resource'],
            'start_utc' => gmdate( 'Y-m-d H:i:s', $entry['start'] ),
            'end_utc' => gmdate( 'Y-m-d H:i:s', $entry['start'] + $entry['duration'] * 60 ),
            'status' => 'held',
            'service_code' => $entry['service'],
            'vehicle_id' => $entry['vehicle'],
            'created_by' => get_current_user_id(),
            'created_at_utc' => gmdate( 'Y-m-d H:i:s' ),
        ), array( '%s', '%s', '%s', '%s', '%s', '%d', '%d', '%s' ) );
        if ( 1 !== $inserted ) {
            $wpdb->query( 'ROLLBACK' );
            return new WP_Error( 'empire_yard_booking_failure', 'Cannot create the internal hold.', array( 'status' => 503 ) );
        }
        $booking_id = (int) $wpdb->insert_id;
        for ( $offset = 0; $offset < $entry['duration'] * 60; $offset += self::INTERVAL_SECONDS ) {
            $inserted = $wpdb->insert( $slots, array(
                'booking_id' => $booking_id,
                'resource_key' => $entry['resource'],
                'slot_utc' => gmdate( 'Y-m-d H:i:s', $entry['start'] + $offset ),
            ), array( '%d', '%s', '%s' ) );
            if ( 1 !== $inserted ) {
                $wpdb->query( 'ROLLBACK' );
                return new WP_Error(
                    'empire_yard_slot_conflict',
                    'One or more internal slots are unavailable.',
                    array( 'status' => 409 )
                );
            }
        }
        if ( false === $wpdb->query( 'COMMIT' ) ) {
            $wpdb->query( 'ROLLBACK' );
            return new WP_Error( 'empire_yard_commit_failed', 'Could not commit internal hold.', array( 'status' => 503 ) );
        }
        return self::no_store( array(
            'booking_id' => $booking_id, 'status' => 'held',
            'customer_booking_created' => false, 'notification_sent' => false,
            'payment_captured' => false,
        ), 201 );
    }

    public static function cancel_private( WP_REST_Request $request ) {
        global $wpdb;
        if ( ! self::transactional_engine_ready() ) {
            return new WP_Error( 'empire_yard_db_not_ready', 'Internal booking tables unavailable.', array( 'status' => 503 ) );
        }
        list( $bookings, $slots ) = self::tables();
        $id = absint( $request['id'] );
        if ( 0 === $id || false === $wpdb->query( 'START TRANSACTION' ) ) {
            return new WP_Error( 'empire_yard_tx_failed', 'Invalid internal cancellation.', array( 'status' => 400 ) );
        }
        $row = $wpdb->get_row(
            $wpdb->prepare( "SELECT id, status FROM {$bookings} WHERE id = %d FOR UPDATE", $id ),
            ARRAY_A
        );
        if ( ! $row || 'held' !== $row['status'] ) {
            $wpdb->query( 'ROLLBACK' );
            return new WP_Error( 'empire_yard_hold_not_found', 'No active internal hold.', array( 'status' => 404 ) );
        }
        if ( 1 !== $wpdb->update( $bookings, array( 'status' => 'cancelled' ), array( 'id' => $id, 'status' => 'held' ), array( '%s' ), array( '%d', '%s' ) )
            || false === $wpdb->delete( $slots, array( 'booking_id' => $id ), array( '%d' ) )
            || false === $wpdb->query( 'COMMIT' ) ) {
            $wpdb->query( 'ROLLBACK' );
            return new WP_Error( 'empire_yard_cancel_failed', 'Internal hold release failed.', array( 'status' => 503 ) );
        }
        return self::no_store( array(
            'booking_id' => $id, 'status' => 'cancelled',
            'outbound_notifications' => 0,
        ) );
    }
}
