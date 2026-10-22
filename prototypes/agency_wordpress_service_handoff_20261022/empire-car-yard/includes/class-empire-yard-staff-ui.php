<?php
/** Staging-only administrator booking workbench. No public routes or PII. */
declare(strict_types=1);
if (!defined('ABSPATH')) { exit; }

final class Empire_Yard_Staff_UI {
    private const PAGE = 'empire-yard-bookings';

    public static function boot(): void {
        if (!defined('EMPIRE_YARD_STAGING_STAFF_UI_ENABLED') ||
            EMPIRE_YARD_STAGING_STAFF_UI_ENABLED !== true || !is_admin()) { return; }
        add_action('admin_menu', [self::class, 'menu']);
        add_action('admin_post_empire_yard_staff_hold', [self::class, 'hold']);
        add_action('admin_post_empire_yard_staff_transition', [self::class, 'transition']);
    }

    private static function guard(): void {
        if (!current_user_can('manage_options') || get_current_user_id() <= 0) {
            wp_die('Administrator required', '', ['response' => 403]);
        }
    }

    private static function store(): Empire_Yard_Booking_Store {
        global $wpdb;
        return new Empire_Yard_Booking_Store($wpdb);
    }

    private static function calendar(): array {
        $calendar = apply_filters('empire_yard_staff_calendar', []);
        return is_array($calendar) ? $calendar : [];
    }

    private static function calendar_ready(array $calendar): bool {
        return isset($calendar['timezone'], $calendar['hours'], $calendar['blackout_dates']) &&
            is_string($calendar['timezone']) &&
            in_array($calendar['timezone'], timezone_identifiers_list(), true) &&
            is_array($calendar['hours']) && count($calendar['hours']) > 0 &&
            is_array($calendar['blackout_dates']);
    }

    private static function field(string $name): string {
        if (!isset($_POST[$name]) || !is_string($_POST[$name])) {
            throw new InvalidArgumentException('Malformed staff input');
        }
        return sanitize_text_field(wp_unslash($_POST[$name]));
    }

    private static function number(string $name): int {
        $value = self::field($name);
        if (!preg_match('/^[0-9]{1,10}$/D', $value)) {
            throw new InvalidArgumentException('Malformed number');
        }
        return (int) $value;
    }

    private static function done(string $status): void {
        if (!in_array($status, ['held', 'changed', 'denied'], true)) { $status = 'denied'; }
        wp_safe_redirect(add_query_arg(
            ['page' => self::PAGE, 'yard_notice' => $status], admin_url('admin.php')
        ));
        exit;
    }

    public static function menu(): void {
        add_menu_page('Demo workshop bookings', 'Demo Workshop', 'manage_options',
            self::PAGE, [self::class, 'page'], 'dashicons-calendar-alt');
    }

    public static function hold(): void {
        self::guard();
        check_admin_referer('empire_yard_staff_hold');
        try {
            $calendar = self::calendar();
            if (!self::calendar_ready($calendar) || !self::store()->ready()) {
                throw new RuntimeException('Verified workshop prerequisites missing');
            }
            self::store()->hold(self::field('bay'), self::field('service'),
                self::field('date'), self::field('time'), self::number('minutes'),
                $calendar['timezone'], $calendar);
        } catch (Throwable $error) {
            self::done('denied');
        }
        self::done('held');
    }

    public static function transition(): void {
        self::guard();
        try {
            $id = self::number('booking_id');
            check_admin_referer('empire_yard_staff_transition_' . $id);
            if (!self::calendar_ready(self::calendar()) || !self::store()->ready()) {
                throw new RuntimeException('Verified workshop prerequisites missing');
            }
            $status = self::field('next_status');
            if (!in_array($status, ['confirmed', 'cancelled', 'completed'], true)) {
                throw new InvalidArgumentException('Unsupported transition');
            }
            self::store()->transition($id, $status);
        } catch (Throwable $error) {
            self::done('denied');
        }
        self::done('changed');
    }

