from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel


class SourceType(StrEnum):
    web_url = "web_url"
    youtube_video = "youtube_video"
    pdf = "pdf"


class Source(BaseModel):
    id: UUID
    source_type: SourceType
    url: str
    description: str | None = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class CreateSourceInput(BaseModel):
    source_type: SourceType
    url: str
    description: str | None = None
    is_active: bool = True


class UpdateSourceInput(BaseModel):
    source_type: SourceType | None = None
    url: str | None = None
    description: str | None = None
    is_active: bool | None = None
