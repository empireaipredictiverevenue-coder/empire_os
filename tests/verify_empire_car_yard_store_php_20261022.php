<?php
declare(strict_types=1);
error_reporting(E_ALL);
const DB_NAME = 'empire_yard_synthetic';
const ARRAY_A = 'ARRAY_A';
$GLOBALS['permit'] = true;
function current_user_can(string $cap): bool { return $cap === 'manage_options' && $GLOBALS['permit']; }
function get_current_user_id(): int { return $GLOBALS['permit'] ? 77 : 0; }
function verify(bool $value, string $description): void { if (!$value) throw new RuntimeException($description); }
function rejected(callable $run, string $description): void {
    try { $run(); } catch (RuntimeException | InvalidArgumentException $exception) { return; }
    throw new RuntimeException('Expected rejection: ' . $description);
}
$classes = dirname(__DIR__) . '/prototypes/agency_wordpress_service_handoff_20261022/empire-car-yard/includes/';
require_once $classes . 'class-empire-yard-booking-rules.php';
require_once $classes . 'class-empire-yard-booking-store.php';

final class FakeYardDB {
    public string $prefix = 'wp_test_';
    public int $insert_id = 0;
    public array $bookings = [];
    public array $events = [];
    public array $slots = [];
    public bool $innodb = true;
    public bool $unique_index = true;
    public bool $deny_lock = false;
    public bool $fail_audit = false;
    public bool $locked = false;
    public string $last_error = '';
    private ?array $snapshot = null;
    public function get_charset_collate(): string { return 'DEFAULT CHARACTER SET utf8mb4'; }
    public function prepare(string $sql, ...$args): string {
        foreach ($args as $arg) {
            if (str_contains($sql, '%s')) {
                $sql = preg_replace('/%s/', "'" . str_replace("'", "''", (string)$arg) . "'", $sql, 1);
            } elseif (str_contains($sql, '%d')) {
                $sql = preg_replace('/%d/', (string)(int)$arg, $sql, 1);
            }
        }
        return $sql;
    }
    public function get_var(string $sql) {
        if (str_contains($sql, 'information_schema.TABLES')) return $this->innodb ? 'InnoDB' : 'MyISAM';
        if (str_contains($sql, 'information_schema.STATISTICS')) return $this->unique_index ? 'bay,slot_utc' : null;
        if (str_contains($sql, 'GET_LOCK(')) { if ($this->deny_lock || $this->locked) return '0'; $this->locked = true; return '1'; }
        if (str_contains($sql, 'RELEASE_LOCK(')) { $this->locked = false; return '1'; }
        if (str_contains($sql, 'SELECT id FROM')) {
            preg_match("/bay = '([^']+)'/", $sql, $bay);
            preg_match("/start_utc < '([^']+)'/", $sql, $end);
            preg_match("/end_utc > '([^']+)'/", $sql, $start);
            foreach ($this->bookings as $id => $r) {
                if ($r['bay'] === ($bay[1] ?? null) && in_array($r['status'], ['held','confirmed'], true)
                    && $r['start_utc'] < ($end[1] ?? '') && $r['end_utc'] > ($start[1] ?? '')) return $id;
            }
            return null;
        }
        throw new RuntimeException('Unexpected get_var query ' . $sql);
    }
    public function get_results(string $sql, $returntype): array {
        $rows = [];
        foreach ($this->bookings as $id => $record) {
            $rows[] = array_merge(['id' => $id], $record);
        }
        return array_reverse(array_slice($rows, -50));
    }
    public function get_row(string $sql, $returntype): ?array {
        preg_match('/WHERE id = (\d+)/', $sql, $match);
        $row = $this->bookings[(int)($match[1] ?? 0)] ?? null;
        return $row === null ? null : array_merge(['id' => (int)$match[1]], $row);
    }
    public function query(string $sql) {
        if ($sql === 'START TRANSACTION') {
            $this->snapshot = [$this->bookings, $this->events, $this->slots];
            return 0;
        }
        if ($sql === 'ROLLBACK') {
            if ($this->snapshot !== null) [$this->bookings, $this->events, $this->slots] = $this->snapshot;
            $this->snapshot = null;
            return 0;
        }
        if ($sql === 'COMMIT') { $this->snapshot = null; return 0; }
        throw new RuntimeException('Unexpected query ' . $sql);
    }
    public function insert(string $table, array $values, array $formats) {
        if (str_ends_with($table, '_events')) {
            if ($this->fail_audit) return false;
            $this->events[] = $values;
            return 1;
        }
        if (str_ends_with($table, '_slots')) {
            foreach ($this->slots as $existing) {
                if ($existing['bay'] === $values['bay'] && $existing['slot_utc'] === $values['slot_utc']) return false;
            }
            $this->slots[] = $values;
            return 1;
        }
        $this->insert_id++;
        $this->bookings[$this->insert_id] = $values;
        return 1;
    }
    public function delete(string $table, array $where, array $formats) {
        $before = count($this->slots);
        $this->slots = array_values(array_filter($this->slots,
            fn($r) => $r['booking_id'] !== $where['booking_id']));
        return $before - count($this->slots);
    }
    public function update(string $table, array $values, array $where, array $formats, array $whereformats) {
        $id = $where['id'];
        if (!isset($this->bookings[$id]) || $this->bookings[$id]['status'] !== $where['status']) return 0;
        $this->bookings[$id] = array_merge($this->bookings[$id], $values);
        return 1;
    }
}