    public static function page(): void {
        self::guard();
        $store = self::store();
        $ready = $store->ready();
        $calendar = self::calendar();
        $configured = self::calendar_ready($calendar);
        echo '<div class="wrap"><h1>Demo workshop bookings</h1>';
        echo '<p>Synthetic staff testing only. No customer details, notifications or payments.</p>';
        if (isset($_GET['yard_notice']) && is_string($_GET['yard_notice'])) {
            $notice = sanitize_key(wp_unslash($_GET['yard_notice']));
            $messages = ['held' => 'Demo hold recorded.', 'changed' => 'Status updated.',
                'denied' => 'Change denied; no success recorded.'];
            if (isset($messages[$notice])) {
                echo '<div class="notice notice-info"><p>' . esc_html($messages[$notice]) . '</p></div>';
            }
        }
        if (!$ready || !$configured) {
            echo '<div class="notice notice-warning"><p>Changes disabled: audited InnoDB tables, '
                . 'unique slot index and approved calendar are required.</p></div>';
        }
        if ($ready && $configured) {
            $today = (new DateTimeImmutable('now', new DateTimeZone($calendar['timezone'])))->format('Y-m-d');
            echo '<h2>Create staff-only hold</h2><form method="post" action="' . esc_url(admin_url('admin-post.php')) . '">';
            echo '<input type="hidden" name="action" value="empire_yard_staff_hold" />';
            wp_nonce_field('empire_yard_staff_hold');
            echo '<p><label for="yard-bay">Bay</label> <input required id="yard-bay" name="bay" pattern="[a-z0-9-]{1,48}" value="bay-1" /></p>';
            echo '<p><label for="yard-service">Service</label> <select id="yard-service" name="service">';
            foreach (Empire_Yard_Booking_Rules::SERVICES as $service) {
                echo '<option value="' . esc_attr($service) . '">' . esc_html(ucfirst($service)) . '</option>';
            }
            echo '</select></p><p><label for="yard-date">Date</label> <input required type="date" id="yard-date" name="date" value="' . esc_attr($today) . '" /></p>';
            echo '<p><label for="yard-time">Time</label> <input required type="time" step="900" id="yard-time" name="time" value="10:00" /></p>';
            echo '<p><label for="yard-minutes">Duration (minutes)</label> <select id="yard-minutes" name="minutes">';
            foreach ([30, 45, 60, 90, 120] as $duration) {
                echo '<option value="' . esc_attr((string) $duration) . '">' . esc_html((string) $duration) . '</option>';
            }
            echo '</select></p><p>Calendar: ' . esc_html($calendar['timezone']) . '</p>';
            submit_button('Hold demo slot');
            echo '</form>';
        }
        echo '<h2>Recent synthetic appointments</h2>';
        if (!$ready) {
            echo '<p>Database not verified; no booking data queried.</p>';
        } else {
            try { $rows = $store->recent(30); }
            catch (Throwable $error) { $rows = []; }
            if (!$rows) { echo '<p>No appointments available.</p>'; }
            else {
                echo '<table class="widefat striped"><thead><tr><th>ID</th><th>Bay</th><th>Service</th><th>Start UTC</th><th>End UTC</th><th>Status</th><th>Staff actions</th></tr></thead><tbody>';
                foreach ($rows as $row) {
                    $id = (int) ($row['id'] ?? 0);
                    $status = (string) ($row['status'] ?? '');
                    echo '<tr><td>' . esc_html((string) $id) . '</td><td>' . esc_html((string) ($row['bay'] ?? ''))
                        . '</td><td>' . esc_html((string) ($row['service'] ?? ''))
                        . '</td><td>' . esc_html((string) ($row['start_utc'] ?? ''))
                        . '</td><td>' . esc_html((string) ($row['end_utc'] ?? ''))
                        . '</td><td>' . esc_html($status) . '</td><td>';
                    $targets = $status === 'held' ? ['confirmed', 'cancelled']
                        : ($status === 'confirmed' ? ['completed', 'cancelled'] : []);
                    foreach ($targets as $target) {
                        echo '<form method="post" style="display:inline-block;margin-right:.5em" action="' . esc_url(admin_url('admin-post.php')) . '">';
                        echo '<input type="hidden" name="action" value="empire_yard_staff_transition" />';
                        echo '<input type="hidden" name="booking_id" value="' . esc_attr((string) $id) . '" />';
                        echo '<input type="hidden" name="next_status" value="' . esc_attr($target) . '" />';
                        wp_nonce_field('empire_yard_staff_transition_' . $id);
                        echo '<button type="submit" class="button">' . esc_html(ucfirst($target)) . '</button></form>';
                    }
                    echo '</td></tr>';
                }
                echo '</tbody></table>';
            }
        }
        echo '</div>';
    }
}
Empire_Yard_Staff_UI::boot();
