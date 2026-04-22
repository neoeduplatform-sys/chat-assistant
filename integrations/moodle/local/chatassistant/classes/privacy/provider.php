<?php
// This file is part of the local_chatassistant plugin for Moodle.

namespace local_chatassistant\privacy;

defined('MOODLE_INTERNAL') || die();

/**
 * Metadata provider — plugin does not persist user data in Moodle DB.
 */
class provider implements \core_privacy\local\metadata\null_provider {
    /**
     * @return string Reason why this plugin stores no personal data locally.
     */
    public static function get_reason(): string {
        return 'privacy:metadata';
    }
}
