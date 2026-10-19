-- ============================================================
-- Academic Assistant & CO Tracker : database schema (PostgreSQL / Supabase)
-- Safe to re-run: tables use IF NOT EXISTS, functions/triggers are replaced.
-- Owner: Aparna. File: backend/migrations/001_init.sql
-- ============================================================

-- Optional, only if the team chooses pgvector for slide Q&A:
-- CREATE EXTENSION IF NOT EXISTS vector;
-- ALTER TABLE content_chunks ADD COLUMN IF NOT EXISTS embedding vector(1024);

-- ---------- Students and users ----------

CREATE TABLE IF NOT EXISTS students (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    usn        text NOT NULL UNIQUE,                 -- store trimmed + UPPERCASE
    name       text NOT NULL,
    pin_hash   text NOT NULL,                        -- bcrypt/argon2, never plain text
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT usn_normalised CHECK (usn = upper(btrim(usn)) AND length(usn) > 0)
);

CREATE TABLE IF NOT EXISTS users (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    role          text NOT NULL CHECK (role IN ('faculty', 'student')),
    email         text UNIQUE,                       -- faculty login
    password_hash text,                              -- faculty login
    student_id    uuid UNIQUE REFERENCES students(id) ON DELETE CASCADE,
    created_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT faculty_has_credentials CHECK (
        role <> 'faculty' OR (email IS NOT NULL AND password_hash IS NOT NULL)),
    CONSTRAINT student_has_student_row CHECK (
        role <> 'student' OR student_id IS NOT NULL)
);

-- ---------- Course structure ----------

CREATE TABLE IF NOT EXISTS subjects (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code                  text NOT NULL,
    name                  text NOT NULL,
    semester              int  NOT NULL CHECK (semester BETWEEN 1 AND 12),
    faculty_user_id       uuid NOT NULL REFERENCES users(id),
    target_attainment_pct numeric(5,2) NOT NULL DEFAULT 60 CHECK (target_attainment_pct BETWEEN 0 AND 100),
    default_threshold_pct numeric(5,2) NOT NULL DEFAULT 60 CHECK (default_threshold_pct BETWEEN 0 AND 100),
    created_at            timestamptz NOT NULL DEFAULT now(),
    UNIQUE (faculty_user_id, code, semester)
);

CREATE TABLE IF NOT EXISTS course_outcomes (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_id            uuid NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    number                int  NOT NULL CHECK (number BETWEEN 1 AND 6),   -- CO1..CO6
    description           text NOT NULL,
    threshold_pct         numeric(5,2) NOT NULL DEFAULT 60 CHECK (threshold_pct BETWEEN 0 AND 100),
    target_attainment_pct numeric(5,2) NOT NULL DEFAULT 60 CHECK (target_attainment_pct BETWEEN 0 AND 100),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (subject_id, number)
);

CREATE TABLE IF NOT EXISTS modules (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_id        uuid NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    number            int  NOT NULL CHECK (number > 0),
    title             text NOT NULL,
    ppt_file_path     text,
    processing_status text NOT NULL DEFAULT 'pending'
                      CHECK (processing_status IN ('pending', 'processing', 'done', 'failed')),
    processing_error  text,
    processed_at      timestamptz,
    created_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (subject_id, number)
);

CREATE TABLE IF NOT EXISTS content_chunks (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    module_id    uuid NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
    slide_number int  NOT NULL CHECK (slide_number > 0),
    text         text NOT NULL,
    tag_status   text NOT NULL DEFAULT 'untagged' CHECK (tag_status IN ('tagged', 'untagged')),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chunk_cos (
    chunk_id   uuid NOT NULL REFERENCES content_chunks(id) ON DELETE CASCADE,
    co_id      uuid NOT NULL REFERENCES course_outcomes(id) ON DELETE CASCADE,
    confidence numeric(4,3) CHECK (confidence BETWEEN 0 AND 1),
    PRIMARY KEY (chunk_id, co_id)
);

-- ---------- Questions and study material ----------

CREATE TABLE IF NOT EXISTS questions (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    module_id      uuid NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
    co_id          uuid NOT NULL REFERENCES course_outcomes(id) ON DELETE CASCADE,
    stem           text NOT NULL,
    options        jsonb NOT NULL,                   -- ["A text","B text","C text","D text"]
    correct_option smallint NOT NULL,                -- index into options: 0..3
    explanation    text,
    marks          numeric(5,2) NOT NULL DEFAULT 1 CHECK (marks > 0),
    difficulty     text CHECK (difficulty IN ('easy', 'medium', 'hard')),
    bloom_level    text CHECK (bloom_level IN ('remember', 'understand', 'apply', 'analyze', 'evaluate', 'create')),
    status         text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'approved', 'rejected')),
    source         text NOT NULL CHECK (source IN ('AI', 'faculty')),
    created_by     uuid REFERENCES users(id),
    created_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT four_options CHECK (jsonb_typeof(options) = 'array' AND jsonb_array_length(options) = 4),
    CONSTRAINT one_correct_in_range CHECK (correct_option BETWEEN 0 AND 3)
);

