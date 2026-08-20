from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt as pyjwt

from app.shared.security.factory import get_token_service

bearer_scheme = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> dict:
    token_service = get_token_service()
    try:
        payload = token_service.decode_token(credentials.credentials)
        return {"id": payload["sub"], "email": payload["email"], "role": payload["role"]}
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user