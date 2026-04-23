<?php
// This file is part of the local_chatassistant plugin for Moodle.
//
// It is distributed under the GNU GPL v3 or later.

defined('MOODLE_INTERNAL') || die();

$plugin->component = 'local_chatassistant';
$plugin->version   = 2026042205;
$plugin->requires  = 2024042200; // Moodle 4.4 — Hooks API (before_footer_html_generation).
$plugin->maturity  = MATURITY_STABLE;
$plugin->release   = '1.0.0';
