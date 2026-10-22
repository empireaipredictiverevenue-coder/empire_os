<?php
/** Verify restored files + MariaDB SQL dump load into a second database. */
declare(strict_types=1);
$root = getenv('YARD_RESTORED_SITE_DIR');
if (!is_string($root) || !is_file($root.'/wp-load.php')) { throw new RuntimeException('Restore tree missing'); }
require_once $root.'/wp-load.php';
function assert_restore(bool $condition, string $reason): void {
    if (!$condition) { throw new RuntimeException('Restore parity failed: '.$reason); }
}
assert_restore(is_blog_installed(), 'WordPress installed schema');
assert_restore(wp_get_theme()->get_stylesheet()==='empire-yard-atelier','active WordPress block theme');
$vehicles=get_posts(['post_type'=>'empire_vehicle','post_status'=>'publish','posts_per_page'=>10]);
assert_restore(count($vehicles)===1,'synthetic vehicle record');
$v=$vehicles[0];
assert_restore(get_post_meta($v->ID,'yard_status',true)==='available','vehicle metadata');
$thumbnail=(int)get_post_thumbnail_id($v->ID);
assert_restore($thumbnail>0,'attached image exists');
$file=get_attached_file($thumbnail);
assert_restore(is_string($file) && is_file($file),'restored attachment exists');
$pages=get_posts(['post_type'=>'page','post_status'=>'publish','posts_per_page'=>20]);
assert_restore(count($pages)>=6,'six example pages');
global $wpdb;
$bookings=(int)$wpdb->get_var("SELECT COUNT(*) FROM {$wpdb->prefix}empire_yard_bookings");
$events=(int)$wpdb->get_var("SELECT COUNT(*) FROM {$wpdb->prefix}empire_yard_booking_events");
assert_restore($bookings===1, 'one historical booking');
assert_restore($events===3, 'hold confirm cancel audit trail');
$store=new Empire_Yard_Booking_Store($wpdb);
assert_restore($store->ready()===false,'anonymous context cannot mutate restored booking store');
echo json_encode(['status'=>'NATIVE_WP_MYSQL_RESTORE_PASS',
    'pages'=>count($pages),'vehicles'=>count($vehicles),
    'attachment_sha256'=>hash_file('sha256',$file),
    'booking_rows'=>$bookings,'booking_audit_events'=>$events,
    'active_theme'=>wp_get_theme()->get_stylesheet(),
    'production_modified'=>false],JSON_UNESCAPED_SLASHES),"\n";
