import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, ForeignKey, Uuid
from app.db.base import Base


class InterviewSession(Base):
    __tablename__ = "voice_interview_sessions"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    candidate_id = Column(Uuid, nullable=False)
    current_question_index = Column(Integer, default=0)
    status = Column(String, default="in_progress")  # in_progress | completed
    completed_at = Column(DateTime, nullable=True)
    overall_score = Column(Float, nullable=True)


class Answer(Base):
    __tablename__ = "voice_interview_answers"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    interview_id = Column(Uuid, ForeignKey("voice_interview_sessions.id"), nullable=False)
    question_index = Column(Integer, nullable=False)
    question_text = Column(String, nullable=False)
    audio_file_ref = Column(String, nullable=False)
    transcript_text = Column(String)
    answer_start_ts = Column(Float)
    answer_end_ts = Column(Float)
    relevance = Column(Float)
    content_depth = Column(Float)
    structure_clarity = Column(Float)
    fluency = Column(Float)
    pacing_wpm = Column(Float)
    composite_score = Column(Float)
    feedback = Column(String)


class CandidateAccess(Base):
    __tablename__ = "voice_interview_candidate_access"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    candidate_id = Column(Uuid, nullable=False)
    token = Column(String, unique=True, nullable=False)
    access_code = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    interview_session_id = Column(Uuid, nullable=True)