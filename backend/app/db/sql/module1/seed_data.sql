-- ============================================================================
--  HR HIRING ASSISTANT - POC
--  Module 1 : Resume Repository & Ingestion
--
--  FILE       : seed_data.sql
--  RUN ORDER  : 5 - AFTER all four table files
--  OWNER      : Monish
--
--  WHAT THIS IS
--    Hand-written test data so the tables are not empty. Lets you run real
--    queries TODAY, weeks before the upload and AI code exists, and lets
--    Module 2 start building against real rows instead of waiting.
--
--  WHAT IT CREATES
--     3 candidates   - a Java dev, a Python/ML dev, and a fresher
--     6 resumes      - including a 2-version history, a pending upload
--                      with candidate_id NULL, and a FAILED one
--     4 vectors      - one live row per candidate + Ravi's deactivated v1
--     2 diary rows   - an EMAIL_MATCH merge and a rejected duplicate file
--
--  IMPORTANT - THE VECTORS ARE FAKE
--    A real embedding needs 768 numbers produced by nomic-embed-text.
--    This file generates deterministic fake vectors instead, so that:
--       - every query, JOIN and index WILL run correctly
--       - the SIMILARITY RESULTS ARE MEANINGLESS
--    Use this to test SQL. Do not use it to judge search quality.
--    Real search testing needs Phase 5 (real embeddings).
--
--  SAFE TO RE-RUN
--    Fixed integer ids plus a cleanup block at the top mean running this
--    file twice replaces the seed data rather than failing on constraints.
--
--  TO REMOVE ALL SEED DATA
--    Run just the CLEANUP section below.
--
--  REVISION 2026-08-26 (Monish)
--    candidate_embeddings is now ONE row per candidate: profile_metadata
--    (JSONB) + embedding_text (compact text) + embedding (vector), with
--    content_hash = SHA-256 of the text. 4 rows replace the old 15 chunks.
--    Ravi's candidates row now reflects his version-2 resume (Infosys, Lead,
--    9.5 years) so the live vector, the diary and the profile agree.
--  REVISION 2026-08-25 (Monish)
--    Rewritten for the simplified schema: integer ids instead of UUIDs;
--    no summary / storage_backend / retry_count / uploaded_by /
--    extraction_started_at / chunk_index / chunk_type / token_count.
--    Section names that used to live in chunk_type are now shown inside
--    chunk_metadata. A RESET THE ID COUNTERS block was added (see there).
--
--  THE IDS USED BELOW
--    candidates  1 = Ravi Kumar     2 = Priya Sharma     3 = Arjun Nair
--    resumes     1 = Ravi v1        2 = Ravi v2          3 = Priya
--                4 = Arjun          5 = still processing 6 = failed
--    diary       1 = Ravi's email match   2 = rejected duplicate file
--    embeddings  auto-numbered by the database
-- ============================================================================


-- ============================================================================
--  CLEANUP  (also the uninstall script - run this section alone to wipe seed)
-- ============================================================================

--  Deleting candidates cascades to their resumes, embeddings and diary rows.
DELETE FROM candidates WHERE candidate_id IN (
    1,   -- Ravi Kumar
    2,   -- Priya Sharma
    3    -- Arjun Nair
);

--  These two resumes have no candidate, so they are not cascaded.
DELETE FROM resumes WHERE resume_id IN (
    5,   -- still processing
    6    -- failed
);

--  Any diary row not attached to a resume (rejected duplicate uploads).
DELETE FROM duplicate_tracking
WHERE duplicate_id = 2;


-- ============================================================================
--  HELPER : deterministic fake 768-dimension vector
--
--  Real vectors come from nomic-embed-text. This produces a repeatable
--  768-number pattern from a seed integer so the column can be populated.
--  Same seed always gives the same vector, so results are stable.
--  Dropped again at the end of this file.
-- ============================================================================
CREATE OR REPLACE FUNCTION seed_fake_embedding(seed INT)
RETURNS vector
LANGUAGE sql IMMUTABLE
AS $$
    SELECT ('[' || string_agg(
                round(sin(seed * 0.7 + i * 0.13)::numeric, 6)::text,
                ',' ORDER BY i
            ) || ']')::vector
    FROM generate_series(1, 768) AS i;
$$;


-- ============================================================================
--  1. CANDIDATES  (3 people)
-- ============================================================================

