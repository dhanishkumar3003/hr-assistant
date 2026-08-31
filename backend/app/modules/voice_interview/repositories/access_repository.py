from uuid import UUID
from sqlalchemy.orm import Session
from app.modules.voice_interview.models import CandidateAccess


class AccessRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, candidate_id: UUID, token: str, access_code: str, expires_at) -> CandidateAccess:
        access = CandidateAccess(
            candidate_id=candidate_id,
            token=token,
            access_code=access_code,
            expires_at=expires_at,
        )
        self.db.add(access)
        self.db.commit()
        return access

    def get_by_token(self, token: str) -> CandidateAccess | None:
        return self.db.query(CandidateAccess).filter(CandidateAccess.token == token).first()

    def get_by_candidate_id(self, candidate_id: UUID) -> CandidateAccess | None:
        return self.db.query(CandidateAccess).filter(CandidateAccess.candidate_id == candidate_id).first()

    def get_all(self) -> list[CandidateAccess]:
        return self.db.query(CandidateAccess).all()

    def mark_used(self, access: CandidateAccess, interview_session_id: UUID):
        access.used = True
        access.interview_session_id = interview_session_id
        self.db.commit()