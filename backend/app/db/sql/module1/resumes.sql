-- ============================================================================
--  HR HIRING ASSISTANT - POC
--  Module 1 : Resume Repository & Ingestion
--
--  TABLE      : resumes
--  RUN ORDER  : 2 of 4   (candidates -> resumes -> candidate_embeddings
--                         -> duplicate_tracking)
--  DATABASE   : PostgreSQL 16 + pgvector
--  OWNER      : Monish
--
--  WHAT IT HOLDS
--    One row = one uploaded resume FILE.
--    One candidate can have many resumes (he re-applies with an updated CV).
--    Exactly one of them is flagged is_latest = TRUE.
--
--  DEPENDS ON
--    candidates.sql   (foreign key candidate_id)
--    set_updated_at() (trigger function defined in candidates.sql)
--
--  IMPORTANT
--    candidate_id is NULLABLE on purpose. A file is saved the moment it
--    arrives, but we do not know WHOSE resume it is until the LLM has read
--    it 60 seconds later. If this column were NOT NULL the very first
--    INSERT would be impossible.
--
--  REVISION 2026-08-25 (Monish)
--    - resume_id is now BIGSERIAL; candidate_id is BIGINT to match.
--    - Removed storage_backend   : local disk only for the POC.
--    - Removed retry_count       : no automatic retries. A FAILED file stays
--                                  FAILED until HR uploads it again.
--    - Removed uploaded_by       : no audit trail of who uploaded. This was
--                                  the only link to the hr_users table, so
--                                  this table no longer depends on the auth
--                                  module at all.
--    - Removed extraction_started_at : queue-wait timing not needed.
-- ============================================================================


-- ----------------------------------------------------------------------------
--  TABLE : resumes
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS resumes (

    -- ---- identity -----------------------------------------------------------
    resume_id              BIGSERIAL     PRIMARY KEY,

    -- ---- link to the person -------------------------------------------------
    --  NULL until the LLM extraction identifies the candidate.
    --  CASCADE: deleting a candidate removes all of their resume rows.
    candidate_id           BIGINT        REFERENCES candidates(candidate_id)
                                         ON DELETE CASCADE,
    resume_version         INTEGER,      -- 1, 2, 3 ... filled with candidate_id

    -- ---- the file itself ----------------------------------------------------
    file_name              VARCHAR(500)  NOT NULL,   -- original name from HR
    file_path              TEXT          NOT NULL,   -- path on local disk
    file_type              VARCHAR(20)   NOT NULL,   -- pdf / docx / doc / txt
    file_size_bytes        BIGINT        NOT NULL,
    file_hash              VARCHAR(64)   NOT NULL,   -- SHA-256 hex, 64 chars

    -- ---- processing pipeline ------------------------------------------------
    processing_status      VARCHAR(50)   NOT NULL DEFAULT 'UPLOADED',
    failure_reason         TEXT,                     -- required when FAILED
    extracted_text         TEXT,                     -- words pulled from the file

    -- ---- version control ----------------------------------------------------
    is_latest              BOOLEAN       NOT NULL DEFAULT FALSE,

    -- ---- timestamps ---------------------------------------------------------
    processed_at           TIMESTAMPTZ,
    created_at             TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ   NOT NULL DEFAULT now(),

    -- ---- guard rails --------------------------------------------------------

    --  Only these six states exist. A typo like 'COMPLETD' is refused.
    CONSTRAINT ck_resumes_status
        CHECK (processing_status IN
              ('UPLOADED','PROCESSING','EXTRACTED','COMPLETED','FAILED','REJECTED')),

    --  Only formats we have a parser for.
    CONSTRAINT ck_resumes_file_type
        CHECK (file_type IN ('pdf','docx','doc','txt')),

    --  SHA-256 hex is ALWAYS exactly 64 lowercase hex characters.
    --  If the hashing code ever breaks, this catches it on the first insert
    --  instead of silently destroying duplicate detection.
    CONSTRAINT ck_resumes_hash_format
        CHECK (file_hash ~ '^[0-9a-f]{64}$'),

    --  No empty files. No files above 10 MB.
    CONSTRAINT ck_resumes_size_positive
        CHECK (file_size_bytes > 0 AND file_size_bytes <= 10485760),

    --  A FAILED resume must say WHY it failed.
    --  Guarantees you can never have a mystery failure six months later.
    CONSTRAINT ck_resumes_failed_has_reason
        CHECK (processing_status <> 'FAILED' OR failure_reason IS NOT NULL),

    --  candidate_id and resume_version are set together, or not at all.
    --  Prevents a half-linked row.
    CONSTRAINT ck_resumes_version_with_candidate
        CHECK ((candidate_id IS NULL     AND resume_version IS NULL)
            OR (candidate_id IS NOT NULL AND resume_version IS NOT NULL)),

    --  You cannot be "the latest resume" of nobody.
    CONSTRAINT ck_resumes_latest_needs_candidate
        CHECK (is_latest = FALSE OR candidate_id IS NOT NULL),

    --  Version numbers start at 1.
    CONSTRAINT ck_resumes_version_positive
        CHECK (resume_version IS NULL OR resume_version >= 1)
);