-- ----------------------------------------------------------------------------
--  Ravi Kumar - lead Java developer, 9.5 years (as of his version-2 resume;
--  his version-1 values are in the diary's old_raw_profile_json).
--  Used to demonstrate resume versioning and duplicate detection.
-- ----------------------------------------------------------------------------
INSERT INTO candidates (
    candidate_id, name, email, phone,
    current_location, current_job_title, current_company, experience_years,
    skills, education, experience, certifications, linkedin_url,
    extraction_confidence, raw_profile_json, is_active
) VALUES (
    1,
    'Ravi Kumar',
    'ravi.kumar@gmail.com',      -- lowercase: ck_candidates_email_lowercase
    '9876543210',                -- 10 digits: ck_candidates_phone_digits
    'Chennai, Tamil Nadu',
    'Lead Software Engineer',
    'Infosys',
    9.50,
    '["Java","Python","SQL","Spring Boot","Kafka","Hibernate","MySQL","PostgreSQL","Redis","Docker","Kubernetes","Terraform","Jenkins","Git","AWS"]'::jsonb,
    '[{"degree":"B.E. Computer Science and Engineering","institution":"Anna University","year":"2017","cgpa":"8.4/10"}]'::jsonb,
    '[{"company":"Infosys","role":"Lead Software Engineer","from":"2025-01","to":"present"},
      {"company":"Tata Consultancy Services","role":"Senior Software Engineer","from":"2021-06","to":"2024-12"},
      {"company":"Zoho Corporation","role":"Software Engineer","from":"2018-07","to":"2021-05"},
      {"company":"Aspire Systems","role":"Junior Developer","from":"2017-08","to":"2018-06"}]'::jsonb,
    '["AWS Certified Developer - Associate (2022)","Oracle Certified Professional Java SE 11 (2020)"]'::jsonb,
    'https://linkedin.com/in/ravikumar-dev',
    0.94,
    -- raw_profile_json holds fields that have NO column of their own.
    -- summary, notice_period and languages below prove why this column exists.
    '{"name":"Ravi Kumar","email":"ravi.kumar@gmail.com","summary":"Backend engineer with 9+ years building scalable microservices for banking and retail clients.","notice_period":"30 days","languages":["English","Tamil","Hindi"],"awards":["Star Performer 2023"]}'::jsonb,
    TRUE
);

-- ----------------------------------------------------------------------------
--  Priya Sharma - Python / machine learning, 5 years.
--  Different skill set, so skill filters have something to separate.
-- ----------------------------------------------------------------------------
INSERT INTO candidates (
    candidate_id, name, email, phone,
    current_location, current_job_title, current_company, experience_years,
    skills, education, experience, certifications, linkedin_url,
    extraction_confidence, raw_profile_json, is_active
) VALUES (
    2,
    'Priya Sharma',
    'priya.sharma@outlook.com',
    '9123456780',
    'Bengaluru, Karnataka',
    'Machine Learning Engineer',
    'Flipkart',
    5.00,
    '["Python","PyTorch","TensorFlow","scikit-learn","Pandas","SQL","Docker","AWS","Airflow","FastAPI"]'::jsonb,
    '[{"degree":"M.Tech Data Science","institution":"IIT Madras","year":"2021"},
      {"degree":"B.Tech Information Technology","institution":"VIT Vellore","year":"2019"}]'::jsonb,
    '[{"company":"Flipkart","role":"Machine Learning Engineer","from":"2022-03","to":"present"},
      {"company":"Mu Sigma","role":"Data Scientist","from":"2021-06","to":"2022-02"}]'::jsonb,
    '["AWS Certified Machine Learning - Specialty (2023)"]'::jsonb,
    'https://linkedin.com/in/priyasharma-ml',
    0.91,
    '{"name":"Priya Sharma","notice_period":"30 days","publications":2}'::jsonb,
    TRUE
);

-- ----------------------------------------------------------------------------
--  Arjun Nair - fresher, 0.5 years.
--  Tests the low end of experience_years and a profile with no real
--  work history, so the Experience line is legitimately absent from his
--  embedding_text.
-- ----------------------------------------------------------------------------
INSERT INTO candidates (
    candidate_id, name, email, phone,
    current_location, current_job_title, current_company, experience_years,
    skills, education, experience, certifications, linkedin_url,
    extraction_confidence, raw_profile_json, is_active
) VALUES (
    3,
    'Arjun Nair',
    'arjun.nair99@gmail.com',
    '9445566778',
    'Kochi, Kerala',
    'Junior Developer',
    'Trainee',
    0.50,
    '["JavaScript","React","HTML","CSS","Node.js","Git","MongoDB"]'::jsonb,
    '[{"degree":"B.Tech Computer Science","institution":"Cochin University","year":"2025","cgpa":"7.9/10"}]'::jsonb,
    '[]'::jsonb,          -- empty array, NOT null - see ck_candidates_experience_is_array
    '[]'::jsonb,
    NULL,                 -- no LinkedIn found: nullable is correct here
    0.68,                 -- lower confidence: sparse resume, harder to read
    '{"name":"Arjun Nair","internship":"6 months at a local startup","notice_period":"immediate"}'::jsonb,
    TRUE
);


