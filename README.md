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