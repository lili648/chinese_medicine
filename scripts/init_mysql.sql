-- ============================================================
-- 基于知识图谱的医疗文献管理平台 (MLM-KG)
-- MySQL 数据库初始化脚本
-- 版本: V1.0  日期: 2026-07-18
-- ============================================================

CREATE DATABASE IF NOT EXISTS chinese_medicine
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE chinese_medicine;

CREATE TABLE IF NOT EXISTS article (
    article_id  VARCHAR(64) NOT NULL,
    pmid        VARCHAR(32) DEFAULT NULL,
    title       TEXT,
    abstract    LONGTEXT,
    authors     TEXT,
    journal     VARCHAR(512) DEFAULT NULL,
    pub_year    INT DEFAULT NULL,
    language    VARCHAR(10) DEFAULT 'en',
    source_file VARCHAR(256) DEFAULT NULL,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (article_id),
    INDEX idx_pmid (pmid),
    INDEX idx_pub_year (pub_year),
    INDEX idx_language (language),
    INDEX idx_source_file (source_file)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS entity (
    entity_id   VARCHAR(32) NOT NULL,
    name        VARCHAR(256) NOT NULL,
    entity_type VARCHAR(20) NOT NULL,
    source      VARCHAR(64) DEFAULT '',
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (entity_id),
    UNIQUE KEY uk_name (name),
    INDEX idx_entity_type (entity_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS relation (
    id            INT NOT NULL AUTO_INCREMENT,
    source_id     VARCHAR(128) NOT NULL,
    target_id     VARCHAR(128) NOT NULL,
    relation_type VARCHAR(20) NOT NULL,
    frequency     INT NOT NULL DEFAULT 1,
    confidence    VARCHAR(10) DEFAULT NULL,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uk_relation (source_id, target_id, relation_type),
    INDEX idx_source (source_id),
    INDEX idx_target (target_id),
    INDEX idx_relation_type (relation_type),
    INDEX idx_source_type (source_id, relation_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
