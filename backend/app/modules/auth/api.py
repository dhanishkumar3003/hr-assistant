from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.core.security import require_admin
from app.modules.auth.repositories.user_repository import UserRepository
from app.modules.auth.services.auth_service import AuthService
from app.modules.auth.schemas import LoginRequest, CreateUserRequest, LoginResponse, UserOut
from app.shared.security.factory import get_password_service, get_token_service

router = APIRouter()


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    """Wires the concrete implementations together for this request.
    This is the ONLY place that knows the concrete classes — everything
    above (AuthService) only ever sees the interfaces."""
    return AuthService(
        user_repo=UserRepository(db),
        password_service=get_password_service(),
        token_service=get_token_service(),
    )


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, auth_service: AuthService = Depends(get_auth_service)):
    return auth_service.login(payload)


@router.post("/admin/create-user", response_model=UserOut)
def create_user(
    payload: CreateUserRequest,
    auth_service: AuthService = Depends(get_auth_service),
    _admin: dict = Depends(require_admin),
):
    return auth_service.create_user(payload)

@router.post("/bootstrap-admin", response_model=UserOut)
def bootstrap_admin(payload: CreateUserRequest, auth_service: AuthService = Depends(get_auth_service)):
    return auth_service.bootstrap_first_admin(payload)