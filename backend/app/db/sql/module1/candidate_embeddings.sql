-- ============================================================================
--  HR HIRING ASSISTANT - POC
--  Module 1 : Resume Repository & Ingestion
--
--  TABLE      : candidate_embeddings
--  RUN ORDER  : 3 of 4   (candidates -> resumes -> candidate_embeddings
--                         -> duplicate_tracking)
--  DATABASE   : PostgreSQL 16 + pgvector
--  OWNER      : Monish
--
--  WHAT IT HOLDS
--    ONE ROW = ONE CANDIDATE (the live row), holding three things:
--
--      profile_metadata  JSONB        the candidate's details (skills, education,
--                                     experience, company, phone ...) in ONE
--                                     flexible column. The SOURCE OF TRUTH that
--                                     Module 2 hands to the LLM.
--      embedding_text    TEXT         that JSON rendered as compact text - the
--                                     exact words the embedding model read.
--      embedding         VECTOR(768)  one vector of numbers capturing the
--                                     MEANING of that text. What search uses.
--
--    So:  JSONB = information.   VECTOR = retrieval.
--
--  HOW SEARCH USES IT
--    A job description is embedded with the same model, then:
--        ORDER BY embedding <=> :query_vector  LIMIT :top_k
--    gives the Top-K most similar candidates by cosine similarity. Only those
--    K rows (their profile_metadata) are sent to the LLM - never every resume.
--
--  WHY ONE ROW PER CANDIDATE, NOT ONE PER CHUNK
--    A resume profile is a few hundred tokens; nomic-embed-text reads 8,192.
--    Matching a whole job description against a whole person is the right
--    granularity, Top-K rows = Top-K people (no "best chunk per candidate"
--    sub-query), and the HNSW index is a third of the size.
--
--  DEPENDS ON
--    candidates.sql        (foreign key candidate_id)
--    resumes.sql           (foreign key resume_id)
--    set_updated_at()      (trigger function defined in candidates.sql)
--    CREATE EXTENSION vector  (done in candidates.sql)
--
--  CRITICAL - VECTOR DIMENSION
--    VECTOR(768) is tied to the embedding model 'nomic-embed-text', which
--    always outputs exactly 768 numbers (see EMBEDDING_MODEL in .env).
--    If the team ever changes the embedding model, this number changes AND
--    every existing vector in this table becomes meaningless. Every candidate
--    would need re-embedding. Do not change the model casually.
--
--  CRITICAL - COLUMN NAME
--    The JSONB column is called profile_metadata, NOT metadata.
--    'metadata' is a reserved attribute on SQLAlchemy declarative models and
--    will raise InvalidRequestError at import time.
--
--  REVISION 2026-08-26 (Monish)
--    One vector per candidate instead of 2-5 chunk rows (design review).
--    - chunk_text     -> embedding_text   (the whole profile as compact text)
--    - chunk_metadata -> profile_metadata (the whole profile as JSONB)
--    - content_hash is SHA-256 of embedding_text: same profile = same hash =
--      no re-embedding on re-upload (zero AI calls when nothing changed).
--    - Unique rules are now UNIQUE(resume_id) and UNIQUE(candidate_id) for
--      the active row. The old (resume_id, content_hash) rule and the
--      candidate / resume / content_hash lookup indexes are gone - the two
--      unique indexes already answer those lookups.
--  REVISION 2026-08-25 (Monish)
--    Integer ids; dropped chunk_index / chunk_type / token_count.
-- ============================================================================


