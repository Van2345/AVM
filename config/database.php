<?php
/*
 * Database connection (PDO + prepared statements).
 * Edit these values only if your XAMPP MySQL settings are different.
 * These credentials stay on the server; they are never sent to JavaScript.
 */
const DB_HOST = 'localhost';
const DB_NAME = 'assistance_volunteer_db';
const DB_USER = 'root';
const DB_PASS = '';   // XAMPP default: empty password

function db(): PDO
{
    static $pdo = null;
    if ($pdo instanceof PDO) {
        return $pdo;
    }
    try {
        $pdo = new PDO(
            'mysql:host=' . DB_HOST . ';dbname=' . DB_NAME . ';charset=utf8mb4',
            DB_USER,
            DB_PASS,
            [
                PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
                PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
                PDO::ATTR_EMULATE_PREPARES   => false,
            ]
        );
    } catch (PDOException $e) {
        error_log('Database connection failed: ' . $e->getMessage());
        throw new RuntimeException('Database connection failed.');
    }
    return $pdo;
}
