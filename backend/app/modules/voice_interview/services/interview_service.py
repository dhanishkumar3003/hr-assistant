from uuid import UUID
from sqlalchemy.orm import Session
from app.shared.interfaces.interview_service import IInterviewService
from app.modules.voice_interview.repositories.interview_repository import InterviewRepository
from app.modules.voice_interview.repositories.access_repository import AccessRepository
from app.modules.voice_interview.services.link_generator import LinkGenerator


class VoiceInterviewService(IInterviewService):
    def __init__(self, db: Session):
        self.interview_repo = InterviewRepository(db)
        self.access_repo = AccessRepository(db)
        self.link_generator = LinkGenerator(self.access_repo)

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

    def _compute_status(self, access, session) -> str:
        if not access.used or session is None:
            return "not_started"
        if session.status == "completed":
            return "completed"
        if session.current_question_index == 0:
            return "started"
        return "in_progress"

    def get_status(self, candidate_id: UUID) -> str:
        access = self.access_repo.get_by_candidate_id(candidate_id)
        if not access:
            return "not_started"
        session = (
            self.interview_repo.get_session(access.interview_session_id)
            if access.interview_session_id else None
        )
        return self._compute_status(access, session)

    def list_statuses(self) -> list[dict]:
        results = []
        for access in self.access_repo.get_all():
            session = (
                self.interview_repo.get_session(access.interview_session_id)
                if access.interview_session_id else None
            )
            results.append({
                "candidate_id": str(access.candidate_id),
                "status": self._compute_status(access, session),
                "overall_score": session.overall_score if session else None,
            })
        return results