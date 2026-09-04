<?php
// This file is part of the local_chatassistant plugin for Moodle.

defined('MOODLE_INTERNAL') || die();

$string['pluginname'] = 'Chat assistant (Kumu)';
$string['privacy:metadata'] = 'This plugin injects a JavaScript chat widget and issues short-lived JWTs for the chat API. No personal data is stored by this plugin.';

$string['jwtsecret'] = 'JWT shared secret';
$string['jwtsecret_desc'] = 'Must match JWT_SECRET on the chat API server. Never commit this value to source control.';
$string['jwtttl'] = 'Token lifetime (seconds)';
$string['jwtttl_desc'] = 'JWT exp claim: time-to-live in seconds from page render.';
$string['jwtissuer'] = 'JWT issuer (iss)';
$string['jwtissuer_desc'] = 'Optional. If your API sets JWT_ISSUER, enter the exact same string here so tokens include iss.';
$string['apiurl'] = 'Chat API URL';
$string['apiurl_desc'] = 'Full URL of POST /api/chat (e.g. https://api.example.com/api/chat).';
$string['widgeturl'] = 'Widget script URL';
$string['widgeturl_desc'] = 'Full URL to chat-widget.js.';
$string['historyurl'] = 'History API URL (optional)';
$string['historyurl_desc'] = 'Full URL of GET /api/chat/history. Leave empty to derive from Chat API URL.';
$string['courseidsource'] = 'Course ID claim source';
$string['courseidsource_desc'] = 'How to build the course_id JWT claim for your backend register of courses.';
$string['courseid_moodleid'] = 'Moodle internal course id (numeric as string)';
$string['courseid_shortname'] = 'Course shortname';
$string['courseid_idnumber'] = 'Course idnumber (falls back to Moodle id if empty)';
$string['courseid_shortname_fallback'] = 'shortname, or Moodle id if shortname empty';
