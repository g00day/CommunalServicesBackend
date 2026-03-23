from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Address(Base):
    __tablename__ = "address"

    id: Mapped[int] = mapped_column(primary_key=True)
    street_id: Mapped[int] = mapped_column(ForeignKey("street.id"), nullable=False)
    house_number: Mapped[str] = mapped_column(String(20), nullable=False)

    street = relationship("Street", back_populates="addresses")
    tickets = relationship("Ticket", back_populates="address")
