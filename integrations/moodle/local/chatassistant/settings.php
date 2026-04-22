<?php
// This file is part of the local_chatassistant plugin for Moodle.

defined('MOODLE_INTERNAL') || die();

if ($hassiteconfig) {
    // Create a dedicated settings page under: Site administration -> Plugins -> Local plugins.
    $settings = new admin_settingpage('localsettingchatassistant', get_string('pluginname', 'local_chatassistant'));
    $ADMIN->add('localplugins', $settings);

    $settings->add(new admin_setting_configpasswordunmask(
        'local_chatassistant/jwt_secret',
        get_string('jwtsecret', 'local_chatassistant'),
        get_string('jwtsecret_desc', 'local_chatassistant'),
        ''
    ));

    $settings->add(new admin_setting_configtext(
        'local_chatassistant/jwt_ttl_seconds',
        get_string('jwtttl', 'local_chatassistant'),
        get_string('jwtttl_desc', 'local_chatassistant'),
        '7200',
        PARAM_INT
    ));

    $settings->add(new admin_setting_configtext(
        'local_chatassistant/jwt_issuer',
        get_string('jwtissuer', 'local_chatassistant'),
        get_string('jwtissuer_desc', 'local_chatassistant'),
        '',
        PARAM_TEXT
    ));

    $courseidsources = [
        'moodle_id' => get_string('courseid_moodleid', 'local_chatassistant'),
        'shortname' => get_string('courseid_shortname', 'local_chatassistant'),
        'idnumber' => get_string('courseid_idnumber', 'local_chatassistant'),
        'shortname_fallback_id' => get_string('courseid_shortname_fallback', 'local_chatassistant'),
    ];
    $settings->add(new admin_setting_configselect(
        'local_chatassistant/course_id_source',
        get_string('courseidsource', 'local_chatassistant'),
        get_string('courseidsource_desc', 'local_chatassistant'),
        'moodle_id',
        $courseidsources
    ));

    $settings->add(new admin_setting_configtext(
        'local_chatassistant/api_url',
        get_string('apiurl', 'local_chatassistant'),
        get_string('apiurl_desc', 'local_chatassistant'),
        'http://localhost:8080/api/chat',
        PARAM_URL
    ));

    $settings->add(new admin_setting_configtext(
        'local_chatassistant/widget_url',
        get_string('widgeturl', 'local_chatassistant'),
        get_string('widgeturl_desc', 'local_chatassistant'),
        'http://localhost:8080/static/chat-widget.js',
        PARAM_URL
    ));

    $settings->add(new admin_setting_configtext(
        'local_chatassistant/history_url',
        get_string('historyurl', 'local_chatassistant'),
        get_string('historyurl_desc', 'local_chatassistant'),
        '',
        PARAM_URL
    ));
}
