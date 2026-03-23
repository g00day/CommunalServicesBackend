from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class District(Base):
    __tablename__ = "district"

    id: Mapped[int] = mapped_column(primary_key=True)
    uprava_id: Mapped[int] = mapped_column(ForeignKey("uprava.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)

    uprava = relationship("Uprava", back_populates="districts")
    streets = relationship("Street", back_populates="district")
