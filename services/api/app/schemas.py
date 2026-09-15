from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ViolationType(StrEnum):
    no_helmet = "NO_HELMET"
    no_vest = "NO_VEST"
    no_mask = "NO_MASK"


class ViolationCreate(BaseModel):
    occurred_at: datetime
    camera_id: str = Field(min_length=1, max_length=64)
    track_id: int = Field(ge=0)
    violation_type: ViolationType
    confidence: float = Field(ge=0.0, le=1.0)
    frame_uri: str | None = None


class Violation(ViolationCreate):
    id: int
    event_key: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ViolationCount(BaseModel):
    violation_type: ViolationType
    count: int


class Summary(BaseModel):
    total: int
    by_type: list[ViolationCount]
