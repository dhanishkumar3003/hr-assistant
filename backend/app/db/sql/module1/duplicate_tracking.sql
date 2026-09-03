-- ============================================================================
--  HR HIRING ASSISTANT - POC
--  Module 1 : Resume Repository & Ingestion
--
--  TABLE      : duplicate_tracking
--  RUN ORDER  : 4 of 4   (candidates -> resumes -> candidate_embeddings
--                         -> duplicate_tracking)
--  DATABASE   : PostgreSQL 16 + pgvector
--  OWNER      : Monish
--
--  WHAT IT HOLDS
--    One row = one duplicate detection event.
--    "We believed this candidate or this file already existed. This is how
--     we detected it, how confident we were, which record matched, and what
--     the system did about it."
--
--    This table is a DIARY. It drives no behaviour. It only remembers.
--
--  DEPENDS ON
--    candidates.sql
--    resumes.sql
--    candidate_embeddings.sql
--
--  APPEND-ONLY BY DESIGN
--    There is deliberately NO updated_at column and NO update trigger on
--    this table. A row is written once and never modified. If history can
--    be edited it stops being evidence. (PDD_TableSchema_V0.3 lists an
--    updated_at column here; it was removed on purpose.)
--
--    If a manual-review workflow is added later, record the resolution as a
--    NEW row rather than editing the original one.
--
--  PROJECT DECISION (Monish, 2026-08-24)
--    Candidate identity is EMAIL or PHONE only. If a person changes both and
--    re-uploads, a new candidate is created and that is accepted.
--    SEMANTIC_MATCH is therefore never auto-merged. The value is kept in the
--    CHECK list so enabling it later is a code change, not a migration.
--
--  REVISION 2026-08-25 (Monish)
--    - duplicate_id is now BIGSERIAL. The five reference columns
--      (resume_id, candidate_id, matched_*) are BIGINT to match the
--      parent tables.
-- ============================================================================


-- ----------------------------------------------------------------------------
--  TABLE : duplicate_tracking
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS duplicate_tracking (

    -- ---- identity -----------------------------------------------------------
    duplicate_id          BIGSERIAL     PRIMARY KEY,

    -- ---- the INCOMING record that triggered this ----------------------------
    --  NULLABLE ON PURPOSE.
    --  When the identical file is re-uploaded, the duplicate is detected from
    --  the file hash BEFORE any resumes row is inserted (and ux_resumes_file_hash
    --  would refuse the insert regardless). Such a rejected upload therefore has
    --  no resume_id to point at, but must still be recorded here so that
    --  "HR uploaded the same file five times" is visible in the audit log.
    --  The file name and hash go into detection_details in that case.
    resume_id             BIGINT        REFERENCES resumes(resume_id)
                                        ON DELETE CASCADE,

    --  Which candidate the incoming resume ended up attached to.
    --  NULL when the upload was rejected outright and no candidate resulted.
    candidate_id          BIGINT        REFERENCES candidates(candidate_id)
                                        ON DELETE SET NULL,

    -- ---- the EXISTING record we matched against -----------------------------
    --  SET NULL rather than CASCADE: if the matched record is later removed,
    --  the diary entry survives. The evidence outlives the evidence's subject.
    matched_candidate_id  BIGINT        REFERENCES candidates(candidate_id)
                                        ON DELETE SET NULL,
    matched_resume_id     BIGINT        REFERENCES resumes(resume_id)
                                        ON DELETE SET NULL,
    matched_embedding_id  BIGINT        REFERENCES candidate_embeddings(embedding_id)
                                        ON DELETE SET NULL,

    -- ---- the verdict --------------------------------------------------------
    duplicate_type        VARCHAR(50)   NOT NULL,   -- HOW it was detected
    duplicate_confidence  NUMERIC(5,2),             -- 0.00 to 1.00
    action_taken          VARCHAR(100)  NOT NULL,   -- WHAT the system did

    -- ---- the evidence -------------------------------------------------------
    --  What actually matched, e.g.
    --    {"matched_on":"email","value":"ravi.kumar@gmail.com"}
    --    {"matched_on":"file_hash","value":"619a1312..."}
    --    {"matched_on":"vector","similarity":0.72}
    detection_details     JSONB         NOT NULL DEFAULT '{}'::jsonb,

    -- ---- THE UNDO BUTTON ----------------------------------------------------
    --  old_raw_profile_json is the candidate's complete profile BEFORE this
    --  event modified it. If a merge turns out to be wrong, this is the only
    --  way to restore the original profile. Without it, a bad automatic merge
    --  destroys a real candidate's data permanently.
    old_raw_profile_json  JSONB,
    new_raw_profile_json  JSONB,

    -- ---- timestamp (creation only - see APPEND-ONLY note above) -------------
    created_at            TIMESTAMPTZ   NOT NULL DEFAULT now(),

    -- ---- guard rails --------------------------------------------------------

    CONSTRAINT ck_dup_type
        CHECK (duplicate_type IN
              ('EXACT_FILE_MATCH','EMAIL_MATCH','PHONE_MATCH','SEMANTIC_MATCH')),

    CONSTRAINT ck_dup_action
        CHECK (action_taken IN
              ('NEW_CANDIDATE_CREATED','RESUME_APPENDED','PROFILE_UPDATED',
               'DUPLICATE_REJECTED','MANUAL_REVIEW_REQUIRED')),

    CONSTRAINT ck_dup_confidence_range
        CHECK (duplicate_confidence IS NULL
               OR duplicate_confidence BETWEEN 0 AND 1),

    --  A fuzzy vector match without a similarity score is useless evidence.
    --  Exact matches (file hash, email, phone) may omit it - they are binary.
    CONSTRAINT ck_dup_semantic_needs_confidence
        CHECK (duplicate_type <> 'SEMANTIC_MATCH'
               OR duplicate_confidence IS NOT NULL),

    --  A "duplicate detected" row where nothing was matched is meaningless.
    --  At least one matched_* reference must be present.
    CONSTRAINT ck_dup_matched_something
        CHECK (matched_candidate_id IS NOT NULL
            OR matched_resume_id    IS NOT NULL
            OR matched_embedding_id IS NOT NULL),

    CONSTRAINT ck_dup_details_is_object
        CHECK (jsonb_typeof(detection_details) = 'object')
);


