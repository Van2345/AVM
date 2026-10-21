<?php
/* Shared helpers: session, CSRF, JSON output, role checks, validation, activity log. */
require_once __DIR__ . '/database.php';

date_default_timezone_set('Asia/Manila');
ini_set('display_errors', '0');

const ASSISTANCE_TYPES   = ['Medical Assistance', 'Emergency Assistance', 'Transportation', 'Campus Assistance', 'Lost and Found', 'Other'];
const URGENCY_LEVELS     = ['Low', 'Medium', 'High', 'Emergency'];
const REQUEST_STATUSES   = ['PENDING', 'APPROVED', 'ASSIGNED', 'ONGOING', 'DONE', 'REJECTED', 'CANCELLED'];
const VOLUNTEER_STATUSES = ['AVAILABLE', 'BUSY', 'UNAVAILABLE'];

if (session_status() === PHP_SESSION_NONE) {
    session_name('AVMS_SESSION');
    session_set_cookie_params(['lifetime' => 0, 'path' => '/', 'httponly' => true, 'samesite' => 'Lax']);
    session_start();
}
if (empty($_SESSION['csrf'])) {
    $_SESSION['csrf'] = bin2hex(random_bytes(32));
}

set_exception_handler(function (Throwable $e) {
    error_log($e->getMessage());
    $msg = ($e instanceof RuntimeException && $e->getMessage() === 'Database connection failed.')
        ? 'Database connection failed.'
        : 'Unable to save data.';
    json_out(['success' => false, 'message' => $msg], 500);
});

function json_out(array $data, int $code = 200): void
{
    http_response_code($code);
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');
    echo json_encode($data, JSON_UNESCAPED_UNICODE);
    exit;
}
function fail(string $message, int $code = 400): void
{
    json_out(['success' => false, 'message' => $message], $code);
}
function ok(string $message, array $extra = []): void
{
    json_out(array_merge(['success' => true, 'message' => $message], $extra));
}

/** Read JSON body (fetch) or fall back to form POST. */
function input(): array
{
    $raw  = file_get_contents('php://input');
    $data = json_decode($raw ?: '', true);
    return is_array($data) ? $data : $_POST;
}

/** POST only + CSRF token check. */
function require_post(): void
{
    if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
        fail('Invalid request method.', 405);
    }
    $sent = $_SERVER['HTTP_X_CSRF_TOKEN'] ?? '';
    if (!is_string($sent) || !hash_equals($_SESSION['csrf'], $sent)) {
        fail('Your session expired. Please refresh the page and try again.', 403);
    }
}

/** Re-check the logged-in user against the database (role and active flag). */
function refresh_session_user(): ?array
{
    $u = $_SESSION['user'] ?? null;
    if (!$u) {
        return null;
    }
    $st = db()->prepare('SELECT id, username, full_name, role, is_active FROM users WHERE id = ?');
    $st->execute([(int)$u['id']]);
    $row = $st->fetch();
    if (!$row || !(int)$row['is_active']) {
        unset($_SESSION['user']);
        return null;
    }
    $_SESSION['user'] = [
        'id'        => (int)$row['id'],
        'username'  => $row['username'],
        'full_name' => $row['full_name'],
        'role'      => $row['role'],
    ];
    return $_SESSION['user'];
}

function require_login(): array
{
    $u = refresh_session_user();
    if (!$u) {
        fail('Please log in first.', 401);
    }
    return $u;
}

function require_role(string ...$roles): array
{
    $u = require_login();
    if (!in_array($u['role'], $roles, true)) {
        fail('You do not have permission to do this.', 403);
    }
    return $u;
}

function log_activity(string $action, string $details, ?int $requestId = null, ?int $userId = null): void
{
    $uid = $userId ?? ($_SESSION['user']['id'] ?? null);
    $st  = db()->prepare('INSERT INTO activity_logs (user_id, request_id, action, details) VALUES (?, ?, ?, ?)');
    $st->execute([$uid, $requestId, $action, mb_substr($details, 0, 255)]);
}

function clean(string $s): string
{
    return trim(preg_replace('/\s+/u', ' ', $s));
}
function valid_contact(string $c): bool
{
    return (bool)preg_match('/^[0-9+\-\s()]{7,20}$/', $c);
}

/** Returns [lat, lng] or [null, null]. Fails on invalid values. */
function parse_coords(array $in): array
{
    $lat = $in['latitude'] ?? null;
    $lng = $in['longitude'] ?? null;
    $blank = fn($v) => $v === null || $v === '';
    if ($blank($lat) && $blank($lng)) {
        return [null, null];
    }
    if ($blank($lat) || $blank($lng) || !is_numeric($lat) || !is_numeric($lng)) {
        fail('Invalid map coordinates.');
    }
    $lat = (float)$lat;
    $lng = (float)$lng;
    if ($lat < -90 || $lat > 90 || $lng < -180 || $lng > 180) {
        fail('Invalid map coordinates.');
    }
    return [round($lat, 6), round($lng, 6)];
}

function validate_volunteer_input(array $in): array
{
    $name    = clean((string)($in['full_name'] ?? ''));
    $contact = trim((string)($in['contact'] ?? ''));
    $skill   = clean((string)($in['skill'] ?? ''));
    $avail   = clean((string)($in['availability'] ?? ''));
    $status  = strtoupper(trim((string)($in['status'] ?? 'AVAILABLE')));

    if ($name === '' || $contact === '' || $skill === '' || $avail === '') {
        fail('Please complete all required fields.');
    }
    if (mb_strlen($name) < 2 || mb_strlen($name) > 100) {
        fail('Full name must be 2 to 100 characters.');
    }
    if (!valid_contact($contact)) {
        fail('Please enter a valid contact number.');
    }
    if (mb_strlen($skill) > 80) {
        fail('Skill / Role is too long (80 characters maximum).');
    }
    if (mb_strlen($avail) > 100) {
        fail('Availability is too long (100 characters maximum).');
    }
    if (!in_array($status, VOLUNTEER_STATUSES, true)) {
        fail('Invalid volunteer status.');
    }
    [$lat, $lng] = parse_coords($in);
    return ['name' => $name, 'contact' => $contact, 'skill' => $skill, 'avail' => $avail, 'status' => $status, 'lat' => $lat, 'lng' => $lng];
}
