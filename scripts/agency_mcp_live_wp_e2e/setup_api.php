<?php
/** Real disposable WordPress+MariaDB staging only. Credentials never printed. */
declare(strict_types=1);
require_once getenv('YARD_SITE_DIR').'/wp-load.php';
require_once ABSPATH.'wp-admin/includes/plugin.php';
if (wp_get_environment_type() !== 'local' ||
    !defined('EMPIRE_AGENCY_STAGING_INTEGRATIONS_ENABLED') ||
    !EMPIRE_AGENCY_STAGING_INTEGRATIONS_ENABLED ||
    !EMPIRE_AGENCY_SYNTHETIC_INVENTORY_ONLY) {
    throw new RuntimeException('Staging integration flags missing');
}
$user=get_user_by('login','demo_yard_admin');
if (!$user instanceof WP_User || !user_can($user,'manage_options')) {
    throw new RuntimeException('No authorised synthetic admin user');
}
wp_set_current_user((int)$user->ID);
$result=activate_plugin('empire-agency-integration-bridge/empire-agency-integration-bridge.php');
if (is_wp_error($result) || !is_plugin_active('empire-agency-integration-bridge/empire-agency-integration-bridge.php')) {
    throw new RuntimeException('Integration bridge activation failed');
}
if (!class_exists('WP_Application_Passwords') || !wp_is_application_passwords_available()) {
    throw new RuntimeException('Local WP application-password support unavailable');
}
$created=WP_Application_Passwords::create_new_application_password((int)$user->ID,[
    'name'=>'Ephemeral MCP staging integration test',
    'app_id'=>wp_generate_uuid4(),
]);
if (is_wp_error($created)) {
    throw new RuntimeException('Test app credential refused, error code: '.$created->get_error_code());
}
$entry = is_array($created[0] ?? null) ? $created[0] : (is_array($created[1] ?? null) ? $created[1] : null);
$password = is_string($created[0] ?? null) ? $created[0] : (is_string($created[1] ?? null) ? $created[1] : null);
if (!is_array($entry) || !isset($entry['uuid']) || !is_string($password) || strlen($password) < 20) {
    throw new RuntimeException('WordPress credential returned unexpected tuple types');
}
$secretFile=getenv('YARD_MCP_SECRET_FILE');
$uuidFile=getenv('YARD_MCP_UUID_FILE');
if (!is_string($secretFile) || !is_string($uuidFile) ||
    file_exists($secretFile) || file_exists($uuidFile)) {
    throw new RuntimeException('Fresh private credential paths required');
}
if (file_put_contents($secretFile, $password, LOCK_EX)===false ||
    file_put_contents($uuidFile, $entry['uuid'], LOCK_EX)===false) {
    throw new RuntimeException('Private fixture credentials unavailable');
}
chmod($secretFile,0600);
chmod($uuidFile,0600);
echo wp_json_encode([
    'status'=>'SYNTHETIC_WORDPRESS_APP_PASSWORD_CREATED',
    'integration_enabled'=>empire_agency_integration_enabled(),
    'plugin_active'=>true,'credential_written_to_private_temp_file'=>true,
    'wordpress_version'=>get_bloginfo('version'),
    'php_version'=>PHP_VERSION,
    'production_changes'=>false
], JSON_UNESCAPED_SLASHES),"\n";
