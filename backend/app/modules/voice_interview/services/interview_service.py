from uuid import UUID
from sqlalchemy.orm import Session
from app.shared.interfaces.interview_service import IInterviewService
from app.modules.voice_interview.repositories.interview_repository import InterviewRepository
from app.modules.voice_interview.repositories.access_repository import AccessRepository
from app.modules.voice_interview.services.link_generator import LinkGenerator


class VoiceInterviewService(IInterviewService):
    def __init__(self, db: Session):
        self.interview_repo = InterviewRepository(db)
        self.link_generator = LinkGenerator(AccessRepository(db))

    def create_link(self, candidate_id: UUID) -> str:
        return self.link_generator.create_link(candidate_id)

    def get_results(self, interview_id: UUID) -> dict | None:
        session = self.interview_repo.get_session(interview_id)
        if not session:
            return None
        answers = self.interview_repo.get_answers(interview_id)
        return {
            "interview_id": str(session.id),
            "candidate_id": str(session.candidate_id),
            "status": session.status,
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
            "overall_score": session.overall_score,
            "answers": [
                {
                    "question_index": a.question_index,
                    "question_text": a.question_text,
                    "transcript": a.transcript_text,
                    "scores": {
                        "relevance": a.relevance,
                        "content_depth": a.content_depth,
                        "structure_clarity": a.structure_clarity,
                        "fluency": a.fluency,
                        "pacing_wpm": a.pacing_wpm,
                        "composite": a.composite_score,
                    },
                    "feedback": a.feedback,
                }
                for a in answers
            ],
        }