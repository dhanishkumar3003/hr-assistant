from abc import ABC, abstractmethod

from sqlalchemy.orm import Session

from app.core.models import HrUser


class IUserRepository(ABC):
    @abstractmethod
    def get_by_email(self, email: str) -> HrUser | None: ...

    @abstractmethod
    def create(self, name: str, email: str, hashed_password: str, role: str) -> HrUser: ...

    @abstractmethod
    def count_all(self) -> int: ...


class UserRepository(IUserRepository):
    """Only class allowed to query/write the hr_users table directly."""

    def __init__(self, db: Session):
        self._db = db

    def get_by_email(self, email: str) -> HrUser | None:
        return self._db.query(HrUser).filter(HrUser.email == email, HrUser.is_active == True).first()

    def create(self, name: str, email: str, hashed_password: str, role: str) -> HrUser:
        user = HrUser(name=name, email=email, hashed_password=hashed_password, role=role)
        self._db.add(user)
        self._db.commit()
        self._db.refresh(user)
        return user

    def count_all(self) -> int:
        return self._db.query(HrUser).count()

    