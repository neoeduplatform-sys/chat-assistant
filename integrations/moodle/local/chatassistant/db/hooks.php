<?php
// This file is part of the local_chatassistant plugin for Moodle.

defined('MOODLE_INTERNAL') || die();

$callbacks = [
    [
        'hook' => \core\hook\output\before_footer_html_generation::class,
        'callback' => [\local_chatassistant\hook_callbacks::class, 'before_footer_html_generation'],
        'priority' => 0,
    ],
];
