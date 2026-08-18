
**Golden rule: stay inside your own module folder.** If your feature needs
something from another module (e.g., candidate data, sending an email), call it
through the shared interface in `backend/app/shared/interfaces/` — never import
another module's internal service class directly, and never write to another
module's database table directly.

---

## 8. Database changes (Alembic)

If you add or change a column in any model:

```bash
cd backend
uv run alembic revision --autogenerate -m "describe your change"
uv run alembic upgrade head
```

**Important:** editing a model file alone does **nothing** to the actual database.
You must run both commands above. See `docs/schema.md` for the shared
`CandidateStatus` enum — don't invent new status values without updating that file
first, since Module 6's dashboard reads directly off this enum.

**If you added a new module's `models.py` with real tables:** add an import line
for it in `backend/app/db/migrations/env.py`, or `--autogenerate` won't see your
new tables at all.

---

## 9. Coding conventions (non-negotiable for this POC)

- **SOLID principles, strictly** — see `docs/HR_Assistant_POC_Module_Responsibilities.docx`
  for the exact class breakdown expected in your module.
- **One responsibility per class** — a class that generates questions should not
  also score answers.
- **Depend on interfaces, not concrete classes** — if your module needs another
  module's functionality, depend on the interface in `shared/interfaces/`, not the
  other module's internal implementation.
- **`uv` only for Python deps** — never `pip install` directly. Use `uv add <package>`
  from `backend/`, which updates `pyproject.toml` and `uv.lock` for everyone.
- **Commit `uv.lock`** — this keeps everyone's dependency versions identical.

---

## 10. Common errors and fixes

| Error | Cause | Fix |
|---|---|---|
| `npm error code EJSONPARSE` | `package.json` is empty/invalid | Make sure `frontend/package.json` has real content (see repo) |
| `column "..." does not exist` | Model changed but migration not run | Run the two Alembic commands in Section 8 |
| `could not translate host name "postgres"` | Running backend locally but `.env` says `postgres` instead of `localhost` | Local runs must use `localhost:5432`, not `postgres` — that hostname only resolves inside Docker's network |
| `no lock file found` during Docker build | `uv.lock` missing or not committed | Run `uv sync` locally once, then `git add uv.lock` and commit it |
| Frontend can't reach backend (network error) | `NEXT_PUBLIC_API_BASE_URL` wrong or backend not running | Check `.env`, confirm http://localhost:8000/health responds |
| `ModuleNotFoundError` in backend | Dependency not installed | `cd backend && uv sync` |

---

## 11. Who owns what

| Module | Owner |
|---|---|
| Resume Repository & Ingestion | Ravindhran |
| HR Conversational Assistant (Chatbot) | Devanathan |
| Email Outreach, Approval & Response Tracking | Prasanth |
| AI Voice Interview (Round 1) | Jeeva |
| AI Technical Interview (Round 2) | Dhanish |
| Unified HR Dashboard & Status Monitoring | Dhanvesh |

Full responsibilities, SOLID mapping, and API contracts for each module are in
`docs/HR_Assistant_POC_Module_Responsibilities.docx`.

---

## 12. Getting help

If you're stuck for more than 30 minutes on an environment/setup issue (not your
actual feature logic), post in the team channel before burning more time — most
setup issues in a POC are one wrong env var or one missed migration.