import secrets
from datetime import datetime, timedelta
from uuid import UUID
from app.modules.voice_interview.repositories.access_repository import AccessRepository


class LinkGenerator:
    def __init__(self, access_repo: AccessRepository):
        self.access_repo = access_repo

    def create_link(self, candidate_id: UUID) -> str:
        token = secrets.token_urlsafe(24)
        access_code = f"{secrets.randbelow(1000000):06d}"
        expires_at = datetime.utcnow() + timedelta(days=7)

        self.access_repo.create(candidate_id, token, access_code, expires_at)

        # Stand-in for real email delivery — out of Module 4's scope
        print("=" * 60)
        print(f"[MOCK EMAIL] Interview invitation — candidate {candidate_id}")
        print(f"Link: http://localhost:3000/interview/{token}")
        print(f"Access Code: {access_code}")
        print(f"Expires: {expires_at.isoformat()} UTC")
        print("=" * 60)

        return token

    def authenticate(self, token: str, access_code: str, candidate_id: UUID):
        access = self.access_repo.get_by_token(token)
        if not access:
            return None, "Invalid link or credentials"
        if access.used:
            return None, "This interview link has already been used"
        if access.expires_at < datetime.utcnow():
            return None, "This interview link has expired"
        if access.candidate_id != candidate_id or access.access_code != access_code:
            return None, "Invalid link or credentials"
        return access, None