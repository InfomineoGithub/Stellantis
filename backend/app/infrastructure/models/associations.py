from sqlalchemy import Column, ForeignKey, Table
from sqlalchemy.dialects.postgresql import UUID

from app.infrastructure.database import Base

vehicle_sources = Table(
    "vehicle_sources",
    Base.metadata,
    Column("vehicle_id", UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="CASCADE"), primary_key=True),
    Column("source_id",  UUID(as_uuid=True), ForeignKey("sources.id",  ondelete="CASCADE"), primary_key=True),
)
