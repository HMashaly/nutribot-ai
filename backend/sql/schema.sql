CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ── Core auth ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    auth_provider TEXT NOT NULL DEFAULT 'local',
    oauth_subject TEXT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Login audit (security + rate-limiting evidence) ───────────────────────────
CREATE TABLE IF NOT EXISTS login_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    email_attempt TEXT NOT NULL,
    success BOOLEAN NOT NULL,
    ip_address TEXT NULL,
    user_agent TEXT NULL,
    failure_reason TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Auth sessions ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS auth_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    ip_address TEXT NULL,
    user_agent TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ NULL
);

-- ── Long-term agent memories (HITL-confirmed facts) ───────────────────────────
CREATE TABLE IF NOT EXISTS user_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    memory TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── User profile — persisted between sessions ─────────────────────────────────
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    weight_kg   REAL    NULL,
    height_cm   REAL    NULL,
    age         INTEGER NULL,
    gender      TEXT    NULL CHECK (gender IN ('male', 'female', NULL)),
    activity_level TEXT NULL CHECK (
        activity_level IN ('sedentary', 'light', 'moderate', 'active', 'very_active', NULL)
    ),
    goal TEXT NULL CHECK (
        goal IN ('weight_loss', 'maintenance', 'muscle_gain', NULL)
    ),
    dietary_restrictions TEXT NULL,  -- comma-separated e.g. "vegan,gluten-free,halal"
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Supermarket offers (cached weekly discounts) ─────────────────────────────
-- Populated offline by offers/ingest.py; read by the find_grocery_offers tool.
CREATE TABLE IF NOT EXISTS supermarket_offers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store TEXT NOT NULL,
    product_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    price_eur NUMERIC(10, 2) NULL,
    unit TEXT NULL,
    discount_pct NUMERIC(5, 2) NULL,
    valid_from DATE NULL,
    valid_to DATE NULL,
    source TEXT NOT NULL DEFAULT 'seed',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Indexes ───────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_users_email             ON users        (email);
CREATE INDEX IF NOT EXISTS idx_login_audit_user_id     ON login_audit  (user_id);
CREATE INDEX IF NOT EXISTS idx_login_audit_created_at  ON login_audit  (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_login_audit_email_time  ON login_audit  (email_attempt, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_id   ON auth_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_expires_at ON auth_sessions(expires_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_memories_user_id   ON user_memories(user_id);
CREATE INDEX IF NOT EXISTS idx_offers_normalized_name  ON supermarket_offers(normalized_name);
CREATE INDEX IF NOT EXISTS idx_offers_store_valid_to   ON supermarket_offers(store, valid_to);
