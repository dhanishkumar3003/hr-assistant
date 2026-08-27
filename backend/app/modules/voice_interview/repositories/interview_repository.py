from datetime import datetime
from uuid import UUID
from sqlalchemy.orm import Session
from app.modules.voice_interview.models import InterviewSession, Answer


class InterviewRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_session(self, candidate_id: UUID) -> InterviewSession:
        session = InterviewSession(candidate_id=candidate_id)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_session(self, interview_id: UUID) -> InterviewSession | None:
        return self.db.get(InterviewSession, interview_id)

    def save(self, session: InterviewSession):
        self.db.commit()

    def complete_session(self, session: InterviewSession):
        session.status = "completed"
        session.completed_at = datetime.utcnow()

        answers = self.get_answers(session.id)
        scored = [a.composite_score for a in answers if a.composite_score is not None]
        session.overall_score = round(sum(scored) / len(scored), 1) if scored else None

        self.db.commit()

    def get_answers(self, interview_id: UUID) -> list[Answer]:
        return (
            self.db.query(Answer)
            .filter(Answer.interview_id == interview_id)
            .order_by(Answer.question_index)
            .all()
        )

    def save_answer(self, interview_id, index, question_text, audio_path, transcript, start_ts, end_ts, scores):
        answer = Answer(
            interview_id=interview_id,
            question_index=index,
            question_text=question_text,
            audio_file_ref=audio_path,
            transcript_text=transcript,
            answer_start_ts=start_ts,
            answer_end_ts=end_ts,
            relevance=scores["relevance"],
            content_depth=scores["content_depth"],
            structure_clarity=scores["structure_clarity"],
            fluency=scores["fluency"],
            pacing_wpm=scores["pacing_wpm"],
            composite_score=scores["composite"],
            feedback=scores["feedback"],
        )
        self.db.add(answer)
        self.db.commit()
        return answer