CREATE TABLE IF NOT EXISTS flashcards (
    id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    module_id uuid NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
    co_id     uuid REFERENCES course_outcomes(id) ON DELETE SET NULL,
    front     text NOT NULL,
    back      text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS notes (
    id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    module_id uuid NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
    co_id     uuid REFERENCES course_outcomes(id) ON DELETE SET NULL,
    title     text NOT NULL,
    body      text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- ---------- Enrollment ----------

CREATE TABLE IF NOT EXISTS enrollments (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id uuid NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    subject_id uuid NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    section    text NOT NULL DEFAULT 'A',
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (student_id, subject_id)                  -- one enrollment per student per subject
);

-- ---------- Quizzes and attempts ----------

CREATE TABLE IF NOT EXISTS quizzes (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    module_id    uuid REFERENCES modules(id) ON DELETE SET NULL,
    subject_id   uuid NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    title        text NOT NULL,
    opens_at     timestamptz,
    closes_at    timestamptz,
    published    boolean NOT NULL DEFAULT false,
    published_at timestamptz,
    created_by   uuid REFERENCES users(id),
    created_at   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT closes_after_opens CHECK (closes_at IS NULL OR opens_at IS NULL OR closes_at > opens_at)
);

CREATE TABLE IF NOT EXISTS quiz_questions (
    quiz_id     uuid NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    question_id uuid NOT NULL REFERENCES questions(id) ON DELETE RESTRICT,
    position    int  NOT NULL DEFAULT 0,
    PRIMARY KEY (quiz_id, question_id)
);

CREATE TABLE IF NOT EXISTS quiz_attempts (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    quiz_id        uuid NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    student_id     uuid NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    attempt_number smallint NOT NULL CHECK (attempt_number IN (1, 2)),   -- max 2 attempts
    answers        jsonb NOT NULL DEFAULT '{}'::jsonb,
    total_score    numeric(7,2),
    max_score      numeric(7,2),
    started_at     timestamptz NOT NULL DEFAULT now(),
    submitted_at   timestamptz,
    created_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (student_id, quiz_id, attempt_number)
);

CREATE TABLE IF NOT EXISTS student_co_scores (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id      uuid NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    subject_id      uuid NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    module_id       uuid REFERENCES modules(id) ON DELETE SET NULL,
    co_id           uuid NOT NULL REFERENCES course_outcomes(id) ON DELETE CASCADE,
    attempt_id      uuid NOT NULL REFERENCES quiz_attempts(id) ON DELETE CASCADE,
    marks_obtained  numeric(7,2) NOT NULL CHECK (marks_obtained >= 0),
    max_marks       numeric(7,2) NOT NULL CHECK (max_marks > 0),
    percentage      numeric(5,2) NOT NULL CHECK (percentage BETWEEN 0 AND 100),
    counted         boolean NOT NULL DEFAULT true,   -- does this row count under ATTEMPT_RULE
    created_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT marks_within_max CHECK (marks_obtained <= max_marks),
    UNIQUE (attempt_id, co_id)
);

-- ---------- Calendar, study plans, logs ----------

CREATE TABLE IF NOT EXISTS events (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_id       uuid NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    section          text,
    type             text NOT NULL CHECK (type IN ('quiz', 'assignment', 'exam', 'teaching', 'custom')),
    title            text NOT NULL,
    starts_at        timestamptz NOT NULL,
    ends_at          timestamptz,
    quiz_id          uuid REFERENCES quizzes(id) ON DELETE SET NULL,
    module_id        uuid REFERENCES modules(id) ON DELETE SET NULL,
    created_by       uuid REFERENCES users(id),
    created_by_agent boolean NOT NULL DEFAULT false,
    created_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ends_after_starts CHECK (ends_at IS NULL OR ends_at >= starts_at)
);

CREATE TABLE IF NOT EXISTS study_plans (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id   uuid NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    subject_id   uuid NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    weak_co_ids  uuid[] NOT NULL DEFAULT '{}',
    plan         jsonb NOT NULL,
    generated_at timestamptz NOT NULL DEFAULT now(),
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent_logs (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           uuid REFERENCES users(id) ON DELETE SET NULL,
    role              text,
    kind              text NOT NULL CHECK (kind IN ('ai_call', 'tool_call')),
    step              text,                           -- tagging, generation, agent, qa, study_plan ...
    model             text,
    tool_name         text,
    prompt_tokens     int,
    completion_tokens int,
    total_tokens      int,
    latency_ms        int,
    args              jsonb,
    result_summary    text,
    error             text,
    created_at        timestamptz NOT NULL DEFAULT now()
);

-- ---------- Indexes ----------

CREATE INDEX IF NOT EXISTS idx_modules_subject       ON modules(subject_id);
CREATE INDEX IF NOT EXISTS idx_chunks_module         ON content_chunks(module_id);
CREATE INDEX IF NOT EXISTS idx_chunk_cos_co          ON chunk_cos(co_id);
CREATE INDEX IF NOT EXISTS idx_questions_module_co   ON questions(module_id, co_id, status);
CREATE INDEX IF NOT EXISTS idx_enrollments_subject   ON enrollments(subject_id, section);
CREATE INDEX IF NOT EXISTS idx_quizzes_subject       ON quizzes(subject_id);
CREATE INDEX IF NOT EXISTS idx_attempts_student      ON quiz_attempts(student_id, quiz_id);
CREATE INDEX IF NOT EXISTS idx_scores_subject_co     ON student_co_scores(subject_id, co_id);
CREATE INDEX IF NOT EXISTS idx_scores_student        ON student_co_scores(student_id);
CREATE INDEX IF NOT EXISTS idx_events_subject_time   ON events(subject_id, starts_at);
CREATE INDEX IF NOT EXISTS idx_agent_logs_step       ON agent_logs(step, created_at);

-- ============================================================
-- Rule: only approved questions can appear in a published quiz.
-- Enforced by three triggers so no code path can get around it.
-- ============================================================

-- 1) A question can only be added to a quiz if it is approved.
CREATE OR REPLACE FUNCTION fn_quiz_question_must_be_approved() RETURNS trigger AS $$
DECLARE q_status text;
BEGIN
    SELECT status INTO q_status FROM questions WHERE id = NEW.question_id;
    IF q_status IS DISTINCT FROM 'approved' THEN
        RAISE EXCEPTION 'Question % is not approved (status: %) and cannot be added to a quiz',
            NEW.question_id, COALESCE(q_status, 'missing')
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_quiz_question_approved ON quiz_questions;
CREATE TRIGGER trg_quiz_question_approved
    BEFORE INSERT OR UPDATE OF question_id ON quiz_questions
    FOR EACH ROW EXECUTE FUNCTION fn_quiz_question_must_be_approved();

-- 2) A quiz can only be published if it has questions and all are approved.
CREATE OR REPLACE FUNCTION fn_quiz_publish_check() RETURNS trigger AS $$
BEGIN
    IF NEW.published THEN
        IF NOT EXISTS (SELECT 1 FROM quiz_questions WHERE quiz_id = NEW.id) THEN
            RAISE EXCEPTION 'Quiz % has no questions and cannot be published', NEW.id
                USING ERRCODE = 'check_violation';
        END IF;
        IF EXISTS (
            SELECT 1 FROM quiz_questions qq
            JOIN questions q ON q.id = qq.question_id
            WHERE qq.quiz_id = NEW.id AND q.status <> 'approved'
        ) THEN
            RAISE EXCEPTION 'Quiz % contains unapproved questions and cannot be published', NEW.id
                USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.published_at IS NULL THEN
            NEW.published_at := now();
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_quiz_publish_check ON quizzes;
CREATE TRIGGER trg_quiz_publish_check
    BEFORE INSERT OR UPDATE OF published ON quizzes
    FOR EACH ROW EXECUTE FUNCTION fn_quiz_publish_check();

-- 3) An approved question cannot be un-approved while it sits in a published quiz.
CREATE OR REPLACE FUNCTION fn_question_unapprove_guard() RETURNS trigger AS $$
BEGIN
    IF OLD.status = 'approved' AND NEW.status <> 'approved' AND EXISTS (
        SELECT 1 FROM quiz_questions qq
        JOIN quizzes z ON z.id = qq.quiz_id
        WHERE qq.question_id = NEW.id AND z.published
    ) THEN
        RAISE EXCEPTION 'Question % is in a published quiz and cannot be un-approved', NEW.id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_question_unapprove_guard ON questions;
CREATE TRIGGER trg_question_unapprove_guard
    BEFORE UPDATE OF status ON questions
    FOR EACH ROW EXECUTE FUNCTION fn_question_unapprove_guard();
