from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.source import SourceType
from app.infrastructure.database import Base
from app.infrastructure.models.associations import vehicle_sources


class SourceTable(Base):
    __tablename__ = "sources"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    source_type: Mapped[str] = mapped_column(SAEnum(SourceType, name="sourcetype"), nullable=False)
    url: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    vehicles: Mapped[list["VehicleTable"]] = relationship(  # noqa: F821
        "VehicleTable",
        secondary=vehicle_sources,
        back_populates="sources",
        lazy="noload",
    )
