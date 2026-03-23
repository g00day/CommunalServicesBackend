from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

class Ticket(Base):
    __tablename__ = "tickets"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    
    address_id: Mapped[int] = mapped_column(ForeignKey("address.id"), nullable=False)
    status_id: Mapped[int] = mapped_column(ForeignKey("ticket_statuses.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    opened_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    address = relationship("Address", back_populates="tickets", lazy="selectin")
    status = relationship("TicketStatus", back_populates="tickets", lazy="selectin")
    creator = relationship("User", back_populates="tickets", lazy="selectin")
    chat = relationship("Chat", back_populates="ticket", uselist=False, lazy="selectin")
    files = relationship("TicketFile", back_populates="ticket", cascade="all, delete-orphan", lazy="selectin")
    
