<?php
// This file is part of the local_chatassistant plugin for Moodle.

namespace local_chatassistant\local;

defined('MOODLE_INTERNAL') || die();

/**
 * Builds HS256 JWT payloads aligned with app/auth.py (sub, course_id, exp, iat; optional iss).
 */
class jwt_helper {
    /**
     * @throws \RuntimeException Missing secret or Firebase JWT unavailable.
     */
    public static function encode(string $userid, string $courseid, int $ttlseconds, ?string $issuer): string {
        $secret = get_config('local_chatassistant', 'jwt_secret');
        if ($secret === false || $secret === '') {
            throw new \RuntimeException('JWT secret not configured');
        }

        $now = time();
        $payload = [
            'sub' => $userid,
            'course_id' => $courseid,
            'iat' => $now,
            'exp' => $now + $ttlseconds,
        ];
        if ($issuer !== null && $issuer !== '') {
            $payload['iss'] = $issuer;
        }

        return \Firebase\JWT\JWT::encode($payload, $secret, 'HS256');
    }
}