-- ----------------------------------------------------------------------------
--  TABLE : candidate_embeddings
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS candidate_embeddings (

    -- ---- identity -----------------------------------------------------------
    embedding_id     BIGSERIAL     PRIMARY KEY,

    -- ---- links --------------------------------------------------------------
    --  Both NOT NULL: a vector is only ever created AFTER the candidate and
    --  the resume rows already exist.
    --  CASCADE: deleting a candidate or a resume removes its vector too.
    candidate_id     BIGINT        NOT NULL REFERENCES candidates(candidate_id)
                                   ON DELETE CASCADE,
    resume_id        BIGINT        NOT NULL REFERENCES resumes(resume_id)
                                   ON DELETE CASCADE,

    -- ---- the profile (JSONB = source of truth) ------------------------------
    --  Everything flexible about the person in ONE column:
    --    {"name":..., "current_job_title":..., "current_company":...,
    --     "experience_years":..., "skills":[...], "education":[...],
    --     "experience":[...], "certifications":[...], "phone":..., ...}
    --  This is a SNAPSHOT of the candidate at embedding time - it is what the
    --  vector was built from, and what Module 2 sends to the LLM for the
    --  Top-K candidates. New attributes go in here, never as new columns.
    --  NOT named "metadata" - that name is reserved by SQLAlchemy.
    profile_metadata JSONB         NOT NULL,

    -- ---- the text (what the model actually read) ----------------------------
    --  profile_metadata rendered as compact lines, e.g.
    --    Ravi Kumar | Lead Software Engineer | Infosys | Chennai | 9.5 years experience
    --    Skills: Java, Spring Boot, Kafka, ...
    --    Experience: Lead Software Engineer at Infosys (2025-01 to present); ...
    --  Kept because a vector is one-way: without this nobody can debug a
    --  search result or show HR WHY a candidate matched. Email / phone /
    --  LinkedIn are deliberately left OUT of the text: they are identity, not
    --  meaning, and only add noise to the vector. They stay in the JSONB.
    embedding_text   TEXT          NOT NULL,

    -- ---- the vector (VECTOR = retrieval) ------------------------------------
    --  768 numbers produced by nomic-embed-text from embedding_text.
    embedding        VECTOR(768)   NOT NULL,

    -- ---- AI traceability ----------------------------------------------------
    --  Vectors from different models are NOT comparable with each other.
    --  Recording the model is what lets you find stale rows after a switch.
    model_name       VARCHAR(100)  NOT NULL,
    model_version    VARCHAR(50),

    --  SHA-256 of embedding_text. On re-upload the app renders the new text,
    --  hashes it, and compares with the live row: same hash + same model =
    --  nothing changed = no embedding call, no new row.
    --  It is the hash of the TEXT, not the JSON, on purpose: Postgres re-orders
    --  JSONB keys, so a JSON hash differs between Python and SQL; and if the
    --  text format ever changes the vectors need rebuilding anyway - a text
    --  hash notices that, a JSON hash would not.
    content_hash     VARCHAR(64)   NOT NULL,

    -- ---- lifecycle ----------------------------------------------------------
    --  When resume v2 arrives with a changed profile, v1's row is set
    --  is_active = FALSE rather than deleted, so a bad re-parse can be
    --  rolled back. Exactly ONE active row per candidate (see
    --  ux_emb_candidate_active).
    is_active        BOOLEAN       NOT NULL DEFAULT TRUE,

    -- ---- timestamps ---------------------------------------------------------
    created_at       TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ   NOT NULL DEFAULT now(),

    -- ---- guard rails --------------------------------------------------------

    --  Embedding an empty string produces meaningless numbers that will
    --  pollute every search result. Refuse it at the door.
    CONSTRAINT ck_emb_text_not_blank
        CHECK (length(trim(embedding_text)) > 0),

    CONSTRAINT ck_emb_content_hash_format
        CHECK (content_hash ~ '^[0-9a-f]{64}$'),

    --  Never store a vector without recording which model produced it.
    CONSTRAINT ck_emb_model_name_not_blank
        CHECK (length(trim(model_name)) > 0),

    --  Always an object {...}, never an array or a bare string.
    CONSTRAINT ck_emb_metadata_is_object
        CHECK (jsonb_typeof(profile_metadata) = 'object')
);


-- ----------------------------------------------------------------------------
--  INDEXES
-- ----------------------------------------------------------------------------

--  UNIQUE : one resume version produces at most ONE vector.
--  (A resume that failed, or whose profile was unchanged, has none - fine.)
CREATE UNIQUE INDEX IF NOT EXISTS ux_emb_resume
    ON candidate_embeddings (resume_id);

--  UNIQUE : one LIVE vector per candidate. Partial (WHERE is_active) so the
--  deactivated history rows of older resume versions do not count.
--  Forgetting to deactivate the old row before inserting the new one raises
--  an error instead of silently leaving two. This index also serves the
--  "give me this candidate's live row" lookup, so no separate index is needed.
CREATE UNIQUE INDEX IF NOT EXISTS ux_emb_candidate_active
    ON candidate_embeddings (candidate_id)
    WHERE is_active;

