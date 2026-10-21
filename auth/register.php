<?php
require_once __DIR__ . '/../config/helpers.php';
require_post();

$in       = input();
$username = trim((string)($in['username'] ?? ''));
$full     = clean((string)($in['full_name'] ?? ''));
$email    = trim((string)($in['email'] ?? ''));
$password = (string)($in['password'] ?? '');
$confirm  = (string)($in['confirm'] ?? '');

if ($username === '' || $full === '' || $password === '') {
    fail('Please complete all required fields.');
}
if (!preg_match('/^[A-Za-z0-9_.]{4,30}$/', $username)) {
    fail('Username must be 4 to 30 characters (letters, numbers, dot or underscore).');
}
if (mb_strlen($full) < 2 || mb_strlen($full) > 100) {
    fail('Full name must be 2 to 100 characters.');
}
if ($email !== '' && (!filter_var($email, FILTER_VALIDATE_EMAIL) || strlen($email) > 120)) {
    fail('Please enter a valid email address.');
}
if (strlen($password) < 8) {
    fail('Password must be at least 8 characters.');
}
if ($password !== $confirm) {
    fail('Passwords do not match.');
}

try {
    // Public registration always creates a REQUESTER account.
    $st = db()->prepare("INSERT INTO users (username, full_name, email, password_hash, role) VALUES (?, ?, ?, ?, 'REQUESTER')");
    $st->execute([$username, $full, $email === '' ? null : $email, password_hash($password, PASSWORD_DEFAULT)]);
} catch (PDOException $e) {
    if ($e->getCode() === '23000') {
        fail('That username is already taken.', 409);
    }
    throw $e;
}

$newId = (int)db()->lastInsertId();
log_activity('REGISTER', "New requester account created: $username", null, $newId);
ok('Account created successfully. You can now log in.');
