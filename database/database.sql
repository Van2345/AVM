-- =====================================================================
-- Assistance and Volunteer Management System - ICCT Antipolo Campus
-- Import this file in phpMyAdmin (http://localhost/phpmyadmin > Import)
-- WARNING: re-importing drops and recreates all tables (resets the data).
-- =====================================================================
CREATE DATABASE IF NOT EXISTS assistance_volunteer_db
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE assistance_volunteer_db;

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS activity_logs;
DROP TABLE IF EXISTS assignments;
DROP TABLE IF EXISTS assistance_requests;
DROP TABLE IF EXISTS volunteers;
DROP TABLE IF EXISTS users;
SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE users (
  id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
  username      VARCHAR(30)  NOT NULL,
  full_name     VARCHAR(100) NOT NULL,
  email         VARCHAR(120) NULL,
  password_hash VARCHAR(255) NOT NULL,
  role          ENUM('ADMIN','VOLUNTEER','REQUESTER') NOT NULL DEFAULT 'REQUESTER',
  is_active     TINYINT(1)   NOT NULL DEFAULT 1,
  created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_users_username (username),
  KEY idx_users_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE volunteers (
  id             INT UNSIGNED NOT NULL AUTO_INCREMENT,
  volunteer_code VARCHAR(10)  NULL,
  user_id        INT UNSIGNED NULL,
  full_name      VARCHAR(100) NOT NULL,
  contact        VARCHAR(20)  NOT NULL,
  skill          VARCHAR(80)  NOT NULL,
  availability   VARCHAR(100) NOT NULL,
  status         ENUM('AVAILABLE','BUSY','UNAVAILABLE') NOT NULL DEFAULT 'AVAILABLE',
  latitude       DECIMAL(9,6) NULL,
  longitude      DECIMAL(9,6) NULL,
  created_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_volunteers_code (volunteer_code),
  UNIQUE KEY uq_volunteers_user (user_id),
  KEY idx_volunteers_status (status),
  CONSTRAINT fk_volunteers_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE assistance_requests (
  id              INT UNSIGNED NOT NULL AUTO_INCREMENT,
  request_code    VARCHAR(12)  NULL,
  user_id         INT UNSIGNED NULL,
  requester_name  VARCHAR(100) NOT NULL,
  contact         VARCHAR(20)  NOT NULL,
  assistance_type VARCHAR(40)  NOT NULL,
  location        VARCHAR(255) NOT NULL,
  latitude        DECIMAL(9,6) NULL,
  longitude       DECIMAL(9,6) NULL,
  description     TEXT         NOT NULL,
  urgency         ENUM('Low','Medium','High','Emergency') NOT NULL DEFAULT 'Low',
  needed_at       DATETIME     NOT NULL,
  status          ENUM('PENDING','APPROVED','ASSIGNED','ONGOING','DONE','REJECTED','CANCELLED') NOT NULL DEFAULT 'PENDING',
  created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_requests_code (request_code),
  KEY idx_requests_status (status),
  KEY idx_requests_user (user_id),
  KEY idx_requests_created (created_at),
  CONSTRAINT fk_requests_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE assignments (
  id           INT UNSIGNED NOT NULL AUTO_INCREMENT,
  request_id   INT UNSIGNED NOT NULL,
  volunteer_id INT UNSIGNED NOT NULL,
  assigned_by  INT UNSIGNED NULL,
  assigned_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  started_at   DATETIME     NULL,
  completed_at DATETIME     NULL,
  status       ENUM('ACTIVE','COMPLETED','CANCELLED') NOT NULL DEFAULT 'ACTIVE',
  PRIMARY KEY (id),
  KEY idx_assign_request (request_id, status),
  KEY idx_assign_volunteer (volunteer_id, status),
  CONSTRAINT fk_assign_request   FOREIGN KEY (request_id)   REFERENCES assistance_requests(id) ON DELETE CASCADE,
  CONSTRAINT fk_assign_volunteer FOREIGN KEY (volunteer_id) REFERENCES volunteers(id) ON DELETE CASCADE,
  CONSTRAINT fk_assign_admin     FOREIGN KEY (assigned_by)  REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE activity_logs (
  id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id    INT UNSIGNED NULL,
  request_id INT UNSIGNED NULL,
  action     VARCHAR(40)  NOT NULL,
  details    VARCHAR(255) NOT NULL,
  created_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_logs_created (created_at),
  KEY idx_logs_user (user_id),
  KEY idx_logs_request (request_id),
  CONSTRAINT fk_logs_user    FOREIGN KEY (user_id)    REFERENCES users(id) ON DELETE SET NULL,
  CONSTRAINT fk_logs_request FOREIGN KEY (request_id) REFERENCES assistance_requests(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- DEMO DATA (demo credentials only - change or delete before real use)
--   admin       / Admin@12345
--   volunteer1  / Volunteer@123
--   requester1  / Requester@123
-- ---------------------------------------------------------------------
INSERT INTO users (id, username, full_name, email, password_hash, role) VALUES
(1, 'admin',      'System Administrator', 'admin@example.com',     '$2y$10$5hD8jn73npIriSZvdCLe8OZ.rXUCCjeIHh.wzVicCKIdTspkEOg4u', 'ADMIN'),
(2, 'volunteer1', 'Maria Santos',         'volunteer@example.com', '$2y$10$GDzs7J4aA9wsT7JfAWsQXeuPfl17sZiSkzeoGoPqpLgU9B4CiSzl2', 'VOLUNTEER'),
(3, 'requester1', 'Juan Dela Cruz',       'requester@example.com', '$2y$10$qZRd09u6bDZJc9VaREEXkeLPvmLLmPTLpWRAVVnR5OWdgUYyu6Bde', 'REQUESTER');

INSERT INTO volunteers (id, volunteer_code, user_id, full_name, contact, skill, availability, status, latitude, longitude) VALUES
(1, 'V-0001', 2,    'Maria Santos',  '09171234567', 'First Aid Responder', 'Mon-Fri 8:00 AM - 5:00 PM',  'BUSY',        14.625900, 121.122900),
(2, 'V-0002', NULL, 'Carlo Reyes',   '09181234567', 'Driver / Transport',  'Mon-Sat 7:00 AM - 4:00 PM',  'AVAILABLE',   14.624800, 121.121500),
(3, 'V-0003', NULL, 'Angela Cruz',   '09191234567', 'Campus Guide',        'Mon-Fri 9:00 AM - 6:00 PM',  'AVAILABLE',   14.626300, 121.123400),
(4, 'V-0004', NULL, 'Paolo Mendoza', '09201234567', 'Security Support',    'Weekends 8:00 AM - 8:00 PM', 'UNAVAILABLE', 14.625100, 121.120900);

INSERT INTO assistance_requests (id, request_code, user_id, requester_name, contact, assistance_type, location, latitude, longitude, description, urgency, needed_at, status) VALUES
(1, 'REQ-000001', 3, 'Juan Dela Cruz', '09221234567', 'Medical Assistance', 'ICCT Antipolo - Main Gate',           14.625700, 121.122000, 'A student feels dizzy and needs first aid at the main gate.', 'High',   NOW(), 'PENDING'),
(2, 'REQ-000002', 3, 'Juan Dela Cruz', '09221234567', 'Transportation',     'ICCT Antipolo - Library',             14.625000, 121.122800, 'Need a ride to the nearby clinic for a follow-up check.',      'Medium', NOW(), 'ASSIGNED'),
(3, 'REQ-000003', 3, 'Juan Dela Cruz', '09221234567', 'Lost and Found',     'ICCT Antipolo - Canteen',             14.625400, 121.121600, 'Lost a black umbrella near the canteen table area.',           'Low',    NOW(), 'DONE'),
(4, 'REQ-000004', 3, 'Juan Dela Cruz', '09221234567', 'Campus Assistance',  'ICCT Antipolo - Computer Laboratory', 14.626100, 121.122500, 'Need help carrying equipment to the computer laboratory.',    'Low',    NOW(), 'APPROVED');

INSERT INTO assignments (request_id, volunteer_id, assigned_by, started_at, completed_at, status) VALUES
(2, 1, 1, NULL, NULL, 'ACTIVE'),
(3, 3, 1, NOW(), NOW(), 'COMPLETED');

INSERT INTO activity_logs (user_id, request_id, action, details) VALUES
(3, 1, 'REQUEST_CREATED',   'Requester submitted REQ-000001'),
(3, 2, 'REQUEST_CREATED',   'Requester submitted REQ-000002'),
(1, 2, 'REQUEST_APPROVED',  'Admin approved REQ-000002'),
(1, 2, 'REQUEST_ASSIGNED',  'Admin assigned Volunteer V-0001 to REQ-000002'),
(3, 3, 'REQUEST_CREATED',   'Requester submitted REQ-000003'),
(1, 3, 'REQUEST_COMPLETED', 'Request REQ-000003 completed'),
(3, 4, 'REQUEST_CREATED',   'Requester submitted REQ-000004'),
(1, 4, 'REQUEST_APPROVED',  'Admin approved REQ-000004');
