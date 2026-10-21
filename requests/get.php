<?php
require_once __DIR__ . '/../config/helpers.php';
$user = require_login();
$pdo  = db();

$map    = isset($_GET['map']);
$q      = trim((string)($_GET['q'] ?? ''));
$status = strtoupper(trim((string)($_GET['status'] ?? '')));
$limit  = min(500, max(1, (int)($_GET['limit'] ?? 200)));

$sql = "SELECT r.id, r.request_code, r.user_id, r.requester_name, r.contact, r.assistance_type, r.location,
               r.latitude, r.longitude, r.description, r.urgency, r.needed_at, r.status, r.created_at,
               v.id AS volunteer_id, v.volunteer_code, v.full_name AS volunteer_name
        FROM assistance_requests r
        LEFT JOIN assignments a ON a.request_id = r.id AND a.status <> 'CANCELLED'
        LEFT JOIN volunteers v ON v.id = a.volunteer_id";
$where  = [];
$params = [];

// Role-based visibility
if ($user['role'] === 'REQUESTER') {
    $where[]  = 'r.user_id = ?';
    $params[] = $user['id'];
} elseif ($user['role'] === 'VOLUNTEER') {
    $where[]  = 'v.user_id = ?';
    $params[] = $user['id'];
}

if ($status !== '' && $status !== 'ALL') {
    if (!in_array($status, REQUEST_STATUSES, true)) {
        fail('Invalid status filter.');
    }
    $where[]  = 'r.status = ?';
    $params[] = $status;
}
if ($map) {
    $where[] = "r.status IN ('PENDING','APPROVED','ASSIGNED','ONGOING')";
}
if ($q !== '') {
    $like     = '%' . $q . '%';
    $where[]  = '(r.request_code LIKE ? OR r.requester_name LIKE ? OR r.assistance_type LIKE ? OR r.location LIKE ?)';
    array_push($params, $like, $like, $like, $like);
}
if ($where) {
    $sql .= ' WHERE ' . implode(' AND ', $where);
}
$sql .= ' ORDER BY r.created_at DESC, r.id DESC LIMIT ' . $limit;

$st = $pdo->prepare($sql);
$st->execute($params);
$rows = $st->fetchAll();

if ($map) {
    // Map data is trimmed: no names, phone numbers or descriptions.
    $rows = array_map(fn($r) => [
        'id'              => (int)$r['id'],
        'request_code'    => $r['request_code'],
        'assistance_type' => $r['assistance_type'],
        'status'          => $r['status'],
        'urgency'         => $r['urgency'],
        'location'        => $r['location'],
        'latitude'        => $r['latitude'] !== null ? (float)$r['latitude'] : null,
        'longitude'       => $r['longitude'] !== null ? (float)$r['longitude'] : null,
    ], $rows);
}

json_out(['success' => true, 'requests' => $rows]);
