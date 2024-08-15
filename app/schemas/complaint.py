from datetime import datetime
from typing import Optional, Annotated
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, HttpUrl, field_serializer

from ..enums import ComplaintStatus
from .feedback import Feedback


class ComplaintBase(BaseModel):
    type: str
    description: str
    supporting_docs: Annotated[
        Optional[str],
        Field(
            title="Supporting Documents",
            description="List of URLs to the supporting documents separated by space",
        ),
    ]

    @field_serializer("supporting_docs", when_used="json")
    def serialize_supporting_docs(value: Optional[str]) -> list[HttpUrl]:
        urls = value.split(" ") if value else []
        urls = [HttpUrl(url=url) for url in urls]
        return urls


class Complaint(ComplaintBase):
    model_config: ConfigDict = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    created_at: datetime
    status: ComplaintStatus
    feedbacks: list[Feedback]


class ComplaintCountByStatus(BaseModel):
    status: ComplaintStatus
    count: int


class ComplaintCountWithStatusAndTotal(BaseModel):
    new: int
    pending: int
    paused: int
    resolved: int
    total: int
