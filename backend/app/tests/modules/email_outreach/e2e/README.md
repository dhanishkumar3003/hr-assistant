# email_outreach E2E test suite

API-level Playwright tests for the `email_outreach` backend module. Read
[Discrepancy from the task's premise](#discrepancy-from-the-tasks-premise)
first — it explains why these are API tests, not browser tests.

## Running

```bash
cd backend/app/tests/modules/email_outreach/e2e
npm install
npx playwright install chromium
npm test               # full suite
npx playwright test tests/draft.spec.ts   # one file
npm run report          # open the HTML report from the last run
```

Requires the backend stack running (`docker compose up -d` from `infra/`)
and reachable at `http://localhost:8000`, and Postgres reachable at
`localhost:5432` (both already true if you're developing this repo
normally). `global-setup.ts` and `global-teardown.ts` **temporarily edit
the repo root `.env`** and restart the `backend` container twice per run
(see [Email provider handling](#email-provider-handling)) — this is
real infrastructure manipulation, not a mock scoped to the test process,
so don't run the suite against a shared/production Docker host.

## Discrepancy from the task's premise

The task assumed a browser UI exists for drafting/approving/rejecting/
sending emails and viewing candidate status/history. **It does not.**
The Next.js frontend (`frontend/src/app/`) has exactly three routes:
a static marketing landing page, `/login`, and the candidate-facing
voice-interview flow (`/interview/[token]`). There is no dashboard, no
candidate list, no draft/approve/send screens, no status/history view —
and `/login` redirects to `/dashboard` on success, which has no
corresponding page file at all. Nothing in `frontend/` calls any
`/email/*` route.

Per the task's own instruction ("If the implementation differs from the
documentation, report the discrepancy and test the actual implementation
while clearly documenting the difference"), these tests drive the real
HTTP API directly via Playwright's `request` fixture instead of a
browser. Every test still exercises the real running application (real
Postgres, real backend process, real LLM classifier, a mocked-at-the-
boundary email provider) — nothing here is a unit test or a mock of the
application itself.

## Test data strategy

Candidates only exist via the static JSON catalog
(`backend/app/tests/modules/email_outreach/testdata.json`,
`JsonCandidateSource`) — there's no API to create one. Each test that
needs a candidate gets one via the `candidateId` / `secondCandidateId`
fixtures (`tests/fixtures/email-outreach.fixture.ts`), which append a
uniquely-id'd entry (`E2E-<timestamp>-<random>`) to that file before the
test and remove it afterward. The file is bind-mounted into the backend
container, and `candidate_source.py::_load()` re-reads it on every call
(no caching), so edits take effect immediately with no restart. Tests
are fully independent — no shared candidate, no execution-order
dependency, and repeated runs (`npx playwright test` twice in a row)
are clean, verified during development of this suite.

## Email provider handling

The live backend is configured for `gmail_pubsub` (real Gmail API).
Sending a real email to an external candidate during automated tests
was explicitly disallowed by the task. Since Python-level mocking
(`unittest.mock.patch`, used by the existing pytest suite) isn't
reachable from an external Playwright process, `global-setup.ts`:

1. Starts a local mock Postal HTTP server (`tests/fixtures/mock-postal-server.ts`)
   as a detached child process, matching the exact request/response
   contract `services/postal_backend.py` expects.
2. Rewrites `.env`: `EMAIL_BACKEND=postal`,
   `POSTAL_API_URL=http://host.docker.internal:<port>/api/v1/send/message`.
3. Restarts the `backend` container (`docker compose up -d --force-recreate backend`)
   and waits for `/email/ping` to respond.

`global-teardown.ts` reverses all three steps, restoring the original
`.env` and restarting the container back onto `gmail_pubsub`. **No real
email leaves the machine during the suite** — every `/email/send` and
`/email/test-round` call is a genuine HTTP round-trip to the backend,
which genuinely POSTs to Postal's API contract, just pointed at a local
mock instead of postalserver.io. Tests assert on exactly what the mock
received (`tests/fixtures/mock-postal-client.ts`) — recipient, subject,
plain/html body, reply-to.

If the suite is interrupted before teardown runs (Ctrl-C, crash), the
backend is left on `EMAIL_BACKEND=postal` pointed at a now-dead mock
server. Recovery: restore `.env` from `.env.e2e-backup` if present (it's
created and only deleted by a clean teardown), then
`docker compose up -d --force-recreate backend` from `infra/`.

## Structure

```
e2e/
├── playwright.config.ts
├── tsconfig.json
├── package.json
└── tests/
    ├── draft.spec.ts
    ├── approval.spec.ts
    ├── rejection.spec.ts
    ├── sending.spec.ts
    ├── assessment.spec.ts
    ├── replies.spec.ts
    ├── reply-matching.spec.ts
    ├── status.spec.ts
    ├── threshold.spec.ts
    └── fixtures/
        ├── email-outreach.fixture.ts   # candidate provisioning + API helper functions
        ├── db.ts                        # direct Postgres reads (token, response_due_at) - see below
        ├── mock-postal-server.ts        # the mock server class
        ├── mock-postal-client.ts        # HTTP client tests use to inspect captured sends
        ├── mock-postal-standalone.ts    # entry point run as a detached process
        ├── global-setup.ts
        └── global-teardown.ts
```

`db.ts` reads the DB directly for two things no API exposes: the real
tracking token (needed to simulate a reply against a just-sent email —
`GET /email/status/*` never returns it), and to backdate
`response_due_at` for the threshold job instead of waiting 72 real
hours. Both are the task's own allowed exception ("Database → only when
necessary" for deterministic setup) — production code was not changed
to accommodate this.

## Scenarios covered

- **Draft** (`draft.spec.ts`): valid creation, candidate/job/HR data in
  the rendered body, duplicate-draft 409, unknown candidate 404,
  unknown round 404, assessment round through `/email/draft` → 422.
- **Approval** (`approval.spec.ts`): Approved transition + approver name
  resolution (hr_id → name, not the raw id), HR-edited body preserved
  verbatim through to send, approve-with-no-draft 404, approve-already-
  sent 404 (state unchanged), unknown hr_id 404, approval with no hr_id
  (optional field) still succeeds.
- **Rejection** (`rejection.spec.ts`): Rejected transition, rejected
  draft can't be sent, rejected record stays in history, reject-non-
  existent 404, reject-twice 404.
- **Sending** (`sending.spec.ts`): Sent transition with real 8-char
  token/message_id/response_due_at (~72h), the actual email content the
  mock Postal server received (recipient/subject/body/reply-to), Draft
  can't be sent, already-Sent can't be sent twice (mock server proves
  only one real send happened).
- **Assessment/test-round** (`assessment.spec.ts`): round advances on
  the existing Sent row (no new row created) with the correct
  round_number, assessment link is actually emailed, unknown candidate/
  round 404, a non-assessment round_id is *accepted* by this endpoint
  (documented behavior differs from `/email/draft` — verified, not
  assumed), calling test-round before any Sent email exists fails,
  missing `url` → 422 (Pydantic validation, distinct from the module's
  own 422 on `/email/draft`).
- **Replies** (`replies.spec.ts`): interested/declined/ambiguous
  classification across the task's example phrases, typo tolerance
  ("Intrested, yes pls." → interested), confirmation email sent after
  classification with the correct subject.
- **Reply matching** (`reply-matching.spec.ts`): known-token → correct
  candidate, unknown-token handled safely (no candidate mutated),
  quoted-original-content doesn't flip classification. See
  [Remaining limitations](#remaining-limitations) for what this file
  deliberately does NOT cover.
- **Status/history** (`status.spec.ts`): full field set on both Draft
  and Sent+replied states, unknown candidate 404, chronological history
  ordering across draft→approve→send→reply, reject+redraft producing
  two attempts in history.
- **Threshold** (`threshold.spec.ts`): overdue Sent candidate →
  Inactive, not-yet-due candidate unchanged, already-replied candidate
  not marked inactive despite being overdue, already-Rejected record
  untouched.

## Test results

Two full Playwright runs during development, plus a direct repro of
the one failure against the classifier function itself:

```
Run 1: Total: 50   Passed: 46   Failed: 4   Skipped: 0
  → All 4 failures were the same cause: the default 30s Playwright test
    timeout was too tight for some LLM-classification calls
    (replies.spec.ts). Fixed by raising playwright.config.ts's
    `timeout` to 60s - not a weakened assertion, a corrected timeout
    for a genuinely slow real dependency.
Run 2: Total: 50   Passed: 49   Failed: 1   Skipped: 0
  → 1 genuine application bug found (below), not a test defect - see
    "Issues found". Confirmed non-deterministic (not a flaky test) by
    calling classify_reply_with_source("I don't want to proceed.")
    directly, repeatedly, outside Playwright: one call returned
    "declined" (correct), five immediately following calls all
    returned "interested" (wrong), same process, same input.
Run 3: Total: 50   Passed: 49   Failed: 1   Skipped: 0
  → Same test failed the same way a third time - the LLM classifier
    bug is real and reproducible, not a one-off fluke.
```

Current status: 49/50 tests pass deterministically; the 1 remaining
test can fail depending on the LLM's non-deterministic output for that
specific input, which is an application bug, not a suite defect - see
below.

```
Total:   50
Passed:  49 (deterministic) / 50 (on a favorable LLM call for the flaky one)
Failed:  0-1 (non-deterministic, see "Issues found")
Skipped: 0
Flaky:   1 - "classifies as declined: I don't want to proceed." (replies.spec.ts)
```

## Issues found

### Bug: LLM reply classifier inconsistently misreads a clear decline as "interested"

**Steps to reproduce:**
```python
from app.modules.email_outreach.services.reply_classifier import classify_reply_with_source
classify_reply_with_source("I don't want to proceed.")
```
(or `POST /email/webhook/reply` with that body against any pending token)

**Expected:** `declined` — this phrase has no regex match in
`REPLY_DECLINED_PATTERNS`/`REPLY_INTERESTED_PATTERNS`
(`reply_classifier.py`), so it falls through to the Ollama LLM
(`llama3.2:3b`), whose system prompt explicitly instructs it to
classify a clear decline as `NOT_INTERESTED`.

**Actual:** Non-deterministic. Across repeated calls in the same
session: one call returned `declined` (correct), five immediately
following calls all returned `interested` (wrong) — see terminal output
captured during this task's own investigation. `settings.temperature=0`
is set on the `ChatOllama` client, which should make output
deterministic for a given model+prompt, but this small quantized local
model still shows run-to-run variance on this specific phrasing.

**Impact:** A candidate who clearly declines using non-templated
phrasing (no "not interested", no "decline", no "no thanks" — the
sentence structure "I don't want to X" isn't in
`REPLY_DECLINED_PATTERNS` at all) can be sent an "Interested" automated
confirmation and have their status recorded as `interested`, silently
misrepresenting their actual response. This is worse than the pattern
falling to `needs_review` (which is a safe failure mode elsewhere in
this classifier) — here it's a confident, wrong, automated action.

Two independent fixes worth considering (not made here, since the task
scope is testing, not fixing "actual application behavior" per its own
constraints ["Do not rewrite production code just to satisfy tests"]):
add `\bdon'?t want to\b` / `\bi don'?t want\b` to
`REPLY_DECLINED_PATTERNS` (closes this specific gap deterministically,
no LLM involved), and/or investigate why a `temperature=0` local Ollama
model is non-deterministic on identical input (batching-order effects
on quantized inference are a known cause).

## Remaining limitations

- **Message threading / plus-tag / subject-token reply matching**
  (task section 9) is **not tested**. `services/reply_matcher.py`'s
  three-signal resolution only runs inside
  `GmailPubSubBackend._resolve_new_messages`, which requires a real
  Gmail push notification carrying real raw email bytes. There is no
  HTTP endpoint that accepts raw email bytes for matching —
  `POST /email/webhook/reply` takes an *already-resolved* token and
  never touches `reply_matcher.py`. Testing the three signals would
  require either a real Gmail mailbox (explicitly out of scope per the
  task) or importing the Python parser directly into a Node test, which
  tests the parser in isolation rather than the running application —
  not real E2E coverage, so it wasn't done. `reply-matching.spec.ts`
  documents this in its own file header and tests what the webhook
  boundary *can* cover (known-token association, unknown-token safety,
  quoted-content protection).
- **UI-level testing** (`getByRole`, `getByLabel`, browser navigation,
  responsive/mobile viewport) — not applicable; no UI exists for this
  module. See [Discrepancy from the task's premise](#discrepancy-from-the-tasks-premise).
- **Real Gmail Pub/Sub send/receive path** — not exercised (by design,
  per "do not send real emails"). The `gmail_pubsub` backend's own code
  path (`services/gmail_pubsub_backend.py`) is switched out for the
  suite's duration; its Gmail-specific logic (watch registration,
  Pub/Sub streaming pull) is unverified by this suite. It was manually
  verified working correctly in the session that built this module
  (real container logs show `Gmail watch registered` / `Streaming pull
  started` / real detected replies) — just not by this automated suite.
- **Message-ID / Reply-To assertions on the invite email** partially
  covered (`sending.spec.ts` checks `reply_to` contains the
  candidate_id) but not the full Message-ID round-trip, since that
  requires the threading path noted above.
