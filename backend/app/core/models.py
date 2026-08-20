import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base



class HrUser(Base):
    __tablename__ = "hr_users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default="hr")  # 'hr', 'technical_evaluator', 'admin'
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)