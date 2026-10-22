<?php
/**
 * Dormant, administrator-only booking persistence candidate.
 * No callbacks, routes, schema writes or customer-facing submission hooks.
 * Requires separately verified MySQL/InnoDB staging tables before use.
 */
declare(strict_types=1);

final class Empire_Yard_Booking_Store {
    private $db;

    public function __construct($wpdb) {
        $this->db = $wpdb;
    }

    private function bookings(): string {
        return $this->db->prefix . 'empire_yard_bookings';
    }

    private function events(): string {
        return $this->db->prefix . 'empire_yard_booking_events';
    }

    private function slots(): string {
        return $this->db->prefix . 'empire_yard_booking_slots';
    }

    /** DDL preview ONLY; no migrations are registered or executed. */
    public function schema_sql(): array {
        $collation = $this->db->get_charset_collate();
        $bookings = $this->bookings();
        $events = $this->events();
        $slots = $this->slots();
        return [
            "CREATE TABLE $bookings (
                id bigint(20) unsigned NOT NULL AUTO_INCREMENT,
                bay varchar(48) NOT NULL,
                service varchar(32) NOT NULL,
                start_utc datetime NOT NULL,
                end_utc datetime NOT NULL,
                timezone varchar(64) NOT NULL,
                status varchar(16) NOT NULL,
                actor_user bigint(20) unsigned NOT NULL,
                created_utc datetime NOT NULL,
                updated_utc datetime NOT NULL,
                PRIMARY KEY  (id),
                KEY bay_status_interval (bay,status,start_utc,end_utc)
            ) ENGINE=InnoDB $collation",
            "CREATE TABLE $events (
                id bigint(20) unsigned NOT NULL AUTO_INCREMENT,
                booking_id bigint(20) unsigned NOT NULL,
                previous_status varchar(16) NOT NULL,
                new_status varchar(16) NOT NULL,
                actor_user bigint(20) unsigned NOT NULL,
                occurred_utc datetime NOT NULL,
                PRIMARY KEY  (id),
                KEY booking_event (booking_id,id)
            ) ENGINE=InnoDB $collation",
            "CREATE TABLE $slots (
                id bigint(20) unsigned NOT NULL AUTO_INCREMENT,
                bay varchar(48) NOT NULL,
                slot_utc datetime NOT NULL,
                booking_id bigint(20) unsigned NOT NULL,
                PRIMARY KEY  (id),
                UNIQUE KEY bay_slot (bay,slot_utc),
                KEY booking_id (booking_id)
            ) ENGINE=InnoDB $collation",
        ];
    }

    private function assert_staff(): int {
        if (!function_exists('current_user_can') || !current_user_can('manage_options') ||
            !function_exists('get_current_user_id')) {
            throw new RuntimeException('Authorised staff session required');
        }
        $actor = (int) get_current_user_id();
        if ($actor <= 0) {
            throw new RuntimeException('Authenticated staff identity required');
        }
        return $actor;
    }

    private function assert_innodb(): void {
        foreach ([$this->bookings(), $this->events(), $this->slots()] as $table) {
            $sql = $this->db->prepare(
                'SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s',
                $table
            );
            if ($this->db->get_var($sql) !== 'InnoDB') {
                throw new RuntimeException('Verified InnoDB booking tables required');
            }
        }
    }

    /** Explicit, complete opening-hour/blackout policy; no configured hours means closed. */
    private function checked_slot(string $service, string $date, string $time, int $minutes,
        string $zone, array $calendar): array {
        if (!in_array($service, Empire_Yard_Booking_Rules::SERVICES, true) ||
            !isset($calendar['timezone']) || $calendar['timezone'] !== $zone ||
            !isset($calendar['hours']) || !is_array($calendar['hours']) ||
            !isset($calendar['blackout_dates']) || !is_array($calendar['blackout_dates'])) {
            throw new InvalidArgumentException('Booking service or opening-hours policy not approved');
        }
        if (!preg_match('/^\d{2}:(00|15|30|45)$/D', $time)) {
            throw new InvalidArgumentException('Workshop bookings require quarter-hour aligned start');
        }
        $slot = Empire_Yard_Booking_Rules::slot($date, $time, $minutes, $zone);
        $weekday = (int) (new DateTimeImmutable($date . ' 12:00', new DateTimeZone($zone)))->format('N');
        $hours = $calendar['hours'][$weekday] ?? null;
        if (!is_array($hours) || count($hours) !== 2 ||
            !is_string($hours[0]) || !is_string($hours[1]) ||
            !preg_match('/^\d{2}:\d{2}$/D', $hours[0]) ||
            !preg_match('/^\d{2}:\d{2}$/D', $hours[1]) ||
            $hours[0] >= $hours[1] ||
            $hours[1] > '23:59' ||
            in_array($date, $calendar['blackout_dates'], true)) {
            throw new InvalidArgumentException('Workshop closed or blackout policy invalid');
        }
        $end = (new DateTimeImmutable($slot['end_utc'], new DateTimeZone('UTC')))
            ->setTimezone(new DateTimeZone($zone));
        if ($time < $hours[0] || $end->format('Y-m-d') !== $date ||
            $end->format('H:i') > $hours[1]) {
            throw new InvalidArgumentException('Slot outside staffed opening hours');
        }
        return $slot;
    }

    private function lock_name(string $bay): string {
        // MySQL GET_LOCK identifiers are server-wide and limited to 64 characters.
        return 'emp_yard_' . substr(hash('sha256', DB_NAME . ':' . $this->bookings() . ':' . $bay), 0, 54);
    }

    /** Serialises checks and writes per bay on the same MySQL connection. */
    private function lock_bay(string $bay): string {
        $name = $this->lock_name($bay);
        $granted = $this->db->get_var($this->db->prepare('SELECT GET_LOCK(%s, 0)', $name));
        if ((string) $granted !== '1') {
            throw new RuntimeException('Booking bay lock unavailable; no write made');
        }
        return $name;
    }

    private function unlock_bay(string $name): void {
        $this->db->get_var($this->db->prepare('SELECT RELEASE_LOCK(%s)', $name));
    }

    private function start(): void {
        if ($this->db->query('START TRANSACTION') === false) {
            throw new RuntimeException('Could not begin atomic booking transaction');
        }
    }

    private function commit(): void {
        if ($this->db->query('COMMIT') === false) {
            throw new RuntimeException('Booking transaction commit failed');
        }
    }

    private function audit(int $booking_id, string $from, string $to, int $actor): void {
        if ($this->db->insert($this->events(), [
            'booking_id' => $booking_id, 'previous_status' => $from,
            'new_status' => $to, 'actor_user' => $actor,
            'occurred_utc' => gmdate('Y-m-d H:i:s'),
        ], ['%d', '%s', '%s', '%d', '%s']) !== 1) {
            throw new RuntimeException('Booking audit insert failed');
        }
    }

    /** Staff-only reservation. Never accepts customer contact data. */
    public function hold(string $bay, string $service, string $date, string $time,
        int $minutes, string $zone, array $calendar): int {
        $actor = $this->assert_staff();
        if (!preg_match('/^[a-z0-9-]{1,48}$/D', $bay)) {
            throw new InvalidArgumentException('Invalid controlled workshop bay');
        }
        $slot = $this->checked_slot($service, $date, $time, $minutes, $zone, $calendar);
        $this->assert_innodb();
        $name = $this->lock_bay($bay);
        $active_transaction = false;
        try {
            $this->start();
            $active_transaction = true;
            $sql = $this->db->prepare(
                "SELECT id FROM {$this->bookings()} WHERE bay = %s AND status IN ('held','confirmed') AND start_utc < %s AND end_utc > %s LIMIT 1 FOR UPDATE",
                $bay, $slot['end_utc'], $slot['start_utc']
            );
            $conflict = $this->db->get_var($sql);
            if ($this->db->last_error !== '') {
                throw new RuntimeException('Could not verify workshop availability');
            }
            if ($conflict !== null) {
                throw new RuntimeException('Workshop bay already booked');
            }
            $now = gmdate('Y-m-d H:i:s');
            if ($this->db->insert($this->bookings(), [
                'bay' => $bay, 'service' => $service,
                'start_utc' => $slot['start_utc'], 'end_utc' => $slot['end_utc'],
                'timezone' => $zone, 'status' => 'held', 'actor_user' => $actor,
                'created_utc' => $now, 'updated_utc' => $now,
            ], ['%s', '%s', '%s', '%s', '%s', '%s', '%d', '%s', '%s']) !== 1) {
                throw new RuntimeException('Booking insert failed');
            }
            $id = (int) $this->db->insert_id;
            if ($id <= 0) {
                throw new RuntimeException('Booking ID unavailable');
            }
            // The unique (bay,slot_utc) index is an independent database-level
            // concurrency guard, even if a connection-scoped advisory lock is lost.
            $at = new DateTimeImmutable($slot['start_utc'], new DateTimeZone('UTC'));
            for ($n = 0; $n < $minutes / 15; $n++) {
                if ($this->db->insert($this->slots(), [
                    'bay' => $bay, 'slot_utc' => $at->format('Y-m-d H:i:s'),
                    'booking_id' => $id,
                ], ['%s', '%s', '%d']) !== 1) {
                    throw new RuntimeException('Workshop slot occupied or unavailable');
                }
                $at = $at->modify('+15 minutes');
            }
            $this->audit($id, 'created', 'held', $actor);
            $this->commit();
            $active_transaction = false;
            return $id;
        } finally {
            if ($active_transaction) {
                $this->db->query('ROLLBACK');
            }
            $this->unlock_bay($name);
        }
    }

    /** Transitions are immutable-audited; cancelling frees a bay, not an email. */
    public function transition(int $booking_id, string $next): bool {
        $actor = $this->assert_staff();
        if ($booking_id <= 0) {
            throw new InvalidArgumentException('Invalid booking ID');
        }
        $this->assert_innodb();
        $row = $this->db->get_row($this->db->prepare(
            "SELECT id,bay FROM {$this->bookings()} WHERE id = %d LIMIT 1", $booking_id
        ), ARRAY_A);
        if (!is_array($row) || !isset($row['bay']) || !is_string($row['bay'])) {
            throw new RuntimeException('Booking not found');
        }
        $bay = $row['bay'];
        if (!preg_match('/^[a-z0-9-]{1,48}$/D', $bay)) {
            throw new RuntimeException('Invalid persisted bay');
        }
        $name = $this->lock_bay($bay);
        $active_transaction = false;
        try {
            $this->start();
            $active_transaction = true;
            $current = $this->db->get_row($this->db->prepare(
                "SELECT id,bay,status FROM {$this->bookings()} WHERE id = %d FOR UPDATE", $booking_id
            ), ARRAY_A);
            if (!is_array($current) || $current['bay'] !== $bay ||
                !Empire_Yard_Booking_Rules::canTransition((string) $current['status'], $next)) {
                throw new RuntimeException('Booking status transition denied');
            }
            if ($this->db->update($this->bookings(), [
                'status' => $next, 'updated_utc' => gmdate('Y-m-d H:i:s'),
            ], ['id' => $booking_id, 'status' => $current['status']],
            ['%s', '%s'], ['%d', '%s']) !== 1) {
                throw new RuntimeException('Booking state update failed');
            }
            if (in_array($next, ['cancelled', 'completed'], true)) {
                if ($this->db->delete($this->slots(), ['booking_id' => $booking_id], ['%d']) === false) {
                    throw new RuntimeException('Workshop slot release failed');
                }
            }
            $this->audit($booking_id, (string) $current['status'], $next, $actor);
            $this->commit();
            $active_transaction = false;
            return true;
        } finally {
            if ($active_transaction) {
                $this->db->query('ROLLBACK');
            }
            $this->unlock_bay($name);
        }
    }
}
