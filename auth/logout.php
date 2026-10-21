<?php
require_once __DIR__ . '/../config/helpers.php';
require_post();

if (!empty($_SESSION['user'])) {
    log_activity('LOGOUT', $_SESSION['user']['full_name'] . ' logged out');
}
$_SESSION = [];
if (ini_get('session.use_cookies')) {
    $p = session_get_cookie_params();
    setcookie(session_name(), '', time() - 42000, $p['path'], $p['domain'], $p['secure'], $p['httponly']);
}
session_destroy();
ok('You have been logged out.');
