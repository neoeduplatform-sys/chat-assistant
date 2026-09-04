<?php
// This file is part of the local_chatassistant plugin for Moodle.

namespace local_chatassistant\local;

defined('MOODLE_INTERNAL') || die();

/**
 * Maps a Moodle course record to the course_id string expected by the chat API.
 */
class course_mapper {
    /**
     * @param \stdClass $course Moodle course row (must include id, shortname, idnumber).
     * @param string $strategy One of: moodle_id, shortname, idnumber, shortname_fallback_id.
     */
    public static function to_api_course_id(\stdClass $course, string $strategy): string {
        switch ($strategy) {
            case 'shortname':
                $sn = isset($course->shortname) ? trim((string) $course->shortname) : '';
                if ($sn === '') {
                    return (string) ((int) $course->id);
                }
                return $sn;

            case 'idnumber':
                $idn = isset($course->idnumber) ? trim((string) $course->idnumber) : '';
                if ($idn === '') {
                    return (string) ((int) $course->id);
                }
                return $idn;

            case 'shortname_fallback_id':
                $sn = isset($course->shortname) ? trim((string) $course->shortname) : '';
                return $sn !== '' ? $sn : (string) ((int) $course->id);

            case 'moodle_id':
            default:
                return (string) ((int) $course->id);
        }
    }
}
