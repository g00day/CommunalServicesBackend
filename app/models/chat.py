from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

class Chat(Base):
    __tablename__ = "chat"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), nullable=False, unique=True)

    ticket = relationship("Ticket", back_populates="chat", lazy="selectin")
    participants = relationship("ChatParticipant", back_populates="chat", cascade="all, delete-orphan", lazy="selectin")
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan", lazy="selectin")
