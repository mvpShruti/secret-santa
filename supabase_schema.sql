-- =========================================================
-- Secret Santa Database Schema for Supabase
-- =========================================================
-- Run this script in your Supabase SQL Editor to create all tables
-- Go to: https://supabase.com/dashboard → SQL Editor → New Query

-- =========================================================
-- 1. TEAMS TABLE
-- =========================================================
CREATE TABLE IF NOT EXISTS teams (
    id BIGSERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    location TEXT,
    admin_pin TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- =========================================================
-- 2. PARTICIPANTS TABLE
-- =========================================================
CREATE TABLE IF NOT EXISTS participants (
    id BIGSERIAL PRIMARY KEY,
    team_id BIGINT NOT NULL,
    name TEXT NOT NULL,
    secret TEXT,
    assigned INTEGER DEFAULT 0,
    email TEXT,
    has_completed_survey INTEGER DEFAULT 0,
    last_login TEXT,
    UNIQUE(team_id, name),
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE
);

-- =========================================================
-- 3. ASSIGNMENTS TABLE
-- =========================================================
CREATE TABLE IF NOT EXISTS assignments (
    id BIGSERIAL PRIMARY KEY,
    team_id BIGINT NOT NULL,
    drawer_name TEXT NOT NULL,
    recipient_name TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    revealed INTEGER DEFAULT 0,
    revealed_timestamp TEXT,
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE
);

-- =========================================================
-- 4. LOGS TABLE
-- =========================================================
CREATE TABLE IF NOT EXISTS logs (
    id BIGSERIAL PRIMARY KEY,
    team_id BIGINT,
    timestamp TEXT NOT NULL,
    actor TEXT,
    action TEXT NOT NULL,
    details TEXT,
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE
);

-- =========================================================
-- 5. WISHLISTS TABLE
-- =========================================================
CREATE TABLE IF NOT EXISTS wishlists (
    id BIGSERIAL PRIMARY KEY,
    participant_id BIGINT NOT NULL,
    team_id BIGINT NOT NULL,
    item_text TEXT NOT NULL,
    priority INTEGER DEFAULT 2,
    item_link TEXT,
    item_order INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (participant_id) REFERENCES participants(id) ON DELETE CASCADE,
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE
);

-- =========================================================
-- 6. SURVEY QUESTIONS TABLE
-- =========================================================
CREATE TABLE IF NOT EXISTS survey_questions (
    id BIGSERIAL PRIMARY KEY,
    question_text TEXT NOT NULL,
    option_a TEXT NOT NULL,
    option_b TEXT NOT NULL,
    emoji_a TEXT,
    emoji_b TEXT,
    display_order INTEGER DEFAULT 0
);

-- =========================================================
-- 7. SURVEY RESPONSES TABLE
-- =========================================================
CREATE TABLE IF NOT EXISTS survey_responses (
    id BIGSERIAL PRIMARY KEY,
    participant_id BIGINT NOT NULL,
    team_id BIGINT NOT NULL,
    question_id BIGINT NOT NULL,
    answer TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(participant_id, team_id, question_id),
    FOREIGN KEY (participant_id) REFERENCES participants(id) ON DELETE CASCADE,
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES survey_questions(id) ON DELETE CASCADE
);

-- =========================================================
-- 8. MESSAGES TABLE
-- =========================================================
CREATE TABLE IF NOT EXISTS messages (
    id BIGSERIAL PRIMARY KEY,
    team_id BIGINT NOT NULL,
    assignment_id BIGINT NOT NULL,
    sender_role TEXT NOT NULL,
    message_type TEXT NOT NULL,
    content TEXT NOT NULL,
    is_read INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
    FOREIGN KEY (assignment_id) REFERENCES assignments(id) ON DELETE CASCADE
);

-- =========================================================
-- CREATE INDEXES FOR BETTER PERFORMANCE
-- =========================================================

-- Participants indexes
CREATE INDEX IF NOT EXISTS idx_participants_team_id ON participants(team_id);
CREATE INDEX IF NOT EXISTS idx_participants_name ON participants(name);

-- Assignments indexes
CREATE INDEX IF NOT EXISTS idx_assignments_team_id ON assignments(team_id);
CREATE INDEX IF NOT EXISTS idx_assignments_drawer ON assignments(drawer_name);
CREATE INDEX IF NOT EXISTS idx_assignments_recipient ON assignments(recipient_name);

-- Wishlists indexes
CREATE INDEX IF NOT EXISTS idx_wishlists_participant ON wishlists(participant_id);
CREATE INDEX IF NOT EXISTS idx_wishlists_team ON wishlists(team_id);

-- Messages indexes
CREATE INDEX IF NOT EXISTS idx_messages_assignment ON messages(assignment_id);
CREATE INDEX IF NOT EXISTS idx_messages_team ON messages(team_id);

-- Logs indexes
CREATE INDEX IF NOT EXISTS idx_logs_team ON logs(team_id);

-- Survey responses indexes
CREATE INDEX IF NOT EXISTS idx_survey_responses_participant ON survey_responses(participant_id);
CREATE INDEX IF NOT EXISTS idx_survey_responses_question ON survey_responses(question_id);

-- =========================================================
-- DONE!
-- =========================================================
-- All tables created successfully.
-- The app will auto-populate survey_questions on first run.
