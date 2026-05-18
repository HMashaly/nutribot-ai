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

-- ── Indexes ───────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_users_email             ON users        (email);
CREATE INDEX IF NOT EXISTS idx_login_audit_user_id     ON login_audit  (user_id);
CREATE INDEX IF NOT EXISTS idx_login_audit_created_at  ON login_audit  (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_memories_user_id   ON user_memories(user_id);