$db = new FakeYardDB();
$store = new Empire_Yard_Booking_Store($db);
$calendar = ['timezone' => 'Australia/Sydney', 'hours' => [4 => ['08:00', '17:00'], 5 => ['08:00', '17:00']], 'blackout_dates' => ['2026-10-23']];
$sql = $store->schema_sql();
verify(count($sql) === 3 && str_contains($sql[0], 'ENGINE=InnoDB') && str_contains($sql[1], 'booking_event') && str_contains($sql[2], 'UNIQUE KEY bay_slot'), 'Staging DDL preview and unique concurrency constraint');
rejected(fn() => $store->hold('bay-1', 'repair', '2026-10-23', '09:00', 60, 'Australia/Sydney', $calendar), 'Blackout day');
rejected(fn() => $store->hold('bay-1', 'repair', '2026-10-22', '07:00', 60, 'Australia/Sydney', $calendar), 'Closed hours');
rejected(fn() => $store->hold('bay-1', 'repair', '2026-10-22', '16:30', 60, 'Australia/Sydney', $calendar), 'Beyond closing');
rejected(fn() => $store->hold('bay-1', 'repair', '2026-10-22', '09:00', 60, 'Europe/London', $calendar), 'Calendar zone mismatch');
rejected(fn() => $store->hold('bay-1', 'repair', '2026-10-22', '09:10', 60, 'Australia/Sydney', $calendar), 'Unaligned 15-minute slots');
rejected(fn() => $store->hold('bay/1', 'repair', '2026-10-22', '09:00', 60, 'Australia/Sydney', $calendar), 'Unsafe bay');
rejected(fn() => $store->hold('bay-1', 'invalid', '2026-10-22', '09:00', 60, 'Australia/Sydney', $calendar), 'Unsupported service');
$db->innodb = false;
rejected(fn() => $store->hold('bay-1', 'repair', '2026-10-22', '09:00', 60, 'Australia/Sydney', $calendar), 'Transactional engine gate');
$db->innodb = true;
$db->unique_index = false;
verify(!$store->ready(), 'Missing unique index must make staff screen unavailable');
rejected(fn() => $store->hold('bay-1', 'repair', '2026-10-22', '09:00', 60, 'Australia/Sydney', $calendar), 'Missing unique index');
$db->unique_index = true;
verify($store->ready(), 'Configured InnoDB tables and unique slot index ready');
$db->deny_lock = true;
rejected(fn() => $store->hold('bay-1', 'repair', '2026-10-22', '09:00', 60, 'Australia/Sydney', $calendar), 'Unavailable advisory lock');
$db->deny_lock = false;
$GLOBALS['permit'] = false;
rejected(fn() => $store->hold('bay-1', 'repair', '2026-10-22', '09:00', 60, 'Australia/Sydney', $calendar), 'Admin permission gate');
$GLOBALS['permit'] = true;
$id = $store->hold('bay-1', 'repair', '2026-10-22', '09:00', 60, 'Australia/Sydney', $calendar);
verify(count($store->recent(30)) === 1, 'Staff-only recent appointments');
verify($id === 1 && !$db->locked && $db->bookings[1]['status'] === 'held' && count($db->events) === 1 && count($db->slots) === 4, 'Commit booking with audit and slot occupancy');
rejected(fn() => $store->hold('bay-1', 'repair', '2026-10-22', '09:45', 60, 'Australia/Sydney', $calendar), 'Overlapping booking');
verify(count($db->bookings) === 1 && !$db->locked, 'Conflict rollback and unlock');
$id2 = $store->hold('bay-1', 'inspection', '2026-10-22', '10:00', 60, 'Australia/Sydney', $calendar);
verify($id2 === 2, 'Adjacent booking permitted');
$id3 = $store->hold('bay-2', 'tyres', '2026-10-22', '09:00', 60, 'Australia/Sydney', $calendar);
verify($id3 === 3, 'Different bay permitted');
verify($store->transition(1, 'confirmed') && $db->bookings[1]['status'] === 'confirmed', 'Confirm');
rejected(fn() => $store->transition(1, 'held'), 'No reverse transition');
verify($store->transition(1, 'cancelled') && $db->bookings[1]['status'] === 'cancelled', 'Cancel');
$id4 = $store->hold('bay-1', 'repair', '2026-10-22', '09:00', 60, 'Australia/Sydney', $calendar);
verify($id4 === 4 && count($db->slots) === 12, 'Cancelled interval can be reused after slot release');
// Even if the advisory lock/overlap scan misses an orphan occupancy row,
// the database UNIQUE index must refuse it atomically.
$utc = Empire_Yard_Booking_Rules::slot('2026-10-22', '09:00', 60, 'Australia/Sydney')['start_utc'];
$db->slots[] = ['bay' => 'bay-3', 'slot_utc' => $utc, 'booking_id' => 999];
rejected(fn() => $store->hold('bay-3', 'inspection', '2026-10-22', '09:00', 60, 'Australia/Sydney', $calendar), 'Unique-slot constraint collision');
verify(count($db->bookings) === 4 && !$db->locked, 'Constraint failure must roll back');
array_pop($db->slots);
$db->fail_audit = true;
rejected(fn() => $store->transition(4, 'confirmed'), 'Audit failure must roll back status change');
verify($db->bookings[4]['status'] === 'held' && !$db->locked, 'Atomic audit rollback');
rejected(fn() => $store->hold('bay-3', 'repair', '2026-10-22', '09:00', 60, 'Australia/Sydney', $calendar), 'Failed audit rolls back booking insert');
verify(count($db->bookings) === 4 && count($db->slots) === 12, 'No phantom bookings or slot rows');
echo "EMPIRE_CAR_YARD_STAFF_STORAGE_SHIM_PASS: permissions, InnoDB gate, serialised conflict checks, booking audit rollback, hours and blackout rules\n";
