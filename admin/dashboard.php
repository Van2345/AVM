<?php
/*
 * Dashboard data endpoint.
 *   GET  ?action=stats        any logged-in role (numbers are scoped to the role)
 *   GET  ?action=users        ADMIN only
 *   GET  ?action=logs         ADMIN only
 *   POST action=toggle_user   ADMIN only (enable / disable an account)
 */
require_once __DIR__ . '/../config/helpers.php';

$isPost = ($_SERVER['REQUEST_METHOD'] ?? '') === 'POST';
$in     = $isPost ? input() : [];
$action = (string)($_GET['action'] ?? $in['action'] ?? '');
if ($isPost) {
    require_post();
}
$user = require_login();
$pdo  = db();

if (in_array($action, ['users', 'logs', 'toggle_user'], true) && $user['role'] !== 'ADMIN') {
    fail('You do not have permission to do this.', 403);
}

if ($action === 'stats') {
    switch ($user['role']) {
        case 'ADMIN':
            $from = 'assistance_requests r';
            $where = '';
            $params = [];
            break;
        case 'REQUESTER':
            $from = 'assistance_requests r';
            $where = 'WHERE r.user_id = ?';
            $params = [$user['id']];
            break;
        default:
            $from = "assistance_requests r
                     JOIN assignments a ON a.request_id = r.id AND a.status <> 'CANCELLED'
                     JOIN volunteers v ON v.id = a.volunteer_id";
            $where = 'WHERE v.user_id = ?';
            $params = [$user['id']];
    }
    $st = $pdo->prepare(
        "SELECT COUNT(*) AS total,
                COALESCE(SUM(r.status = 'PENDING'), 0)  AS pending,
                COALESCE(SUM(r.status = 'APPROVED'), 0) AS approved,
                COALESCE(SUM(r.status = 'ASSIGNED'), 0) AS assigned,
                COALESCE(SUM(r.status = 'ONGOING'), 0)  AS ongoing,
                COALESCE(SUM(r.status = 'DONE'), 0)     AS done
         FROM $from $where"
    );
    $st->execute($params);
    $stats = array_map('intval', $st->fetch());

    $vol = $pdo->query("SELECT COUNT(*) AS total, COALESCE(SUM(status = 'AVAILABLE'), 0) AS available FROM volunteers")->fetch();
    $vol = array_map('intval', $vol);

    $base = "SELECT l.id, l.action, l.details, l.created_at, u.full_name
             FROM activity_logs l LEFT JOIN users u ON u.id = l.user_id
             WHERE l.action NOT IN ('LOGIN', 'LOGOUT', 'REGISTER')";
    if ($user['role'] === 'ADMIN') {
        $st = $pdo->query($base . ' ORDER BY l.id DESC LIMIT 8');
    } elseif ($user['role'] === 'REQUESTER') {
        $st = $pdo->prepare($base . ' AND (l.user_id = ? OR l.request_id IN (SELECT id FROM assistance_requests WHERE user_id = ?)) ORDER BY l.id DESC LIMIT 8');
        $st->execute([$user['id'], $user['id']]);
    } else {
        $st = $pdo->prepare(
            $base . ' AND (l.user_id = ? OR l.request_id IN
                (SELECT a.request_id FROM assignments a JOIN volunteers v ON v.id = a.volunteer_id WHERE v.user_id = ?))
             ORDER BY l.id DESC LIMIT 8'
        );
        $st->execute([$user['id'], $user['id']]);
    }
    json_out(['success' => true, 'stats' => $stats, 'volunteers' => $vol, 'activities' => $st->fetchAll()]);
}

if ($action === 'users') {
    $rows = $pdo->query('SELECT id, username, full_name, email, role, is_active, created_at FROM users ORDER BY id ASC')->fetchAll();
    json_out(['success' => true, 'users' => $rows]);
}

if ($action === 'logs') {
    $rows = $pdo->query(
        'SELECT l.id, l.action, l.details, l.created_at, u.full_name
         FROM activity_logs l LEFT JOIN users u ON u.id = l.user_id
         ORDER BY l.id DESC LIMIT 300'
    )->fetchAll();
    json_out(['success' => true, 'logs' => $rows]);
}

if ($action === 'toggle_user') {
    if (!$isPost) {
        fail('Invalid request method.', 405);
    }
    $id = (int)($in['id'] ?? 0);
    if ($id === $user['id']) {
        fail('You cannot disable your own account.', 409);
    }
    $st = $pdo->prepare('SELECT id, username, is_active FROM users WHERE id = ?');
    $st->execute([$id]);
    $target = $st->fetch();
    if (!$target) {
        fail('User not found.', 404);
    }
    $new = (int)$target['is_active'] ? 0 : 1;
    $pdo->prepare('UPDATE users SET is_active = ? WHERE id = ?')->execute([$new, $id]);
    log_activity($new ? 'USER_ENABLED' : 'USER_DISABLED', 'Admin ' . ($new ? 'enabled' : 'disabled') . ' account ' . $target['username']);
    ok($new ? 'Account enabled.' : 'Account disabled.');
}

fail('Invalid request.');
