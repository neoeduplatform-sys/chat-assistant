<?php
// This file is part of the local_chatassistant plugin for Moodle.

namespace local_chatassistant;

use core\hook\output\before_footer_html_generation;
use local_chatassistant\local\course_mapper;
use local_chatassistant\local\jwt_helper;

defined('MOODLE_INTERNAL') || die();

/**
 * Injects chat widget globals + script on relevant course pages.
 */
class hook_callbacks {
    public static function before_footer_html_generation(before_footer_html_generation $hook): void {
        self::register_widget_requirements();
    }

    /**
     * Build the widget HTML or return null when not applicable.
     *
     * This is shared by both the Hooks API subscriber and the legacy output callback.
     */
    public static function build_widget_html(): ?string {
        // Backwards-compatible entry point used by the legacy callback.
        // Prefer $PAGE->requires injection for themes/CSP compatibility.
        return self::register_widget_requirements();
    }

    /**
     * Registers the widget via Moodle's $PAGE->requires and returns HTML fallback.
     *
     * Using $PAGE->requires is more reliable than emitting <script> tags directly,
     * because some themes / security filters may strip or defer inline scripts
     * inserted into footer output.
     *
     * @return string|null HTML fallback (usually empty string) or null when not applicable.
     */
    public static function register_widget_requirements(): ?string {
        global $PAGE, $USER, $SITE, $COURSE;

        // Diagnostic marker to confirm this callback runs on the page.
        // This helps troubleshoot cases where the widget script never appears.
        $PAGE->requires->js_init_code(
            'window.__LOCAL_CHATASSISTANT_PLUGIN_RAN__=true;'
        );

        if (!isloggedin() || isguestuser()) {
            $PAGE->requires->js_init_code('window.__LOCAL_CHATASSISTANT_STATUS__="not_logged_in_or_guest";');
            return null;
        }

        // Resolve course context robustly.
        // Some Moodle pages (depending on theme / routing) may not populate $PAGE->course.
        $course = null;
        if (isset($PAGE->course) && !empty($PAGE->course->id)) {
            $course = $PAGE->course;
        } else if (isset($COURSE) && !empty($COURSE->id)) {
            $course = $COURSE;
        } else if (isset($PAGE->context) && isset($PAGE->context->contextlevel)) {
            // CONTEXT_COURSE = 50, CONTEXT_MODULE = 70 (constants in core).
            if ((int) $PAGE->context->contextlevel === 50) {
                try {
                    $course = get_course((int) $PAGE->context->instanceid);
                } catch (\Throwable $e) {
                    $course = null;
                }
            } else if ((int) $PAGE->context->contextlevel === 70 && isset($PAGE->cm) && !empty($PAGE->cm->course)) {
                try {
                    $course = get_course((int) $PAGE->cm->course);
                } catch (\Throwable $e) {
                    $course = null;
                }
            }
        }

        if (!$course || empty($course->id)) {
            $PAGE->requires->js_init_code('window.__LOCAL_CHATASSISTANT_STATUS__="no_course_context";');
            return null;
        }

        $courseid = (int) $course->id;
        $siteid = isset($SITE->id) ? (int) $SITE->id : 1;
        if ($courseid <= 1 || $courseid === $siteid) {
            $PAGE->requires->js_init_code('window.__LOCAL_CHATASSISTANT_STATUS__="site_home_or_invalid_course";');
            return null;
        }

        $secret = get_config('local_chatassistant', 'jwt_secret');
        if ($secret === false || $secret === '') {
            $PAGE->requires->js_init_code('window.__LOCAL_CHATASSISTANT_STATUS__="missing_jwt_secret";');
            return null;
        }

        $ttl = (int) get_config('local_chatassistant', 'jwt_ttl_seconds');
        if ($ttl <= 0) {
            $ttl = 7200;
        }

        $issuerconfig = get_config('local_chatassistant', 'jwt_issuer');
        $issuer = ($issuerconfig !== false && trim((string) $issuerconfig) !== '')
            ? trim((string) $issuerconfig)
            : '';

        $strategy = get_config('local_chatassistant', 'course_id_source');
        if ($strategy === false || $strategy === '') {
            $strategy = 'moodle_id';
        }

        $apicourseid = course_mapper::to_api_course_id($course, $strategy);

        try {
            $jwt = jwt_helper::encode((string) $USER->id, $apicourseid, $ttl, $issuer !== '' ? $issuer : null);
        } catch (\Throwable $e) {
            debugging('local_chatassistant: JWT encode failed: ' . $e->getMessage(), DEBUG_DEVELOPER);
            return null;
        }

        $apiurl = get_config('local_chatassistant', 'api_url');
        if ($apiurl === false || trim((string) $apiurl) === '') {
            $PAGE->requires->js_init_code('window.__LOCAL_CHATASSISTANT_STATUS__="missing_api_url";');
            return null;
        }
        $apiurl = trim((string) $apiurl);

        $widgeturl = get_config('local_chatassistant', 'widget_url');
        if ($widgeturl === false || trim((string) $widgeturl) === '') {
            $PAGE->requires->js_init_code('window.__LOCAL_CHATASSISTANT_STATUS__="missing_widget_url";');
            return null;
        }
        $widgeturl = trim((string) $widgeturl);

        $historyconfig = get_config('local_chatassistant', 'history_url');
        $historyurl = ($historyconfig !== false && trim((string) $historyconfig) !== '')
            ? trim((string) $historyconfig)
            : self::derive_history_url($apiurl);

        // Register config first, then load script.
        $flags = JSON_HEX_TAG | JSON_HEX_APOS | JSON_HEX_QUOT | JSON_HEX_AMP | JSON_UNESCAPED_SLASHES;
        $tokenjs = json_encode($jwt, $flags);
        $apijs = json_encode($apiurl, $flags);
        $histjs = json_encode($historyurl, $flags);
        $coursejs = json_encode($apicourseid, $flags);

        $PAGE->requires->js_init_code(
            'window.CHATBOT_TOKEN=' . $tokenjs . ';' .
            'window.CHATBOT_API_URL=' . $apijs . ';' .
            'window.CHATBOT_HISTORY_URL=' . $histjs . ';' .
            'window.CHATBOT_COURSE_ID=' . $coursejs . ';'
        );

        // Load external widget script.
        $PAGE->requires->js(new \moodle_url($widgeturl));

        // No extra HTML needed when using $PAGE->requires.
        return '';
    }