-- ============================================================================
--  2. RESUMES  (6 files)
-- ============================================================================

-- ----------------------------------------------------------------------------
--  Ravi, version 1 - his ORIGINAL resume. is_latest = FALSE (superseded).
-- ----------------------------------------------------------------------------
INSERT INTO resumes (
    resume_id, candidate_id, resume_version,
    file_name, file_path, file_type, file_size_bytes, file_hash,
    processing_status, extracted_text, is_latest,
    processed_at, created_at
) VALUES (
    1,
    1,
    1,
    'ravi_kumar_resume.pdf',
    '/uploads/2026/08/ravi_kumar_resume.pdf',
    'pdf', 245680,
    encode(sha256('seed-ravi-v1'::bytea), 'hex'),
    'COMPLETED',
    'RAVI KUMAR Senior Software Engineer Chennai Tamil Nadu ravi.kumar@gmail.com Java Spring Boot MySQL Docker Kubernetes AWS 8 years TCS Zoho Aspire Systems B.E Computer Science Anna University',
    FALSE,                                    -- superseded by version 2
    '2026-08-24 17:31:03+05:30',
    '2026-08-24 17:30:00+05:30'
);

-- ----------------------------------------------------------------------------
--  Ravi, version 2 - uploaded 4 months later. is_latest = TRUE.
--  Only ONE row per candidate may have is_latest = TRUE.
--  Enforced by the partial unique index ux_resumes_one_latest.
-- ----------------------------------------------------------------------------
INSERT INTO resumes (
    resume_id, candidate_id, resume_version,
    file_name, file_path, file_type, file_size_bytes, file_hash,
    processing_status, extracted_text, is_latest,
    processed_at, created_at
) VALUES (
    2,
    1,
    2,
    'ravi_kumar_updated_2026.pdf',
    '/uploads/2026/12/ravi_kumar_updated_2026.pdf',
    'pdf', 251044,
    encode(sha256('seed-ravi-v2'::bytea), 'hex'),
    'COMPLETED',
    'RAVI KUMAR Lead Software Engineer Chennai ravi.kumar@gmail.com Java Spring Boot Kafka Docker Kubernetes AWS Terraform 9 years Infosys TCS Zoho B.E Computer Science Anna University',
    TRUE,                                     -- the current resume
    '2026-12-10 11:21:10+05:30',
    '2026-12-10 11:20:00+05:30'
);

-- ----------------------------------------------------------------------------
--  Priya - single resume.
-- ----------------------------------------------------------------------------
INSERT INTO resumes (
    resume_id, candidate_id, resume_version,
    file_name, file_path, file_type, file_size_bytes, file_hash,
    processing_status, extracted_text, is_latest,
    processed_at, created_at
) VALUES (
    3,
    2,
    1,
    'priya_sharma_cv.docx',
    '/uploads/2026/08/priya_sharma_cv.docx',
    'docx', 132400,
    encode(sha256('seed-priya-v1'::bytea), 'hex'),
    'COMPLETED',
    'PRIYA SHARMA Machine Learning Engineer Bengaluru priya.sharma@outlook.com Python PyTorch TensorFlow scikit-learn Airflow FastAPI Docker AWS Flipkart Mu Sigma M.Tech Data Science IIT Madras',
    TRUE,
    '2026-08-25 09:16:20+05:30',
    '2026-08-25 09:15:00+05:30'
);

-- ----------------------------------------------------------------------------
--  Arjun - single resume, a plain text file.
-- ----------------------------------------------------------------------------
INSERT INTO resumes (
    resume_id, candidate_id, resume_version,
    file_name, file_path, file_type, file_size_bytes, file_hash,
    processing_status, extracted_text, is_latest,
    processed_at, created_at
) VALUES (
    4,
    3,
    1,
    'arjun_nair_resume.txt',
    '/uploads/2026/08/arjun_nair_resume.txt',
    'txt', 4820,
    encode(sha256('seed-arjun-v1'::bytea), 'hex'),
    'COMPLETED',
    'ARJUN NAIR Junior Developer Kochi Kerala arjun.nair99@gmail.com JavaScript React HTML CSS Node.js MongoDB Git B.Tech Computer Science Cochin University 2025',
    TRUE,
    '2026-08-25 14:02:44+05:30',
    '2026-08-25 14:02:00+05:30'
);

