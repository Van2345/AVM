<?php
require_once __DIR__ . '/../config/helpers.php';
require_post();
require_role('ADMIN');
$pdo = db();

$id = (int)(input()['id'] ?? 0);
$st = $pdo->prepare('SELECT * FROM volunteers WHERE id = ?');
$st->execute([$id]);
$vol = $st->fetch();
if (!$vol) {
    fail('Volunteer not found.', 404);
}

$st = $pdo->prepare("SELECT COUNT(*) FROM assignments WHERE volunteer_id = ? AND status = 'ACTIVE'");
$st->execute([$id]);
if ((int)$st->fetchColumn() > 0) {
    fail('This volunteer has an active assignment and cannot be deleted.', 409);
}

$pdo->beginTransaction();
try {
    $pdo->prepare('DELETE FROM volunteers WHERE id = ?')->execute([$id]);
    if ($vol['user_id']) {
        $pdo->prepare("DELETE FROM users WHERE id = ? AND role = 'VOLUNTEER'")->execute([$vol['user_id']]);
    }
    $pdo->commit();
} catch (Throwable $e) {
    if ($pdo->inTransaction()) {
        $pdo->rollBack();
    }
    throw $e;
}

log_activity('VOLUNTEER_DELETED', "Admin deleted Volunteer {$vol['volunteer_code']} ({$vol['full_name']})");
ok('Volunteer deleted.');
