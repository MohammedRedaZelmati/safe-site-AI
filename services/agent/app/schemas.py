from typing import Any

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)


class AskResponse(BaseModel):
    status: str
    intent: str | None
    sql: str | None
    parameters: list[Any]
    rows: list[dict[str, Any]]
    answer: str
    answer_provider: str


class VisionRequest(BaseModel):
    image_path: str = Field(min_length=1, max_length=500)


class VisionResponse(BaseModel):
    status: str
    model: str
    description: str