-- ----------------------------------------------------------------------------
--  A file that is STILL BEING PROCESSED.
--
--  THIS IS THE IMPORTANT ROW. candidate_id and resume_version are both NULL
--  because the AI has not run yet - we do not know whose resume this is.
--  This is exactly the state every upload begins in. If candidate_id had
--  been declared NOT NULL, this row would be impossible and Module 1 could
--  never accept an upload at all.
-- ----------------------------------------------------------------------------
INSERT INTO resumes (
    resume_id, candidate_id, resume_version,
    file_name, file_path, file_type, file_size_bytes, file_hash,
    processing_status, extracted_text, is_latest, created_at
) VALUES (
    5,
    NULL,                                     -- unknown: AI has not run
    NULL,                                     -- unknown: set with candidate_id
    'unknown_candidate_2026.pdf',
    '/uploads/2026/08/unknown_candidate_2026.pdf',
    'pdf', 198220,
    encode(sha256('seed-pending'::bytea), 'hex'),
    'PROCESSING',
    NULL,                                     -- text not extracted yet
    FALSE,                                    -- cannot be latest without a candidate
    now()
);

-- ----------------------------------------------------------------------------
--  A file that FAILED.
--  ck_resumes_failed_has_reason forces failure_reason to be present, so a
--  mystery failure is impossible. There are no automatic retries - this row
--  stays FAILED until HR uploads the file again.
-- ----------------------------------------------------------------------------
INSERT INTO resumes (
    resume_id, candidate_id, resume_version,
    file_name, file_path, file_type, file_size_bytes, file_hash,
    processing_status, failure_reason, is_latest, processed_at, created_at
) VALUES (
    6,
    NULL, NULL,
    'corrupt_scan.pdf',
    '/uploads/2026/08/corrupt_scan.pdf',
    'pdf', 890112,
    encode(sha256('seed-failed'::bytea), 'hex'),
    'FAILED',
    'PDF is password protected - no text could be extracted',
    FALSE,
    now(),
    now()
);


-- ============================================================================
--  3. CANDIDATE_EMBEDDINGS  (4 rows - one vector per resume version)
--
--  ONE row per candidate is live (is_active = TRUE). Each row holds the
--  profile as JSONB (profile_metadata), that JSON rendered as compact text
--  (embedding_text), and the vector built from the text (embedding).
--     JSONB  = the information Module 2 hands to the LLM.
--     VECTOR = what search ranks with.
--
--  REMINDER: these vectors are FAKE. Queries will run; results are noise.
--
--  content_hash is computed exactly the way the application does it:
--  SHA-256 of embedding_text. The INSERT ... SELECT shape lets the same text
--  feed both columns without being typed twice. embedding_id is left to the
--  database (BIGSERIAL).
-- ============================================================================

-- ----------------------------------------------------------------------------
--  Ravi version 1 - is_active = FALSE. Superseded when version 2 changed his
--  profile (new company, more skills). Kept rather than deleted so a bad
--  re-parse of version 2 can be rolled back. The partial HNSW index ignores
--  it, so it never pollutes a search.
-- ----------------------------------------------------------------------------
INSERT INTO candidate_embeddings (
    candidate_id, resume_id, profile_metadata, embedding_text,
    embedding, model_name, model_version, content_hash, is_active
)
SELECT 1, 1,
       '{"name":"Ravi Kumar","email":"ravi.kumar@gmail.com","phone":"9876543210","current_location":"Chennai, Tamil Nadu","current_job_title":"Senior Software Engineer","current_company":"Tata Consultancy Services","experience_years":8.5,"skills":["Java","Python","SQL","Spring Boot","Hibernate","JUnit","MySQL","PostgreSQL","Redis","Docker","Kubernetes","Jenkins","Git","AWS"],"education":[{"degree":"B.E. Computer Science and Engineering","institution":"Anna University","year":"2017","cgpa":"8.4/10"}],"experience":[{"company":"Tata Consultancy Services","role":"Senior Software Engineer","from":"2021-06","to":"present"},{"company":"Zoho Corporation","role":"Software Engineer","from":"2018-07","to":"2021-05"},{"company":"Aspire Systems","role":"Junior Developer","from":"2017-08","to":"2018-06"}],"certifications":["AWS Certified Developer - Associate (2022)","Oracle Certified Professional Java SE 11 (2020)"],"linkedin_url":"https://linkedin.com/in/ravikumar-dev","summary":"Backend engineer with 8+ years building scalable microservices for banking and retail clients."}'::jsonb,
       t, seed_fake_embedding(1), 'nomic-embed-text', 'v1.5',
       encode(sha256(convert_to(t, 'UTF8')), 'hex'), FALSE
