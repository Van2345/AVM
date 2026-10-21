<?php
require_once __DIR__ . '/../config/helpers.php';
require_post();
$user = require_role('ADMIN', 'REQUESTER');

$in      = input();
$name    = clean((string)($in['requester_name'] ?? ''));
$contact = trim((string)($in['contact'] ?? ''));
$type    = trim((string)($in['assistance_type'] ?? ''));
$loc     = clean((string)($in['location'] ?? ''));
$desc    = trim((string)($in['description'] ?? ''));
$urgency = trim((string)($in['urgency'] ?? ''));
$needed  = trim((string)($in['needed_at'] ?? ''));

if ($name === '' || $contact === '' || $type === '' || $loc === '' || $desc === '' || $urgency === '' || $needed === '') {
    fail('Please complete all required fields.');
}
if (mb_strlen($name) < 2 || mb_strlen($name) > 100) {
    fail('Requester name must be 2 to 100 characters.');
}
if (!valid_contact($contact)) {
    fail('Please enter a valid contact number.');
}
if (!in_array($type, ASSISTANCE_TYPES, true)) {
    fail('Please choose a valid assistance type.');
}
if (mb_strlen($loc) < 3 || mb_strlen($loc) > 255) {
    fail('Location must be 3 to 255 characters.');
}
if (mb_strlen($desc) < 5 || mb_strlen($desc) > 2000) {
    fail('Description must be 5 to 2000 characters.');
}
if (!in_array($urgency, URGENCY_LEVELS, true)) {
    fail('Please choose a valid urgency level.');
}
$dt = false;
foreach (['Y-m-d\TH:i', 'Y-m-d H:i:s', 'Y-m-d H:i'] as $fmt) {
    $dt = DateTime::createFromFormat($fmt, $needed);
    if ($dt !== false) {
        break;
    }
}
if ($dt === false) {
    fail('Please enter a valid date and time.');
}
[$lat, $lng] = parse_coords($in);

$pdo = db();
$pdo->beginTransaction();
try {
    $st = $pdo->prepare(
        "INSERT INTO assistance_requests
         (user_id, requester_name, contact, assistance_type, location, latitude, longitude, description, urgency, needed_at, status)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')"
    );
    $st->execute([$user['id'], $name, $contact, $type, $loc, $lat, $lng, $desc, $urgency, $dt->format('Y-m-d H:i:s')]);
    $id   = (int)$pdo->lastInsertId();
    $code = sprintf('REQ-%06d', $id);
    $pdo->prepare('UPDATE assistance_requests SET request_code = ? WHERE id = ?')->execute([$code, $id]);
    $pdo->commit();
} catch (Throwable $e) {
    if ($pdo->inTransaction()) {
        $pdo->rollBack();
    }
    throw $e;
}

log_activity('REQUEST_CREATED', ucfirst(strtolower($user['role'])) . " submitted $code", $id);
ok('Request submitted successfully.', ['id' => $id, 'request_code' => $code]);
