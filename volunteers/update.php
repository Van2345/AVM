<?php
require_once __DIR__ . '/../config/helpers.php';
require_post();
require_role('ADMIN');
$pdo = db();

$in     = input();
$id     = (int)($in['id'] ?? 0);
$action = (string)($in['action'] ?? 'update');

$st = $pdo->prepare('SELECT * FROM volunteers WHERE id = ?');
$st->execute([$id]);
$vol = $st->fetch();
if (!$vol) {
    fail('Volunteer not found.', 404);
}

$st = $pdo->prepare("SELECT COUNT(*) FROM assignments WHERE volunteer_id = ? AND status = 'ACTIVE'");
$st->execute([$id]);
$hasActive = (int)$st->fetchColumn() > 0;

if ($action === 'status') {
    $new = strtoupper(trim((string)($in['status'] ?? '')));
    if (!in_array($new, VOLUNTEER_STATUSES, true)) {
        fail('Invalid volunteer status.');
    }
    if ($hasActive && $new !== 'BUSY') {
        fail('This volunteer has an active assignment. Complete or cancel it first.', 409);
    }
    $pdo->prepare('UPDATE volunteers SET status = ? WHERE id = ?')->execute([$new, $id]);
    log_activity('VOLUNTEER_STATUS', "Admin set Volunteer {$vol['volunteer_code']} to $new");
    ok('Volunteer status updated.');
}

$v = validate_volunteer_input($in);
if ($hasActive && $v['status'] !== 'BUSY') {
    fail('This volunteer has an active assignment. Complete or cancel it first.', 409);
}
$pdo->prepare(
    'UPDATE volunteers SET full_name = ?, contact = ?, skill = ?, availability = ?, status = ?, latitude = ?, longitude = ? WHERE id = ?'
)->execute([$v['name'], $v['contact'], $v['skill'], $v['avail'], $v['status'], $v['lat'], $v['lng'], $id]);

if ($vol['user_id']) {
    $pdo->prepare('UPDATE users SET full_name = ? WHERE id = ?')->execute([$v['name'], $vol['user_id']]);
}
log_activity('VOLUNTEER_UPDATED', "Admin updated Volunteer {$vol['volunteer_code']}");
ok('Volunteer updated successfully.');
