from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.vehicle import BodyType, FuelType, Transmission, VehicleClass
from app.infrastructure.database import Base
from app.infrastructure.models.associations import vehicle_sources


class VehicleTable(Base):
    __tablename__ = "vehicles"
    __table_args__ = (UniqueConstraint("manufacturer", "model_name", "year"),)

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    manufacturer: Mapped[str] = mapped_column(String, nullable=False)
    model_name: Mapped[str] = mapped_column(String, nullable=False)
    vehicle_class: Mapped[str] = mapped_column(SAEnum(VehicleClass, name="vehicleclass"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    body_type: Mapped[str] = mapped_column(SAEnum(BodyType, name="bodytype"), nullable=False)
    transmission: Mapped[str] = mapped_column(SAEnum(Transmission, name="transmission"), nullable=False)
    fuel_type: Mapped[str] = mapped_column(SAEnum(FuelType, name="fueltype"), nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    sources: Mapped[list["SourceTable"]] = relationship(  # noqa: F821
        "SourceTable",
        secondary=vehicle_sources,
        back_populates="vehicles",
        lazy="noload",
    )
