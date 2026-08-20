from passlib.context import CryptContext

from app.shared.interfaces.password_service import IPasswordService


class BcryptPasswordService(IPasswordService):
    def __init__(self):
        self._context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def hash(self, plain_password: str) -> str:
        return self._context.hash(plain_password)

    def verify(self, plain_password: str, hashed_password: str) -> bool:
        return self._context.verify(plain_password, hashed_password)