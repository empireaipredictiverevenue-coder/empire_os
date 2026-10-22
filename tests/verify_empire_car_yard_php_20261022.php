<?php
declare(strict_types=1);

function must(bool $ok, string $message): void {
    if (!$ok) { throw new RuntimeException($message); }
}
$plugin = dirname(__DIR__) . '/prototypes/agency_wordpress_service_handoff_20261022/empire-car-yard/empire-car-yard.php';

define('ABSPATH', __DIR__ . '/');
$GLOBALS['vehicle_registration'] = null;
$GLOBALS['meta_registration'] = [];
function add_action(...$args): void {}
function add_shortcode(...$args): void {}
function register_post_type($name, $args): void { $GLOBALS['vehicle_registration'] = [$name, $args]; }
function register_post_meta($type, $field, $args): void { $GLOBALS['meta_registration'][$field] = $args; }
function current_user_can(string $cap): bool { return false; }
function sanitize_key(string $s): string { return preg_replace('/[^a-z0-9_\-]/', '', strtolower($s)); }
function sanitize_text_field(string $s): string { return trim(strip_tags($s)); }
function absint($s): int { return abs((int) $s); }
require_once $plugin;
empire_yard_register_inventory();
[$type, $config] = $GLOBALS['vehicle_registration'];
must($type === 'empire_vehicle', 'Wrong post type');
must($config['public'] === false && $config['publicly_queryable'] === false, 'Direct public CPT must stay disabled');
must($config['show_in_rest'] === false && $config['exclude_from_search'] === true, 'Public REST/search must stay disabled');
must($config['capabilities']['edit_posts'] === 'manage_options', 'Admin-only mutation gate');
must(count($GLOBALS['meta_registration']) === 6, 'Expected six fields');
foreach ($GLOBALS['meta_registration'] as $field => $settings) {
    must($settings['show_in_rest'] === false && ($settings['auth_callback'])() === false, 'Meta access gate: ' . $field);
}
must(empire_yard_sanitize('yard_status', '<script>sale</script>') === 'archived', 'Unknown status must archive');
must(empire_yard_sanitize('yard_status', 'AVAILABLE') === 'available', 'Status normalisation');
must(empire_yard_sanitize('yard_year', '1800') === 0, 'Old year must fail');
must(empire_yard_sanitize('yard_year', '2020') === 2020, 'Year parse');
must(empire_yard_sanitize('yard_odometer_km', '999999999') === 9999999, 'Odometer cap');
must(empire_yard_sanitize('yard_make', '<b>Ford</b>') === 'Ford', 'Text field sanitisation');

$rules = Empire_Yard_Booking_Rules::class;
$slot = $rules::slot('2026-10-22', '10:00', 60, 'Europe/London');
must($slot['start_utc'] === '2026-10-22 09:00:00', 'Timezone conversion');
must($slot['end_utc'] === '2026-10-22 10:00:00', 'Elapsed duration');
foreach ([['2026-03-29', '01:30'], ['2026-10-25', '01:30']] as [$date, $time]) {
    $raised = false;
    try { $rules::slot($date, $time, 30, 'Europe/London'); }
    catch (InvalidArgumentException $e) { $raised = true; }
    must($raised, 'DST gap/fold must fail closed: ' . $date);
}
foreach ([['2026-10-04', '02:30'], ['2027-04-04', '02:30']] as [$date, $time]) {
    $raised = false;
    try { $rules::slot($date, $time, 30, 'Australia/Sydney'); }
    catch (InvalidArgumentException $e) { $raised = true; }
    must($raised, 'Australian DST gap/fold: ' . $date);
}
must(!$rules::overlaps('2026-10-22 09:00:00', '2026-10-22 10:00:00', '2026-10-22 10:00:00', '2026-10-22 11:00:00'), 'Adjacent slots');
must($rules::overlaps('2026-10-22 09:00:00', '2026-10-22 10:00:00', '2026-10-22 09:45:00', '2026-10-22 11:00:00'), 'Overlaps');
$first = ['bay' => 'bay-1', 'status' => 'confirmed', 'start_utc' => '2026-10-22 09:00:00', 'end_utc' => '2026-10-22 10:00:00'];
$second = ['bay' => 'bay-1', 'status' => 'held', 'start_utc' => '2026-10-22 09:30:00', 'end_utc' => '2026-10-22 10:30:00'];
must($rules::conflicts($first, $second), 'Same-bay active overlap');
must(!$rules::conflicts($first, array_replace($second, ['bay' => 'bay-2'])), 'Different bay');
must(!$rules::conflicts($first, array_replace($second, ['status' => 'cancelled'])), 'Cancelled slot');
must($rules::canTransition('held', 'confirmed'), 'Hold to confirm');
must(!$rules::canTransition('completed', 'confirmed'), 'Completed slot immutable');
must(!$rules::canTransition('cancelled', 'held'), 'Cancelled slot immutable');
echo "EMPIRE_CAR_YARD_PHP_UNIT_PASS: WordPress shim inventory safety and DST/overlap/booking-state rules\n";