FROM (SELECT
         E'Ravi Kumar | Senior Software Engineer | Tata Consultancy Services | Chennai, Tamil Nadu | 8.5 years experience\n'
      || E'Summary: Backend engineer with 8+ years building scalable microservices for banking and retail clients.\n'
      || E'Skills: Java, Python, SQL, Spring Boot, Hibernate, JUnit, MySQL, PostgreSQL, Redis, Docker, Kubernetes, Jenkins, Git, AWS\n'
      || E'Experience: Senior Software Engineer at Tata Consultancy Services (2021-06 to present); Software Engineer at Zoho Corporation (2018-07 to 2021-05); Junior Developer at Aspire Systems (2017-08 to 2018-06)\n'
      || E'Education: B.E. Computer Science and Engineering, Anna University, 2017\n'
      || E'Certifications: AWS Certified Developer - Associate (2022); Oracle Certified Professional Java SE 11 (2020)'
      AS t) AS src;

-- ----------------------------------------------------------------------------
--  Ravi version 2 - is_active = TRUE. This is the row search uses for Ravi.
--  profile_metadata matches his candidates row (Infosys, Lead, 9.5 years).
-- ----------------------------------------------------------------------------
INSERT INTO candidate_embeddings (
    candidate_id, resume_id, profile_metadata, embedding_text,
    embedding, model_name, model_version, content_hash, is_active
)
SELECT 1, 2,
       '{"name":"Ravi Kumar","email":"ravi.kumar@gmail.com","phone":"9876543210","current_location":"Chennai, Tamil Nadu","current_job_title":"Lead Software Engineer","current_company":"Infosys","experience_years":9.5,"skills":["Java","Python","SQL","Spring Boot","Kafka","Hibernate","MySQL","PostgreSQL","Redis","Docker","Kubernetes","Terraform","Jenkins","Git","AWS"],"education":[{"degree":"B.E. Computer Science and Engineering","institution":"Anna University","year":"2017","cgpa":"8.4/10"}],"experience":[{"company":"Infosys","role":"Lead Software Engineer","from":"2025-01","to":"present"},{"company":"Tata Consultancy Services","role":"Senior Software Engineer","from":"2021-06","to":"2024-12"},{"company":"Zoho Corporation","role":"Software Engineer","from":"2018-07","to":"2021-05"},{"company":"Aspire Systems","role":"Junior Developer","from":"2017-08","to":"2018-06"}],"certifications":["AWS Certified Developer - Associate (2022)","Oracle Certified Professional Java SE 11 (2020)"],"linkedin_url":"https://linkedin.com/in/ravikumar-dev","summary":"Backend engineer with 9+ years building scalable microservices for banking and retail clients."}'::jsonb,
       t, seed_fake_embedding(11), 'nomic-embed-text', 'v1.5',
       encode(sha256(convert_to(t, 'UTF8')), 'hex'), TRUE
FROM (SELECT
         E'Ravi Kumar | Lead Software Engineer | Infosys | Chennai, Tamil Nadu | 9.5 years experience\n'
      || E'Summary: Backend engineer with 9+ years building scalable microservices for banking and retail clients.\n'
      || E'Skills: Java, Python, SQL, Spring Boot, Kafka, Hibernate, MySQL, PostgreSQL, Redis, Docker, Kubernetes, Terraform, Jenkins, Git, AWS\n'
      || E'Experience: Lead Software Engineer at Infosys (2025-01 to present); Senior Software Engineer at Tata Consultancy Services (2021-06 to 2024-12); Software Engineer at Zoho Corporation (2018-07 to 2021-05); Junior Developer at Aspire Systems (2017-08 to 2018-06)\n'
      || E'Education: B.E. Computer Science and Engineering, Anna University, 2017\n'
      || E'Certifications: AWS Certified Developer - Associate (2022); Oracle Certified Professional Java SE 11 (2020)'
      AS t) AS src;

