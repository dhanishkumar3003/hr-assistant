-- ============================================================================
--  HR HIRING ASSISTANT - POC
--  Module 1 : Resume Repository & Ingestion
--
--  TABLE      : candidates
--  RUN ORDER  : 1 of 4   (candidates -> resumes -> candidate_embeddings
--                         -> duplicate_tracking)
--  DATABASE   : PostgreSQL 16 + pgvector
--  OWNER      : Monish
--
--  WHAT IT HOLDS
--    One row = one human being. The master candidate profile.
--    This is the parent table. Every other Module 1 table points here.
--
--  NOTE
--    Run this file FIRST. The other three tables have foreign keys to
--    candidates and will fail if this table does not exist yet.
--
--  REVISION 2026-08-25 (Monish)
--    - candidate_id is now BIGSERIAL (1, 2, 3 ...) instead of UUID.
--      Simpler to read, smaller to store, faster to join. The pgcrypto
--      extension is no longer needed. Trade-off: ids are guessable, so a
--      candidate_id must never be treated as a secret (interview links get
--      their own random token from Module 4/5).
--    - summary column removed. If the LLM writes a one-paragraph intro it
--      still lives inside raw_profile_json.
-- ============================================================================


-- ----------------------------------------------------------------------------
--  EXTENSIONS  (safe to re-run; needed once per database)
-- ----------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS vector;     -- pgvector, used by candidate_embeddings


-- ----------------------------------------------------------------------------
--  SHARED TRIGGER FUNCTION
--  Automatically stamps updated_at on every UPDATE.
--  Without this, updated_at is a lie - it only changes if the application
--  remembers to set it every single time, which it will not.
--  Defined here because candidates is the first table created; the other
--  three tables reuse this same function.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- ----------------------------------------------------------------------------
--  TABLE : candidates
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS candidates (

    -- ---- identity -----------------------------------------------------------
    --  BIGSERIAL = BIGINT that fills itself in: 1, 2, 3 ... on every insert.
    candidate_id           BIGSERIAL     PRIMARY KEY,

    -- ---- contact ------------------------------------------------------------
    name                   VARCHAR(255)  NOT NULL,
    email                  VARCHAR(320),          -- nullable: AI may not find one
    phone                  VARCHAR(30),           -- normalised to last 10 digits

    -- ---- current position ---------------------------------------------------
    current_location       VARCHAR(255),
    current_job_title      VARCHAR(255),
    current_company        VARCHAR(255),
    experience_years       NUMERIC(5,2),          -- decimal: 8.50 years is valid

    -- ---- profile content ----------------------------------------------------
    skills                 JSONB         NOT NULL DEFAULT '[]'::jsonb,
    education              JSONB         NOT NULL DEFAULT '[]'::jsonb,
    experience             JSONB         NOT NULL DEFAULT '[]'::jsonb,
    certifications         JSONB         NOT NULL DEFAULT '[]'::jsonb,
    linkedin_url           VARCHAR(500),

    -- ---- AI traceability ----------------------------------------------------
    extraction_confidence  NUMERIC(5,2),          -- 0.00 to 1.00
    raw_profile_json       JSONB,                 -- complete untouched LLM output

    -- ---- record lifecycle ---------------------------------------------------
    is_active              BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at             TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ   NOT NULL DEFAULT now(),

    -- ---- guard rails --------------------------------------------------------
    --  The database refuses bad data. Do not rely on Python alone.

    CONSTRAINT ck_candidates_name_not_blank
        CHECK (length(trim(name)) > 0),

    CONSTRAINT ck_candidates_experience_range
        CHECK (experience_years IS NULL OR experience_years BETWEEN 0 AND 70),

    CONSTRAINT ck_candidates_confidence_range
        CHECK (extraction_confidence IS NULL OR extraction_confidence BETWEEN 0 AND 1),

    -- forces ravi@gmail.com, never Ravi@Gmail.com
    CONSTRAINT ck_candidates_email_lowercase
        CHECK (email IS NULL OR email = lower(email)),

    -- forces 9876543210, never '+91 98765 43210'
    -- if this is not enforced, duplicate detection by phone silently fails
    CONSTRAINT ck_candidates_phone_digits
        CHECK (phone IS NULL OR phone ~ '^[0-9]{10}$'),

    -- forces ["Java"] and never {"Java": true}
    CONSTRAINT ck_candidates_skills_is_array
        CHECK (jsonb_typeof(skills)         = 'array'),
    CONSTRAINT ck_candidates_education_is_array
        CHECK (jsonb_typeof(education)      = 'array'),
    CONSTRAINT ck_candidates_experience_is_array
        CHECK (jsonb_typeof(experience)     = 'array'),
    CONSTRAINT ck_candidates_certifications_is_array
        CHECK (jsonb_typeof(certifications) = 'array')
);


