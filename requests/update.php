<?php
require_once __DIR__ . '/../config/helpers.php';
require_post();
$user = require_login();
$pdo  = db();

$in     = input();
$id     = (int)($in['id'] ?? 0);
$action = (string)($in['action'] ?? '');
$isAdmin = $user['role'] === 'ADMIN';
$who     = ucfirst(strtolower($user['role']));

function bail(PDO $pdo, string $msg, int $code = 400): void
{
    if ($pdo->inTransaction()) {
        $pdo->rollBack();
    }
    fail($msg, $code);
}

if ($id <= 0 || !in_array($action, ['approve', 'reject', 'assign', 'start', 'complete', 'cancel'], true)) {
    fail('Invalid request.');
}

$pdo->beginTransaction();
try {
    $st = $pdo->prepare('SELECT * FROM assistance_requests WHERE id = ? FOR UPDATE');
    $st->execute([$id]);
    $req = $st->fetch();
    if (!$req) {
        bail($pdo, 'Request not found.', 404);
    }

    $st = $pdo->prepare(
        "SELECT a.*, v.user_id AS volunteer_user_id
         FROM assignments a JOIN volunteers v ON v.id = a.volunteer_id
         WHERE a.request_id = ? AND a.status = 'ACTIVE' FOR UPDATE"
    );
    $st->execute([$id]);
    $asg = $st->fetch() ?: null;

    $code   = $req['request_code'];
    $status = $req['status'];
    $isOwner = (int)$req['user_id'] === $user['id'];
    $isAssignedVolunteer = $asg && $user['role'] === 'VOLUNTEER' && (int)$asg['volunteer_user_id'] === $user['id'];

    $setStatus = function (string $s) use ($pdo, $id) {
        $pdo->prepare('UPDATE assistance_requests SET status = ? WHERE id = ?')->execute([$s, $id]);
    };
    $freeVolunteer = function (int $vid) use ($pdo) {
        $pdo->prepare("UPDATE volunteers SET status = 'AVAILABLE' WHERE id = ?")->execute([$vid]);
    };

    $msg = '';
    $log = ['', ''];
    $newStatus = $status;

    switch ($action) {
        case 'approve':
            if (!$isAdmin) bail($pdo, 'You do not have permission to do this.', 403);
            if ($status !== 'PENDING') bail($pdo, 'Only pending requests can be approved.');
            $newStatus = 'APPROVED';
            $setStatus($newStatus);
            $msg = 'Request successfully approved.';
            $log = ['REQUEST_APPROVED', "$who approved $code"];
            break;

        case 'reject':
            if (!$isAdmin) bail($pdo, 'You do not have permission to do this.', 403);
            if (!in_array($status, ['PENDING', 'APPROVED'], true)) bail($pdo, 'Only pending or approved requests can be rejected.');
            $newStatus = 'REJECTED';
            $setStatus($newStatus);
            $msg = 'Request rejected.';
            $log = ['REQUEST_REJECTED', "$who rejected $code"];
            break;

        case 'assign':
            if (!$isAdmin) bail($pdo, 'You do not have permission to do this.', 403);
            if ($status !== 'APPROVED') bail($pdo, 'Only approved requests can be assigned to a volunteer.');
            if ($asg) bail($pdo, 'This request already has a volunteer.');
            $vid = (int)($in['volunteer_id'] ?? 0);
            $st  = $pdo->prepare('SELECT * FROM volunteers WHERE id = ? FOR UPDATE');
            $st->execute([$vid]);
            $vol = $st->fetch();
            if (!$vol) bail($pdo, 'Volunteer not found.', 404);
            if ($vol['status'] !== 'AVAILABLE') bail($pdo, 'This volunteer is not available. Please choose another volunteer.', 409);
            $pdo->prepare("INSERT INTO assignments (request_id, volunteer_id, assigned_by, status) VALUES (?, ?, ?, 'ACTIVE')")
                ->execute([$id, $vid, $user['id']]);
            $pdo->prepare("UPDATE volunteers SET status = 'BUSY' WHERE id = ?")->execute([$vid]);
            $newStatus = 'ASSIGNED';
            $setStatus($newStatus);
            $msg = 'Volunteer successfully assigned.';
            $log = ['REQUEST_ASSIGNED', "$who assigned Volunteer {$vol['volunteer_code']} to $code"];
            break;

        case 'start':
            if (!$asg) bail($pdo, 'This request has no assigned volunteer.');
            if (!$isAdmin && !$isAssignedVolunteer) bail($pdo, 'You do not have permission to do this.', 403);
            if ($status !== 'ASSIGNED') bail($pdo, 'Only assigned requests can be started.');
            $pdo->prepare('UPDATE assignments SET started_at = NOW() WHERE id = ?')->execute([$asg['id']]);
            $newStatus = 'ONGOING';
            $setStatus($newStatus);
            $msg = 'Assistance started.';
            $log = ['REQUEST_STARTED', "$who started $code"];
            break;

        case 'complete':
            if (!$asg) bail($pdo, 'This request has no assigned volunteer.');
            if (!$isAdmin && !$isAssignedVolunteer) bail($pdo, 'You do not have permission to do this.', 403);
            $allowed = $isAdmin ? ['ASSIGNED', 'ONGOING'] : ['ONGOING'];
            if (!in_array($status, $allowed, true)) bail($pdo, 'Start the assistance before completing it.');
            $pdo->prepare("UPDATE assignments SET status = 'COMPLETED', completed_at = NOW(), started_at = COALESCE(started_at, NOW()) WHERE id = ?")
                ->execute([$asg['id']]);
            $freeVolunteer((int)$asg['volunteer_id']);
            $newStatus = 'DONE';
            $setStatus($newStatus);
            $msg = 'Request successfully completed.';
            $log = ['REQUEST_COMPLETED', "Request $code completed"];
            break;

        case 'cancel':
            if ($isAdmin) {
                $allowed = ['PENDING', 'APPROVED', 'ASSIGNED', 'ONGOING'];
            } elseif ($user['role'] === 'REQUESTER' && $isOwner) {
                $allowed = ['PENDING', 'APPROVED'];
            } else {
                bail($pdo, 'You do not have permission to do this.', 403);
            }
            if (!in_array($status, $allowed, true)) bail($pdo, 'This request can no longer be cancelled.');
            if ($asg) {
                $pdo->prepare("UPDATE assignments SET status = 'CANCELLED' WHERE id = ?")->execute([$asg['id']]);
                $freeVolunteer((int)$asg['volunteer_id']);
            }
            $newStatus = 'CANCELLED';
            $setStatus($newStatus);
            $msg = 'Request cancelled.';
            $log = ['REQUEST_CANCELLED', "$who cancelled $code"];
            break;
    }

    $pdo->commit();
} catch (Throwable $e) {
    if ($pdo->inTransaction()) {
        $pdo->rollBack();
    }
    throw $e;
}

log_activity($log[0], $log[1], $id);
ok($msg, ['status' => $newStatus]);
