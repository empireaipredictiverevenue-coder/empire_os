<?php
/** Synthetic native WordPress staging bootstrap. Run only in disposable tree. */
declare(strict_types=1);
define('WP_ADMIN', true);
define('WP_INSTALLING', true);
require_once getenv('YARD_SITE_DIR') . '/wp-load.php';
require_once ABSPATH . 'wp-admin/includes/upgrade.php';
require_once ABSPATH . 'wp-admin/includes/plugin.php';
require_once ABSPATH . 'wp-admin/includes/image.php';
$adminPassword = getenv('YARD_ADMIN_PASSWORD');
if (!is_string($adminPassword) || strlen($adminPassword) < 32) {
    throw new RuntimeException('Synthetic test credential unavailable');
}
if (!is_blog_installed()) {
    wp_install('Synthetic Vehicle Workshop', 'demo_yard_admin', 'test@example.invalid', false, '', $adminPassword, 'en_US');
}
$admin = get_user_by('login', 'demo_yard_admin');
if (!$admin instanceof WP_User) { throw new RuntimeException('Admin not installed'); }
wp_set_current_user((int) $admin->ID);

$activated = activate_plugin('empire-car-yard/empire-car-yard.php');
if (is_wp_error($activated)) { throw new RuntimeException('Plugin activation: ' . $activated->get_error_message()); }
if (!post_type_exists('empire_vehicle')) {
    empire_yard_register_inventory();
}
switch_theme('empire-yard-atelier');
update_option('blog_public', '0');
update_option('permalink_structure', '/%postname%/');
flush_rewrite_rules(false);

$pages = [
    'home' => 'Home', 'services' => 'Services', 'about' => 'About',
    'areas' => 'Areas', 'contact' => 'Contact',
];
$created = [];
foreach ($pages as $slug => $title) {
    $id = wp_insert_post(['post_type'=>'page', 'post_title'=>$title,
        'post_name'=>$slug, 'post_status'=>'publish',
        'post_content'=>'Fictional service website integration test. No live enquiries.'], true);
    if (is_wp_error($id) || (int)$id < 1) { throw new RuntimeException('Page creation failed: '.$slug); }
    $created[$slug] = (int)$id;
}
update_option('show_on_front', 'page');
update_option('page_on_front', $created['home']);
$stock = wp_insert_post(['post_type'=>'page', 'post_title'=>'Synthetic Stock',
    'post_name'=>'demo-stock', 'post_status'=>'publish',
    'post_content'=>'[empire_car_yard_inventory]'], true);
if (is_wp_error($stock) || (int)$stock < 1) { throw new RuntimeException('Inventory page creation failed'); }
$vehicle = wp_insert_post(['post_type'=>'empire_vehicle', 'post_status'=>'publish',
    'post_title'=>'SYNTHETIC DEMO BLUE VAN',
    'post_content'=>'Synthetic inventory only. Not for sale.'], true);
if (is_wp_error($vehicle) || (int)$vehicle < 1) { throw new RuntimeException('Vehicle insertion failed'); }
foreach (['yard_make'=>'Ford', 'yard_model'=>'Transit', 'yard_year'=>2020,
    'yard_odometer_km'=>34000, 'yard_status'=>'available', 'yard_fuel'=>'Diesel'] as $key=>$value) {
    if (!update_post_meta((int)$vehicle, $key, $value)) {
        throw new RuntimeException('Vehicle metadata failed: '.$key);
    }
}

$imageSource=getenv('YARD_FAKE_IMAGE');
if (!is_string($imageSource) || !is_file($imageSource)) { throw new RuntimeException('Synthetic image missing'); }
$upload=wp_upload_dir();
if ($upload['error']) { throw new RuntimeException('Upload directory error'); }
$dest=$upload['path'].'/synthetic-blue-van.png';
if (!copy($imageSource, $dest)) { throw new RuntimeException('Synthetic image copy failed'); }
$attachment=wp_insert_attachment([
    'post_mime_type'=>'image/png', 'post_title'=>'Synthetic Blue Van',
    'post_content'=>'Synthetic artwork; not a real vehicle', 'post_status'=>'inherit'
], $dest, (int)$vehicle, true);
if (is_wp_error($attachment) || (int)$attachment < 1) { throw new RuntimeException('Attachment insert failed'); }
$metadata=wp_generate_attachment_metadata((int)$attachment,$dest);
if (!is_array($metadata)) { throw new RuntimeException('GD image metadata generation failed'); }
wp_update_attachment_metadata((int)$attachment,$metadata);
if (!set_post_thumbnail((int)$vehicle,(int)$attachment)) { throw new RuntimeException('Featured image failed'); }

global $wpdb;
$store=new Empire_Yard_Booking_Store($wpdb);
foreach ($store->schema_sql() as $sql) {
    if ($wpdb->query($sql) === false) { throw new RuntimeException('Staging-only MySQL DDL failed'); }
}
if (!$store->ready()) { throw new RuntimeException('Native WordPress InnoDB readiness failed'); }
$calendar=apply_filters('empire_yard_staff_calendar',[]);
if (!is_array($calendar) || !isset($calendar['timezone']) || $calendar['timezone'] !== 'Australia/Sydney') {
    throw new RuntimeException('Staging calendar missing');
}
echo json_encode([
    'status'=>'NATIVE_WP_MYSQL_STAGE_BOOTSTRAP_PASS',
    'wordpress'=>get_bloginfo('version'), 'php'=>PHP_VERSION,
    'plugin_active'=>is_plugin_active('empire-car-yard/empire-car-yard.php'),
    'theme'=>wp_get_theme()->get_stylesheet(),
    'pages_created'=>count($created)+1,
    'vehicle_id'=>(int)$vehicle, 'synthetic_attachment_id'=>(int)$attachment,
    'native_wpdb_innodb_ready'=>$store->ready(),
    'synthetic_only'=>true
], JSON_UNESCAPED_SLASHES|JSON_PRETTY_PRINT), "\n";
