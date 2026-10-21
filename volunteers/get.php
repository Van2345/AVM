<?php
require_once __DIR__ . '/../config/helpers.php';
require_role('ADMIN');
$pdo = db();

$map    = isset($_GET['map']);
$q      = trim((string)($_GET['q'] ?? ''));
$status = strtoupper(trim((string)($_GET['status'] ?? '')));

$sql = "SELECT v.id, v.volunteer_code, v.user_id, v.full_name, v.contact, v.skill, v.availability, v.status,
               v.latitude, v.longitude, u.username, r.request_code AS current_request
        FROM volunteers v
        LEFT JOIN users u ON u.id = v.user_id
        LEFT JOIN assignments a ON a.volunteer_id = v.id AND a.status = 'ACTIVE'
        LEFT JOIN assistance_requests r ON r.id = a.request_id";
$where  = [];
$params = [];

if ($status !== '' && $status !== 'ALL') {
    if (!in_array($status, VOLUNTEER_STATUSES, true)) {
        fail('Invalid status filter.');
    }
    $where[]  = 'v.status = ?';
    $params[] = $status;
}
if ($map) {
    $where[] = 'v.latitude IS NOT NULL AND v.longitude IS NOT NULL';
}
if ($q !== '') {
    $like     = '%' . $q . '%';
    $where[]  = '(v.volunteer_code LIKE ? OR v.full_name LIKE ? OR v.skill LIKE ? OR v.contact LIKE ?)';
    array_push($params, $like, $like, $like, $like);
}
if ($where) {
    $sql .= ' WHERE ' . implode(' AND ', $where);
}
$sql .= ' ORDER BY v.id ASC';

$st = $pdo->prepare($sql);
$st->execute($params);
json_out(['success' => true, 'volunteers' => $st->fetchAll()]);
