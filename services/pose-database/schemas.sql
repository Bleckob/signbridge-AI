-- Run this once in Supabase SQL editor to create tables (sign_poses, sessions, organisations, config).
-- Run block 1 first, then block 2.
-- Then run setup_db.py to populate config with bone names.

-- BLOCK 1: TABLES
/*
1. TABLES
*/
-- config table: stores bone names and other configuration
CREATE TABLE IF NOT EXISTS config (
  key   text PRIMARY KEY,
  value jsonb NOT NULL
);

-- sign poses table: core table
CREATE TABLE IF NOT EXISTS sign_poses (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    gloss TEXT NOT NULL,        -- ASL gloss word
    keyframes JSON NOT NULL,    -- quaternion array from mediapipe
    num_tags TEXT[],            -- non-manual marker tags
    bone_names TEXT[],
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX ON sign_poses(gloss);      -- keeps queries under 50ms


-- sessions & organisations table: These tables must NOT have audio or transcript columns. That's a legal 
-- requirement under NDPA 2023.

-- organisations table
CREATE TABLE IF NOT EXISTS organisations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    api_key TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- sessions table
CREATE TABLE IF NOT EXISTS sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id uuid REFERENCES organisations(id) ON DELETE CASCADE,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
    -- NO audio_data, NO transcript columns (NDPA 2023)
);

-- BLOCK 2: ROW LEVEL SECURITY & POLICIES
/*
2. ROW LEVEL SECURITY: enable on all tables
*/

ALTER TABLE sign_poses      ENABLE ROW LEVEL SECURITY;
ALTER TABLE organisations   ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions        ENABLE ROW LEVEL SECURITY;
ALTER TABLE config          ENABLE ROW LEVEL SECURITY;

/*
3. RLS POLICIES
*/

-- sign_poses
-- Anyone (including anonymous) can read poses to render signs on the avatar.
-- Only permanent (non-anonymous) users can insert or update pose records.
CREATE POLICY "anyone can read poses"
    ON sign_poses FOR SELECT
    USING(true);

CREATE POLICY "only permanent users can insert poses"
    ON sign_poses FOR INSERT 
    WITH CHECK(
        auth.jwt() ->> 'is_anonymous' = 'false'
    );

-- sessions
-- Any authenticated user (including anonymous) can create and update
-- their own session. No one can read other users' sessions.
CREATE POLICY "users can create their own sessions"
    ON sessions FOR INSERT
    WITH CHECK(auth.uid() IS NOT NULL);

CREATE POLICY "users can update their own sessions"
    ON sessions FOR UPDATE
    WITH CHECK(auth.uid()::text = org_id::text);

-- organisations
-- Only permanent users can read org data.
-- Anonymous users must never see API keys.
CREATE POLICY "only permanent users can read orgs"
  ON organisations FOR SELECT
  USING (
    auth.jwt() ->> 'is_anonymous' = 'false'
  );

-- config
-- Anyone can read config (bone names, settings).
-- Only permanent users can update it.
CREATE POLICY "anyone can read config"
  ON config FOR SELECT
  USING (true);

CREATE POLICY "only permanent users can update config"
  ON config FOR UPDATE
  USING (
    auth.jwt() ->> 'is_anonymous' = 'false'
  );

/*
4. ADMIN VIEW
*/

-- Only service_role (Isaac's admin key) can read session data.
-- This powers the password-protected admin view.
CREATE POLICY "admin only"
  ON sessions FOR SELECT
  USING (auth.role() = 'service_role');