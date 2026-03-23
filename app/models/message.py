from datetime import datetime
from sqlalchemy import ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

class Message(Base):
    __tablename__ = "message"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("chat.id"), nullable=False)
    sender_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    chat = relationship("Chat", back_populates="messages", lazy="selectin")
    sender = relationship("User", lazy="selectin")
    files = relationship("MessageFile", back_populates="message", cascade="all, delete-orphan", lazy="selectin")