-- ----------------------------------------------------------------------------
--  INDEXES
-- ----------------------------------------------------------------------------

--  UNIQUE : two candidates can never share an email address.
--  lower() so Ravi@Gmail.com and ravi@gmail.com are treated as one person.
--  Partial (WHERE email IS NOT NULL) so many candidates may have no email.
--  This is what makes duplicate detection race-condition proof - a Python
--  "if exists" check cannot guarantee this, the database can.
CREATE UNIQUE INDEX IF NOT EXISTS ux_candidates_email
    ON candidates (lower(email))
    WHERE email IS NOT NULL;

--  Phone is NOT unique (families and offices share numbers) but is indexed
--  because duplicate detection looks it up on every single upload.
CREATE INDEX IF NOT EXISTS ix_candidates_phone
    ON candidates (phone)
    WHERE phone IS NOT NULL;

--  HR filter columns
CREATE INDEX IF NOT EXISTS ix_candidates_job_title
    ON candidates (current_job_title);

CREATE INDEX IF NOT EXISTS ix_candidates_experience
    ON candidates (experience_years);

CREATE INDEX IF NOT EXISTS ix_candidates_location
    ON candidates (current_location);

--  GIN : searches INSIDE the JSON.
--  Makes  skills @> '["Java"]'  fast instead of a full table scan.
CREATE INDEX IF NOT EXISTS ix_candidates_skills_gin
    ON candidates USING gin (skills);

--  Same, for  certifications @> '["AWS Certified Developer"]'
CREATE INDEX IF NOT EXISTS ix_candidates_certifications_gin
    ON candidates USING gin (certifications);

--  Almost every listing query says "WHERE is_active" and sorts newest first.
--  Partial index = smaller and faster than indexing every row.
CREATE INDEX IF NOT EXISTS ix_candidates_active
    ON candidates (created_at DESC)
    WHERE is_active;


-- ----------------------------------------------------------------------------
--  TRIGGER : keep updated_at honest
-- ----------------------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_candidates_updated_at ON candidates;

CREATE TRIGGER trg_candidates_updated_at
    BEFORE UPDATE ON candidates
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();


-- ----------------------------------------------------------------------------
--  DOCUMENTATION  (stored inside the database itself)
--  Any developer can run  \d+ candidates  and read these.
-- ----------------------------------------------------------------------------
COMMENT ON TABLE candidates IS
    'Master candidate profile. One row per human being. Owned by Module 1 (Resume Repository and Ingestion). Parent of resumes, candidate_embeddings and duplicate_tracking.';

COMMENT ON COLUMN candidates.candidate_id IS
    'Primary key, BIGSERIAL (auto-incrementing integer). Referenced by every other module. Guessable by design - never use it as a secret.';

COMMENT ON COLUMN candidates.email IS
    'Stored lowercase (see ck_candidates_email_lowercase). Unique when present. Primary signal for duplicate detection.';

COMMENT ON COLUMN candidates.phone IS
    'Normalised to the last 10 digits only (see ck_candidates_phone_digits). Secondary signal for duplicate detection.';

COMMENT ON COLUMN candidates.skills IS
    'JSON array of skill strings, for example ["Java","Docker","AWS"]. Query with the @> containment operator.';

COMMENT ON COLUMN candidates.certifications IS
    'JSON array of certificate strings. Filterable with the @> containment operator.';

COMMENT ON COLUMN candidates.extraction_confidence IS
    'LLM self-reported confidence, 0.00 to 1.00. Low values indicate a profile a human should review.';

COMMENT ON COLUMN candidates.raw_profile_json IS
    'Complete untouched LLM output, including fields that have no column of their own (summary, notice period, languages, awards). Source for backfilling new columns later WITHOUT re-running the AI on every resume.';

COMMENT ON COLUMN candidates.is_active IS
    'Soft delete flag. Never DELETE a candidate row; set this to FALSE instead.';


-- ============================================================================
--  END OF FILE : candidates.sql
--  NEXT        : resumes.sql
-- ============================================================================
