<?php
// This file is part of the local_chatassistant plugin for Moodle.

defined('MOODLE_INTERNAL') || die();

/**
 * Legacy output callback.
 *
 * Some sites/themes rely on legacy output callbacks, or the Hooks API may be
 * disabled/misconfigured. Moodle core will also call legacy callbacks from the
 * Hooks API via process_legacy_callbacks() in some contexts, but providing the
 * legacy callback explicitly makes injection more robust across versions.
 *
 * @return string HTML to append before the footer, or empty string.
 */
function local_chatassistant_before_footer(): string {
    // Lazy-load the class (Moodle autoloader should handle it).
    // We register via $PAGE->requires and return empty HTML.
    $html = \local_chatassistant\hook_callbacks::build_widget_html();
    return $html ?? '';
}
