from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings
from app.shared.interfaces.token_service import ITokenService

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 hour HR shift


class JWTTokenService(ITokenService):
    def create_access_token(self, user_id: str, email: str, role: str) -> str:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        payload = {"sub": user_id, "email": email, "role": role, "exp": expire}
        return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)

    def decode_token(self, token: str) -> dict:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])