    /**
     * Same derivation as frontend/chat-widget.js when CHATBOT_HISTORY_URL is unset.
     */
    private static function derive_history_url(string $apiurl): string {
        $trimmed = preg_replace('#/api/chat/?$#i', '', rtrim($apiurl));
        return rtrim($trimmed, '/') . '/api/chat/history';
    }

    /**
     * @return string Safe HTML fragments (inline JSON for globals + external script tag).
     */
    private static function build_inline_script_html(
        string $jwt,
        string $apiurl,
        string $historyurl,
        string $courseidclaim,
        string $widgeturl
    ): string {
        $flags = JSON_HEX_TAG | JSON_HEX_APOS | JSON_HEX_QUOT | JSON_HEX_AMP | JSON_UNESCAPED_SLASHES;

        $tokenjs = json_encode($jwt, $flags);
        $apijs = json_encode($apiurl, $flags);
        $histjs = json_encode($historyurl, $flags);
        $coursejs = json_encode($courseidclaim, $flags);

        $safesrc = htmlspecialchars($widgeturl, ENT_QUOTES | ENT_HTML5, 'UTF-8');

        return '<script>'
            . 'window.CHATBOT_TOKEN=' . $tokenjs . ';'
            . 'window.CHATBOT_API_URL=' . $apijs . ';'
            . 'window.CHATBOT_HISTORY_URL=' . $histjs . ';'
            . 'window.CHATBOT_COURSE_ID=' . $coursejs . ';'
            . '</script>'
            . '<script src="' . $safesrc . '"></script>';
    }
}
