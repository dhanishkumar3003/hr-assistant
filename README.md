# HR Assistant POC

An AI-driven hiring assistant. HR interacts through a chatbot to filter candidates,
approve outreach emails, and review AI-scored interviews (voice Round 1 + technical
Round 2) through a single dashboard.

This README assumes you know nothing about the project yet. Follow it top to bottom.

---

## 1. Prerequisites (install these first)

| Tool | Version | Check with |
|---|---|---|
| Docker Desktop | latest | `docker --version` |
| Docker Compose | v2 (bundled with Docker Desktop) | `docker compose version` |
| Python | 3.11+ | `python3 --version` |
| uv | latest | `uv --version` |
| Node.js | 20+ | `node --version` |
| Git | any recent | `git --version` |

**Don't have `uv`?** Install it:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

You do **not** need to install Postgres locally — it runs inside Docker.

---

## 2. Clone the repo

```bash
git clone <repo-url>
cd hr-assistant-poc
```

---

## 3. Set up environment variables

This project uses **one shared `.env` file at the project root** for both backend and
frontend (read by Docker Compose and by the backend directly; the frontend only
picks up its `NEXT_PUBLIC_*` vars).

```bash
cp .env.example .env
```

Open `.env` and fill in the values you have. If you don't have API keys yet
(LLM, STT, Graph API), leave them blank — the app will still boot, you just won't
be able to test those specific features until a key is added.

**Never commit `.env`.** It's already in `.gitignore` — only `.env.example` should
ever be pushed.

---

## 4. Running the project (Docker — recommended)

This is the easiest way. It starts Postgres, the FastAPI backend, and the Next.js
frontend together, all wired to talk to each other.

```bash
cd infra
docker compose up --build
```

First run will take a few minutes (installing dependencies inside the containers).
Subsequent runs are fast.

**Once it's running:**
| Service | URL |
|---|---|
| Backend API | http://localhost:8000 |
| Backend health check | http://localhost:8000/health |
| API docs (Swagger) | http://localhost:8000/docs |
| Frontend | http://localhost:3000 |

**To stop everything:**
```bash
docker compose down
```

**To stop AND wipe the database (fresh start):**
```bash
docker compose down -v
```

---

## 5. Running the backend locally (without Docker, for faster dev loops)

Only do this if you specifically want to debug backend code outside a container.
The database still needs to be running via Docker.

```bash
# 1. Start only Postgres
cd infra
docker compose up postgres -d

# 2. Install backend dependencies
cd ../backend
uv sync

# 3. Run the server
uv run uvicorn app.main:app --reload
```

Your local backend will connect to the same Postgres container via `localhost:5432`.

---

## 6. Running the frontend locally (without Docker)

```bash
cd frontend
npm install
npm run dev
```

Runs on http://localhost:3000. The backend must already be running (either via
Docker or locally per Section 5) for the frontend to have data to call.

---

## 7. Project structure — where do I put my code?

hr-assistant-poc/
├── backend/app/
│ ├── main.py # registers every module's router — don't touch unless adding a new module
│ ├── core/ # config, security — shared, ask before editing
│ ├── db/ # DB session + Alembic migrations — shared
│ ├── shared/ # enums, shared Candidate model, interfaces — READ-ONLY unless the team agrees on a change
│ └── modules/
│ ├── resume_ingestion/ # Ravindhran
│ ├── hr_assistant/ # Devanathan
│ ├── email_outreach/ # Prasanth
│ ├── voice_interview/ # Jeeva
│ ├── technical_interview/ # Dhanish
│ └── dashboard/ # Dhanvesh
│
├── frontend/app/
│ ├── chat/ # Devanathan
│ ├── dashboard/ # Dhanvesh
│ ├── upload/ # Ravindhran
│ ├── interview/[token]/ # Jeeva
│ └── technical-interview/[token]/ # Dhanish
│
├── infra/ # docker-compose.yml, Postgres init
└── docs/ # module responsibility doc, API contracts, schema notes


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