from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    user_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", lazy="selectin")
