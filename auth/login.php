<?php
require_once __DIR__ . '/../config/helpers.php';
require_post();

$in       = input();
$username = trim((string)($in['username'] ?? ''));
$password = (string)($in['password'] ?? '');

if ($username === '' || $password === '') {
    fail('Please complete all required fields.');
}

$st = db()->prepare('SELECT id, username, full_name, password_hash, role, is_active FROM users WHERE username = ? LIMIT 1');
$st->execute([$username]);
$u = $st->fetch();

if (!$u || !password_verify($password, $u['password_hash'])) {
    fail('Invalid login credentials.', 401);
}
if (!(int)$u['is_active']) {
    fail('This account has been disabled. Please contact the administrator.', 403);
}

session_regenerate_id(true);
$_SESSION['user'] = [
    'id'        => (int)$u['id'],
    'username'  => $u['username'],
    'full_name' => $u['full_name'],
    'role'      => $u['role'],
];

if (password_needs_rehash($u['password_hash'], PASSWORD_DEFAULT)) {
    db()->prepare('UPDATE users SET password_hash = ? WHERE id = ?')
        ->execute([password_hash($password, PASSWORD_DEFAULT), $u['id']]);
}

log_activity('LOGIN', $u['full_name'] . ' logged in', null, (int)$u['id']);
ok('Login successful.', ['role' => $u['role']]);
