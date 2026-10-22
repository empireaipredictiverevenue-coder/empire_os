<?php
/**
 * Disposable MariaDB-only booking-store concurrency verification.
 * No WordPress network/HTTP, no production DB connection, synthetic data only.
 */
declare(strict_types=1);
define('DB_NAME', 'empire_yard_synthetic');
define('ARRAY_A', 'ARRAY_A');
function current_user_can(string $cap): bool { return $cap === 'manage_options'; }
function get_current_user_id(): int { return 77; }
require_once dirname(__DIR__) . '/prototypes/agency_wordpress_service_handoff_20261022/empire-car-yard/includes/class-empire-yard-booking-rules.php';
require_once dirname(__DIR__) . '/prototypes/agency_wordpress_service_handoff_20261022/empire-car-yard/includes/class-empire-yard-booking-store.php';

final class RealYardWPDB {
    public string $prefix = 'wp_stage_';
    public int $insert_id = 0;
    public string $last_error = '';
    private mysqli $db;

    public function __construct(string $socket) {
        mysqli_report(MYSQLI_REPORT_ERROR | MYSQLI_REPORT_STRICT);
        $this->db = new mysqli('localhost', 'root', '', DB_NAME, 0, $socket);
        $this->db->set_charset('utf8mb4');
    }
    public function get_charset_collate(): string {
        return 'DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci';
    }
    public function prepare(string $sql, ...$args): string {
        foreach ($args as $arg) {
            $s = strpos($sql, '%s');
            $d = strpos($sql, '%d');
            if ($s === false && $d === false) { throw new RuntimeException('Unexpected SQL argument'); }
            if ($d !== false && ($s === false || $d < $s)) {
                $sql = substr_replace($sql, (string)(int)$arg, $d, 2);
            } else {
                $sql = substr_replace($sql, "'" . $this->db->real_escape_string((string)$arg) . "'", $s, 2);
            }
        }
        return $sql;
    }
    public function query(string $sql) {
        $result = $this->db->query($sql);
        $this->last_error = '';
        return $result === true ? $this->db->affected_rows : $result;
    }
    public function get_var(string $sql) {
        $result = $this->db->query($sql);
        $this->last_error = '';
        if (!$result instanceof mysqli_result) { return null; }
        $row = $result->fetch_row();
        $result->free();
        return $row[0] ?? null;
    }
    public function get_row(string $sql, $format): ?array {
        $result = $this->db->query($sql);
        $this->last_error = '';
        $row = $result->fetch_assoc();
        $result->free();
        return $row === null ? null : $row;
    }
    public function get_results(string $sql, $format): array {
        $result = $this->db->query($sql);
        $this->last_error = '';
        $rows = $result->fetch_all(MYSQLI_ASSOC);
        $result->free();
        return $rows;
    }
    private function sql_value($value, string $format): string {
        return $format === '%d' ? (string)(int)$value :
            "'" . $this->db->real_escape_string((string)$value) . "'";
    }
    public function insert(string $table, array $values, array $formats) {
        $columns = array_keys($values);
        $pieces = [];
        foreach (array_values($values) as $i => $value) {
            $pieces[] = $this->sql_value($value, $formats[$i]);
        }
        $sql = 'INSERT INTO ' . $table . ' (' . implode(',', $columns) . ') VALUES (' . implode(',', $pieces) . ')';
        $this->db->query($sql);
        $this->last_error = '';
        $this->insert_id = $this->db->insert_id;
        return $this->db->affected_rows;
    }
    public function update(string $table, array $values, array $where, array $formats, array $whereformats) {
        $assignments = [];
        foreach (array_values(array_keys($values)) as $i => $key) {
            $assignments[] = $key . ' = ' . $this->sql_value($values[$key], $formats[$i]);
        }
        $conditions = [];
        foreach (array_values(array_keys($where)) as $i => $key) {
            $conditions[] = $key . ' = ' . $this->sql_value($where[$key], $whereformats[$i]);
        }
        $this->db->query('UPDATE ' . $table . ' SET ' . implode(',', $assignments) . ' WHERE ' . implode(' AND ', $conditions));
        $this->last_error = '';
        return $this->db->affected_rows;
    }
    public function delete(string $table, array $where, array $formats) {
        $conditions = [];
        foreach (array_values(array_keys($where)) as $i => $key) {
            $conditions[] = $key . ' = ' . $this->sql_value($where[$key], $formats[$i]);
        }
        $this->db->query('DELETE FROM ' . $table . ' WHERE ' . implode(' AND ', $conditions));
        $this->last_error = '';
        return $this->db->affected_rows;
    }
}
function ensure(bool $condition, string $reason): void {
    if (!$condition) { throw new RuntimeException('Verification failed: ' . $reason); }
}
[$script, $mode, $socket, $gate] = array_pad($argv, 4, '');
ensure(str_starts_with($socket, '/tmp/empire_yard_mysql_v03_')
    && str_ends_with($socket, '/sock') && is_dir(dirname($socket)),
    'private ephemeral test socket only');
