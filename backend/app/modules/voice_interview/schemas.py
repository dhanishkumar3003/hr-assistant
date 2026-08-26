from uuid import UUID
from pydantic import BaseModel


class AuthenticateRequest(BaseModel):
    candidate_id: UUID
    token: str
    access_code: str