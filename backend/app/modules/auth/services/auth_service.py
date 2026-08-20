from fastapi import HTTPException

from app.modules.auth.repositories.user_repository import IUserRepository
from app.shared.interfaces.password_service import IPasswordService
from app.shared.interfaces.token_service import ITokenService
from app.modules.auth.schemas import LoginRequest, CreateUserRequest, LoginResponse, UserOut


class AuthService:
    """Orchestrates login and user creation. Depends only on abstractions —
    swap UserRepository, password hashing, or token signing without touching this class."""

    def __init__(self, user_repo: IUserRepository, password_service: IPasswordService, token_service: ITokenService):
        self._user_repo = user_repo
        self._password_service = password_service
        self._token_service = token_service

    def login(self, payload: LoginRequest) -> LoginResponse:
        user = self._user_repo.get_by_email(payload.email)
        if not user or not self._password_service.verify(payload.password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        token = self._token_service.create_access_token(str(user.id), user.email, user.role)
        return LoginResponse(
            access_token=token,
            user=UserOut(id=str(user.id), name=user.name, email=user.email, role=user.role),
        )

    def create_user(self, payload: CreateUserRequest) -> UserOut:
        if self._user_repo.get_by_email(payload.email):
            raise HTTPException(status_code=409, detail="Email already registered")

        hashed = self._password_service.hash(payload.password)
        user = self._user_repo.create(payload.name, payload.email, hashed, payload.role)
        return UserOut(id=str(user.id), name=user.name, email=user.email, role=user.role)

    def bootstrap_first_admin(self, payload: CreateUserRequest) -> UserOut:
        if self._user_repo.count_all() > 0:
            raise HTTPException(status_code=403, detail="Bootstrap already completed. Use admin/create-user instead.")

        hashed = self._password_service.hash(payload.password)
        user = self._user_repo.create(payload.name, payload.email, hashed, role="admin")
        return UserOut(id=str(user.id), name=user.name, email=user.email, role=user.role)