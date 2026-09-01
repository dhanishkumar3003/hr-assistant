# email_outreach module — port notes

Ported from a standalone project (`C:\Users\dhanishkumar.v\Desktop\Python Projects\Email automation`,
still intact and unmodified there) into this repo's module layout. No functionality
changes — only file structure, naming, and config access were adapted.

## Layout
- `models.py` — `Email` / `CandidateResponse`, SQLAlchemy 2.0 `Mapped` style, subclass
  shared `app.db.base.Base`. Tables prefixed `email_outreach_*` to avoid name collisions.
- `repositories/email_repository.py` — `IEmailRepository` (ABC) + `EmailRepository`,
  ported 1:1 from the original `state_manager.py` functions.
- `services/` — business logic + infra, one class per file, constructor-injected
  interfaces (matches the `auth` module's pattern):
  - `sender.py`, `reply_tracker.py` — filled pre-existing empty stub files.
  - `response_service.py`, `test_round_service.py` — new files (orchestration layer
    split out, mirroring the original project's `api/services/`).
  - `email_parser.py` + `email_builder.py` — split from the original single
    `email_handler.py` (parse vs. build direction).
  - `tracking_token_service.py` — renamed from `token_manager.py` to avoid colliding
    with the pre-existing `app/shared/interfaces/token_service.py::ITokenService`
    (unrelated JWT-auth concept, same word).
  - `email_backend.py`, `imap_backend.py`, `gmail_backend.py`, `gmail_pubsub_backend.py`,
    `gmail_auth_service.py`, `reply_matcher.py`, `reply_classifier.py`,
    `llm_reply_classifier.py`, `email_template_service.py`, `confirmation_content.py`,
    `candidate_source.py` — direct ports, import paths + config access updated only.
  - `drafter.py`, `approval_gate.py` — filled in to match the POC doc's Module 3
    contract (draft → HR-approve → send gate). No equivalent in the original
    ported project (which sent immediately); these are new, built against the
    existing `Email.status` column (`Draft`/`Approved`/`Sent`/`Rejected`).
  - `threshold_evaluator.py` — still an empty stub; no equivalent in the
    original project, left untouched.
- `schemas.py` — merged from original `api/schemas/response.py` + `test_round.py`,
  plus new `DraftEmailRequest/Response`, `Approve/RejectDraftRequest`, `SendEmailRequest`,
  `EmailStatusResponse`, `ReplyWebhookRequest` for the Module 3 API contract below.
- `api.py` — overwrote the pre-existing `/ping`-only stub. Routes: `GET /respond/{candidate_id}`,
  `POST /test-round` (both pre-existing, kept), plus the full Module 3 doc contract:
  `POST /draft`, `POST /approve`, `POST /reject` (not in doc, added for symmetry),
  `POST /send`, `GET /status/{candidate_id}`, `POST /webhook/reply`. Already wired into
  `app/main.py` under `/email` prefix (pre-existing, no main.py change needed).
- `cli.py` — new (no precedent elsewhere in repo, but needed to preserve CLI-triggered
  functionality). Commands: `send`, `send-from-source`, `monitor`, `monitor-pubsub`.
  Run via `python -m app.modules.email_outreach.cli <command>` from `backend/`.
- `templates/` — the 6 HTML/CSS files copied from the original project's `Email/`.
- Test data moved to `backend/tests/email_outreach/testdata.json` (was
  `app/modules/email_outreach/data/testdata.json` — test fixtures don't belong
  under the module's own package). `Settings.testdata_json_path` default updated
  to match; override in `.env` if needed.

## Shared infra changes
- `app/core/config.py` — new `Settings` fields: `gmail_address`, `gmail_app_password`,
  `email_backend` (imap|gmail_api|gmail_pubsub), `gmail_pubsub_topic`,
  `gmail_pubsub_subscription`, `candidate_source` (json|api), `testdata_json_path`,
  `response_server_base_url`. Reuses pre-existing `ollama_base_url` / `llm_model` for
  the LLM reply classifier (defaults already matched).
- `app/db/migrations/versions/c1a5e0f9b3d2_add_email_outreach_tables.py` — new
  migration, `down_revision = '9336eb4da9d1'` (was sole head at port time — reverify
  with `alembic heads` before running, in case other work has landed since).
- `app/db/migrations/env.py` — added model-import line for autogenerate.
- `pyproject.toml` — added `langchain-ollama`, `google-api-python-client`,
  `google-auth-httplib2`, `google-auth-oauthlib`, `google-cloud-pubsub`.

## Architecture decisions made with the user
- DB: integrated into the shared repo DB (not a separate standalone Postgres) —
  models subclass shared `Base`, use shared `get_db()` / `SessionLocal`.
- Config: Gmail/Ollama/candidate-source settings added alongside the existing
  MS Graph fields on `Settings` — email transport stays Gmail, MS Graph fields
  are unrelated/untouched (they're for a future, different transport).

## Verified
- `python -m py_compile` clean on every new/edited file.
- All modules import successfully with `DATABASE_URL` set (confirmed via direct
  `python -c "from app.modules.email_outreach... import ..."` checks, including the
  Gmail/Pub-Sub/LLM-dependent ones — no missing-import errors).
- Not yet verified: no unit/integration tests run, no live Gmail/DB connection tested.

## Still needed before running for real
1. `uv sync` (or equivalent) to install the 5 new dependencies.
2. Set new `.env` values matching the `Settings` fields above.
3. Place `credentials.json` / `token.json` at this module's root
   (`app/modules/email_outreach/`) if using `gmail_api` / `gmail_pubsub` backend —
   gitignore both, never commit.
4. `alembic upgrade head` to create `email_outreach_emails` and
   `email_outreach_candidate_responses`.

## Module 3 doc-contract additions (this pass)
Per `HR_Assistant_POC_Module_Responsibilities.pdf` §5, the ported project sent
emails immediately (no approval gate) and had no draft/status/webhook API.
Added to close that gap:
- `Email.status` lifecycle: `Draft` -> `Approved` (or `Rejected`) -> `Sent`.
  `EmailRepository`: `save_draft`, `get_draft_by_candidate_id`, `approve_draft`,
  `reject_draft`, `mark_sent`, `get_status_by_candidate_id`.
- `services/drafter.py::EmailDrafter.create_draft` — renders the invite template,
  stores as `Draft`. No token yet (a placeholder `draft-{candidate_id}` fills the
  not-null/unique `token` column) — the real tracking token is only generated at
  send time, since it's embedded in the subject line that goes out.
- `services/approval_gate.py::ApprovalGate.approve/reject` — HR can edit the body
  before approving (`edited_body`); rejecting a draft is terminal.
- `services/sender.py::EmailSenderService.send_approved_draft` — assigns the
  token, appends `[Ref:<token>]` to the draft's subject, sends the stored body
  verbatim (no re-render, so HR edits go out exactly as approved). Uses new
  `email_builder.build_prebuilt_message` (wraps a pre-rendered HTML body with the
  same Message-ID / candidate_id Reply-To tagging as `build_invite_message`).
- `services/reply_tracker.py::ReplyTrackerService.process_reply` — extracted the
  record+classify+confirm sequence out of `monitor_replies`'s loop into its own
  method, called by both the poll/Pub-Sub loop (`check_for_replies`) and the new
  `POST /email/webhook/reply` endpoint. The doc suggests a webhook model; this
  module's primary reply-detection mechanism is still poll/Pub-Sub (see
  `email_backend.py`), but both now converge on one processing path, so swapping
  in a real mail-provider webhook later means calling `process_reply` with its
  parsed payload — no duplicated logic.
- New endpoints in `api.py`: `POST /draft`, `POST /approve`, `POST /reject` (not
  in the doc's table, added for symmetry with approve), `POST /send`,
  `GET /status/{candidate_id}`, `POST /webhook/reply`. Pre-existing `/respond`
  (candidate accept/reject link) and `/test-round` endpoints kept as-is — they're
  extra convenience surfaces, not part of the doc's contract, but nothing in the
  doc says to remove them.
- Not yet done: Module 2 (chatbot) and Module 6 (dashboard) are meant to call
  these through shared service interfaces per the doc's cross-cutting notes —
  this pass only builds Module 3's own API/service layer, not those callers.

## Switched outreach template to reply-only (this pass)
Invite emails now render `templates/interview_call.html` (was
`interview_invitation.html`) - no accept/reject link, candidate responds by
replying to the email and `services/reply_classifier.py` determines interest
from the reply text.
- `email_template_service.py::INVITE_TEMPLATE` -> `interview_call.html`.
- `sender.py::send_invite` no longer builds `accept_link`/`reject_link` into
  the template context (candidate_id is still set - only used for the
  Reply-To plus-tag now, not a link).
- `drafter.py`/`send_approved_draft` unaffected - they already went through
  `render_invite_html`, so they picked up the new template automatically.
- `api.py`'s `GET /respond/{candidate_id}` (click-link flow) and
  `response_service.py` kept in place per explicit instruction, but are now
  dead code - nothing generates a link to that route anymore. Doc's Module 3
  contract has no such endpoint; reply-classifier + webhook is the only
  response path going forward.

## Task-list gap-fill (this pass)
Checked the module against a 13-item task list; these were missing or partial:
- **Rejection draft (#3)**: `services/rejection_drafter.py` - LLM-generated
  (Ollama, same pattern as `llm_reply_classifier.py`) rejection paragraph,
  falls back to a static default if Ollama is unavailable. `drafter.py` now
  branches on `purpose` (`EMAIL_TYPE_CANDIDATE_REJECTION` -> renders
  `templates/candidate_rejection.html` via new `render_rejection_html`;
  template's hardcoded decision paragraph replaced with `{{decision_paragraph}}`).
- **Next-round draft (#2)**: `drafter.py`'s `_SUBJECT_BY_PURPOSE` gives
  `EMAIL_TYPE_NEXT_ROUND_INVITATION` its own subject line (still renders the
  same invite template as initial outreach - no distinct next-round HTML
  template exists yet, only interview_call.html).
- **Postal API (#6)**: `services/postal_backend.py`, new `email_backend`
  option `"postal"`. Send-only (Postal has no fetch API) -
  `fetch_unseen()` always returns `[]`; reply detection still needs IMAP
  polling on the receiving mailbox or the webhook endpoint regardless of
  which backend sends outbound mail. New `Settings` fields:
  `postal_api_url`, `postal_api_key`, `postal_sender_address`.
- **Response-threshold timer (#9) / auto-inactive job (#10)**: filled in
  `services/threshold_evaluator.py` (was an empty stub).
  `response_due_at` (pre-existing `Email` column) is now set at send time
  (`sender.py::send_approved_draft`, `sent_at + settings.response_threshold_hours`,
  new setting, default 72). `EmailRepository.get_overdue_sent_candidate_ids` /
  `mark_inactive` (+ new `STATUS_INACTIVE`) back the job. Runnable via
  `POST /email/threshold/run` or `python -m app.modules.email_outreach.cli
  mark-inactive` - no scheduler/cron infra exists in this repo yet, so
  nothing calls either automatically; wire one of them into whatever
  scheduler the team adopts.
- **Status/history view (#13)**: `GET /email/status/{candidate_id}/history` -
  the outreach email plus every recorded reply against it, oldest first
  (`EmailRepository.get_email_history_by_candidate_id`). `GET
  /email/status/{candidate_id}` (current snapshot) unchanged.
- **Interview-link dispatch (#11)**: no code change - `test_round_service.py`
  already does this (`POST /test-round`), just under different naming from
  the task list.
- **Not done**: #12 approval-queue UI (Next.js frontend) - out of scope for
  this backend-only pass.

## Cleanup pass (dead code removed)
- Deleted `services/response_service.py`, `api.py`'s `GET
  /respond/{candidate_id}` route, and the now-unused `ResponseChoice` schema.
  Dead since the interview_call.html switch (reply-only response model) -
  nothing generated a link to that route anymore. `render_response_html` /
  `get_confirmation_content` are still used (by `email_builder.py::
  build_response_message` / `sender.py::send_confirmation` - the reply-
  classifier confirmation-email flow, unrelated to the deleted click-link
  route), so those stayed.
- Deleted `app/modules/email_outreach/data/` (a stale duplicate
  `testdata.json` left behind by the earlier move to
  `tests/email_outreach/testdata.json` - config only ever read the `tests/`
  copy).
- `templates/interview_invitation.html`/`.css` are unused (superseded by
  `interview_call.html`) but kept on request in case the click-link flow is
  wanted back later.

## Known gap (unresolved)
`EmailRepository`'s "unknown token" cases (`record_reply` / `set_classification`)
dropped the `log.warning(...)` calls the original `state_manager.py` had, on the
reasoning that repositories in this codebase stay logging-free (logging lives at
the service layer, per the `auth` module's convention). Equivalent logging has
**not yet** been added back at the calling service-layer sites — worth doing if
these no-op cases need visibility in production.
