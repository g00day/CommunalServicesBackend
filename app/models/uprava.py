from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Uprava(Base):
    __tablename__ = "uprava"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)

    districts = relationship("District", back_populates="uprava", lazy="selectin")
    users = relationship("User", back_populates="uprava", lazy="selectin")
