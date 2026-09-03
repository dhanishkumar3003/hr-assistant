import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# uvicorn configures its own "uvicorn"/"uvicorn.access" loggers, but
# never touches the root logger - without this, every module's
# logging.getLogger(__name__).info(...) call (e.g. the email_outreach
# reply monitor started below) silently goes nowhere.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from app.db.session import SessionLocal
from app.modules.resume_ingestion.api import router as resume_ingestion_router
from app.modules.resume_ingestion.api import candidates_router
from app.modules.hr_assistant.api import router as hr_assistant_router
from app.modules.email_outreach.api import router as email_outreach_router
from app.modules.email_outreach.repositories.email_repository import EmailRepository
from app.modules.email_outreach.services.sender import EmailSenderService
from app.modules.email_outreach.services.reply_tracker import ReplyTrackerService
from app.modules.voice_interview.api import router as voice_interview_router
from app.modules.technical_interview.api import router as technical_interview_router
from app.modules.dashboard.api import router as dashboard_router
from app.modules.auth.api import router as auth_router

log = logging.getLogger(__name__)


def _run_reply_monitor(stop_event: threading.Event) -> None:
    """
    Background-thread target for the email_outreach reply monitor.

    Opens its own DB session (this runs outside any FastAPI request
    lifecycle, so there's no per-request get_db() to use) and blocks in
    ReplyTrackerService.monitor_forever until stop_event is set on
    app shutdown. Runs regardless of which email backend is configured -
    for "gmail_pubsub" it's the real push listener; for "postal" it's a
    harmless idle loop (Postal's actual reply path is
    POST /email/webhook/reply instead).
    """
    with SessionLocal() as db:
        repo = EmailRepository(db)
        sender = EmailSenderService(repo)
        tracker = ReplyTrackerService(repo, sender)
        try:
            tracker.monitor_forever(stop_event=stop_event)
        except Exception:
            log.exception("Email reply monitor crashed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop_event = threading.Event()
    monitor_thread = threading.Thread(
        target=_run_reply_monitor,
        args=(stop_event,),
        name="email-reply-monitor",
        daemon=True,
    )
    monitor_thread.start()
    log.info("Email reply monitor thread started")

    yield

    stop_event.set()
    # The loop only checks stop_event between iterations, and one
    # iteration can itself block up to IDLE_BACKEND_WAIT_SECONDS (15s) -
    # give it enough headroom to notice and exit cleanly.
    monitor_thread.join(timeout=20)


app = FastAPI(title="HR Assistant POC", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(resume_ingestion_router, prefix="/resumes", tags=["Resume Ingestion"])
app.include_router(candidates_router, prefix="/candidates", tags=["Resume Ingestion"])
app.include_router(hr_assistant_router, prefix="/chat", tags=["HR Assistant"])
app.include_router(email_outreach_router, prefix="/email", tags=["Email Outreach"])
app.include_router(voice_interview_router, prefix="/interview", tags=["Voice Interview"])
app.include_router(technical_interview_router, prefix="/technical-interview", tags=["Technical Interview"])
app.include_router(dashboard_router, prefix="/dashboard", tags=["Dashboard"])
app.include_router(auth_router, prefix="/auth", tags=["Auth"])

@app.get("/health")
def health():
    return {"status": "ok"}