-- ----------------------------------------------------------------------------
--  INDEXES
-- ----------------------------------------------------------------------------

--  "Show me this candidate's duplicate history"
CREATE INDEX IF NOT EXISTS ix_dup_candidate
    ON duplicate_tracking (candidate_id)
    WHERE candidate_id IS NOT NULL;

--  "What was merged INTO this candidate?"
CREATE INDEX IF NOT EXISTS ix_dup_matched_candidate
    ON duplicate_tracking (matched_candidate_id)
    WHERE matched_candidate_id IS NOT NULL;

--  "Why was this uploaded file rejected?"
CREATE INDEX IF NOT EXISTS ix_dup_resume
    ON duplicate_tracking (resume_id);

--  THE REVIEW QUEUE.
--  Partial index: only the small number of rows awaiting a human decision.
--  Stays instant even when the table holds 100,000 historical entries.
CREATE INDEX IF NOT EXISTS ix_dup_review_queue
    ON duplicate_tracking (created_at)
    WHERE action_taken = 'MANUAL_REVIEW_REQUIRED';

--  Reporting: "how many email matches did we get this month?"
CREATE INDEX IF NOT EXISTS ix_dup_type
    ON duplicate_tracking (duplicate_type);

--  The audit timeline, newest first.
CREATE INDEX IF NOT EXISTS ix_dup_created
    ON duplicate_tracking (created_at DESC);


-- ----------------------------------------------------------------------------
--  NO UPDATE TRIGGER ON THIS TABLE - THIS IS INTENTIONAL.
--  candidates, resumes and candidate_embeddings each have a
--  trg_*_updated_at trigger. duplicate_tracking does not, because rows here
--  are never updated. Do not "fix" this by adding one.
-- ----------------------------------------------------------------------------


-- ----------------------------------------------------------------------------
--  DOCUMENTATION
-- ----------------------------------------------------------------------------
COMMENT ON TABLE duplicate_tracking IS
    'Append-only audit log of duplicate detection events. Records how a duplicate was detected, how confident the system was, which record matched, and what action was taken. Drives no behaviour - it is evidence only. Owned by Module 1.';

COMMENT ON COLUMN duplicate_tracking.resume_id IS
    'The incoming resume that triggered this detection event. NULL for an EXACT_FILE_MATCH rejection, where the duplicate is caught from the file hash before any resumes row is created - in that case the file name and hash are recorded in detection_details.';

COMMENT ON COLUMN duplicate_tracking.candidate_id IS
    'The candidate the incoming resume was ultimately attached to. NULL when the upload was rejected and no candidate resulted.';

COMMENT ON COLUMN duplicate_tracking.matched_candidate_id IS
    'The pre-existing candidate that was matched. For RESUME_APPENDED this is the same value as candidate_id - the new file was attributed to the person it matched.';

COMMENT ON COLUMN duplicate_tracking.matched_embedding_id IS
    'The specific chunk whose vector was similar. Populated only for SEMANTIC_MATCH.';

COMMENT ON COLUMN duplicate_tracking.duplicate_type IS
    'EXACT_FILE_MATCH (file hash, certain) / EMAIL_MATCH / PHONE_MATCH (strong identity signals) / SEMANTIC_MATCH (vector similarity, weak - never auto-merged on this project).';

COMMENT ON COLUMN duplicate_tracking.duplicate_confidence IS
    '0.00 to 1.00. Exact matches record 1.00. Mandatory for SEMANTIC_MATCH.';

COMMENT ON COLUMN duplicate_tracking.action_taken IS
    'What the system actually did. MANUAL_REVIEW_REQUIRED is reserved for a future review workflow and is not produced by the current POC rules.';

COMMENT ON COLUMN duplicate_tracking.detection_details IS
    'Evidence object describing exactly what matched, for example {"matched_on":"email","value":"ravi.kumar@gmail.com"}.';

COMMENT ON COLUMN duplicate_tracking.old_raw_profile_json IS
    'The candidate complete profile BEFORE this event modified it. This is the undo button - the only way to restore a profile after an incorrect merge. Never leave it empty on a PROFILE_UPDATED row.';

COMMENT ON COLUMN duplicate_tracking.new_raw_profile_json IS
    'The candidate profile AFTER this event. Paired with old_raw_profile_json to show exactly what changed.';


-- ============================================================================
--  END OF FILE : duplicate_tracking.sql
--
--  ALL FOUR MODULE 1 TABLES ARE NOW DEFINED:
--      1. candidates            - the PERSON
--      2. resumes               - the FILES
--      3. candidate_embeddings  - the MEANING (semantic search)
--      4. duplicate_tracking    - the DIARY   (audit only)
-- ============================================================================
