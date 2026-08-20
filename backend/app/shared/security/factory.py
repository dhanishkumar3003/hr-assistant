from functools import lru_cache

from app.shared.interfaces.token_service import ITokenService
from app.shared.interfaces.password_service import IPasswordService
from app.shared.security.jwt_token_service import JWTTokenService
from app.shared.security.bcrypt_password_service import BcryptPasswordService


@lru_cache
def get_token_service() -> ITokenService:
    return JWTTokenService()


@lru_cache
def get_password_service() -> IPasswordService:
    return BcryptPasswordService()