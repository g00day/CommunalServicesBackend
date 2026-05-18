from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, func
from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), index=True)    
    role = relationship("Role", back_populates="users", lazy="selectin")

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    surname: Mapped[str] = mapped_column(String(100), nullable=False)
    father_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    hash_pass: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    avatar_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    tg_chat_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uprava_id: Mapped[int | None] = mapped_column(ForeignKey("uprava.id"), nullable=True)
    position: Mapped[str | None] = mapped_column(String(120), nullable=True)

    last_login: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_activated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    uprava = relationship("Uprava", back_populates="users", lazy="selectin")
    tickets = relationship("Ticket", back_populates="creator")
    chat_participations = relationship("ChatParticipant", back_populates="user")

    @property
    def full_name(self) -> str:
        parts = [self.surname, self.name]
        if self.father_name:
            parts.append(self.father_name)
        return " ".join(parts)

    @property
    def permission_codes(self) -> set[str]:
        if not self.role:
            return set()
        return {permission.code for permission in self.role.permissions}
