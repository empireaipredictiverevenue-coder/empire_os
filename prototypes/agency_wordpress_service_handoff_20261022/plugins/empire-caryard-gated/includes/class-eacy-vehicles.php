<?php
/**
 * Fictional car-yard inventory catalogue; no buyer-contact information.
 */
if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

final class EACY_Vehicles {
    public const POST_TYPE = 'eacy_vehicle';
    private const STATES = array( 'unverified', 'available', 'reserved', 'sold' );

    public static function register(): void {
        register_post_type(
            self::POST_TYPE,
            array(
                'labels' => array(
                    'name' => __( 'Demo Vehicles', 'empire-caryard-gated' ),
                    'singular_name' => __( 'Demo Vehicle', 'empire-caryard-gated' ),
                ),
                'public' => true,
                'show_in_rest' => true,
                'has_archive' => true,
                'rewrite' => array( 'slug' => 'demo-vehicles' ),
                'show_in_menu' => true,
                'menu_icon' => 'dashicons-car',
                'supports' => array( 'title', 'editor', 'excerpt', 'thumbnail', 'custom-fields' ),
                'capability_type' => 'post',
                'map_meta_cap' => true,
            )
        );
    }

    public static function sanitize_stock_state( $value ): string {
        $state = sanitize_key( (string) $value );
        return in_array( $state, self::STATES, true ) ? $state : 'unverified';
    }

    public static function sanitize_year( $value ): int {
        $year = filter_var( $value, FILTER_VALIDATE_INT );
        return ( false !== $year && $year >= 1950 && $year <= 2100 ) ? (int) $year : 0;
    }

    public static function sanitize_price( $value ): int {
        // Prototype uses integer AUD. Floating-point monetary arithmetic
        // and claims about dealer stock are intentionally excluded.
        $price = filter_var( $value, FILTER_VALIDATE_INT );
        return ( false !== $price && $price >= 0 && $price <= 10000000 ) ? (int) $price : 0;
    }

    public static function register_meta(): void {
        $auth = static function () : bool {
            return current_user_can( 'edit_posts' );
        };

        register_post_meta(
            self::POST_TYPE,
            '_eacy_year',
            array(
                'type' => 'integer',
                'single' => true,
                'default' => 0,
                'show_in_rest' => true,
                'sanitize_callback' => array( __CLASS__, 'sanitize_year' ),
                'auth_callback' => $auth,
            )
        );
        register_post_meta(
            self::POST_TYPE,
            '_eacy_price_aud',
            array(
                'type' => 'integer',
                'single' => true,
                'default' => 0,
                'show_in_rest' => true,
                'sanitize_callback' => array( __CLASS__, 'sanitize_price' ),
                'auth_callback' => $auth,
            )
        );
        register_post_meta(
            self::POST_TYPE,
            '_eacy_stock_state',
            array(
                'type' => 'string',
                'single' => true,
                'default' => 'unverified',
                'show_in_rest' => true,
                'sanitize_callback' => array( __CLASS__, 'sanitize_stock_state' ),
                'auth_callback' => $auth,
            )
        );
    }

    public static function register_shortcode(): void {
        add_shortcode( 'empire_demo_vehicles', array( __CLASS__, 'render_inventory' ) );
    }

    public static function render_inventory(): string {
        $query = new WP_Query(
            array(
                'post_type' => self::POST_TYPE,
                'post_status' => 'publish',
                'posts_per_page' => 12,
                'no_found_rows' => true,
                'orderby' => 'date',
                'order' => 'DESC',
            )
        );

        $markup = '<section class="eacy-inventory" aria-label="' .
            esc_attr__( 'Demonstration vehicle inventory', 'empire-caryard-gated' ) . '">';
        $markup .= '<p><strong>' .
            esc_html__( 'Capability demo only: no vehicle stock, pricing, title or availability is independently confirmed.', 'empire-caryard-gated' ) .
            '</strong></p>';

        if ( ! $query->have_posts() ) {
            $markup .= '<p>' . esc_html__( 'No demo vehicles are published.', 'empire-caryard-gated' ) . '</p>';
        }

        while ( $query->have_posts() ) {
            $query->the_post();
            $post_id = get_the_ID();
            $year = self::sanitize_year( get_post_meta( $post_id, '_eacy_year', true ) );
            $price = self::sanitize_price( get_post_meta( $post_id, '_eacy_price_aud', true ) );
            $state = self::sanitize_stock_state( get_post_meta( $post_id, '_eacy_stock_state', true ) );
            $markup .= '<article class="eacy-vehicle">';
            $markup .= '<h3><a href="' . esc_url( get_permalink( $post_id ) ) . '">' .
                esc_html( get_the_title( $post_id ) ) . '</a></h3>';
            if ( $year > 0 ) {
                $markup .= '<p>' . esc_html__( 'Model year (demo): ', 'empire-caryard-gated' ) . esc_html( (string) $year ) . '</p>';
            }
            if ( $price > 0 ) {
                $markup .= '<p>' . esc_html__( 'Unverified asking price (AUD): ', 'empire-caryard-gated' ) .
                    esc_html( number_format_i18n( $price, 0 ) ) . '</p>';
            }
            $markup .= '<p>' . esc_html__( 'Dealer-supplied demo status: ', 'empire-caryard-gated' ) .
                esc_html( ucfirst( $state ) ) . '</p>';
            $markup .= '</article>';
        }
        wp_reset_postdata();
        return $markup . '</section>';
    }
}