-- ----------------------------------------------------------------------------
--  Priya - one live row. No summary in her raw_profile_json, so the JSON
--  carries "summary": null and the text simply has no Summary line.
-- ----------------------------------------------------------------------------
INSERT INTO candidate_embeddings (
    candidate_id, resume_id, profile_metadata, embedding_text,
    embedding, model_name, model_version, content_hash, is_active
)
SELECT 2, 3,
       '{"name":"Priya Sharma","email":"priya.sharma@outlook.com","phone":"9123456780","current_location":"Bengaluru, Karnataka","current_job_title":"Machine Learning Engineer","current_company":"Flipkart","experience_years":5.0,"skills":["Python","PyTorch","TensorFlow","scikit-learn","Pandas","SQL","Docker","AWS","Airflow","FastAPI"],"education":[{"degree":"M.Tech Data Science","institution":"IIT Madras","year":"2021"},{"degree":"B.Tech Information Technology","institution":"VIT Vellore","year":"2019"}],"experience":[{"company":"Flipkart","role":"Machine Learning Engineer","from":"2022-03","to":"present"},{"company":"Mu Sigma","role":"Data Scientist","from":"2021-06","to":"2022-02"}],"certifications":["AWS Certified Machine Learning - Specialty (2023)"],"linkedin_url":"https://linkedin.com/in/priyasharma-ml","summary":null}'::jsonb,
       t, seed_fake_embedding(21), 'nomic-embed-text', 'v1.5',
       encode(sha256(convert_to(t, 'UTF8')), 'hex'), TRUE
FROM (SELECT
         E'Priya Sharma | Machine Learning Engineer | Flipkart | Bengaluru, Karnataka | 5 years experience\n'
      || E'Skills: Python, PyTorch, TensorFlow, scikit-learn, Pandas, SQL, Docker, AWS, Airflow, FastAPI\n'
      || E'Experience: Machine Learning Engineer at Flipkart (2022-03 to present); Data Scientist at Mu Sigma (2021-06 to 2022-02)\n'
      || E'Education: M.Tech Data Science, IIT Madras, 2021; B.Tech Information Technology, VIT Vellore, 2019\n'
      || E'Certifications: AWS Certified Machine Learning - Specialty (2023)'
      AS t) AS src;

-- ----------------------------------------------------------------------------
--  Arjun - one live row. A fresher: empty experience and certifications, no
--  LinkedIn. Shows that missing pieces simply leave lines out of the text.
--  Resumes 5 (still processing) and 6 (failed) have no row - a vector is only
--  ever built once a candidate exists.
-- ----------------------------------------------------------------------------
INSERT INTO candidate_embeddings (
    candidate_id, resume_id, profile_metadata, embedding_text,
    embedding, model_name, model_version, content_hash, is_active
)
SELECT 3, 4,
       '{"name":"Arjun Nair","email":"arjun.nair99@gmail.com","phone":"9445566778","current_location":"Kochi, Kerala","current_job_title":"Junior Developer","current_company":"Trainee","experience_years":0.5,"skills":["JavaScript","React","HTML","CSS","Node.js","Git","MongoDB"],"education":[{"degree":"B.Tech Computer Science","institution":"Cochin University","year":"2025","cgpa":"7.9/10"}],"experience":[],"certifications":[],"linkedin_url":null,"summary":null}'::jsonb,
       t, seed_fake_embedding(31), 'nomic-embed-text', 'v1.5',
       encode(sha256(convert_to(t, 'UTF8')), 'hex'), TRUE
FROM (SELECT
         E'Arjun Nair | Junior Developer | Trainee | Kochi, Kerala | 0.5 years experience\n'
      || E'Skills: JavaScript, React, HTML, CSS, Node.js, Git, MongoDB\n'
      || E'Education: B.Tech Computer Science, Cochin University, 2025'
      AS t) AS src;


-- ============================================================================
--  4. DUPLICATE_TRACKING  (2 diary entries)
-- ============================================================================

-- ----------------------------------------------------------------------------
--  Entry 1 : Ravi uploaded an updated resume in December.
--  Email matched an existing candidate, so instead of creating a second
--  "Ravi Kumar" the system appended a new resume version and refreshed
--  his profile.
--
--  Note candidate_id and matched_candidate_id are the SAME value. That is
--  correct: the incoming file was attributed to the very person it matched.
--
--  old_raw_profile_json is the undo button. If this merge had been wrong,
--  it is the only way to restore his original profile.
-- ----------------------------------------------------------------------------
INSERT INTO duplicate_tracking (
    duplicate_id, resume_id, candidate_id,
    matched_candidate_id, matched_resume_id, matched_embedding_id,
    duplicate_type, duplicate_confidence, action_taken,
    detection_details, old_raw_profile_json, new_raw_profile_json, created_at
) VALUES (
    1,
    2,                                        -- the NEW file (Ravi v2)
    1,                                        -- who it was attributed to
    1,                                        -- the EXISTING person matched
    1,                                        -- the EXISTING file (Ravi v1)
    NULL,                                     -- not a vector match
    'EMAIL_MATCH',
    1.00,                                     -- email is exact, so full confidence
    'RESUME_APPENDED',
    '{"matched_on":"email","value":"ravi.kumar@gmail.com"}'::jsonb,
    '{"experience_years":8.5,"current_company":"Tata Consultancy Services","current_job_title":"Senior Software Engineer"}'::jsonb,
    '{"experience_years":9.5,"current_company":"Infosys","current_job_title":"Lead Software Engineer"}'::jsonb,
    '2026-12-10 11:21:11+05:30'
);

