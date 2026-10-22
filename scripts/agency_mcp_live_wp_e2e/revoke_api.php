<?php
/** Test-site credential revocation. Never use on production. */
declare(strict_types=1);
require_once getenv('YARD_SITE_DIR').'/wp-load.php';
$user=get_user_by('login','demo_yard_admin');
if (!$user instanceof WP_User) {throw new RuntimeException('Synthetic user missing');}
$uuidFile=getenv('YARD_MCP_UUID_FILE');
if (!is_string($uuidFile) || !is_file($uuidFile)) {throw new RuntimeException('Ephemeral UUID missing');}
$uuid=trim((string)file_get_contents($uuidFile));
if (!wp_is_uuid($uuid)) {throw new RuntimeException('Invalid UUID fixture');}
$removed=WP_Application_Passwords::delete_application_password((int)$user->ID,$uuid);
if (is_wp_error($removed) || $removed !== true) {
    throw new RuntimeException('Credential revocation failed');
}
echo '{"status":"SYNTHETIC_WORDPRESS_APP_PASSWORD_REVOKED","production_changes":false}',"\n";
