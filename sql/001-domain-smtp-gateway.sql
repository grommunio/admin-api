-- Migration: Add per-domain SMTP gateway configuration
-- Target: grommunio database (used by gromox)
-- Compatible with MariaDB 10.5+ / MySQL 8+
--
-- This migration adds a new table `domain_smtp_gateway` that allows each
-- grommunio domain to have its own outbound SMTP server (relay/gateway)
-- with optional authentication. gromox reads from this table at SMTP
-- delivery time and picks the right server per recipient domain.
--
-- gromox uses MySQL via libgxs_mysql_adaptor (see exch/mysql_adaptor/
-- in the gromox source). The connection parameters come from
-- /etc/gromox/mysql_adaptor.cfg. Make sure gromox-delivery-queue and
-- gromox-delivery can read this table.

CREATE TABLE IF NOT EXISTS `domain_smtp_gateway` (
    `domain_id`           INT(10) UNSIGNED NOT NULL,
    `host`                VARCHAR(255) NOT NULL,
    `port`                INT(11) NOT NULL DEFAULT 25,
    `encryption`          ENUM('none', 'starttls', 'starttls_unverified', 'tls') NOT NULL DEFAULT 'none',
    `username`            VARCHAR(255) DEFAULT NULL,
    `password`            VARCHAR(255) DEFAULT NULL,
    `from_address`        VARCHAR(255) DEFAULT NULL,
    `enabled`             TINYINT(1) NOT NULL DEFAULT 1,
    `description`         VARCHAR(255) DEFAULT NULL,
    `created_at`          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`domain_id`),
    CONSTRAINT `fk_dsg_domain`
        FOREIGN KEY (`domain_id`) REFERENCES `domains` (`id`)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Index for fast lookup by domain id (already primary key, but explicit
-- name helps query plans for the gromox daemon that joins on it).
-- MariaDB does not support `CREATE INDEX IF NOT EXISTS`; use the
-- information_schema check so the migration is idempotent on both
-- MariaDB and MySQL 8+.
SET @ix := (SELECT COUNT(*) FROM information_schema.statistics
            WHERE table_schema = DATABASE()
              AND table_name = 'domain_smtp_gateway'
              AND index_name = 'idx_dsg_enabled');
SET @sql := IF(@ix = 0,
    'CREATE INDEX `idx_dsg_enabled` ON `domain_smtp_gateway` (`enabled`)',
    'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;