-- ----------------------------------------------------------------------------
--  Entry 2 : HR accidentally re-uploaded a file that was already in the system.
--
--  resume_id is NULL here. The duplicate was caught from the file hash
--  BEFORE any resumes row was created - and ux_resumes_file_hash would have
--  refused the insert anyway. The file name and hash are recorded in
--  detection_details instead, so the rejection is still auditable.
-- ----------------------------------------------------------------------------
INSERT INTO duplicate_tracking (
    duplicate_id, resume_id, candidate_id,
    matched_candidate_id, matched_resume_id, matched_embedding_id,
    duplicate_type, duplicate_confidence, action_taken,
    detection_details, old_raw_profile_json, new_raw_profile_json, created_at
) VALUES (
    2,
    NULL,                                     -- never stored: rejected on arrival
    NULL,                                     -- no candidate resulted
    1,                                        -- it belonged to Ravi
    2,                                        -- it was byte-identical to Ravi v2
    NULL,
    'EXACT_FILE_MATCH',
    1.00,
    'DUPLICATE_REJECTED',
    ('{"matched_on":"file_hash","file_name":"ravi_kumar_updated_2026.pdf","value":"'
      || encode(sha256('seed-ravi-v2'::bytea),'hex') || '"}')::jsonb,
    NULL,                                     -- nothing was changed
    NULL,
    '2026-12-11 09:05:00+05:30'
);


-- ============================================================================
--  RESET THE ID COUNTERS
--
--  The rows above were inserted with hand-picked ids (1, 2, 3 ...). A
--  BIGSERIAL column keeps its own counter and does not notice that. Without
--  this block, the first REAL upload would ask the counter for "the next id",
--  get 1, and collide with Ravi. This moves each counter past the seed rows.
--
--  candidate_embeddings is not listed: its ids were generated by the
--  counter itself, so it is already correct.
-- ============================================================================
SELECT setval(pg_get_serial_sequence('candidates', 'candidate_id'),
              (SELECT GREATEST(max(candidate_id), 1) FROM candidates));

SELECT setval(pg_get_serial_sequence('resumes', 'resume_id'),
              (SELECT GREATEST(max(resume_id), 1) FROM resumes));

SELECT setval(pg_get_serial_sequence('duplicate_tracking', 'duplicate_id'),
              (SELECT GREATEST(max(duplicate_id), 1) FROM duplicate_tracking));


-- ============================================================================
--  CLEAN UP THE HELPER FUNCTION
--  Real embeddings come from the application, never from SQL.
-- ============================================================================
DROP FUNCTION IF EXISTS seed_fake_embedding(INT);


-- ============================================================================
--  VERIFY  -  run these after seeding
-- ============================================================================

--  Row counts. Expect: 3 candidates, 6 resumes, 4 embeddings, 2 diary rows.
--     SELECT 'candidates' AS t, count(*) FROM candidates
--     UNION ALL SELECT 'resumes',              count(*) FROM resumes
--     UNION ALL SELECT 'candidate_embeddings', count(*) FROM candidate_embeddings
--     UNION ALL SELECT 'duplicate_tracking',   count(*) FROM duplicate_tracking;

--  Ravi has 2 resumes, exactly one flagged latest.
--     SELECT resume_version, file_name, is_latest, processing_status
--     FROM resumes
--     WHERE candidate_id = 1
--     ORDER BY resume_version;

--  Skill filter using the GIN index.  Expect: Ravi only.
--     SELECT name, current_job_title, experience_years
--     FROM candidates
--     WHERE skills @> '["Java"]' AND is_active;

--  Certification filter.  Expect: Ravi and Priya.
--     SELECT name, certifications FROM candidates
--     WHERE jsonb_array_length(certifications) > 0;

