<?php
/** Vite-built, locally bundled React/Three.js WordPress child theme. */
declare(strict_types=1);
if (!defined('ABSPATH')) { exit; }
add_action('wp_enqueue_scripts', static function (): void {
    $dir = get_stylesheet_directory();
    $url = get_stylesheet_directory_uri();
    $css = $dir . '/dist/yard.css';
    $js = $dir . '/dist/yard.js';
    if (is_file($css)) {
        wp_enqueue_style('empire-yard-tailwind', $url . '/dist/yard.css', [], (string) filemtime($css));
    }
    if (is_front_page() && is_file($js)) {
        wp_enqueue_script('empire-yard-react-three', $url . '/dist/yard.js', [], (string) filemtime($js), true);
    }
    // Tailwind utilities augment read-only demo stock without altering plugin or booking logic.
    $enhance = $dir . '/src/inventory-enhance.js';
    if (is_page('demo-stock') && is_file($enhance)) {
        wp_enqueue_script('empire-yard-stock-presentation', $url . '/src/inventory-enhance.js', [], (string) filemtime($enhance), true);
    }
});