-- ----------------------------------------------------------------------------
--  INDEXES
-- ----------------------------------------------------------------------------

--  UNIQUE : the identical file can physically never be stored twice.
--  This is EXACT_FILE_MATCH enforced by the database, not by Python.
--  Even two simultaneous uploads of the same file cannot both succeed.
CREATE UNIQUE INDEX IF NOT EXISTS ux_resumes_file_hash
    ON resumes (file_hash);

--  UNIQUE : one candidate cannot have two resumes numbered "version 2".
--  Partial, because unlinked rows have NULL in both columns.
CREATE UNIQUE INDEX IF NOT EXISTS ux_resumes_version
    ON resumes (candidate_id, resume_version)
    WHERE candidate_id IS NOT NULL;

--  UNIQUE + PARTIAL : the most important index in this table.
--  Among rows where is_latest = TRUE, candidate_id must be unique.
--  Meaning: ONE candidate can have exactly ONE latest resume.
--  If the application code forgets to unset the old one, Postgres raises
--  an error instead of silently leaving two "latest" resumes behind.
CREATE UNIQUE INDEX IF NOT EXISTS ux_resumes_one_latest
    ON resumes (candidate_id)
    WHERE is_latest = TRUE;

--  "Show me all of Ravi's resumes, newest first"
CREATE INDEX IF NOT EXISTS ix_resumes_candidate
    ON resumes (candidate_id, resume_version DESC);

--  The background worker asks: "what still needs processing?"
CREATE INDEX IF NOT EXISTS ix_resumes_status
    ON resumes (processing_status);

--  The work queue. Partial index = only the handful of unfinished rows,
--  so it stays tiny even with 100,000 completed resumes.
CREATE INDEX IF NOT EXISTS ix_resumes_pending
    ON resumes (created_at)
    WHERE processing_status IN ('UPLOADED','PROCESSING');


-- ----------------------------------------------------------------------------
--  TRIGGER : keep updated_at honest
--  Reuses set_updated_at() defined in candidates.sql
-- ----------------------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_resumes_updated_at ON resumes;

CREATE TRIGGER trg_resumes_updated_at
    BEFORE UPDATE ON resumes
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();


-- ----------------------------------------------------------------------------
--  DOCUMENTATION
-- ----------------------------------------------------------------------------
COMMENT ON TABLE resumes IS
    'One row per uploaded resume file. A candidate may have many resumes; exactly one carries is_latest = TRUE. Owned by Module 1.';

COMMENT ON COLUMN resumes.candidate_id IS
    'NULLABLE BY DESIGN. The file is stored the instant it arrives, but the owning candidate is only known after LLM extraction completes. Filled in together with resume_version.';

COMMENT ON COLUMN resumes.resume_version IS
    'Sequential per candidate, starting at 1. Set together with candidate_id.';

COMMENT ON COLUMN resumes.file_path IS
    'Path on local disk where the uploaded file is kept. Local storage only for the POC.';

COMMENT ON COLUMN resumes.file_hash IS
    'SHA-256 of the raw file bytes, lowercase hex, exactly 64 characters. UNIQUE - this is how EXACT_FILE_MATCH duplicate detection is enforced at the database level.';

COMMENT ON COLUMN resumes.processing_status IS
    'UPLOADED -> PROCESSING -> EXTRACTED -> COMPLETED. Or FAILED (see failure_reason) / REJECTED (duplicate file). No automatic retries: a FAILED file stays FAILED until HR uploads it again.';

COMMENT ON COLUMN resumes.failure_reason IS
    'Mandatory whenever processing_status is FAILED. See ck_resumes_failed_has_reason.';

COMMENT ON COLUMN resumes.extracted_text IS
    'Raw text pulled out of the file by the parser. Input to the LLM profile extractor and to the chunker.';

COMMENT ON COLUMN resumes.is_latest IS
    'TRUE for the candidate current resume. Enforced unique per candidate by ux_resumes_one_latest. Always unset the previous row BEFORE setting the new one.';

COMMENT ON COLUMN resumes.processed_at IS
    'When processing finished (COMPLETED or FAILED). NULL while still in the pipeline.';


-- ============================================================================
--  END OF FILE : resumes.sql
--  NEXT        : candidate_embeddings.sql
-- ============================================================================