--  Only ACTIVE rows are searchable.  Expect: 3 active, 1 inactive.
--     SELECT is_active, count(*) FROM candidate_embeddings GROUP BY is_active;

--  The JSONB profile next to its text, for the live rows. The skills come
--  straight out of profile_metadata - no join to candidates needed.
--     SELECT candidate_id, profile_metadata->>'current_company' AS company,
--            profile_metadata->'skills' AS skills, left(embedding_text, 60) AS text
--     FROM candidate_embeddings WHERE is_active ORDER BY candidate_id;

--  The hash really is SHA-256 of the text (what lets a re-upload skip the
--  embedding call). Expect: hash_ok = true on every row.
--     SELECT candidate_id, resume_id,
--            content_hash = encode(sha256(convert_to(embedding_text,'UTF8')),'hex') AS hash_ok
--     FROM candidate_embeddings;

--  A field with NO column of its own, read straight out of raw_profile_json.
--     SELECT name, raw_profile_json->>'summary' AS summary,
--            raw_profile_json->>'notice_period' AS notice_period
--     FROM candidates;

--  Uploads still in flight - the ones with no candidate yet.
--     SELECT file_name, processing_status, candidate_id, failure_reason
--     FROM resumes WHERE candidate_id IS NULL;

--  The audit diary.
--     SELECT duplicate_type, action_taken, duplicate_confidence, detection_details
--     FROM duplicate_tracking ORDER BY created_at;

--  The id counters are past the seed rows. Expect: 3, 6, 2.
--     SELECT last_value FROM candidates_candidate_id_seq
--     UNION ALL SELECT last_value FROM resumes_resume_id_seq
--     UNION ALL SELECT last_value FROM duplicate_tracking_duplicate_id_seq;


-- ============================================================================
--  PROVE THE GUARD RAILS WORK
--  Every statement below MUST fail. Uncomment one at a time and run it.
--  Seeing the named constraint in the error message is the proof.
-- ============================================================================

--  1. phone not normalised   -> ck_candidates_phone_digits
--     INSERT INTO candidates (name, phone) VALUES ('Test One', '+91 98765 43210');

--  2. email not lowercase    -> ck_candidates_email_lowercase
--     INSERT INTO candidates (name, email) VALUES ('Test Two', 'Test@Gmail.com');

--  3. duplicate email        -> ux_candidates_email
--     INSERT INTO candidates (name, email) VALUES ('Fake Ravi', 'ravi.kumar@gmail.com');

--  4. impossible experience  -> ck_candidates_experience_range
--     INSERT INTO candidates (name, experience_years) VALUES ('Test Four', 250);

--  5. skills as object not array -> ck_candidates_skills_is_array
--     INSERT INTO candidates (name, skills) VALUES ('Test Five', '{"Java":true}'::jsonb);

--  6. FAILED with no reason  -> ck_resumes_failed_has_reason
--     INSERT INTO resumes (file_name, file_path, file_type, file_size_bytes,
--                          file_hash, processing_status)
--     VALUES ('x.pdf','/tmp/x','pdf',100, repeat('a',64), 'FAILED');

--  7. a SECOND latest resume for Ravi -> ux_resumes_one_latest
--     INSERT INTO resumes (candidate_id, resume_version, file_name, file_path,
--                          file_type, file_size_bytes, file_hash, is_latest)
--     VALUES (1, 3, 'y.pdf','/tmp/y', 'pdf', 100, repeat('b',64), TRUE);

--  8. re-uploading a byte-identical file -> ux_resumes_file_hash
--     INSERT INTO resumes (file_name, file_path, file_type, file_size_bytes, file_hash)
--     VALUES ('copy.pdf','/tmp/copy','pdf', 245680,
--             encode(sha256('seed-ravi-v2'::bytea),'hex'));

--  9. a SECOND live vector for Ravi -> ux_emb_candidate_active
--     (reuses an existing vector because the fake-vector helper is gone)
--     INSERT INTO candidate_embeddings (candidate_id, resume_id, profile_metadata, embedding_text,
--                                       embedding, model_name, content_hash)
--     VALUES (1, 5, '{"name":"Ravi Kumar"}'::jsonb, 'Ravi Kumar',
--             (SELECT embedding FROM candidate_embeddings WHERE resume_id = 2),
--             'nomic-embed-text', encode(sha256('Ravi Kumar'::bytea),'hex'));

-- 10. a second vector for the SAME resume -> ux_emb_resume
--     (statement 9 with resume_id = 2 and an extra column is_active = FALSE)


-- ============================================================================
--  END OF FILE : seed_data.sql
-- ============================================================================