$db = new RealYardWPDB($socket);
$store = new Empire_Yard_Booking_Store($db);
$calendar = [
    'timezone' => 'Australia/Sydney',
    'hours' => [1 => ['08:00', '17:00'], 2 => ['08:00', '17:00'], 3 => ['08:00', '17:00']],
    'blackout_dates' => [],
];
switch ($mode) {
    case 'schema':
        foreach ($store->schema_sql() as $sql) { $db->query($sql); }
        ensure($store->ready(), 'InnoDB + unique slot index');
        echo "SCHEMA_READY\n";
        break;
    case 'hold':
        $who = basename($gate);
        file_put_contents($gate . '.ready', $who);
        $start = microtime(true);
        while (!file_exists(dirname($gate) . '/go')) {
            if (microtime(true) - $start > 12) { throw new RuntimeException('Barrier timeout'); }
            usleep(10000);
        }
        try {
            $id = $store->hold('bay-1', 'repair', '2026-10-26', '10:00', 60, 'Australia/Sydney', $calendar);
            echo json_encode(['result' => 'ACCEPTED', 'id' => $id]) . "\n";
        } catch (Throwable $error) {
            echo json_encode(['result' => 'DENIED', 'type' => get_class($error)]) . "\n";
        }
        break;
    case 'verify':
        ensure($store->ready(), 'verified schema');
        $rows = $store->recent();
        ensure(count($rows) === 1, 'exactly one booking row');
        ensure($rows[0]['status'] === 'held', 'held state');
        ensure((int)$db->get_var('SELECT COUNT(*) FROM wp_stage_empire_yard_booking_slots') === 4, 'four occupied quarter-hour slots');
        ensure((int)$db->get_var('SELECT COUNT(*) FROM wp_stage_empire_yard_booking_events') === 1, 'one immutable audit event');
        $unique = $db->get_var("SELECT GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX SEPARATOR ',') FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'wp_stage_empire_yard_booking_slots' AND INDEX_NAME = 'bay_slot' AND NON_UNIQUE = 0");
        ensure($unique === 'bay,slot_utc', 'unique bay slot index active');
        echo json_encode(['result' => 'MYSQL_TWO_PROCESS_BOOKING_PASS', 'bookings' => 1, 'slots' => 4, 'audits' => 1]) . "\n";
        break;
    case 'cancel_rebook':
        $rows = $store->recent();
        ensure(count($rows) === 1, 'precondition held booking exists');
        $id = (int)$rows[0]['id'];
        ensure($store->transition($id, 'cancelled'), 'cancel persisted');
        ensure((int)$db->get_var('SELECT COUNT(*) FROM wp_stage_empire_yard_booking_slots') === 0, 'cancellation released slots');
        $next = $store->hold('bay-1', 'repair', '2026-10-26', '10:00', 60, 'Australia/Sydney', $calendar);
        ensure($next !== $id, 'rebooking new id');
        ensure((int)$db->get_var('SELECT COUNT(*) FROM wp_stage_empire_yard_booking_slots') === 4, 'rebook slots present');
        ensure((int)$db->get_var('SELECT COUNT(*) FROM wp_stage_empire_yard_booking_events') === 3, 'audits of hold cancel rebook');
        echo json_encode(['result' => 'MYSQL_CANCEL_REBOOK_PASS', 'bookings' => 2, 'slots' => 4, 'audits' => 3]) . "\n";
        break;
    default: throw new RuntimeException('Invalid disposable test mode');
}