--  THE SEARCH INDEX.
--
--  HNSW = Hierarchical Navigable Small World. It is what turns
--  "find the most similar meaning among 100,000 candidates" from a full scan
--  into a few milliseconds.
--
--  vector_cosine_ops = cosine distance, the correct measure for text
--  embeddings. Used by the <=> operator:
--        ORDER BY embedding <=> :query_vector
--  Smaller distance = more similar.
--
--  m = 16               : links per node. Higher = better recall, more memory.
--  ef_construction = 64 : effort at build time. Higher = better index, slower build.
--  These are the pgvector defaults and are correct for a POC.
--
--  PARTIAL (WHERE is_active) so superseded rows from old resume versions
--  are not searched and do not bloat the index. Your search queries MUST
--  include "WHERE is_active" for this index to be used.
--
--  PERFORMANCE NOTE: if you ever bulk-load thousands of rows, DROP this index
--  first, load, then recreate it. Building after loading is far faster.
CREATE INDEX IF NOT EXISTS ix_emb_hnsw
    ON candidate_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64)
    WHERE is_active;


-- ----------------------------------------------------------------------------
--  TRIGGER : keep updated_at honest
--  Reuses set_updated_at() defined in candidates.sql
-- ----------------------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_emb_updated_at ON candidate_embeddings;

CREATE TRIGGER trg_emb_updated_at
    BEFORE UPDATE ON candidate_embeddings
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();


-- ----------------------------------------------------------------------------
--  DOCUMENTATION
-- ----------------------------------------------------------------------------
COMMENT ON TABLE candidate_embeddings IS
    'One semantic vector per candidate (one active row each) plus the JSONB profile it was built from. Owned by Module 1, queried by Module 2 for Top-K candidate retrieval.';

COMMENT ON COLUMN candidate_embeddings.resume_id IS
    'The exact resume version this vector was generated from. When a newer resume changes the profile, the older row is set is_active = FALSE.';

COMMENT ON COLUMN candidate_embeddings.profile_metadata IS
    'The candidate profile as one JSONB object (skills, education, experience, company, phone, ...). Source of truth for what the vector represents; what Module 2 sends to the LLM. Deliberately NOT named "metadata" because that attribute name is reserved by SQLAlchemy declarative models.';

COMMENT ON COLUMN candidate_embeddings.embedding_text IS
    'profile_metadata rendered as compact text - the exact input the embedding model read. NEVER drop this column: a vector cannot be turned back into text, and this is what lets the UI show HR why a candidate matched.';

COMMENT ON COLUMN candidate_embeddings.embedding IS
    'VECTOR(768) produced by nomic-embed-text from embedding_text. The dimension is model-specific. Changing the embedding model invalidates every row in this table.';

COMMENT ON COLUMN candidate_embeddings.model_name IS
    'Embedding model that produced this vector. Vectors from different models are not comparable. Required for identifying stale rows after a model change.';

COMMENT ON COLUMN candidate_embeddings.content_hash IS
    'SHA-256 of embedding_text. Same hash and same model on re-upload means the profile did not change, so the embedding is not regenerated.';

COMMENT ON COLUMN candidate_embeddings.is_active IS
    'TRUE on exactly one row per candidate (ux_emb_candidate_active). FALSE means superseded by a newer resume version. Search queries must filter on is_active for the partial HNSW index to be used.';


-- ============================================================================
--  EXAMPLE SEARCH QUERY  (for reference - Module 2 will call this)
--
--    SELECT c.candidate_id,
--           c.name,
--           c.current_job_title,
--           e.profile_metadata,                              -- give THIS to the LLM
--           1 - (e.embedding <=> :query_vector) AS similarity
--    FROM   candidate_embeddings e
--    JOIN   candidates c ON c.candidate_id = e.candidate_id
--    WHERE  e.is_active
--      AND  c.is_active
--      AND  c.experience_years >= :min_experience
--    ORDER  BY e.embedding <=> :query_vector
--    LIMIT  :top_k;
--
--  <=>  is the pgvector cosine-distance operator. Smaller = more similar.
--  1 - distance gives a 0..1 similarity score that is nicer to display.
--  One row per candidate, so LIMIT :top_k really is the Top-K people.
-- ============================================================================


-- ============================================================================
--  END OF FILE : candidate_embeddings.sql
--  NEXT        : duplicate_tracking.sql
-- ============================================================================
