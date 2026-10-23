<?php
/** Native WordPress child-theme integration for the Empire AI Atelier showroom. */
declare(strict_types=1);
if (!defined('ABSPATH')) { exit; }

function empire_yard_brand_defaults(): array {
    return [
        'name' => 'Atelier Motors',
        'strapline' => 'Showroom concept',
        'eyebrow' => 'The future of the showroom',
        'headline' => 'Drive something',
        'highlight' => 'extraordinary.',
        'description' => 'An immersive WordPress dealership concept with cinematic 3D, refined inventory discovery, and a governed service-workshop foundation.',
        'contact_label' => 'Enquiry info',
        'contact_path' => '/contact/',
        'accent' => 'gold',
    ];
}

/** Typed/size-bounded options; contact destinations cannot leave this WordPress site. */
function empire_yard_sanitize_brand($value): array {
    $defaults = empire_yard_brand_defaults();
    if (!is_array($value)) { return $defaults; }
    $out = $defaults;
    $limits = [
        'name' => 54, 'strapline' => 48, 'eyebrow' => 72,
        'headline' => 65, 'highlight' => 55, 'description' => 320,
        'contact_label' => 50,
    ];
    foreach ($limits as $key => $maxLength) {
        if (isset($value[$key]) && is_string($value[$key])) {
            $clean = $key === 'description'
                ? sanitize_textarea_field($value[$key])
                : sanitize_text_field($value[$key]);
            $clean = trim(mb_substr($clean, 0, $maxLength));
            if ($clean !== '') { $out[$key] = $clean; }
        }
    }
    if (isset($value['contact_path']) && is_string($value['contact_path'])) {
        $path = trim($value['contact_path']);
        if (preg_match('~^/(?:[a-z0-9-]+/){1,4}$~D', $path) === 1) {
            $out['contact_path'] = $path;
        }
    }
    if (isset($value['accent']) && in_array($value['accent'], ['gold', 'ice', 'copper'], true)) {
        $out['accent'] = $value['accent'];
    }
    return $out;
}
function empire_yard_brand_settings(): array {
    $stored = get_option('empire_yard_brand_v1', []);
    return empire_yard_sanitize_brand(is_array($stored) ? $stored : []);
}
add_action('admin_init', static function (): void {
    register_setting('empire_yard_branding', 'empire_yard_brand_v1', [
        'type' => 'array',
        'sanitize_callback' => 'empire_yard_sanitize_brand',
        'default' => empire_yard_brand_defaults(),
        'show_in_rest' => false,
    ]);
});
add_action('admin_menu', static function (): void {
    add_theme_page('Showroom Branding', 'Showroom Branding', 'edit_theme_options',
        'empire-yard-branding', 'empire_yard_branding_page');
});
function empire_yard_branding_page(): void {
    if (!current_user_can('edit_theme_options')) {
        wp_die(esc_html__('You are not allowed to edit this showroom.', 'empire-yard-atelier'));
    }
    $settings = empire_yard_brand_settings();
    $labels = [
        'name' => 'Display brand', 'strapline' => 'Brand strapline',
        'eyebrow' => 'Hero eyebrow', 'headline' => 'Hero headline',
        'highlight' => 'Hero highlighted words', 'description' => 'Hero description',
        'contact_label' => 'Contact button label', 'contact_path' => 'Internal contact page path',
    ];
    echo '<div class="wrap"><h1>Showroom Branding</h1>';
    echo '<p>Client-specific presentation only. No live vehicle sales, customer bookings or payments are enabled.</p>';
    echo '<form action="options.php" method="post">';
    settings_fields('empire_yard_branding');
    echo '<table class="form-table" role="presentation"><tbody>';
    foreach ($labels as $key => $label) {
        $id = 'empire_yard_' . $key;
        echo '<tr><th scope="row"><label for="' . esc_attr($id) . '">' . esc_html($label) . '</label></th><td>';
        if ($key === 'description') {
            echo '<textarea class="large-text" rows="4" id="' . esc_attr($id) . '" name="empire_yard_brand_v1[' . esc_attr($key) . ']">' . esc_textarea($settings[$key]) . '</textarea>';
        } else {
            echo '<input class="regular-text" type="text" id="' . esc_attr($id) . '" name="empire_yard_brand_v1[' . esc_attr($key) . ']" value="' . esc_attr($settings[$key]) . '" />';
        }
        if ($key === 'contact_path') {
            echo '<p class="description">Relative WordPress path only, e.g. /contact/; external URLs and queries are not allowed.</p>';
        }
        echo '</td></tr>';
    }
    echo '<tr><th scope="row"><label for="empire_yard_accent">Accent palette</label></th><td>';
    echo '<select id="empire_yard_accent" name="empire_yard_brand_v1[accent]">';
    foreach (['gold' => 'Champagne gold', 'ice' => 'Arctic ice', 'copper' => 'Warm copper'] as $value => $label) {
        echo '<option value="' . esc_attr($value) . '"' . selected($settings['accent'], $value, false) . '>' . esc_html($label) . '</option>';
    }
    echo '</select></td></tr></tbody></table>';
    submit_button('Save showroom branding');
    echo '</form></div>';
}

