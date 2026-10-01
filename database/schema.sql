-- =====================================================================
-- RehabX AI — PostgreSQL schema (reference DDL)
-- The backend uses SQLAlchemy to create these tables; this file is the
-- canonical DDL for provisioning a fresh PostgreSQL/Supabase database.
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()

-- ---------- users ----------
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT NOT NULL UNIQUE,
    hashed_password TEXT NOT NULL,
    full_name       TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'patient',      -- patient|clinician|admin
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_users_email ON users (email);

-- ---------- xray_uploads ----------
CREATE TABLE xray_uploads (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    original_filename TEXT NOT NULL,
    storage_key     TEXT NOT NULL UNIQUE,                 -- never the user filename
    content_type    TEXT NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    image_width     INT,
    image_height    INT,
    affected_side   TEXT,                                  -- left|right
    affected_region TEXT,                                  -- hand|wrist|fingers
    status          TEXT NOT NULL DEFAULT 'uploaded',      -- uploaded|processing|completed|failed
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_uploads_user ON xray_uploads (user_id);

-- ---------- ai_analysis ----------
CREATE TABLE ai_analysis (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    upload_id         UUID NOT NULL REFERENCES xray_uploads(id) ON DELETE CASCADE,
    user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    model_name        TEXT NOT NULL,
    model_version     TEXT NOT NULL,
    model_status      TEXT NOT NULL,          -- fine_tuned|pretrained_backbone
    prediction_label  TEXT NOT NULL,          -- normal|abnormal
    confidence        DOUBLE PRECISION NOT NULL,
    class_probabilities JSONB NOT NULL,
    findings          JSONB NOT NULL,
    preprocessing     JSONB,
    analysis_duration_ms INT,
    status            TEXT NOT NULL DEFAULT 'completed',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_analysis_user ON ai_analysis (user_id);
CREATE INDEX idx_analysis_upload ON ai_analysis (upload_id);

-- ---------- detected_regions ----------
CREATE TABLE detected_regions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id     UUID NOT NULL REFERENCES ai_analysis(id) ON DELETE CASCADE,
    label           TEXT NOT NULL,
    region_type     TEXT NOT NULL,           -- bone|joint|background
    bbox_x          INT,
    bbox_y          INT,
    bbox_w          INT,
    bbox_h          INT,
    confidence      DOUBLE PRECISION NOT NULL DEFAULT 0,
    detection_method TEXT NOT NULL DEFAULT 'classical_cv',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_regions_analysis ON detected_regions (analysis_id);

-- ---------- rehabilitation_recommendations ----------
CREATE TABLE rehabilitation_recommendations (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id      UUID NOT NULL UNIQUE REFERENCES ai_analysis(id) ON DELETE CASCADE,
    user_id          UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    upload_id        UUID NOT NULL REFERENCES xray_uploads(id) ON DELETE CASCADE,
    rehab_focus      TEXT NOT NULL,
    affected_region  TEXT NOT NULL,
    abnormality_category TEXT NOT NULL,
    focus_reasoning  JSONB NOT NULL,
    recommended_exercise_categories JSONB NOT NULL,
    movement_requirements JSONB NOT NULL,
    repetition_guidance  JSONB NOT NULL,
    session_structure    JSONB NOT NULL,
    safety_warnings      JSONB NOT NULL,
    disclaimer       TEXT NOT NULL,
    engine_version   TEXT NOT NULL DEFAULT '1.0.0',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_recommendations_user ON rehabilitation_recommendations (user_id);

-- ---------- exercises ----------
CREATE TABLE exercises (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug          TEXT NOT NULL UNIQUE,
    name          TEXT NOT NULL,
    description   TEXT NOT NULL,
    target_region TEXT NOT NULL,
    movement_type TEXT NOT NULL,
    starting_position TEXT NOT NULL,
    required_movement TEXT NOT NULL,
    contraindications JSONB NOT NULL DEFAULT '[]',
    difficulty    TEXT NOT NULL DEFAULT 'beginner',
    rep_range_min INT NOT NULL DEFAULT 8,
    rep_range_max INT NOT NULL DEFAULT 12,
    set_range_min INT NOT NULL DEFAULT 2,
    set_range_max INT NOT NULL DEFAULT 3,
    animation_placeholder TEXT,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_exercises_slug ON exercises (slug);

-- ---------- exercise_sessions ----------
CREATE TABLE exercise_sessions (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    exercise_id   UUID NOT NULL REFERENCES exercises(id) ON DELETE CASCADE,
    analysis_id   UUID REFERENCES ai_analysis(id) ON DELETE SET NULL,
    planned_reps  INT,
    planned_sets  INT,
    completed_reps INT,
    completed_sets INT,
    status        TEXT NOT NULL DEFAULT 'planned',
    pain_level    INT CHECK (pain_level BETWEEN 0 AND 10),
    notes         TEXT,
    scheduled_date TIMESTAMPTZ,
    completed_at  TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_sessions_user ON exercise_sessions (user_id);

-- ---------- progress ----------
CREATE TABLE progress (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    analysis_id   UUID REFERENCES ai_analysis(id) ON DELETE SET NULL,
    date          TIMESTAMPTZ NOT NULL DEFAULT now(),
    pain_level    INT CHECK (pain_level BETWEEN 0 AND 10),
    grip_strength_kg DOUBLE PRECISION CHECK (grip_strength_kg >= 0),
    range_of_motion_deg DOUBLE PRECISION CHECK (range_of_motion_deg >= 0),
    self_reported_improvement INT CHECK (self_reported_improvement BETWEEN 0 AND 100),
    notes         TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_progress_user ON progress (user_id);

-- ---------- audit_logs ----------
CREATE TABLE audit_logs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES users(id) ON DELETE SET NULL,
    action      TEXT NOT NULL,
    entity_type TEXT,
    entity_id   TEXT,
    ip_address  TEXT,
    user_agent  TEXT,
    details     JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_user ON audit_logs (user_id);
CREATE INDEX idx_audit_action ON audit_logs (action);
