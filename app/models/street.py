from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Street(Base):
    __tablename__ = "street"

    id: Mapped[int] = mapped_column(primary_key=True)
    district_id: Mapped[int] = mapped_column(ForeignKey("district.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)

    district = relationship("District", back_populates="streets")
    addresses = relationship("Address", back_populates="street")