/** JSON data, never executable JS: React renders text safely. */
add_action('wp_head', static function (): void {
    if (!is_front_page()) { return; }
    $json = wp_json_encode(empire_yard_brand_settings(),
        JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT);
    if (!is_string($json)) { return; }
    echo '<script id="empire-yard-brand-settings" type="application/json">' . $json . '</script>' . "\n";
}, 3);

add_action('wp_enqueue_scripts', static function (): void {
    $dir = get_stylesheet_directory();
    $url = get_stylesheet_directory_uri();
    $css = $dir . '/dist/yard.css';
    $js = $dir . '/dist/yard.js';
    if (is_file($css)) {
        wp_enqueue_style('empire-yard-tailwind', $url . '/dist/yard.css', [], (string) filemtime($css));
    }
    if (is_front_page() && is_file($js)) {
        // The ES module entry keeps React and Three.js as separately cached chunks.
        if (function_exists('wp_enqueue_script_module')) {
            wp_enqueue_script_module('empire-yard-react-three', $url . '/dist/yard.js', [], (string) filemtime($js));
        }
    }
    // Tailwind utilities augment the existing read-only stock page.
    $enhance = $dir . '/src/inventory-enhance.js';
    if (is_page('demo-stock') && is_file($enhance)) {
        wp_enqueue_script('empire-yard-stock-presentation', $url . '/src/inventory-enhance.js', [], (string) filemtime($enhance), true);
    }
});

/**
 * Native WordPress template parts reuse the same brand as the React homepage.
 * No new endpoints or extra client-side frameworks.
 */
add_shortcode('empire_yard_site_nav', static function (): string {
    $brand = empire_yard_brand_settings();
    $accent = [
        'gold' => 'text-[#e7c794]', 'ice' => 'text-[#b6ddeb]',
        'copper' => 'text-[#dca87c]',
    ][$brand['accent']];
    return '<div class="bg-[#d5b37b] text-[#15212a] text-center text-[10px] font-extrabold uppercase tracking-[.28em] py-2 px-3">'
        . 'Fictional dealership demonstration — no live vehicles or bookings</div>'
        . '<nav data-yard-site-header="true" aria-label="Main navigation" class="bg-[#091923] text-white border-b border-white/15">'
        . '<div class="mx-auto max-w-6xl min-h-20 px-5 md:px-8 flex flex-wrap items-center justify-between gap-4 py-4">'
        . '<a href="/" class="text-white no-underline text-xl font-bold tracking-[.12em]">'
        . esc_html($brand['name']) . '<span class="block text-[9px] font-semibold uppercase tracking-[.25em] ' . esc_attr($accent) . '">'
        . esc_html($brand['strapline']) . '</span></a>'
        . '<div class="flex flex-wrap gap-5 text-sm">'
        . '<a class="text-slate-200 no-underline hover:text-white" href="/">Home</a>'
        . '<a class="text-slate-200 no-underline hover:text-white" href="/demo-stock/">Inventory</a>'
        . '<a class="text-slate-200 no-underline hover:text-white" href="/services/">Services</a>'
        . '<a class="text-slate-200 no-underline hover:text-white" href="' . esc_url($brand['contact_path']) . '">'
        . esc_html($brand['contact_label']) . '</a></div></div></nav>';
});
add_shortcode('empire_yard_site_footer', static function (): string {
    $brand = empire_yard_brand_settings();
    return '<div data-yard-site-footer="true" class="bg-[#091923] text-slate-300 py-12">'
        . '<div class="mx-auto max-w-6xl px-5 md:px-8 grid gap-5 md:grid-cols-2">'
        . '<div><p class="text-white font-bold uppercase tracking-widest">' . esc_html($brand['name']) . '</p>'
        . '<p class="text-xs leading-7">Fictional showroom UI. No actual stock, trading business, sales claims, customer intake, outbound messages or live booking.</p></div>'
        . '<div class="md:text-right text-xs leading-7"><p>Built within Empire AI&#039;s isolated WordPress delivery engine.</p>'
        . '<p>Commercial approval, privacy, consent and ownership remain pending.</p></div></div></div>';
});
