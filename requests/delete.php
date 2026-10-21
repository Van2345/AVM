<?php
require_once __DIR__ . '/../config/helpers.php';
require_post();
$user = require_role('ADMIN');
$pdo  = db();

$id = (int)(input()['id'] ?? 0);
if ($id <= 0) {
    fail('Invalid request.');
}

$pdo->beginTransaction();
try {
    $st = $pdo->prepare('SELECT request_code FROM assistance_requests WHERE id = ? FOR UPDATE');
    $st->execute([$id]);
    $req = $st->fetch();
    if (!$req) {
        $pdo->rollBack();
        fail('Request not found.', 404);
    }
    // Free any volunteer that is still busy with this request.
    $pdo->prepare(
        "UPDATE volunteers SET status = 'AVAILABLE'
         WHERE id IN (SELECT volunteer_id FROM assignments WHERE request_id = ? AND status = 'ACTIVE')"
    )->execute([$id]);
    $pdo->prepare('DELETE FROM assistance_requests WHERE id = ?')->execute([$id]);
    $pdo->commit();
} catch (Throwable $e) {
    if ($pdo->inTransaction()) {
        $pdo->rollBack();
    }
    throw $e;
}

log_activity('REQUEST_DELETED', 'Admin deleted ' . $req['request_code']);
ok('Request deleted.');
