<?php
require_once __DIR__ . '/../config/helpers.php';
require_post();
require_role('ADMIN');

$in = input();
$v  = validate_volunteer_input($in);

// Optional login account for the volunteer
$username = trim((string)($in['username'] ?? ''));
$password = (string)($in['password'] ?? '');
$makeAccount = $username !== '' || $password !== '';
if ($makeAccount) {
    if (!preg_match('/^[A-Za-z0-9_.]{4,30}$/', $username)) {
        fail('Username must be 4 to 30 characters (letters, numbers, dot or underscore).');
    }
    if (strlen($password) < 8) {
        fail('Password must be at least 8 characters.');
    }
}

$pdo = db();
$pdo->beginTransaction();
try {
    $userId = null;
    if ($makeAccount) {
        $pdo->prepare("INSERT INTO users (username, full_name, password_hash, role) VALUES (?, ?, ?, 'VOLUNTEER')")
            ->execute([$username, $v['name'], password_hash($password, PASSWORD_DEFAULT)]);
        $userId = (int)$pdo->lastInsertId();
    }
    $pdo->prepare(
        'INSERT INTO volunteers (user_id, full_name, contact, skill, availability, status, latitude, longitude)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
    )->execute([$userId, $v['name'], $v['contact'], $v['skill'], $v['avail'], $v['status'], $v['lat'], $v['lng']]);
    $id   = (int)$pdo->lastInsertId();
    $code = sprintf('V-%04d', $id);
    $pdo->prepare('UPDATE volunteers SET volunteer_code = ? WHERE id = ?')->execute([$code, $id]);
    $pdo->commit();
} catch (PDOException $e) {
    if ($pdo->inTransaction()) {
        $pdo->rollBack();
    }
    if ($e->getCode() === '23000') {
        fail('That username is already taken.', 409);
    }
    throw $e;
}

log_activity('VOLUNTEER_ADDED', "Admin added Volunteer $code ({$v['name']})");
ok('Volunteer added successfully.', ['id' => $id, 'volunteer_code' => $code]);
