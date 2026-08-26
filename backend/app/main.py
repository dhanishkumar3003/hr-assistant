from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.modules.resume_ingestion.api import router as resume_ingestion_router
from app.modules.hr_assistant.api import router as hr_assistant_router
from app.modules.email_outreach.api import router as email_outreach_router
from app.modules.voice_interview.api import router as voice_interview_router
from app.modules.technical_interview.api import router as technical_interview_router
from app.modules.dashboard.api import router as dashboard_router
from app.modules.auth.api import router as auth_router

app = FastAPI(title="HR Assistant POC")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(resume_ingestion_router, prefix="/resumes", tags=["Resume Ingestion"])
app.include_router(hr_assistant_router, prefix="/chat", tags=["HR Assistant"])
app.include_router(email_outreach_router, prefix="/email", tags=["Email Outreach"])
app.include_router(voice_interview_router, prefix="/interview", tags=["Voice Interview"])
app.include_router(technical_interview_router, prefix="/technical-interview", tags=["Technical Interview"])
app.include_router(dashboard_router, prefix="/dashboard", tags=["Dashboard"])
app.include_router(auth_router, prefix="/auth", tags=["Auth"])

@app.get("/health")
def health():
    return {"status": "ok"}